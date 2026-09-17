from __future__ import annotations

import json
from pathlib import Path

from core.app_paths import recent_file


PROJECT_VERSION = 12


def normalize_project_path(path: str) -> str:
    path_obj = Path(path)
    name = path_obj.name.lower()
    if not name.endswith(".fds"):
        path_obj = path_obj.with_suffix(".fds")
    return str(path_obj)


def save_project_file(path: str, data: dict) -> str:
    output = Path(normalize_project_path(path))
    payload = {
        "format": "FrameDeck Studio Project",
        "version": PROJECT_VERSION,
        **data,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    add_recent_project(str(output))
    return str(output)


def load_project_file(path: str) -> dict:
    project_path = Path(path)
    data = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("工程文件格式无效。")
    add_recent_project(str(project_path))
    return data


def load_recent_projects() -> list[str]:
    try:
        data = json.loads(recent_file().read_text(encoding="utf-8"))
        items = data.get("projects", [])
        return [p for p in items if Path(p).exists()]
    except Exception:
        return []


def add_recent_project(path: str) -> None:
    items = load_recent_projects()
    path = str(Path(path))
    items = [p for p in items if p != path]
    items.insert(0, path)
    items = items[:10]
    recent_file().write_text(
        json.dumps({"projects": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
