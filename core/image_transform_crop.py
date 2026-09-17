"""
FrameDeck Studio
UI-05-30 Stage 01 - Non-destructive image crop data layer

建议安装位置：
    core/image_transform_crop.py

本模块只负责裁切数据，不修改图片文件，也不依赖 PySide6。
裁切数据使用 0.0～1.0 的归一化坐标，适合保存到 FDS 工程 JSON。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, MutableMapping

CROP_MIN_SIZE = 0.03

# UI-05-37B：允许高倍缩放图片保存超过 ±100% 的位置。
IMAGE_OFFSET_LIMIT = 50.0

DEFAULT_CROP: dict[str, Any] = {
    "enabled": False,
    "x": 0.0,
    "y": 0.0,
    "width": 1.0,
    "height": 1.0,
    "aspect_mode": "free",
    "aspect_ratio": None,
}

DEFAULT_IMAGE_TRANSFORM: dict[str, Any] = {
    "zoom": 1.0,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "rotation": 0,
    "flip_h": False,
    "flip_v": False,
    "crop": deepcopy(DEFAULT_CROP),
}


@dataclass(frozen=True)
class CropRect:
    """归一化裁切矩形。"""

    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def top(self) -> float:
        return self.y

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0

    def as_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def _finite_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)

    if not isfinite(number):
        return float(default)

    return number


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def default_crop() -> dict[str, Any]:
    """返回新的默认裁切字典，避免多个图片共享同一对象。"""
    return deepcopy(DEFAULT_CROP)


def default_transform() -> dict[str, Any]:
    """返回新的完整图片变换字典。"""
    return deepcopy(DEFAULT_IMAGE_TRANSFORM)


def normalize_crop(
    crop: Mapping[str, Any] | None,
    *,
    minimum_size: float = CROP_MIN_SIZE,
) -> dict[str, Any]:
    """
    清理并约束裁切数据。

    坐标规则：
        x / y / width / height 均使用 0.0～1.0。
        裁切矩形始终位于原图内部。
    """
    source = dict(crop or {})

    minimum_size = _clamp(
        _finite_float(minimum_size, CROP_MIN_SIZE),
        0.001,
        1.0,
    )

    x = _clamp(_finite_float(source.get("x"), 0.0), 0.0, 1.0)
    y = _clamp(_finite_float(source.get("y"), 0.0), 0.0, 1.0)

    width = _clamp(
        _finite_float(source.get("width"), 1.0),
        minimum_size,
        1.0,
    )
    height = _clamp(
        _finite_float(source.get("height"), 1.0),
        minimum_size,
        1.0,
    )

    if x + width > 1.0:
        x = max(0.0, 1.0 - width)

    if y + height > 1.0:
        y = max(0.0, 1.0 - height)

    aspect_mode = str(
        source.get("aspect_mode", "free") or "free"
    ).strip().lower()

    if aspect_mode not in {"free", "original", "frame", "custom"}:
        aspect_mode = "free"

    aspect_ratio = source.get("aspect_ratio")
    aspect_ratio = _finite_float(aspect_ratio, 0.0)

    if aspect_ratio <= 0.0:
        aspect_ratio = None

    enabled = bool(source.get("enabled", False))

    if (
        abs(x) < 1e-9
        and abs(y) < 1e-9
        and abs(width - 1.0) < 1e-9
        and abs(height - 1.0) < 1e-9
    ):
        enabled = False

    return {
        "enabled": enabled,
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
        "aspect_mode": aspect_mode,
        "aspect_ratio": (
            round(aspect_ratio, 6)
            if aspect_ratio is not None
            else None
        ),
    }


def normalize_transform(
    transform: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    把旧工程或不完整变换数据升级为包含 crop 的完整结构。

    旧工程没有 crop 字段时会自动补全，不影响现有图片。
    """
    result = default_transform()
    source = dict(transform or {})

    result["zoom"] = max(
        0.05,
        _finite_float(source.get("zoom"), 1.0),
    )
    result["offset_x"] = _clamp(
        _finite_float(source.get("offset_x"), 0.0),
        -IMAGE_OFFSET_LIMIT,
        IMAGE_OFFSET_LIMIT,
    )
    result["offset_y"] = _clamp(
        _finite_float(source.get("offset_y"), 0.0),
        -IMAGE_OFFSET_LIMIT,
        IMAGE_OFFSET_LIMIT,
    )

    try:
        rotation = int(source.get("rotation", 0))
    except (TypeError, ValueError):
        rotation = 0

    result["rotation"] = rotation % 360
    result["flip_h"] = bool(source.get("flip_h", False))
    result["flip_v"] = bool(source.get("flip_v", False))
    result["crop"] = normalize_crop(source.get("crop"))

    return result


