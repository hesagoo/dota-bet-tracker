import os, sys, tempfile, unittest
from datetime import datetime, date, timedelta
from decimal import Decimal as Dd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.models import *
from core.calculator import bank_summary, bet_profit, validate_bet
from core.database import Database
from core import stats as st
from core.money import parse_decimal


def bet(i, day, stake, odds, result, tour="", typ=TYPE_SINGLE):
    return Bet(i, datetime(2026, 11, day, 12, 0), f"M{i}", tour, typ, Dd(stake), Dd(odds), result)


def op(i, day, kind, amount):
    return BankOp(i, datetime(2026, 11, day, 9, 0), kind, Dd(amount))


class Calc(unittest.TestCase):
    def test_profit(self):
        self.assertEqual(bet_profit(bet(1, 1, "100", "1.85", WIN)), Dd("85.00"))
        self.assertEqual(bet_profit(bet(1, 1, "33.33", "1.73", WIN)), Dd("24.33"))
        self.assertEqual(bet_profit(bet(1, 1, "100", "1.85", LOSS)), Dd("-100.00"))
        self.assertEqual(bet_profit(bet(1, 1, "100", "1.85", REFUND)), Dd("0.00"))
        self.assertEqual(bet_profit(bet(1, 1, "100", "1.85", PENDING)), Dd("0.00"))

    def test_bank_no_double_count(self):
        ops = [op(1, 1, OP_INITIAL, "1000"), op(2, 2, OP_DEPOSIT, "500"), op(3, 3, OP_WITHDRAW, "-200")]
        bets = [bet(1, 4, "100", "2.0", WIN), bet(2, 5, "50", "1.5", LOSS),
                bet(3, 6, "70", "3", REFUND), bet(4, 7, "30", "2", PENDING)]
        s = bank_summary(bets, ops)
        self.assertEqual(s["current"], Dd("1350.00"))     # 1000+500-200+100-50
        self.assertEqual(s["reserved"], Dd("30.00"))
        self.assertEqual(s["available"], Dd("1320.00"))
        self.assertEqual(s["bets_result"], Dd("50.00"))

    def test_change_initial_keeps_history(self):
        ops = [op(1, 1, OP_INITIAL, "1000"), op(2, 2, OP_INITIAL_CHANGE, "-300")]
        self.assertEqual(bank_summary([], ops)["initial"], Dd("700.00"))
        self.assertEqual(bank_summary([], ops)["deposits"], 0)

    def test_validation(self):
        validate_bet("A vs B", Dd("10"), Dd("1.5"))
        for args in [("", "10", "1.5"), ("A", "0", "1.5"), ("A", "-5", "1.5"), ("A", "10", "0"),
                     ("A", "10", "1"), ("A", "10.123", "1.5"), ("A", "10", "1.5555")]:
            with self.assertRaises(ValueError):
                validate_bet(args[0], Dd(args[1]), Dd(args[2]))
        self.assertEqual(parse_decimal("1 500,50"), Dd("1500.50"))
        with self.assertRaises(ValueError):
            parse_decimal("abc")


class Stats(unittest.TestCase):
    def setUp(self):
        self.bets = [bet(1, 1, "100", "2.0", WIN, "TI"), bet(2, 2, "100", "1.5", WIN, "TI"),
                     bet(3, 3, "100", "3.0", LOSS, "DreamLeague"), bet(4, 4, "100", "1.8", REFUND, "TI"),
                     bet(5, 5, "100", "1.7", LOSS, ""), bet(6, 6, "50", "1.4", LOSS, "TI"),
                     bet(7, 7, "100", "2.0", PENDING, "TI", TYPE_EXPRESS)]

    def test_main(self):
        s = st.compute_stats(self.bets)
        self.assertEqual((s.total, s.wins, s.losses, s.refunds, s.pending), (7, 2, 3, 1, 1))
        self.assertEqual(s.gross_profit, Dd("150.00"))
        self.assertEqual(s.gross_loss, Dd("250.00"))
        self.assertEqual(s.net, Dd("-100.00"))
        self.assertEqual(s.turnover, Dd("650.00"))
        self.assertEqual(s.risked, Dd("450.00"))
        self.assertEqual(s.roi, Dd("-22.22"))
        self.assertEqual(s.win_rate, Dd("40.00"))
        self.assertEqual(s.win_streak, 2)
        self.assertEqual(s.loss_streak, 3)   # возврат серию не прерывает
        self.assertEqual(s.max_profit, Dd("100.00"))
        self.assertEqual(s.max_loss, Dd("100.00"))
        self.assertEqual(s.avg_win, Dd("75.00"))
        self.assertEqual(s.top_win_odds, Dd("2.0"))
        self.assertEqual(s.top_loss_odds, Dd("3.0"))

    def test_groups(self):
        t = {r.label: r for r in st.by_tournament(self.bets)}
        self.assertEqual(t["TI"].profit, Dd("100.00") + Dd("50.00") - Dd("50"))
        self.assertIn("Без турнира", t)
        o = st.by_odds(self.bets)
        self.assertEqual(len(o), 6)
        self.assertEqual(sum(r.bets for r in o), 7)
        self.assertEqual(st.by_month(self.bets)[0].label, "Ноябрь 2026")

    def test_curve_and_drawdown(self):
        ops = [op(1, 1, OP_INITIAL, "1000")]
        bets = [bet(1, 2, "100", "2", WIN), bet(2, 3, "300", "2", LOSS), bet(3, 4, "100", "2", LOSS)]
        pts = st.bank_curve(ops, bets, now=datetime(2026, 11, 5))
        self.assertEqual([p[1] for p in pts][:4], [1000, 1100, 800, 700])
        series, mx, mxp, cur, curp = st.drawdown(pts)
        self.assertEqual(mx, Dd("400.00"))
        self.assertEqual(mxp, Dd("36.36"))
        bb = st.bank_before_bets(ops, bets)
        self.assertEqual(bb[1], 1000); self.assertEqual(bb[2], 1100)

    def test_period_slice(self):
        ops = [op(1, 1, OP_INITIAL, "1000")]
        bets = [bet(1, 2, "100", "2", WIN), bet(2, 10, "100", "2", LOSS)]
        pts = st.bank_curve(ops, bets, date(2026, 11, 5), date(2026, 11, 20), now=datetime(2026, 11, 20, 18))
        self.assertEqual(pts[0][1], 1100)       # баланс на начало периода
        self.assertEqual(pts[-1][1], 1000)

    def test_buckets(self):
        b = st.profit_buckets(self.bets, date(2026, 11, 1), date(2026, 11, 7))
        self.assertEqual(len(b), 7)
        self.assertEqual(sum(x[1] for x in b), Dd("-100.00"))


