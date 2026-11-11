"""Вся финансовая логика. Итоги всегда считаются заново из исходных записей,
поэтому редактирование и удаление ставок не могут привести к двойному учёту."""
from decimal import Decimal

from .models import (Bet, WIN, LOSS, REFUND, PENDING, INITIAL_KINDS, OP_DEPOSIT, OP_WITHDRAW)
from .money import q2, ZERO


def validate_bet(match: str, stake: Decimal, odds: Decimal) -> None:
    if not (match or "").strip():
        raise ValueError("Укажите название матча")
    if len(match.strip()) > 150:
        raise ValueError("Название слишком длинное (максимум 150 символов)")
    if stake <= 0:
        raise ValueError("Сумма ставки должна быть больше нуля")
    if stake != q2(stake):
        raise ValueError("Сумма: не больше двух знаков после запятой")
    if stake > Decimal("1000000000"):
        raise ValueError("Слишком большая сумма ставки")
    if odds <= 1:
        raise ValueError("Коэффициент должен быть больше 1,00")
    if odds > Decimal("10000"):
        raise ValueError("Слишком большой коэффициент")
    if odds != odds.quantize(Decimal("0.001")):
        raise ValueError("Коэффициент: не больше трёх знаков после запятой")


def bet_profit(b: Bet) -> Decimal:
    """Чистый результат ставки: выигрыш = сумма × (коэф − 1), проигрыш = −сумма."""
    if b.result == WIN:
        return q2(b.stake * (b.odds - 1))
    if b.result == LOSS:
        return -q2(b.stake)
    return ZERO


def bet_payout(b: Bet) -> Decimal:
    """Сколько денег вернулось на счёт (для справки)."""
    if b.result == WIN:
        return q2(b.stake) + bet_profit(b)
    if b.result == REFUND:
        return q2(b.stake)
    return ZERO


def initial_total(ops) -> Decimal:
    return sum((o.amount for o in ops if o.kind in INITIAL_KINDS), ZERO)


def bank_summary(bets, ops) -> dict:
    initial = initial_total(ops)
    deposits = sum((o.amount for o in ops if o.kind == OP_DEPOSIT), ZERO)
    withdrawals = -sum((o.amount for o in ops if o.kind == OP_WITHDRAW), ZERO)
    bets_result = sum((bet_profit(b) for b in bets), ZERO)
    reserved = sum((q2(b.stake) for b in bets if b.result == PENDING), ZERO)
    current = initial + deposits - withdrawals + bets_result
    return {
        "initial": initial, "deposits": deposits, "withdrawals": withdrawals,
        "bets_result": bets_result, "current": current,
        "reserved": reserved, "available": current - reserved,
    }


# ---------- помощник по размеру ставки ----------
from decimal import ROUND_HALF_UP, ROUND_FLOOR

STAKE_PCTS = (3, 4, 5)
MAX_STAKE_PCT = Decimal(5)       # жёсткий предел: рекомендаций выше 5% нет
STAKE_STEP = Decimal(50)         # округление до удобных сумм


def stake_options(available, step: Decimal = STAKE_STEP):
    """Рекомендуемые суммы ставки (3%, 4%, 5% от ДОСТУПНОГО банка: ставки «в игре» не считаются свободными).

    Сумма округляется до ближайших `step`, но никогда не превышает ни 5% банка, ни доступный остаток:
    если округление вверх пробивает лимит — округляем вниз. Для совсем маленького банка берём целые единицы.
    Возвращает [{'pct', 'raw', 'amount'}], amount=None, если разумной суммы нет."""
    avail = max(Decimal(available), Decimal(0))
    limit = min(avail * MAX_STAKE_PCT / 100, avail)
    out = []
    for pct in STAKE_PCTS:
        raw = avail * pct / 100
        amount = (raw / step).to_integral_value(ROUND_HALF_UP) * step
        if amount > limit:
            amount = (limit / step).to_integral_value(ROUND_FLOOR) * step
        if amount <= 0:
            amount = min(raw.to_integral_value(ROUND_FLOOR), limit)
        out.append({"pct": pct, "raw": q2(raw), "amount": q2(amount) if amount > 0 else None})
    return out
