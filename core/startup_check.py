from __future__ import annotations

from pathlib import Path

from core.app_paths import bundled_root


REQUIRED_RESOURCES = [
    "resources/icon.ico",
    "resources/icon.png",
]


def run_startup_checks() -> list[str]:
    warnings = []
    root = bundled_root()

    for relative in REQUIRED_RESOURCES:
        if not (root / relative).exists():
            warnings.append(f"缺少资源：{relative}")

    try:
        test_dir = Path.home() / ".framedeck_write_test"
        test_dir.write_text("ok", encoding="utf-8")
        test_dir.unlink(missing_ok=True)
    except Exception as exc:
        warnings.append(f"用户目录不可写：{exc}")

    return warnings
