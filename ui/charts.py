"""Собственные графики на QPainter: линия, столбцы, кольцо. Всегда строятся по реальным данным."""
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont, QFontMetrics)
from PySide6.QtWidgets import QWidget

from . import theme
from .fmt import F, NB


def col(key, alpha=None):
    c = QColor(theme.P[key])
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def nice_ticks(lo, hi, n=4):
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = mag * 10
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    first = math.floor(lo / step) * step
    ticks, v = [], first
    while v < hi + step * 0.999:
        ticks.append(round(v, 10))
        v += step
        if len(ticks) > 12:
            break
    return ticks, step


def axis_fmt(v, step=1.0, suffix=""):
    a = abs(v)
    if a >= 1e6:
        s = f"{v / 1e6:g}M"
    elif a >= 1e4:
        s = f"{v / 1e3:g}k"
    elif step < 1:
        s = f"{v:.1f}".replace(".", ",")
    else:
        s = f"{v:,.0f}".replace(",", NB)
    return s.replace("-", "−") + suffix


class ChartBase(QWidget):
    LEFT, TOP, RIGHT, BOTTOM = 56, 14, 14, 30

    def __init__(self, min_h=230):
        super().__init__()
        self.setMinimumHeight(min_h)
        self.setMouseTracking(True)
        self.hover_x = None
        self.empty_text = "Нет данных за выбранный период"

    def plot(self):
        return QRectF(self.LEFT, self.TOP, max(10, self.width() - self.LEFT - self.RIGHT),
                      max(10, self.height() - self.TOP - self.BOTTOM))

    def mouseMoveEvent(self, e):
        self.hover_x = e.position().x()
        self.update()

    def leaveEvent(self, e):
        self.hover_x = None
        self.update()

    def _small(self, p):
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)

    def _empty(self, p):
        p.setPen(col("faint"))
        p.drawText(self.rect(), Qt.AlignCenter, self.empty_text)

    def _grid(self, p, rect, ticks, step, y_of, suffix=""):
        self._small(p)
        fm = p.fontMetrics()
        for t in ticks:
            y = y_of(t)
            p.setPen(QPen(col("border_soft" if abs(t) > 1e-9 else "border"), 1))
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            p.setPen(col("faint"))
            txt = axis_fmt(t, step, suffix)
            p.drawText(QRectF(0, y - 9, self.LEFT - 8, 18), Qt.AlignRight | Qt.AlignVCenter, txt)

    def _tooltip(self, p, anchor, lines):
        self._small(p)
        fm = p.fontMetrics()
        w = max(fm.horizontalAdvance(t) for t in lines) + 20
        h = len(lines) * 17 + 12
        x = anchor.x() + 12
        if x + w > self.width() - 4:
            x = anchor.x() - w - 12
        y = min(max(anchor.y() - h / 2, 2), self.height() - h - 2)
        r = QRectF(x, y, w, h)
        p.setPen(QPen(col("border"), 1))
        p.setBrush(col("card2"))
        p.drawRoundedRect(r, 8, 8)
        for i, t in enumerate(lines):
            p.setPen(col("text" if i else "muted"))
            p.drawText(QRectF(x + 10, y + 6 + i * 17, w - 14, 17), Qt.AlignLeft | Qt.AlignVCenter, t)


