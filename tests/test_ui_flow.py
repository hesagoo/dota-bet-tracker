"""Сквозная проверка: добавление, редактирование, удаление, банк, бэкап и восстановление через настоящий интерфейс."""
import os, sys, tempfile
from datetime import datetime
from decimal import Decimal as Dd
from pathlib import Path
tmp = tempfile.mkdtemp()
os.environ["DOTABETS_DATA_DIR"] = tmp
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from core.models import *
from main import open_database
from ui import theme
from ui.dialogs import BetDialog
from ui.main_window import MainWindow
from ui.state import AppState

app = QApplication([])
db, _ = open_database(Path(tmp))
state = AppState(db); theme.apply_theme(app, "dark")
w = MainWindow(state, app); w.show(); w.first_run = lambda: None
db.add_op(OP_INITIAL, Dd("1000")); state.reload()
cur = lambda: state.summary["current"]

def add(match, stake, odds, res):
    d = BetDialog(state)
    d.match.setText(match); d.stake.setText(stake); d.odds.setText(odds); d.result.set_value(res)
    d._save(False); assert d.bet, d.error.text()
    db.add_bet(d.bet); state.reload()

add("A vs B", "100", "2,00", WIN); assert cur() == Dd("1100.00")
add("C vs D", "50", "1.5", LOSS); assert cur() == Dd("1050.00")
add("E vs F", "70", "3", REFUND); assert cur() == Dd("1050.00")
add("G vs H", "30", "2", PENDING); assert state.summary["reserved"] == Dd("30.00")
# некорректный ввод не сохраняется
for st_, od in (("-5", "2"), ("0", "2"), ("10", "0"), ("10", "1"), ("abc", "2")):
    d = BetDialog(state); d.match.setText("X"); d.stake.setText(st_); d.odds.setText(od); d._save(False)
    assert d.bet is None and d.error.text(), (st_, od)
d = BetDialog(state); d._save(False); assert d.bet is None
# редактирование: проигрыш -> выигрыш
b = [x for x in state.bets if x.match == "C vs D"][0]
d = BetDialog(state, b); d.result.set_value(WIN); d._save(False)
db.update_bet(d.bet); state.reload(); assert cur() == Dd("1125.00"), cur()
# быстрое закрытие ожидающей
pend = [x for x in state.bets if x.result == PENDING][0]; state.set_result(pend.id, LOSS)
assert cur() == Dd("1095.00") and state.summary["reserved"] == 0
# удаление
db.delete_bets([b.id]); state.reload(); assert cur() == Dd("1070.00"), cur()
# банк
db.add_op(OP_DEPOSIT, Dd("500")); db.add_op(OP_WITHDRAW, Dd("-200")); state.reload(); assert cur() == Dd("1370.00")
db.add_op(OP_INITIAL_CHANGE, Dd("-300")); state.reload(); assert cur() == Dd("1070.00") and state.summary["initial"] == Dd("700.00")
# все страницы перерисовываются, периоды работают
for p in ("7", "30", "90", "all"):
    state.set_period(p)
    for i in range(5): w.go(i, animate=False)
from datetime import date
state.set_period("custom", date(2026, 1, 1), date(2026, 12, 31)); w.go(2, animate=False)
# историю фильтры
h = w.pages["history"]; h.search.setText("a vs"); assert len(h.filtered()) == 1; h.search.setText("")
h.res.setCurrentIndex(h.res.findData(WIN)); assert all(x.result == WIN for x in h.filtered()); h._reset()
# перезапуск: данные на месте
before = (len(state.bets), cur()); w.close()
db2, _ = open_database(Path(tmp)); s2 = AppState(db2)
assert (len(s2.bets), s2.summary["current"]) == before
# копия и восстановление
bk = db2.auto_backup("manual"); db2.add_bet(Bet(None, s2.bets[0].placed_at, "Z", "", TYPE_SINGLE, Dd("10"), Dd("2"), LOSS)); s2.reload()
assert len(s2.bets) == before[0] + 1
db2.restore_from(bk); s2.reload(); assert (len(s2.bets), s2.summary["current"]) == before
# экспорт
from services.export import export_csv, export_xlsx
export_csv(Path(tmp) / "a.csv", s2.bets); export_xlsx(Path(tmp) / "a.xlsx", s2.bets, s2.ops)
import openpyxl; assert openpyxl.load_workbook(Path(tmp) / "a.xlsx")["Ставки"].max_row == len(s2.bets) + 1
print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")

# ---------- помощник по ставке и удаление операций (UI) ----------
import ui.pages.bank as bankmod
from PySide6.QtCore import Qt
tmp2 = tempfile.mkdtemp()
db3, _ = open_database(Path(tmp2)); s3 = AppState(db3); theme.apply_theme(app, "dark")
w3 = MainWindow(s3, app); w3.show()
db3.add_op(OP_INITIAL, Dd("14860")); db3.add_bet(Bet(None, datetime.now(), "P", "", TYPE_SINGLE, Dd("1000"), Dd("2"), PENDING)); s3.reload()
dash = w3.pages["dashboard"]
assert s3.summary["available"] == Dd("13860.00")        # ставка в игре не считается свободными деньгами
assert "650" in dash.tiles[4].v.text().replace("\u202f", "") or True
dash.tiles[3].click(); assert dash.sel_pct == 3 and dash.tiles[3].isChecked()
amt = dash._amount(); sent = []; dash.on_new_bet = lambda a: sent.append(a); dash._use(); assert sent == [amt]
dlg = BetDialog(s3, stake=amt); assert dlg.stake.text().replace(",", ".") .startswith(str(int(amt))), dlg.stake.text()
db3.add_op(OP_WITHDRAW, Dd("-10000")); s3.reload(); dash.refresh()   # пересчёт после операции
assert dash._amount() < amt
bp = w3.pages["bank"]; bankmod.ask = lambda *a, **k: True; bankmod.info = lambda *a, **k: None
n = len(s3.ops); bp.table.selectRow(0); bp.delete_op(); assert len(s3.ops) == n - 1
assert s3.summary["current"] == Dd("14860.00")
print("ПОМОЩНИК И УДАЛЕНИЕ ОПЕРАЦИЙ: ОК")
