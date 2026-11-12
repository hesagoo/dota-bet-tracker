from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QLabel

from core import stats as st
from core.calculator import bet_profit, stake_options
from core.models import PENDING, WIN, LOSS, REFUND, TYPE_LABELS
from core.money import q2
from ..charts import LineChart
from ..fmt import F
from PySide6.QtWidgets import QButtonGroup
from ..widgets import Page, ResponsiveGrid, StatCard, Card, Tile, label, button, repolish


def tone(v):
    if v is None or v == 0:
        return None
    return "win" if v > 0 else "loss"


class DashboardPage(Page):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.hero = ResponsiveGrid(240, 4)
        self.c_bank = StatCard("Текущий банк", hero=True)
        self.c_avail = StatCard("Доступный баланс", hero=True)
        self.c_reserved = StatCard("Зарезервировано в ставках", hero=True)
        self.c_net = StatCard("Чистая прибыль", hero=True)
        for c in (self.c_bank, self.c_avail, self.c_reserved, self.c_net):
            self.hero.add(c)
        self.col.addWidget(self.hero)

        # --- помощник по размеру ставки ---
        self.on_new_bet = None
        self.sel_pct = 4
        self.helper = Card("Помощник по ставке")
        self.helper_info = label("", "muted", wrap=True)
        self.helper.add(self.helper_info)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.tiles, self.tile_group = {}, QButtonGroup(self)
        for pct, name, rec in ((3, "3% · осторожно", False), (4, "4% · рекомендуется", True), (5, "5% · максимум", False)):
            tile = Tile(name, rec)
            self.tile_group.addButton(tile)
            tile.clicked.connect(lambda _=False, p=pct: self._pick(p))
            self.tiles[pct] = tile
            row.addWidget(tile, 1)
        self.helper.body.addLayout(row)
        foot = QHBoxLayout()
        self.helper_note = label("Инструмент контроля размера ставки, а не гарантия безопасности или прибыли. Выше 5% банка не предлагается.", "hint", wrap=True)
        foot.addWidget(self.helper_note, 1)
        self.use_btn = button("Добавить ставку", "primary")
        self.use_btn.clicked.connect(self._use)
        foot.addWidget(self.use_btn)
        self.helper.body.addLayout(foot)
        self.col.addWidget(self.helper)

        self.chart = LineChart(min_h=250)
        self.chart_card = Card("Динамика банка")
        self.chart_card.add(self.chart)
        self.col.addWidget(self.chart_card)

        self.pending_card = Card("Ожидают расчёта")
        self.pending_box = QVBoxLayout()
        self.pending_box.setSpacing(8)
        self.pending_card.body.addLayout(self.pending_box)
        self.col.addWidget(self.pending_card)

        self.grid = ResponsiveGrid(190, 5)
        names = [("initial", "Начальный банк"), ("gprofit", "Общая прибыль"), ("gloss", "Общий убыток"),
                 ("roi", "ROI"), ("total", "Всего ставок"), ("wins", "Выиграно"), ("losses", "Проиграно"),
                 ("refunds", "Возвраты"), ("wr", "Win Rate"), ("avgodds", "Средний коэффициент"),
                 ("turnover", "Общая сумма ставок"), ("maxp", "Максимальная прибыль"),
                 ("maxl", "Максимальный проигрыш"), ("pend", "Ожидают расчёта"), ("avgstake", "Средняя ставка")]
        self.k = {}
        for key, title in names:
            self.k[key] = self.grid.add(StatCard(title))
        self.col.addWidget(self.grid)
        self.finish()

    def refresh(self):
        s, sm = st.compute_stats(self.state.period_bets()), self.state.summary
        per = self.state.period_label()
        all_time = self.state.period[0] == "all"
        self.c_bank.set(F.money(sm["current"]), "Все операции за всё время")
        self.c_avail.set(F.money(sm["available"]), "Банк минус зарезервированное")
        self.c_reserved.set(F.money(sm["reserved"]), f"Активных ставок: {sum(1 for b in self.state.bets if b.result == PENDING)}")
        self.c_net.set(F.money(s.net, True), per, tone(s.net))
        self.chart.set_data(st.bank_curve(self.state.ops, self.state.bets, *self.state.period_range()),
                            F.money)
        k = self.k
        k["initial"].set(F.money(sm["initial"]), "С учётом изменений")
        k["gprofit"].set(F.money(s.gross_profit), "Только выигрыши", "win" if s.gross_profit else None)
        k["gloss"].set(F.money(s.gross_loss), "Только проигрыши", "loss" if s.gross_loss else None)
        k["roi"].set(F.pct(s.roi, 2, True), "Прибыль / сумма рассчитанных ставок", tone(s.roi))
        k["total"].set(str(s.total), per if not all_time else "")
        k["wins"].set(str(s.wins), "", "win" if s.wins else None)
        k["losses"].set(str(s.losses), "", "loss" if s.losses else None)
        k["refunds"].set(str(s.refunds), "", "refund" if s.refunds else None)
        k["wr"].set(F.pct(s.win_rate, 1), f"из {s.settled} рассчитанных")
        k["avgodds"].set(F.odds(s.avg_odds))
        k["turnover"].set(F.money(s.turnover), "Оборот: все ставки периода")
        k["maxp"].set(F.money(s.max_profit), s.best_bet.match if s.best_bet else "", "win" if s.max_profit else None)
        k["maxl"].set(F.money(-s.max_loss) if s.max_loss else "—", s.worst_bet.match if s.worst_bet else "",
                      "loss" if s.max_loss else None)
        k["pend"].set(str(s.pending), F.money(s.pending_stake) + " в игре" if s.pending else "")
        k["avgstake"].set(F.money(s.avg_stake))
        self._helper()
        self._pending()

    # --- помощник ---
    def _pick(self, pct):
        self.sel_pct = pct
        self._helper()

    def _amount(self):
        opts = {o["pct"]: o for o in stake_options(self.state.summary["available"])}
        return opts[self.sel_pct]["amount"]

    def _helper(self):
        avail = self.state.summary["available"]
        opts = stake_options(avail)
        if avail > 0:
            self.helper_info.setText(f"Доступный банк: {F.money(avail)} (ставки «в игре» — {F.money(self.state.summary['reserved'])} — не учитываются). "
                                     "Суммы округлены до 50 и не превышают 5%.")
        else:
            self.helper_info.setText("Свободных средств нет: доступный банк равен нулю или меньше. Пополните банк или дождитесь расчёта активных ставок.")
        for o in opts:
            tile = self.tiles[o["pct"]]
            ok = o["amount"] is not None
            tile.set(F.money_short(o["amount"]) if ok else "—", f"{o['pct']}% от банка = {F.money(o['raw'])}" if ok else "слишком мало средств", ok)
            tile.setChecked(ok and o["pct"] == self.sel_pct)
        amt = self._amount()
        self.use_btn.setEnabled(amt is not None)
        self.use_btn.setText(f"Добавить ставку на {F.money_short(amt)}" if amt is not None else "Добавить ставку")

    def _use(self):
        amt = self._amount()
        if amt is not None and self.on_new_bet:
            self.on_new_bet(amt)

    def _pending(self):
        while self.pending_box.count():
            it = self.pending_box.takeAt(0)
            w = it.widget()
            if w:
                w.hide()                 # сразу убираем с экрана, не дожидаясь удаления
                w.setParent(None)
                w.deleteLater()
        pend = [b for b in self.state.bets if b.result == PENDING]
        self.pending_card.setVisible(True)
        if not pend:
            self.pending_box.addWidget(label("Нет активных ставок — все рассчитаны.", "muted"))
            return
        for b in sorted(pend, key=lambda x: x.placed_at, reverse=True)[:8]:
            row = QFrame()
            row.setObjectName("PendingRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(14, 8, 10, 8)
            h.setSpacing(8)
            text = QVBoxLayout()
            text.setSpacing(0)
            m = label(b.match)
            m.setMinimumWidth(80)
            text.addWidget(m)
            text.addWidget(label(f"{TYPE_LABELS[b.bet_type]} · {F.money(b.stake)} × {F.odds(b.odds)} · {F.dt(b.placed_at)}", "sub"))
            h.addLayout(text, 1)
            for res, txt, tn in ((WIN, "Выигрыш", "win"), (LOSS, "Проигрыш", "loss"), (REFUND, "Возврат", "refund")):
                btn = button(txt, "mini", tn)
                btn.clicked.connect(lambda _=False, i=b.id, r=res: (self.state.set_result(i, r), self.state.toast.emit("Результат сохранён")))
                h.addWidget(btn)
            self.pending_box.addWidget(row)
        if len(pend) > 8:
            self.pending_box.addWidget(label(f"…и ещё {len(pend) - 8}. Все ставки — на странице «История».", "muted"))
