# -*- coding: utf-8 -*-
"""
FrameDeck Studio - UI-05-50C Release Regression Check

用法：
  python FrameDeck_UI05_50C_release_regression_check.py
  python FrameDeck_UI05_50C_release_regression_check.py --smoke

功能：
- 检查 main.py/core/gui Python 语法
- 检查关键稳定功能标记
- 检查根目录清理状态
- 检查关键 Python 依赖
- 可选启动 main.py 8 秒做冒烟测试
- 生成 RELEASE_REGRESSION_REPORT.txt
- 生成 RELEASE_REGRESSION_CHECKLIST.txt
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


MAIN_MARKERS = (
    "UI-05-46C - RESERVED BLANK PAGE FLOW",
    "UI-05-47A - MULTI IMPORT PLACEMENT",
    "UI-05-47B - COMPACT IMPORT PROMPT",
    "UI-05-49A - SOFT DEPTH BUTTON SYSTEM",
)

ACTIVE_RELEASE_TOOLS = {
    "FrameDeck_UI05_50C_release_regression_check.py",
    "FrameDeck_UI05_51A_packaging_preflight.py",
}

DEPENDENCIES = {
    "PySide6": "PySide6",
    "Pillow": "PIL",
    "python-pptx": "pptx",
}


class Report:
    def __init__(self):
        self.lines = []
        self.passed = 0
        self.warned = 0
        self.failed = 0

    def _add(self, level, text):
        self.lines.append(f"[{level}] {text}")
        print(f"[{level}] {text}")

    def ok(self, text):
        self.passed += 1
        self._add("PASS", text)

    def warn(self, text):
        self.warned += 1
        self._add("WARN", text)

    def fail(self, text):
        self.failed += 1
        self._add("FAIL", text)

    def info(self, text):
        self._add("INFO", text)


def args():
    p = argparse.ArgumentParser()
    p.add_argument("project", nargs="?", default=".")
    p.add_argument("--smoke", action="store_true")
    return p.parse_args()


def read(path):
    return path.read_text(encoding="utf-8-sig")


def check_files(root, r):
    for rel in (
        "main.py",
        "gui/main_window.py",
        "gui/slide_thumbnail_bar.py",
    ):
        if (root / rel).is_file():
            r.ok(f"关键文件存在：{rel}")
        else:
            r.fail(f"缺少关键文件：{rel}")

    for rel in ("core", "gui", "resources", "Template"):
        if (root / rel).is_dir():
            r.ok(f"关键目录存在：{rel}/")
        else:
            r.warn(f"未找到目录：{rel}/")


def check_syntax(root, r):
    targets = [root / "main.py"]

    for name in ("core", "gui"):
        folder = root / name
        if folder.is_dir():
            targets.extend(
                p for p in folder.rglob("*.py")
                if "__pycache__" not in p.parts
            )

    errors = []

    for path in sorted(set(p for p in targets if p.is_file())):
        try:
            compile(read(path), str(path), "exec")
        except Exception as exc:
            errors.append(
                f"{path.relative_to(root)}: {type(exc).__name__}: {exc}"
            )

    if errors:
        for value in errors:
            r.fail(value)
    else:
        r.ok(f"Python语法检查通过：{len(targets)} 个文件")


def check_markers(root, r):
    path = root / "gui" / "main_window.py"

    if not path.is_file():
        return

    text = read(path)

    for marker in MAIN_MARKERS:
        if marker in text:
            r.ok(f"稳定功能标记存在：{marker}")
        else:
            r.warn(f"未找到标记：{marker}")

    preview = root / "gui" / "preview_widget.py"
    preview_text = read(preview) if preview.is_file() else ""
    if (
        "def dragEnterEvent(self, event):" in preview_text
        and "def dropEvent(self, event):" in preview_text
        and "PreviewCanvas.dragEnterEvent =" not in text
        and "_fd_ui0550a_fix02_drag_enter" not in text
    ):
        r.ok("PreviewCanvas 使用正式拖放实现，无旧运行时覆盖")
    else:
        r.fail("PreviewCanvas 正式拖放实现或覆盖链检查失败")

    for label, marker in (
        ("事件驱动界面翻译", "_queue_widget_translation"),
        ("全局页面导航主题", "QListWidget#PageNavigatorList"),
        ("合并配置写入", "request_config_save"),
    ):
        if marker in text:
            r.ok(f"稳定实现存在：{label}")
        else:
            r.fail(f"缺少稳定实现：{label}")

    nav = root / "gui" / "slide_thumbnail_bar.py"

    if nav.is_file():
        nav_text = read(nav)

        if (
            "ExtendedSelection" in nav_text
            and "selected_pages" in nav_text
        ):
            r.ok("页面导航 Ctrl/Shift 多选版本存在")
        else:
            r.warn("未发现页面导航多选标记，请人工确认")


def check_clean(root, r):
    patches = [
        p for p in root.glob("FrameDeck_UI05_*.py")
        if p.name not in ACTIVE_RELEASE_TOOLS
    ]

    if patches:
        r.warn(
            "根目录仍有历史 UI05 脚本："
            + ", ".join(p.name for p in patches[:8])
        )
    else:
        r.ok("根目录无历史 UI05 patch 脚本")

    if (root / "development_archive").is_dir():
        r.ok("development_archive 存在")
    else:
        r.warn("development_archive 不存在")

    if (root / "CURRENT_STABLE_BASELINE.txt").is_file():
        r.ok("CURRENT_STABLE_BASELINE.txt 存在")
    else:
        r.warn("CURRENT_STABLE_BASELINE.txt 不存在")

    caches = [
        p for p in root.rglob("__pycache__")
        if "development_archive" not in p.parts
    ]

    if caches:
        r.warn(f"发现 {len(caches)} 个 __pycache__，打包前再清理")
    else:
        r.ok("活动代码无 __pycache__")


def check_deps(r):
    for label, module in DEPENDENCIES.items():
        if importlib.util.find_spec(module):
            r.ok(f"依赖可用：{label}")
        else:
            r.fail(f"缺少依赖：{label} ({module})")

    for label, module in (("pillow-heif", "pillow_heif"),):
        if importlib.util.find_spec(module):
            r.ok(f"可选依赖可用：{label}")
        else:
            r.warn(f"可选依赖未安装：{label}")


def check_writable(root, r):
    try:
        with tempfile.NamedTemporaryFile(delete=True) as f:
            f.write(b"FrameDeck")
            f.flush()
        r.ok("系统临时目录可写")
    except Exception as exc:
        r.fail(f"临时目录不可写：{exc}")

    probe = root / ".framedeck_write_test.tmp"

    try:
        probe.write_text("test", encoding="utf-8")
        probe.unlink(missing_ok=True)
        r.ok("项目根目录可写")
    except Exception as exc:
        r.warn(f"项目根目录写入失败：{exc}")


def smoke(root, r):
    r.info("执行 main.py 8秒启动冒烟测试……")
    process = None

    try:
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(root),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        deadline = time.monotonic() + 8

        while time.monotonic() < deadline:
            code = process.poll()

            if code is not None:
                out, err = process.communicate(timeout=2)

                if code == 0:
                    r.warn("main.py 在8秒内退出，请人工确认是否正常")
                else:
                    r.fail(f"main.py 启动异常退出，退出码={code}")

                if err.strip():
                    r.info("stderr尾部：" + err.strip()[-1200:])
                return

            time.sleep(0.25)

        r.ok("main.py 连续运行8秒，无启动级崩溃")

    except Exception as exc:
        r.fail(f"冒烟测试执行失败：{exc}")

    finally:
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=4)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass


CHECKLIST = """FrameDeck Studio
UI-05-50C 发布前完整回归清单
================================

