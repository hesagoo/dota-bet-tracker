"""Интерфейс обновлений: фоновая проверка, окно со списком изменений, загрузка и запуск установки."""
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar, QApplication

from core import updater as U
from core.paths import is_frozen, app_root
from version import EXE_NAME, __version__
from .dialogs import info
from .widgets import label, button


class CheckWorker(QThread):
    done = Signal(object, str)          # (UpdateInfo | None, текст ошибки)

    def __init__(self, current, url):
        super().__init__()
        self.current, self.url = current, url

    def run(self):
        try:
            self.done.emit(U.check(self.current, self.url), "")
        except U.UpdateError as e:
            self.done.emit(None, str(e))
        except Exception as e:
            self.done.emit(None, f"Ошибка проверки: {e}")


class PrepareWorker(QThread):
    progress = Signal(int, int)
    status = Signal(str)
    done = Signal(str, str)             # (папка со свежими файлами, текст ошибки)

    def __init__(self, upd, work_dir, install_dir):
        super().__init__()
        self.upd, self.work, self.install = upd, Path(work_dir), Path(install_dir)
        self.cancel = False

    def _try(self, pkg):
        self.status.emit("Скачиваю обновление…" if pkg.kind == "delta" else "Скачиваю полный пакет…")
        z = U.download(pkg, self.work / f"{pkg.kind}-{self.upd.version}.zip", lambda d, t: self.progress.emit(d, t), lambda: self.cancel)
        self.status.emit("Проверяю и распаковываю…")
        stage = self.work / "staging"
        U.extract_safe(z, stage)
        if self.upd.files:
            U.verify_result(stage, self.install, self.upd.files)
        return stage

    def run(self):
        try:
            try:
                stage = self._try(self.upd.package)
            except U.UpdateError as e:
                if self.upd.fallback and not self.cancel and "Загрузка отменена" not in str(e):
                    stage = self._try(self.upd.fallback)       # дельта не подошла — берём полный пакет
                else:
                    raise
            self.done.emit(str(stage), "")
        except U.UpdateError as e:
            U.cleanup_downloads(self.work)
            self.done.emit("", str(e))
        except Exception as e:
            U.cleanup_downloads(self.work)
            self.done.emit("", f"Ошибка при подготовке обновления: {e}")


class UpdateDialog(QDialog):
    def __init__(self, state, upd, parent=None):
        super().__init__(parent)
        self.state, self.upd, self.worker = state, upd, None
        self.setWindowTitle("Доступно обновление")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(12)
        lay.addWidget(label(f"Версия {upd.version}", "dialogtitle"))
        size = f"{upd.package.size / 1e6:.1f} МБ" if upd.package.size >= 1e5 else f"{max(1, upd.package.size // 1024)} КБ"
        kind = "только изменённые файлы" if upd.package.kind == "delta" else "полный пакет"
        lay.addWidget(label(f"Сейчас установлена {__version__}. Будет скачано: {size} ({kind})." +
                            (f" Дата выпуска: {upd.released}." if upd.released else ""), "muted", wrap=True))
        lay.addWidget(label("Что нового:", "cardhead"))
        lay.addWidget(label("\n".join("•  " + n for n in upd.notes) or "Список изменений не указан.", wrap=True))
        lay.addWidget(label("Ваши ставки, банк, история и настройки не затрагиваются. Перед установкой автоматически "
                            "создаётся копия базы данных; если новая версия не запустится, программа сама вернёт старую.", "hint", wrap=True))
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.hide()
        self.status = label("", "muted")
        lay.addWidget(self.bar)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch()
        self.later = button("Позже")
        self.later.clicked.connect(self._close)
        self.go = button("Установить и перезапустить", "primary")
        self.go.clicked.connect(self._start)
        row.addWidget(self.later)
        row.addWidget(self.go)
        lay.addLayout(row)

    def _close(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel = True
            self.worker.wait(3000)
        self.reject()

    def _start(self):
        if not is_frozen():
            info(self, "Установка недоступна из исходников",
                 "Автоустановка работает в собранной программе (DotaBetTracker.exe, см. build_exe.bat). "
                 "Из папки с исходниками просто замените файлы проекта новой версией.")
            return
        self.go.setEnabled(False)
        self.bar.show()
        work = self.state.db.dir / "updates"
        work.mkdir(exist_ok=True)
        self.worker = PrepareWorker(self.upd, work, app_root())
        self.worker.progress.connect(lambda d, t: (self.bar.setMaximum(max(t, 1)), self.bar.setValue(d)))
        self.worker.status.connect(self.status.setText)
        self.worker.done.connect(self._prepared)
        self.worker.start()

    def _prepared(self, stage, err):
        if err:
            self.status.setText("")
            self.bar.hide()
            self.go.setEnabled(True)
            info(self, "Обновление не установлено", err + "\n\nНичего не изменено, программа работает как раньше.")
            return
        self.status.setText("Создаю резервную копию данных…")
        QApplication.processEvents()
        try:
            self.state.db.auto_backup("before_update")
            U.launch_apply(Path(stage), app_root(), EXE_NAME + ".exe", self.state.db.dir / "updates")
        except Exception as e:
            self.go.setEnabled(True)
            info(self, "Не удалось начать установку", str(e))
            return
        self.status.setText("Перезапуск…")
        self.accept()
        QApplication.instance().quit()
