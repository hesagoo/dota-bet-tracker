from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt

from core import stats as st
from .. import theme
from ..charts import LineChart, BarChart, DonutChart
from ..fmt import F
from ..widgets import Page, ResponsiveGrid, StatCard, Card, label
from .dashboard import tone

HEAD = ["", "Ставок", "Побед", "Поражений", "Win Rate", "Оборот", "Прибыль", "ROI"]


def make_table():
    t = QTableWidget(0, len(HEAD))
    t.setHorizontalHeaderLabels(HEAD)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    t.setShowGrid(False)
    t.verticalHeader().setDefaultSectionSize(38)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(0, QHeaderView.Stretch)
    return t


def fill(t, rows, first):
    t.horizontalHeaderItem(0).setText(first)
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        vals = [(row.label, None, Qt.AlignLeft), (str(row.bets), None, Qt.AlignRight), (str(row.wins), "win" if row.wins else "muted", Qt.AlignRight),
                (str(row.losses), "loss" if row.losses else "muted", Qt.AlignRight),
                (F.pct(row.win_rate), None, Qt.AlignRight), (F.money(row.turnover), "muted", Qt.AlignRight),
                (F.money(row.profit, True), tone(row.profit) or "muted", Qt.AlignRight),
                (F.pct(row.roi, 1, True), tone(row.roi) or "muted", Qt.AlignRight)]
        for c, (txt, tn, al) in enumerate(vals):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(al | Qt.AlignVCenter)
            if tn:
                it.setForeground(QColor(theme.P[tn]))
            t.setItem(r, c, it)
    t.setFixedHeight(max(90, 44 + 38 * len(rows)))


class AnalyticsPage(Page):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.kpi = ResponsiveGrid(170, 6)
        self.k = {}
        for key, title in (("net", "Чистая прибыль"), ("roi", "ROI"), ("wr", "Win Rate"), ("stake", "Средняя ставка"),
                           ("odds", "Средний коэффициент"), ("dd", "Макс. просадка")):
            self.k[key] = self.kpi.add(StatCard(title))
        self.col.addWidget(self.kpi)

        self.charts = ResponsiveGrid(430, 2)
        self.bank = LineChart(min_h=260)
        self.dd = LineChart("loss", min_h=230)
        self.profit = BarChart(min_h=230)
        self.donut = DonutChart(min_h=230)
        self.dist = BarChart(signed=False, min_h=230)
        self.charts.add(self._wrap("Банк во времени", self.bank), 2)
        self.charts.add(self._wrap("Просадка банка (Drawdown)", self.dd))
        self.charts.add(self._wrap("Прибыль и убытки", self.profit))
        self.charts.add(self._wrap("Выиграно и проиграно", self.donut))
        self.charts.add(self._wrap("Ставки по коэффициентам", self.dist))
        self.col.addWidget(self.charts)

        self.tabs = QTabWidget()
        self.t_month, self.t_tour, self.t_odds = make_table(), make_table(), make_table()
        self.tabs.addTab(self.t_month, "По месяцам")
        self.tabs.addTab(self.t_tour, "По турнирам")
        self.tabs.addTab(self.t_odds, "По коэффициентам")
        self.tabs.currentChanged.connect(lambda _: self._fit())
        c = Card("Детальная статистика")
        c.add(self.tabs)
        self.col.addWidget(c)

        self.extra = ResponsiveGrid(220, 4)
        self.e = {}
        for key, title in (("ws", "Макс. серия побед"), ("ls", "Макс. серия поражений"), ("aw", "Средняя прибыль на выигрыш"),
                           ("al", "Средний убыток на проигрыш"), ("tw", "Самый высокий выигравший коэф."),
                           ("tl", "Самый высокий проигравший коэф."), ("bb", "Самая прибыльная ставка"),
                           ("wb", "Самая убыточная ставка"), ("cd", "Текущая просадка")):
            self.e[key] = self.extra.add(StatCard(title))
        self.col.addWidget(self.extra)
        self.finish()

    def _wrap(self, title, chart):
        c = Card(title)
        c.add(chart)
        return c

    def _fit(self):
        t = self.tabs.currentWidget()
        self.tabs.setFixedHeight(t.height() + 50)

    def refresh(self):
        bets = self.state.period_bets()
        a, b = self.state.period_range()
        s = st.compute_stats(bets)
        k = self.k
        k["net"].set(F.money(s.net, True), self.state.period_label(), tone(s.net))
        k["roi"].set(F.pct(s.roi, 2, True), "", tone(s.roi))
        k["wr"].set(F.pct(s.win_rate), f"{s.wins} из {s.settled}")
        k["stake"].set(F.money(s.avg_stake))
        k["odds"].set(F.odds(s.avg_odds))
        pts = st.bank_curve(self.state.ops, self.state.bets, a, b)
        series, mx, mxp, cur, curp = st.drawdown(pts)
        self.bank.set_data(pts, F.money)
        self.dd.set_data(series, lambda v: F.pct(-v, 2) if v else "0%", include_zero=True, suffix="%")
        k["dd"].set(F.pct(mxp, 2), F.money(mx), "loss" if mx else None)
        buckets = st.profit_buckets(bets, a, b)
        self.profit.set_data([(l, v, t) for l, v, t in buckets], lambda v: F.money(v, True))
        self.donut.set_data([("Выиграно", s.wins, "win"), ("Проиграно", s.losses, "loss"), ("Возвраты", s.refunds, "refund")],
                            F.pct(s.win_rate, 0) if s.win_rate is not None else "—", "Win Rate")
        odds_rows = st.by_odds(bets)
        self.dist.set_data([(r.label, r.bets, f"Коэф. {r.label}") for r in odds_rows], lambda v: f"{int(v)} ставок")
        fill(self.t_month, st.by_month(bets), "Месяц")
        fill(self.t_tour, st.by_tournament(bets), "Турнир")
        fill(self.t_odds, odds_rows, "Коэффициент")
        self._fit()
        e = self.e
        e["ws"].set(str(s.win_streak), "Возвраты серию не прерывают", "win" if s.win_streak else None)
        e["ls"].set(str(s.loss_streak), "", "loss" if s.loss_streak else None)
        e["aw"].set(F.money(s.avg_win), "", "win" if s.avg_win else None)
        e["al"].set(F.money(-s.avg_loss) if s.avg_loss else "—", "", "loss" if s.avg_loss else None)
        e["tw"].set(F.odds(s.top_win_odds))
        e["tl"].set(F.odds(s.top_loss_odds))
        e["bb"].set(F.money(s.max_profit, True), s.best_bet.match if s.best_bet else "", "win" if s.max_profit else None)
        e["wb"].set(F.money(-s.max_loss) if s.max_loss else "—", s.worst_bet.match if s.worst_bet else "", "loss" if s.max_loss else None)
        e["cd"].set(F.pct(curp, 2), F.money(cur), "loss" if cur else None)