class Db(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "bets.db")

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def test_crud_persist_backup_restore(self):
        i = self.db.add_bet(bet(None, 1, "100.50", "1.85", WIN, "TI"))
        self.db.add_op(OP_INITIAL, Dd("1000"), "старт")
        self.db.set_setting("currency", "$")
        # перезапуск
        self.db.close()
        self.db = Database(Path(self.tmp.name) / "bets.db")
        b = self.db.get_bets()[0]
        self.assertEqual((b.id, b.stake, b.odds, b.result), (i, Dd("100.50"), Dd("1.85"), WIN))
        self.assertEqual(self.db.get_setting("currency"), "$")
        self.assertEqual(self.db.get_setting("theme"), "dark")
        # бэкап → изменения → восстановление
        bk = self.db.auto_backup("manual")
        self.db.add_bet(bet(None, 2, "10", "2", LOSS))
        self.db.delete_bets([i])
        self.assertEqual(len(self.db.get_bets()), 1)
        self.db.restore_from(bk)
        got = self.db.get_bets()
        self.assertEqual(len(got), 1); self.assertEqual(got[0].id, i)
        self.assertTrue(any("before_restore" in p.name for p in self.db.list_backups()))
        # редактирование и удаление
        got[0].stake = Dd("200"); got[0].result = LOSS
        self.db.update_bet(got[0])
        self.assertEqual(bank_summary(self.db.get_bets(), self.db.get_ops())["current"], Dd("800.00"))
        self.db.delete_bets([i])
        self.assertEqual(bank_summary(self.db.get_bets(), self.db.get_ops())["current"], Dd("1000.00"))

    def test_bad_backup(self):
        bad = Path(self.tmp.name) / "x.db"; bad.write_text("not a database")
        with self.assertRaises(ValueError):
            self.db.restore_from(bad)

    def test_auto_backup_prune(self):
        for k in range(5):
            self.db.backup_to(self.db.backup_dir / f"bets_2026010{k}_000000_auto.db")
            os.utime(self.db.backup_dir / f"bets_2026010{k}_000000_auto.db", (1000 + k, 1000 + k))
        self.db.auto_backup("auto", keep=3)
        self.assertEqual(len([p for p in self.db.list_backups() if p.stem.endswith("_auto")]), 3)


if __name__ == "__main__":
    unittest.main()


class StakeHelper(unittest.TestCase):
    def test_options(self):
        from core.calculator import stake_options
        o = {x["pct"]: x for x in stake_options(Dd("14860"))}
        self.assertEqual(o[3]["amount"], Dd("450.00"))
        self.assertEqual(o[4]["amount"], Dd("600.00"))
        self.assertEqual(o[5]["amount"], Dd("700.00"))        # 750 пробило бы лимит 5% (743)
        for avail in ("14860", "1000", "400", "60", "20000.55", "123.45"):
            for x in stake_options(Dd(avail)):
                if x["amount"] is not None:
                    self.assertLessEqual(x["amount"], Dd(avail) * Dd("0.05") + Dd("0.0001"))
                    self.assertLessEqual(x["amount"], Dd(avail))
        self.assertTrue(all(x["amount"] is None for x in stake_options(Dd("0"))))
        self.assertTrue(all(x["amount"] is None for x in stake_options(Dd("-10"))))
