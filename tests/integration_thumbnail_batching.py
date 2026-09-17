from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QListWidgetItem

import gui.main_window as main_window_module
from gui.main_window import MainWindow, THUMBNAIL_ITEM_TOKEN_ROLE


def main() -> None:
    app = QApplication.instance() or QApplication([])
    original_config_file = main_window_module.CONFIG_FILE

    with tempfile.TemporaryDirectory() as temp_dir:
        main_window_module.CONFIG_FILE = Path(temp_dir) / "config.json"
        window = None
        try:
            window = MainWindow(app)
            window.autosave_timer.stop()
            window.preview_timer.stop()
            window._page_thumbnail_debounce_timer.stop()
            window._page_thumbnail_render_timer.stop()
            window._thumbnail_dispatch_timer.stop()
            window._thumbnail_priority_timer.stop()

            paths = [
                f"C:/FrameDeckSynthetic/image_{index:04d}.png"
                for index in range(2000)
            ]
            window.image_list.blockSignals(True)
            try:
                for token, path in enumerate(paths, start=1):
                    item = QListWidgetItem(path)
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    item.setData(THUMBNAIL_ITEM_TOKEN_ROLE, token)
                    window.image_list.addItem(item)
                    window._thumbnail_item_refs[token] = item
                    window._thumbnail_pending.append(
                        {
                            "generation": window._thumbnail_generation,
                            "request_id": token,
                            "token": token,
                            "path": path,
                            "heavy": False,
                        }
                    )
            finally:
                window.image_list.blockSignals(False)

            window.images = list(paths)
            window.preview.set_images(paths)
            window._thumbnail_priority_dirty = True

            priority_calls = [0]
            original_priority = window._thumbnail_entry_priority

            def counted_priority(entry, context):
                priority_calls[0] += 1
                return original_priority(entry, context)

            window._thumbnail_entry_priority = counted_priority
            started = time.perf_counter()
            first = window._next_thumbnail_entry()
            first_pass_calls = priority_calls[0]
            second = window._next_thumbnail_entry()
            while window._thumbnail_pending:
                window._next_thumbnail_entry()
            elapsed_ms = (time.perf_counter() - started) * 1000.0

            assert first is not None and second is not None
            assert first_pass_calls == len(paths)
            assert priority_calls[0] == first_pass_calls
            assert not window._thumbnail_priority_dirty

            window._thumbnail_pending.clear()
            window._thumbnail_item_refs.clear()
            page_count = window.preview.page_count()
            window._page_thumbnail_signatures = {
                index: f"signature-{index}"
                for index in range(page_count)
            }
            expected_dirty_pages = {
                window.preview.page_index_for_image(0),
                window.preview.page_index_for_image(13),
            }
            refresh_calls = [0]
            window.schedule_real_thumbnail_refresh = (
                lambda: refresh_calls.__setitem__(0, refresh_calls[0] + 1)
            )

            for path in (paths[0], paths[1], paths[13]):
                window._invalidate_navigation_thumbnail_for_path(path)
            window._thumbnail_navigation_flush_timer.stop()
            window._flush_navigation_thumbnail_invalidations()

            assert refresh_calls[0] == 1
            assert all(
                index not in window._page_thumbnail_signatures
                for index in expected_dirty_pages
            )
            assert not window._thumbnail_navigation_dirty_paths

            large = QPixmap(300, 190)
            large.fill(QColor("#4477AA"))
            window.slide_thumbnail_bar.set_pages([None])
            window.slide_thumbnail_bar.update_page_thumbnail(0, large)
            stored = window.slide_thumbnail_bar._page_sources[0]
            assert isinstance(stored, QPixmap)
            assert stored.width() <= 100 and stored.height() <= 60

            print(
                "2000 queued thumbnails: one priority pass, "
                f"complete drain in {elapsed_ms:.2f} ms; "
                "navigation invalidations: one refresh"
            )
        finally:
            main_window_module.CONFIG_FILE = original_config_file
            if window is not None:
                window._close_in_progress = True
                window._thumbnail_navigation_flush_timer.stop()
                window._page_thumbnail_debounce_timer.stop()
                window._page_thumbnail_render_timer.stop()
                window._thumbnail_pool.clear()
                window.image_list.clear()
                window.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
