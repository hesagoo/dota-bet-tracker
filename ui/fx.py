"""Визуальные эффекты: свечение кнопок при наведении, уведомления, размытие фона Windows 11 (по желанию).
Всё отключается в настройках; при выключенных анимациях эффекты применяются мгновенно."""
import sys

from PySide6.QtCore import QObject, QEvent, QVariantAnimation, QEasingCurve, QTimer, Qt, QPropertyAnimation, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QFrame, QHBoxLayout, QLabel

from . import theme
from .appearance import A


def _glow_color(btn) -> QColor:
    var, tone = btn.property("variant"), btn.property("tone")
    if tone in ("win", "loss", "refund", "pending") and (var == "mini" or btn.property("seg")):
        key = tone
    elif var == "danger":
        key = "loss"
    elif var in ("primary", "tile", "chip") or btn.property("nav") or btn.property("seg"):
        key = "accent"
    else:
        key = "accent"
    c = QColor(theme.P[key])
    return c


class GlowManager(QObject):
    """Мягкое свечение вокруг кнопок: плавно появляется при наведении, вспыхивает при нажатии."""

    def __init__(self, app):
        super().__init__(app)
        app.installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.Enter, QEvent.Leave, QEvent.MouseButtonPress) and isinstance(obj, QPushButton):
            try:
                if t == QEvent.Enter:
                    self._set(obj, 1.0)
                elif t == QEvent.Leave:
                    self._set(obj, 0.0)
                elif obj.isEnabled():
                    self._pulse(obj)
            except RuntimeError:
                pass
        return False

    # --- внутреннее ---
    @staticmethod
    def _persistent(btn) -> bool:
        return bool(btn.property("nav") and btn.isChecked())

    def _effect(self, btn):
        eff = btn.graphicsEffect()
        if not isinstance(eff, QGraphicsDropShadowEffect):
            if eff is not None:
                return None            # на кнопке уже стоит другой эффект — не мешаем
            eff = QGraphicsDropShadowEffect(btn)
            eff.setOffset(0, 0)
            eff.setBlurRadius(0)
            eff.setColor(QColor(0, 0, 0, 0))
            btn.setGraphicsEffect(eff)
        return eff

    def _apply(self, btn, eff, v):
        c = _glow_color(btn)
        strength = 0.55 if theme.THEME == "light" else 1.0
        c.setAlpha(int(max(0.0, min(1.0, v)) * 150 * strength))
        eff.setColor(c)
        eff.setBlurRadius(4 + 20 * v)

    def _set(self, btn, target):
        if not A.glow or (target and not btn.isEnabled()):
            return
        if not target and self._persistent(btn):
            target = 0.55                                  # выбранный пункт меню светится всегда
        eff = self._effect(btn)
        if eff is None:
            return
        anim = getattr(btn, "_glow_anim", None)
        if anim is not None:
            anim.stop()
        start = getattr(btn, "_glow_v", 0.0)
        ms = A.ms(170)
        if ms == 0:
            self._finish(btn, eff, target)
            return
        anim = QVariantAnimation(btn)
        anim.setStartValue(float(start))
        anim.setEndValue(float(target))
        anim.setDuration(ms)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def step(v):
            try:
                btn._glow_v = float(v)
                self._apply(btn, eff, float(v))
            except RuntimeError:
                pass
        anim.valueChanged.connect(step)
        anim.finished.connect(lambda: self._finish(btn, eff, target))
        btn._glow_anim = anim
        anim.start()

    def _finish(self, btn, eff, target):
        try:
            btn._glow_v = target
            self._apply(btn, eff, target)
            if target == 0.0 and btn.graphicsEffect() is eff:
                btn.setGraphicsEffect(None)                # убираем эффект, чтобы не тратить ресурсы
        except RuntimeError:
            pass

    def _pulse(self, btn):
        if not A.glow or A.ms(1) == 0:
            return
        eff = self._effect(btn)
        if eff is None:
            return
        anim = getattr(btn, "_glow_anim", None)
        if anim is not None:
            anim.stop()
        a = QVariantAnimation(btn)
        a.setStartValue(1.7)
        a.setEndValue(1.0)
        a.setDuration(220)
        a.setEasingCurve(QEasingCurve.OutQuad)
        a.valueChanged.connect(lambda v: self._safe_apply(btn, eff, float(v)))
        a.finished.connect(lambda: self._safe_apply(btn, eff, 1.0 if btn.underMouse() else 0.0, finish=True))
        btn._glow_anim = a
        a.start()

    def _safe_apply(self, btn, eff, v, finish=False):
        try:
            btn._glow_v = v
            self._apply(btn, eff, v)
            if finish and v == 0.0 and not self._persistent(btn) and btn.graphicsEffect() is eff:
                btn.setGraphicsEffect(None)
        except RuntimeError:
            pass

    @staticmethod
    def refresh_nav(buttons):
        """Выбранный пункт меню — постоянное мягкое свечение; остальные — без эффекта."""
        for b in buttons:
            try:
                eff = b.graphicsEffect()
                if b.isChecked() and A.glow:
                    if eff is None:
                        eff = QGraphicsDropShadowEffect(b)
                        eff.setOffset(0, 0)
                        b.setGraphicsEffect(eff)
                    if isinstance(eff, QGraphicsDropShadowEffect):
                        c = QColor(theme.P["accent"])
                        c.setAlpha(80 if theme.THEME != "light" else 45)
                        eff.setColor(c)
                        eff.setBlurRadius(16)
                elif isinstance(eff, QGraphicsDropShadowEffect) and not b.underMouse():
                    b.setGraphicsEffect(None)
            except RuntimeError:
                pass


