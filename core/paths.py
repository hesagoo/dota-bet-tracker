"""Где хранятся данные программы."""
import os
from pathlib import Path


def data_dir() -> Path:
    env = os.environ.get("DOTABETS_DATA_DIR")
    if env:
        p = Path(env)
    elif os.name == "nt":
        p = Path(os.environ.get("APPDATA", str(Path.home()))) / "DotaBets"
    else:
        p = Path.home() / ".dotabets"
    (p / "backups").mkdir(parents=True, exist_ok=True)
    return p


def app_root() -> Path:
    """Папка программы: рядом с EXE (после сборки) или корень проекта."""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(rel: str) -> Path:
    """Путь к встроенному файлу (иконка и т.п.) — работает и из исходников, и из EXE."""
    import sys
    base = Path(getattr(sys, "_MEIPASS", app_root()))
    return base / rel


def is_frozen() -> bool:
    import sys
    return bool(getattr(sys, "frozen", False))
