"""
FrameDeck Studio Template System T-01

安装：
    将本文件改名为 template_system.py
    放到 core/template_system.py

T-01 功能：
- 模板 JSON 规范与校验
- 内置模板发现、分类和读取
- 用户自由网格模板保存
- 保存自定义 layout.frames，供 T-02 渲染引擎使用
"""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TEMPLATE_SCHEMA = "framedeck.template"
TEMPLATE_SCHEMA_VERSION = 1

CATEGORY_ORDER = (
    "ai_character",
    "film_visual",
)

CATEGORY_LABELS = {
    "ai_character": "AI角色设计",
    "film_visual": "电影视觉开发",
    "user": "用户模板",
}


class TemplateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateSummary:
    template_id: str
    name: str
    short_name: str
    category: str
    category_label: str
    description: str
    path: Path
    image_slot_count: int
    page_size: str


def application_root() -> Path:
    frozen_root = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if frozen_root:
        return Path(frozen_root)

    return Path(__file__).resolve().parents[1]


def builtin_templates_root() -> Path:
    return application_root() / "templates"


def _mapping(
    value: Any,
    field: str,
) -> dict:
    if not isinstance(value, dict):
        raise TemplateValidationError(
            f"{field} 必须是对象。"
        )

    return value


def _text(
    value: Any,
    field: str,
) -> str:
    result = str(value or "").strip()

    if not result:
        raise TemplateValidationError(
            f"{field} 不能为空。"
        )

    return result


