from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(app)
    window.autosave_timer.stop()
    window.preview_timer.stop()
    window._page_thumbnail_debounce_timer.stop()
    window._page_thumbnail_render_timer.stop()
    # Keep this regression independent from the user's persisted layout.
    window.row_step.setValue(1)
    window.col_step.setValue(4)

    window.image_list.blockSignals(True)
    try:
        for index in range(24):
            path = f"C:/FrameDeckSynthetic/delete_{index:03d}.png"
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            window.image_list.addItem(item)
    finally:
        window.image_list.blockSignals(False)

    window.images = window.visible_images()
    window.preview.set_images(window.images)
    window.preview.set_settings(window.preview_settings())
    before_pages = int(window.preview.page_count())
    before_history = len(window.undo_stack)
    schedule_method = window.schedule_real_thumbnail_refresh

    assert before_pages == 6
    window.on_thumbnail_delete_pages([1, 3])

    after_pages = int(window.preview.page_count())
    assert after_pages == before_pages - 2
    assert len(window.undo_stack) == before_history + 1
    assert window.schedule_real_thumbnail_refresh == schedule_method
    assert not getattr(window, "_thumbnail_refresh_suspended", False)
    print(
        f"delete pages [1, 3]: {before_pages} -> {after_pages}; "
        "one history record; scheduler binding preserved"
    )

    window._close_in_progress = True
    window._page_thumbnail_debounce_timer.stop()
    window._page_thumbnail_render_timer.stop()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
