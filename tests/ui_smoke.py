"""Проверка интерфейса без показа окон: заполняет временную базу тестовыми данными и делает скриншоты.
Запуск: python tests/ui_smoke.py  (данные пользователя не затрагиваются)"""
import os, sys, tempfile, random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["DOTABETS_DATA_DIR"] = tmp
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from core.database import Database
from core.models import *
from main import open_database
from ui import theme
from ui.main_window import MainWindow
from ui.state import AppState
from ui.dialogs import BetDialog, AmountDialog

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tmp)
out.mkdir(exist_ok=True)
random.seed(4)
db, _ = open_database(Path(tmp))
db.add_op(OP_INITIAL, Decimal("10000"), "старт", datetime.now() - timedelta(days=100))
teams = ["Team Spirit", "Team Falcons", "Gaimin Gladiators", "Tundra", "BetBoom Team", "PARIVISION", "Team Liquid", "Xtreme"]
tours = ["The International", "DreamLeague", "PGL Wallachia", "", "BLAST Slam"]
for i in range(70):
    t = datetime.now() - timedelta(days=99 - i * 1.4, hours=random.randint(0, 10))
    odds = Decimal(str(round(random.uniform(1.3, 3.4), 2)))
    stake = Decimal(random.choice([300, 500, 700, 1000, 1500]))
    res = random.choices([WIN, LOSS, REFUND], [47, 48, 5])[0]
    if i >= 67:
        res = PENDING
    db.add_bet(Bet(None, t, f"{random.choice(teams)} vs {random.choice(teams)}", random.choice(tours),
                   random.choice([TYPE_SINGLE, TYPE_SINGLE, TYPE_EXPRESS]), stake, odds, res, ""))
db.add_op(OP_DEPOSIT, Decimal("3000"), "пополнение", datetime.now() - timedelta(days=40))
db.add_op(OP_WITHDRAW, Decimal("-2000"), "вывод", datetime.now() - timedelta(days=15))
db.add_op(OP_INITIAL_CHANGE, Decimal("500"), "Изменение начального банка", datetime.now() - timedelta(days=10))

app = QApplication([])

def settle():
    for _ in range(4):
        app.processEvents()
state = AppState(db)
theme.apply_theme(app, "dark")
w = MainWindow(state, app)
w.resize(1320, 860)
w.show()
for i, (key, _) in enumerate(w.PAGES):
    w.go(i, animate=False)
    settle()
    w.grab().save(str(out / f"page_{key}.png"))
state.set_period("30")
w.go(2, animate=False); settle(); w.grab().save(str(out / "page_analytics_30.png"))
d = BetDialog(state, parent=w)
d.match.setText("Team Spirit vs Falcons"); d.stake.setText("1000"); d.odds.setText("1,85"); d.more_btn.setChecked(True)
d.show(); settle(); d.grab().save(str(out / "dialog_bet.png"))
w.apply_theme("light"); w.go(0, animate=False); settle(); w.grab().save(str(out / "light_dashboard.png"))
w.resize(1000, 700); settle(); w.grab().save(str(out / "narrow_dashboard.png"))
print("OK", tmp)
