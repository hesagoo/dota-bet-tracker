"""Диалоги: ставка, сумма, период, восстановление."""
from datetime import datetime, date
from decimal import Decimal

from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QWidget,
                               QDateEdit, QDateTimeEdit, QCompleter, QListWidget, QListWidgetItem, QFileDialog)

from core.calculator import validate_bet, bet_profit, stake_options
from core.models import (Bet, PENDING, WIN, LOSS, REFUND, TYPE_SINGLE, TYPE_EXPRESS, RESULT_LABELS)
from core.money import parse_decimal, q2
from .fmt import F
from .widgets import Segmented, label, button


def ask(parent, title, text, yes="Да", no="Отмена"):
    m = QMessageBox(parent)
    m.setWindowTitle(title)
    m.setText(text)
    m.setIcon(QMessageBox.Question)
    y = m.addButton(yes, QMessageBox.AcceptRole)
    n = m.addButton(no, QMessageBox.RejectRole)
    m.setDefaultButton(n)
    m.exec()
    return m.clickedButton() is y


def info(parent, title, text, icon=QMessageBox.Information):
    m = QMessageBox(parent)
    m.setWindowTitle(title)
    m.setText(text)
    m.setIcon(icon)
    m.addButton("Понятно", QMessageBox.AcceptRole)
    m.exec()


def _field(text, widget):
    box = QVBoxLayout()
    box.setSpacing(5)
    box.addWidget(label(text, "field"))
    box.addWidget(widget)
    return box


