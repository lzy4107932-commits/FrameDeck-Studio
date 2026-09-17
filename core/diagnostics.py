from __future__ import annotations

import json
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from core.app_paths import crash_marker_file, logs_dir


def write_crash_log(exc_type, exc_value, exc_traceback) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir() / f"crash_{timestamp}.log"

    content = [
        "FrameDeck Studio V12 crash report",
        f"Time: {datetime.now().isoformat(timespec='seconds')}",
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        "",
        "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
    ]
    log_path.write_text("\n".join(content), encoding="utf-8")

    crash_marker_file().write_text(
        json.dumps(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "log": str(log_path),
                "message": str(exc_value),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return log_path


def install_exception_hook(show_error_callback=None) -> None:
    def handler(exc_type, exc_value, exc_traceback):
        log_path = write_crash_log(exc_type, exc_value, exc_traceback)
        if show_error_callback is not None:
            try:
                show_error_callback(str(exc_value), str(log_path))
                return
            except Exception:
                pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handler
