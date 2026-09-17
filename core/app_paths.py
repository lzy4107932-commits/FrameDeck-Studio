from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "FrameDeck Studio"
APP_VERSION = "12.0"


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    path = base / "FrameDeck Studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def autosave_file() -> Path:
    return user_data_dir() / "autosave.fds"


def settings_file() -> Path:
    return user_data_dir() / "settings.json"


def recent_file() -> Path:
    return user_data_dir() / "recent.json"


def crash_marker_file() -> Path:
    return user_data_dir() / "last_crash.json"


def resource_path(relative: str) -> str:
    return str(bundled_root() / relative)
