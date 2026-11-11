from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QKeySequence, QShortcut, QPolygonF
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QPushButton, QLabel, QApplication)

from . import theme
from version import APP_NAME, __version__
from .dialogs import BetDialog, AmountDialog, PeriodDialog, info
from .fmt import F
from .pages.analytics import AnalyticsPage
from .pages.bank import BankPage
from .pages.dashboard import DashboardPage
from .pages.history import HistoryPage
from .pages.settings import SettingsPage
from .widgets import Segmented, button, label, fade_in
from .update_ui import CheckWorker, UpdateDialog
from version import DEFAULT_UPDATE_URL
from core.models import OP_INITIAL
from core.money import q2


def draw_icon(kind, color):
    pm = QPixmap(44, 44)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if kind == "dashboard":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            p.drawRoundedRect(QRectF(x + 1, y + 1, 6.5, 6.5), 2, 2)
    elif kind == "history":
        for i, y in enumerate((5, 11, 17)):
            p.drawEllipse(QPointF(4.5, y), 1, 1)
            p.drawLine(QPointF(9, y), QPointF(19, y))
    elif kind == "analytics":
        p.drawPolyline(QPolygonF([QPointF(3, 4), QPointF(3, 19), QPointF(20, 19)]))
        p.drawPolyline(QPolygonF([QPointF(6.5, 14), QPointF(10, 9.5), QPointF(13, 12.5), QPointF(18.5, 5.5)]))
    elif kind == "bank":
        p.drawRoundedRect(QRectF(2.5, 5.5, 17, 12.5), 3, 3)
        p.drawLine(QPointF(2.5, 9.5), QPointF(19.5, 9.5))
        p.drawEllipse(QPointF(15.5, 13.8), 1.1, 1.1)
    else:
        for y, x in ((5.5, 7), (11, 14.5), (16.5, 9)):
            p.drawLine(QPointF(3, y), QPointF(19, y))
            p.setBrush(QColor(theme.P["sidebar"]))
            p.drawEllipse(QPointF(x, y), 2.2, 2.2)
            p.setBrush(Qt.NoBrush)
    p.end()
    return pm


def make_icon(kind):
    ic = QIcon()
    ic.addPixmap(draw_icon(kind, theme.P["muted"]), QIcon.Normal, QIcon.Off)
    ic.addPixmap(draw_icon(kind, theme.P["accent"]), QIcon.Normal, QIcon.On)
    return ic


