# -*- coding: utf-8 -*-
"""
FrameDeck Studio
UI-05-51A - Packaging Preflight & Build Runner

目标：
1. 发布前检查 Python / PyInstaller / 关键依赖 / 项目结构。
2. 检查现有 build_exe.bat / build_portable_exe.bat / build_setup_installer.bat。
3. 构建前自动归档旧 build/dist（不直接丢失旧产物）。
4. 可选择：
   --check             仅检查（默认）
   --build-exe         调用 build_exe.bat
   --build-portable    调用 build_portable_exe.bat
   --build-installer   调用 build_setup_installer.bat
5. 保存完整构建日志到 build_logs。
6. 自动扫描新生成的 EXE / 安装包并写入 PACKAGING_REPORT.txt。
7. 可选 --smoke-exe 对新 EXE 做 20 秒窗口级启动冒烟测试。

用法：
    python FrameDeck_UI05_51A_packaging_preflight.py

    python FrameDeck_UI05_51A_packaging_preflight.py --build-exe

    python FrameDeck_UI05_51A_packaging_preflight.py --build-portable --smoke-exe

    python FrameDeck_UI05_51A_packaging_preflight.py --build-installer

说明：
- 本脚本不会修改 gui/main_window.py 等业务代码。
- 构建前会把旧 build/dist 移到 build_archive/时间戳 下。
- 真正的 PyInstaller 参数仍以你现有 build_*.bat 为准。
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


APP_NAME = "FrameDeck Studio"
STAGE = "UI-05-51A Packaging Preflight"

REQUIRED_FILES = (
    "main.py",
    "gui/main_window.py",
    "gui/slide_thumbnail_bar.py",
    "requirements.txt",
)

BUILD_SCRIPTS = {
    "exe": "build_exe.bat",
    "portable": "build_portable_exe.bat",
    "installer": "build_setup_installer.bat",
}

REQUIRED_MODULES = {
    "PySide6": "PySide6",
    "Pillow": "PIL",
    "python-pptx": "pptx",
    "pillow-heif": "pillow_heif",
}

OPTIONAL_MODULES = {}

ACTIVE_RELEASE_TOOLS = {
    "FrameDeck_UI05_50C_release_regression_check.py",
    "FrameDeck_UI05_51A_packaging_preflight.py",
}

RESOURCE_DIRS = (
    "resources",
    "Template",
)

ICON_CANDIDATES = (
    "resources/app.ico",
    "resources/FrameDeck.ico",
    "resources/icon.ico",
    "app.ico",
    "FrameDeck.ico",
)

STARTUP_ERROR_TITLE_MARKERS = (
    "unhandled exception in script",
    "fatal error detected",
    "failed to execute script",
    "framedeck studio 发生错误",
)


class Report:
    def __init__(self):
        self.lines = []
        self.passed = 0
        self.warned = 0
        self.failed = 0

    def _log(self, level, text):
        line = f"[{level}] {text}"
        self.lines.append(line)
        print(line)

    def ok(self, text):
        self.passed += 1
        self._log("PASS", text)

    def warn(self, text):
        self.warned += 1
        self._log("WARN", text)

    def fail(self, text):
        self.failed += 1
        self._log("FAIL", text)

    def info(self, text):
        self._log("INFO", text)


def parse_args():
    parser = argparse.ArgumentParser(
        description="FrameDeck Studio EXE打包预检/构建工具"
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="项目根目录，默认当前目录",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="仅执行预检（默认）",
    )
    group.add_argument(
        "--build-exe",
        action="store_true",
        help="调用 build_exe.bat",
    )
    group.add_argument(
        "--build-portable",
        action="store_true",
        help="调用 build_portable_exe.bat",
    )
    group.add_argument(
        "--build-installer",
        action="store_true",
        help="调用 build_setup_installer.bat",
    )

    parser.add_argument(
        "--smoke-exe",
        action="store_true",
        help="构建成功后对最新EXE做20秒窗口级启动测试",
    )

    parser.add_argument(
        "--no-archive-old-build",
        action="store_true",
        help="不归档旧build/dist（不推荐）",
    )

    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )


def check_project(root: Path, report: Report):
    report.info("检查项目结构……")

    for rel in REQUIRED_FILES:
        path = root / rel

        if path.is_file():
            report.ok(f"关键文件存在：{rel}")
        else:
            report.fail(f"缺少关键文件：{rel}")

    for rel in RESOURCE_DIRS:
        path = root / rel

        if path.is_dir():
            report.ok(f"资源目录存在：{rel}/")
        else:
            report.warn(f"资源目录不存在：{rel}/")

    if (root / "CURRENT_STABLE_BASELINE.txt").is_file():
        report.ok("CURRENT_STABLE_BASELINE.txt 存在")
    else:
        report.warn("未找到 CURRENT_STABLE_BASELINE.txt")

    if (root / "RELEASE_REGRESSION_REPORT.txt").is_file():
        report.ok("RELEASE_REGRESSION_REPORT.txt 存在")
    else:
        report.warn("未找到 RELEASE_REGRESSION_REPORT.txt")


def check_python(report: Report):
    report.info("检查 Python 环境……")

    report.info(
        f"Python: {sys.version.splitlines()[0]}"
    )
    report.info(
        f"Platform: {platform.platform()}"
    )

    if sys.version_info >= (3, 10):
        report.ok(
            f"Python版本可用于当前开发环境："
            f"{sys.version_info.major}.{sys.version_info.minor}"
        )
    else:
        report.fail("Python版本过低")


def check_modules(report: Report):
    report.info("检查关键依赖……")

    for label, module in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module):
            report.ok(f"关键依赖可用：{label}")
        else:
            report.fail(
                f"缺少关键依赖：{label} ({module})"
            )

    for label, module in OPTIONAL_MODULES.items():
        if importlib.util.find_spec(module):
            report.ok(f"可选依赖可用：{label}")
        else:
            report.warn(
                f"可选依赖未安装：{label}"
            )

    if importlib.util.find_spec("PyInstaller"):
        try:
            import PyInstaller
            version = getattr(
                PyInstaller,
                "__version__",
                "unknown",
            )
            report.ok(
                f"PyInstaller可用：{version}"
            )
        except Exception:
            report.ok("PyInstaller可用")
    else:
        report.fail(
            "未安装 PyInstaller；"
            "请先执行：python -m pip install pyinstaller"
        )


def syntax_check(root: Path, report: Report):
    report.info("检查活动源码语法……")

    targets = [root / "main.py"]

    for folder_name in ("core", "gui"):
        folder = root / folder_name

        if folder.is_dir():
            targets.extend(
                path
                for path in folder.rglob("*.py")
                if "__pycache__" not in path.parts
            )

    errors = []

    for path in sorted(
        set(
            p for p in targets
            if p.is_file()
        )
    ):
        try:
            compile(
                read_text(path),
                str(path),
                "exec",
            )
        except Exception as exc:
            errors.append(
                f"{path.relative_to(root)}: "
                f"{type(exc).__name__}: {exc}"
            )

    if errors:
        for error in errors:
            report.fail(
                "Python语法错误：" + error
            )
    else:
        report.ok(
            f"活动源码语法通过：{len(targets)} 个文件"
        )


def check_build_scripts(
    root: Path,
    report: Report,
):
    report.info("检查现有构建脚本……")

    for label, file_name in BUILD_SCRIPTS.items():
        path = root / file_name

        if path.is_file():
            report.ok(
                f"构建脚本存在：{file_name}"
            )

            text = read_text(path)

            lowered = text.lower()

            if (
                "pyinstaller"
                in lowered
                or ".spec"
                in lowered
                or "python"
                in lowered
                or "iscc"
                in lowered
            ):
                report.ok(
                    f"{file_name} 包含构建命令"
                )
            else:
                report.warn(
                    f"{file_name} 未识别到明显构建命令，"
                    "建议人工检查"
                )

            if label in {"exe", "portable"}:
                if (
                    "python_exe" in lowered
                    and "set \"path=%systemroot%\\system32;" in lowered
                ):
                    report.ok(
                        f"{file_name} 使用隔离的打包 DLL 搜索路径"
                    )
                else:
                    report.fail(
                        f"{file_name} 未隔离 PyInstaller DLL 搜索路径"
                    )
        else:
            report.warn(
                f"构建脚本不存在：{file_name}"
            )


def check_icon(root: Path, report: Report):
    found = []

    for rel in ICON_CANDIDATES:
        path = root / rel

        if path.is_file():
            found.append(rel)

    if found:
        report.ok(
            "发现应用图标：" + ", ".join(found)
        )
    else:
        # 不把图标设为FAIL，因为当前bat可能使用其它名称。
        ico_files = list(
            (root / "resources").glob("*.ico")
        ) if (root / "resources").is_dir() else []

        if ico_files:
            report.ok(
                "resources中发现ICO："
                + ", ".join(
                    path.name
                    for path in ico_files[:6]
                )
            )
        else:
            report.warn(
                "未找到常见 .ico 图标文件；"
                "如打包脚本使用其它路径可忽略"
            )


def check_root_clean(root: Path, report: Report):
    patch_files = [
        path
        for path in root.glob("FrameDeck_UI05_*.py")
        if path.name not in ACTIVE_RELEASE_TOOLS
    ]

    if patch_files:
        report.warn(
            "根目录仍有 UI05 开发脚本："
            + ", ".join(
                p.name
                for p in patch_files[:10]
            )
        )
    else:
        report.ok(
            "根目录无历史 UI05 patch 脚本"
        )

    caches = [
        path
        for path in root.rglob("__pycache__")
        if "development_archive" not in path.parts
    ]

    if caches:
        report.warn(
            f"检测到 {len(caches)} 个 __pycache__；"
            "正式打包前建议清理"
        )
    else:
        report.ok("未发现活动代码缓存目录")


def archive_old_outputs(
    root: Path,
    report: Report,
):
    existing = []

    for name in (
        "build",
        "dist",
    ):
        path = root / name

        if path.exists():
            existing.append(path)

    if not existing:
        report.info(
            "未发现旧 build/dist，无需归档"
        )
        return None

    stamp = dt.datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    archive = (
        root
        / "build_archive"
        / stamp
    )
    archive.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source in existing:
        destination = archive / source.name

        try:
            shutil.move(
                str(source),
                str(destination),
            )
            report.ok(
                f"旧 {source.name}/ 已归档到 "
                f"{destination.relative_to(root)}"
            )
        except Exception as exc:
            report.fail(
                f"归档 {source.name}/ 失败：{exc}"
            )

    return archive


def choose_build(args):
    if args.build_exe:
        return "exe"
    if args.build_portable:
        return "portable"
    if args.build_installer:
        return "installer"

    return None


def run_build(
    root: Path,
    mode: str,
    report: Report,
):
    bat_name = BUILD_SCRIPTS[
        mode
    ]
    bat_path = root / bat_name

    if not bat_path.is_file():
        report.fail(
            f"无法构建：缺少 {bat_name}"
        )
        return False, None

    logs = root / "build_logs"
    logs.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = dt.datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    log_path = (
        logs
        / f"{mode}_{stamp}.log"
    )

    report.info(
        f"开始执行：{bat_name}"
    )
    report.info(
        f"构建日志：{log_path.relative_to(root)}"
    )

    start = time.monotonic()

    try:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                str(bat_path),
            ],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )

        elapsed = time.monotonic() - start

        output = completed.stdout or ""

        log_path.write_text(
            output,
            encoding="utf-8",
        )

        if completed.returncode == 0:
            report.ok(
                f"{bat_name} 执行完成，"
                f"耗时 {elapsed:.1f}s"
            )
            return True, log_path

        report.fail(
            f"{bat_name} 构建失败，"
            f"退出码={completed.returncode}；"
            f"请查看 {log_path.relative_to(root)}"
        )

        return False, log_path

    except Exception as exc:
        report.fail(
            f"执行 {bat_name} 失败：{exc}"
        )
        return False, log_path


def collect_artifacts(
    root: Path,
    report: Report,
):
    candidates = []

    for folder_name in (
        "dist",
        "installer",
    ):
        folder = root / folder_name

        if not folder.exists():
            continue

        for pattern in (
            "*.exe",
            "*.msi",
        ):
            candidates.extend(
                folder.rglob(pattern)
            )

    # 只列存在的文件并按修改时间排序。
    candidates = sorted(
        {
            path.resolve()
            for path in candidates
            if path.is_file()
        },
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        report.warn(
            "未扫描到新的 EXE/MSI 产物"
        )
        return []

    report.ok(
        f"扫描到 {len(candidates)} 个 EXE/MSI 产物"
    )

    for path in candidates[:12]:
        size_mb = (
            path.stat().st_size
            / 1024
            / 1024
        )

        report.info(
            f"产物：{path.relative_to(root)} "
            f"({size_mb:.1f} MB)"
        )

    return candidates


def choose_smoke_exe(
    artifacts,
):
    exe_files = [
        path
        for path in artifacts
        if path.suffix.lower() == ".exe"
        and "unins" not in path.name.lower()
        and "setup" not in path.name.lower()
        and "install" not in path.name.lower()
    ]

    if not exe_files:
        return None

    return exe_files[0]


def visible_window_titles():
    if os.name != "nt":
        return {}

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    windows = {}

    @callback_type
    def collect(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)

        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()

        if title:
            windows[int(hwnd)] = title

        return True

    if not user32.EnumWindows(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())

    return windows


def new_startup_error_windows(before_handles):
    errors = {}

    for hwnd, title in visible_window_titles().items():
        lowered = title.casefold()

        if (
            hwnd not in before_handles
            and any(
                marker in lowered
                for marker in STARTUP_ERROR_TITLE_MARKERS
            )
        ):
            errors[hwnd] = title

    return errors


def stop_smoke_process(process):
    if process is None or process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            [
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        process.terminate()
        process.wait(timeout=4)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def smoke_exe(
    exe: Path,
    report: Report,
    seconds: int = 20,
):
    report.info(
        f"EXE启动冒烟测试：{exe.name}"
    )

    process = None
    before_windows = visible_window_titles()
    main_window_seen_at = None

    try:
        process = subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )

        deadline = time.monotonic() + seconds

        while time.monotonic() < deadline:
            code = process.poll()

            error_windows = new_startup_error_windows(
                before_windows
            )

            if error_windows:
                titles = ", ".join(
                    sorted(set(error_windows.values()))
                )
                report.fail(
                    f"{exe.name} 显示启动错误窗口：{titles}"
                )
                return

            current_windows = visible_window_titles()
            new_titles = (
                title
                for hwnd, title in current_windows.items()
                if hwnd not in before_windows
            )

            if any(
                "framedeck studio" in title.casefold()
                for title in new_titles
            ):
                if main_window_seen_at is None:
                    main_window_seen_at = time.monotonic()

            if code is not None:
                if code == 0:
                    report.warn(
                        f"{exe.name} 在 {seconds}s 内正常退出；"
                        "请确认是否为预期"
                    )
                else:
                    report.fail(
                        f"{exe.name} 启动后异常退出，"
                        f"退出码={code}"
                    )

                return

            if (
                main_window_seen_at is not None
                and time.monotonic() - main_window_seen_at >= 3
            ):
                report.ok(
                    f"{exe.name} 主窗口持续显示3秒，"
                    "未发现启动错误窗口"
                )
                return

            time.sleep(0.25)

        if os.name == "nt":
            report.fail(
                f"{exe.name} 在 {seconds}s 内未出现可见主窗口"
            )
        else:
            report.ok(
                f"{exe.name} 连续运行 {seconds}s，"
                "未发生启动级崩溃"
            )

    except Exception as exc:
        report.fail(
            f"EXE冒烟测试失败：{exc}"
        )

    finally:
        stop_smoke_process(process)


def write_report(
    root: Path,
    report: Report,
    mode,
):
    output = (
        root
        / "PACKAGING_REPORT.txt"
    )

    lines = [
        "FrameDeck Studio",
        STAGE,
        "=" * 72,
        f"Time: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"Python: {sys.version}",
        f"Project: {root}",
        f"Build mode: {mode or 'check only'}",
        "",
        *report.lines,
        "",
        "=" * 72,
        f"PASS={report.passed}",
        f"WARN={report.warned}",
        f"FAIL={report.failed}",
        "",
        (
            "结论：可继续打包/跨电脑测试"
            if report.failed == 0
            else "结论：存在FAIL，先修复再发布"
        ),
    ]

    output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return output


def main():
    a = parse_args()
    root = Path(
        a.project
    ).expanduser().resolve()

    if not (root / "main.py").is_file():
        raise SystemExit(
            "当前目录不是 FrameDeck Studio 项目根目录"
        )

    mode = choose_build(a)

    print("=" * 72)
    print(APP_NAME)
    print(STAGE)
    print("=" * 72)
    print("项目：" + str(root))
    print()

    report = Report()

    check_project(root, report)
    check_python(report)
    check_modules(report)
    syntax_check(root, report)
    check_build_scripts(root, report)
    check_icon(root, report)
    check_root_clean(root, report)

    # 预检有FAIL时不继续真正构建。
    if mode and report.failed:
        report.fail(
            "预检存在FAIL，已阻止构建"
        )
        report_path = write_report(
            root,
            report,
            mode,
        )
        print(
            "报告：" + str(report_path)
        )
        raise SystemExit(1)

    artifacts = []

    if mode:
        if not a.no_archive_old_build:
            archive_old_outputs(
                root,
                report,
            )

            if report.failed:
                report_path = write_report(
                    root,
                    report,
                    mode,
                )
                print(
                    "报告：" + str(report_path)
                )
                raise SystemExit(1)

        success, _log = run_build(
            root,
            mode,
            report,
        )

        if success:
            artifacts = collect_artifacts(
                root,
                report,
            )

            if a.smoke_exe:
                exe = choose_smoke_exe(
                    artifacts
                )

                if exe is None:
                    report.warn(
                        "未找到适合冒烟测试的应用EXE"
                    )
                else:
                    smoke_exe(
                        exe,
                        report,
                    )

    report_path = write_report(
        root,
        report,
        mode,
    )

    print()
    print("=" * 72)
    print(
        f"PASS={report.passed}  "
        f"WARN={report.warned}  "
        f"FAIL={report.failed}"
    )
    print("=" * 72)
    print(
        "报告：" + str(report_path)
    )

    if report.failed:
        print(
            "存在FAIL，暂不建议跨电脑发布。"
        )
        raise SystemExit(1)

    if mode is None:
        print()
        print(
            "预检通过。下一步可执行："
        )
        print(
            "  python FrameDeck_UI05_51A_packaging_preflight.py --build-exe"
        )
        print(
            "或："
        )
        print(
            "  python FrameDeck_UI05_51A_packaging_preflight.py "
            "--build-portable --smoke-exe"
        )
    else:
        print()
        print(
            "构建阶段完成。下一步请在一台未安装Python的Windows电脑测试。"
        )


if __name__ == "__main__":
    main()
