"""Проверка системы обновлений на локальном сервере: проверка версии, delta/full, хэши, защита от подмены."""
import json, os, sys, tempfile, threading, zipfile, hashlib, shutil
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import updater as U


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def sha(b): return hashlib.sha256(b).hexdigest()


class Upd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.srv_dir = self.tmp / "srv"; self.srv_dir.mkdir()
        self.install = self.tmp / "app"; (self.install / "_internal").mkdir(parents=True)
        self.old = {"App.exe": b"exe-v1", "_internal/lib.dll": b"LIB", "_internal/data.txt": b"d1"}
        self.new = {"App.exe": b"exe-v2", "_internal/lib.dll": b"LIB", "_internal/data.txt": b"d2", "_internal/new.txt": b"n"}
        for k, v in self.old.items(): (self.install / k).write_bytes(v)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(self.srv_dir)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}/"

    def tearDown(self):
        self.httpd.shutdown(); shutil.rmtree(self.tmp, ignore_errors=True)

    def zip(self, name, files):
        p = self.srv_dir / name
        with zipfile.ZipFile(p, "w") as z:
            for k, v in files.items(): z.writestr(k, v)
        return {"url": name, "sha256": sha(p.read_bytes()), "size": p.stat().st_size}

    def manifest(self, **over):
        changed = {k: v for k, v in self.new.items() if self.old.get(k) != v}
        m = {"version": "1.2.0", "released": "2026-11-20", "notes": ["a", "b"],
             "files": {k: sha(v) for k, v in self.new.items()},
             "full": self.zip("full.zip", self.new), "delta": {"from": "1.1.0", **self.zip("delta.zip", changed)}}
        m.update(over)
        (self.srv_dir / "latest.json").write_text(json.dumps(m))

    def test_versions_and_urls(self):
        self.assertGreater(U.parse_version("1.10.0"), U.parse_version("1.9.9"))
        self.assertEqual(U.normalize_url("https://github.com/me/repo"), "https://github.com/me/repo/releases/latest/download/latest.json")
        with self.assertRaises(U.UpdateError): U.normalize_url("http://evil.example/x.json")
        with self.assertRaises(U.UpdateError): U.normalize_url("")

    def test_no_update(self):
        self.manifest()
        self.assertIsNone(U.check("1.2.0", self.base + "latest.json"))
        self.assertIsNone(U.check("1.3.0", self.base + "latest.json"))

    def test_delta_flow(self):
        self.manifest()
        info = U.check("1.1.0", self.base + "latest.json")
        self.assertEqual((info.version, info.package.kind, info.notes), ("1.2.0", "delta", ["a", "b"]))
        self.assertIsNotNone(info.fallback)
        z = U.download(info.package, self.tmp / "dl" / "d.zip")
        U.extract_safe(z, self.tmp / "stage")
        self.assertEqual(sorted(p.name for p in (self.tmp / "stage").rglob("*") if p.is_file()), ["App.exe", "data.txt", "new.txt"])  # lib.dll не качался
        U.verify_result(self.tmp / "stage", self.install, info.files)

    def test_full_when_other_version(self):
        self.manifest()
        info = U.check("1.0.0", self.base + "latest.json")
        self.assertEqual(info.package.kind, "full")

    def test_tampered_package_rejected(self):
        self.manifest()
        info = U.check("1.1.0", self.base + "latest.json")
        (self.srv_dir / "delta.zip").write_bytes((self.srv_dir / "delta.zip").read_bytes() + b"x")
        with self.assertRaises(U.UpdateError): U.download(info.package, self.tmp / "d.zip")
        self.assertFalse((self.tmp / "d.zip").exists())

    def test_verify_detects_mismatch(self):
        self.manifest()
        info = U.check("1.1.0", self.base + "latest.json")
        z = U.download(info.package, self.tmp / "d.zip"); U.extract_safe(z, self.tmp / "stage")
        (self.install / "_internal/lib.dll").write_bytes(b"CORRUPT")
        with self.assertRaises(U.UpdateError): U.verify_result(self.tmp / "stage", self.install, info.files)

    def test_zip_slip(self):
        p = self.tmp / "evil.zip"
        with zipfile.ZipFile(p, "w") as z: z.writestr("../evil.txt", "x")
        with self.assertRaises(U.UpdateError): U.extract_safe(p, self.tmp / "st")

    def test_bat_is_ascii(self):
        U.APPLY_BAT.encode("ascii")


if __name__ == "__main__":
    unittest.main()


