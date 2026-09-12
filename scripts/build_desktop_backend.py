import os
import shutil
from pathlib import Path

from PyInstaller.__main__ import run

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "desktop" / "src-tauri" / "resources" / "backend"
SEP = os.pathsep


def data(source: str, target: str) -> str:
    return f"{ROOT / source}{SEP}{target}"


shutil.rmtree(DIST, ignore_errors=True)
DIST.mkdir(parents=True)
run([
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name",
    "stocks-backend",
    "--distpath",
    str(DIST),
    "--workpath",
    str(ROOT / ".pyinstaller-work"),
    "--specpath",
    str(ROOT / ".pyinstaller-spec"),
    "--paths",
    str(ROOT / "backend"),
    "--paths",
    str(ROOT),
    "--add-data",
    data("backend/app", "backend/app"),
    "--add-data",
    data("collector", "collector"),
    "--add-data",
    data("shared", "shared"),
    "--add-data",
    data("scripts", "scripts"),
    str(ROOT / "scripts" / "desktop_bootstrap.py"),
])