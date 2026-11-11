"""Форматирование чисел, денег и дат с учётом настроек."""
from decimal import Decimal

from core.money import q2

NB = "\u202f"


class Fmt:
    def __init__(self):
        self.currency = "₽"
        self.date_fmt = "%d.%m.%Y"

    @property
    def qt_date(self) -> str:
        return self.date_fmt.replace("%d", "dd").replace("%m", "MM").replace("%Y", "yyyy")

    @property
    def qt_datetime(self) -> str:
        return self.qt_date + " HH:mm"

    def num(self, v, digits=2) -> str:
        if v is None:
            return "—"
        d = Decimal(str(v))
        s = f"{abs(d):,.{digits}f}".replace(",", "\x00").replace(".", ",").replace("\x00", NB)
        return ("−" if d < 0 and float(d) != 0 else "") + s

    def money(self, v, sign=False) -> str:
        if v is None:
            return "—"
        v = q2(v)
        cur = f"\u00a0{self.currency}" if self.currency else ""
        body = self.num(abs(v)) + cur
        if v < 0:
            return "−" + body
        return ("+" + body) if sign and v > 0 else body

    def money_short(self, v) -> str:
        """Без копеек, если сумма целая (для подсказок по ставке)."""
        v = q2(v)
        if v == v.to_integral_value():
            cur = f"\u00a0{self.currency}" if self.currency else ""
            return self.num(v, 0) + cur
        return self.money(v)

    def pct(self, v, digits=1, sign=False) -> str:
        if v is None:
            return "—"
        t = self.num(abs(Decimal(str(v))), digits) + "%"
        if Decimal(str(v)) < 0:
            return "−" + t
        return ("+" + t) if sign and Decimal(str(v)) > 0 else t

    def odds(self, v) -> str:
        if v is None:
            return "—"
        d = Decimal(str(v))
        s = f"{d:f}"
        if "." in s:
            s = s.rstrip("0")
            if len(s.split(".")[1]) < 2:
                s = f"{d:.2f}"
        else:
            s += ".00"
        return s.replace(".", ",")

    def date(self, d) -> str:
        return d.strftime(self.date_fmt)

    def dt(self, d) -> str:
        return d.strftime(self.date_fmt + " %H:%M")


F = Fmt()
