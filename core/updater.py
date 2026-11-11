"""Обновление программы по сети: проверка версии, скачивание только изменённых файлов,
проверка контрольных сумм, подготовка к установке с откатом.

Схема (подробнее — docs/UPDATES.md):
  latest.json  ->  версия + список изменений + ссылки на пакеты + SHA-256 каждого файла новой версии
  delta-пакет  ->  только файлы, изменившиеся с предыдущей версии (если у пользователя именно она)
  full-пакет   ->  вся папка программы (запасной вариант)
Пользовательские данные лежат отдельно (%APPDATA%\\DotaBets) и обновлением не затрагиваются."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT = 15
CHUNK = 1024 * 256


class UpdateError(Exception):
    pass


@dataclass
class Package:
    url: str
    sha256: str
    size: int
    kind: str                       # "delta" | "full"


@dataclass
class UpdateInfo:
    version: str
    released: str
    notes: list
    package: Package
    files: dict = field(default_factory=dict)       # относительный путь -> sha256 (вся новая версия)
    fallback: "Package | None" = None               # full-пакет, если delta не подойдёт


def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", str(v))
    if not nums:
        raise UpdateError(f"Непонятная версия: {v!r}")
    return tuple(int(x) for x in nums[:4]) + (0,) * (3 - len(nums[:4]))


_BAD_ADDR = ("Укажите адрес репозитория GitHub (https://github.com/логин/репозиторий) "
             "или прямую ссылку на файл latest.json.")


def _github_repo(url: str):
    """(владелец, репозиторий), если это любая ссылка на репозиторий GitHub: страница релизов,
    ветка, git-адрес и т.п. Прямые ссылки на файлы .json сюда не относятся."""
    u = (url or "").strip()
    m = re.match(r"^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", u)
    if m:
        return m.group(1), m.group(2)
    if re.match(r"^(www\.)?github\.com/", u, re.I):
        u = "https://" + u
    p = urllib.parse.urlparse(u)
    if p.scheme in ("http", "https") and p.netloc.lower() in ("github.com", "www.github.com"):
        if p.path.lower().endswith(".json"):
            return None
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            repo = parts[1][:-4] if parts[1].lower().endswith(".git") else parts[1]
            return parts[0], repo
        raise UpdateError("В адресе не хватает названия репозитория. Нужен вид: https://github.com/логин/репозиторий")
    return None


def clean_input(url: str) -> str:
    """Приводит введённый адрес к аккуратному виду (для поля в настройках). Ничего не проверяет по сети."""
    url = (url or "").strip()
    try:
        r = _github_repo(url)
    except UpdateError:
        return url
    return f"https://github.com/{r[0]}/{r[1]}" if r else url


def normalize_url(url: str) -> str:
    """Принимает адрес репозитория GitHub (в том числе ссылку на страницу Releases) или прямую ссылку на latest.json."""
    url = (url or "").strip()
    if not url:
        raise UpdateError("Не указан адрес обновлений")
    r = _github_repo(url)
    if r:
        return f"https://github.com/{r[0]}/{r[1]}/releases/latest/download/latest.json"
    if re.match(r"^(www\.)?github\.com/", url, re.I):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    local = p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")
    if not (p.scheme in ("https", "file") or local):
        raise UpdateError("Адрес обновлений должен начинаться с https://. " + _BAD_ADDR)
    if not p.path.lower().endswith(".json"):
        raise UpdateError("По этому адресу нет файла latest.json. " + _BAD_ADDR)
    return url


def _get(url: str, timeout=TIMEOUT, what="manifest"):
    req = urllib.request.Request(url, headers={"User-Agent": "DotaBetTracker-Updater"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404 and what == "manifest":
            raise UpdateError("Файл latest.json не найден (HTTP 404). Возможные причины: на GitHub ещё нет опубликованного "
                              "релиза (черновик и pre-release не считаются), в релиз не загружен файл latest.json "
                              "или адрес указан неверно.")
        if e.code == 404:
            raise UpdateError("Файл обновления не найден на сервере (HTTP 404). Проверьте, что в релиз загружены все файлы.")
        raise UpdateError(f"Сервер ответил ошибкой (HTTP {e.code}). Попробуйте позже.")
    except Exception as e:
        raise UpdateError(f"Не удалось подключиться: {e}")


def fetch_manifest(url: str) -> dict:
    with _get(normalize_url(url)) as r:
        raw = r.read().decode("utf-8-sig", errors="replace")
    try:
        return json.loads(raw)
    except ValueError:
        if raw.lstrip().lower().startswith(("<!doctype", "<html", "<")):
            raise UpdateError("По этому адресу открывается веб-страница, а не файл latest.json. " + _BAD_ADDR)
        raise UpdateError("Файл обновлений повреждён (latest.json)")


def _package(d: dict, base: str, kind: str) -> Package:
    try:
        return Package(urllib.parse.urljoin(base, d["url"]), str(d["sha256"]).lower(), int(d["size"]), kind)
    except (KeyError, TypeError, ValueError):
        raise UpdateError("В latest.json неверно описан пакет обновления")


def check(current: str, url: str):
    """Возвращает UpdateInfo, если на сервере версия новее текущей, иначе None."""
    base = normalize_url(url)
    m = fetch_manifest(url)
    try:
        newest = str(m["version"])
    except KeyError:
        raise UpdateError("В latest.json нет номера версии")
    if parse_version(newest) <= parse_version(current):
        return None
    if "min_version" in m and parse_version(current) < parse_version(m["min_version"]):
        raise UpdateError(f"Версия {current} слишком старая для автообновления. Скачайте установщик {newest} вручную.")
    full = _package(m["full"], base, "full") if "full" in m else None
    delta = None
    if "delta" in m and str(m["delta"].get("from")) == str(current):
        delta = _package(m["delta"], base, "delta")
    pkg = delta or full
    if not pkg:
        raise UpdateError("В latest.json нет пакета обновления")
    notes = m.get("notes", [])
    if isinstance(notes, str):
        notes = [notes]
    return UpdateInfo(newest, str(m.get("released", "")), list(notes), pkg, dict(m.get("files", {})),
                      full if delta else None)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def download(pkg: Package, dest: Path, progress=None, should_cancel=lambda: False) -> Path:
    """Скачивает пакет во временный файл, проверяет размер и SHA-256, только потом переименовывает."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    h, done = hashlib.sha256(), 0
    with _get(pkg.url, timeout=30, what="package") as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or pkg.size or 0)
        while True:
            if should_cancel():
                tmp.unlink(missing_ok=True)
                raise UpdateError("Загрузка отменена")
            chunk = r.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if pkg.size and done != pkg.size:
        tmp.unlink(missing_ok=True)
        raise UpdateError("Файл скачался не полностью. Попробуйте ещё раз.")
    if h.hexdigest() != pkg.sha256:
        tmp.unlink(missing_ok=True)
        raise UpdateError("Контрольная сумма не совпала — файл повреждён или подменён. Обновление отменено.")
    os.replace(tmp, dest)
    return dest