def upgrade_transform_map(
    transforms: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """
    批量升级工程中的 image_transforms。

    输入和输出均可直接 JSON 序列化。
    """
    return {
        str(path): normalize_transform(transform)
        for path, transform in (transforms or {}).items()
    }


def get_crop_rect(
    crop: Mapping[str, Any] | None,
) -> CropRect:
    normalized = normalize_crop(crop)

    return CropRect(
        normalized["x"],
        normalized["y"],
        normalized["width"],
        normalized["height"],
    )


def crop_is_modified(
    crop: Mapping[str, Any] | None,
) -> bool:
    normalized = normalize_crop(crop)

    return bool(normalized["enabled"]) or any(
        (
            abs(normalized["x"]) > 1e-6,
            abs(normalized["y"]) > 1e-6,
            abs(normalized["width"] - 1.0) > 1e-6,
            abs(normalized["height"] - 1.0) > 1e-6,
        )
    )


def reset_crop(
    transform: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = normalize_transform(transform)
    result["crop"] = default_crop()
    return result


def set_crop_rect(
    transform: Mapping[str, Any] | None,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    enabled: bool = True,
    aspect_mode: str | None = None,
    aspect_ratio: float | None = None,
) -> dict[str, Any]:
    """在图片变换中写入新的非破坏裁切矩形。"""
    result = normalize_transform(transform)

    current_crop = dict(result["crop"])
    current_crop.update(
        {
            "enabled": enabled,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
    )

    if aspect_mode is not None:
        current_crop["aspect_mode"] = aspect_mode

    if aspect_ratio is not None:
        current_crop["aspect_ratio"] = aspect_ratio

    result["crop"] = normalize_crop(current_crop)
    return result


def translate_crop(
    crop: Mapping[str, Any] | None,
    dx: float,
    dy: float,
) -> dict[str, Any]:
    """移动裁切框，dx/dy 同样使用归一化比例。"""
    normalized = normalize_crop(crop)
    rect = get_crop_rect(normalized)

    normalized["x"] = _clamp(
        rect.x + _finite_float(dx, 0.0),
        0.0,
        1.0 - rect.width,
    )
    normalized["y"] = _clamp(
        rect.y + _finite_float(dy, 0.0),
        0.0,
        1.0 - rect.height,
    )
    normalized["enabled"] = True

    return normalize_crop(normalized)


def resize_crop(
    crop: Mapping[str, Any] | None,
    *,
    left: float = 0.0,
    top: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
    minimum_size: float = CROP_MIN_SIZE,
) -> dict[str, Any]:
    """
    调整裁切框四边。

    参数为相对原图尺寸的增量：
        left > 0  表示左边向右收缩
        right < 0 表示右边向左收缩
    """
    normalized = normalize_crop(
        crop,
        minimum_size=minimum_size,
    )
    rect = get_crop_rect(normalized)

    new_left = rect.left + _finite_float(left, 0.0)
    new_top = rect.top + _finite_float(top, 0.0)
    new_right = rect.right + _finite_float(right, 0.0)
    new_bottom = rect.bottom + _finite_float(bottom, 0.0)

    minimum_size = _clamp(
        _finite_float(minimum_size, CROP_MIN_SIZE),
        0.001,
        1.0,
    )

    new_left = _clamp(
        new_left,
        0.0,
        new_right - minimum_size,
    )
    new_top = _clamp(
        new_top,
        0.0,
        new_bottom - minimum_size,
    )
    new_right = _clamp(
        new_right,
        new_left + minimum_size,
        1.0,
    )
    new_bottom = _clamp(
        new_bottom,
        new_top + minimum_size,
        1.0,
    )

    normalized.update(
        {
            "enabled": True,
            "x": new_left,
            "y": new_top,
            "width": new_right - new_left,
            "height": new_bottom - new_top,
        }
    )

    return normalize_crop(
        normalized,
        minimum_size=minimum_size,
    )


def crop_rect_to_pixels(
    crop: Mapping[str, Any] | None,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """
    将归一化裁切矩形转换为像素坐标：
        (x, y, width, height)
    """
    width_px = max(1, int(image_width))
    height_px = max(1, int(image_height))
    rect = get_crop_rect(crop)

    x = int(round(rect.x * width_px))
    y = int(round(rect.y * height_px))
    width = max(1, int(round(rect.width * width_px)))
    height = max(1, int(round(rect.height * height_px)))

    if x + width > width_px:
        width = max(1, width_px - x)

    if y + height > height_px:
        height = max(1, height_px - y)

    return x, y, width, height


def fit_crop_to_aspect(
    crop: Mapping[str, Any] | None,
    aspect_ratio: float,
) -> dict[str, Any]:
    """
    在现有裁切框中心内，生成指定宽高比的最大裁切框。
    """
    ratio = _finite_float(aspect_ratio, 0.0)

    if ratio <= 0.0:
        return normalize_crop(crop)

    normalized = normalize_crop(crop)
    rect = get_crop_rect(normalized)
    current_ratio = rect.width / max(rect.height, 1e-9)

    if current_ratio > ratio:
        new_height = rect.height
        new_width = new_height * ratio
    else:
        new_width = rect.width
        new_height = new_width / ratio

    x = rect.center_x - new_width / 2.0
    y = rect.center_y - new_height / 2.0

    normalized.update(
        {
            "enabled": True,
            "x": x,
            "y": y,
            "width": new_width,
            "height": new_height,
            "aspect_mode": "custom",
            "aspect_ratio": ratio,
        }
    )

    return normalize_crop(normalized)


def apply_crop_to_transform_in_place(
    transform: MutableMapping[str, Any],
    crop: Mapping[str, Any] | None,
) -> MutableMapping[str, Any]:
    """
    给需要保持原字典引用的调用方使用。
    """
    normalized = normalize_transform(transform)
    normalized["crop"] = normalize_crop(crop)

    transform.clear()
    transform.update(normalized)
    return transform


def self_test() -> None:
    """轻量自检，不读取或修改任何图片。"""
    upgraded = normalize_transform(
        {
            "zoom": 1.2,
            "rotation": 450,
        }
    )

    assert upgraded["rotation"] == 90
    assert upgraded["crop"]["width"] == 1.0

    cropped = set_crop_rect(
        upgraded,
        x=0.1,
        y=0.2,
        width=0.7,
        height=0.6,
    )

    assert cropped["crop"]["enabled"] is True
    assert crop_rect_to_pixels(
        cropped["crop"],
        1000,
        800,
    ) == (100, 160, 700, 480)

    moved = translate_crop(
        cropped["crop"],
        1.0,
        1.0,
    )

    assert moved["x"] <= 1.0 - moved["width"]
    assert moved["y"] <= 1.0 - moved["height"]

    restored = reset_crop(cropped)
    assert crop_is_modified(restored["crop"]) is False


if __name__ == "__main__":
    self_test()
    print("UI-05-30 crop core self-test: OK")
