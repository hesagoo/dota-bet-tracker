from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu)

from core.calculator import bank_summary
from core.models import (OP_LABELS, OP_DEPOSIT, OP_WITHDRAW, OP_INITIAL, OP_INITIAL_CHANGE)
from core.money import ZERO, q2
from .. import theme
from ..dialogs import AmountDialog, ask, info
from ..fmt import F
from ..widgets import Page, ResponsiveGrid, StatCard, Card, button, label
from .dashboard import tone


class BankPage(Page):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.cards = ResponsiveGrid(240, 3)
        self.c = {}
        for key, title in (("initial", "Начальный банк"), ("current", "Текущий банк"), ("available", "Доступно"),
                           ("reserved", "В активных ставках"), ("dep", "Всего пополнено"), ("wd", "Всего выведено")):
            self.c[key] = self.cards.add(StatCard(title, hero=key == "current"))
        self.col.addWidget(self.cards)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.b_dep = button("＋  Пополнить", "primary")
        self.b_wd = button("−  Вывести")
        self.b_init = button("Изменить начальный банк")
        self.b_dep.clicked.connect(self.deposit)
        self.b_wd.clicked.connect(self.withdraw)
        self.b_init.clicked.connect(self.change_initial)
        for b in (self.b_dep, self.b_wd, self.b_init):
            actions.addWidget(b)
        actions.addStretch()
        self.col.addLayout(actions)

        card = Card("История операций")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Дата", "Операция", "Сумма", "Комментарий"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setMinimumHeight(260)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        card.add(self.table)
        foot = QHBoxLayout()
        foot.addWidget(label("Пополнения и выводы не считаются прибылью или убытком от ставок. "
                             "Изменение начального банка записывается отдельной строкой.", "muted", wrap=True), 1)
        self.b_del = button("Удалить операцию", "danger")
        self.b_del.clicked.connect(self.delete_op)
        foot.addWidget(self.b_del)
        card.body.addLayout(foot)
        self.col.addWidget(card)
        QShortcut(QKeySequence(Qt.Key_Delete), self.table, self.delete_op, context=Qt.WidgetShortcut)
        self.finish()

    def refresh(self):
        sm = self.state.summary
        c = self.c
        c["initial"].set(F.money(sm["initial"]))
        c["current"].set(F.money(sm["current"]), f"Результат ставок: {F.money(sm['bets_result'], True)}")
        c["available"].set(F.money(sm["available"]), "Банк минус зарезервированное")
        c["reserved"].set(F.money(sm["reserved"]))
        c["dep"].set(F.money(sm["deposits"]), "", "win" if sm["deposits"] else None)
        c["wd"].set(F.money(sm["withdrawals"]), "", "loss" if sm["withdrawals"] else None)
        ops = sorted(self.state.ops, key=lambda o: (o.ts, o.id), reverse=True)
        t = self.table
        t.setRowCount(len(ops))
        for r, o in enumerate(ops):
            tn = "win" if o.amount > 0 else ("loss" if o.amount < 0 else "muted")
            vals = [(F.dt(o.ts), None, Qt.AlignLeft), (OP_LABELS[o.kind], None, Qt.AlignLeft),
                    (F.money(o.amount, True), tn, Qt.AlignRight), (o.comment or "—", "muted", Qt.AlignLeft)]
            for ci, (txt, color, al) in enumerate(vals):
                it = QTableWidgetItem(txt)
                it.setData(Qt.UserRole, o.id)
                it.setTextAlignment(al | Qt.AlignVCenter)
                if color:
                    it.setForeground(QColor(theme.P[color]))
                t.setItem(r, ci, it)

    def _sel(self):
        pass        # кнопка всегда активна: при неверном выборе объясняем, что делать

    def _selected(self):
        """Выбранная операция (по выделенной строке или по текущей ячейке)."""
        t = self.table
        rows = {i.row() for i in t.selectedItems()}
        if not rows and t.currentRow() >= 0:
            rows = {t.currentRow()}
        if len(rows) != 1:
            return None
        item = t.item(rows.pop(), 0)
        if item is None:
            return None
        oid = item.data(Qt.UserRole)
        return next((o for o in self.state.ops if o.id == oid), None)

    def deposit(self):
        d = AmountDialog("Пополнение банка", "Сумма пополнения", "Пополнить", parent=self)
        if d.exec():
            self.state.db.add_op(OP_DEPOSIT, d.value, d.comment_text)
            self.state.reload()
            self.state.toast.emit("Банк пополнен")

    def withdraw(self):
        avail = self.state.summary["available"]
        d = AmountDialog("Вывод из банка", "Сумма вывода", "Вывести",
                         f"Доступно для вывода: {F.money(avail)}", limit=max(avail, ZERO),
                         limit_text=f"Нельзя вывести больше доступного баланса ({F.money(avail)})", parent=self)
        if d.exec():
            self.state.db.add_op(OP_WITHDRAW, -d.value, d.comment_text)
            self.state.reload()
            self.state.toast.emit("Вывод записан")

    def change_initial(self):
        old = self.state.summary["initial"]
        d = AmountDialog("Начальный банк", "Новый начальный банк", "Сохранить",
                         f"Сейчас: {F.money(old)}. Изменение будет записано в историю операций; "
                         "прибылью или убытком оно не считается.", initial=F.num(old).replace("\u202f", ""),
                         allow_zero=True, comment_hint="Причина изменения (необязательно)", parent=self)
        if not d.exec():
            return
        delta = d.value - old
        if delta == 0:
            return
        txt = f"Изменение начального банка: {F.money(old)} → {F.money(d.value)}"
        if d.comment_text:
            txt += f". {d.comment_text}"
        self.state.db.add_op(OP_INITIAL_CHANGE, delta, txt)
        self.state.reload()
        self.state.toast.emit("Начальный банк изменён")

    def delete_op(self):
        op = self._selected()
        if op is None:
            info(self, "Выберите операцию", "Сначала щёлкните по нужной строке в истории операций, затем нажмите «Удалить операцию».")
            return
        if op.kind == OP_INITIAL:
            info(self, "Эту запись удалить нельзя",
                 "«Начальный банк» — основа всех расчётов. Чтобы изменить сумму, нажмите «Изменить начальный банк».")
            return
        title = f"«{OP_LABELS[op.kind]}» на {F.money(abs(op.amount))} от {F.dt(op.ts)}"
        text = f"Удалить операцию {title}?\nБанк и вся статистика будут пересчитаны."
        new_current = self.state.summary["current"] - op.amount
        if new_current < 0:
            text += f"\n\nВнимание: после удаления банк станет отрицательным ({F.money(new_current)})."
        if not ask(self, "Удаление операции", text, "Удалить"):
            return
        try:
            self.state.db.delete_op(op.id)
        except Exception as e:
            info(self, "Не удалось удалить", str(e))
            return
        self.state.reload()
        self.state.toast.emit("Операция удалена")

    def _menu(self, pos):
        if self._selected():
            m = QMenu(self)
            m.addAction("Удалить операцию…", self.delete_op)
            m.exec(self.table.viewport().mapToGlobal(pos))
