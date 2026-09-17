from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QPushButton,
    QStyle,
    QToolButton,
)

from core.group_layout import PAGINATION_CONTINUOUS, PAGINATION_GROUPED
from gui.main_window import MainWindow, THEME_META


def _required_text_width(widget) -> int:
    text = str(widget.text() or "")
    required = widget.fontMetrics().horizontalAdvance(text)
    if isinstance(widget, QCheckBox):
        required += widget.style().pixelMetric(
            QStyle.PixelMetric.PM_IndicatorWidth,
            None,
            widget,
        )
        required += widget.style().pixelMetric(
            QStyle.PixelMetric.PM_CheckBoxLabelSpacing,
            None,
            widget,
        )
    elif isinstance(widget, (QPushButton, QToolButton)):
        required += 18
    return required


def _assert_left_panel_text_fits(window, app) -> None:
    failures = []
    for key, card in window._collapsible_cards.items():
        card.set_expanded(True)
        app.processEvents()

        header = card.header_button
        header_required = _required_text_width(header)
        if header_required > header.width():
            failures.append(
                (key, type(header).__name__, header.text(), header_required, header.width())
            )

        for widget_type in (QLabel, QCheckBox, QPushButton, QToolButton):
            for widget in card.content_widget.findChildren(widget_type):
                if not widget.isVisible() or not str(widget.text() or "").strip():
                    continue
                if isinstance(widget, QLabel) and widget.wordWrap():
                    continue
                required = _required_text_width(widget)
                if required > widget.width():
                    failures.append(
                        (
                            key,
                            type(widget).__name__,
                            widget.text(),
                            required,
                            widget.width(),
                        )
                    )

        for combo in card.content_widget.findChildren(QComboBox):
            if not combo.isVisible():
                continue
            required = combo.fontMetrics().horizontalAdvance(combo.currentText()) + 34
            if required > combo.width():
                failures.append(
                    (key, type(combo).__name__, combo.currentText(), required, combo.width())
                )

    assert not failures, failures


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(app)
    window.autosave_timer.stop()
    assert not hasattr(window, "_language_refresh_timer")
    window.show()
    app.processEvents()
    window.resize(1024, 650)
    app.processEvents()
    assert not window.header_layout_badge.isVisible()
    assert not window.header_project_badge.isVisible()
    assert not window.brand_title.isVisible()
    assert not window.brand_subtitle.isVisible()
    assert window.add_images_primary_button.isVisible()
    assert window.import_ppt_images_button.isVisible()
    assert window.start_btn.isVisible()

    window.resize(1480, 920)
    app.processEvents()
    assert window.header_layout_badge.isVisible()
    assert window.header_project_badge.isVisible()
    assert window.brand_title.isVisible()
    assert window.brand_subtitle.isVisible()
    assert window.brand_title.text() == "FrameDeck Studio"

    window.set_language("en_US", persist=False)
    app.processEvents()
    assert window.preview._settings["language"] == "en_US"
    assert "Add Images" in window.add_images_primary_button.text()
    assert "Import PPT" in window.import_ppt_images_button.text()
    assert window.image_search.placeholderText() == "Search…"
    assert window.auto_layout_check.text() == "Auto Layout"
    assert window.confirm_auto_layout_btn.text() == "Keep"
    assert window.left_scroll.width() == 328
    assert window.header_project_badge.text() == "Unsaved Project"
    assert not window.status_project.isVisible()
    assert window.status_project.parent() is window
    window.apply_theme("深空暗色", persist=False)
    assert window.status_bar.currentMessage().startswith("Theme changed to:")

    _assert_left_panel_text_fits(window, app)

    original_visible_images = window.visible_images
    original_refresh_preview = window.refresh_preview
    original_push_history = window.push_history
    try:
        fake_image_count = [10]
        window.visible_images = lambda: [
            f"image_{index}"
            for index in range(fake_image_count[0])
        ]
        window.refresh_preview = lambda: None
        window.push_history = lambda *_args, **_kwargs: None
        window.row_step.setValue(1)
        window.col_step.setValue(4)
        window._image_groups = [
            {"id": "group_a", "name": "A", "start": 0},
            {"id": "group_b", "name": "B", "start": 4},
        ]
        window._manual_page_breaks = {4}
        window._group_page_breaks = {4}
        window._blank_fill_page_breaks = set()
        window._set_pagination_mode(PAGINATION_GROUPED, refresh=False)
        assert not window.auto_layout_check.isChecked()
        assert window._current_pagination_mode() == PAGINATION_GROUPED, (
            window.pagination_mode_combo.currentIndex(),
            window.pagination_mode_combo.currentData(),
            window._pagination_mode,
            [
                window.pagination_mode_combo.itemData(index)
                for index in range(window.pagination_mode_combo.count())
            ],
        )
        assert window._computed_page_ranges() == [(0, 4), (4, 8), (8, 10)]

        window.row_step.setValue(2)
        grouped_ranges = window._computed_page_ranges()
        assert grouped_ranges == [(0, 4), (4, 10)], (
            grouped_ranges,
            window._current_pagination_mode(),
            window._effective_page_breaks(10),
            window._image_groups,
            window._group_page_breaks,
        )

        window.auto_layout_check.setChecked(True)
        app.processEvents()
        assert window._current_pagination_mode() == PAGINATION_CONTINUOUS
        assert window._effective_page_breaks(10) == []
        assert window._computed_page_ranges() == [(0, 8), (8, 10)]
        assert not window.confirm_auto_layout_btn.isHidden()
        assert window._auto_layout_restore_state is not None
        active_project_data = window.project_data()
        assert not active_project_data["confirmed_auto_layout"]
        assert active_project_data["auto_layout_restore_state"] is not None
        _assert_left_panel_text_fits(window, app)

        window.auto_layout_check.setChecked(False)
        app.processEvents()
        assert window._current_pagination_mode() == PAGINATION_GROUPED
        assert window._computed_page_ranges() == [(0, 4), (4, 10)]
        assert window.confirm_auto_layout_btn.isHidden()

        # Confirming keeps the auto-arranged version as the new fixed layout.
        window.auto_layout_check.setChecked(True)
        app.processEvents()
        window.confirm_auto_layout()
        app.processEvents()
        assert window._current_pagination_mode() == PAGINATION_GROUPED
        assert not window.auto_layout_check.isChecked()
        assert window._confirmed_auto_layout
        assert window._computed_page_ranges() == [(0, 8), (8, 10)]
        confirmed_project_data = window.project_data()
        assert confirmed_project_data["confirmed_auto_layout"]
        assert confirmed_project_data["auto_layout_restore_state"] is None

        # A later deletion shortens its page instead of pulling the next page up.
        window._shift_group_page_breaks_for_delete(
            [2],
            image_count_before=10,
        )
        fake_image_count[0] = 9
        assert window._computed_page_ranges() == [(0, 7), (7, 9)]
    finally:
        window.visible_images = original_visible_images
        window.refresh_preview = original_refresh_preview
        window.push_history = original_push_history

    expected_headers = {
        "page_layout": "Page Layout",
        "page_title": "Batch Title",
        "layout_spacing": "Layout Spacing",
        "image_adjust": "Image Adjustments",
        "display_settings": "Footer and Display",
    }
    for key, expected in expected_headers.items():
        card = window._collapsible_cards[key]
        card.set_expanded(True)
        app.processEvents()
        assert expected in card.header_button.text()
        card.set_expanded(False)
        app.processEvents()
        assert expected in card.header_button.text()

    window.refresh_preview()
    app.processEvents()
    assert window.header_project_badge.text() == "Unsaved Project"
    window.refresh_recent_state()
    assert window.header_project_badge.text() == "Unsaved Project"

    window.apply_zoom("适应窗口")
    assert window.status_zoom.text() == "Canvas Fit to Window"

    numeric_buttons = [
        window.row_step.minus,
        window.row_step.plus,
        window.col_step.minus,
        window.col_step.plus,
    ]
    assert all(
        button.property("fdNumericStepButton") is True
        for button in numeric_buttons
    )
    assert (
        window.title_font_size_input.buttonSymbols()
        == window.title_font_size_input.ButtonSymbols.PlusMinus
    )
    assert (
        window.image_zoom_input.buttonSymbols()
        == window.image_zoom_input.ButtonSymbols.PlusMinus
    )
    stylesheet = app.styleSheet()
    assert 'QPushButton#CompactCommandButton' in stylesheet
    assert 'background: qlineargradient' in stylesheet
    assert 'background-color: ' in stylesheet

    dialog = QDialog(window)
    label = QLabel("添加图片", dialog)
    dialog.show()
    app.processEvents()
    app.processEvents()
    assert label.text() == "Add Images"

    window.set_language("zh_CN", persist=False)
    app.processEvents()
    assert window.preview._settings["language"] == "zh_CN"
    assert "添加图片" in window.add_images_primary_button.text()
    assert "导入PPT" in window.import_ppt_images_button.text()
    assert label.text() == "添加图片"
    assert window.auto_layout_check.text() == "自动排版"
    assert window.confirm_auto_layout_btn.text() == "确认此次排版"
    assert window.left_scroll.width() == 226
    window._collapsible_cards["display_settings"].set_expanded(True)
    assert "页脚与显示" in window._collapsible_cards[
        "display_settings"
    ].header_button.text()
    window.apply_zoom("适应窗口")
    assert window.status_zoom.text() == "画布 适应窗口"

    theme_names = list(THEME_META)
    assert theme_names == [
        "极光浅色",
        "雾银灰",
        "深空暗色",
        "海洋蓝",
        "珊瑚暮色",
    ]
    for theme_name in theme_names:
        window.apply_theme(theme_name, persist=False)
        assert window.current_theme_name() == theme_name
        assert app.property("activeTheme") == theme_name
        assert window.styleSheet() == ""
        assert window.slide_thumbnail_bar.page_list.styleSheet() == ""
        assert window.slide_thumbnail_bar.add_button.styleSheet() == ""
        assert app.styleSheet()

    window.apply_theme("石墨专业", persist=False)
    assert window.current_theme_name() == "雾银灰"

    print(
        "event-driven language switch and dynamic dialog translation OK; "
        "global theme switch OK"
    )

    dialog.close()
    window._close_in_progress = True
    window.preview_timer.stop()
    window._page_thumbnail_debounce_timer.stop()
    window._page_thumbnail_render_timer.stop()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
