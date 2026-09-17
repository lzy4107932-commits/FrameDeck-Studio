
"""
FrameDeck Studio
UI-05-42A - 分组分页核心

安装位置:
    core/group_layout.py

核心原则:
- continuous: 所有图片连续向前补满
- grouped: 每个分组独立分页，组尾允许空缺，不跨组补位
- 分组边界独立于旧 manual page breaks
- 预留全局/分组/单页标题数据与样式继承结构
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import re
import uuid


PAGINATION_CONTINUOUS = "continuous"
PAGINATION_GROUPED = "grouped"

VALID_PAGINATION_MODES = frozenset(
    {
        PAGINATION_CONTINUOUS,
        PAGINATION_GROUPED,
    }
)


def normalize_pagination_mode(value: Any) -> str:
    value = str(value or "").strip().lower()

    if value in VALID_PAGINATION_MODES:
        return value

    return PAGINATION_CONTINUOUS


def _new_group_id() -> str:
    return "group_" + uuid.uuid4().hex[:12]


def normalize_groups(
    groups: Any,
    image_count: int,
) -> list[dict[str, Any]]:
    image_count = max(0, int(image_count))

    if image_count <= 0:
        return []

    candidates = []

    for item in list(groups or []):
        if not isinstance(item, dict):
            continue

        try:
            start = int(item.get("start", 0))
        except (TypeError, ValueError):
            continue

        if not (0 <= start < image_count):
            continue

        candidates.append(
            {
                "id": str(item.get("id") or _new_group_id()),
                "name": str(item.get("name") or ""),
                "start": start,
            }
        )

    if not any(item["start"] == 0 for item in candidates):
        candidates.append(
            {
                "id": _new_group_id(),
                "name": "",
                "start": 0,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["start"],
            item["id"],
        )
    )

    result = []
    used_starts = set()
    used_ids = set()

    for item in candidates:
        start = int(item["start"])

        if start in used_starts:
            continue

        group_id = str(item["id"])

        if group_id in used_ids:
            group_id = _new_group_id()

        used_starts.add(start)
        used_ids.add(group_id)

        result.append(
            {
                "id": group_id,
                "name": str(item.get("name") or ""),
                "start": start,
            }
        )

    for index, item in enumerate(result, start=1):
        if not item["name"].strip():
            item["name"] = f"分组 {index:02d}"

    return result


def group_breaks(groups: Any, image_count: int) -> list[int]:
    return [
        int(item["start"])
        for item in normalize_groups(groups, image_count)
        if int(item["start"]) > 0
    ]


def effective_page_breaks(
    manual_breaks: Any,
    groups: Any,
    mode: Any,
    image_count: int,
) -> list[int]:
    image_count = max(0, int(image_count))

    breaks = {
        int(value)
        for value in list(manual_breaks or [])
        if 0 < int(value) < image_count
    }

    if normalize_pagination_mode(mode) == PAGINATION_GROUPED:
        breaks.update(
            group_breaks(groups, image_count)
        )

    return sorted(breaks)


def compute_page_ranges(
    image_count: int,
    capacity: int,
    breaks: Any = None,
) -> list[tuple[int, int]]:
    image_count = max(0, int(image_count))
    capacity = max(1, int(capacity))

    if image_count <= 0:
        return [(0, 0)]

    boundaries = [0]
    boundaries.extend(
        sorted(
            {
                int(value)
                for value in list(breaks or [])
                if 0 < int(value) < image_count
            }
        )
    )
    boundaries.append(image_count)

    ranges = []

    for start, end in zip(
        boundaries[:-1],
        boundaries[1:],
    ):
        cursor = start

        while cursor < end:
            page_end = min(cursor + capacity, end)
            ranges.append((cursor, page_end))
            cursor = page_end

    return ranges or [(0, 0)]


def group_for_index(
    groups: Any,
    image_index: int,
    image_count: int,
) -> dict[str, Any] | None:
    normalized = normalize_groups(groups, image_count)

    if not normalized:
        return None

    image_index = max(
        0,
        min(
            int(image_index),
            max(0, int(image_count) - 1),
        ),
    )

    current = normalized[0]

    for item in normalized:
        if int(item["start"]) <= image_index:
            current = item
        else:
            break

    return deepcopy(current)


def shift_groups_for_insert(
    groups: Any,
    insert_index: int,
    count: int,
    image_count_before: int,
    *,
    boundary_belongs_to_previous: bool = False,
    create_new_group: bool = False,
    new_group_name: str = "",
) -> list[dict[str, Any]]:
    image_count_before = max(0, int(image_count_before))
    insert_index = max(
        0,
        min(int(insert_index), image_count_before),
    )
    count = max(0, int(count))

    if count <= 0:
        return normalize_groups(groups, image_count_before)

    normalized = normalize_groups(
        groups,
        image_count_before,
    )

    shifted = []

    for source in normalized:
        item = dict(source)
        start = int(item["start"])

        if (
            start > insert_index
            or (
                boundary_belongs_to_previous
                and start == insert_index
                and start > 0
            )
        ):
            start += count

        item["start"] = start
        shifted.append(item)

    image_count_after = image_count_before + count

    if create_new_group:
        if image_count_before <= 0:
            shifted = [
                {
                    "id": _new_group_id(),
                    "name": (
                        str(new_group_name).strip()
                        or "分组 01"
                    ),
                    "start": 0,
                }
            ]
        elif (
            0 < insert_index < image_count_after
            and not any(
                int(item["start"]) == insert_index
                for item in shifted
            )
        ):
            shifted.append(
                {
                    "id": _new_group_id(),
                    "name": str(new_group_name or "").strip(),
                    "start": insert_index,
                }
            )

    return normalize_groups(
        shifted,
        image_count_after,
    )


def shift_groups_for_delete(
    groups: Any,
    deleted_indices: Any,
    image_count_before: int,
) -> list[dict[str, Any]]:
    image_count_before = max(0, int(image_count_before))

    deleted = sorted(
        {
            int(value)
            for value in list(deleted_indices or [])
            if 0 <= int(value) < image_count_before
        }
    )

    if not deleted:
        return normalize_groups(
            groups,
            image_count_before,
        )

    image_count_after = max(
        0,
        image_count_before - len(deleted),
    )

    if image_count_after <= 0:
        return []

    normalized = normalize_groups(
        groups,
        image_count_before,
    )
    shifted = []

    for source in normalized:
        item = dict(source)
        old_start = int(item["start"])

        shift = sum(
            1
            for index in deleted
            if index < old_start
        )

        item["start"] = max(
            0,
            old_start - shift,
        )
        shifted.append(item)

    return normalize_groups(
        shifted,
        image_count_after,
    )


def default_title_style() -> dict[str, Any]:
    return {
        "font_family": "Microsoft YaHei",
        "font_size": 20.0,
        "color": "#111827",
        "bold": True,
        "alignment": "center",
        "top_spacing_cm": 0.0,
        "region_height_cm": 0.9,
        "auto_height": False,
    }


def minimum_title_region_height_cm(
    font_size: Any,
    bold: bool = True,
) -> float:
    try:
        points = max(6.0, min(96.0, float(font_size)))
    except (TypeError, ValueError):
        points = 20.0
    font_height_cm = points * 2.54 / 72.0
    line_factor = 1.30 if bold else 1.24
    return max(0.35, font_height_cm * line_factor + 0.16)


def resolve_title_vertical_geometry(
    style: Any,
    *,
    enabled: bool,
    has_content: bool,
) -> dict[str, float | bool]:
    """Resolve a title band that cannot overlap the image grid."""
    normalized = normalize_title_style(style)
    requested_height = float(normalized["region_height_cm"])
    top_spacing = float(normalized["top_spacing_cm"])
    # Reserve line leading plus symmetric breathing room so glyph
    # ascenders/descenders never enter the image row.
    safe_height = minimum_title_region_height_cm(
        normalized["font_size"],
        bool(normalized.get("bold")),
    )

    active = bool(enabled and has_content)
    effective_height = max(requested_height, safe_height) if active else 0.0
    effective_spacing = max(0.0, top_spacing) if active else 0.0
    return {
        "effective_height_cm": effective_height,
        "effective_top_spacing_cm": effective_spacing,
        "minimum_height_cm": safe_height,
        "auto_expanded": bool(active and effective_height > requested_height + 1e-9),
    }


def _normalize_title_style_value(
    key: str,
    value: Any,
) -> Any:
    if key == "font_family":
        family = str(value or "Microsoft YaHei").strip()
        return family or "Microsoft YaHei"

    if key == "font_size":
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 20.0
        return max(6.0, min(96.0, number))

    if key == "color":
        color = str(value or "#111827").strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            color = "#111827"
        return color.upper()

    if key == "bold":
        return bool(value)

    if key == "alignment":
        alignment = str(value or "center").strip().lower()
        if alignment not in {"left", "center", "right"}:
            alignment = "center"
        return alignment

    if key == "top_spacing_cm":
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        return max(0.0, min(5.0, number))

    if key == "region_height_cm":
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.9
        return max(0.35, min(5.0, number))

    if key == "auto_height":
        return bool(value)

    return value


def normalize_title_style(
    value: Any,
    base: Any = None,
) -> dict[str, Any]:
    result = default_title_style()

    if isinstance(base, dict):
        for key, item in base.items():
            if key in result:
                result[key] = _normalize_title_style_value(
                    key,
                    item,
                )

    if isinstance(value, dict):
        for key, item in value.items():
            if key in result:
                result[key] = _normalize_title_style_value(
                    key,
                    item,
                )

    return result


def normalize_title_style_override(
    value: Any,
) -> dict[str, Any]:
    """
    只规范化明确存在的字段，不补默认值。
    这样分组/单页只覆盖用户真正修改过的属性，
    其它属性会继续动态继承上一级。
    """
    if not isinstance(value, dict):
        return {}

    valid_keys = set(
        default_title_style()
    )
    result = {}

    for key, item in value.items():
        if key not in valid_keys:
            continue

        result[key] = _normalize_title_style_value(
            key,
            item,
        )

    return result


def default_title_system() -> dict[str, Any]:
    return {
        "version": 2,
        "content_mode": "global",
        "style_mode": "hierarchical",
        "global_title": "",
        "global_subtitle": "",
        "group_titles": {},
        "page_titles": {},
        "global_style": default_title_style(),
        "group_styles": {},
        "page_styles": {},
    }


def _normalize_title_record(
    value: Any,
) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "title": str(value.get("title", "") or ""),
            "subtitle": str(value.get("subtitle", "") or ""),
        }

    if value is None:
        return {"title": "", "subtitle": ""}

    return {"title": str(value), "subtitle": ""}


def normalize_title_system(
    value: Any,
    *,
    global_title: str | None = None,
    global_subtitle: str | None = None,
    title_height: float | None = None,
    title_enabled: bool | None = None,
    group_ids: Any = None,
) -> dict[str, Any]:
    result = default_title_system()

    if isinstance(value, dict):
        incoming = deepcopy(value)

        for key in (
            "content_mode",
            "style_mode",
            "global_title",
            "global_subtitle",
            "group_titles",
            "page_titles",
            "global_style",
            "group_styles",
            "page_styles",
        ):
            if key in incoming:
                result[key] = incoming[key]

    mode = str(
        result.get("content_mode", "global") or "global"
    ).strip().lower()
    if mode not in {"none", "global", "group", "page"}:
        mode = "global"
    if mode == "none" and title_enabled is True:
        mode = "global"

    result["content_mode"] = mode
    result["style_mode"] = "hierarchical"

    if global_title is not None:
        result["global_title"] = str(global_title)
    else:
        result["global_title"] = str(
            result.get("global_title", "") or ""
        )

    if global_subtitle is not None:
        result["global_subtitle"] = str(global_subtitle)
    else:
        result["global_subtitle"] = str(
            result.get("global_subtitle", "") or ""
        )

    global_style = normalize_title_style(
        result.get("global_style", {})
    )
    if title_height is not None:
        global_style["region_height_cm"] = (
            _normalize_title_style_value(
                "region_height_cm",
                title_height,
            )
        )
    result["global_style"] = global_style

    result["group_titles"] = {
        str(key): _normalize_title_record(record)
        for key, record in dict(
            result.get("group_titles", {}) or {}
        ).items()
    }
    result["page_titles"] = {
        str(key): _normalize_title_record(record)
        for key, record in dict(
            result.get("page_titles", {}) or {}
        ).items()
    }

    result["group_styles"] = {
        str(key): normalize_title_style_override(style)
        for key, style in dict(
            result.get("group_styles", {}) or {}
        ).items()
    }
    result["page_styles"] = {
        str(key): normalize_title_style_override(style)
        for key, style in dict(
            result.get("page_styles", {}) or {}
        ).items()
    }

    valid_group_ids = {
        str(group_id)
        for group_id in list(group_ids or [])
        if str(group_id)
    }
    if valid_group_ids:
        result["group_titles"] = {
            key: value
            for key, value in result["group_titles"].items()
            if key in valid_group_ids
        }
        result["group_styles"] = {
            key: value
            for key, value in result["group_styles"].items()
            if key in valid_group_ids
        }

    result["version"] = 2
    return result


def title_record_for_scope(
    title_system: Any,
    scope: str,
    *,
    group_id: str = "",
    page_index: int = 0,
) -> dict[str, str]:
    system = normalize_title_system(title_system)
    scope = str(scope or "global").strip().lower()

    if scope == "group":
        return _normalize_title_record(
            system.get("group_titles", {}).get(
                str(group_id),
                {},
            )
        )

    if scope == "page":
        return _normalize_title_record(
            system.get("page_titles", {}).get(
                str(int(page_index)),
                {},
            )
        )

    return {
        "title": str(system.get("global_title", "") or ""),
        "subtitle": str(
            system.get("global_subtitle", "") or ""
        ),
    }


def inherited_title_record(
    title_system: Any,
    *,
    group_id: str = "",
    page_index: int = 0,
    exclude_scope: str = "",
) -> dict[str, str]:
    system = normalize_title_system(title_system)
    exclude_scope = str(exclude_scope or "").lower()

    global_record = title_record_for_scope(
        system,
        "global",
    )

    if exclude_scope == "group" or not group_id:
        return global_record

    group_record = title_record_for_scope(
        system,
        "group",
        group_id=group_id,
    )

    return {
        "title": group_record["title"] or global_record["title"],
        "subtitle": (
            group_record["subtitle"]
            or global_record["subtitle"]
        ),
    }


def resolve_title_content(
    title_system: Any,
    *,
    group_id: str = "",
    page_index: int = 0,
) -> dict[str, str]:
    system = normalize_title_system(title_system)
    mode = str(
        system.get("content_mode", "global")
    ).lower()

    global_record = title_record_for_scope(
        system,
        "global",
    )

    if mode == "none":
        return {"title": "", "subtitle": ""}

    if mode == "global":
        return global_record

    group_record = title_record_for_scope(
        system,
        "group",
        group_id=group_id,
    )

    if mode == "group":
        return {
            "title": group_record["title"] or global_record["title"],
            "subtitle": (
                group_record["subtitle"]
                or global_record["subtitle"]
            ),
        }

    page_record = title_record_for_scope(
        system,
        "page",
        page_index=page_index,
    )

    return {
        "title": (
            page_record["title"]
            or group_record["title"]
            or global_record["title"]
        ),
        "subtitle": (
            page_record["subtitle"]
            or group_record["subtitle"]
            or global_record["subtitle"]
        ),
    }


def resolve_title_style(
    title_system: Any,
    *,
    group_id: str = "",
    page_index: int = 0,
) -> dict[str, Any]:
    system = normalize_title_system(title_system)
    style = normalize_title_style(
        system.get("global_style", {})
    )

    group_override = normalize_title_style_override(
        system.get("group_styles", {}).get(
            str(group_id),
            {},
        )
    )
    style = normalize_title_style(
        group_override,
        style,
    )

    page_override = normalize_title_style_override(
        system.get("page_styles", {}).get(
            str(int(page_index)),
            {},
        )
    )
    style = normalize_title_style(
        page_override,
        style,
    )

    return style


def resolve_title_context(
    title_system: Any,
    *,
    group_id: str = "",
    page_index: int = 0,
) -> dict[str, Any]:
    content = resolve_title_content(
        title_system,
        group_id=group_id,
        page_index=page_index,
    )

    return {
        **content,
        "style": resolve_title_style(
            title_system,
            group_id=group_id,
            page_index=page_index,
        ),
        "group_id": str(group_id or ""),
        "page_index": int(page_index),
    }
