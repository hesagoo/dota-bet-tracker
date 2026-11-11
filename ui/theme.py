"""Цвета и стили (тёмная и светлая тема)."""
from string import Template

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF

from core.paths import data_dir

DARK = dict(
    bg="#0D0F14", sidebar="#11141B", card="#171A23", card2="#1E2230", input="#12151D",
    border="#252A39", border_soft="#1E2230", text="#E8EAF0", muted="#8C93A8", faint="#586079",
    accent="#7C9CFF", accent_hover="#92AEFF", on_accent="#0D1020",
    win="#4CC38A", loss="#E5646E", refund="#E3B341", pending="#8FA3C7",
)
LIGHT = dict(
    bg="#F3F4F8", sidebar="#FFFFFF", card="#FFFFFF", card2="#F0F2F7", input="#F7F8FB",
    border="#E1E4EC", border_soft="#EDEFF4", text="#1B1F2B", muted="#6B7389", faint="#A0A6B8",
    accent="#4F6BED", accent_hover="#6179F0", on_accent="#FFFFFF",
    win="#1FA971", loss="#D8444F", refund="#B9830A", pending="#6B7FA6",
)
P: dict = {}
THEME = "dark"


def tint(hexcolor: str, alpha: float) -> str:
    c = QColor(hexcolor)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def tone_color(tone: str) -> str:
    return P.get(tone or "", P["text"])


def _icons():
    d = data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)

    def chevron(path, color):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(color), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)]))
        p.end()
        pm.save(str(path))

    def tick(path):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(P["on_accent"]), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(6, 12.5), QPointF(10.5, 17), QPointF(18, 7.5)]))
        p.end()
        pm.save(str(path))

    a, t = d / f"arrow_{THEME}.png", d / f"tick_{THEME}.png"
    chevron(a, P["muted"])
    tick(t)
    return a.as_posix(), t.as_posix()


