"""Статистика: все функции принимают уже отфильтрованный по периоду список ставок."""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from .calculator import bet_profit, initial_total
from .models import WIN, LOSS, REFUND, PENDING, INITIAL_KINDS
from .money import q2, ZERO

HUNDRED = Decimal(100)
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
          "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def _pct(a: Decimal, b: Decimal):
    return (a / b * HUNDRED).quantize(Decimal("0.01")) if b else None


def in_range(bets, start: date | None, end: date | None):
    out = []
    for b in bets:
        d = b.placed_at.date()
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(b)
    return out


def compute_stats(bets) -> SimpleNamespace:
    wins = [b for b in bets if b.result == WIN]
    losses = [b for b in bets if b.result == LOSS]
    refunds = [b for b in bets if b.result == REFUND]
    pending = [b for b in bets if b.result == PENDING]
    s = SimpleNamespace()
    s.total, s.wins, s.losses = len(bets), len(wins), len(losses)
    s.refunds, s.pending = len(refunds), len(pending)
    s.gross_profit = sum((bet_profit(b) for b in wins), ZERO)
    s.gross_loss = sum((q2(b.stake) for b in losses), ZERO)
    s.net = s.gross_profit - s.gross_loss
    s.turnover = sum((q2(b.stake) for b in bets), ZERO)
    s.pending_stake = sum((q2(b.stake) for b in pending), ZERO)
    s.risked = sum((q2(b.stake) for b in wins + losses), ZERO)
    s.roi = _pct(s.net, s.risked)
    s.win_rate = _pct(Decimal(s.wins), Decimal(s.wins + s.losses))
    s.settled = s.wins + s.losses
    s.avg_odds = (sum((b.odds for b in bets), Decimal(0)) / len(bets)).quantize(Decimal("0.01")) if bets else None
    s.avg_stake = (s.turnover / len(bets)).quantize(Decimal("0.01")) if bets else None
    s.best_bet = max(wins, key=bet_profit) if wins else None
    s.worst_bet = max(losses, key=lambda b: b.stake) if losses else None
    s.max_profit = bet_profit(s.best_bet) if s.best_bet else None
    s.max_loss = q2(s.worst_bet.stake) if s.worst_bet else None
    s.avg_win = (s.gross_profit / len(wins)).quantize(Decimal("0.01")) if wins else None
    s.avg_loss = (s.gross_loss / len(losses)).quantize(Decimal("0.01")) if losses else None
    s.top_win_odds = max((b.odds for b in wins), default=None)
    s.top_loss_odds = max((b.odds for b in losses), default=None)
    best = cur_w = worst = cur_l = 0
    for b in sorted(bets, key=lambda x: (x.placed_at, x.id or 0)):
        if b.result == WIN:
            cur_w += 1; cur_l = 0
        elif b.result == LOSS:
            cur_l += 1; cur_w = 0
        else:
            continue          # возвраты и ожидающие серию не прерывают
        best, worst = max(best, cur_w), max(worst, cur_l)
    s.win_streak, s.loss_streak = best, worst
    return s


@dataclass
class Row:
    key: object
    label: str
    bets: int = 0
    wins: int = 0
    losses: int = 0
    refunds: int = 0
    pending: int = 0
    profit: Decimal = ZERO
    risked: Decimal = ZERO
    turnover: Decimal = ZERO

    @property
    def roi(self):
        return _pct(self.profit, self.risked)

    @property
    def win_rate(self):
        return _pct(Decimal(self.wins), Decimal(self.wins + self.losses))


def group_stats(bets, keyfn, labelfn, preset=None) -> "OrderedDict":
    rows: "OrderedDict" = OrderedDict()
    for k, lbl in (preset or []):
        rows[k] = Row(k, lbl)
    for b in bets:
        k = keyfn(b)
        r = rows.setdefault(k, Row(k, labelfn(k)))
        r.bets += 1
        r.turnover += q2(b.stake)
        p = bet_profit(b)
        r.profit += p
        if b.result == WIN:
            r.wins += 1; r.risked += q2(b.stake)
        elif b.result == LOSS:
            r.losses += 1; r.risked += q2(b.stake)
        elif b.result == REFUND:
            r.refunds += 1
        else:
            r.pending += 1
    return rows


def by_month(bets):
    rows = group_stats(bets, lambda b: (b.placed_at.year, b.placed_at.month),
                       lambda k: f"{MONTHS[k[1] - 1]} {k[0]}")
    return [rows[k] for k in sorted(rows, reverse=True)]


def by_tournament(bets):
    rows = group_stats(bets, lambda b: (b.tournament or "").strip() or "Без турнира", lambda k: k)
    return sorted(rows.values(), key=lambda r: r.profit, reverse=True)


