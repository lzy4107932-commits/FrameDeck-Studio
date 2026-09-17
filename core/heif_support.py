"""
FrameDeck Studio
UI-05-38A - HEIF / HEIC 图像支持

安装位置：
    core/heif_support.py

依赖：
    pillow-heif

安装命令：
    python -m pip install --upgrade pillow-heif
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from PIL import Image, ImageOps
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage


STANDARD_IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
    }
)

HEIF_EXTENSIONS = frozenset(
    {
        ".heic",
        ".heics",
        ".heif",
        ".heifs",
        ".hif",
    }
)

SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    STANDARD_IMAGE_EXTENSIONS
    | HEIF_EXTENSIONS
)

HEIF_FILE_FILTER = (
    "*.heic *.heics *.heif *.heifs *.hif"
)

ALL_IMAGE_FILE_FILTER = (
    "*.jpg *.jpeg *.png *.webp *.bmp "
    "*.tif *.tiff "
    + HEIF_FILE_FILTER
)


_REGISTER_LOCK = RLock()
_REGISTER_ATTEMPTED = False
_HEIF_AVAILABLE = False
_HEIF_ERROR = ""


def register_heif_support() -> bool:
    """
    注册 pillow-heif 的 Pillow 插件。

    不安装 pillow-heif 时不会让软件崩溃；
    标准 JPG / PNG / TIFF 等格式仍可正常使用。
    """
    global _REGISTER_ATTEMPTED
    global _HEIF_AVAILABLE
    global _HEIF_ERROR

    with _REGISTER_LOCK:
        if _REGISTER_ATTEMPTED:
            return _HEIF_AVAILABLE

        _REGISTER_ATTEMPTED = True

        try:
            from pillow_heif import (
                register_heif_opener,
            )

            try:
                # 关闭HEIF内嵌缩略图解码，减少导入时额外开销。
                register_heif_opener(
                    thumbnails=False
                )
            except TypeError:
                # 兼容较旧的 pillow-heif。
                register_heif_opener()

            _HEIF_AVAILABLE = True
            _HEIF_ERROR = ""

        except Exception as error:
            _HEIF_AVAILABLE = False
            _HEIF_ERROR = (
                f"{type(error).__name__}: {error}"
            )

        return _HEIF_AVAILABLE


def heif_support_available() -> bool:
    return register_heif_support()


def heif_support_error() -> str:
    register_heif_support()
    return _HEIF_ERROR


def is_heif_path(
    path: str | Path,
) -> bool:
    return (
        Path(path).suffix.lower()
        in HEIF_EXTENSIONS
    )


def is_supported_image_path(
    path: str | Path,
) -> bool:
    return (
        Path(path).suffix.lower()
        in SUPPORTED_IMAGE_EXTENSIONS
    )


def can_decode_image_path(
    path: str | Path,
) -> bool:
    if not is_supported_image_path(path):
        return False

    if is_heif_path(path):
        return heif_support_available()

    return True


def missing_dependency_message() -> str:
    detail = heif_support_error()

    message = (
        "当前 Python 环境尚未安装 HEIF/HEIC 解码组件。\n\n"
        "请关闭软件后运行：\n"
        "python -m pip install --upgrade pillow-heif\n\n"
        "安装完成后重新启动 FrameDeck Studio。"
    )

    if detail:
        message += (
            "\n\n检测信息："
            + detail
        )

    return message


def open_pillow_image(
    path: str | Path,
):
    """
    使用 Pillow 打开图片。

    HEIF文件会先确保 pillow-heif 插件已经注册。
    返回值可直接用于 `with open_pillow_image(path) as image:`。
    """
    if is_heif_path(path):
        if not register_heif_support():
            raise RuntimeError(
                missing_dependency_message()
            )

    return Image.open(str(path))


def _scaled_pillow_size(
    source_width: int,
    source_height: int,
    *,
    target_size: QSize | None = None,
    max_long_edge: int | None = None,
) -> tuple[int, int]:
    source_width = max(
        1,
        int(source_width),
    )
    source_height = max(
        1,
        int(source_height),
    )

    if (
        target_size is not None
        and target_size.width() > 0
        and target_size.height() > 0
    ):
        ratio = min(
            target_size.width()
            / source_width,
            target_size.height()
            / source_height,
            1.0,
        )

        return (
            max(
                1,
                round(source_width * ratio),
            ),
            max(
                1,
                round(source_height * ratio),
            ),
        )

    if max_long_edge:
        max_long_edge = max(
            1,
            int(max_long_edge),
        )
        source_long_edge = max(
            source_width,
            source_height,
        )

        if source_long_edge > max_long_edge:
            ratio = (
                max_long_edge
                / source_long_edge
            )

            return (
                max(
                    1,
                    round(source_width * ratio),
                ),
                max(
                    1,
                    round(source_height * ratio),
                ),
            )

    return (
        source_width,
        source_height,
    )


def read_heif_qimage(
    path: str | Path,
    *,
    target_size: QSize | None = None,
    max_long_edge: int | None = None,
) -> QImage:
    """
    将HEIF/HEIC解码为独立QImage。

    - 使用HEIF主图像
    - 输出8位RGBA，兼容Qt中央画布与缩略图缓存
    - 使用LANCZOS高质量缩放
    - QImage.copy()确保图像数据不依赖临时Python字节对象
    """
    if not is_heif_path(path):
        return QImage()

    if not register_heif_support():
        return QImage()

    try:
        with open_pillow_image(path) as opened:
            # Pillow-Heif插件会打开主图像；load后再复制，
            # 防止HEIF文件关闭后数据失效。
            opened.load()
            image = ImageOps.exif_transpose(
                opened
            ).convert("RGBA")

            target_width, target_height = (
                _scaled_pillow_size(
                    image.width,
                    image.height,
                    target_size=target_size,
                    max_long_edge=max_long_edge,
                )
            )

            if (
                target_width != image.width
                or target_height != image.height
            ):
                image = image.resize(
                    (
                        target_width,
                        target_height,
                    ),
                    Image.Resampling.LANCZOS,
                )

            raw = image.tobytes(
                "raw",
                "RGBA",
            )
            stride = image.width * 4

            qimage = QImage(
                raw,
                image.width,
                image.height,
                stride,
                QImage.Format.Format_RGBA8888,
            )

            return qimage.copy()

    except Exception:
        return QImage()


# 软件导入模块时立即尝试注册。
register_heif_support()
