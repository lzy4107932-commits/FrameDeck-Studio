from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from core.ppt_generator import PAGE_SIZES
from core.image_transform_crop import (
    CROP_MIN_SIZE,
    crop_is_modified,
    crop_rect_to_pixels,
    default_crop,
    normalize_crop,
    translate_crop,
)
from core.image_cache_manager import image_cache
from core.heif_support import (
    is_supported_image_path,
)
from core.drag_protocol import rows_from_mime
from core.group_layout import resolve_title_vertical_geometry


class PreviewCanvas(QWidget):
    swapRequested = Signal(int, int)
    selectionChanged = Signal(int)
    multiSelectionChanged = Signal(list, int)
    zoomChanged = Signal(int, float)
    pageTitleEditRequested = Signal(int)

    # UI-05-37A：放大图片后的抓手拖动。
    panStarted = Signal(int)
    panChanged = Signal(int, float, float)
    panFinished = Signal(int, float, float)

    cropStarted = Signal(int)
    cropChanged = Signal(int, dict)
    cropFinished = Signal(int, bool)

    # UI-05-37B：扩展图片变换范围。
    IMAGE_ZOOM_MIN = 0.10
    IMAGE_ZOOM_MAX = 10.00
    PAN_ABSOLUTE_LIMIT = 50.0

    # offset 使用归一化值。接近中心时自动吸附到 0，
    # 避免鼠标很难精确停在中心。
    PAN_CENTER_SNAP = 0.035

    def __init__(self, parent=None):
        super().__init__(parent)
        # UI-05-45A：中央画布不再用大号最小尺寸挤压导航区。
        # 在小屏幕 / 高缩放比例下允许布局继续收缩，实际页面仍按
        # 当前可用空间自适应绘制。
        self.setMinimumSize(QSize(360, 240))
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # UI-05-33A：
        # QWidget 默认可能不接收键盘焦点。中央画布必须成为真实
        # 焦点区域，Delete / Ctrl+D 才不会被导航栏快捷键抢占。
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self._images: list[str] = []
        self._image_transforms: dict[str, dict] = {}

        # UI-05-28A：
        # 记录显式分页起点，使未填满页面也可以独立复制。
        self._manual_page_breaks: list[int] = []

        # UI-05-42B FIX02：
        # 空白页使用“逻辑页面位置”保存，不再限制只能追加在图片页末尾。
        # 例如 [1, 3] 表示第2页和第4页为空白页。
        self._blank_page_positions: list[int] = []

        self._page_index = 0
        self._settings: dict = {}

        # UI-05-42B FIX09：
        # 页面Logo独立小缓存，避免每次paintEvent重复从磁盘读取。
        self._logo_cache_path = ""
        self._logo_cache_pixmap = QPixmap()

        # UI-05-36A：
        # 中央画布不再固定压缩到 3200px。
        # 根据画布尺寸、画布缩放、图片缩放和裁切范围动态请求分辨率。
        self._image_cache = image_cache()
        self._preview_cache_min_long_edge = 4096
        self._preview_cache_max_long_edge = 8192
        self._render_quality_override = 0

        # UI-05-39B：
        # 顶部页面导航的离屏画布只读取后台生成的缩略图缓存，
        # 缓存尚未完成时显示空槽，不在主线程解码原图。
        self._navigation_thumbnail_mode = False
        self._navigation_thumbnail_width = 360
        self._navigation_thumbnail_height = 240

        self._zoom = 1.0
        self._theme = "深空暗色"
        self._palette = {}

        self._slot_rects: list[tuple[int, QRectF]] = []
        self._title_edit_rect = QRectF()

        # UI-05-23A：
        # 外部文件拖入使用独立槽位表。
        # dragMoveEvent 只更新预览高亮，真正插入只在 dropEvent 执行。
        self._external_drop_slot_rects: list[tuple[int, QRectF]] = []
        self._external_drop_target_index = -1
        self._external_drop_target_rect = QRectF()

        self._selected_index = -1
        self._selected_indices: set[int] = set()
        self._selection_anchor = -1

        self._pressed_index = -1
        self._drag_target_index = -1
        self._press_pos = QPoint()

        # UI-05-37A：图片放大后的抓手拖动状态。
        self._pan_candidate = False
        self._pan_active = False
        self._pan_index = -1
        self._pan_start = QPoint()
        self._pan_start_offset_x = 0.0
        self._pan_start_offset_y = 0.0

        # UI-05-30 Stage 02：中央画布裁切状态。
        self._crop_mode = False
        self._crop_index = -1
        self._crop_original = default_crop()
        self._crop_working = default_crop()

        self._crop_source_rect = QRectF()
        self._crop_frame_rect = QRectF()
        self._crop_handle_rects: dict[str, QRectF] = {}

        self._crop_drag_handle = ""
        self._crop_drag_start = QPoint()
        self._crop_drag_start_data = default_crop()
        self._crop_confirm_rect = QRectF()
        self._crop_cancel_rect = QRectF()

    def set_images(self, images: list[str]):
        self._images = images
        self._manual_page_breaks = sorted(
            {
                int(value)
                for value in self._manual_page_breaks
                if 0 < int(value) < len(images)
            }
        )
        self._blank_page_positions = (
            self._normalized_blank_page_positions()
        )
        self._page_index = min(
            self._page_index,
            max(0, self.page_count() - 1),
        )

        self._selected_indices = {
            index
            for index in self._selected_indices
            if 0 <= index < len(images)
        }

        if (
            self._crop_mode
            and not (0 <= self._crop_index < len(images))
        ):
            self._clear_crop_state()

        if self._selected_index not in self._selected_indices:
            self._selected_index = (
                min(self._selected_indices)
                if self._selected_indices
                else -1
            )

        if not (0 <= self._selection_anchor < len(images)):
            self._selection_anchor = self._selected_index

        self.rearm_external_drop()
        self.update()

    def set_image_transforms(self, transforms: dict[str, dict]):
        """
        接收 MainWindow 保存的图片精修参数。

        UI-05-27A 在加入多选接口时，替换 set_images 到
        set_page_index 之间的代码块，误删了原有的这个方法，
        导致软件启动阶段调用失败。
        """
        self._image_transforms = {
            path: dict(value)
            for path, value in (transforms or {}).items()
        }
        self.update()

    # =====================================================
    # UI-05-30 Stage 02 - Central Canvas Crop API
    # =====================================================

    def is_crop_mode(self) -> bool:
        return bool(self._crop_mode)

    def crop_index(self) -> int:
        return int(self._crop_index)

    def _clear_crop_state(self):
        self._crop_mode = False
        self._crop_index = -1
        self._crop_original = default_crop()
        self._crop_working = default_crop()
        self._crop_source_rect = QRectF()
        self._crop_frame_rect = QRectF()
        self._crop_handle_rects = {}
        self._crop_drag_handle = ""
        self._crop_confirm_rect = QRectF()
        self._crop_cancel_rect = QRectF()
        self.unsetCursor()
        self.update()

    def begin_crop_mode(self, index: int | None = None) -> bool:
        """
        进入单张图片裁切模式。
        """
        if index is None:
            index = self._selected_index

        index = int(index)

        if not (0 <= index < len(self._images)):
            return False

        if len(self._selected_indices) != 1:
            return False

        path = self._images[index]
        pixmap = self._pixmap(path)

        if pixmap.isNull():
            return False

        if self._crop_mode:
            if self._crop_index == index:
                return True
            self.cancel_crop_mode()

        transform = self._image_transforms.get(path, {})
        crop = normalize_crop(transform.get("crop"))

        self._crop_mode = True
        self._crop_index = index
        self._crop_original = dict(crop)
        self._crop_working = dict(crop)
        self._crop_drag_handle = ""

        self.cropStarted.emit(index)
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.update()
        return True

    def confirm_crop_mode(self) -> bool:
        if not self._crop_mode:
            return False

        index = self._crop_index
        crop = normalize_crop(self._crop_working)

        self.cropChanged.emit(index, dict(crop))
        self.cropFinished.emit(index, True)
        self._clear_crop_state()
        return True

    def cancel_crop_mode(self) -> bool:
        if not self._crop_mode:
            return False

        index = self._crop_index
        original = normalize_crop(self._crop_original)

        self.cropChanged.emit(index, dict(original))
        self.cropFinished.emit(index, False)
        self._clear_crop_state()
        return True

    def reset_crop_in_editor(self) -> bool:
        if not self._crop_mode:
            return False

        self._crop_working = default_crop()
        self.cropChanged.emit(
            self._crop_index,
            dict(self._crop_working),
        )
        self.update()
        return True

    def _crop_frame_from_data(
        self,
        crop,
        source_rect: QRectF,
    ) -> QRectF:
        normalized = normalize_crop(crop)

        return QRectF(
            source_rect.left()
            + normalized["x"] * source_rect.width(),
            source_rect.top()
            + normalized["y"] * source_rect.height(),
            normalized["width"] * source_rect.width(),
            normalized["height"] * source_rect.height(),
        )

    def _update_crop_handles(self):
        self._crop_handle_rects = {}

        if self._crop_frame_rect.isNull():
            return

        rect = self._crop_frame_rect
        size = 12.0
        half = size / 2.0

        points = {
            "nw": (rect.left(), rect.top()),
            "n": (rect.center().x(), rect.top()),
            "ne": (rect.right(), rect.top()),
            "e": (rect.right(), rect.center().y()),
            "se": (rect.right(), rect.bottom()),
            "s": (rect.center().x(), rect.bottom()),
            "sw": (rect.left(), rect.bottom()),
            "w": (rect.left(), rect.center().y()),
        }

        for name, (x, y) in points.items():
            self._crop_handle_rects[name] = QRectF(
                x - half,
                y - half,
                size,
                size,
            )

    def _crop_handle_at(self, point: QPoint) -> str:
        for name, rect in self._crop_handle_rects.items():
            if rect.adjusted(-3, -3, 3, 3).contains(point):
                return name

        if self._crop_frame_rect.contains(point):
            return "move"

        return ""

    def _crop_cursor(self, handle: str):
        mapping = {
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "n": Qt.CursorShape.SizeVerCursor,
            "s": Qt.CursorShape.SizeVerCursor,
            "e": Qt.CursorShape.SizeHorCursor,
            "w": Qt.CursorShape.SizeHorCursor,
            "move": Qt.CursorShape.SizeAllCursor,
        }

        return mapping.get(
            handle,
            Qt.CursorShape.ArrowCursor,
        )

    def _set_crop_working(self, crop, emit=True):
        self._crop_working = normalize_crop(crop)

        if emit and self._crop_mode:
            self.cropChanged.emit(
                self._crop_index,
                dict(self._crop_working),
            )

        self.update()

    def _resize_crop_from_drag(
        self,
        handle: str,
        dx: float,
        dy: float,
    ):
        crop = normalize_crop(
            self._crop_drag_start_data
        )

        left = crop["x"]
        top = crop["y"]
        right = left + crop["width"]
        bottom = top + crop["height"]

        if "w" in handle:
            left += dx
        if "e" in handle:
            right += dx
        if "n" in handle:
            top += dy
        if "s" in handle:
            bottom += dy

        minimum = CROP_MIN_SIZE

        left = max(
            0.0,
            min(left, right - minimum),
        )
        top = max(
            0.0,
            min(top, bottom - minimum),
        )
        right = min(
            1.0,
            max(right, left + minimum),
        )
        bottom = min(
            1.0,
            max(bottom, top + minimum),
        )

        crop.update(
            {
                "enabled": True,
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top,
                "aspect_mode": "free",
                "aspect_ratio": None,
            }
        )
        self._set_crop_working(crop)

    def _scale_crop_around_center(self, factor: float):
        crop = normalize_crop(self._crop_working)

        center_x = crop["x"] + crop["width"] / 2.0
        center_y = crop["y"] + crop["height"] / 2.0

        width = max(
            CROP_MIN_SIZE,
            min(1.0, crop["width"] * factor),
        )
        height = max(
            CROP_MIN_SIZE,
            min(1.0, crop["height"] * factor),
        )

        x = center_x - width / 2.0
        y = center_y - height / 2.0

        x = max(0.0, min(x, 1.0 - width))
        y = max(0.0, min(y, 1.0 - height))

        crop.update(
            {
                "enabled": True,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "aspect_mode": "free",
                "aspect_ratio": None,
            }
        )
        self._set_crop_working(crop)

    def _paint_crop_overlay(
        self,
        painter: QPainter,
        source_rect: QRectF,
        accent_color: QColor,
    ):
        self._crop_source_rect = QRectF(source_rect)
        self._crop_frame_rect = (
            self._crop_frame_from_data(
                self._crop_working,
                source_rect,
            )
        )
        self._update_crop_handles()

        frame = self._crop_frame_rect

        painter.save()

        shade = QColor(0, 0, 0, 138)
        outside_rects = [
            QRectF(
                source_rect.left(),
                source_rect.top(),
                source_rect.width(),
                max(0.0, frame.top() - source_rect.top()),
            ),
            QRectF(
                source_rect.left(),
                frame.bottom(),
                source_rect.width(),
                max(0.0, source_rect.bottom() - frame.bottom()),
            ),
            QRectF(
                source_rect.left(),
                frame.top(),
                max(0.0, frame.left() - source_rect.left()),
                frame.height(),
            ),
            QRectF(
                frame.right(),
                frame.top(),
                max(0.0, source_rect.right() - frame.right()),
                frame.height(),
            ),
        ]

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shade)

        for outside in outside_rects:
            if outside.width() > 0 and outside.height() > 0:
                painter.drawRect(outside)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#FFFFFF"), 3))
        painter.drawRect(frame)

        painter.setPen(
            QPen(
                QColor(255, 255, 255, 150),
                1,
                Qt.PenStyle.DashLine,
            )
        )

        for fraction in (1 / 3, 2 / 3):
            x = frame.left() + frame.width() * fraction
            y = frame.top() + frame.height() * fraction

            painter.drawLine(
                int(x),
                int(frame.top()),
                int(x),
                int(frame.bottom()),
            )
            painter.drawLine(
                int(frame.left()),
                int(y),
                int(frame.right()),
                int(y),
            )

        painter.setPen(QPen(accent_color, 2))
        painter.setBrush(QColor("#FFFFFF"))

        for rect in self._crop_handle_rects.values():
            painter.drawRoundedRect(rect, 2, 2)

        # UI-05-37A：紧凑确认/取消按钮，不再遮挡顶部裁切线。
        button_size = 30.0
        button_gap = 7.0
        group_width = button_size * 2 + button_gap

        available_above = frame.top() - source_rect.top()

        if available_above >= button_size + 12:
            buttons_top = frame.top() - button_size - 8
        else:
            buttons_top = source_rect.top() + 8

        buttons_left = max(
            source_rect.left() + 8,
            source_rect.right() - group_width - 8,
        )

        self._crop_confirm_rect = QRectF(
            buttons_left,
            buttons_top,
            button_size,
            button_size,
        )
        self._crop_cancel_rect = QRectF(
            buttons_left + button_size + button_gap,
            buttons_top,
            button_size,
            button_size,
        )

        painter.setPen(QPen(QColor(255, 255, 255, 215), 1))
        painter.setBrush(accent_color)
        painter.drawRoundedRect(self._crop_confirm_rect, 8, 8)

        painter.setBrush(QColor(15, 23, 42, 225))
        painter.drawRoundedRect(self._crop_cancel_rect, 8, 8)

        painter.setPen(
            QPen(
                QColor("#FFFFFF"),
                2.4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )

        confirm = self._crop_confirm_rect
        painter.drawLine(
            int(confirm.left() + 8),
            int(confirm.center().y()),
            int(confirm.left() + 13),
            int(confirm.bottom() - 8),
        )
        painter.drawLine(
            int(confirm.left() + 13),
            int(confirm.bottom() - 8),
            int(confirm.right() - 7),
            int(confirm.top() + 8),
        )

        cancel = self._crop_cancel_rect
        painter.drawLine(
            int(cancel.left() + 9),
            int(cancel.top() + 9),
            int(cancel.right() - 9),
            int(cancel.bottom() - 9),
        )
        painter.drawLine(
            int(cancel.right() - 9),
            int(cancel.top() + 9),
            int(cancel.left() + 9),
            int(cancel.bottom() - 9),
        )

        painter.restore()

    def selected_indices(self):
        return sorted(self._selected_indices)

    def set_selected_indices(
        self,
        indices,
        primary_index: int = -1,
        reveal: bool = False,
    ):
        valid = {
            int(index)
            for index in list(indices or [])
            if 0 <= int(index) < len(self._images)
        }

        if primary_index not in valid:
            primary_index = min(valid) if valid else -1

        if (
            self._crop_mode
            and (
                len(valid) != 1
                or self._crop_index not in valid
            )
        ):
            self.cancel_crop_mode()

        self._selected_indices = valid
        self._selected_index = int(primary_index)

        if self._selected_index >= 0:
            self._selection_anchor = self._selected_index

        if reveal and self._selected_index >= 0:
            self._page_index = self.page_index_for_image(
                self._selected_index
            )

        self.update()

    def set_selected_index(
        self,
        index: int,
        reveal: bool = False,
    ):
        if 0 <= index < len(self._images):
            self.set_selected_indices(
                [index],
                index,
                reveal,
            )
        else:
            self.set_selected_indices(
                [],
                -1,
                False,
            )

    def _emit_selection(self):
        indices = sorted(self._selected_indices)
        self.multiSelectionChanged.emit(
            indices,
            self._selected_index,
        )
        self.selectionChanged.emit(
            self._selected_index,
        )


    # =====================================================
    # UI-05-42B FIX02 - Movable Blank Page API
    # =====================================================

    def _base_page_count(self) -> int:
        return max(
            1,
            len(
                self.page_ranges()
            ),
        )

    def _normalized_blank_page_positions(
        self,
        positions=None,
    ) -> list[int]:
        base_count = self._base_page_count()

        raw = sorted(
            {
                int(value)
                for value in (
                    self._blank_page_positions
                    if positions is None
                    else list(
                        positions or []
                    )
                )
                if int(value) >= 0
            }
        )

        normalized = []

        for value in raw:
            maximum = (
                base_count
                + len(normalized)
            )
            value = max(
                0,
                min(
                    int(value),
                    maximum,
                ),
            )

            # 同一逻辑索引不能表示两张空白页；
            # 连续空白页会自然表现为相邻索引，例如 [1, 2]。
            if value in normalized:
                continue

            normalized.append(
                value
            )

        normalized.sort()
        return normalized

    def blank_page_positions(self):
        self._blank_page_positions = (
            self._normalized_blank_page_positions()
        )
        return list(
            self._blank_page_positions
        )

    def set_blank_page_positions(
        self,
        positions,
    ):
        self._blank_page_positions = (
            self._normalized_blank_page_positions(
                positions
            )
        )
        self._page_index = max(
            0,
            min(
                int(
                    self._page_index
                ),
                max(
                    0,
                    self.page_count()
                    - 1,
                ),
            ),
        )
        self.update()

    def is_blank_page(
        self,
        logical_page_index,
    ) -> bool:
        return int(
            logical_page_index
        ) in set(
            self.blank_page_positions()
        )

    def image_page_index_for_logical(
        self,
        logical_page_index,
    ):
        logical_page_index = int(
            logical_page_index
        )

        if self.is_blank_page(
            logical_page_index
        ):
            return None

        blank_before = sum(
            1
            for value in (
                self.blank_page_positions()
            )
            if value < logical_page_index
        )
        image_page_index = (
            logical_page_index
            - blank_before
        )

        if (
            0
            <= image_page_index
            < self._base_page_count()
        ):
            return image_page_index

        return None

    def logical_page_index_for_image_page(
        self,
        image_page_index,
    ) -> int:
        image_page_index = max(
            0,
            min(
                int(image_page_index),
                self._base_page_count()
                - 1,
            ),
        )

        logical = image_page_index

        for blank_index in (
            self.blank_page_positions()
        ):
            if blank_index <= logical:
                logical += 1
            else:
                break

        return logical

    def add_blank_page_after(
        self,
        logical_page_index=None,
    ) -> int:
        total_before = self.page_count()

        if logical_page_index is None:
            logical_page_index = (
                self._page_index
            )

        logical_page_index = max(
            -1,
            min(
                int(logical_page_index),
                total_before - 1,
            ),
        )
        insert_at = (
            logical_page_index
            + 1
        )

        positions = []

        for value in (
            self.blank_page_positions()
        ):
            positions.append(
                value + 1
                if value >= insert_at
                else value
            )

        positions.append(
            insert_at
        )
        self.set_blank_page_positions(
            positions
        )
        self._page_index = insert_at
        self._selected_index = -1
        self._selected_indices = set()
        self.update()
        return insert_at

    def add_empty_page(self):
        self.add_blank_page_after(
            self._page_index
        )
        return True

    def add_blank_page(self):
        return self.add_empty_page()

    def remove_blank_page(
        self,
        logical_page_index,
    ) -> bool:
        logical_page_index = int(
            logical_page_index
        )
        positions = (
            self.blank_page_positions()
        )

        if (
            logical_page_index
            not in positions
        ):
            return False

        updated = []

        for value in positions:
            if value == logical_page_index:
                continue

            updated.append(
                value - 1
                if value > logical_page_index
                else value
            )

        self.set_blank_page_positions(
            updated
        )
        self._page_index = max(
            0,
            min(
                self._page_index,
                self.page_count() - 1,
            ),
        )
        self.update()
        return True

    def set_page_breaks(self, breaks):
        """
        设置显式分页起点。

        breaks 中的值是“可见图片索引”，例如：
            [16, 19]
        表示第 3 页从索引 16 开始，第 4 页从索引 19 开始。
        """
        self._manual_page_breaks = sorted(
            {
                int(value)
                for value in list(breaks or [])
                if 0 < int(value) < len(self._images)
            }
        )
        self._blank_page_positions = (
            self._normalized_blank_page_positions()
        )
        self._page_index = max(
            0,
            min(
                self._page_index,
                max(0, self.page_count() - 1),
            ),
        )
        self.update()

    def page_ranges(self):
        """
        返回图片页面范围列表：
            [(start, end), ...]

        每个显式分页段内部仍按当前行列容量继续自动分页。
        """
        rows = max(
            1,
            int(self._settings.get("rows", 2)),
        )
        cols = max(
            1,
            int(self._settings.get("cols", 6)),
        )
        capacity = max(1, rows * cols)
        image_count = len(self._images)

        if image_count <= 0:
            return [(0, 0)]

        boundaries = [0]
        boundaries.extend(
            value
            for value in self._manual_page_breaks
            if 0 < value < image_count
        )
        boundaries.append(image_count)

        ranges = []

        for segment_index in range(len(boundaries) - 1):
            start = boundaries[segment_index]
            end = boundaries[segment_index + 1]

            cursor = start

            while cursor < end:
                page_end = min(cursor + capacity, end)
                ranges.append((cursor, page_end))
                cursor = page_end

        return ranges or [(0, 0)]

    def page_range(self, page_index=None):
        ranges = self.page_ranges()

        if page_index is None:
            page_index = self._page_index

        logical_page_index = int(
            page_index
        )
        image_page_index = (
            self.image_page_index_for_logical(
                logical_page_index
            )
        )

        if (
            image_page_index is not None
            and 0
            <= image_page_index
            < len(ranges)
        ):
            return ranges[
                image_page_index
            ]

        # 任意位置的空白页返回空图片范围。
        end = len(
            self._images
        )
        return end, end

    def page_index_for_image(
        self,
        image_index,
    ):
        image_index = int(
            image_index
        )

        for image_page_index, (
            start,
            end,
        ) in enumerate(
            self.page_ranges()
        ):
            if (
                start
                <= image_index
                < end
            ):
                return (
                    self.logical_page_index_for_image_page(
                        image_page_index
                    )
                )

        return (
            self.logical_page_index_for_image_page(
                max(
                    0,
                    len(
                        self.page_ranges()
                    )
                    - 1,
                )
            )
        )

    def set_page_index(self, page_index: int):
        new_page = max(
            0,
            min(
                page_index,
                max(0, self.page_count() - 1),
            ),
        )

        if self._crop_mode:
            crop_page = self.page_index_for_image(
                self._crop_index
            )

            if new_page != crop_page:
                self.cancel_crop_mode()

        self._page_index = new_page
        self.update()

    def set_settings(self, settings: dict):
        self._settings = settings.copy()
        self.update()

    def set_language(self, language: str):
        language = "en_US" if str(language).lower().startswith("en") else "zh_CN"
        if self._settings.get("language") == language:
            return
        self._settings["language"] = language
        self.update()

    def set_zoom(self, zoom: float):
        self._zoom = max(0.5, min(1.6, zoom))
        self.update()

    def set_theme(self, theme_name: str, palette: dict | None = None):
        self._theme = theme_name
        self._palette = palette or {}
        self.update()

    def page_count(self):
        return max(
            1,
            self._base_page_count()
            + len(
                self.blank_page_positions()
            ),
        )

    def current_page(self):
        return self._page_index

    def _adaptive_preview_long_edge(self, path: str) -> int:
        """
        估算当前图片真正需要的预览分辨率。

        影响因素：
        - 当前窗口像素尺寸
        - Windows 高分屏倍率
        - 画布缩放
        - 单张图片缩放
        - 裁切后只使用原图局部
        """
        if self._render_quality_override > 0:
            return int(
                self._render_quality_override
            )

        device_scale = max(
            1.0,
            float(self.devicePixelRatioF()),
        )
        viewport_edge = max(
            1,
            int(
                max(
                    self.width(),
                    self.height(),
                )
                * device_scale
                * max(1.0, self._zoom)
            ),
        )

        transform = self._image_transforms.get(
            path,
            {},
        )
        image_zoom = max(
            1.0,
            float(
                transform.get(
                    "zoom",
                    1.0,
                )
            ),
        )

        crop = normalize_crop(
            transform.get("crop")
        )
        crop_factor = 1.0

        if crop_is_modified(crop):
            smallest_side = max(
                0.20,
                min(
                    float(crop["width"]),
                    float(crop["height"]),
                ),
            )
            crop_factor = min(
                4.0,
                1.0 / smallest_side,
            )

        requested = round(
            viewport_edge
            * 2.25
            * image_zoom
            * crop_factor
        )

        return max(
            self._preview_cache_min_long_edge,
            min(
                self._preview_cache_max_long_edge,
                requested,
            ),
        )

    def _pixmap(self, path: str):
        if self._navigation_thumbnail_mode:
            return (
                self._image_cache.cached_thumbnail_pixmap(
                    path,
                    self._navigation_thumbnail_width,
                    self._navigation_thumbnail_height,
                )
            )

        return self._image_cache.preview_pixmap(
            path,
            max_long_edge=(
                self._adaptive_preview_long_edge(
                    path
                )
            ),
        )

    def set_navigation_thumbnail_mode(
        self,
        enabled: bool,
        width: int = 360,
        height: int = 240,
    ):
        self._navigation_thumbnail_mode = bool(
            enabled
        )
        self._navigation_thumbnail_width = max(
            64,
            int(width),
        )
        self._navigation_thumbnail_height = max(
            48,
            int(height),
        )
        self.update()

    def set_render_quality_override(
        self,
        max_long_edge: int | None,
    ):
        """
        导出PDF/PNG时临时请求更高质量的原图预览。
        传入 None 或 0 恢复自动模式。
        """
        value = int(max_long_edge or 0)
        self._render_quality_override = max(
            0,
            value,
        )
        self.update()

    def render_quality_override(self) -> int:
        return int(
            self._render_quality_override
        )

    def _page_logo_pixmap(
        self,
        path,
    ):
        path = str(
            path or ""
        ).strip()

        if path != self._logo_cache_path:
            self._logo_cache_path = path

            if (
                path
                and Path(path).is_file()
            ):
                self._logo_cache_pixmap = QPixmap(
                    path
                )
            else:
                self._logo_cache_pixmap = QPixmap()

        return self._logo_cache_pixmap

    def clear_memory_cache(self):
        self._image_cache.clear_memory()
        self.update()

    def _slot_rect_for_index(self, index: int) -> QRectF:
        for absolute_index, rect in self._slot_rects:
            if absolute_index == index:
                return QRectF(rect)
        return QRectF()

    def _image_transform_for_index(
        self,
        index: int,
    ) -> dict:
        if not (0 <= index < len(self._images)):
            return {}

        path = self._images[index]
        return dict(
            self._image_transforms.get(
                path,
                {},
            )
        )

    def _image_zoom_for_index(self, index: int) -> float:
        return float(
            self._image_transform_for_index(
                index
            ).get(
                "zoom",
                1.0,
            )
        )

    def _image_can_pan(
        self,
        index: int,
    ) -> bool:
        """
        图片满足任一条件时启用抓手：
        - 缩放不等于 1×，包括缩小状态；
        - 仍保留历史水平/垂直位移。

        这样图片缩小后可以拖动；恢复 1× 但尚未居中时，
        也能继续拖回中心。
        """
        transform = (
            self._image_transform_for_index(
                index
            )
        )
        zoom = float(
            transform.get(
                "zoom",
                1.0,
            )
        )
        offset_x = float(
            transform.get(
                "offset_x",
                0.0,
            )
        )
        offset_y = float(
            transform.get(
                "offset_y",
                0.0,
            )
        )

        return bool(
            abs(zoom - 1.0) > 0.001
            or abs(offset_x) > 0.0005
            or abs(offset_y) > 0.0005
        )

    def pan_limits_for_index(
        self,
        index: int,
        *,
        zoom_override: float | None = None,
    ) -> tuple[float, float]:
        """
        根据图片真实溢出范围动态计算水平/垂直移动上限。

        offset=1.0 表示移动图片框半宽/半高，即界面中的 100%。
        旧版固定 ±100%，在 3× 放大或极端纵横比时不足以把
        头部、脚部或图片边缘移动回框内。
        """
        if not (0 <= index < len(self._images)):
            return 1.0, 1.0

        frame = self._slot_rect_for_index(index)

        if frame.width() <= 0 or frame.height() <= 0:
            return 1.0, 1.0

        path = self._images[index]
        pixmap = self._pixmap(path)

        if pixmap.isNull():
            return 1.0, 1.0

        transform = self._image_transforms.get(
            path,
            {},
        )
        crop = normalize_crop(
            transform.get("crop")
        )

        source_w = float(pixmap.width())
        source_h = float(pixmap.height())

        if crop_is_modified(crop):
            _x, _y, crop_w, crop_h = (
                crop_rect_to_pixels(
                    crop,
                    pixmap.width(),
                    pixmap.height(),
                )
            )
            source_w = max(
                1.0,
                float(crop_w),
            )
            source_h = max(
                1.0,
                float(crop_h),
            )

        rotation = int(
            transform.get("rotation", 0)
        ) % 360

        if rotation in {90, 270}:
            source_w, source_h = (
                source_h,
                source_w,
            )

        zoom = (
            float(zoom_override)
            if zoom_override is not None
            else float(
                transform.get("zoom", 1.0)
            )
        )
        zoom = max(
            self.IMAGE_ZOOM_MIN,
            min(
                self.IMAGE_ZOOM_MAX,
                zoom,
            ),
        )

        if (
            self._settings.get("image_mode")
            == "裁剪填充"
        ):
            base_scale = max(
                frame.width() / source_w,
                frame.height() / source_h,
            )
        else:
            base_scale = min(
                frame.width() / source_w,
                frame.height() / source_h,
            )

        target_w = (
            source_w * base_scale * zoom
        )
        target_h = (
            source_h * base_scale * zoom
        )

        # 渲染位移：
        # shift = offset * frame_size * 0.5
        # 将图像边缘对齐框边所需：
        # offset = abs(target/frame - 1)
        limit_x = abs(
            target_w / frame.width()
            - 1.0
        )
        limit_y = abs(
            target_h / frame.height()
            - 1.0
        )

        # 保持旧版至少 ±100% 的自由范围，同时允许高倍放大
        # 和极端纵横比图像达到完整边缘。
        limit_x = max(
            1.0,
            min(
                self.PAN_ABSOLUTE_LIMIT,
                limit_x,
            ),
        )
        limit_y = max(
            1.0,
            min(
                self.PAN_ABSOLUTE_LIMIT,
                limit_y,
            ),
        )

        return (
            round(limit_x, 4),
            round(limit_y, 4),
        )

    def _reset_pan_state(self):
        self._pan_candidate = False
        self._pan_active = False
        self._pan_index = -1
        self._pan_start = QPoint()
        self._pan_start_offset_x = 0.0
        self._pan_start_offset_y = 0.0

    def _index_at(self, pos: QPoint) -> int:
        for absolute_index, rect in self._slot_rects:
            if rect.contains(pos):
                return absolute_index
        return -1

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        # 点击中央画布后，复制和删除快捷键立即切换到图片操作。
        self.setFocus(
            Qt.FocusReason.MouseFocusReason
        )

        if self._crop_mode:
            point = event.position().toPoint()

            if self._crop_confirm_rect.contains(point):
                self.confirm_crop_mode()
                event.accept()
                return

            if self._crop_cancel_rect.contains(point):
                self.cancel_crop_mode()
                event.accept()
                return

            handle = self._crop_handle_at(point)

            if not handle:
                event.ignore()
                return

            self._crop_drag_handle = handle
            self._crop_drag_start = (
                event.position().toPoint()
            )
            self._crop_drag_start_data = dict(
                self._crop_working
            )
            self.setCursor(
                self._crop_cursor(handle)
            )
            event.accept()
            return

        index = self._index_at(
            event.position().toPoint()
        )
        modifiers = event.modifiers()
        ctrl = bool(
            modifiers
            & Qt.KeyboardModifier.ControlModifier
        )
        shift = bool(
            modifiers
            & Qt.KeyboardModifier.ShiftModifier
        )

        self._drag_target_index = -1
        self._press_pos = event.position().toPoint()

        if index < 0:
            self._pressed_index = -1

            if not ctrl and not shift:
                self._selected_indices.clear()
                self._selected_index = -1
                self._selection_anchor = -1
                self._emit_selection()
                self.update()

            return

        if shift:
            anchor = self._selection_anchor

            if not (0 <= anchor < len(self._images)):
                anchor = index

            start = min(anchor, index)
            end = max(anchor, index)
            range_selection = set(range(start, end + 1))

            if ctrl:
                self._selected_indices.update(
                    range_selection
                )
            else:
                self._selected_indices = range_selection

            self._selected_index = index

        elif ctrl:
            if index in self._selected_indices:
                self._selected_indices.remove(index)

                if self._selected_index == index:
                    self._selected_index = (
                        min(self._selected_indices)
                        if self._selected_indices
                        else -1
                    )
            else:
                self._selected_indices.add(index)
                self._selected_index = index
                self._selection_anchor = index

        else:
            self._selected_indices = {index}
            self._selected_index = index
            self._selection_anchor = index

        can_pan = (
            not ctrl
            and not shift
            and index in self._selected_indices
            and self._image_can_pan(index)
        )

        if can_pan:
            path = self._images[index]
            transform = self._image_transforms.get(path, {})
            self._pan_candidate = True
            self._pan_active = False
            self._pan_index = index
            self._pan_start = QPoint(self._press_pos)
            self._pan_start_offset_x = float(
                transform.get("offset_x", 0.0)
            )
            self._pan_start_offset_y = float(
                transform.get("offset_y", 0.0)
            )
            self._pressed_index = -1
        else:
            self._reset_pan_state()
            self._pressed_index = (
                index if index in self._selected_indices else -1
            )

        self._emit_selection()
        self.setCursor(
            Qt.CursorShape.ClosedHandCursor
            if can_pan
            else Qt.CursorShape.ArrowCursor
        )
        self.update()


    def mouseMoveEvent(self, event: QMouseEvent):
        if self._crop_mode:
            point = event.position().toPoint()

            if (
                self._crop_confirm_rect.contains(point)
                or self._crop_cancel_rect.contains(point)
            ):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                event.accept()
                return

            if self._crop_drag_handle:
                source = self._crop_source_rect

                if (
                    source.width() <= 0
                    or source.height() <= 0
                ):
                    return

                delta = point - self._crop_drag_start
                dx = delta.x() / source.width()
                dy = delta.y() / source.height()

                if self._crop_drag_handle == "move":
                    moved = translate_crop(
                        self._crop_drag_start_data,
                        dx,
                        dy,
                    )
                    self._set_crop_working(moved)
                else:
                    self._resize_crop_from_drag(
                        self._crop_drag_handle,
                        dx,
                        dy,
                    )

                event.accept()
                return

            handle = self._crop_handle_at(point)
            self.setCursor(
                self._crop_cursor(handle)
            )
            event.accept()
            return

        if self._pan_candidate:
            point = event.position().toPoint()
            delta = point - self._pan_start

            if (
                not self._pan_active
                and delta.manhattanLength() >= 3
            ):
                self._pan_active = True
                self.panStarted.emit(self._pan_index)

            if self._pan_active:
                slot_rect = self._slot_rect_for_index(self._pan_index)

                if slot_rect.width() > 0 and slot_rect.height() > 0:
                    limit_x, limit_y = (
                        self.pan_limits_for_index(
                            self._pan_index
                        )
                    )
                    offset_x = max(
                        -limit_x,
                        min(
                            limit_x,
                            self._pan_start_offset_x
                            + 2.0 * delta.x() / slot_rect.width(),
                        ),
                    )
                    offset_y = max(
                        -limit_y,
                        min(
                            limit_y,
                            self._pan_start_offset_y
                            + 2.0 * delta.y() / slot_rect.height(),
                        ),
                    )

                    # 靠近中心时自动吸附，确保能够真正回到 0 / 0。
                    if abs(offset_x) <= self.PAN_CENTER_SNAP:
                        offset_x = 0.0

                    if abs(offset_y) <= self.PAN_CENTER_SNAP:
                        offset_y = 0.0

                    self.panChanged.emit(
                        self._pan_index,
                        float(offset_x),
                        float(offset_y),
                    )

                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

        if self._pressed_index < 0:
            index = self._index_at(event.position().toPoint())
            pannable = (
                index >= 0
                and self._image_can_pan(index)
            )
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if pannable
                else Qt.CursorShape.ArrowCursor
            )
            return

        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance >= 8:
            self._drag_target_index = self._index_at(event.position().toPoint())
            self.update()

    def mouseDoubleClickEvent(
        self,
        event: QMouseEvent,
    ):
        """
        双击已变换图片：立即水平、垂直居中。

        不改变图片缩放，只把 offset_x / offset_y 恢复为 0。
        """
        if (
            event.button()
            != Qt.MouseButton.LeftButton
            or self._crop_mode
        ):
            return super().mouseDoubleClickEvent(
                event
            )

        point = event.position().toPoint()
        if self._title_edit_rect.contains(point):
            self._reset_pan_state()
            self.pageTitleEditRequested.emit(self._page_index)
            event.accept()
            return

        index = self._index_at(point)

        if (
            index < 0
            or not self._image_can_pan(index)
        ):
            return super().mouseDoubleClickEvent(
                event
            )

        self._reset_pan_state()
        self.panStarted.emit(index)
        self.panChanged.emit(
            index,
            0.0,
            0.0,
        )
        self.panFinished.emit(
            index,
            0.0,
            0.0,
        )
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
        )
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._crop_mode:
            if event.button() != Qt.MouseButton.LeftButton:
                return super().mouseReleaseEvent(event)

            self._crop_drag_handle = ""
            handle = self._crop_handle_at(
                event.position().toPoint()
            )
            self.setCursor(
                self._crop_cursor(handle)
            )
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)

        if self._pan_candidate:
            pan_index = self._pan_index
            pan_active = self._pan_active
            offset_x = self._pan_start_offset_x
            offset_y = self._pan_start_offset_y

            if 0 <= pan_index < len(self._images):
                path = self._images[pan_index]
                transform = self._image_transforms.get(path, {})
                offset_x = float(transform.get("offset_x", offset_x))
                offset_y = float(transform.get("offset_y", offset_y))

            self._reset_pan_state()
            self.setCursor(Qt.CursorShape.OpenHandCursor)

            if pan_active:
                self.panFinished.emit(
                    pan_index,
                    offset_x,
                    offset_y,
                )

            event.accept()
            return

        source = self._pressed_index
        target = self._index_at(event.position().toPoint())

        self._pressed_index = -1
        self._drag_target_index = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if source >= 0 and target >= 0 and source != target:
            self.swapRequested.emit(source, target)
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        if self._crop_mode:
            if not self._crop_source_rect.contains(
                event.position()
            ):
                event.ignore()
                return

            delta = event.angleDelta().y()

            if delta:
                factor = 0.92 if delta > 0 else 1.08
                self._scale_crop_around_center(
                    factor
                )

            event.accept()
            return

        index = self._index_at(event.position().toPoint())
        if index < 0:
            return super().wheelEvent(event)

        path = self._images[index]
        current = float(self._image_transforms.get(path, {}).get("zoom", 1.0))
        step = (
            0.10
            if event.angleDelta().y() > 0
            else -0.10
        )
        new_zoom = max(
            self.IMAGE_ZOOM_MIN,
            min(
                self.IMAGE_ZOOM_MAX,
                round(current + step, 2),
            ),
        )

        self._selected_indices = {index}
        self._selected_index = index
        self._selection_anchor = index
        self._emit_selection()
        self.zoomChanged.emit(index, new_zoom)
        event.accept()


    def _external_image_path(self, path: str):
        return is_supported_image_path(path)

    def rearm_external_drop(self):
        """
        只恢复外部文件拖入状态。

        选区同步会调用 refresh_preview() 和 set_images()。
        因此外部拖放恢复不能清空中央画布正在进行的内部鼠标操作，
        否则会中断图片交换拖动和放大图片抓手移动。
        """
        self.setAcceptDrops(True)
        self._external_drop_target_index = -1
        self._external_drop_target_rect = QRectF()
        self.update()

    def _cancel_internal_pointer_interaction(self):
        """
        显式取消中央画布内部鼠标操作。

        普通选区同步、页面刷新和外部拖放恢复不会调用此方法。
        """
        self._pressed_index = -1
        self._drag_target_index = -1
        self._reset_pan_state()
        self.setCursor(
            Qt.CursorShape.ArrowCursor
        )
        self.update()

    def _refresh_external_drop_geometry(self):
        """
        图片插入后若paint尚未执行，主动刷新槽位表，
        避免第二次拖入无法命中画布槽位。
        """
        if not self._external_drop_slot_rects:
            self.repaint()
            return

        page_start, page_end = self.page_range(
            self._page_index
        )
        indices = [
            index
            for index, _rect
            in self._external_drop_slot_rects
        ]

        if (
            not indices
            or min(indices) < page_start
            or max(indices) > page_end
        ):
            self.repaint()

    def _external_paths_from_mime(self, mime_data):
        paths = []

        if not mime_data.hasUrls():
            return paths

        for url in mime_data.urls():
            path = url.toLocalFile()
            if path and self._external_image_path(path):
                paths.append(path)

        return paths

    def _drop_receiver(self):
        receiver = self.parent()
        while receiver is not None:
            if (
                hasattr(receiver, "handle_canvas_multi_drop")
                or hasattr(receiver, "handle_image_list_drop_to_current_page")
            ):
                return receiver
            try:
                receiver = receiver.parent()
            except (AttributeError, RuntimeError):
                return None
        return None

    def _external_target_at(self, pos: QPoint):
        """
        返回鼠标所在槽位的插入索引与槽位矩形。

        已有图片槽位：插入到该图片之前。
        空槽位：插入到当前图片序列末端。
        """
        for insertion_index, rect in self._external_drop_slot_rects:
            if rect.contains(pos):
                return insertion_index, QRectF(rect)

        return -1, QRectF()

    def _clear_external_drop_target(self):
        changed = (
            self._external_drop_target_index != -1
            or not self._external_drop_target_rect.isNull()
        )

        self._external_drop_target_index = -1
        self._external_drop_target_rect = QRectF()

        if changed:
            self.update()

    def dragEnterEvent(self, event):
        """
        进入画布时只接受拖动，不修改图片数据。
        """
        mime = event.mimeData()
        internal_rows = rows_from_mime(mime)
        paths = self._external_paths_from_mime(mime)

        if not internal_rows and not paths:
            event.ignore()
            return

        self.setAcceptDrops(True)
        self._refresh_external_drop_geometry()

        target_index, target_rect = self._external_target_at(
            event.position().toPoint()
        )
        self._external_drop_target_index = target_index
        self._external_drop_target_rect = target_rect
        self.update()

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragMoveEvent(self, event):
        """
        鼠标移动时只更新目标区域高亮。
        不导入、不追加、不改变右侧图片列表。
        """
        mime = event.mimeData()
        internal_rows = rows_from_mime(mime)
        paths = self._external_paths_from_mime(mime)

        if not internal_rows and not paths:
            self._clear_external_drop_target()
            event.ignore()
            return

        self._refresh_external_drop_geometry()

        target_index, target_rect = self._external_target_at(
            event.position().toPoint()
        )

        changed = (
            target_index != self._external_drop_target_index
            or target_rect != self._external_drop_target_rect
        )

        self._external_drop_target_index = target_index
        self._external_drop_target_rect = target_rect

        if changed:
            self.update()

        if target_index < 0:
            event.ignore()
            return

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._clear_external_drop_target()
        self.rearm_external_drop()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.rearm_external_drop()

    def dropEvent(self, event):
        """
        只有松开鼠标后才插入图片。

        每次drop结束后都恢复中央画布拖入状态，
        支持连续拖入第2张及后续图片。
        """
        receiver_found = False

        try:
            mime = event.mimeData()
            internal_rows = rows_from_mime(mime)
            paths = self._external_paths_from_mime(mime)

            self._refresh_external_drop_geometry()
            target_index, target_rect = (
                self._external_target_at(
                    event.position().toPoint()
                )
            )

            # 图片刚插入后，新一轮paint可能尚未完成。
            if paths and target_index < 0:
                self.repaint()
                target_index, target_rect = (
                    self._external_target_at(
                        event.position().toPoint()
                    )
                )

            self._external_drop_target_index = (
                target_index
            )
            self._external_drop_target_rect = (
                target_rect
            )

            if (not internal_rows and not paths) or target_index < 0:
                event.ignore()
                return

            receiver = self._drop_receiver()
            if receiver is not None and internal_rows:
                handler = getattr(
                    receiver,
                    "handle_image_list_drop_to_current_page",
                    None,
                )
                if callable(handler):
                    receiver_found = bool(handler(internal_rows, target_index))
            elif receiver is not None and paths:
                handler = getattr(receiver, "handle_canvas_multi_drop", None)
                if callable(handler):
                    result = handler(paths, target_index)
                    receiver_found = True if result is None else bool(result)

            if receiver_found:
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
                event.accept()
            else:
                event.ignore()

        finally:
            self._clear_external_drop_target()
            self.rearm_external_drop()



    def paintEvent(self, event):
        self._title_edit_rect = QRectF()
        dark = bool(self._palette.get("dark", True))
        canvas_color = QColor(self._palette.get("canvas", "#070B14"))
        stage_color = QColor(self._palette.get("stage", "#0B1220"))
        card_color = QColor(self._palette.get("slide", "#111827"))
        empty_color = QColor(self._palette.get("slot", "#172033"))
        border_color = QColor(self._palette.get("border_strong", "#334155"))
        text_color = QColor(self._palette.get("muted", "#CBD5E1"))
        accent_color = QColor(self._palette.get("accent", "#22D3EE"))

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        painter.fillRect(self.rect(), canvas_color)
        stage_rect = self.rect().adjusted(10, 10, -10, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(stage_color)
        painter.drawRoundedRect(stage_rect, 14, 14)

        page_name = self._settings.get("page_size", "16:9")
        slide_w, slide_h = PAGE_SIZES.get(page_name, PAGE_SIZES["16:9"])
        ratio = slide_w / slide_h
        outer = self.rect().adjusted(30, 26, -30, -26)
        max_w = outer.width() * self._zoom
        max_h = outer.height() * self._zoom

        if max_w / max_h > ratio:
            height = max_h
            width = height * ratio
        else:
            width = max_w
            height = width / ratio

        slide_rect = QRectF(
            self.rect().center().x() - width / 2,
            self.rect().center().y() - height / 2,
            width,
            height,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 95 if dark else 45))
        painter.drawRoundedRect(slide_rect.translated(0, 10), 12, 12)
        painter.setBrush(card_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(slide_rect, 10, 10)

        if self._settings.get("show_grid", False):
            painter.save()
            grid_pen = QPen(QColor(border_color.red(), border_color.green(), border_color.blue(), 90), 1)
            grid_pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(grid_pen)
            for i in range(1, 12):
                x = slide_rect.left() + slide_rect.width() * i / 12
                painter.drawLine(int(x), int(slide_rect.top()), int(x), int(slide_rect.bottom()))
            for i in range(1, 8):
                y = slide_rect.top() + slide_rect.height() * i / 8
                painter.drawLine(int(slide_rect.left()), int(y), int(slide_rect.right()), int(y))
            painter.restore()

        rows = max(1, int(self._settings.get("rows", 2)))
        cols = max(1, int(self._settings.get("cols", 6)))
        ml = float(self._settings.get("margin_left", 0.6))
        mr = float(self._settings.get("margin_right", 0.6))
        mt = float(self._settings.get("margin_top", 0.8))
        mb = float(self._settings.get("margin_bottom", 0.8))
        gx = float(self._settings.get("gap_x", 0.25))
        gy = float(self._settings.get("gap_y", 0.35))
        label_h = float(self._settings.get("label_height", 0.45))

        sx = slide_rect.width() / slide_w
        sy = slide_rect.height() / slide_h

        show_title = bool(
            self._settings.get(
                "show_title",
                False,
            )
        )

        title_context = {}
        resolved_title_pages = (
            self._settings.get(
                "resolved_title_pages",
                [],
            )
        )

        if (
            isinstance(
                resolved_title_pages,
                list,
            )
            and 0
            <= self._page_index
            < len(
                resolved_title_pages
            )
            and isinstance(
                resolved_title_pages[
                    self._page_index
                ],
                dict,
            )
        ):
            title_context = dict(
                resolved_title_pages[
                    self._page_index
                ]
            )

        title_text = str(
            title_context.get(
                "title",
                self._settings.get(
                    "title_text",
                    "",
                ),
            )
            or ""
        ).strip()
        # UI-05-45A：副标题功能已经移除；旧工程字段只做兼容读取。
        subtitle_text = ""

        title_style = dict(
            title_context.get(
                "style",
                self._settings.get(
                    "title_style",
                    {},
                ),
            )
            or {}
        )

        try:
            title_height = float(
                title_style.get(
                    "region_height_cm",
                    self._settings.get(
                        "title_height",
                        0.9,
                    ),
                )
            )
        except (TypeError, ValueError):
            title_height = 0.9

        try:
            title_top_spacing = float(
                title_style.get(
                    "top_spacing_cm",
                    0.0,
                )
            )
        except (TypeError, ValueError):
            title_top_spacing = 0.0

        # UI-05-45A：页面 Logo 功能已经移除。
        logo_path = ""
        logo_pixmap = QPixmap()
        has_logo = False

        title_geometry = resolve_title_vertical_geometry(
            {
                **title_style,
                "font_size": title_style.get("font_size", 20.0),
                "region_height_cm": title_height,
                "top_spacing_cm": title_top_spacing,
            },
            enabled=show_title,
            has_content=bool(title_text or subtitle_text or has_logo),
        )
        effective_title_h = float(title_geometry["effective_height_cm"])
        effective_title_spacing = float(
            title_geometry["effective_top_spacing_cm"]
        )

        usable_w = (
            slide_w
            - ml
            - mr
            - (cols - 1) * gx
        )
        usable_h = (
            slide_h
            - mt
            - mb
            - effective_title_spacing
            - effective_title_h
            - (rows - 1) * gy
        )

        if usable_w <= 0 or usable_h <= 0:
            painter.setPen(
                QColor("#EF4444")
            )
            painter.drawText(
                slide_rect,
                Qt.AlignmentFlag.AlignCenter,
                "边距或标题设置过大，已没有可用排版区域",
            )
            return

        if effective_title_h > 0:
            title_rect = QRectF(
                slide_rect.left()
                + ml * sx,
                slide_rect.top()
                + (
                    mt
                    + effective_title_spacing
                )
                * sy,
                usable_w * sx,
                effective_title_h * sy,
            )
            self._title_edit_rect = QRectF(title_rect)

            # FIX09：在中央画布标题区域真实绘制Logo。
            # 尺寸限制在标题区内部并保持原始宽高比。
            logo_space_px = 0.0

            if has_logo:
                logo_max_h = max(
                    8,
                    int(
                        title_rect.height()
                        * 0.78
                    ),
                )
                logo_max_w = max(
                    12,
                    int(
                        min(
                            1.35 * sx,
                            title_rect.width()
                            * 0.18,
                        )
                    ),
                )
                scaled_logo = logo_pixmap.scaled(
                    logo_max_w,
                    logo_max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                if not scaled_logo.isNull():
                    logo_x = (
                        title_rect.left()
                        + 5
                    )
                    logo_y = (
                        title_rect.top()
                        + (
                            title_rect.height()
                            - scaled_logo.height()
                        )
                        / 2
                    )
                    painter.drawPixmap(
                        int(logo_x),
                        int(logo_y),
                        scaled_logo,
                    )
                    logo_space_px = (
                        scaled_logo.width()
                        + 12
                    )

            text_title_rect = QRectF(
                title_rect.left()
                + logo_space_px,
                title_rect.top(),
                max(
                    1.0,
                    title_rect.width()
                    - logo_space_px,
                ),
                title_rect.height(),
            )

            title_color = QColor(
                str(
                    title_style.get(
                        "color",
                        "",
                    )
                    or ""
                )
            )
            if not title_color.isValid():
                title_color = QColor(
                    text_color
                )
            painter.setPen(
                title_color
            )

            font_family = str(
                title_style.get(
                    "font_family",
                    "Microsoft YaHei",
                )
                or "Microsoft YaHei"
            )
            try:
                font_size_pt = float(
                    title_style.get(
                        "font_size",
                        20.0,
                    )
                )
            except (TypeError, ValueError):
                font_size_pt = 20.0

            title_font = QFont(
                font_family
            )
            title_font.setBold(
                bool(
                    title_style.get(
                        "bold",
                        True,
                    )
                )
            )
            requested_title_px = max(
                6,
                round(
                    font_size_pt
                    * 2.54
                    / 72.0
                    * sy
                ),
            )
            title_font.setPixelSize(requested_title_px)
            painter.setFont(
                title_font
            )

            align_value = str(
                title_style.get(
                    "alignment",
                    "center",
                )
                or "center"
            ).lower()
            horizontal_alignment = {
                "left": (
                    Qt.AlignmentFlag.AlignLeft
                ),
                "right": (
                    Qt.AlignmentFlag.AlignRight
                ),
            }.get(
                align_value,
                Qt.AlignmentFlag.AlignHCenter,
            )
            text_alignment = (
                horizontal_alignment
                | Qt.AlignmentFlag.AlignVCenter
            )

            available_title_width = max(1, int(text_title_rect.width() - 10))
            measured_title_width = max(
                1,
                painter.fontMetrics().horizontalAdvance(title_text),
            )
            if measured_title_width > available_title_width:
                fitted_px = max(
                    6,
                    int(
                        requested_title_px
                        * available_title_width
                        / measured_title_width
                    ),
                )
                title_font.setPixelSize(fitted_px)
                painter.setFont(title_font)

            title_display = painter.fontMetrics().elidedText(
                title_text,
                Qt.TextElideMode.ElideRight,
                available_title_width,
            )

            main_rect = text_title_rect

            if subtitle_text:
                main_rect = QRectF(
                    text_title_rect.left(),
                    text_title_rect.top(),
                    text_title_rect.width(),
                    text_title_rect.height()
                    * 0.64,
                )

            painter.drawText(
                main_rect.adjusted(
                    5, 0, -5, 0
                ),
                text_alignment,
                title_display,
            )

            if subtitle_text:
                sub_rect = QRectF(
                    text_title_rect.left(),
                    main_rect.bottom(),
                    text_title_rect.width(),
                    text_title_rect.height()
                    * 0.36,
                )
                subtitle_font = QFont(
                    font_family
                )
                subtitle_font.setBold(
                    False
                )
                subtitle_font.setPixelSize(
                    max(
                        6,
                        round(
                            font_size_pt
                            * 0.55
                            * 2.54
                            / 72.0
                            * sy
                        ),
                    )
                )
                painter.setFont(
                    subtitle_font
                )
                sub_display = (
                    painter.fontMetrics().elidedText(
                        subtitle_text,
                        Qt.TextElideMode.ElideRight,
                        max(
                            1,
                            int(
                                sub_rect.width()
                                - 10
                            ),
                        ),
                    )
                )
                painter.drawText(
                    sub_rect.adjusted(
                        5, 0, -5, 0
                    ),
                    text_alignment,
                    sub_display,
                )

        # 没有标题时，在幻灯片上沿外侧提供轻量入口；它只属于编辑界面，
        # 不进入页面缩略图和任何导出结果。
        if (
            not self._navigation_thumbnail_mode
            and effective_title_h <= 0
        ):
            control_w = 62.0
            control_h = 21.0
            control_rect = QRectF(
                slide_rect.right() - control_w - 5.0,
                max(3.0, slide_rect.top() - control_h - 3.0),
                control_w,
                control_h,
            )
            self._title_edit_rect = QRectF(control_rect)
            painter.save()
            painter.setPen(QPen(accent_color, 1))
            painter.setBrush(QColor(accent_color.red(), accent_color.green(), accent_color.blue(), 24))
            painter.drawRoundedRect(control_rect, 7, 7)
            painter.setFont(QFont("Microsoft YaHei", 8))
            label = (
                "+ Title"
                if self._settings.get("language") == "en_US"
                else "＋ 标题"
            )
            painter.drawText(
                control_rect,
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
            painter.restore()

        cell_w = usable_w / cols
        cell_h = usable_h / rows
        show_label = self._settings.get("show_filename") or self._settings.get("show_index")
        actual_label_h = min(label_h, cell_h * 0.3) if show_label else 0
        image_h = max(0.01, cell_h - actual_label_h)

        per_page = rows * cols
        start, page_end = self.page_range(
            self._page_index
        )
        page_images = self._images[start:page_end]
        painter.setFont(QFont("Microsoft YaHei UI", 7))
        self._slot_rects = []
        self._external_drop_slot_rects = []

        for pos in range(per_page):
            row = pos // cols
            col = pos % cols
            absolute_index = start + pos

            x_cm = ml + col * (cell_w + gx)
            y_cm = (
                mt
                + effective_title_spacing
                + effective_title_h
                + row * (
                    cell_h
                    + gy
                )
            )
            cell = QRectF(
                slide_rect.left() + x_cm * sx,
                slide_rect.top() + y_cm * sy,
                cell_w * sx,
                cell_h * sy,
            )
            image_rect = QRectF(cell.left(), cell.top(), cell.width(), image_h * sy)

            # 外部拖入可以命中已有图片槽位，也可以命中当前页空槽位。
            # 显式分页的空槽位应插入到当前页末尾，而不是整个项目末尾。
            insertion_index = (
                absolute_index
                if pos < len(page_images)
                else page_end
            )
            self._external_drop_slot_rects.append(
                (insertion_index, QRectF(image_rect))
            )

            if absolute_index < len(self._images):
                self._slot_rects.append((absolute_index, image_rect))

            painter.setBrush(empty_color)
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(image_rect, 4, 4)

            if pos >= len(page_images):
                if (
                    self._external_drop_target_index >= 0
                    and image_rect == self._external_drop_target_rect
                ):
                    painter.setBrush(
                        QColor(
                            accent_color.red(),
                            accent_color.green(),
                            accent_color.blue(),
                            62,
                        )
                    )
                    painter.setPen(
                        QPen(
                            accent_color,
                            3,
                            Qt.PenStyle.DashLine,
                        )
                    )
                    painter.drawRoundedRect(
                        image_rect.adjusted(2, 2, -2, -2),
                        6,
                        6,
                    )
                    painter.setPen(accent_color)
                    painter.setFont(
                        QFont(
                            "Microsoft YaHei UI",
                            8,
                            QFont.Weight.Bold,
                        )
                    )
                    painter.drawText(
                        image_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        "松开插入",
                    )
                continue

            path = page_images[pos]
            pixmap = self._pixmap(path)
            transform = self._image_transforms.get(path, {})
            image_zoom = float(transform.get("zoom", 1.0))
            offset_x = float(transform.get("offset_x", 0.0))
            offset_y = float(transform.get("offset_y", 0.0))
            rotation = int(transform.get("rotation", 0)) % 360
            flip_h = bool(transform.get("flip_h", False))
            flip_v = bool(transform.get("flip_v", False))
            crop = normalize_crop(transform.get("crop"))

            crop_editor = (
                self._crop_mode
                and absolute_index == self._crop_index
            )
            crop_editor_target = QRectF()

            if not pixmap.isNull():
                clip = QPainterPath()
                clip.addRoundedRect(image_rect, 4, 4)
                painter.save()
                painter.setClipPath(clip)

                if crop_editor:
                    # UI-05-36B：
                    # 不再先缩小成槽位尺寸后再绘制。直接使用原始高分辨率
                    # pixmap 映射到目标区域，避免裁切模式预览被提前降采样。
                    source_w = max(
                        1.0,
                        float(pixmap.width()),
                    )
                    source_h = max(
                        1.0,
                        float(pixmap.height()),
                    )
                    editor_scale = min(
                        image_rect.width() / source_w,
                        image_rect.height() / source_h,
                    )
                    editor_width = (
                        source_w * editor_scale
                    )
                    editor_height = (
                        source_h * editor_scale
                    )
                    crop_editor_target = QRectF(
                        image_rect.center().x()
                        - editor_width / 2,
                        image_rect.center().y()
                        - editor_height / 2,
                        editor_width,
                        editor_height,
                    )
                    painter.drawPixmap(
                        crop_editor_target,
                        pixmap,
                        QRectF(pixmap.rect()),
                    )

                else:
                    source_pixmap = pixmap

                    if crop_is_modified(crop):
                        crop_x, crop_y, crop_w, crop_h = (
                            crop_rect_to_pixels(
                                crop,
                                pixmap.width(),
                                pixmap.height(),
                            )
                        )
                        source_pixmap = pixmap.copy(
                            crop_x,
                            crop_y,
                            crop_w,
                            crop_h,
                        )

                    # UI-05-36B：
                    # 旧版渲染链路：
                    #   原图 -> 缩小到图片槽 -> 再放大到 3.0x
                    # 这会把已经只有几百像素的槽位预览重新放大，因此
                    # 即使缓存中有 4K/8K 原图，中央画布仍然会明显模糊。
                    #
                    # 新版渲染链路：
                    #   原始高分辨率 pixmap -> 一次性映射到最终目标区域
                    # 不再创建低分辨率 base/scaled 中间图。
                    if rotation or flip_h or flip_v:
                        transform_matrix = QTransform()
                        transform_matrix.scale(
                            -1 if flip_h else 1,
                            -1 if flip_v else 1,
                        )
                        transform_matrix.rotate(
                            rotation
                        )
                        transformed = (
                            source_pixmap.transformed(
                                transform_matrix,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    else:
                        transformed = source_pixmap

                    source_w = max(
                        1.0,
                        float(transformed.width()),
                    )
                    source_h = max(
                        1.0,
                        float(transformed.height()),
                    )

                    if (
                        self._settings.get("image_mode")
                        == "裁剪填充"
                    ):
                        base_scale = max(
                            image_rect.width() / source_w,
                            image_rect.height() / source_h,
                        )
                    else:
                        base_scale = min(
                            image_rect.width() / source_w,
                            image_rect.height() / source_h,
                        )

                    final_scale = max(
                        0.000001,
                        base_scale * image_zoom,
                    )
                    target_width = (
                        source_w * final_scale
                    )
                    target_height = (
                        source_h * final_scale
                    )

                    target = QRectF(
                        image_rect.center().x()
                        - target_width / 2
                        + offset_x
                        * image_rect.width()
                        * 0.5,
                        image_rect.center().y()
                        - target_height / 2
                        + offset_y
                        * image_rect.height()
                        * 0.5,
                        target_width,
                        target_height,
                    )

                    # QPainter 从原始高分辨率源区域直接采样到最终目标。
                    # 在屏幕预览和450DPI页面导出中都只进行一次缩放。
                    painter.drawPixmap(
                        target,
                        transformed,
                        QRectF(
                            transformed.rect()
                        ),
                    )

                painter.restore()

            if self._settings.get("add_border"):
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(border_color, 1))
                painter.drawRoundedRect(image_rect, 4, 4)

            if absolute_index in self._selected_indices:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(
                    QPen(
                        accent_color,
                        3 if absolute_index == self._selected_index else 2,
                    )
                )
                painter.drawRoundedRect(
                    image_rect.adjusted(1, 1, -1, -1),
                    5,
                    5,
                )

                if absolute_index == self._selected_index:
                    badge = QRectF(
                        image_rect.right() - 56,
                        image_rect.top() + 6,
                        50,
                        20,
                    )
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(accent_color)
                    painter.drawRoundedRect(badge, 8, 8)
                    painter.setPen(
                        QColor(
                            self._palette.get(
                                "accent_text",
                                "#03141A",
                            )
                        )
                    )
                    painter.drawText(
                        badge,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{image_zoom:.1f}×",
                    )

            if (
                crop_editor
                and not crop_editor_target.isNull()
            ):
                self._paint_crop_overlay(
                    painter,
                    crop_editor_target,
                    accent_color,
                )

            if absolute_index == self._drag_target_index and absolute_index != self._pressed_index:
                painter.setBrush(QColor(accent_color.red(), accent_color.green(), accent_color.blue(), 55))
                painter.setPen(QPen(accent_color, 2, Qt.PenStyle.DashLine))
                painter.drawRoundedRect(image_rect.adjusted(2, 2, -2, -2), 5, 5)

            if (
                self._external_drop_target_index >= 0
                and image_rect == self._external_drop_target_rect
            ):
                painter.setBrush(
                    QColor(
                        accent_color.red(),
                        accent_color.green(),
                        accent_color.blue(),
                        62,
                    )
                )
                painter.setPen(
                    QPen(
                        accent_color,
                        3,
                        Qt.PenStyle.DashLine,
                    )
                )
                painter.drawRoundedRect(
                    image_rect.adjusted(2, 2, -2, -2),
                    6,
                    6,
                )
                painter.setPen(accent_color)
                painter.setFont(
                    QFont(
                        "Microsoft YaHei UI",
                        8,
                        QFont.Weight.Bold,
                    )
                )
                painter.drawText(
                    image_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "松开插入",
                )
                painter.setFont(QFont("Microsoft YaHei UI", 7))

            if show_label:
                parts = []
                if self._settings.get("show_index"):
                    parts.append(f"{absolute_index + 1:03d}")
                if self._settings.get("show_filename"):
                    parts.append(Path(path).stem)
                label_rect = QRectF(
                    cell.left(),
                    image_rect.bottom(),
                    cell.width(),
                    actual_label_h * sy,
                )
                painter.setPen(text_color)
                txt = "  ".join(parts)
                txt = painter.fontMetrics().elidedText(
                    txt,
                    Qt.TextElideMode.ElideMiddle,
                    max(1, int(label_rect.width() - 4)),
                )
                painter.drawText(
                    label_rect.adjusted(2, 0, -2, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    txt,
                )

        if not self._images and not self._navigation_thumbnail_mode:
            guide_width = min(390.0, slide_rect.width() * 0.62)
            guide_height = 64.0
            guide_rect = QRectF(
                slide_rect.center().x() - guide_width / 2.0,
                slide_rect.center().y() - guide_height / 2.0,
                guide_width,
                guide_height,
            )
            guide_fill = QColor(card_color)
            guide_fill.setAlpha(235 if dark else 242)
            painter.save()
            painter.setBrush(guide_fill)
            painter.setPen(QPen(accent_color, 1.5))
            painter.drawRoundedRect(guide_rect, 10, 10)
            english = self._settings.get("language") == "en_US"
            primary = (
                "Add images or drop them here"
                if english
                else "添加图片，或将图片拖到此处"
            )
            secondary = (
                "You can also import a PPT from the top bar"
                if english
                else "也可以从顶部导入 PPT"
            )
            painter.setPen(accent_color)
            painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
            painter.drawText(
                guide_rect.adjusted(10, 7, -10, -28),
                Qt.AlignmentFlag.AlignCenter,
                primary,
            )
            painter.setPen(text_color)
            painter.setFont(QFont("Microsoft YaHei UI", 8))
            painter.drawText(
                guide_rect.adjusted(10, 31, -10, -6),
                Qt.AlignmentFlag.AlignCenter,
                secondary,
            )
            painter.restore()

        if self._settings.get("show_footer", False):
            footer_text = str(self._settings.get("footer_text", "")).strip()
            if footer_text:
                painter.setPen(text_color)
                painter.setFont(QFont("Microsoft YaHei UI", 6))
                painter.drawText(
                    QRectF(
                        slide_rect.left() + 10,
                        slide_rect.bottom() - 17,
                        slide_rect.width() - 20,
                        13,
                    ),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    footer_text,
                )

        if self._settings.get("show_page_number", True):
            painter.setPen(text_color)
            painter.drawText(
                QRectF(slide_rect.left(), slide_rect.bottom() - 18, slide_rect.width(), 15),
                Qt.AlignmentFlag.AlignCenter,
                f"{self._page_index + 1} / {self.page_count()}",
            )
