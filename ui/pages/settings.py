import os
from datetime import date

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QCheckBox, QSpinBox, QHBoxLayout, QVBoxLayout, QFileDialog, QApplication, QLineEdit
from version import DEFAULT_UPDATE_URL

from services.export import export_csv, export_xlsx
from .. import theme
from ..dialogs import ask, info, RestoreDialog
from ..fmt import F
from ..widgets import Page, Card, ResponsiveGrid, Segmented, label, button

CURRENCIES = [("₽", "Рубли  ₽"), ("$", "Доллары  $"), ("€", "Евро  €"), ("₸", "Тенге  ₸"), ("₴", "Гривны  ₴"),
              ("Br", "Белорусские рубли  Br"), ("", "Без символа")]
DATES = [("%d.%m.%Y", "ДД.ММ.ГГГГ  (10.11.2026)"), ("%Y-%m-%d", "ГГГГ-ММ-ДД  (2026-11-10)"),
         ("%d/%m/%Y", "ДД/ММ/ГГГГ  (10/11/2026)"), ("%m/%d/%Y", "ММ/ДД/ГГГГ  (11/10/2026)")]
PERIODS = [("all", "Всё время"), ("7", "7 дней"), ("30", "30 дней"), ("90", "90 дней")]


def row(text, widget, hint=""):
    box = QHBoxLayout()
    left = QVBoxLayout()
    left.setSpacing(1)
    left.addWidget(label(text))
    if hint:
        left.addWidget(label(hint, "hint"))
    box.addLayout(left, 1)
    box.addWidget(widget)
    return box


