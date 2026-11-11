"""Общее состояние приложения: данные, период, настройки."""
from datetime import date, timedelta

from PySide6.QtCore import QObject, Signal

from core import stats as st
from core.calculator import bank_summary
from .fmt import F

PERIODS = {"7": 7, "30": 30, "90": 90}


class AppState(QObject):
    changed = Signal()
    period_changed = Signal()
    settings_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.bets, self.ops = [], []
        self.summary, self.bank_before = {}, {}
        p = db.get_setting("default_period")
        self.period = (p if p in ("7", "30", "90", "all") else "all", None, None)
        self.apply_settings(emit=False)
        self.reload(emit=False)

    def reload(self, emit=True):
        self.bets = self.db.get_bets()
        self.ops = self.db.get_ops()
        self.summary = bank_summary(self.bets, self.ops)
        self.bank_before = st.bank_before_bets(self.ops, self.bets)
        if emit:
            self.changed.emit()

    def apply_settings(self, emit=True):
        F.currency = self.db.get_setting("currency")
        F.date_fmt = self.db.get_setting("date_fmt")
        if emit:
            self.settings_changed.emit()

    # --- период ---
    def set_period(self, kind, start=None, end=None):
        self.period = (kind, start, end)
        self.period_changed.emit()

    def period_range(self):
        kind, a, b = self.period
        if kind in PERIODS:
            today = date.today()
            return today - timedelta(days=PERIODS[kind] - 1), today
        if kind == "custom":
            return a, b
        return None, None

    def period_bets(self):
        return st.in_range(self.bets, *self.period_range())

    def period_label(self):
        a, b = self.period_range()
        if a is None and b is None:
            return "За всё время"
        return f"{F.date(a)} — {F.date(b)}"

    # --- действия ---
    def set_result(self, bet_id, result):
        self.db.set_result(bet_id, result)
        self.reload()
