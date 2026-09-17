from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import gui.main_window as main_window_module
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    original_config_file = main_window_module.CONFIG_FILE

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.json"
        main_window_module.CONFIG_FILE = config_file
        window = None
        try:
            window = MainWindow(app)
            window.autosave_timer.stop()
            window._config_save_timer.stop()

            window.save_config()
            first_stat = config_file.stat()
            first_text = config_file.read_text(encoding="utf-8")

            window.save_config()
            second_stat = config_file.stat()
            assert second_stat.st_mtime_ns == first_stat.st_mtime_ns
            assert config_file.read_text(encoding="utf-8") == first_text

            window.folder_edit.setText("D:/FrameDeck/config-coalescing-check")
            for _ in range(8):
                window.request_config_save()
            assert window._config_save_timer.isActive()

            window.save_config()
            assert not window._config_save_timer.isActive()
            payload = json.loads(config_file.read_text(encoding="utf-8"))
            assert payload["folder"] == "D:/FrameDeck/config-coalescing-check"

            print("unchanged config writes skipped; rapid save requests coalesced")
        finally:
            main_window_module.CONFIG_FILE = original_config_file
            if window is not None:
                window._close_in_progress = True
                window.preview_timer.stop()
                window._config_save_timer.stop()
                window._page_thumbnail_debounce_timer.stop()
                window._page_thumbnail_render_timer.stop()
                window.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