class Toast(QFrame):
    """Короткое уведомление в правом нижнем углу окна."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 18, 10)
        self.dot = QLabel("●")
        self.dot.setProperty("tone", "accent")
        self.text = QLabel("")
        lay.addWidget(self.dot)
        lay.addWidget(self.text)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._hide)
        self.eff = QGraphicsOpacityEffect(self)
        self.eff.setOpacity(1.0)
        self.anim = None

    def _place(self):
        p = self.parentWidget()
        self.adjustSize()
        self.move(p.width() - self.width() - 28, p.height() - self.height() - 24)

    def show_message(self, text: str, ms: int = 2600):
        self.text.setText(text)
        self._place()
        self.raise_()
        self.show()
        self.timer.start(ms)
        d = A.ms(180)
        if d:
            self.setGraphicsEffect(self.eff)
            self._fade(0.0, 1.0, d, None)
        else:
            self.setGraphicsEffect(None)

    def _fade(self, a, b, d, done):
        if self.anim is not None:
            self.anim.stop()
        self.eff.setOpacity(a)
        anim = QPropertyAnimation(self.eff, b"opacity", self)
        anim.setStartValue(a)
        anim.setEndValue(b)
        anim.setDuration(d)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        if done:
            anim.finished.connect(done)
        self.anim = anim
        anim.start()

    def _hide(self):
        d = A.ms(220)
        if d and self.graphicsEffect() is self.eff:
            self._fade(1.0, 0.0, d, self.hide)
        else:
            self.hide()


def backdrop_supported() -> bool:
    return sys.platform == "win32" and getattr(sys, "getwindowsversion", lambda: None)() is not None \
        and sys.getwindowsversion().build >= 22621


def enable_backdrop(window, mode: str) -> bool:
    """Размытие фона Windows 11 (Mica / Acrylic). Возвращает True, только если система приняла настройку.
    На других системах и при любой ошибке — False, и интерфейс остаётся обычным."""
    if mode not in ("mica", "acrylic") or not backdrop_supported():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.windll.dwmapi
        hwnd = int(window.winId())
        dark = ctypes.c_int(0 if theme.THEME == "light" else 1)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        kind = ctypes.c_int(2 if mode == "mica" else 3)
        r = dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38, ctypes.byref(kind), ctypes.sizeof(kind))

        class MARGINS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]
        m = MARGINS(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(m))
        return r == 0
    except Exception:
        return False
