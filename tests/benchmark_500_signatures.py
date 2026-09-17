from __future__ import annotations

import os
import sys
import time
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

    window.image_list.blockSignals(True)
    try:
        for index in range(500):
            path = f"C:/FrameDeckSynthetic/image_{index:04d}.png"
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            window.image_list.addItem(item)
    finally:
        window.image_list.blockSignals(False)

    window.images = window.visible_images()
    window.preview.set_images(window.images)

    resolved_calls = [0]
    original_resolver = window._resolved_title_pages

    def counted_resolver():
        resolved_calls[0] += 1
        return original_resolver()

    window._resolved_title_pages = counted_resolver
    page_count = max(1, int(window.preview.page_count()))
    started = time.perf_counter()
    signatures = window._page_thumbnail_signature_map(page_count)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    assert len(signatures) == page_count
    assert resolved_calls[0] == 1
    assert all(value is not None for value in signatures.values())
    print(
        f"500 images / {page_count} pages: {elapsed_ms:.2f} ms; "
        f"title resolutions: {resolved_calls[0]}"
    )

    window._close_in_progress = True
    window.image_list.clear()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
