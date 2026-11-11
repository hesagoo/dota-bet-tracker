"""Базовые элементы интерфейса: карточки, сетка, переключатели."""
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton,
                               QButtonGroup, QScrollArea, QGraphicsOpacityEffect, QSizePolicy)


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


def label(text="", role=None, tone=None, wrap=False):
    l = QLabel(text)
    if role:
        l.setProperty("role", role)
    if tone:
        l.setProperty("tone", tone)
    l.setWordWrap(wrap)
    return l


def button(text, variant=None, tone=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setAutoDefault(False)
    if variant:
        b.setProperty("variant", variant)
    if tone:
        b.setProperty("tone", tone)
    return b


def fade_in(widget, ms=220):
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade = anim
    anim.start()


class StatCard(QFrame):
    def __init__(self, title, hero=False, hint=None):
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("hero", hero)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(3)
        self.title = label(title, "cardtitle")
        self.value = label("—", "valuehero" if hero else "value")
        self.sub = label("", "sub")
        self.sub.setWordWrap(True)
        for w in (self.title, self.value, self.sub):
            lay.addWidget(w)
        lay.addStretch(1)
        self.sub.hide()
        if hint:
            self.setToolTip(hint)

    def set(self, value, sub="", tone=None):
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        self.value.setProperty("tone", tone or "")
        repolish(self.value)


class Card(QFrame):
    def __init__(self, title=None, right=None):
        super().__init__()
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(12)
        if title or right:
            head = QHBoxLayout()
            if title:
                head.addWidget(label(title, "cardhead"))
            head.addStretch()
            if right:
                head.addWidget(right)
            self.body.addLayout(head)

    def add(self, w, **kw):
        self.body.addWidget(w, **kw)
        return w


class ResponsiveGrid(QWidget):
    """Сетка, которая сама меняет число колонок под ширину окна."""

    def __init__(self, min_w=220, max_cols=4, spacing=14):
        super().__init__()
        self.min_w, self.max_cols = min_w, max_cols
        self.items, self._cols = [], 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    def add(self, widget, span=1):
        self.items.append((widget, span))
        self._layout(force=True)
        return widget

    def minimumSizeHint(self):
        h = super().minimumSizeHint()
        return QSize(self.min_w, h.height())

    def _cols_for(self, width):
        return max(1, min(self.max_cols, int(width // self.min_w)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()

    def _layout(self, force=False):
        cols = self._cols_for(self.width() if self.width() > 50 else 900)
        if cols == self._cols and not force:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        r = c = 0
        for w, span in self.items:
            s = min(span, cols)
            if c + s > cols:
                r, c = r + 1, 0
            self.grid.addWidget(w, r, c, 1, s)
            c += s
            if c >= cols:
                r, c = r + 1, 0
        for i in range(10):
            self.grid.setColumnStretch(i, 1 if i < cols else 0)


class Segmented(QWidget):
    changed = Signal(object)

    def __init__(self, options, value=None, tones=None):
        super().__init__()
        self.setObjectName("SegWrap")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.values, self.buttons = [], {}
        for i, (val, text) in enumerate(options):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoDefault(False)
            b.setProperty("seg", True)
            if tones and tones.get(val):
                b.setProperty("tone", tones[val])
            self.group.addButton(b, i)
            self.values.append(val)
            self.buttons[val] = b
            lay.addWidget(b)
        self.group.idClicked.connect(lambda i: self.changed.emit(self.values[i]))
        self.set_value(value if value is not None else options[0][0])

    def value(self):
        i = self.group.checkedId()
        return self.values[i] if i >= 0 else None

    def set_value(self, v):
        if v in self.buttons:
            self.buttons[v].setChecked(True)

    def set_text(self, v, text):
        self.buttons[v].setText(text)


class Page(QScrollArea):
    """Страница с прокруткой и вертикальной колонкой."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self.setWidget(inner)
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(32, 6, 32, 32)
        self.col.setSpacing(16)

    def finish(self):
        self.col.addStretch(1)


class Tile(QPushButton):
    """Крупная выбираемая плитка: заголовок, сумма, подпись."""

    def __init__(self, title, rec=False):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoDefault(False)
        self.setProperty("variant", "tile")
        self.setProperty("rec", rec)
        self.setMinimumHeight(92)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.t = label(title, "cardtitle")
        self.v = label("—", "value")
        self.s = label("", "sub")
        for w in (self.t, self.v, self.s):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(w)

    def set(self, amount_text, sub, enabled):
        self.v.setText(amount_text)
        self.s.setText(sub)
        self.setEnabled(enabled)
