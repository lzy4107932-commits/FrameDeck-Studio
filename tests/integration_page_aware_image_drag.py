from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import gui.main_window as main_window_module
from gui.main_window import MainWindow


def _names(window: MainWindow) -> list[str]:
    return [Path(path).name for path in window.ordered_images()]


def main() -> None:
    app = QApplication.instance() or QApplication([])
    original_config_file = main_window_module.CONFIG_FILE

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        main_window_module.CONFIG_FILE = temp_path / "config.json"
        paths = []
        for index, color in enumerate(("red", "green", "blue", "yellow")):
            path = temp_path / f"image_{index}.png"
            image = QImage(80, 60, QImage.Format.Format_RGB32)
            image.fill(QColor(color))
            assert image.save(str(path))
            paths.append(str(path))

        window = None
        try:
            window = MainWindow(app)
            window.autosave_timer.stop()
            window.preview_timer.stop()
            window._page_thumbnail_debounce_timer.stop()
            window._page_thumbnail_render_timer.stop()
            window.row_step.setValue(1)
            window.col_step.setValue(2)
            for path in paths:
                window.image_list.addItem(window._create_external_image_item(path))
            window.refresh_preview()
            app.processEvents()

            # The linear order is already A2, B1, but dropping A2 on the
            # upper edge of B1 transfers A2 to the next page by moving the
            # page boundary.  B2 then overflows naturally to a third page.
            assert window.handle_image_list_internal_drop([1], 2, affinity="before")
            assert _names(window) == ["image_0.png", "image_1.png", "image_2.png", "image_3.png"]
            transferred_ranges = [
                window._page_visible_range(index)
                for index in range(window.preview.page_count())
            ]
            assert transferred_ranges == [(0, 1), (1, 3), (3, 4)], transferred_ranges
            window.undo()
            assert window._page_visible_range(0) == (0, 2)
            assert window._page_visible_range(1) == (2, 4)

            assert window._swap_image_list_slots([1], 2)
            assert _names(window) == ["image_0.png", "image_2.png", "image_1.png", "image_3.png"]
            assert window._page_visible_range(0) == (0, 2)
            assert window._page_visible_range(1) == (2, 4)

            window.undo()
            assert _names(window) == ["image_0.png", "image_1.png", "image_2.png", "image_3.png"]
            window.redo()
            assert _names(window) == ["image_0.png", "image_2.png", "image_1.png", "image_3.png"]

            assert window.on_thumbnail_image_drop(1, [0], "start")
            assert _names(window) == ["image_2.png", "image_1.png", "image_0.png", "image_3.png"]
            assert window._page_visible_range(0) == (0, 2)
            assert window._page_visible_range(1) == (2, 4)

            assert window.on_thumbnail_image_drop(0, [3], "end")
            assert _names(window) == ["image_2.png", "image_3.png", "image_1.png", "image_0.png"]
            assert window._page_visible_range(0) == (0, 2)
            assert window._page_visible_range(1) == (2, 4)

            before_lock = _names(window)
            window._displayed_page_index = 0
            window.preview.set_page_index(0)
            window.toggle_current_page_lock()
            assert not window.on_thumbnail_image_drop(0, [2], "start")
            assert _names(window) == before_lock

            print("page-aware image drag: swap, page start/end, undo/redo, and lock checks passed")
        finally:
            main_window_module.CONFIG_FILE = original_config_file
            if window is not None:
                window._close_in_progress = True
                window.image_list.clear()
                window.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
