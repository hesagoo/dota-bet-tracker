"""Dota Bets — личный учёт ставок на Dota 2. Запуск: python main.py"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QLinearGradient, QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from core.database import Database, NewerDatabaseError
from core.paths import data_dir, resource_path
from version import APP_NAME, APP_ID, __version__


def app_icon() -> QIcon:
    f = resource_path("assets/icon.ico")
    if f.exists():
        ic = QIcon(str(f))
        if not ic.isNull():
            return ic
    ic = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, s, s)
        g.setColorAt(0, QColor("#8FA9FF"))
        g.setColorAt(1, QColor("#5B6FE0"))
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, s, s, s * 0.24, s * 0.24)
        f = QFont("Segoe UI", 1)
        f.setPixelSize(int(s * 0.58))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#0D1020"))
        p.drawText(pm.rect(), Qt.AlignCenter, "D")
        p.end()
        ic.addPixmap(pm)
    return ic


def open_database(base: Path) -> tuple:
    """Открывает базу. Если файл повреждён — откладывает его в сторону и пытается взять последнюю копию."""
    path = base / "bets.db"
    note = None
    try:
        db = Database(path)
        db.get_bets()
        return db, note
    except NewerDatabaseError:
        raise                      # файл не повреждён — его нельзя трогать
    except Exception:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if path.exists():
            path.rename(base / f"bets_damaged_{stamp}.db")
        db = Database(path)
        for b in db.list_backups():
            try:
                db.restore_from(b)
                return db, f"Основной файл данных оказался повреждён.\nДанные восстановлены из последней копии:\n{b.name}"
            except Exception:
                continue
        return db, "Основной файл данных оказался повреждён, а резервных копий не нашлось. Создана новая пустая база."


def main():
    base = data_dir()
    log = base / "error.log"

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
        except OSError:
            pass
        if QApplication.instance():
            m = QMessageBox()
            m.setIcon(QMessageBox.Warning)
            m.setWindowTitle("Что-то пошло не так")
            m.setText("Произошла ошибка, но ваши данные в безопасности — "
                      "все операции сохраняются сразу.\nПодробности записаны в файл error.log в папке данных.")
            m.setDetailedText(text)
            m.exec()

    sys.excepthook = hook
    if sys.platform == "win32":      # свой значок в панели задач вместо значка Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    from ui import theme
    from ui.main_window import MainWindow
    from ui.state import AppState

    try:
        db, note = open_database(base)
    except NewerDatabaseError as e:
        QMessageBox.critical(None, APP_NAME, f"{e}\n\nДанные не тронуты.")
        sys.exit(1)
    state = AppState(db)
    theme.apply_theme(app, db.get_setting("theme"))
    win = MainWindow(state, app)
    win.show()
    try:      # метка «приложение запустилось» — по ней система обновлений понимает, что всё хорошо
        (base / "updates").mkdir(exist_ok=True)
        (base / "updates" / "started_ok.flag").write_text(__version__, encoding="utf-8")
        from core.updater import cleanup_downloads     # убираем скачанные пакеты прошлых обновлений
        cleanup_downloads(base / "updates")
    except OSError:
        pass
    win.first_run()
    if note:
        QMessageBox.information(win, "Восстановление данных", note)
    code = app.exec()
    sys.exit(code)


if __name__ == "__main__":
    main()