def _float(
    value: Any,
    field: str,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise TemplateValidationError(
            f"{field} 必须是数字。"
        ) from error


def _rect(
    value: Any,
    field: str,
) -> dict:
    value = _mapping(value, field)

    result = {
        key: _float(
            value.get(key),
            f"{field}.{key}",
        )
        for key in ("x", "y", "w", "h")
    }

    for key, number in result.items():
        if number < 0.0 or number > 1.0:
            raise TemplateValidationError(
                f"{field}.{key} 必须位于 0～1。"
            )

    if result["w"] <= 0 or result["h"] <= 0:
        raise TemplateValidationError(
            f"{field} 的宽高必须大于 0。"
        )

    if result["x"] + result["w"] > 1.000001:
        raise TemplateValidationError(
            f"{field} 超出页面右边界。"
        )

    if result["y"] + result["h"] > 1.000001:
        raise TemplateValidationError(
            f"{field} 超出页面下边界。"
        )

    return result


def validate_template_document(
    document: Any,
) -> dict:
    document = copy.deepcopy(
        _mapping(
            document,
            "template",
        )
    )

    if (
        _text(
            document.get("schema"),
            "schema",
        )
        != TEMPLATE_SCHEMA
    ):
        raise TemplateValidationError(
            "这不是 FrameDeck 模板文件。"
        )

    try:
        schema_version = int(
            document.get(
                "schema_version",
                0,
            )
        )
    except (TypeError, ValueError) as error:
        raise TemplateValidationError(
            "schema_version 必须是整数。"
        ) from error

    if schema_version != TEMPLATE_SCHEMA_VERSION:
        raise TemplateValidationError(
            (
                "不支持的模板版本："
                f"{schema_version}"
            )
        )

    template_id = _text(
        document.get("id"),
        "id",
    )
    name = _text(
        document.get("name"),
        "name",
    )
    short_name = str(
        document.get("short_name")
        or name
    ).strip()
    category = _text(
        document.get("category"),
        "category",
    )

    fallback = _mapping(
        document.get(
            "fallback_settings"
        ),
        "fallback_settings",
    )
    fallback["rows"] = max(
        1,
        int(fallback.get("rows", 1)),
    )
    fallback["cols"] = max(
        1,
        int(fallback.get("cols", 1)),
    )
    fallback.setdefault(
        "page_size",
        "16:9",
    )
    fallback.setdefault(
        "image_mode",
        "裁剪填充",
    )

    layout = _mapping(
        document.get("layout"),
        "layout",
    )
    mode = str(
        layout.get("mode")
        or "frames"
    ).strip()

    if mode not in {"frames", "grid"}:
        raise TemplateValidationError(
            "layout.mode 只支持 frames 或 grid。"
        )

    frames = layout.get("frames", [])

    if not isinstance(frames, list):
        raise TemplateValidationError(
            "layout.frames 必须是数组。"
        )

    normalized_frames = []
    frame_ids = set()

    for index, frame in enumerate(frames):
        frame = _mapping(
            frame,
            f"layout.frames[{index}]",
        )
        frame_id = _text(
            frame.get("id"),
            f"layout.frames[{index}].id",
        )

        if frame_id in frame_ids:
            raise TemplateValidationError(
                f"框架 ID 重复：{frame_id}"
            )

        frame_ids.add(frame_id)

        frame_type = str(
            frame.get("type")
            or "image"
        ).strip()

        if frame_type not in {
            "image",
            "text",
            "color",
        }:
            raise TemplateValidationError(
                (
                    f"layout.frames[{index}].type "
                    "只支持 image、text、color。"
                )
            )

        item = dict(frame)
        item["id"] = frame_id
        item["type"] = frame_type
        item["rect"] = _rect(
            frame.get("rect"),
            f"layout.frames[{index}].rect",
        )
        normalized_frames.append(item)

    image_slots = [
        frame
        for frame in normalized_frames
        if frame["type"] == "image"
    ]

    if not image_slots:
        raise TemplateValidationError(
            "模板至少需要一个图片框。"
        )

    layout["mode"] = mode
    layout["coordinate_space"] = (
        "normalized_slide"
    )
    layout["frames"] = normalized_frames

    document.update(
        {
            "schema": TEMPLATE_SCHEMA,
            "schema_version": (
                TEMPLATE_SCHEMA_VERSION
            ),
            "id": template_id,
            "name": name,
            "short_name": short_name,
            "category": category,
            "description": str(
                document.get("description")
                or ""
            ).strip(),
            "fallback_settings": fallback,
            "layout": layout,
        }
    )

    document.setdefault("style", {})
    document.setdefault("usage", {})
    document.setdefault("metadata", {})

    return document


def load_template_file(
    path: str | Path,
) -> dict:
    path = Path(path)

    return validate_template_document(
        json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    )


def discover_builtin_templates(
    root: str | Path | None = None,
) -> list[TemplateSummary]:
    root_path = (
        Path(root)
        if root is not None
        else builtin_templates_root()
    )

    if not root_path.is_dir():
        return []

    items = []

    for path in sorted(
        root_path.rglob("*.json")
    ):
        try:
            document = load_template_file(
                path
            )
        except Exception:
            continue

        image_slot_count = sum(
            1
            for frame in document[
                "layout"
            ]["frames"]
            if frame["type"] == "image"
        )
        category = document["category"]

        items.append(
            TemplateSummary(
                template_id=document["id"],
                name=document["name"],
                short_name=document[
                    "short_name"
                ],
                category=category,
                category_label=(
                    CATEGORY_LABELS.get(
                        category,
                        category,
                    )
                ),
                description=document[
                    "description"
                ],
                path=path,
                image_slot_count=(
                    image_slot_count
                ),
                page_size=str(
                    document[
                        "fallback_settings"
                    ].get(
                        "page_size",
                        "16:9",
                    )
                ),
            )
        )

    rank = {
        category: index
        for index, category
        in enumerate(CATEGORY_ORDER)
    }

    items.sort(
        key=lambda item: (
            rank.get(
                item.category,
                999,
            ),
            item.name,
        )
    )

    return items


def template_catalog(
    root: str | Path | None = None,
) -> dict[str, list[TemplateSummary]]:
    result = {}

    for summary in discover_builtin_templates(
        root
    ):
        result.setdefault(
            summary.category,
            [],
        ).append(summary)

    return result


def load_builtin_template(
    template_id: str,
    root: str | Path | None = None,
) -> dict:
    template_id = str(
        template_id
    ).strip()

    for summary in discover_builtin_templates(
        root
    ):
        if summary.template_id == template_id:
            return load_template_file(
                summary.path
            )

    raise FileNotFoundError(
        f"找不到内置模板：{template_id}"
    )


def template_fallback_settings(
    document: dict,
) -> dict:
    document = validate_template_document(
        document
    )
    return copy.deepcopy(
        document["fallback_settings"]
    )


def create_user_template(
    *,
    name: str,
    settings: dict,
    description: str = "",
) -> dict:
    settings = copy.deepcopy(
        dict(settings or {})
    )
    settings.pop(
        "layout_template",
        None,
    )

    rows = max(
        1,
        int(settings.get("rows", 2)),
    )
    cols = max(
        1,
        int(settings.get("cols", 6)),
    )

    gap = 0.012
    frame_w = (
        1.0 - gap * (cols + 1)
    ) / cols
    frame_h = (
        1.0 - gap * (rows + 1)
    ) / rows
    frames = []

    for row in range(rows):
        for col in range(cols):
            frames.append(
                {
                    "id": (
                        f"image_{row + 1}_"
                        f"{col + 1}"
                    ),
                    "type": "image",
                    "role": "grid",
                    "label": (
                        f"图片 "
                        f"{row * cols + col + 1}"
                    ),
                    "rect": {
                        "x": (
                            gap
                            + col
                            * (frame_w + gap)
                        ),
                        "y": (
                            gap
                            + row
                            * (frame_h + gap)
                        ),
                        "w": frame_w,
                        "h": frame_h,
                    },
                }
            )

    return validate_template_document(
        {
            "schema": TEMPLATE_SCHEMA,
            "schema_version": 1,
            "id": "user.grid.template",
            "name": str(
                name or "用户模板"
            ),
            "short_name": str(
                name or "用户模板"
            )[:12],
            "category": "user",
            "description": str(
                description
                or "用户保存的自由网格模板"
            ),
            "fallback_settings": settings,
            "layout": {
                "mode": "grid",
                "coordinate_space": (
                    "normalized_slide"
                ),
                "frames": frames,
            },
            "style": {
                "background": "theme",
                "accent": "theme",
            },
            "usage": {
                "recommended_images": (
                    rows * cols
                ),
            },
            "metadata": {
                "created_by": (
                    "FrameDeck Studio"
                ),
            },
        }
    )
