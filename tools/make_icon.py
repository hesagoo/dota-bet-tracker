"""Создаёт assets/icon.ico (и icon.png). Запуск: python tools/make_icon.py
Хотите свою иконку — просто положите свой файл ICO в assets/icon.ico (этот скрипт запускать не нужно)."""
import os, struct, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt, QBuffer, QIODevice, QPointF, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QLinearGradient, QPen, QBrush, QPolygonF, QFont

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(s: int) -> QImage:
    img = QImage(s, s, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#1B2033"))
    g.setColorAt(1, QColor("#0D0F14"))
    p.setBrush(QBrush(g))
    p.setPen(QPen(QColor("#2C3350"), max(1, s / 64)))
    r = s * 0.02
    p.drawRoundedRect(QRectF(r, r, s - 2 * r, s - 2 * r), s * 0.22, s * 0.22)
    # график-стрелка вверх
    pts = [(0.20, 0.68), (0.38, 0.52), (0.52, 0.62), (0.78, 0.30)]
    pen = QPen(QColor("#7C9CFF"), s * 0.075, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(x * s, y * s) for x, y in pts]))
    ax, ay = pts[-1][0] * s, pts[-1][1] * s
    p.setBrush(QColor("#4CC38A"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(ax, ay), s * 0.075, s * 0.075)
    # буква D снизу
    f = QFont("Segoe UI", 1)
    f.setPixelSize(int(s * 0.26))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#E8EAF0"))
    p.drawText(QRectF(0, s * 0.70, s, s * 0.24), Qt.AlignCenter, "DBT")
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def main():
    app = QGuiApplication([])
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(exist_ok=True)
    pngs = [(s, png_bytes(render(s))) for s in SIZES]
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, data = b"", b""
    for s, b in pngs:
        entries += struct.pack("<BBBBHHII", 0 if s >= 256 else s, 0 if s >= 256 else s, 0, 0, 1, 32, len(b), offset)
        offset += len(b)
        data += b
    (out / "icon.ico").write_bytes(head + entries + data)
    render(256).save(str(out / "icon.png"))
    print("Готово:", out / "icon.ico")


if __name__ == "__main__":
    main()
