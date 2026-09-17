from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import gui.main_window as main_window_module
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    original_config_file = main_window_module.CONFIG_FILE

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        main_window_module.CONFIG_FILE = temp_path / "config.json"
        paths = []
        for index, color in enumerate(("red", "green", "blue", "yellow"), start=1):
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
            window.current_project_file = str(temp_path / "clipboard_test.fds")
            window.row_step.setValue(1)
            window.col_step.setValue(2)

            for path in paths:
                window.image_list.addItem(window._create_external_image_item(path))
                window.image_transforms[path] = window.get_transform(path)
            window.image_transforms[paths[0]]["scale"] = 1.35
            window.refresh_preview()
            app.processEvents()

            first_item = window.image_list.item(0)
            first_item.setSelected(True)
            window.image_list.setCurrentItem(first_item)
            window.image_list.setFocus(Qt.FocusReason.OtherFocusReason)
            window.shortcut_copy_images()
            assert len(window._image_clipboard) == 1

            # Page 2 is full. Pasted content must displace its last item
            # instead of being appended as the first item of page 3.
            window.on_thumbnail_page_selected(1)
            window.paste_images_to_current_page()
            app.processEvents()

            result = window.ordered_images()
            assert len(result) == 5
            pasted_path = next(path for path in result if path not in paths)
            assert pasted_path != paths[0]
            assert Path(pasted_path).is_file()
            assert window.image_transforms[pasted_path]["scale"] == 1.35
            assert window._page_visible_range(0) == (0, 2)
            assert window._page_visible_range(1) == (2, 4)
            page_start, page_end = window._page_visible_range(1)
            assert pasted_path in window.visible_images()[page_start:page_end]
            assert window.preview.current_page() == 1

            # Cut moves the original path and transform; it does not create
            # another file. A successful paste turns the clipboard into copy
            # mode, matching desktop clipboard behavior.
            cut_path = paths[1]
            window.image_transforms[cut_path]["rotation"] = 90
            cut_row = window.ordered_images().index(cut_path)
            window.image_list.clearSelection()
            window.image_list.item(cut_row).setSelected(True)
            window.image_list.setCurrentRow(cut_row)
            window.shortcut_cut_images()
            assert cut_path not in window.ordered_images()
            assert Path(cut_path).is_file()
            assert window._image_clipboard_mode == "cut"

            window.on_thumbnail_page_selected(1)
            window.paste_images_to_current_page()
            app.processEvents()
            assert window.ordered_images().count(cut_path) == 1
            assert window.image_transforms[cut_path]["rotation"] == 90
            page_start, page_end = window._page_visible_range(1)
            assert cut_path in window.visible_images()[page_start:page_end]
            assert window._image_clipboard_mode == "copy"

            window.paste_images_to_current_page()
            assert len(window.ordered_images()) == 6
            assert window.ordered_images().count(cut_path) == 1
            print("image clipboard: full-page paste and cut/paste behavior passed")
        finally:
            main_window_module.CONFIG_FILE = original_config_file
            if window is not None:
                window._close_in_progress = True
                window.image_list.clear()
                window.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