QSS = Template("""
QWidget { color: $text; font-size: 13px; }
QMainWindow, QDialog, #Content { background: $bg; }
QLabel { background: transparent; }
QToolTip { background: $card2; color: $text; border: 1px solid $border; padding: 6px 8px; border-radius: 6px; }

#Sidebar { background: $sidebar; border-right: 1px solid $border; }
#Logo { font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }
QLabel[role="pagetitle"] { font-size: 24px; font-weight: 700; }
QLabel[role="pagesub"] { color: $muted; font-size: 12px; }
QLabel[role="dialogtitle"] { font-size: 19px; font-weight: 700; }
QLabel[role="cardhead"] { font-size: 14px; font-weight: 600; }
QLabel[role="cardtitle"] { color: $muted; font-size: 12px; font-weight: 500; }
QLabel[role="value"] { font-size: 21px; font-weight: 700; }
QLabel[role="valuehero"] { font-size: 28px; font-weight: 700; }
QLabel[role="sub"], QLabel[role="muted"] { color: $muted; font-size: 12px; }
QLabel[role="field"] { color: $muted; font-size: 12px; font-weight: 500; }
QLabel[role="error"] { color: $loss; font-size: 12px; }
QLabel[role="preview"] { color: $muted; font-size: 12px; }
QLabel[role="hint"] { color: $faint; font-size: 11px; }
QLabel[tone="win"] { color: $win; }
QLabel[tone="loss"] { color: $loss; }
QLabel[tone="refund"] { color: $refund; }
QLabel[tone="pending"] { color: $pending; }
QLabel[tone="accent"] { color: $accent; }
QLabel[tone="muted"] { color: $muted; }

#Card, #StatCard { background: $card; border: 1px solid $border; border-radius: 14px; }
#StatCard:hover { border-color: $faint; }
#StatCard[hero="true"] { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $card, stop:1 $accent_bg0); }
QPushButton[variant="tile"] { text-align: left; padding: 0; border-radius: 12px; background: $card2; border: 1px solid $border; }
QPushButton[variant="tile"][rec="true"] { border: 1px solid $accent_bd; }
QPushButton[variant="tile"]:hover { border-color: $faint; }
QPushButton[variant="tile"]:checked { background: $accent_bg; border: 1px solid $accent; }
QPushButton[variant="tile"]:disabled { background: $card; }
QPushButton[variant="chip"] { padding: 4px 10px; font-size: 12px; border-radius: 12px; background: $card2; }
QPushButton[variant="chip"]:hover { border-color: $accent; color: $accent; }
#PendingRow { background: $card2; border-radius: 10px; }

QPushButton { background: $card2; border: 1px solid $border; border-radius: 9px; padding: 8px 14px; font-weight: 500; }
QPushButton:hover { border-color: $faint; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $faint; }
QPushButton[variant="primary"] { background: $accent; border: none; color: $on_accent; font-weight: 600; padding: 9px 18px; }
QPushButton[variant="primary"]:hover { background: $accent_hover; }
QPushButton[variant="danger"] { color: $loss; }
QPushButton[variant="danger"]:hover { border-color: $loss; }
QPushButton[variant="ghost"] { background: transparent; border: none; color: $muted; padding: 6px 8px; }
QPushButton[variant="ghost"]:hover { color: $text; }
QPushButton[variant="mini"] { padding: 4px 10px; font-size: 12px; border-radius: 7px; }
QPushButton[variant="mini"][tone="win"] { color: $win; }
QPushButton[variant="mini"][tone="loss"] { color: $loss; }
QPushButton[variant="mini"][tone="refund"] { color: $refund; }
QPushButton[nav="true"] { text-align: left; padding: 11px 14px; border: none; background: transparent; color: $muted; border-radius: 10px; font-weight: 500; }
QPushButton[nav="true"]:hover { background: $card2; color: $text; }
QPushButton[nav="true"]:checked { background: $accent_bg; color: $accent; font-weight: 600; }
QPushButton[seg="true"] { background: transparent; border: none; border-radius: 8px; padding: 6px 14px; color: $muted; font-weight: 500; }
QPushButton[seg="true"]:hover { color: $text; }
QPushButton[seg="true"]:checked { background: $card2; color: $text; border: 1px solid $border; }
QPushButton[seg="true"][tone="win"]:checked { background: $win_bg; color: $win; border: 1px solid $win_bd; }
QPushButton[seg="true"][tone="loss"]:checked { background: $loss_bg; color: $loss; border: 1px solid $loss_bd; }
QPushButton[seg="true"][tone="refund"]:checked { background: $refund_bg; color: $refund; border: 1px solid $refund_bd; }
QPushButton[seg="true"][tone="pending"]:checked { background: $pending_bg; color: $pending; border: 1px solid $pending_bd; }
#SegWrap { background: $input; border: 1px solid $border; border-radius: 11px; }

QLineEdit, QDateEdit, QDateTimeEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: $input; border: 1px solid $border; border-radius: 9px; padding: 8px 10px; selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:focus, QDateEdit:focus, QDateTimeEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border-color: $accent; }
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down { border: none; width: 26px; }
QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow { image: url($arrow); width: 12px; height: 12px; }
QComboBox QAbstractItemView, QListView { background: $card; border: 1px solid $border; selection-background-color: $accent_bg; selection-color: $text; padding: 4px; outline: 0; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QCalendarWidget QWidget { background: $card; }
QCalendarWidget QAbstractItemView { selection-background-color: $accent; selection-color: $on_accent; }
QCalendarWidget QToolButton { background: transparent; border: none; padding: 4px 8px; }

QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid $border; border-radius: 5px; background: $input; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($tick); }

QTableWidget { background: transparent; border: none; gridline-color: transparent; selection-background-color: transparent; alternate-background-color: transparent; }
QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid $border_soft; }
QTableWidget::item:selected { background: $accent_bg; color: $text; }
QTableWidget::item:hover { background: $card2; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: $muted; border: none; border-bottom: 1px solid $border; padding: 10px 8px; font-weight: 600; font-size: 12px; }
QTableCornerButton::section { background: transparent; border: none; }

QTabWidget::pane { border: none; top: 8px; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 16px; margin-right: 4px; border-radius: 8px; font-weight: 500; }
QTabBar::tab:selected { background: $card2; color: $text; }
QTabBar::tab:hover { color: $text; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $faint; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: $card; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: $accent_bg; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QMessageBox { background: $bg; }
QMessageBox QLabel { color: $text; }
""")


def apply_theme(app, name: str = "dark"):
    global THEME
    THEME = "light" if name == "light" else "dark"
    P.clear()
    P.update(LIGHT if THEME == "light" else DARK)
    arrow, tick = _icons()
    vals = dict(P, arrow=arrow, tick=tick, accent_bg=tint(P["accent"], 0.16), accent_bg0=tint(P["accent"], 0.10))
    vals["accent_bd"] = tint(P["accent"], 0.50)
    for k in ("win", "loss", "refund", "pending"):
        vals[k + "_bg"] = tint(P[k], 0.14)
        vals[k + "_bd"] = tint(P[k], 0.45)
    f = QFont()
    for fam in ("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"):
        f.setFamily(fam)
        break
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(13)
    app.setFont(f)
    app.setStyleSheet(QSS.safe_substitute(vals))