class MainWindow(QMainWindow):
    PAGES = [("dashboard", "Дашборд"), ("history", "История"), ("analytics", "Аналитика"), ("bank", "Банк"), ("settings", "Настройки")]

    def __init__(self, state, app):
        super().__init__()
        self.state, self.app = state, app
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1320, 840)
        self.setMinimumSize(1000, 660)
        root = QWidget()
        root.setObjectName("Content")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 22, 16, 18)
        sl.setSpacing(4)
        logo = QLabel("●  Bet Tracker")
        logo.setObjectName("Logo")
        sl.addWidget(logo)
        sl.addSpacing(18)
        self.nav = []
        for i, (key, name) in enumerate(self.PAGES):
            b = QPushButton("   " + name)
            b.setProperty("nav", True)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(22, 22))
            b.clicked.connect(lambda _=False, i=i: self.go(i))
            self.nav.append((key, b))
            sl.addWidget(b)
        sl.addStretch(1)
        self.upd_btn = button("⬆  Доступно обновление", "primary")
        self.upd_btn.hide()
        self.upd_btn.clicked.connect(self.show_update)
        sl.addWidget(self.upd_btn)
        sl.addWidget(label(f"Ctrl+N — новая ставка   ·   v{__version__}", "hint"))
        outer.addWidget(side)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(32, 24, 32, 14)
        head.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = label("", "pagetitle")
        self.subtitle = label("", "pagesub")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        self.period = Segmented([("7", "7 дней"), ("30", "30 дней"), ("90", "90 дней"), ("all", "Всё время"), ("custom", "Период…")],
                                state.period[0])
        self.period.changed.connect(self._period_clicked)
        head.addWidget(self.period)
        self.add_btn = button("＋  Добавить ставку", "primary")
        self.add_btn.clicked.connect(lambda: self.new_bet())
        head.addWidget(self.add_btn)
        rl.addLayout(head)
        self.stack = QStackedWidget()
        self.pages = {
            "dashboard": DashboardPage(state), "history": HistoryPage(state, self),
            "analytics": AnalyticsPage(state), "bank": BankPage(state), "settings": SettingsPage(state, self),
        }
        for key, _ in self.PAGES:
            self.stack.addWidget(self.pages[key])
        rl.addWidget(self.stack, 1)
        outer.addWidget(right, 1)

        self.pages["dashboard"].on_new_bet = self.new_bet
        state.changed.connect(self.refresh_all)
        state.settings_changed.connect(self.refresh_all)
        state.period_changed.connect(self._period_changed)
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.new_bet())
        for i in range(5):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, lambda i=i: self.go(i))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.periodic_backup)
        self.timer.start(30 * 60 * 1000)
        self.apply_icons()
        self.current = 0
        self.go(0, animate=False)
        self.startup_backup()
        self.pending_update = None
        QTimer.singleShot(2500, self.auto_check_updates)

    # --- навигация ---
    def apply_icons(self):
        for key, b in self.nav:
            b.setIcon(make_icon(key))

    def go(self, i, animate=True):
        self.current = i
        key = self.PAGES[i][0]
        for k, (_, b) in enumerate(self.nav):
            b.setChecked(k == i)
        self.stack.setCurrentIndex(i)
        self.title.setText(self.PAGES[i][1])
        self.period.setVisible(key in ("dashboard", "analytics"))
        self.refresh_page(key)
        self._subtitle()
        if animate:
            fade_in(self.pages[key])

    def _subtitle(self):
        key = self.PAGES[self.current][0]
        self.subtitle.setText({"dashboard": self.state.period_label(), "analytics": self.state.period_label(),
                               "history": "Все ставки: поиск, фильтры, редактирование",
                               "bank": "Пополнения, выводы и начальный банк",
                               "settings": "Внешний вид, данные и резервные копии"}[key])

    def refresh_page(self, key):
        self.pages[key].refresh()

    def refresh_all(self):
        for k in self.pages:
            self.pages[k].refresh()
        self._subtitle()

    def apply_theme(self, name):
        theme.apply_theme(self.app, name)
        self.apply_icons()
        self.refresh_all()
        for sg in self.findChildren(Segmented):
            sg.updateGeometry()
            sg.adjustSize()
        for w in self.findChildren(QWidget):
            w.update()

    # --- период ---
    def _period_clicked(self, v):
        if v == "custom":
            a, b = self.state.period[1], self.state.period[2]
            d = PeriodDialog(a, b, self)
            if d.exec():
                self.state.set_period("custom", d.start, d.end)
            else:
                self.period.set_value(self.state.period[0])
            return
        self.state.set_period(v)

    def _period_changed(self):
        kind, a, b = self.state.period
        self.period.set_value(kind)
        self.period.set_text("custom", f"{a:%d.%m}–{b:%d.%m}" if kind == "custom" else "Период…")
        self.refresh_all()

    # --- ставки ---
    def new_bet(self, stake=None):
        stake = stake if isinstance(stake, (int, float)) or hasattr(stake, "quantize") else None
        while True:
            d = BetDialog(self.state, parent=self, stake=stake)
            if not d.exec() or not d.bet:
                return
            self.state.db.add_bet(d.bet)
            self.state.reload()
            if not d.again:
                return
            stake = None

    def edit_bet(self, bet):
        if not bet:
            return
        d = BetDialog(self.state, bet, self)
        if d.exec() and d.bet:
            self.state.db.update_bet(d.bet)
            self.state.reload()

    # --- обновления ---
    def _update_url(self):
        return (self.state.db.get_setting("update_url") or DEFAULT_UPDATE_URL).strip()

    def auto_check_updates(self):
        if self.state.db.get_setting("update_check") == "1" and self._update_url():
            self.check_updates(manual=False)

    def check_updates(self, manual=False):
        url = self._update_url()
        sp = self.pages["settings"]
        if not url:
            if manual:
                sp.upd_status.setText("Укажите адрес обновлений в поле выше.")
            return
        if manual:
            sp.upd_status.setText("Проверяю…")
            sp.upd_btn.setEnabled(False)
        self._chk = CheckWorker(__version__, url)
        self._chk.done.connect(lambda upd, err: self._checked(upd, err, manual))
        self._chk.start()

    def _checked(self, upd, err, manual):
        sp = self.pages["settings"]
        sp.upd_btn.setEnabled(True)
        if err:
            if manual:
                sp.upd_status.setText(err)
            return
        if upd is None:
            self.pending_update = None
            self.upd_btn.hide()
            if manual:
                sp.upd_status.setText(f"У вас последняя версия ({__version__}).")
            return
        self.pending_update = upd
        self.upd_btn.setText(f"⬆  Обновление {upd.version}")
        self.upd_btn.show()
        sp.upd_status.setText(f"Найдена новая версия {upd.version}.")
        if manual:
            self.show_update()

    def show_update(self):
        if self.pending_update:
            UpdateDialog(self.state, self.pending_update, self).exec()

    # --- резервные копии ---
    def _can_backup(self):
        return self.state.db.get_setting("auto_backup") == "1"

    def startup_backup(self):
        db = self.state.db
        try:
            t = db.last_backup_time()
            if self._can_backup() and (db.get_bets() or db.get_ops()) and (t is None or datetime.now() - t > timedelta(hours=1)):
                db.auto_backup("auto")
        except Exception:
            pass

    def periodic_backup(self):
        try:
            if self._can_backup() and self.state.db.dirty:
                self.state.db.auto_backup("auto")
        except Exception:
            pass

    def closeEvent(self, e):
        self.periodic_backup()
        self.state.db.close()
        e.accept()

    def first_run(self):
        if self.state.ops:
            return
        d = AmountDialog("Добро пожаловать!", "Начальный банк", "Начать",
                         "Укажите сумму, с которой вы начинаете вести учёт. Её можно изменить позже на странице «Банк».",
                         initial="0", allow_zero=True, comment_hint="Комментарий (необязательно)", parent=self)
        d.exec()
        self.state.db.add_op(OP_INITIAL, d.value if d.value is not None else q2(0), d.comment_text or "Начальный банк")
        self.state.reload()