class Hardening(unittest.TestCase):
    """Проверки правок: адреса, скрипт установки, очистка, версия установщика."""

    def test_url_variants(self):
        want = "https://github.com/hesagoo/dota-bet-tracker/releases/latest/download/latest.json"
        for u in ("https://github.com/hesagoo/dota-bet-tracker", "https://github.com/hesagoo/dota-bet-tracker/",
                  "https://github.com/hesagoo/dota-bet-tracker.git", "https://github.com/hesagoo/dota-bet-tracker/releases",
                  "https://github.com/hesagoo/dota-bet-tracker/releases/latest",
                  "https://github.com/hesagoo/dota-bet-tracker/releases/tag/v1.1.0",
                  "github.com/hesagoo/dota-bet-tracker", "git@github.com:hesagoo/dota-bet-tracker.git", want):
            self.assertEqual(U.normalize_url(u), want, u)
        self.assertEqual(U.clean_input("https://github.com/hesagoo/dota-bet-tracker/releases"), "https://github.com/hesagoo/dota-bet-tracker")
        self.assertEqual(U.clean_input(want), want)           # прямая ссылка на файл не ломается
        for bad in ("https://github.com/hesagoo", "https://example.com/page", "http://evil.example/x.json", ""):
            with self.assertRaises(U.UpdateError): U.normalize_url(bad)

    def test_html_page_instead_of_manifest(self):
        d = Path(tempfile.mkdtemp()); (d / "latest.json").write_text("<!DOCTYPE html><html>page</html>")
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(d)))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(U.UpdateError) as c: U.fetch_manifest(f"http://127.0.0.1:{httpd.server_address[1]}/latest.json")
            self.assertIn("веб-страница", str(c.exception))
            with self.assertRaises(U.UpdateError) as c: U.fetch_manifest(f"http://127.0.0.1:{httpd.server_address[1]}/missing.json")
            self.assertIn("HTTP 404", str(c.exception)); self.assertIn("релиз", str(c.exception))
        finally:
            httpd.shutdown()

    def test_apply_script(self):
        bat = U.APPLY_BAT
        bat.encode("ascii")
        self.assertNotIn("timeout", bat.lower())
        self.assertIn("ping -n 2 127.0.0.1", bat)
        self.assertIn("GEQ 90", bat)
        self.assertEqual(bat.count("ping -n"), 3)
        import re
        labels = set(re.findall(r"^:(\w+)", bat, re.M))
        for g in re.findall(r"goto (\w+)", bat):
            self.assertIn(g, labels, g)
        self.assertEqual(bat.count("("), bat.count(")"))
        ok_part = bat.split(":ok")[1].split(":rollback")[0]
        self.assertIn('del /q "%WORK_DIR%\\*.zip"', ok_part)
        for var in set(re.findall(r"%([A-Z_]+)%", bat)):
            self.assertIn(var, {"APP_PID", "APP_DIR", "STAGE_DIR", "BAK_DIR", "EXE_NAME", "FLAG", "LOG", "WORK_DIR"})

    def test_launch_flags_and_env(self):
        calls = {}
        class FakePopen:
            def __init__(self, *a, **k): calls.update(k); calls["args"] = a
        old_p, old_plat = U.subprocess.Popen, U.sys.platform
        U.subprocess.Popen, U.sys.platform = FakePopen, "win32"
        try:
            tmp = Path(tempfile.mkdtemp())
            U.launch_apply(tmp / "stage", tmp / "app", "App.exe", tmp / "updates")
        finally:
            U.subprocess.Popen, U.sys.platform = old_p, old_plat
        self.assertEqual(calls["creationflags"], 0x08000000 | 0x00000200)
        self.assertEqual(calls["creationflags"] & 0x00000008, 0)          # DETACHED_PROCESS не используется
        for k in ("APP_PID", "APP_DIR", "STAGE_DIR", "BAK_DIR", "EXE_NAME", "FLAG", "LOG", "WORK_DIR"):
            self.assertIn(k, calls["env"])
        self.assertEqual(calls["env"]["WORK_DIR"], str(tmp / "updates"))
        self.assertTrue((tmp / "updates" / "apply_update.bat").read_bytes().count(b"\r\n") > 10)

    def test_cleanup(self):
        w = Path(tempfile.mkdtemp())
        (w / "delta-1.2.0.zip").write_bytes(b"z"); (w / "x.zip.part").write_bytes(b"p"); (w / "staging" / "a").mkdir(parents=True)
        (w / "update.log").write_text("log"); (w / "app_backup").mkdir(); (w / "app_backup" / "keep.txt").write_text("k")
        U.cleanup_downloads(w)
        self.assertEqual(sorted(p.name for p in w.iterdir()), ["app_backup", "update.log"])
        U.cleanup_downloads(w / "nope")                                   # несуществующая папка — без ошибок

    def test_installer_version_from_version_py(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import write_installer_version as W, version
        self.assertIn(f'#define AppVersion "{version.__version__}"', W.render())
        root = Path(__file__).resolve().parent.parent
        iss = (root / "installer" / "DotaBetTracker.iss").read_text(encoding="utf-8")
        self.assertIn('#include "app_version.iss"', iss)
        self.assertNotRegex(iss, r'#define AppVersion "\d')               # номер вручную больше не записан
        self.assertIn(f'#define AppVersion "{version.__version__}"', (root / "installer" / "app_version.iss").read_text(encoding="utf-8"),
                      "запустите tools/write_installer_version.py — app_version.iss устарел")
