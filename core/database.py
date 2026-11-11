"""Локальная база SQLite: ставки, операции банка, настройки, резервные копии."""
import os
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .models import Bet, BankOp
from .money import q2

TS = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at TEXT NOT NULL, match TEXT NOT NULL, tournament TEXT NOT NULL DEFAULT '',
    bet_type TEXT NOT NULL DEFAULT 'single', stake TEXT NOT NULL, odds TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT 'pending', comment TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS bank_ops(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, kind TEXT NOT NULL, amount TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

SCHEMA_VERSION = 1      # версия структуры базы; новые версии программы добавляют миграции ниже
MIGRATIONS = {          # {номер: [SQL-команды]} — выполняются по порядку, данные пользователя сохраняются
    # 2: ["ALTER TABLE bets ADD COLUMN ..."],
}

DEFAULT_SETTINGS = {
    "currency": "₽", "date_fmt": "%d.%m.%Y", "theme": "dark",
    "auto_backup": "1", "backup_keep": "15", "default_period": "all",
    "update_url": "", "update_check": "1",
}


class NewerDatabaseError(RuntimeError):
    pass


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.dir = self.path.parent
        self.backup_dir = self.dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()
        self.dirty = False

    def _ensure_schema(self):
        with self.conn:
            self.conn.executescript(SCHEMA)
        ver = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if ver > SCHEMA_VERSION:
            raise NewerDatabaseError("База создана более новой версией программы. Обновите программу.")
        for v in range(ver + 1, SCHEMA_VERSION + 1):        # старые базы (версия 0) подходят без изменений
            with self.conn:
                for sql in MIGRATIONS.get(v, []):
                    self.conn.execute(sql)
        if ver < SCHEMA_VERSION:
            self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ---------- ставки ----------
    @staticmethod
    def _bet(r) -> Bet:
        return Bet(r["id"], datetime.strptime(r["placed_at"], TS), r["match"], r["tournament"],
                   r["bet_type"], Decimal(r["stake"]), Decimal(r["odds"]), r["result"], r["comment"])

    def get_bets(self):
        rows = self.conn.execute("SELECT * FROM bets ORDER BY placed_at, id").fetchall()
        return [self._bet(r) for r in rows]

    def add_bet(self, b: Bet) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO bets(placed_at,match,tournament,bet_type,stake,odds,result,comment) VALUES(?,?,?,?,?,?,?,?)",
                (b.placed_at.strftime(TS), b.match.strip(), b.tournament.strip(), b.bet_type,
                 str(q2(b.stake)), str(b.odds), b.result, b.comment.strip()))
        self.dirty = True
        return cur.lastrowid

    def update_bet(self, b: Bet):
        with self.conn:
            self.conn.execute(
                "UPDATE bets SET placed_at=?,match=?,tournament=?,bet_type=?,stake=?,odds=?,result=?,comment=? WHERE id=?",
                (b.placed_at.strftime(TS), b.match.strip(), b.tournament.strip(), b.bet_type,
                 str(q2(b.stake)), str(b.odds), b.result, b.comment.strip(), b.id))
        self.dirty = True

    def set_result(self, bet_id: int, result: str):
        with self.conn:
            self.conn.execute("UPDATE bets SET result=? WHERE id=?", (result, bet_id))
        self.dirty = True

    def delete_bets(self, ids):
        with self.conn:
            self.conn.executemany("DELETE FROM bets WHERE id=?", [(i,) for i in ids])
        self.dirty = True

    # ---------- банк ----------
    def get_ops(self):
        rows = self.conn.execute("SELECT * FROM bank_ops ORDER BY ts, id").fetchall()
        return [BankOp(r["id"], datetime.strptime(r["ts"], TS), r["kind"], Decimal(r["amount"]), r["comment"])
                for r in rows]

    def add_op(self, kind: str, amount: Decimal, comment: str = "", ts: datetime | None = None) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO bank_ops(ts,kind,amount,comment) VALUES(?,?,?,?)",
                                    ((ts or datetime.now()).strftime(TS), kind, str(q2(amount)), comment.strip()))
        self.dirty = True
        return cur.lastrowid

    def delete_op(self, op_id: int):
        with self.conn:
            cur = self.conn.execute("DELETE FROM bank_ops WHERE id=?", (op_id,))
            if cur.rowcount != 1:          # откатываем, если удалилось не ровно одна запись
                raise RuntimeError("Операция не найдена в базе данных")
        self.dirty = True

    # ---------- настройки ----------
    def get_setting(self, key: str) -> str:
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else DEFAULT_SETTINGS.get(key, "")

    def set_setting(self, key: str, value: str):
        with self.conn:
            self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        self.dirty = True

    # ---------- резервные копии ----------
    def backup_to(self, dest) -> Path:
        """Согласованная копия базы: сначала во временный файл, потом атомарная замена."""
        dest = Path(dest)
        tmp = dest.with_name(dest.name + ".tmp")
        if tmp.exists():
            tmp.unlink()
        out = sqlite3.connect(tmp)
        try:
            self.conn.backup(out)
        finally:
            out.close()
        os.replace(tmp, dest)
        self.dirty = False
        return dest

    def list_backups(self):
        files = [p for p in self.backup_dir.glob("*.db") if p.is_file()]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def auto_backup(self, tag: str = "auto", keep: int | None = None) -> Path:
        name = f"bets_{datetime.now():%Y%m%d_%H%M%S}_{tag}.db"
        p = self.backup_to(self.backup_dir / name)
        if tag == "auto":
            keep = keep if keep is not None else int(self.get_setting("backup_keep") or 15)
            autos = [f for f in self.list_backups() if f.stem.endswith("_auto")]
            for old in autos[max(keep, 1):]:
                try:
                    old.unlink()
                except OSError:
                    pass
        return p

    def last_backup_time(self):
        b = self.list_backups()
        return datetime.fromtimestamp(b[0].stat().st_mtime) if b else None

    @staticmethod
    def check_backup(path) -> None:
        """Проверяет, что файл — рабочая база этой программы. ValueError с понятным текстом."""
        path = Path(path)
        if not path.is_file():
            raise ValueError("Файл не найден")
        try:
            s = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            try:
                if s.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Файл повреждён")
                tables = {r[0] for r in s.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                s.close()
        except sqlite3.Error:
            raise ValueError("Это не файл базы данных или он повреждён")
        if not {"bets", "bank_ops"} <= tables:
            raise ValueError("Это не резервная копия этой программы")

    def restore_from(self, path) -> None:
        self.check_backup(path)
        self.auto_backup("before_restore")          # страховка на случай ошибки выбора
        s = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
        try:
            s.backup(self.conn)
        finally:
            s.close()
        self._ensure_schema()
        self.dirty = True
