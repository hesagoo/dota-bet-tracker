"""Записывает версию из version.py в installer/app_version.iss, чтобы установщик Inno Setup
всегда брал номер версии оттуда. Запускается автоматически из build_exe.bat; вручную: python tools/write_installer_version.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__, APP_NAME, EXE_NAME


def render() -> str:
    return (f"; Файл создан автоматически из version.py (tools/write_installer_version.py). Вручную не редактируйте.\n"
            f'#define AppVersion "{__version__}"\n')


def main():
    out = ROOT / "installer" / "app_version.iss"
    out.write_text(render(), encoding="utf-8")
    print(f"installer\\app_version.iss: версия {__version__}")


if __name__ == "__main__":
    main()