def extract_safe(zip_path: Path, stage: Path) -> None:
    """Распаковка с защитой от выхода за пределы папки (zip-slip)."""
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    root = stage.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            target = (stage / name).resolve()
            if root != target and root not in target.parents:
                raise UpdateError("В архиве обновления найден небезопасный путь")
        z.extractall(stage)


def verify_result(stage: Path, install_dir: Path, files: dict) -> None:
    """Проверяет, что «установленные файлы + новые файлы» в точности равны новой версии из manifest."""
    for rel, want in files.items():
        p = stage / rel
        if not p.exists():
            p = install_dir / rel
        if not p.exists():
            raise UpdateError(f"Не хватает файла {rel}")
        if sha256_file(p) != str(want).lower():
            raise UpdateError(f"Файл {rel} не совпадает с версией на сервере")


APPLY_BAT = r"""@echo off
setlocal
echo [%date% %time%] update started > "%LOG%"
:wait
tasklist /FI "PID eq %APP_PID%" 2>nul | find "%APP_PID%" >nul
if not errorlevel 1 (
  ping -n 2 127.0.0.1 >nul
  goto wait
)
if exist "%BAK_DIR%" rmdir /s /q "%BAK_DIR%"
robocopy "%APP_DIR%" "%BAK_DIR%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS >> "%LOG%"
if errorlevel 8 goto fail
robocopy "%STAGE_DIR%" "%APP_DIR%" /E /IS /IT /R:3 /W:1 /NFL /NDL /NJH /NJS >> "%LOG%"
if errorlevel 8 goto rollback
if exist "%FLAG%" del /q "%FLAG%"
start "" "%APP_DIR%\%EXE_NAME%"
set /a n=0
:probe
if exist "%FLAG%" goto ok
set /a n+=1
if %n% GEQ 90 goto rollback
ping -n 2 127.0.0.1 >nul
goto probe
:ok
echo update ok >> "%LOG%"
rmdir /s /q "%STAGE_DIR%" 2>nul
del /q "%WORK_DIR%\*.zip" 2>nul
del /q "%WORK_DIR%\*.part" 2>nul
exit /b 0
:rollback
echo ROLLBACK: new version did not start >> "%LOG%"
taskkill /F /IM "%EXE_NAME%" >nul 2>nul
ping -n 3 127.0.0.1 >nul
robocopy "%BAK_DIR%" "%APP_DIR%" /MIR /R:3 /W:1 /NFL /NDL /NJH /NJS >> "%LOG%"
:fail
start "" "%APP_DIR%\%EXE_NAME%"
exit /b 1
"""


def cleanup_downloads(work_dir) -> None:
    """Убирает скачанные пакеты (*.zip, *.part) и папку распаковки. Копию программы (app_backup) и журнал не трогает.
    Вызывается при успешном запуске программы и после неудачной подготовки обновления."""
    work_dir = Path(work_dir)
    if not work_dir.is_dir():
        return
    for pat in ("*.zip", "*.part"):
        for f in work_dir.glob(pat):
            try:
                f.unlink()
            except OSError:
                pass
    shutil.rmtree(work_dir / "staging", ignore_errors=True)


def launch_apply(stage: Path, install_dir: Path, exe_name: str, work_dir: Path) -> Path:
    """Запускает отдельный скрипт, который после закрытия программы заменит файлы, проверит запуск
    и при неудаче вернёт старую версию. Пути передаются через переменные окружения (скрипт — чистый ASCII)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    bat = work_dir / "apply_update.bat"
    bat.write_text(APPLY_BAT.replace("\n", "\r\n"), encoding="ascii")
    env = dict(os.environ, APP_PID=str(os.getpid()), APP_DIR=str(install_dir), STAGE_DIR=str(stage),
               BAK_DIR=str(work_dir / "app_backup"), EXE_NAME=exe_name, FLAG=str(work_dir / "started_ok.flag"),
               LOG=str(work_dir / "update.log"), WORK_DIR=str(work_dir))
    flags = 0
    if sys.platform == "win32":
        # Только CREATE_NO_WINDOW (скрытая консоль) + новая группа процессов. DETACHED_PROCESS с ним несовместим:
        # Windows игнорирует «без окна», а команды вроде timeout остаются без консоли.
        flags = 0x08000000 | 0x00000200
    subprocess.Popen(["cmd", "/c", str(bat)], env=env, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return bat
