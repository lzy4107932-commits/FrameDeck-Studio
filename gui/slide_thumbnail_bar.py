# FrameDeck Studio V12
# UI-05-48A FIX02 SOURCE-COMPAT NAVIGATION
# Based directly on user's UI-05-21 source; no _theme_meta dependency
# PySide6

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.drag_protocol import rows_from_mime

THUMBNAIL_WIDTH = 100
THUMBNAIL_HEIGHT = 60
ITEM_WIDTH = 112
ITEM_HEIGHT = 84
BAR_HEIGHT = 108


def _placeholder_pixmap(index: int) -> QPixmap:
    pixmap = QPixmap(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
    pixmap.fill(QColor("#F8FAFC"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#CBD5E1"), 1))
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawRoundedRect(1, 1, THUMBNAIL_WIDTH - 2, THUMBNAIL_HEIGHT - 2, 5, 5)
    painter.setPen(QColor("#64748B"))
    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        f"Page {index + 1:02d}",
    )
    painter.end()
    return pixmap


def _source_to_pixmap(source: Any, index: int) -> QPixmap:
    pixmap = QPixmap()

    if isinstance(source, QPixmap):
        pixmap = source
    elif isinstance(source, str):
        pixmap = QPixmap(source)
    elif source is not None:
        for attr_name in ("path", "image_path", "file_path"):
            value = getattr(source, attr_name, None)
            if isinstance(value, str) and value:
                pixmap = QPixmap(value)
                break

    if pixmap.isNull():
        return _placeholder_pixmap(index)

    return pixmap.scaled(
        THUMBNAIL_WIDTH,
        THUMBNAIL_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class HorizontalPageList(QListWidget):
    """
    UI-05-24B 稳定横向页面列表。

    QListWidget 的 IconMode + Movement.Snap 在 Windows 上通常只改变图标
    的视觉坐标，不一定真正移动模型行，因此 rowsMoved 不会稳定触发。

    本版本不再依赖 Qt 自动移动模型，而是在 dropEvent 中手动执行：
        takeItem -> insertItem -> emit orderChanged
    """

    orderChanged = Signal(list)
    imageDropRequested = Signal(int, list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PageNavigatorList")

        self._drag_source_row = -1
        self._drop_insertion_row = -1
        self._image_drop_page = -1
        self._image_drop_edge = ""

        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListView.ResizeMode.Adjust)

        # Static 防止 IconMode 只移动视觉坐标而不改变列表模型。
        self.setMovement(QListView.Movement.Static)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setIconSize(QSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        self.setGridSize(QSize(ITEM_WIDTH, ITEM_HEIGHT))
        self.setUniformItemSizes(True)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(64)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAutoScroll(True)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSpacing(2)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            bar = self.horizontalScrollBar()
            step = max(40, bar.singleStep() * 3)
            bar.setValue(
                bar.value() - (step if delta > 0 else -step)
            )
            event.accept()
            return

        super().wheelEvent(event)

    def current_order(self) -> list[int]:
        order = []

        for row in range(self.count()):
            item = self.item(row)
            order.append(
                int(item.data(Qt.ItemDataRole.UserRole))
            )

        return order


    def startDrag(self, supported_actions):
        """
        单页选择时保留原拖动排序。
        多页选择时禁止拖动，避免“多个页面到底如何移动”的歧义。
        """
        if len(self.selectedItems()) > 1:
            self._drag_source_row = -1
            self._drop_insertion_row = -1
            self.viewport().update()
            return

        self._drag_source_row = self.currentRow()
        self._drop_insertion_row = -1

        if self._drag_source_row < 0:
            return

        super().startDrag(Qt.DropAction.MoveAction)

        self._drag_source_row = -1
        self._drop_insertion_row = -1
        self.viewport().update()

    def _insertion_row_at(self, position):
        """
        返回“插入线位置”，范围为 0..count。

        例如：
            0     = 第一项之前
            count = 最后一项之后
        """
        count = self.count()

        if count <= 0:
            return 0

        item = self.itemAt(position)

        if item is None:
            first_rect = self.visualItemRect(self.item(0))
            last_rect = self.visualItemRect(
                self.item(count - 1)
            )

            if position.x() < first_rect.center().x():
                return 0

            if position.x() > last_rect.center().x():
                return count

            # 鼠标位于项目之间的空白区域时，选择最近的插入位置。
            nearest_row = count
            nearest_distance = None

            for row in range(count):
                rect = self.visualItemRect(self.item(row))
                left_distance = abs(position.x() - rect.left())
                right_distance = abs(position.x() - rect.right())

                if (
                    nearest_distance is None
                    or left_distance < nearest_distance
                ):
                    nearest_distance = left_distance
                    nearest_row = row

                if right_distance < nearest_distance:
                    nearest_distance = right_distance
                    nearest_row = row + 1

            return max(0, min(nearest_row, count))

        row = self.row(item)
        rect = self.visualItemRect(item)

        if position.x() >= rect.center().x():
            row += 1

        return max(0, min(row, count))

    def dragEnterEvent(self, event):
        rows = rows_from_mime(event.mimeData())
        if rows and event.source() != self:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        if event.source() == self and self._drag_source_row >= 0:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        event.ignore()

    def dragMoveEvent(self, event):
        rows = rows_from_mime(event.mimeData())
        if rows and event.source() != self:
            item = self.itemAt(event.position().toPoint())
            if item is None:
                self._image_drop_page = -1
                self._image_drop_edge = ""
                self.viewport().update()
                event.ignore()
                return
            rect = self.visualItemRect(item)
            edge = "start" if event.position().x() < rect.center().x() else "end"
            page = self.row(item)
            if (page, edge) != (self._image_drop_page, self._image_drop_edge):
                self._image_drop_page = page
                self._image_drop_edge = edge
                self.viewport().update()
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        if event.source() != self or self._drag_source_row < 0:
            self._drop_insertion_row = -1
            self.viewport().update()
            event.ignore()
            return

        insertion_row = self._insertion_row_at(
            event.position().toPoint()
        )

        if insertion_row != self._drop_insertion_row:
            self._drop_insertion_row = insertion_row
            self.viewport().update()

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._drop_insertion_row = -1
        self._image_drop_page = -1
        self._image_drop_edge = ""
        self.viewport().update()
        event.accept()

    def move_page_item(self, source_row, insertion_row):
        """
        手动移动一个页面项目。

        insertion_row 是删除前的插入线位置，范围为 0..count。
        成功返回 True。
        """
        count = self.count()

        if not (
            0 <= source_row < count
            and 0 <= insertion_row <= count
        ):
            return False

        # 插入线位于源项目自身两侧时，顺序不变。
        if insertion_row in (source_row, source_row + 1):
            self.setCurrentRow(source_row)
            return False

        target_row = insertion_row

        # 源项目在插入线之前，删除后目标索引需要减一。
        if source_row < insertion_row:
            target_row -= 1

        target_row = max(
            0,
            min(target_row, count - 1),
        )

        item = self.takeItem(source_row)

        if item is None:
            return False

        self.insertItem(target_row, item)
        self.setCurrentItem(item)
        self.scrollToItem(
            item,
            QAbstractItemView.ScrollHint.EnsureVisible,
        )

        self.orderChanged.emit(self.current_order())
        return True

    def dropEvent(self, event):
        rows = rows_from_mime(event.mimeData())
        if rows and event.source() != self:
            item = self.itemAt(event.position().toPoint())
            page = self.row(item) if item is not None else -1
            edge = self._image_drop_edge
            if page >= 0 and edge in {"start", "end"}:
                self.imageDropRequested.emit(page, rows, edge)
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
            self._image_drop_page = -1
            self._image_drop_edge = ""
            self.viewport().update()
            return

        if event.source() != self:
            self._drop_insertion_row = -1
            self.viewport().update()
            event.ignore()
            return

        source_row = self._drag_source_row

        if source_row < 0:
            source_row = self.currentRow()

        insertion_row = self._insertion_row_at(
            event.position().toPoint()
        )

        moved = self.move_page_item(
            source_row,
            insertion_row,
        )

        self._drop_insertion_row = -1
        self.viewport().update()

        if moved:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            # 顺序未变化也结束本次拖动，避免 Qt 再执行默认移动。
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()

    def paintEvent(self, event):
        super().paintEvent(event)

        if 0 <= self._image_drop_page < self.count():
            item = self.item(self._image_drop_page)
            rect = self.visualItemRect(item).adjusted(2, 2, -2, -2)
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            accent = QColor("#4F6CFF")
            painter.setPen(QPen(accent, 3))
            painter.setBrush(QColor(79, 108, 255, 38))
            painter.drawRoundedRect(rect, 5, 5)
            x = rect.left() + 2 if self._image_drop_edge == "start" else rect.right() - 2
            painter.drawLine(x, rect.top() + 4, x, rect.bottom() - 4)
            painter.end()

        insertion_row = self._drop_insertion_row

        if insertion_row < 0:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        accent = QColor("#4F6CFF")
        painter.setPen(
            QPen(
                accent,
                4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )

        count = self.count()

        if count <= 0:
            x = 8
            top = 8
            bottom = max(20, self.viewport().height() - 20)
        elif insertion_row <= 0:
            rect = self.visualItemRect(self.item(0))
            x = rect.left() - 3
            top = rect.top() + 5
            bottom = rect.bottom() - 5
        elif insertion_row >= count:
            rect = self.visualItemRect(
                self.item(count - 1)
            )
            x = rect.right() + 3
            top = rect.top() + 5
            bottom = rect.bottom() - 5
        else:
            rect = self.visualItemRect(
                self.item(insertion_row)
            )
            x = rect.left() - 3
            top = rect.top() + 5
            bottom = rect.bottom() - 5

        painter.drawLine(x, top, x, bottom)

        # 插入线顶部和底部增加短横线，提高可见度。
        painter.drawLine(x - 4, top, x + 4, top)
        painter.drawLine(x - 4, bottom, x + 4, bottom)


class SlideThumbnailBar(QWidget):
    pageSelected = Signal(int)
    addPageRequested = Signal()
    duplicatePageRequested = Signal(int)
    deletePageRequested = Signal(int)
    pagesReordered = Signal(list)
    movePageRequested = Signal(int, int)
    imageDropRequested = Signal(int, list, str)


    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_index = 0
        self._page_sources: list[Any] = []
        self._canvas_source = None

        self.setFixedHeight(BAR_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.page_list = HorizontalPageList(self)
        self.page_list.itemClicked.connect(self._on_item_clicked)
        self.page_list.currentRowChanged.connect(self._on_current_row_changed)
        self.page_list.customContextMenuRequested.connect(self._show_context_menu)
        self.page_list.orderChanged.connect(self._on_order_changed)
        self.page_list.imageDropRequested.connect(self.imageDropRequested.emit)
        self.page_list.setToolTip(
            "单击：切换页面\n"
            "Ctrl + 左键：增减多选\n"
            "Shift + 左键：连续范围多选\n"
            "Delete / Backspace：删除所选页面\n"
            "单页选择时可拖动调整顺序\n"
            "图片拖到缩略图左/右半部：移到页首/页尾"
        )

        self.add_button = QPushButton("+", self)
        self.add_button.setObjectName("PageNavigatorAddButton")
        self.add_button.setFixedSize(44, 44)
        self.add_button.setToolTip("添加空白页面")
        self.add_button.clicked.connect(self.addPageRequested.emit)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(self.page_list, 1)
        top_layout.addWidget(
            self.add_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 1, 2, 1)
        main_layout.setSpacing(0)
        main_layout.addLayout(top_layout)


    def set_pages(self, pages):
        """
        增量同步页面卡片，不再 clear() 整个导航栏。

        重要兼容规则：
        - 本文件的稳定基线 _source_to_pixmap(source, index) 只有两个参数；
        - 不依赖 _theme_meta；
        - [None] * count 只同步页数，不覆盖已经生成的真实缩略图；
        - 删除中间页时由 remove_pages() 精确移除对应卡片。
        """
        incoming = list(pages or [])

        if not incoming:
            incoming = [None]

        target_count = len(incoming)
        old_current = max(0, int(self._current_index))
        old_selected = {
            self.page_list.row(item)
            for item in self.page_list.selectedItems()
            if self.page_list.row(item) >= 0
        }

        blocked = self.page_list.blockSignals(True)

        try:
            while self.page_list.count() > target_count:
                row = self.page_list.count() - 1
                self.page_list.takeItem(row)

                if 0 <= row < len(self._page_sources):
                    self._page_sources.pop(row)

            while self.page_list.count() < target_count:
                index = self.page_list.count()
                source = incoming[index]
                pixmap = _source_to_pixmap(source, index)

                item = QListWidgetItem(
                    QIcon(pixmap),
                    f"{index + 1:02d}",
                )
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    index,
                )
                item.setToolTip(
                    f"第 {index + 1} 页"
                )
                item.setSizeHint(
                    QSize(ITEM_WIDTH, ITEM_HEIGHT)
                )
                self.page_list.addItem(item)
                self._page_sources.append(
                    pixmap if source is not None else None
                )

            while len(self._page_sources) < target_count:
                self._page_sources.append(None)

            if len(self._page_sources) > target_count:
                del self._page_sources[target_count:]

            # 已存在页面只有拿到真实 source 时才更新图标。
            # refresh_preview() 传入 [None] * count 时保留缓存图。
            for index, source in enumerate(incoming):
                item = self.page_list.item(index)

                if item is None:
                    continue

                item.setText(f"{index + 1:02d}")
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    index,
                )
                item.setToolTip(
                    f"第 {index + 1} 页"
                )
                item.setSizeHint(
                    QSize(ITEM_WIDTH, ITEM_HEIGHT)
                )

                if source is not None:
                    pixmap = _source_to_pixmap(
                        source,
                        index,
                    )
                    item.setIcon(QIcon(pixmap))
                    # Keep only the final 100x60 navigation image. Retaining
                    # the 300x190 render source for every page multiplied
                    # memory usage without improving the visible result.
                    self._page_sources[index] = pixmap

            valid_selected = sorted(
                row
                for row in old_selected
                if 0 <= row < target_count
            )

            self.page_list.clearSelection()

            for row in valid_selected:
                item = self.page_list.item(row)

                if item is not None:
                    item.setSelected(True)

            safe_index = max(
                0,
                min(
                    old_current,
                    self.page_list.count() - 1,
                ),
            )
            self._current_index = safe_index

            if len(valid_selected) <= 1:
                self.page_list.setCurrentRow(
                    safe_index
                )

        finally:
            self.page_list.blockSignals(blocked)

        item = self.page_list.item(
            self._current_index
        )

        if item is not None:
            self.page_list.scrollToItem(
                item,
                QAbstractItemView.ScrollHint.EnsureVisible,
            )

    def update_thumbnails(self, pages):
        self.set_pages(pages)

    def update_page_thumbnail(self, index: int, source):
        if not (0 <= index < self.page_list.count()):
            return

        pixmap = _source_to_pixmap(source, index)
        item = self.page_list.item(index)
        item.setIcon(QIcon(pixmap))

        if 0 <= index < len(self._page_sources):
            self._page_sources[index] = pixmap


    def set_current_page(self, index: int):
        """
        同步当前页时保留 Ctrl/Shift 正在建立的多选集合。
        """
        if self.page_list.count() <= 0:
            self._current_index = 0
            return

        index = max(
            0,
            min(
                int(index),
                self.page_list.count() - 1,
            ),
        )
        self._current_index = index

        modifiers = QApplication.keyboardModifiers()
        multi_selecting = bool(
            modifiers
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        )

        if not multi_selecting:
            blocked = self.page_list.blockSignals(True)

            try:
                self.page_list.setCurrentRow(index)
            finally:
                self.page_list.blockSignals(blocked)

        item = self.page_list.item(index)

        if item is not None:
            self.page_list.scrollToItem(
                item,
                QAbstractItemView.ScrollHint.EnsureVisible,
            )

    def current_page(self) -> int:
        return self._current_index

    def page_count(self) -> int:
        return self.page_list.count()

    def current_order(self) -> list[int]:
        return self.page_list.current_order()


    def selected_pages(self) -> list[int]:
        """返回顶部导航当前选中的逻辑页索引。"""
        rows = []

        for item in self.page_list.selectedItems():
            row = self.page_list.row(item)

            if row >= 0:
                rows.append(row)

        return sorted(set(rows))


    def remove_pages(
        self,
        indices,
        current_index=None,
    ):
        """
        原位移除指定页面卡片。

        MainWindow 在真正删除页面数据前调用本方法，
        因而其它已经生成的缩略图可以继续保留，不必整栏 clear/rebuild。
        """
        rows = sorted(
            {
                int(index)
                for index in (indices or [])
                if 0
                <= int(index)
                < self.page_list.count()
            },
            reverse=True,
        )

        if not rows:
            return 0

        blocked = self.page_list.blockSignals(True)

        try:
            for row in rows:
                self.page_list.takeItem(row)

                if 0 <= row < len(self._page_sources):
                    self._page_sources.pop(row)

            if self.page_list.count() <= 0:
                self._page_sources = [None]
                pixmap = _placeholder_pixmap(0)
                item = QListWidgetItem(
                    QIcon(pixmap),
                    "01",
                )
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    0,
                )
                item.setToolTip("第 1 页")
                item.setSizeHint(
                    QSize(ITEM_WIDTH, ITEM_HEIGHT)
                )
                self.page_list.addItem(item)

            while len(self._page_sources) < self.page_list.count():
                self._page_sources.append(None)

            if len(self._page_sources) > self.page_list.count():
                del self._page_sources[
                    self.page_list.count():
                ]

            for row in range(
                self.page_list.count()
            ):
                item = self.page_list.item(row)

                if item is None:
                    continue

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row,
                )
                item.setText(
                    f"{row + 1:02d}"
                )
                item.setToolTip(
                    f"第 {row + 1} 页"
                )

                # 占位图里写着 Page XX，页号变化时同步重绘占位卡。
                if self._page_sources[row] is None:
                    item.setIcon(
                        QIcon(
                            _placeholder_pixmap(
                                row
                            )
                        )
                    )

            if current_index is None:
                current_index = min(
                    min(rows),
                    self.page_list.count() - 1,
                )

            safe_index = max(
                0,
                min(
                    int(current_index),
                    self.page_list.count() - 1,
                ),
            )

            self.page_list.clearSelection()
            self.page_list.setCurrentRow(
                safe_index
            )
            self._current_index = safe_index

        finally:
            self.page_list.blockSignals(blocked)

        item = self.page_list.item(
            self._current_index
        )

        if item is not None:
            self.page_list.scrollToItem(
                item,
                QAbstractItemView.ScrollHint.EnsureVisible,
            )

        return len(rows)

    def set_canvas_source(self, canvas):
        self._canvas_source = canvas

    def refresh_from_canvas(self):
        return

    def _on_item_clicked(self, item):
        row = self.page_list.row(item)
        if row < 0:
            return
        self._current_index = row
        self.pageSelected.emit(row)

    def _on_current_row_changed(self, row):
        if row >= 0:
            self._current_index = row


    def _show_context_menu(self, position):
        item = self.page_list.itemAt(position)

        if item is None:
            return

        row = self.page_list.row(item)

        if row < 0:
            return

        selected = self.selected_pages()

        # 右键点到未选中的页：切回单页上下文。
        if row not in selected:
            blocked = self.page_list.blockSignals(True)

            try:
                self.page_list.clearSelection()
                self.page_list.setCurrentRow(row)
            finally:
                self.page_list.blockSignals(blocked)

            self._current_index = row
            selected = [row]

        menu = QMenu(self)

        if len(selected) > 1:
            delete_action = QAction(
                f"删除所选页面（{len(selected)} 页）",
                self,
            )
            delete_action.triggered.connect(
                lambda checked=False, page=row:
                self.deletePageRequested.emit(page)
            )
            menu.addAction(delete_action)

        else:
            duplicate_action = QAction(
                "复制页面",
                self,
            )
            delete_action = QAction(
                "删除页面",
                self,
            )

            duplicate_action.triggered.connect(
                lambda checked=False, page=row:
                self.duplicatePageRequested.emit(page)
            )
            delete_action.triggered.connect(
                lambda checked=False, page=row:
                self.deletePageRequested.emit(page)
            )

            menu.addAction(duplicate_action)
            menu.addAction(delete_action)

        menu.exec(
            self.page_list.viewport().mapToGlobal(
                position
            )
        )

    def _on_order_changed(self, order):
        """
        列表拖动完成后，向 MainWindow 发送完整页面顺序。

        order 的含义：
            新位置 -> 拖动前的页面索引

        例如：
            [1, 0, 2]
        表示原第 2 页移动到第 1 页。
        """
        if not order:
            return

        current_item = self.page_list.currentItem()
        if current_item is not None:
            self._current_index = self.page_list.row(current_item)

        self.pagesReordered.emit(list(order))

    def commit_current_order(self):
        """
        MainWindow 成功应用页面顺序后调用。

        将当前视觉顺序重新编号为 0..N-1，避免下一次拖动仍携带
        上一次的旧 UserRole，从而产生错误排列。
        """
        current_row = self.page_list.currentRow()

        self.page_list.blockSignals(True)
        try:
            for row in range(self.page_list.count()):
                item = self.page_list.item(row)
                item.setData(Qt.ItemDataRole.UserRole, row)
                item.setText(f"{row + 1:02d}")
                item.setToolTip(f"第 {row + 1} 页")
        finally:
            self.page_list.blockSignals(False)

        if self.page_list.count() > 0:
            current_row = max(
                0,
                min(current_row, self.page_list.count() - 1),
            )
            self._current_index = current_row
            self.page_list.setCurrentRow(current_row)


    def reset_visual_order(self, current_index=0):
        """
        当 MainWindow 拒绝一次页面移动时恢复标准页面顺序。

        增量 set_pages() 不再 clear()，因此这里不能继续依赖
        set_pages([None] * count) 来恢复顺序，而是按 UserRole 排回去。
        """
        count = self.page_list.count()

        if count <= 0:
            self.set_pages([None])
            self.set_current_page(0)
            return

        blocked = self.page_list.blockSignals(True)

        try:
            items = []

            while self.page_list.count() > 0:
                item = self.page_list.takeItem(0)

                if item is not None:
                    items.append(item)

            items.sort(
                key=lambda item: int(
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                )
            )

            self._page_sources = [
                None
            ] * len(items)

            for row, item in enumerate(items):
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row,
                )
                item.setText(
                    f"{row + 1:02d}"
                )
                item.setToolTip(
                    f"第 {row + 1} 页"
                )
                self.page_list.addItem(item)

        finally:
            self.page_list.blockSignals(blocked)

        self.set_current_page(current_index)