ODDS_EDGES = [Decimal("1.5"), Decimal("2"), Decimal("2.5"), Decimal("3"), Decimal("4")]
ODDS_LABELS = ["до 1,50", "1,50–1,99", "2,00–2,49", "2,50–2,99", "3,00–3,99", "от 4,00"]


def by_odds(bets):
    rows = group_stats(bets, lambda b: sum(1 for e in ODDS_EDGES if b.odds >= e),
                       lambda k: ODDS_LABELS[k], preset=list(enumerate(ODDS_LABELS)))
    return list(rows.values())


# ---------- банк во времени ----------

def _events(ops, bets):
    ev = [(o.ts, 0, o.id or 0, o.amount, None) for o in ops if o.kind not in INITIAL_KINDS]
    ev += [(b.placed_at, 1, b.id or 0, bet_profit(b), b.id) for b in bets]
    ev.sort(key=lambda e: e[:3])
    return ev


def bank_before_bets(ops, bets) -> dict:
    """Сколько было в банке прямо перед каждой ставкой (нужно для «% от банка»)."""
    bal, out = initial_total(ops), {}
    for ts, _, _, delta, bet_id in _events(ops, bets):
        if bet_id is not None:
            out[bet_id] = bal
        bal += delta
    return out


def bank_curve(ops, bets, start: date | None = None, end: date | None = None, now=None):
    """Точки (время, банк). Начальный банк считается существующим с самого начала."""
    now = now or datetime.now()
    bal = initial_total(ops)
    ev = _events(ops, bets)
    first = ev[0][0] if ev else now
    pts = [(first, bal)]
    for ts, _, _, delta, _ in ev:
        bal += delta
        if delta != 0:
            pts.append((ts, bal))
    start_dt = datetime.combine(start, time.min) if start else pts[0][0]
    end_dt = datetime.combine(end, time.max) if end else max(now, pts[-1][0])
    if end_dt > now and end and end >= now.date():
        end_dt = max(now, pts[-1][0])
    before = pts[0][1]
    for ts, b in pts:
        if ts < start_dt:
            before = b
    out = [(start_dt, before)] + [(ts, b) for ts, b in pts[1:] if start_dt <= ts <= end_dt]
    if out[-1][0] < end_dt:
        out.append((end_dt, out[-1][1]))
    return out


def drawdown(points):
    """Просадка от исторического максимума. Возвращает (ряд в %, макс. сумма, макс. %, текущая сумма, текущий %)."""
    peak = None
    series, max_abs, max_pct = [], ZERO, Decimal(0)
    cur_abs, cur_pct = ZERO, Decimal(0)
    for ts, bal in points:
        peak = bal if peak is None else max(peak, bal)
        dd = peak - bal
        pct = (dd / peak * HUNDRED) if peak > 0 else Decimal(0)
        series.append((ts, -float(pct)))
        max_abs, max_pct = max(max_abs, dd), max(max_pct, pct)
        cur_abs, cur_pct = dd, pct
    return series, max_abs, max_pct.quantize(Decimal("0.01")), cur_abs, cur_pct.quantize(Decimal("0.01"))


def profit_buckets(bets, start: date | None, end: date | None, today: date | None = None):
    """Прибыль по дням (или неделям / месяцам, если период длинный). [(подпись, сумма, подсказка)]"""
    bets = [b for b in bets if b.result in (WIN, LOSS)]
    if not bets:
        return []
    today = today or date.today()
    lo = start or min(b.placed_at.date() for b in bets)
    hi = end or max(today, max(b.placed_at.date() for b in bets))
    span = (hi - lo).days + 1
    if span <= 45:
        mode = "day"
    elif span <= 200:
        mode = "week"
    else:
        mode = "month"

    def key(d: date):
        if mode == "day":
            return d
        if mode == "week":
            return d - timedelta(days=d.weekday())
        return d.replace(day=1)

    sums = {}
    for b in bets:
        k = key(b.placed_at.date())
        sums[k] = sums.get(k, ZERO) + bet_profit(b)
    keys, k = [], key(lo)
    while k <= hi:
        keys.append(k)
        if mode == "day":
            k += timedelta(days=1)
        elif mode == "week":
            k += timedelta(days=7)
        else:
            k = (k.replace(day=28) + timedelta(days=4)).replace(day=1)
    out = []
    for k in keys:
        if mode == "month":
            lbl, tip = f"{k.month:02d}.{k.year}", f"{MONTHS[k.month - 1]} {k.year}"
        elif mode == "week":
            lbl, tip = f"{k.day:02d}.{k.month:02d}", f"Неделя с {k.day:02d}.{k.month:02d}.{k.year}"
        else:
            lbl, tip = f"{k.day:02d}.{k.month:02d}", f"{k.day:02d}.{k.month:02d}.{k.year}"
        out.append((lbl, sums.get(k, ZERO), tip))
    return out
