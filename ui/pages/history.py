from datetime import date

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLineEdit, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QMenu, QFileDialog, QWidget, QVBoxLayout)

from core.calculator import bet_profit
from core.models import (RESULT_LABELS, TYPE_LABELS, PENDING, WIN, LOSS, REFUND, TYPE_SINGLE, TYPE_EXPRESS)
from core.money import ZERO, q2
from services.export import export_csv, export_xlsx
from .. import theme
from ..dialogs import ask, info, BetDialog
from ..fmt import F
from ..widgets import Page, Card, label, button

MIN_DATE = QDate(2000, 1, 1)
COLS = ["Дата", "Тип", "Матч", "Турнир", "Сумма", "Коэф.", "% банка", "Результат", "Итог"]
TONE = {PENDING: "pending", WIN: "win", LOSS: "loss", REFUND: "refund"}


class SortItem(QTableWidgetItem):
    def __lt__(self, other):
        a, b = self.data(Qt.UserRole + 1), other.data(Qt.UserRole + 1)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class HistoryPage(Page):
    def __init__(self, state, window):
        super().__init__()
        self.state, self.window_ = state, window
        self.shown = []
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по матчу, команде или турниру…")
        self.search.setClearButtonEnabled(True)
        self.res = QComboBox()
        for v, t in (("all", "Все результаты"), (WIN, "Выигрыши"), (LOSS, "Проигрыши"), (REFUND, "Возвраты"), (PENDING, "Ожидают расчёта")):
            self.res.addItem(t, v)
        self.typ = QComboBox()
        for v, t in (("all", "Все типы"), (TYPE_SINGLE, "Одиночные"), (TYPE_EXPRESS, "Экспрессы")):
            self.typ.addItem(t, v)
        self.d1, self.d2 = QDateEdit(MIN_DATE), QDateEdit(MIN_DATE)
        for d in (self.d1, self.d2):
            d.setMinimumDate(MIN_DATE)
            d.setCalendarPopup(True)
            d.setSpecialValueText("Любая дата")
            d.setDate(MIN_DATE)
        self.d1.setToolTip("Дата «с»")
        self.d2.setToolTip("Дата «по»")
        reset = button("Сбросить", "ghost")
        reset.clicked.connect(self._reset)
        bar.addWidget(self.search, 3)
        for w in (self.res, self.typ, self.d1, self.d2, reset):
            bar.addWidget(w)
        self.card = Card()
        self.card.body.addLayout(bar)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setMinimumHeight(360)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSortIndicatorShown(True)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 150)
        for c in (4, 5, 6, 8):
            self.table.horizontalHeaderItem(c).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for c in (0, 1, 2, 3, 7):
            self.table.horizontalHeaderItem(c).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.doubleClicked.connect(self._edit)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemSelectionChanged.connect(self._sel)
        self.card.add(self.table)
        foot = QHBoxLayout()
        self.summary = label("", "muted")
        foot.addWidget(self.summary, 1)
        self.b_edit, self.b_del = button("Изменить"), button("Удалить", "danger")
        self.b_exp = button("Экспорт…")
        self.b_edit.clicked.connect(self._edit)
        self.b_del.clicked.connect(self._delete)
        self.b_exp.clicked.connect(self._export)
        for b in (self.b_exp, self.b_edit, self.b_del):
            foot.addWidget(b)
        self.card.body.addLayout(foot)
        self.col.addWidget(self.card, 1)
        self.table.sortByColumn(0, Qt.DescendingOrder)
        self.search.textChanged.connect(self.refresh)
        self.res.currentIndexChanged.connect(self.refresh)
        self.typ.currentIndexChanged.connect(self.refresh)
        self.d1.dateChanged.connect(self.refresh)
        self.d2.dateChanged.connect(self.refresh)
        self._sel()

    def _reset(self):
        self.search.clear()
        self.res.setCurrentIndex(0)
        self.typ.setCurrentIndex(0)
        self.d1.setDate(MIN_DATE)
        self.d2.setDate(MIN_DATE)

    def filtered(self):
        q = self.search.text().strip().lower()
        res, typ = self.res.currentData(), self.typ.currentData()
        a = self.d1.date().toPython() if self.d1.date() > MIN_DATE else None
        b = self.d2.date().toPython() if self.d2.date() > MIN_DATE else None
        out = []
        for x in self.state.bets:
            if res != "all" and x.result != res:
                continue
            if typ != "all" and x.bet_type != typ:
                continue
            d = x.placed_at.date()
            if (a and d < a) or (b and d > b):
                continue
            if q and q not in (x.match + " " + x.tournament + " " + x.comment).lower():
                continue
            out.append(x)
        return out

    def refresh(self):
        keep = set(self._selected_ids())
        bets = self.filtered()
        self.shown = bets
        t = self.table
        t.setSortingEnabled(False)
        t.setRowCount(len(bets))
        for r, b in enumerate(bets):
            p = bet_profit(b)
            bank = self.state.bank_before.get(b.id)
            pct = (b.stake / bank * 100) if bank and bank > 0 else None
            tone = TONE[b.result]
            if b.result == WIN:
                prof, pc = F.money(p, True), "win"
            elif b.result == LOSS:
                prof, pc = F.money(p), "loss"
            elif b.result == REFUND:
                prof, pc = F.money(0), "refund"
            else:
                prof, pc = "—", "pending"
            cells = [
                (F.dt(b.placed_at), b.placed_at, None, Qt.AlignLeft),
                (TYPE_LABELS[b.bet_type], b.bet_type, "muted", Qt.AlignLeft),
                (b.match, b.match.lower(), None, Qt.AlignLeft),
                (b.tournament or "—", b.tournament.lower(), "muted", Qt.AlignLeft),
                (F.money(b.stake), float(b.stake), None, Qt.AlignRight),
                (F.odds(b.odds), float(b.odds), None, Qt.AlignRight),
                (F.pct(pct), float(pct) if pct is not None else -1.0, "muted", Qt.AlignRight),
                ("●  " + RESULT_LABELS[b.result], RESULT_LABELS[b.result], tone, Qt.AlignLeft),
                (prof, float(p), pc, Qt.AlignRight),
            ]
            for c, (text, key, tn, al) in enumerate(cells):
                it = SortItem(text)
                it.setData(Qt.UserRole, b.id)
                it.setData(Qt.UserRole + 1, key)
                it.setTextAlignment(al | Qt.AlignVCenter)
                if tn:
                    it.setForeground(QColor(theme.P[tn]))
                if c == 2:
                    it.setToolTip(b.match + ("\n" + b.comment if b.comment else ""))
                t.setItem(r, c, it)
        t.setSortingEnabled(True)
        if keep:
            for r in range(t.rowCount()):
                if t.item(r, 0).data(Qt.UserRole) in keep:
                    t.selectRow(r)
        net = sum((bet_profit(b) for b in bets), ZERO)
        self.summary.setText(f"Показано ставок: {len(bets)} из {len(self.state.bets)}   ·   итог по показанным: {F.money(net, True)}")
        self._sel()

    def _selected_ids(self):
        rows = {i.row() for i in self.table.selectedItems()}
        return [self.table.item(r, 0).data(Qt.UserRole) for r in sorted(rows)]

    def _sel(self):
        n = len(self._selected_ids())
        self.b_edit.setEnabled(n == 1)
        self.b_del.setEnabled(n >= 1)

    def _bet(self, bid):
        return next((b for b in self.state.bets if b.id == bid), None)

    def _edit(self, *_):
        ids = self._selected_ids()
        if len(ids) != 1:
            return
        self.window_.edit_bet(self._bet(ids[0]))

    def _delete(self):
        ids = self._selected_ids()
        if not ids:
            return
        text = "Удалить выбранную ставку?" if len(ids) == 1 else f"Удалить выбранные ставки ({len(ids)})?"
        if ask(self, "Удаление", text + "\nЕё влияние на банк и статистику будет полностью убрано. Отменить это нельзя.", "Удалить"):
            self.state.db.delete_bets(ids)
            self.state.reload()

    def _menu(self, pos):
        ids = self._selected_ids()
        if not ids:
            return
        m = QMenu(self)
        if len(ids) == 1:
            m.addAction("Изменить…", self._edit)
            m.addSeparator()
        for res in (WIN, LOSS, REFUND, PENDING):
            m.addAction(f"Отметить: {RESULT_LABELS[res].lower()}", lambda r=res: self._set(ids, r))
        m.addSeparator()
        m.addAction("Удалить…", self._delete)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _set(self, ids, res):
        for i in ids:
            self.state.db.set_result(i, res)
        self.state.reload()

    def _export(self):
        if not self.shown:
            info(self, "Экспорт", "Нет ставок для экспорта.")
            return
        path, flt = QFileDialog.getSaveFileName(self, "Экспорт ставок", f"ставки_{date.today():%Y-%m-%d}.xlsx",
                                                "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv") or "csv" in flt.lower() and not path.lower().endswith(".xlsx"):
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                export_csv(path, self.shown, F.date_fmt)
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                export_xlsx(path, self.shown, None, F.date_fmt)
            info(self, "Экспорт", f"Готово: сохранено {len(self.shown)} ставок.\n{path}")
        except Exception as e:
            info(self, "Не удалось сохранить файл", str(e))