class BetDialog(QDialog):
    TONES = {PENDING: "pending", WIN: "win", LOSS: "loss", REFUND: "refund"}

    def __init__(self, state, bet=None, parent=None, stake=None):
        super().__init__(parent)
        self.state, self.edit, self.bet, self.again = state, bet, None, False
        self.setWindowTitle("Изменить ставку" if bet else "Новая ставка")
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)
        lay.addWidget(label("Изменить ставку" if bet else "Новая ставка", "dialogtitle"))

        self.type = Segmented([(TYPE_SINGLE, "Одиночная"), (TYPE_EXPRESS, "Экспресс")],
                              bet.bet_type if bet else TYPE_SINGLE)
        lay.addWidget(self.type)
        self.match = QLineEdit(bet.match if bet else "")
        self.match.setMaxLength(150)
        lay.addLayout(_field("Матч", self.match))

        row = QHBoxLayout()
        row.setSpacing(12)
        self.stake = QLineEdit(F.num(bet.stake).replace("\u202f", "") if bet else "")
        self.stake.setPlaceholderText("1000")
        self.odds = QLineEdit(F.odds(bet.odds) if bet else "")
        self.odds.setPlaceholderText("1,85")
        self.odds_label = "Коэффициент"
        row.addLayout(_field("Сумма ставки", self.stake))
        row.addLayout(_field("Коэффициент", self.odds))
        lay.addLayout(row)
        if stake is not None and not bet:
            self.stake.setText(F.num(stake).replace("\u202f", ""))
        if not bet:       # быстрые суммы от помощника (3–5% доступного банка)
            chips = QHBoxLayout()
            chips.setSpacing(6)
            chips.addWidget(label("Помощник:", "hint"))
            for o in stake_options(state.summary["available"]):
                if o["amount"] is None:
                    continue
                c = button(f"{o['pct']}% · {F.money_short(o['amount'])}", "chip")
                c.clicked.connect(lambda _=False, a=o["amount"]: self.stake.setText(F.num(a).replace("\u202f", "")))
                chips.addWidget(c)
            chips.addStretch()
            lay.addLayout(chips)

        self.result = Segmented([(k, RESULT_LABELS[k]) for k in (PENDING, WIN, LOSS, REFUND)],
                                bet.result if bet else PENDING, self.TONES)
        box = QVBoxLayout()
        box.setSpacing(5)
        box.addWidget(label("Результат", "field"))
        box.addWidget(self.result)
        lay.addLayout(box)

        self.preview = label("", "preview")
        self.error = label("", "error", wrap=True)
        self.error.hide()
        lay.addWidget(self.preview)
        lay.addWidget(self.error)

        self.more_btn = button("Дополнительно  ▾", "ghost")
        self.more_btn.setCheckable(True)
        lay.addWidget(self.more_btn, alignment=Qt.AlignLeft)
        self.more = QWidget()
        ml = QVBoxLayout(self.more)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(12)
        self.tournament = QLineEdit(bet.tournament if bet else "")
        tours = sorted({b.tournament for b in state.bets if b.tournament})
        comp = QCompleter(tours, self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        self.tournament.setCompleter(comp)
        self.when = QDateTimeEdit(QDateTime(bet.placed_at) if bet else QDateTime.currentDateTime())
        self.when.setDisplayFormat(F.qt_datetime)
        self.when.setCalendarPopup(True)
        self.comment = QLineEdit(bet.comment if bet else "")
        r2 = QHBoxLayout()
        r2.setSpacing(12)
        r2.addLayout(_field("Турнир (необязательно)", self.tournament))
        r2.addLayout(_field("Дата и время", self.when))
        ml.addLayout(r2)
        ml.addLayout(_field("Комментарий (необязательно)", self.comment))
        lay.addWidget(self.more)
        extra = bool(bet and (bet.tournament or bet.comment))
        self.more.setVisible(extra)
        self.more_btn.setChecked(extra)
        self.more_btn.toggled.connect(self._toggle_more)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()
        cancel = button("Отмена")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        if not bet:
            more = button("Сохранить и добавить ещё")
            more.clicked.connect(lambda: self._save(True))
            btns.addWidget(more)
        save = button("Сохранить", "primary")
        save.setDefault(True)
        save.clicked.connect(lambda: self._save(False))
        btns.addWidget(save)
        lay.addLayout(btns)

        self.base_bank = (state.bank_before.get(bet.id, state.summary["current"]) if bet else state.summary["current"])
        for w in (self.stake, self.odds):
            w.textChanged.connect(self._update_preview)
        self.type.changed.connect(self._type_changed)
        self._type_changed(self.type.value())
        self._update_preview()
        (self.odds if (stake is not None and not bet) else (self.match if not bet else self.stake)).setFocus()
        if stake is not None and not bet:
            self.match.setFocus()

    def _toggle_more(self, on):
        self.more.setVisible(on)
        self.more_btn.setText("Дополнительно  ▴" if on else "Дополнительно  ▾")
        self.adjustSize()

    def _type_changed(self, t):
        self.match.setPlaceholderText("Например: Spirit + Falcons + Liquid (итоговый коэффициент — ниже)"
                                      if t == TYPE_EXPRESS else "Например: Team Spirit vs Team Falcons")

    def _update_preview(self):
        try:
            s, o = parse_decimal(self.stake.text()), parse_decimal(self.odds.text())
            if s <= 0 or o <= 1:
                raise ValueError
            gain = q2(s * (o - 1))
            txt = f"Возможный выигрыш {F.money(gain, True)}  ·  выплата {F.money(q2(s) + gain)}"
            if self.base_bank > 0:
                txt += f"  ·  {F.pct(s / self.base_bank * 100)} от банка"
            self.preview.setText(txt)
        except (ValueError, ArithmeticError):
            self.preview.setText("Введите сумму и коэффициент — покажу возможный выигрыш")

    def _collect(self) -> Bet:
        try:
            stake = parse_decimal(self.stake.text())
        except ValueError:
            raise ValueError("Сумма: введите число, например 1000 или 1500,50")
        try:
            odds = parse_decimal(self.odds.text())
        except ValueError:
            raise ValueError("Коэффициент: введите число, например 1,85")
        validate_bet(self.match.text(), stake, odds)
        return Bet(self.edit.id if self.edit else None, self.when.dateTime().toPython().replace(second=0, microsecond=0),
                   self.match.text().strip(), self.tournament.text().strip(), self.type.value(),
                   q2(stake), odds, self.result.value(), self.comment.text().strip())

    def _save(self, again):
        try:
            bet = self._collect()
        except ValueError as e:
            self.error.setText(str(e))
            self.error.show()
            return
        self.error.hide()
        if bet.result == PENDING:
            avail = self.state.summary["available"]
            if self.edit and self.edit.result == PENDING:
                avail += q2(self.edit.stake)
            if bet.stake > avail and not ask(
                    self, "Ставка больше доступного баланса",
                    f"Доступно: {F.money(avail)}. Ставка: {F.money(bet.stake)}.\nВсё равно сохранить?",
                    "Сохранить"):
                return
        self.bet, self.again = bet, again
        self.accept()


class AmountDialog(QDialog):
    """Пополнение, вывод и изменение начального банка."""

    def __init__(self, title, field, button_text, info_text="", initial="", allow_zero=False, limit=None,
                 limit_text="", comment_hint="Комментарий (необязательно)", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.allow_zero, self.limit, self.limit_text = allow_zero, limit, limit_text
        self.value, self.comment_text = None, ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)
        lay.addWidget(label(title, "dialogtitle"))
        if info_text:
            lay.addWidget(label(info_text, "muted", wrap=True))
        self.amount = QLineEdit(initial)
        lay.addLayout(_field(field, self.amount))
        self.comment = QLineEdit()
        lay.addLayout(_field(comment_hint, self.comment))
        self.error = label("", "error", wrap=True)
        lay.addWidget(self.error)
        row = QHBoxLayout()
        row.addStretch()
        c = button("Отмена")
        c.clicked.connect(self.reject)
        ok = button(button_text, "primary")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        row.addWidget(c)
        row.addWidget(ok)
        lay.addLayout(row)
        self.amount.setFocus()
        self.amount.selectAll()

    def _ok(self):
        try:
            v = parse_decimal(self.amount.text())
        except ValueError:
            self.error.setText("Введите число, например 5000 или 1500,50")
            return
        if v != q2(v):
            self.error.setText("Не больше двух знаков после запятой")
            return
        if v < 0 or (v == 0 and not self.allow_zero):
            self.error.setText("Сумма должна быть больше нуля" if not self.allow_zero else "Сумма не может быть отрицательной")
            return
        if self.limit is not None and v > self.limit:
            self.error.setText(self.limit_text)
            return
        self.value, self.comment_text = q2(v), self.comment.text().strip()
        self.accept()


class PeriodDialog(QDialog):
    def __init__(self, start=None, end=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Произвольный период")
        self.setMinimumWidth(400)
        self.start = self.end = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)
        lay.addWidget(label("Произвольный период", "dialogtitle"))
        today = QDate.currentDate()
        self.a, self.b = QDateEdit(QDate(start) if start else today.addDays(-29)), QDateEdit(QDate(end) if end else today)
        for w in (self.a, self.b):
            w.setCalendarPopup(True)
            w.setDisplayFormat(F.qt_date)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addLayout(_field("С", self.a))
        row.addLayout(_field("По", self.b))
        lay.addLayout(row)
        self.error = label("", "error")
        lay.addWidget(self.error)
        r = QHBoxLayout()
        r.addStretch()
        c = button("Отмена")
        c.clicked.connect(self.reject)
        ok = button("Применить", "primary")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        r.addWidget(c)
        r.addWidget(ok)
        lay.addLayout(r)

    def _ok(self):
        a, b = self.a.date().toPython(), self.b.date().toPython()
        if a > b:
            self.error.setText("Начало периода позже конца")
            return
        self.start, self.end = a, b
        self.accept()


class RestoreDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Восстановление из копии")
        self.setMinimumSize(520, 420)
        self.path = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(label("Восстановление из копии", "dialogtitle"))
        lay.addWidget(label("Выберите копию. Текущие данные будут заменены; перед этим программа "
                            "автоматически сохранит их ещё одной копией.", "muted", wrap=True))
        self.list = QListWidget()
        names = {"auto": "авто", "manual": "вручную", "before_restore": "перед восстановлением"}
        for p in db.list_backups():
            tag = p.stem.rsplit("_", 1)[-1]
            when = datetime.fromtimestamp(p.stat().st_mtime)
            it = QListWidgetItem(f"{F.dt(when)}   ·   {names.get(tag, tag)}   ·   {max(1, p.stat().st_size // 1024)} КБ")
            it.setData(Qt.UserRole, str(p))
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            lay.addWidget(label("Автоматических копий пока нет.", "muted"))
        self.list.itemDoubleClicked.connect(lambda _: self._pick())
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        file_btn = button("Выбрать файл…")
        file_btn.clicked.connect(self._file)
        row.addWidget(file_btn)
        row.addStretch()
        c = button("Отмена")
        c.clicked.connect(self.reject)
        ok = button("Восстановить выбранную", "primary")
        ok.clicked.connect(self._pick)
        row.addWidget(c)
        row.addWidget(ok)
        lay.addLayout(row)

    def _pick(self):
        it = self.list.currentItem()
        if it:
            self.path = it.data(Qt.UserRole)
            self.accept()

    def _file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Файл резервной копии", "", "База данных (*.db *.sqlite);;Все файлы (*)")
        if f:
            self.path = f
            self.accept()