class LineChart(ChartBase):
    def __init__(self, tone="accent", min_h=230):
        super().__init__(min_h)
        self.tone, self.points = tone, []
        self.value_fmt = lambda v: f"{v:.2f}"
        self.include_zero, self.suffix = False, ""

    def set_data(self, points, value_fmt=None, include_zero=False, tone=None, suffix=""):
        self.points = [(t, float(v)) for t, v in points]
        if value_fmt:
            self.value_fmt = value_fmt
        self.include_zero, self.suffix = include_zero, suffix
        if tone:
            self.tone = tone
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pts = self.points
        if not pts:
            return self._empty(p)
        rect = self.plot()
        xs = [t.timestamp() for t, _ in pts]
        ys = [v for _, v in pts]
        x0, x1 = min(xs), max(xs)
        if x1 - x0 < 1:
            x0, x1 = x0 - 43200, x1 + 43200
        lo, hi = min(ys), max(ys)
        if self.include_zero:
            lo, hi = min(lo, 0), max(hi, 0)
        if hi - lo < 1e-9:
            pad = max(abs(hi) * 0.05, 1)
            lo, hi = lo - pad, hi + pad
        else:
            pad = (hi - lo) * 0.08
            hi += pad
            if not (self.include_zero and lo >= 0) and not (self.include_zero and lo == 0):
                lo -= pad
        ticks, step = nice_ticks(lo, hi)
        lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
        lo, hi = ticks[0], ticks[-1]
        y_of = lambda v: rect.bottom() - (v - lo) / (hi - lo) * rect.height()
        x_of = lambda x: rect.left() + (x - x0) / (x1 - x0) * rect.width()
        self._grid(p, rect, ticks, step, y_of, self.suffix)
        # подписи по оси X
        span = x1 - x0
        fmt = "%d.%m %H:%M" if span <= 2 * 86400 else ("%m.%Y" if span > 550 * 86400 else "%d.%m")
        from datetime import datetime
        p.setPen(col("faint"))
        for i in range(5):
            x = x0 + span * i / 4
            txt = datetime.fromtimestamp(x).strftime(fmt)
            px = x_of(x)
            fm = p.fontMetrics()
            w = fm.horizontalAdvance(txt)
            tx = min(max(px - w / 2, 0), self.width() - w)
            p.drawText(QPointF(tx, self.height() - 9), txt)
        color = col(self.tone)
        path = QPainterPath()
        coords = [QPointF(x_of(x), y_of(y)) for x, y in zip(xs, ys)]
        path.moveTo(coords[0])
        for c in coords[1:]:
            path.lineTo(c)
        base = y_of(0) if (lo <= 0 <= hi and self.include_zero) else rect.bottom()
        fill = QPainterPath(path)
        fill.lineTo(coords[-1].x(), base)
        fill.lineTo(coords[0].x(), base)
        fill.closeSubpath()
        g = QLinearGradient(0, rect.top(), 0, rect.bottom())
        g.setColorAt(0, col(self.tone, 90))
        g.setColorAt(1, col(self.tone, 0))
        p.fillPath(fill, QBrush(g))
        p.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setBrush(color)
        p.setPen(QPen(col("card"), 2))
        p.drawEllipse(coords[-1], 4.5, 4.5)
        if self.hover_x is not None and rect.left() <= self.hover_x <= rect.right():
            i = min(range(len(coords)), key=lambda k: abs(coords[k].x() - self.hover_x))
            c = coords[i]
            p.setPen(QPen(col("faint"), 1, Qt.DashLine))
            p.drawLine(QPointF(c.x(), rect.top()), QPointF(c.x(), rect.bottom()))
            p.setPen(QPen(col("card"), 2))
            p.setBrush(color)
            p.drawEllipse(c, 5, 5)
            self._tooltip(p, c, [F.dt(pts[i][0]), self.value_fmt(pts[i][1])])


