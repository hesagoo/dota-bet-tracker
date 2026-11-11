"""Готовит файлы релиза для автообновления.
Запуск (после build_exe.bat):
    python tools/make_release.py --notes "Исправлено удаление операций" --notes "Помощник по ставке"
Что делает: считает хэши всех файлов сборки dist/DotaBetTracker, делает полный и дельта-пакет
(только изменённые файлы относительно прошлого релиза из папки release/) и пишет latest.json.
Версия берётся из version.py. Результат — папка release/<версия>/ : загрузите ВСЕ её файлы в GitHub Release."""
import argparse, hashlib, json, sys, zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__, EXE_NAME
from core.updater import parse_version


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pack(zpath: Path, build: Path, rels):
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for r in rels:
            z.write(build / r, r)
    return {"url": zpath.name, "sha256": sha(zpath), "size": zpath.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=str(ROOT / "dist" / EXE_NAME))
    ap.add_argument("--notes", action="append", default=[], help="строка списка изменений (можно несколько раз)")
    ap.add_argument("--notes-file", help="текстовый файл: одна строка — один пункт")
    ap.add_argument("--min-version", default="")
    a = ap.parse_args()
    build = Path(a.build)
    if not (build / f"{EXE_NAME}.exe").exists():
        sys.exit(f"Не найдена сборка: {build}\\{EXE_NAME}.exe — сначала запустите build_exe.bat")
    notes = list(a.notes)
    if a.notes_file:
        notes += [l.strip() for l in Path(a.notes_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = ROOT / "release" / __version__
    out.mkdir(parents=True, exist_ok=True)
    files = {p.relative_to(build).as_posix(): sha(p) for p in sorted(build.rglob("*")) if p.is_file()}
    prev = None
    for d in (ROOT / "release").iterdir():
        if d.is_dir() and (d / "files.json").exists() and d.name != __version__:
            try:
                if parse_version(d.name) < parse_version(__version__) and (prev is None or parse_version(d.name) > parse_version(prev.name)):
                    prev = d
            except Exception:
                pass
    m = {"version": __version__, "released": date.today().isoformat(), "notes": notes, "files": files}
    if a.min_version:
        m["min_version"] = a.min_version
    m["full"] = pack(out / f"{EXE_NAME}-{__version__}-full.zip", build, files)
    if prev:
        old = json.loads((prev / "files.json").read_text(encoding="utf-8"))
        changed = [r for r, h in files.items() if old.get(r) != h]
        m["delta"] = {"from": prev.name, **pack(out / f"{EXE_NAME}-{__version__}-delta-from-{prev.name}.zip", build, changed)}
        print(f"Дельта от {prev.name}: {len(changed)} файлов из {len(files)}")
    (out / "files.json").write_text(json.dumps(files, indent=1), encoding="utf-8")
    (out / "latest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Готово. Загрузите в GitHub Release все файлы из:", out)
    for f in sorted(out.iterdir()):
        print("  ", f.name, f"{f.stat().st_size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