class SettingsPage(Page):
    def __init__(self, state, window):
        super().__init__()
        self.state, self.window_ = state, window
        db = state.db
        self.loading = True

        look = Card("Оформление и формат")
        self.theme = Segmented([("dark", "Тёмная"), ("light", "Светлая")], db.get_setting("theme"))
        self.cur = QComboBox()
        for v, t in CURRENCIES:
            self.cur.addItem(t, v)
        self.cur.setMinimumWidth(220)
        self.date = QComboBox()
        for v, t in DATES:
            self.date.addItem(t, v)
        self.date.setMinimumWidth(220)
        self.per = QComboBox()
        for v, t in PERIODS:
            self.per.addItem(t, v)
        self.per.setMinimumWidth(220)
        for lbl, w, hint in (("Тема", self.theme, ""), ("Валюта отображения", self.cur, "Только символ в интерфейсе, суммы не пересчитываются"),
                             ("Формат даты", self.date, ""), ("Период при запуске", self.per, "Какой период показывать на дашборде при открытии программы")):
            look.body.addLayout(row(lbl, w, hint))
        self.col.addWidget(look)

        data = Card("Данные и резервные копии")
        open_btn = button("Открыть папку")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(db.dir))))
        data.body.addLayout(row("Папка с данными", open_btn, str(db.dir)))
        self.auto = QCheckBox("Автоматически сохранять копии")
        self.keep = QSpinBox()
        self.keep.setRange(3, 200)
        self.keep.setSuffix("  копий")
        self.keep.setMinimumWidth(110)
        data.body.addLayout(row("Автокопии", self.auto, "При запуске, при выходе и раз в 30 минут при наличии изменений"))
        data.body.addLayout(row("Хранить последних", self.keep))
        self.last = label("", "muted")
        data.add(self.last)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        b1, b2, b3 = button("Создать копию сейчас", "primary"), button("Сохранить копию как…"), button("Восстановить из копии…")
        b1.clicked.connect(self.backup_now)
        b2.clicked.connect(self.backup_as)
        b3.clicked.connect(self.restore)
        for b in (b1, b2, b3):
            btns.addWidget(b)
        btns.addStretch()
        data.body.addLayout(btns)
        self.col.addWidget(data)

        upd = Card("О программе и обновления")
        from version import APP_NAME, __version__
        upd.add(label(f"{APP_NAME}  ·  версия {__version__}", "cardhead"))
        self.url = QLineEdit(db.get_setting("update_url") or DEFAULT_UPDATE_URL)
        self.url.setPlaceholderText("https://github.com/ЛОГИН/РЕПОЗИТОРИЙ")
        self.url.setMinimumWidth(360)
        upd.body.addLayout(row("Адрес обновлений", self.url, "Ссылка на репозиторий GitHub с релизами (или прямая ссылка на latest.json)"))
        self.upd_auto = QCheckBox("Проверять при запуске")
        upd.body.addLayout(row("Автопроверка", self.upd_auto, "Проверка идёт в фоне; если есть новая версия, появится кнопка в меню слева"))
        self.upd_status = label("", "muted", wrap=True)
        upd.add(self.upd_status)
        ub = QHBoxLayout()
        self.upd_btn = button("Проверить обновления", "primary")
        self.upd_btn.clicked.connect(lambda: window.check_updates(manual=True))
        ub.addWidget(self.upd_btn)
        ub.addStretch()
        upd.body.addLayout(ub)
        self.col.addWidget(upd)

        exp = Card("Экспорт")
        exp.add(label("Вся история ставок (и операции банка в Excel). Для выгрузки с фильтрами используйте кнопку «Экспорт» на странице «История».", "muted", wrap=True))
        eb = QHBoxLayout()
        x, c = button("Excel (.xlsx)"), button("CSV (.csv)")
        x.clicked.connect(lambda: self.export("xlsx"))
        c.clicked.connect(lambda: self.export("csv"))
        eb.addWidget(x)
        eb.addWidget(c)
        eb.addStretch()
        exp.body.addLayout(eb)
        self.col.addWidget(exp)

        about = Card("Как считаются показатели")
        about.add(label(
            "• Выигрыш: прибыль = сумма × (коэффициент − 1). Проигрыш: −сумма. Возврат и ожидание: 0.\n"
            "• Текущий банк = начальный банк + пополнения − выводы + результат ставок.\n"
            "• Доступно = текущий банк − сумма ставок, ожидающих расчёта.\n"
            "• Win Rate = выигрыши / (выигрыши + проигрыши); возвраты не учитываются.\n"
            "• ROI = чистая прибыль / сумма выигравших и проигравших ставок.\n"
            "• «% банка» у ставки — доля от банка на момент ставки.\n"
            "• Статистика на дашборде и в аналитике считается за выбранный период; текущий банк — всегда актуальный.",
            "muted", wrap=True))
        self.col.addWidget(about)
        self.finish()
        self.load()
        self.loading = False
        self.theme.changed.connect(lambda v: self.save("theme", v))
        self.cur.currentIndexChanged.connect(lambda: self.save("currency", self.cur.currentData()))
        self.date.currentIndexChanged.connect(lambda: self.save("date_fmt", self.date.currentData()))
        self.per.currentIndexChanged.connect(lambda: self.save("default_period", self.per.currentData(), False))
        self.auto.toggled.connect(lambda v: self.save("auto_backup", "1" if v else "0", False))
        self.keep.valueChanged.connect(lambda v: self.save("backup_keep", str(v), False))
        self.upd_auto.toggled.connect(lambda v: self.save("update_check", "1" if v else "0", False))
        self.url.editingFinished.connect(self._save_url)

    def load(self):
        db = self.state.db
        self.cur.setCurrentIndex(max(0, self.cur.findData(db.get_setting("currency"))))
        self.date.setCurrentIndex(max(0, self.date.findData(db.get_setting("date_fmt"))))
        self.per.setCurrentIndex(max(0, self.per.findData(db.get_setting("default_period"))))
        self.auto.setChecked(db.get_setting("auto_backup") == "1")
        self.keep.setValue(int(db.get_setting("backup_keep") or 15))
        self.upd_auto.setChecked(db.get_setting("update_check") == "1")

    def refresh(self):
        t = self.state.db.last_backup_time()
        n = len(self.state.db.list_backups())
        self.last.setText(f"Последняя копия: {F.dt(t) if t else 'ещё не создавалась'}   ·   всего копий: {n}")

    def _save_url(self):
        from core import updater as U
        raw = self.url.text().strip()
        fixed = U.clean_input(raw)
        if fixed != raw:
            self.url.setText(fixed)
            self.upd_status.setText(f"Адрес исправлен: {fixed}")
        elif raw:
            try:
                U.normalize_url(raw)
                self.upd_status.setText("")
            except U.UpdateError as e:
                self.upd_status.setText(str(e))
        self.save("update_url", fixed, False)

    def save(self, key, value, apply=True):
        if self.loading:
            return
        self.state.db.set_setting(key, value)
        if key == "theme":
            self.window_.apply_theme(value)
        elif apply:
            self.state.apply_settings()

    def backup_now(self):
        try:
            p = self.state.db.auto_backup("manual")
            self.refresh()
            info(self, "Копия создана", f"Файл сохранён:\n{p}")
        except Exception as e:
            info(self, "Не удалось создать копию", str(e))

    def backup_as(self):
        f, _ = QFileDialog.getSaveFileName(self, "Сохранить копию базы", f"dota_bets_{date.today():%Y-%m-%d}.db", "База данных (*.db)")
        if f:
            try:
                self.state.db.backup_to(f)
                info(self, "Копия создана", f"Файл сохранён:\n{f}")
            except Exception as e:
                info(self, "Не удалось создать копию", str(e))

    def restore(self):
        d = RestoreDialog(self.state.db, self)
        if not d.exec() or not d.path:
            return
        try:
            self.state.db.check_backup(d.path)
        except ValueError as e:
            info(self, "Нельзя восстановить", str(e))
            return
        if not ask(self, "Восстановление", "Заменить текущие данные выбранной копией?\nТекущие данные будут сохранены отдельной копией.", "Восстановить"):
            return
        try:
            self.state.db.restore_from(d.path)
        except Exception as e:
            info(self, "Не удалось восстановить", str(e))
            return
        self.state.apply_settings(emit=False)
        self.window_.apply_theme(self.state.db.get_setting("theme"))
        self.loading = True
        self.load()
        self.theme.set_value(self.state.db.get_setting("theme"))
        self.loading = False
        self.state.reload()
        self.state.settings_changed.emit()
        info(self, "Готово", "Данные восстановлены из копии.")

    def export(self, kind):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", f"ставки_{date.today():%Y-%m-%d}.{kind}",
                                              "Excel (*.xlsx)" if kind == "xlsx" else "CSV (*.csv)")
        if not path:
            return
        try:
            if kind == "xlsx":
                export_xlsx(path, self.state.bets, self.state.ops, F.date_fmt)
            else:
                export_csv(path, self.state.bets, F.date_fmt)
            info(self, "Экспорт", f"Готово.\n{path}")
        except Exception as e:
            info(self, "Не удалось сохранить файл", str(e))
