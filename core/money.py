"""Деньги считаем только через Decimal — никаких ошибок округления."""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value).strip().replace(",", ".").replace(" ", "").replace("\u00a0", ""))


def q2(value) -> Decimal:
    return D(value).quantize(CENT, ROUND_HALF_UP)


def parse_decimal(text) -> Decimal:
    """Разбирает ввод пользователя ('1 500,50' или '1500.5'). ValueError, если не число."""
    s = str(text).strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace(",", ".")
    if not s:
        raise ValueError("пусто")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError("не число")
    if not d.is_finite():
        raise ValueError("не число")
    return d
