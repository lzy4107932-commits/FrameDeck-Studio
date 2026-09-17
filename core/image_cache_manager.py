"""
FrameDeck Studio
UI-05-34A - 图片缓存管理器

安装位置：
    core/image_cache_manager.py
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap

from core.app_paths import user_data_dir
from core.heif_support import (
    is_heif_path,
    read_heif_qimage,
)


CACHE_VERSION = "ui05_38a_heif_v1"


@dataclass(frozen=True)
class CacheStats:
    thumbnail_memory_items: int
    preview_memory_items: int
    thumbnail_memory_bytes: int
    preview_memory_bytes: int
    disk_files: int
    disk_bytes: int


class _PixmapLRU:
    def __init__(self, max_bytes: int):
        self.max_bytes = max(8 * 1024 * 1024, int(max_bytes))
        self._items: OrderedDict[str, tuple[QPixmap, int]] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    @staticmethod
    def _cost(pixmap: QPixmap) -> int:
        if pixmap.isNull():
            return 0
        return max(1, pixmap.width() * pixmap.height() * 4)

    def get(self, key: str) -> QPixmap | None:
        with self._lock:
            entry = self._items.pop(key, None)

            if entry is None:
                return None

            self._items[key] = entry
            return entry[0]

    def put(self, key: str, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return

        cost = self._cost(pixmap)

        with self._lock:
            old = self._items.pop(key, None)

            if old is not None:
                self._bytes -= old[1]

            self._items[key] = (pixmap, cost)
            self._bytes += cost

            while (
                self._bytes > self.max_bytes
                and len(self._items) > 1
            ):
                _key, (_pixmap, old_cost) = self._items.popitem(
                    last=False
                )
                self._bytes -= old_cost

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def info(self) -> tuple[int, int]:
        with self._lock:
            return len(self._items), self._bytes


class ImageCacheManager:
    """
    右侧列表：
        内存缓存 + 磁盘缩略图缓存。

    中央画布：
        有内存上限的 LRU 预览缓存。
    """

    def __init__(
        self,
        *,
        thumbnail_memory_mb: int = 96,
        preview_memory_mb: int = 384,
    ):
        self.cache_root = (
            user_data_dir()
            / "cache"
            / "image_thumbnails"
            / CACHE_VERSION
        )
        self.cache_root.mkdir(parents=True, exist_ok=True)

        self._thumbnail_memory = _PixmapLRU(
            thumbnail_memory_mb * 1024 * 1024
        )
        self._preview_memory = _PixmapLRU(
            preview_memory_mb * 1024 * 1024
        )
        self._prune_marker = self.cache_root / ".last_prune.json"

    @staticmethod
    def _file_signature(path: str) -> tuple[str, int, int]:
        source = Path(path)

        try:
            resolved = str(source.resolve())
        except OSError:
            resolved = str(source.absolute())

        try:
            stat = source.stat()
            return resolved, int(stat.st_size), int(stat.st_mtime_ns)
        except OSError:
            return resolved, 0, 0

    def _key(
        self,
        path: str,
        *,
        kind: str,
        width: int = 0,
        height: int = 0,
        max_long_edge: int = 0,
    ) -> str:
        resolved, size, modified = self._file_signature(path)
        raw = json.dumps(
            {
                "version": CACHE_VERSION,
                "kind": kind,
                "path": resolved,
                "size": size,
                "modified": modified,
                "width": int(width),
                "height": int(height),
                "max_long_edge": int(max_long_edge),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha1(raw).hexdigest()

    def _disk_path(self, key: str) -> Path:
        directory = self.cache_root / key[:2]
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.png"

    @staticmethod
    def _read_scaled(
        path: str,
        *,
        target_size: QSize | None = None,
        max_long_edge: int | None = None,
    ) -> QImage:
        # Qt在多数Windows环境中不自带HEIF图像插件。
        # HEIF/HEIC使用pillow-heif解码，其余格式继续走QImageReader。
        if is_heif_path(path):
            return read_heif_qimage(
                path,
                target_size=target_size,
                max_long_edge=max_long_edge,
            )

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()

        if (
            target_size is not None
            and source_size.width() > 0
            and source_size.height() > 0
        ):
            reader.setScaledSize(
                source_size.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
            )

        elif (
            max_long_edge
            and source_size.width() > 0
            and source_size.height() > 0
            and max(
                source_size.width(),
                source_size.height(),
            ) > max_long_edge
        ):
            ratio = float(max_long_edge) / float(
                max(source_size.width(), source_size.height())
            )
            reader.setScaledSize(
                QSize(
                    max(1, round(source_size.width() * ratio)),
                    max(1, round(source_size.height() * ratio)),
                )
            )

        image = reader.read()

        if image.isNull():
            return image

        if target_size is not None and (
            image.width() > target_size.width()
            or image.height() > target_size.height()
        ):
            image = image.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        elif max_long_edge and max(
            image.width(),
            image.height(),
        ) > max_long_edge:
            image = image.scaled(
                QSize(max_long_edge, max_long_edge),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        return image

    def thumbnail_image(
        self,
        path: str,
        width: int = 360,
        height: int = 240,
    ) -> QImage:
        """
        后台线程安全的缩略图入口。

        只使用 QImage，不创建 QPixmap。
        因此可以在 QThreadPool / QRunnable 中执行。
        """
        width = max(32, int(width))
        height = max(24, int(height))
        key = self._key(
            path,
            kind="thumbnail",
            width=width,
            height=height,
        )
        disk_path = self._disk_path(key)

        if disk_path.is_file():
            image = QImage(str(disk_path))

            if not image.isNull():
                try:
                    os.utime(disk_path, None)
                except OSError:
                    pass

                # 返回独立数据，安全跨线程传递。
                return image.copy()

        image = self._read_scaled(
            path,
            target_size=QSize(width, height),
        )

        if image.isNull():
            return QImage()

        # 每个线程使用独立临时文件，避免并发写同一路径。
        temporary = disk_path.with_name(
            (
                f"{disk_path.stem}."
                f"{os.getpid()}."
                f"{get_ident()}.tmp"
            )
        )

        try:
            if image.save(
                str(temporary),
                "PNG",
            ):
                os.replace(
                    temporary,
                    disk_path,
                )
        except OSError:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        return image.copy()

    def cached_thumbnail_pixmap(
        self,
        path: str,
        width: int = 360,
        height: int = 240,
    ) -> QPixmap:
        """
        仅读取已存在的缩略图缓存。

        不解码原始图片，适合主线程中的页面导航离屏渲染。
        """
        width = max(32, int(width))
        height = max(24, int(height))
        key = self._key(
            path,
            kind="thumbnail",
            width=width,
            height=height,
        )

        pixmap = self._thumbnail_memory.get(
            key
        )

        if pixmap is not None:
            return pixmap

        disk_path = self._disk_path(key)

        if not disk_path.is_file():
            return QPixmap()

        pixmap = QPixmap(
            str(disk_path)
        )

        if pixmap.isNull():
            return QPixmap()

        self._thumbnail_memory.put(
            key,
            pixmap,
        )

        try:
            os.utime(disk_path, None)
        except OSError:
            pass

        return pixmap

    def remember_thumbnail_pixmap(
        self,
        path: str,
        width: int,
        height: int,
        pixmap: QPixmap,
    ) -> None:
        """
        在主线程中把后台生成的 QPixmap 写入内存 LRU。
        """
        if pixmap.isNull():
            return

        key = self._key(
            path,
            kind="thumbnail",
            width=max(32, int(width)),
            height=max(24, int(height)),
        )
        self._thumbnail_memory.put(
            key,
            pixmap,
        )

    def thumbnail(
        self,
        path: str,
        width: int = 180,
        height: int = 124,
    ) -> QPixmap:
        """
        主线程兼容入口。

        优先内存/磁盘缓存；缓存不存在时通过 QImage 解码，
        最后才在主线程创建 QPixmap。
        """
        width = max(32, int(width))
        height = max(24, int(height))

        cached = self.cached_thumbnail_pixmap(
            path,
            width,
            height,
        )

        if not cached.isNull():
            return cached

        image = self.thumbnail_image(
            path,
            width,
            height,
        )

        if image.isNull():
            return QPixmap()

        pixmap = QPixmap.fromImage(
            image
        )
        self.remember_thumbnail_pixmap(
            path,
            width,
            height,
            pixmap,
        )
        return pixmap


    def preview_pixmap(
        self,
        path: str,
        *,
        max_long_edge: int = 3200,
    ) -> QPixmap:
        max_long_edge = max(800, int(max_long_edge))
        key = self._key(
            path,
            kind="preview",
            max_long_edge=max_long_edge,
        )

        pixmap = self._preview_memory.get(key)

        if pixmap is not None:
            return pixmap

        image = self._read_scaled(
            path,
            max_long_edge=max_long_edge,
        )

        if image.isNull():
            return QPixmap()

        pixmap = QPixmap.fromImage(image)
        self._preview_memory.put(key, pixmap)
        return pixmap

    def clear_memory(self) -> None:
        self._thumbnail_memory.clear()
        self._preview_memory.clear()

    def clear_disk_cache(self) -> int:
        deleted = 0

        for path in self.cache_root.rglob("*.png"):
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass

        return deleted

    def prune_disk_cache(
        self,
        *,
        max_bytes: int = 1024 * 1024 * 1024,
        max_age_days: int = 60,
    ) -> dict[str, int]:
        now = time.time()
        max_age_seconds = max(1, int(max_age_days)) * 86400
        max_bytes = max(64 * 1024 * 1024, int(max_bytes))

        files: list[tuple[Path, float, int]] = []
        deleted = 0
        freed = 0

        for path in self.cache_root.rglob("*.png"):
            try:
                stat = path.stat()
            except OSError:
                continue

            if now - stat.st_mtime > max_age_seconds:
                try:
                    path.unlink()
                    deleted += 1
                    freed += int(stat.st_size)
                except OSError:
                    pass
            else:
                files.append(
                    (path, float(stat.st_mtime), int(stat.st_size))
                )

        total = sum(size for _path, _mtime, size in files)

        if total > max_bytes:
            files.sort(key=lambda item: item[1])

            for path, _mtime, size in files:
                if total <= max_bytes:
                    break

                try:
                    path.unlink()
                    total -= size
                    deleted += 1
                    freed += size
                except OSError:
                    pass

        return {
            "deleted_files": deleted,
            "freed_bytes": freed,
            "remaining_bytes": max(0, total),
        }

    def prune_if_due(
        self,
        *,
        interval_hours: int = 24,
        max_bytes: int = 1024 * 1024 * 1024,
        max_age_days: int = 60,
    ) -> dict[str, int] | None:
        now = time.time()
        interval = max(1, int(interval_hours)) * 3600

        try:
            marker = json.loads(
                self._prune_marker.read_text(encoding="utf-8")
            )
            last_run = float(marker.get("timestamp", 0.0))
        except Exception:
            last_run = 0.0

        if now - last_run < interval:
            return None

        result = self.prune_disk_cache(
            max_bytes=max_bytes,
            max_age_days=max_age_days,
        )

        try:
            self._prune_marker.write_text(
                json.dumps(
                    {"timestamp": now, **result},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

        return result

    def stats(self) -> CacheStats:
        thumb_items, thumb_bytes = self._thumbnail_memory.info()
        preview_items, preview_bytes = self._preview_memory.info()
        disk_files = 0
        disk_bytes = 0

        for path in self.cache_root.rglob("*.png"):
            try:
                disk_files += 1
                disk_bytes += int(path.stat().st_size)
            except OSError:
                pass

        return CacheStats(
            thumbnail_memory_items=thumb_items,
            preview_memory_items=preview_items,
            thumbnail_memory_bytes=thumb_bytes,
            preview_memory_bytes=preview_bytes,
            disk_files=disk_files,
            disk_bytes=disk_bytes,
        )


_SHARED_CACHE: ImageCacheManager | None = None
_SHARED_LOCK = RLock()


def image_cache() -> ImageCacheManager:
    global _SHARED_CACHE

    with _SHARED_LOCK:
        if _SHARED_CACHE is None:
            _SHARED_CACHE = ImageCacheManager()

        return _SHARED_CACHE