A. 启动/工程
[ ] 01 正常启动，无异常弹窗
[ ] 02 新建/保存工程正常
[ ] 03 关闭并重开工程，页面/图片/标题/变换保持
[ ] 04 撤销/重做正常

B. 图片导入
[ ] 05 第一次添加图片正常
[ ] 06 二次添加出现 尾部/之后/之前
[ ] 07 三种插入位置都正确
[ ] 08 Windows单张图片拖入中央正常
[ ] 09 Windows多张图片拖入中央正常
[ ] 10 外部拖入无 recursion depth 错误

C. PPT
[ ] 11 Import PPT 可重复使用
[ ] 12 连续导入正常
[ ] 13 保留原PPT页结构正常
[ ] 14 PPT空白页正常
[ ] 15 单页图片超容量自动续页正常
[ ] 16 PPT二次导入 尾部/之前/之后 正常

D. 页面/固定网格
[ ] 17 行列调整正常
[ ] 18 未满页拖入空槽正常
[ ] 19 拖到已有照片位置能插入并顺延
[ ] 20 满页插入向后顺延
[ ] 21 手动空白页承接顺延
[ ] 22 图片拖入空白页后保持独立
[ ] 23 新增/复制/删除/移动页面正常

E. 导航
[ ] 24 Ctrl+左键增减多选
[ ] 25 Shift+左键范围多选
[ ] 26 Delete/Backspace批量删除
[ ] 27 删除中间页后导航不整栏清空
[ ] 28 单页拖动排序正常