class BarChart(ChartBase):
    """items: [(подпись, значение, подсказка)]"""

    def __init__(self, signed=True, min_h=230):
        super().__init__(min_h)
        self.items, self.signed = [], signed
        self.value_fmt = lambda v: f"{v:.2f}"
        self.suffix = ""

    def set_data(self, items, value_fmt=None, suffix=""):
        self.items = [(a, float(b), c) for a, b, c in items]
        if value_fmt:
            self.value_fmt = value_fmt
        self.suffix = suffix
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        items = self.items
        if not items or all(v == 0 for _, v, _ in items) and self.signed:
            return self._empty(p)
        rect = self.plot()
        vals = [v for _, v, _ in items]
        lo, hi = min(min(vals), 0), max(max(vals), 0)
        ticks, step = nice_ticks(lo, hi if hi > lo else lo + 1)
        lo, hi = ticks[0], ticks[-1]
        y_of = lambda v: rect.bottom() - (v - lo) / (hi - lo) * rect.height()
        self._grid(p, rect, ticks, step, y_of, self.suffix)
        n = len(items)
        slot = rect.width() / n
        bw = max(3.0, min(slot * 0.62, 46))
        zero = y_of(0)
        hov = None
        if self.hover_x is not None and rect.left() <= self.hover_x <= rect.right():
            hov = min(n - 1, int((self.hover_x - rect.left()) / slot))
        every = max(1, math.ceil(46 / slot))
        self._small(p)
        for i, (lbl, v, tip) in enumerate(items):
            cx = rect.left() + slot * (i + 0.5)
            y = y_of(v)
            top, bottom = (y, zero) if v >= 0 else (zero, y)
            r = QRectF(cx - bw / 2, top, bw, max(bottom - top, 0))
            key = ("win" if v >= 0 else "loss") if self.signed else "accent"
            c = col(key, 255 if i == hov else 205)
            if r.height() > 0:
                path = QPainterPath()
                path.addRoundedRect(r, min(5, bw / 2), min(5, bw / 2))
                p.fillPath(path, c)
            if i % every == 0:
                p.setPen(col("faint"))
                p.drawText(QRectF(cx - slot * every / 2, self.height() - 22, slot * every, 18), Qt.AlignCenter, lbl)
        if hov is not None:
            lbl, v, tip = items[hov]
            cx = rect.left() + slot * (hov + 0.5)
            self._tooltip(p, QPointF(cx, y_of(v)), [tip or lbl, self.value_fmt(v)])


class DonutChart(ChartBase):
    def __init__(self, min_h=230):
        super().__init__(min_h)
        self.slices, self.center, self.center_sub = [], "", ""
        self.empty_text = "Пока нет рассчитанных ставок"

    def set_data(self, slices, center="", sub=""):
        self.slices = [s for s in slices]
        self.center, self.center_sub = center, sub
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        total = sum(v for _, v, _ in self.slices)
        if total <= 0:
            return self._empty(p)
        d = min(self.height() - 20, self.width() * 0.5, 230)
        ring = QRectF(16, (self.height() - d) / 2, d, d)
        th = d * 0.16
        arc = ring.adjusted(th / 2, th / 2, -th / 2, -th / 2)
        start = 90 * 16
        gap = 3 * 16 if sum(1 for _, v, _ in self.slices if v) > 1 else 0
        for lbl, v, key in self.slices:
            if v <= 0:
                continue
            span = int(-360 * 16 * v / total)
            p.setPen(QPen(col(key), th, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(arc, start, span + gap if span + gap < 0 else span)
            start += span
        f = QFont(self.font())
        f.setPixelSize(24)
        f.setBold(True)
        p.setFont(f)
        p.setPen(col("text"))
        p.drawText(QRectF(ring.left(), ring.center().y() - 24, d, 30), Qt.AlignCenter, self.center)
        f.setPixelSize(11)
        f.setBold(False)
        p.setFont(f)
        p.setPen(col("muted"))
        p.drawText(QRectF(ring.left(), ring.center().y() + 6, d, 18), Qt.AlignCenter, self.center_sub)
        # легенда
        x = ring.right() + 28
        y = self.height() / 2 - len(self.slices) * 15
        f.setPixelSize(13)
        p.setFont(f)
        for lbl, v, key in self.slices:
            p.setBrush(col(key))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, y + 5, 10, 10), 3, 3)
            p.setPen(col("text"))
            p.drawText(QRectF(x + 18, y, 140, 20), Qt.AlignLeft | Qt.AlignVCenter, f"{lbl}: {int(v)}")
            y += 30
