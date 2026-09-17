from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "windows" if "--windows" in sys.argv else "offscreen",
)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import gui.main_window as main_window_module
from gui.main_window import MainWindow, THEME_META


def main() -> None:
    app = QApplication.instance() or QApplication([])
    output_dir = Path(tempfile.gettempdir()) / "framedeck_ui_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    original_config_file = main_window_module.CONFIG_FILE

    with tempfile.TemporaryDirectory() as temp_dir:
        main_window_module.CONFIG_FILE = Path(temp_dir) / "config.json"
        window = None
        try:
            window = MainWindow(app)
            window.autosave_timer.stop()
            window._config_save_timer.stop()
            window.show()

            captures = (
                ("light_default", "zh_CN", "极光浅色", 1480, 920),
                ("gray_default", "zh_CN", "雾银灰", 1480, 920),
                ("dark_default", "zh_CN", "深空暗色", 1480, 920),
                ("ocean_default", "zh_CN", "海洋蓝", 1480, 920),
                ("coral_default", "zh_CN", "珊瑚暮色", 1480, 920),
                ("light_compact", "zh_CN", "极光浅色", 1024, 650),
                ("dark_english", "en_US", "深空暗色", 1480, 920),
                ("dark_english_compact", "en_US", "深空暗色", 1024, 650),
                ("dark_english_title", "en_US", "深空暗色", 1480, 920),
                ("light_spacing", "zh_CN", "极光浅色", 1480, 920),
                ("light_auto_layout", "zh_CN", "极光浅色", 1480, 920),
                ("dark_english_auto_layout_compact", "en_US", "深空暗色", 1024, 650),
            )
            expanded_sections = {
                "dark_english_title": "page_title",
                "light_spacing": "layout_spacing",
            }
            for name, language, theme, width, height in captures:
                window.set_language(language, persist=False)
                window.apply_theme(theme, persist=False)
                window.resize(width, height)
                section_key = expanded_sections.get(name, "page_layout")
                for key, card in window._collapsible_cards.items():
                    card.set_expanded(key == section_key, emit_signal=False)
                if "auto_layout" in name:
                    window.auto_layout_check.setChecked(True)
                app.processEvents()
                path = output_dir / f"{name}.png"
                assert window.grab().save(str(path), "PNG")
                print(path)
        finally:
            main_window_module.CONFIG_FILE = original_config_file
            if window is not None:
                window._close_in_progress = True
                window.preview_timer.stop()
                window._config_save_timer.stop()
                window._page_thumbnail_debounce_timer.stop()
                window._page_thumbnail_render_timer.stop()
                window.close()
                window.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