F. 图片调整/标题
[ ] 29 缩放/水平/垂直移动
[ ] 30 旋转/镜像/重置
[ ] 31 标题显示/隐藏
[ ] 32 标题字体/字号/颜色/位置
[ ] 33 布局间距/页脚显示

G. UI/主题/语言
[ ] 34 浅色主题全界面变化
[ ] 35 深色主题全界面变化
[ ] 36 中文界面完整
[ ] 37 英文界面完整
[ ] 38 Add Images / Import PPT 英文正确
[ ] 39 左侧按钮圆角/立体效果正常

H. 500张性能
[ ] 40 导入约500张后仍可操作
[ ] 41 右侧列表滚动可接受
[ ] 42 页面切换可接受
[ ] 43 连续参数调整不卡死
[ ] 44 跨页拖动无明显累计卡顿
[ ] 45 保存/重开大工程正常

I. 导出
[ ] 46 PPT导出正常且清晰
[ ] 47 PDF导出正常且清晰
[ ] 48 页面图片导出正常且清晰
[ ] 49 标题/页码/布局与预览一致

J. 发布前
[ ] 50 根目录无历史patch
[ ] 51 CURRENT_STABLE_BASELINE.txt存在
[ ] 52 development_archive快照存在
[ ] 53 build_exe.bat可用
[ ] 54 requirements依赖确认
"""


def write_outputs(root, r):
    report_path = root / "RELEASE_REGRESSION_REPORT.txt"
    checklist_path = root / "RELEASE_REGRESSION_CHECKLIST.txt"

    header = [
        "FrameDeck Studio - UI-05-50C Release Regression",
        "=" * 68,
        f"Time: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"Python: {sys.version}",
        f"Project: {root}",
        "",
    ]

    footer = [
        "",
        "=" * 68,
        f"PASS={r.passed}  WARN={r.warned}  FAIL={r.failed}",
        (
            "静态检查结论：PASS"
            if r.failed == 0
            else "静态检查结论：FAIL"
        ),
        "静态检查通过后仍需完成 RELEASE_REGRESSION_CHECKLIST.txt。",
    ]

    report_path.write_text(
        "\n".join(header + r.lines + footer),
        encoding="utf-8",
    )
    checklist_path.write_text(
        CHECKLIST,
        encoding="utf-8",
    )

    return report_path, checklist_path


def main():
    a = args()
    root = Path(a.project).expanduser().resolve()

    if not (root / "main.py").is_file():
        raise SystemExit("当前目录不是 FrameDeck Studio 项目根目录")

    print("=" * 68)
    print("FrameDeck Studio - UI-05-50C 发布前回归检查")
    print("=" * 68)

    r = Report()

    check_files(root, r)
    check_syntax(root, r)
    check_markers(root, r)
    check_clean(root, r)
    check_deps(r)
    check_writable(root, r)

    if a.smoke:
        smoke(root, r)
    else:
        r.info("未执行启动冒烟测试；可加 --smoke")

    report_path, checklist_path = write_outputs(root, r)

    print()
    print(f"PASS={r.passed}  WARN={r.warned}  FAIL={r.failed}")
    print("报告：" + str(report_path))
    print("清单：" + str(checklist_path))

    if r.failed:
        print("存在 FAIL，暂不建议进入 EXE 打包。")
        raise SystemExit(1)

    print("静态检查通过。完成手工回归后即可进入 EXE/安装包阶段。")


if __name__ == "__main__":
    main()
