"""Фоновый слой окна: глубокий градиент с мягкой подсветкой и лёгкий световой след курсора.
След рисуется ПОЗАДИ карточек и кнопок, поэтому не перекрывает текст и не мешает работе."""
import math
import random

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QPixmap, QCursor, QLinearGradient, QBrush
from PySide6.QtWidgets import QWidget

from . import theme
from .appearance import A

MAX_PARTICLES = 48


class AmbientBackground(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Content")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.particles = []          # [x, y, возраст_мс, срок_мс, размер, vx, vy]
        self.last = None
        self.backdrop_ok = False     # включено ли размытие Windows (тогда фон частично прозрачен)
        self._cache = None
        self._cache_key = None
        self._dirty = QRect()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.sync()

    # --- настройки ---
    def sync(self):
        """Вызывается при смене темы и настроек: сбрасывает кэш и запускает/останавливает эффект."""
        self._cache = None
        if A.trail:
            if not self.timer.isActive():
                self.timer.start(40)
        else:
            self.timer.stop()
            self.particles.clear()
            self.last = None
        self.update()

    # --- кэш фона ---
    def _build_cache(self):
        dpr = self.devicePixelRatioF()
        w, h = max(1, self.width()), max(1, self.height())
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        base = QColor(theme.P["bg"])
        if self.backdrop_ok:
            base.setAlpha(int(255 * (1 - 0.6 * A.glass / 100)))
        p.fillRect(0, 0, w, h, base)
        light = theme.THEME == "light"
        acc = QColor(theme.P["accent"])
        big = max(w, h)
        g1 = QRadialGradient(QPointF(w * 0.88, -h * 0.12), big * 0.75)
        c = QColor(acc); c.setAlpha(34 if not light else 30)
        g1.setColorAt(0, c)
        c2 = QColor(acc); c2.setAlpha(0)
        g1.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, QBrush(g1))
        g2 = QRadialGradient(QPointF(w * 0.02, h * 1.1), big * 0.6)
        n = QColor(255, 255, 255, 14) if not light else QColor(80, 90, 120, 18)
        g2.setColorAt(0, n)
        n0 = QColor(n); n0.setAlpha(0)
        g2.setColorAt(1, n0)
        p.fillRect(0, 0, w, h, QBrush(g2))
        p.end()
        self._cache = pm
        self._cache_key = (w, h, dpr)

    def paintEvent(self, e):
        key = (self.width(), self.height(), self.devicePixelRatioF())
        if self._cache is None or self._cache_key != key:
            self._build_cache()
        p = QPainter(self)
        p.setClipRect(e.rect())
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawPixmap(0, 0, self._cache)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self.particles and A.trail:
            p.setRenderHint(QPainter.Antialiasing)
            light = theme.THEME == "light"
            if not light:
                p.setCompositionMode(QPainter.CompositionMode_Plus)
            acc = QColor(theme.P["accent"])
            for x, y, age, life, size, vx, vy in self.particles:
                t = age / life
                a = (1 - t) ** 2
                r = size * (1 + 0.8 * t)
                grad = QRadialGradient(QPointF(x, y), r)
                c = QColor(acc)
                c.setAlpha(int((135 if not light else 95) * a))
                grad.setColorAt(0, c)
                c0 = QColor(acc); c0.setAlpha(0)
                grad.setColorAt(1, c0)
                p.setBrush(QBrush(grad))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, y), r, r)
        p.end()

    # --- след курсора ---
    def _tick(self):
        dt = self.timer.interval()
        win = self.window()
        pos = None
        if A.trail and win is not None and win.isActiveWindow():
            lp = self.mapFromGlobal(QCursor.pos())
            if self.rect().contains(lp):
                pos = QPointF(lp)
        moved = False
        if pos is not None:
            if self.last is not None:
                dx, dy = pos.x() - self.last.x(), pos.y() - self.last.y()
                dist = math.hypot(dx, dy)
                if dist > 2:
                    steps = min(6, int(dist // 14) + 1)       # при быстром движении — несколько точек вдоль пути
                    for i in range(1, steps + 1):
                        k = i / steps
                        self._spawn(self.last.x() + dx * k, self.last.y() + dy * k)
                    moved = True
            self.last = pos
        else:
            self.last = None
        if not self.particles:
            self.timer.setInterval(60 if not moved else 33)
            return
        self.timer.setInterval(33)
        dirty = None
        keep = []
        for pt in self.particles:
            r = pt[4] * 2.2 + 4
            rect = QRect(int(pt[0] - r), int(pt[1] - r), int(2 * r), int(2 * r))
            dirty = rect if dirty is None else dirty.united(rect)
            pt[2] += dt
            pt[0] += pt[5] * dt / 1000
            pt[1] += pt[6] * dt / 1000
            if pt[2] < pt[3]:
                keep.append(pt)
                r = pt[4] * 2.2 + 4
                dirty = dirty.united(QRect(int(pt[0] - r), int(pt[1] - r), int(2 * r), int(2 * r)))
        self.particles = keep
        if dirty is not None:
            self.update(dirty)

    def _spawn(self, x, y):
        if len(self.particles) >= MAX_PARTICLES:
            self.particles.pop(0)
        self.particles.append([x + random.uniform(-3, 3), y + random.uniform(-3, 3), 0.0, random.uniform(600, 1000),
                               random.uniform(10, 22), random.uniform(-8, 8), random.uniform(-8, 8)])
