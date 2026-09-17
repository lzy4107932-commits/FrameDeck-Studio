from __future__ import annotations

import json
from typing import Any


INTERNAL_IMAGE_ROWS_MIME = "application/x-framedeck-current-page-drag-v2"


def normalize_drag_rows(values: Any) -> list[int]:
    try:
        candidates = list(values or [])
    except TypeError:
        return []

    rows = set()
    for value in candidates:
        try:
            row = int(value)
        except (TypeError, ValueError):
            continue
        if row >= 0:
            rows.add(row)
    return sorted(rows)


def encode_drag_rows(values: Any) -> bytes:
    return json.dumps(
        normalize_drag_rows(values),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_drag_rows(payload: Any) -> list[int]:
    try:
        raw = bytes(payload).decode("utf-8", errors="strict")
        return normalize_drag_rows(json.loads(raw))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return []


def rows_from_mime(mime: Any) -> list[int]:
    if mime is None:
        return []
    try:
        if not mime.hasFormat(INTERNAL_IMAGE_ROWS_MIME):
            return []
        return decode_drag_rows(mime.data(INTERNAL_IMAGE_ROWS_MIME))
    except (AttributeError, RuntimeError):
        return []
