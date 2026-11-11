from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

PENDING, WIN, LOSS, REFUND = "pending", "win", "loss", "refund"
RESULT_LABELS = {PENDING: "Ожидает", WIN: "Выигрыш", LOSS: "Проигрыш", REFUND: "Возврат"}

TYPE_SINGLE, TYPE_EXPRESS = "single", "express"
TYPE_LABELS = {TYPE_SINGLE: "Одиночная", TYPE_EXPRESS: "Экспресс"}

OP_INITIAL, OP_INITIAL_CHANGE = "initial", "initial_change"
OP_DEPOSIT, OP_WITHDRAW = "deposit", "withdraw"
OP_LABELS = {
    OP_INITIAL: "Начальный банк",
    OP_INITIAL_CHANGE: "Изменение начального банка",
    OP_DEPOSIT: "Пополнение",
    OP_WITHDRAW: "Вывод",
}
INITIAL_KINDS = (OP_INITIAL, OP_INITIAL_CHANGE)


@dataclass
class Bet:
    id: Optional[int]
    placed_at: datetime
    match: str
    tournament: str
    bet_type: str
    stake: Decimal
    odds: Decimal
    result: str = PENDING
    comment: str = ""


@dataclass
class BankOp:
    id: Optional[int]
    ts: datetime
    kind: str
    amount: Decimal   # со знаком: пополнение и начальный банк > 0, вывод < 0
    comment: str = ""
