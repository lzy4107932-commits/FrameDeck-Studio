from __future__ import annotations

# UI-05-45B - 固定网格跨页填空 + 真实缩略图尺寸

import inspect
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from copy import deepcopy
from pathlib import Path

from PIL import Image
from natsort import natsorted
from PySide6.QtCore import (
    QObject, QRunnable, QThread, QThreadPool, QTimer, Signal, Slot,
    Qt, QSize, QRect, QRectF, QPoint, QEvent
)
from PySide6.QtGui import (
    QAction, QIcon, QPixmap, QPalette, QColor, QKeySequence, QShortcut,
    QPainter, QPen, QImage
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QColorDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QProgressDialog, QPushButton, QScrollArea, QSplitter, QTextEdit,
    QDialog, QInputDialog,
    QToolBar, QVBoxLayout, QWidget, QAbstractItemView, QSlider, QSpinBox, QDoubleSpinBox, QDockWidget, QSizePolicy, QTabWidget, QToolButton, QStatusBar, QMenu, QToolBox
)

from core.ppt_generator import (
    generate_ppt,
    PAGE_SIZES,
    preflight_ppt_output,
)
from core.image_transform_crop import (
    default_crop,
    default_transform,
    normalize_crop,
)
from core.image_cache_manager import image_cache
from core.heif_support import (
    ALL_IMAGE_FILE_FILTER,
    HEIF_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    can_decode_image_path,
    heif_support_available,
    is_heif_path,
    is_supported_image_path as is_supported_media_path,
    missing_dependency_message,
    register_heif_support,
)
from core.template_system import (
    CATEGORY_LABELS,
    create_user_template,
    load_builtin_template,
    load_template_file,
    template_catalog,
    template_fallback_settings,
    validate_template_document,
)
from core.app_paths import autosave_file
from core.group_layout import (
    PAGINATION_CONTINUOUS,
    PAGINATION_GROUPED,
    compute_page_ranges,
    default_title_system,
    effective_page_breaks,
    group_breaks,
    group_for_index,
    inherited_title_record,
    minimum_title_region_height_cm,
    normalize_groups,
    normalize_pagination_mode,
    normalize_title_style,
    normalize_title_system,
    resolve_title_vertical_geometry,
    resolve_title_context,
    resolve_title_style,
    title_record_for_scope,
    shift_groups_for_delete,
    shift_groups_for_insert,
)
from core.ppt_importer import (
    PPT_IMPORT_MODE_FLAT,
    PPT_IMPORT_MODE_GROUP_BY_SLIDE,
    PPT_IMPORT_MODE_PAGE_BY_SLIDE,
    SUPPORTED_PPT_EXTENSIONS,
    extract_ppt_images,
)
from core.project_manager import (
    load_project_file,
    load_recent_projects,
    normalize_project_path,
    save_project_file,
)
from core.drag_protocol import (
    INTERNAL_IMAGE_ROWS_MIME,
    encode_drag_rows,
    rows_from_mime,
)
from gui.preview_widget import PreviewCanvas
from gui.widgets import (
    ModernDoubleStepper,
    ModernStepper,
    InfoBadge,
    CompactNumberStepper
)

from gui.slide_thumbnail_bar import SlideThumbnailBar


def resource_path(relative: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return str(base / relative)


register_heif_support()

SUPPORTED = tuple(
    sorted(
        SUPPORTED_IMAGE_EXTENSIONS
    )
)
CONFIG_FILE = Path.home() / ".framedeck_studio_v11.json"
AUTOSAVE_FILE = autosave_file()

THUMBNAIL_ITEM_TOKEN_ROLE = (
    int(Qt.ItemDataRole.UserRole) + 39
)
THUMBNAIL_WORK_WIDTH = 360
THUMBNAIL_WORK_HEIGHT = 240

# ============================================================
# UI-05-44A
# Chinese / English interface
# ============================================================

I18N_COMBO_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 141

LEFT_PANEL_WIDTH_ZH = 226
LEFT_PANEL_WIDTH_EN = 328

# User-facing source strings remain Chinese so existing project values,
# pagination constants and template data stay fully backward compatible.
I18N_EN = {
    "帧页工坊": "Frame Layout Studio",
    "极光浅色": "Aurora Light",
    "深空暗色": "Deep Space Dark",
    "石墨专业": "Graphite Pro",
    "海洋蓝": "Ocean Blue",
    "翡翠绿": "Emerald Green",
    "赛博青": "Cyber Cyan",
    "紫晶夜": "Amethyst Night",
    "适应窗口": "Fit to Window",
    "收起": "Collapse",
    "展开": "Expand",
    "分组管理": "Group Manager",
    "当前工程分组": "Groups in Current Project",
    "定位": "Go to",
    "重命名": "Rename",
    "当前页设为新分组": "Start New Group Here",
    "与上一组合并": "Merge with Previous",
    "与下一组合并": "Merge with Next",
    "关闭": "Close",
    "说明：分组只记录图片归属与分页边界；不会复制、删除或修改原图片。": "Note: Groups only record image ownership and page boundaries; original images are never copied, deleted, or modified.",
    "分组排版": "Grouped Layout",
    "连续排版": "Continuous Layout",
    "重命名分组": "Rename Group",
    "分组名称：": "Group name:",
    "分组名称": "Group Name",
    "分组名称不能为空。": "The group name cannot be empty.",
    "撤销": "Undo",
    "重做": "Redo",
    "显示日志": "Show Log",
    "隐藏日志": "Hide Log",
    "图片 0": "Images 0",
    "页面 1/1": "Page 1/1",
    "画布 100%": "Canvas 100%",
    "未保存": "Unsaved",
    "未保存工程": "Unsaved Project",
    "停止缩略图": "Stop Thumbnails",
    "停止剩余后台缩略图任务；已导入图片不会被删除": "Stop the remaining background thumbnail tasks; imported images will not be removed",
    "新建": "New",
    "打开": "Open",
    "最近": "Recent",
    "保存": "Save",
    "模板": "Templates",
    "日志": "Log",
    "创建新工程": "Create a new project",
    "打开工程文件": "Open a project file",
    "最近打开的工程": "Recently opened projects",
    "保存当前工程": "Save the current project",
    "撤销上一步操作": "Undo the previous action",
    "恢复上一步操作": "Redo the previous action",
    "载入排版模板": "Load a layout template",
    "显示或隐藏生成日志": "Show or hide the generation log",
    "更多工具": "More Tools",
    "载入模板": "Load Template",
    "选择主题": "Choose Theme",
    "主题选择": "Theme Selection",
    "极光浅色": "Aurora Light",
    "雾银灰": "Mist Gray",
    "深空暗色": "Deep Space Dark",
    "海洋蓝": "Ocean Blue",
    "珊瑚暮色": "Coral Dusk",
    "生成 PPT": "Export PPT",
    "生成 PDF": "Export PDF",
    "生成图片": "Export Images",
    "页面图片": "Page Images",
    "生成 PowerPoint 文件": "Export a PowerPoint file",
    "生成多页 PDF 文件": "Export a multipage PDF file",
    "按页面生成 PNG 图片": "Export each page as a PNG image",
    "点击主体生成 PPT；点击右侧箭头选择 PDF 或图片": "Click the main button to export PPT; use the arrow for PDF or images",
    "图片素材": "Image Assets",
    "从本机选择照片加入当前工程": "Choose photos from this computer and add them to the project",
    "当前 0 张": "Current: 0 images",
    "＋  添加图片": "+  Add Images",
    "导入素材": "Import Assets",
    "从PPT导入图片": "Import Images from PPT",
    "点击主体添加图片；点击右侧箭头可从PPT导入": "Click the main button to add images; use the arrow to import from PPT",
    "多选添加 JPG、PNG、WEBP、TIFF、HEIF/HEIC 图片": "Select one or more JPG, PNG, WEBP, TIFF, HEIF/HEIC images",
    "▣  导入PPT图片": "▣  Import PPT Images",
    "从 .pptx / .pptm 中按页码和视觉位置提取图片，并加入当前工程": "Extract images from .pptx/.pptm by slide and visual position, then add them to this project",
    "每次导入创建新分组": "Create a new group for each import",
    "仅在“分组排版”模式生效。\n每次批量添加的同类图片会从新页面开始，上一组末页的空位不会被下一组自动补齐。": "Available in Grouped Layout only.\nEach imported batch starts on a new page, and empty slots at the end of a group are not filled by the next group.",
    "支持拖入 · JPG/PNG/WEBP/TIFF/HEIF · PPTX/PPTM": "Drag & drop · JPG/PNG/WEBP/TIFF/HEIF · PPTX/PPTM",
    "页面布局": "Page Layout",
    "行数": "Rows",
    "列数": "Columns",
    "页面尺寸": "Page Size",
    "图片模式": "Image Mode",
    "自动排版": "Auto Layout",
    "按当前行列连续补满页面空位": "Continuously fill page slots using the current rows and columns",
    "确认此次排版": "Keep",
    "确认当前自动排版并停止自动补位": "Keep the current layout and stop automatic filling",
    "取消勾选将恢复开启自动排版前的版本": "Turn this off to restore the version from before Auto Layout",
    "已恢复开启自动排版前的版本": "Restored the version from before Auto Layout",
    "已保留此次自动排版，后续删除不会自动补位": "Layout confirmed; later deletions will keep their page gaps",
    "分页方式": "Pagination",
    "连续排版 · 自动补满": "Continuous · Auto Fill",
    "分组排版 · 保留组尾空位": "Grouped · Keep End Gaps",
    "连续：自动补满。\n分组：组尾保留空位，不跨组补位。": "Continuous: automatically fills pages.\nGrouped: keeps gaps at group ends and never fills across groups.",
    "连续模式：自动补满": "Continuous mode: Auto fill",
    "分组管理…": "Manage Groups…",
    "整理分组…": "Organize Groups…",
    "整理分组": "Organize Groups",
    "拖动图片即可跨页 / 跨组调整": "Drag images to rearrange across pages or groups",
    "重命名或整理分组边界": "Rename groups or organize their boundaries",
    "查看、重命名、拆分和合并图片分组": "View, rename, split, and merge image groups",
    "锁定当前页": "Lock Current Page",
    "解锁当前页": "Unlock Current Page",
    "锁定当前图片页边界；删除图片后，后页不会自动补位。": "Lock the current image-page boundary so later pages do not refill it after deletion.",
    "锁定当前组": "Lock Current Group",
    "解锁当前组": "Unlock Current Group",
    "锁定当前分组与当前页面结构；锁定后不能拆分、合并或移动该组页面。": "Lock this group and its page structure; locked group pages cannot be split, merged, or moved.",
    "当前页：未锁定 · 当前组：未锁定": "Page: Unlocked · Group: Unlocked",
    "空白页独立": "Blank Page Is Independent",
    "本页随组锁定": "Locked with Group",
    "随组锁定": "With Group",
    "已锁定": "Locked",
    "未锁定": "Unlocked",
    "页面标题": "Page Title",
    "批量标题": "Batch Title",
    "显示页面标题": "Show Page Titles",
    "统一标题": "Shared Title",
    "应用到全部页": "Apply to All Pages",
    "应用全部": "Apply All",
    "双击标题或画布上的“＋ 标题”即可编辑": "Double-click a title or “+ Title” on the canvas to edit",
    "编辑页面标题": "Edit Page Title",
    "已将统一标题应用到全部页面": "Shared title applied to all pages",
    "已清除全部页面标题": "All page titles cleared",
    "启用页面标题": "Enable Page Title",
    "全局统一": "Global",
    "按分组": "By Group",
    "每页独立": "Per Page",
    "全局统一：所有页面使用同一标题。\n按分组：同组页面使用同一标题，未填写时继承全局标题。\n每页独立：当前页可单独填写，未填写时继承分组/全局标题。": "Global: use one title on every page.\nBy Group: pages in a group share a title and inherit the global title when empty.\nPer Page: each page can have its own title and inherits from its group/global title when empty.",
    "当前范围：全部页面": "Current scope: All pages",
    "主标题": "Main Title",
    "副标题（可选）": "Subtitle (optional)",
    "样式：全部页面": "Style: All Pages",
    "样式：当前分组": "Style: Current Group",
    "样式：当前页": "Style: Current Page",
    "恢复继承": "Restore Inheritance",
    "删除当前分组或当前页的样式覆盖，恢复继承上一级标题样式": "Remove this group/page override and inherit the parent title style",
    "可直接输入电脑中已安装的其它字体名称": "You can enter the name of any other installed font",
    "字体": "Font",
    "字号": "Size",
    "颜色": "Color",
    "选择标题文字颜色": "Choose title text color",
    "加粗": "Bold",
    "左对齐": "Left",
    "居中": "Center",
    "右对齐": "Right",
    "顶部间距": "Top Spacing",
    "标题高度": "Title Height",
    "Logo 图片路径（可选）": "Logo image path (optional)",
    "Logo：未选择": "Logo: Not selected",
    "尚未选择 Logo": "No logo selected",
    "选择": "Choose",
    "选择 Logo 图片": "Choose a logo image",
    "清除": "Clear",
    "取消当前 Logo": "Remove the current logo",
    "启用页脚": "Enable Footer",
    "页脚文字": "Footer Text",
    "布局间距": "Layout Spacing",
    "单位：cm": "Unit: cm",
    "左边距": "Left Margin",
    "右边距": "Right Margin",
    "上边距": "Top Margin",
    "下边距": "Bottom Margin",
    "水平间距": "Horizontal Gap",
    "垂直间距": "Vertical Gap",
    "图片下方文字高度": "Caption Height",
    "图片调整": "Image Adjustments",
    "未选择图片": "No Image Selected",
    "已选择图片": "Image Selected",
    "默认参数": "Default Settings",
    "多选状态": "Multiple Selection",
    "图片缩放范围：0.10×～10.00×": "Image scale range: 0.10×–10.00×",
    "范围会根据图片比例和缩放倍率自动扩展": "The range expands automatically based on image ratio and scale",
    "缩放": "Scale",
    "水平位置": "Horizontal Position",
    "垂直位置": "Vertical Position",
    "旋转与镜像": "Rotate & Flip",
    "左转 90°": "Rotate Left 90°",
    "右转 90°": "Rotate Right 90°",
    "水平镜像": "Flip Horizontal",
    "垂直翻转": "Flip Vertical",
    "重置参数": "Reset Settings",
    "显示设置": "Display Settings",
    "页脚与显示": "Footer and Display",
    "显示文件名": "Show Filenames",
    "显示编号": "Show Numbers",
    "显示页码": "Show Page Numbers",
    "图片边框": "Image Borders",
    "页面预览": "Page Preview",
    "页\n面\n预\n览": "Page\nPreview",
    "缩小画布": "Zoom Out",
    "放大画布": "Zoom In",
    "首页": "First",
    "上一页": "Previous",
    "下一页": "Next",
    "末页": "Last",
    "第": "Page",
    "页": "",
    "搜索图片素材…": "Search…",
    "输入文件名关键词实时筛选（Ctrl+F）；点击右侧 × 清除搜索": "Filter by filename (Ctrl+F); click × to clear",
    "缩略图": "Thumbnail",
    "调整图片列表缩略图大小": "Adjust image-list thumbnail size",
    "调整右侧图片列表▫": "Resize thumbnails in the right image list",
    "列表显示": "List View",
    "小缩略图": "Small Thumbnails",
    "中缩略图": "Medium Thumbnails",
    "大缩略图": "Large Thumbnails",
    "生成日志": "Generation Log",
    "生成与操作日志会显示在这里。": "Generation and operation logs appear here.",
    "拖入图片文件夹，或点击浏览": "Drop an image folder here, or click Browse",
    "请先点击中央画布、图片列表或页面导航栏": "Click the canvas, image list, or page navigator first",
    "点击切换页面；拖动调整页面顺序；导航栏聚焦时 Ctrl+D 复制页": "Click to switch pages; drag to reorder; press Ctrl+D when focused to duplicate a page",
    "已聚焦文件名搜索": "Filename search focused",
    "已聚焦中央画布": "Canvas focused",
    "已聚焦图片列表": "Image list focused",
    "已聚焦页面导航": "Page navigator focused",
    "选择 Logo": "Choose Logo",
    "已取消页面 Logo": "Page logo removed",
    "专业模板": "Professional Templates",
    "恢复自由网格布局": "Restore Free Grid Layout",
    "从 JSON 文件载入…": "Load from JSON…",
    "保存当前设置为模板…": "Save Current Settings as Template…",
    "选择AI角色设计或电影视觉开发模板": "Choose an AI character-design or cinematic visual-development template",
    "当前为自由网格布局": "Current layout: Free Grid",
    "已恢复自由网格布局": "Free Grid layout restored",
    "所有页面统一主标题": "One main title for all pages",
    "所有页面统一副标题（可选）": "One subtitle for all pages (optional)",
    "调整标题内容方式": "Change title content mode",
    "选择标题颜色": "Choose Title Color",
    "恢复标题样式继承": "Restore Title Style Inheritance",
    "水平移动图片": "Move Image Horizontally",
    "垂直移动图片": "Move Image Vertically",
    "旋转图片": "Rotate Image",
    "镜像图片": "Flip Image",
    "重置图片裁切": "Reset Image Crop",
    "重置当前图片精修": "Reset Current Image Adjustments",
    "隐藏图片": "Hide Image",
    "恢复隐藏图片": "Restore Hidden Image",
    "重置排版": "Reset Layout",
    "保持比例": "Fit",
    "裁剪填充": "Fill & Crop",
    "需要安装 HEIF 支持": "HEIF Support Required",
    "全部图片 · 一个分组": "All Images · One Group",
    "原PPT每页 · 一个分组": "Each PPT Slide · One Group",
    "原PPT每页 · 对应页面": "Each PPT Slide · Matching Page",
    "选择要提取图片的PPT": "Choose a PPT to extract images from",
    "PPT导入方式": "PPT Import Mode",
    "取消": "Cancel",
    "正在扫描PPT……": "Scanning PPT…",
    "取消导入": "Cancel Import",
    "导入PPT图片": "Import PPT Images",
    "PPT图片导入完成": "PPT Image Import Complete",
    "PPT图片导入失败": "PPT Image Import Failed",
    "添加图片": "Add Images",
    "选择图片目录": "Choose Image Folder",
    "画布指定区域插入图片": "Insert Images into Canvas Area",
    "右侧图片列表拖入图片": "Drop Images into Right List",
    "已确认当前预览与图片顺序，开始生成 PPT...": "Preview and image order confirmed; exporting PPT…",
    "完成": "Complete",
    "生成失败": "Export Failed",
    "生成失败，日志面板已自动打开。": "Export failed. The log panel has been opened.",
    "复制所选图片": "Duplicate Selected Images",
    "复制所选图片副本": "Duplicate Selected Image Files",
    "复制到项目剪贴板": "Copy to Project Clipboard",
    "粘贴到当前页": "Paste into Current Page",
    "粘贴图片": "Paste Images",
    "移到上一页末尾": "Move to End of Previous Page",
    "移到下一页开头": "Move to Start of Next Page",
    "删除所选图片": "Delete Selected Images",
    "进入裁切模式": "Enter Crop Mode",
    "全选图片": "Select All Images",
    "取消选择": "Clear Selection",
    "批量操作": "Batch Operation",
    "请先在图片列表中多选图片。": "Select multiple images in the image list first.",
    "批量旋转": "Batch Rotate",
    "批量隐藏": "Batch Hide",
    "批量重置": "Batch Reset",
    "新建工程": "New Project",
    "确定清空当前工程并重新开始吗？": "Clear the current project and start over?",
    "调整页面顺序": "Reorder Pages",
    "复制页面": "Duplicate Page",
    "删除页面": "Delete Page",
    "FrameDeck 工程另存为": "Save FrameDeck Project As",
    "保存 FrameDeck 工程": "Save FrameDeck Project",
    "FrameDeck 工程 (*.fds)": "FrameDeck Project (*.fds)",
    "打开 FrameDeck 工程": "Open FrameDeck Project",
    "旧版工程": "Legacy Project",
    "恢复自动保存": "Recover Autosave",
    "检测到上次自动保存的工程。": "An autosaved project from the previous session was found.",
    "恢复工程": "Recover Project",
    "放弃恢复": "Discard Recovery",
    "保存 FrameDeck 模板": "Save FrameDeck Template",
    "FrameDeck 模板 (*.json)": "FrameDeck Template (*.json)",
    "载入 FrameDeck 模板": "Load FrameDeck Template",
    "保存工程": "Save Project",
    "关闭软件前是否保存当前工程？\n\n保存工程会保留图片顺序、页面、模板、裁切、缩放和位置调整。": "Save the current project before closing?\n\nSaving preserves image order, pages, templates, crop, scale, and position adjustments.",
    "不保存": "Don't Save",
    "取消关闭": "Cancel Closing",
    "部分图片缺失": "Some Images Are Missing",
    "页面锁定": "Page Lock",
    "空白页本身就是独立页面，不需要额外锁定。": "A blank page is already independent and does not need an additional lock.",
    "当前页已随分组锁定。\n如需单独控制，请先解锁当前组。": "This page is locked with its group.\nUnlock the group first to control the page separately.",
    "分组锁定": "Group Lock",
    "当前页不属于可锁定的图片分组。": "The current page does not belong to a lockable image group.",
    "当前工程还没有图片。": "The current project has no images.",
    "建立分组": "Create Group",
    "空白页没有图片，不能作为图片分组起点。": "A blank page has no images and cannot start an image group.",
    "分组已锁定": "Group Is Locked",
    "当前分组处于锁定状态。\n请先解锁当前组，再建立新的分组边界。": "The current group is locked.\nUnlock it before creating a new group boundary.",
    "参与合并的分组中存在已锁定分组。\n请先解锁分组，再执行合并。": "One of the groups being merged is locked.\nUnlock it before merging.",
    "存在锁定分组": "Locked Group Exists",
    "当前工程存在已锁定分组。\n请先解锁所有分组，再切换到连续排版。": "This project contains locked groups.\nUnlock all groups before switching to Continuous Layout.",
    "切换分组排版": "Switch to Grouped Layout",
    "切换连续排版": "Switch to Continuous Layout",
    "图片位置已调整": "Image position updated",
    "无法进入裁切": "Cannot Enter Crop Mode",
    "请先只选择一张图片。": "Select exactly one image first.",
    "请先选择需要裁切的图片。": "Select an image to crop first.",
    "当前图片无法读取或暂时不能裁切。": "The current image cannot be read or cropped right now.",
    "未选择图片": "No Image Selected",
    "请先选择需要重置裁切的图片。": "Select an image before resetting its crop.",
    "图片裁切已重置": "Image crop reset",
    "请先在预览或图片列表中选择一张图片。": "Select one image in the preview or image list first.",
    "已经是默认参数": "Already using default settings",
    "复制失败": "Duplication Failed",
    "复制图片": "Duplicate Images",
    "部分图片复制失败": "Some Images Could Not Be Duplicated",
    "删除图片": "Delete Images",
    "没有隐藏图片": "No Hidden Images",
    "当前没有被隐藏的图片。": "There are no hidden images.",
}

I18N_EN.update({
    "FrameDeck Studio V12 Stable V6 · 帧页工坊": "FrameDeck Studio V12 Stable V6 · Frame Layout Studio",
    "A4横版": "A4 Landscape",
    "A4竖版": "A4 Portrait",
    "缩小画布（Ctrl+-）": "Zoom Out (Ctrl+-)",
    "适应窗口（Ctrl+0）": "Fit to Window (Ctrl+0)",
    "放大画布（Ctrl++）": "Zoom In (Ctrl++)",
    "首页（Ctrl+Home）": "First Page (Ctrl+Home)",
    "上一页（PageUp / Alt+←）": "Previous Page (PageUp / Alt+←)",
    "下一页（PageDown / Alt+→）": "Next Page (PageDown / Alt+→)",
    "末页（Ctrl+End）": "Last Page (Ctrl+End)",
    "左转 90°（Ctrl+Alt+←）": "Rotate Left 90° (Ctrl+Alt+←)",
    "右转 90°（Ctrl+Alt+→）": "Rotate Right 90° (Ctrl+Alt+→)",
    "水平镜像（Ctrl+Alt+H）": "Flip Horizontal (Ctrl+Alt+H)",
    "垂直翻转（Ctrl+Alt+V）": "Flip Vertical (Ctrl+Alt+V)",
    "重置图片参数（Ctrl+Alt+R）": "Reset Image Settings (Ctrl+Alt+R)",
    "模板无效": "Invalid Template",
    "模板载入失败": "Template Load Failed",
    "当前页：无图片 · 当前组：无": "Page: No Images · Group: None",
    "当前页：空白页无需锁定 · 当前组：无": "Page: Blank Page Needs No Lock · Group: None",
    "建立新分组": "Create New Group",
    "新分组名称：": "New group name:",
    "合并分组": "Merge Groups",
    "已自动修复中间空白框，图片顺序已连续回填": "Intermediate empty slots repaired; images now fill continuously",
    "图片已恢复 1.00× 并自动居中": "Image restored to 1.00× and centered",
    "图片可见区域已调整": "Visible image area updated",
    "裁切模式：拖动边框、控制点或框内区域；右上角 ✓ 确认，× 取消；Enter / Esc 仍可使用": "Crop mode: drag the border, handles, or inside area; use ✓ to apply, × to cancel, or press Enter/Esc",
    "当前图片没有裁切": "The current image is not cropped",
    "请先选择要复制的图片": "Select images to duplicate first",
    "没有可撤销的操作": "Nothing to undo",
    "没有可重做的操作": "Nothing to redo",
    "PPT图片正在导入": "PPT Images Are Being Imported",
    "请等待当前PPT图片提取完成，或在进度窗口中取消。": "Wait for the current PPT extraction to finish, or cancel it in the progress window.",
    "PowerPoint 文件 (*.pptx *.pptm);;PowerPoint 演示文稿 (*.pptx);;启用宏的演示文稿 (*.pptm)": "PowerPoint Files (*.pptx *.pptm);;PowerPoint Presentation (*.pptx);;Macro-enabled Presentation (*.pptm)",
    "暂不支持旧版PPT": "Legacy PPT Is Not Supported",
    "旧版 .ppt 是二进制格式。\n\n请先使用WPS或PowerPoint另存为 .pptx，再执行图片导入。": "The legacy .ppt format is binary.\n\nSave it as .pptx in WPS or PowerPoint before importing images.",
    "文件格式不支持": "Unsupported File Format",
    "当前支持 .pptx 和 .pptm。": ".pptx and .pptm are currently supported.",
    "图片始终按“原页码 → 页面视觉顺序”提取。\n\n全部图片 · 一个分组：合并为一个导入批次。\n原PPT每页 · 一个分组：每个有图片的原页建立独立分组，并切换到分组排版。\n原PPT每页 · 对应页面：保留原页边界；无图片原页生成空白页。\n\n若某一原页图片数超过当前页面容量，会紧接该原页自动续页。\n原PPT不会被修改。": "Images are extracted in original slide order, then visual order.\n\nAll Images · One Group: merge everything into one import batch.\nEach PPT Slide · One Group: create a group for every slide containing images and switch to Grouped Layout.\nEach PPT Slide · Matching Page: preserve slide boundaries and create blank pages for slides without images.\n\nIf a source slide exceeds the current page capacity, continuation pages are created immediately after it.\nThe original PPT is never modified.",
    "PPT页面结构导入完成": "PPT Page Structure Imported",
    "没有可导入图片": "No Images to Import",
    "PPT解析或图片提取失败。\n\n原PPT和当前工程没有被修改，详细错误已写入日志面板。": "PPT parsing or image extraction failed.\n\nThe original PPT and current project were not modified. Details are available in the log panel.",
    "已取消PPT图片导入": "PPT image import cancelled",
    "已停止剩余缩略图后台加载；图片和工程内容仍然保留": "Remaining background thumbnail loading stopped; images and project content are preserved",
    "图片拖动": "Move Images",
    "当前图片列表正在搜索筛选。\n请先清除搜索内容，再进行跨组拖拽。": "The image list is currently filtered.\nClear the search before dragging images across groups.",
    "选中的图片中包含已隐藏素材。\n请先恢复显示，再执行跨组拖动。": "The selection contains hidden assets.\nRestore them before dragging across groups.",
    "本次拖动涉及已锁定分组。\n请先解锁相关分组，再移动图片。": "This move involves a locked group.\nUnlock the affected groups before moving images.",
    "页面已锁定": "Page Is Locked",
    "本次拖动会改变已锁定页面的图片归属。\n请先解锁相关页面，再执行跨页/跨组拖动。": "This move would change images on a locked page.\nUnlock the affected pages before dragging across pages or groups.",
    "无法生成": "Cannot Export",
    "请先添加图片。": "Add images first.",
    "所有图片都已隐藏，请先恢复至少一张图片。": "All images are hidden. Restore at least one image first.",
    "覆盖图片": "Replace Images",
    "覆盖文件": "Replace File",
    "PPT文件正在使用或无法写入": "The PPT File Is in Use or Not Writable",
    "输出路径检查失败": "Output Path Check Failed",
    "拖动操作会改变已锁定分组的页面位置。\n请先解锁该分组再调整页面顺序。": "This operation would move pages in a locked group.\nUnlock the group before reordering pages.",
    "页面顺序已调整": "Page order updated",
    "添加页面失败": "Could Not Add Page",
    "当前页面属于已锁定分组。\n请先解锁当前组，再复制页面。": "The current page belongs to a locked group.\nUnlock the group before duplicating the page.",
    "复制页面失败": "Could Not Duplicate Page",
    "无法删除": "Cannot Delete",
    "工程中至少需要保留一个页面。": "The project must contain at least one page.",
    "当前页面处于锁定状态。\n请先解锁当前页或当前组，再删除整页。": "The current page is locked.\nUnlock the page or its group before deleting it.",
    "保存失败": "Save Failed",
    "最近工程": "Recent Projects",
    "暂无最近工程。": "No recent projects.",
    "打开失败": "Open Failed",
    "已放弃自动保存，进入空白工程": "Autosave discarded; opened a blank project",
    "本次未恢复自动保存": "Autosave was not recovered this time",
    "Compact Professional Image Layout & PPT Composer\n\n支持批量图片排版、可视化预览、单图调整、批量编辑、页面标题、页脚、工程与模板管理。": "Compact Professional Image Layout & PPT Composer\n\nSupports batch image layout, visual preview, per-image adjustments, batch editing, page titles, footers, projects, and templates.",
    "FrameDeck Studio 快捷键": "FrameDeck Studio Keyboard Shortcuts",
    "FrameDeck Studio 常用快捷键": "FrameDeck Studio Common Keyboard Shortcuts",
    "常用快捷键": "Keyboard Shortcuts",
    "工程": "Project",
    "另存为": "Save As",
    "生成与历史": "Export & History",
    "功能区焦点": "Panel Focus",
    "中央画布": "Canvas",
    "图片列表": "Image List",
    "搜索文件名": "Search Filenames",
    "页面导航": "Page Navigation",
    "页面操作": "Page Operations",
    "新增空白页": "Create Blank Page",
    "复制当前页": "Duplicate Current Page",
    "删除当前页": "Delete Current Page",
    "移动当前页": "Move Current Page",
    "画布缩放": "Canvas Zoom",
    "图片选择、复制与排序": "Image Selection, Duplication & Order",
    "增减选择": "Toggle Selection",
    "连续多选": "Range Selection",
    "复制所选图片": "Duplicate Selected Images",
    "删除所选图片": "Delete Selected Images",
    "选择上一张或下一张": "Select Previous or Next Image",
    "向前或向后移动图片": "Move Image Forward or Backward",
    "图片微调": "Image Fine-tuning",
    "图片变换与裁切": "Image Transform & Crop",
    "进入裁切": "Enter Crop",
    "重置裁切": "Reset Crop",
    "裁切模式": "Crop Mode",
    "拖动边框或控制点调整范围": "Drag borders or handles to adjust the crop",
    "拖动框内移动": "Drag inside the crop box to move it",
    "滚轮缩放裁切范围": "Use the mouse wheel to resize the crop",
    "确认": "Apply",
    "其它": "Other",
    "全屏": "Full Screen",
    "确定": "OK",
    "是": "Yes",
    "否": "No",
    "添加空白页": "Add Blank Page",
    "添加页面": "Add Page",
    "复制当前页面": "Duplicate This Page",
    "删除当前页面": "Delete This Page",
    "向前移动": "Move Forward",
    "向后移动": "Move Backward",
    "浏览": "Browse",
    "向前": "Forward",
    "向后": "Backward",
    "▣  导入PPT": "▣  Import PPT",
    "▣ 导入PPT": "▣ Import PPT",
    "导入PPT": "Import PPT",
    "从 PPTX / PPTM 中提取图片并插入工程":
        "Extract images from PPTX/PPTM and insert them into the project",
    "本次PPT内容": "This PPT content",
    "PPT导入方式": "PPT Import Mode",
    "连续导入": "Continuous Import",
    "保留原PPT页结构": "Keep Original PPT Pages",
    "插入尾部": "Insert at End",
    "插入之后": "Insert After",
    "插入之前": "Insert Before",
    "选择插入位置": "Choose Insert Position",
})

I18N_ZH = {english: chinese for chinese, english in I18N_EN.items()}


def read_saved_language() -> str:
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        value = str(payload.get("language", "zh_CN"))
        return "en_US" if value.lower().startswith("en") else "zh_CN"
    except Exception:
        return "zh_CN"


def translate_ui_text(text, language="zh_CN"):
    """Translate UI chrome without touching project/user content."""
    value = str(text or "")
    if not value:
        return value

    table = I18N_EN if language == "en_US" else I18N_ZH
    if value in table:
        return table[value]

    # Collapsible-card captions are assembled dynamically.
    match = re.fullmatch(r"([▾▸])\s{2}(.+)", value)
    if match:
        return f"{match.group(1)}  {translate_ui_text(match.group(2), language)}"

    if language == "en_US":
        patterns = (
            (r"^图片\s+(\d+)$", r"Images \1"),
            (r"^页面\s+(\d+)/(\d+)$", r"Page \1/\2"),
            (r"^画布\s+(.+)$", lambda m: f"Canvas {translate_ui_text(m.group(1), language)}"),
            (r"^当前\s+(\d+)\s+张$", r"Current: \1 images"),
            (r"^当前\s+(\d+)\s+张\s*·\s*(\d+)\s+组$", r"Current: \1 images · \2 groups"),
            (r"^图片\s+(\d+)/(\d+)$", r"Images \1/\2"),
            (r"^已选择\s+(\d+)\s+张图片$", r"\1 images selected"),
            (r"^Logo：(.+)$", r"Logo: \1"),
            (r"^当前主题：(.+)\n点击选择其他主题$", lambda m: f"Current theme: {translate_ui_text(m.group(1), language)}\nClick to choose another theme"),
            (r"^主题已切换为：(.+)$", lambda m: f"Theme changed to: {translate_ui_text(m.group(1), language)}"),
            (r"^点击(收起|展开)(.+)$", lambda m: ("Click to collapse " if m.group(1) == "收起" else "Click to expand ") + translate_ui_text(m.group(2), language)),
            (r"^第\s*(\d+)\s*页$", r"Page \1"),
            (r"^共\s*(\d+)\s*个分组\s*·\s*当前模式：(.+)$", lambda m: f"{m.group(1)} groups · Mode: {translate_ui_text(m.group(2), language)}"),
            (r"^当前水平范围：(.+)$", r"Horizontal range: \1"),
            (r"^当前垂直范围：(.+)$", r"Vertical range: \1"),
            (r"^当前页：(.+?)\s*·\s*当前组：(.+)$", lambda m: f"Page: {translate_ui_text(m.group(1), language)} · Group: {translate_ui_text(m.group(2), language)}"),
            (r"^已撤销：(.+)$", r"Undone: \1"),
            (r"^已重做：(.+)$", r"Redone: \1"),
            (r"^已定位到分组：(.+)$", r"Located group: \1"),
            (r"^已复制\s+(\d+)\s+张图片$", r"Duplicated \1 images"),
            (r"^已删除\s+(\d+)\s+张图片$", r"Deleted \1 images"),
            (r"^缩略图后台缓存完成：(\d+)\s+张$", r"Background thumbnail caching complete: \1 images"),
            (r"^后台生成缩略图：(\d+)/(\d+)（软件可继续操作）$", r"Generating thumbnails: \1/\2 (you can keep working)"),
            (r"^页面缩略图已静默更新：(\d+)\s+页$", r"Page thumbnails updated in background: \1 pages"),
            (r"^已调整\s+(\d+)\s+张图片顺序$", r"Reordered \1 images"),
            (r"^已在第\s+(\d+)\s+页后插入空白页（新第\s+(\d+)\s+页）$", r"Inserted a blank page after page \1 (new page \2)"),
            (r"^已删除第\s+(\d+)\s+页$", r"Deleted page \1"),
            (r"^工程已另存为：(.+)$", r"Project saved as: \1"),
            (r"^工程已保存：(.+)$", r"Project saved: \1"),
            (r"^模板已保存：(.+)$", r"Template saved: \1"),
            (r"^已恢复上次自动保存：(\d+)\s+张图片$", r"Recovered autosave: \1 images"),
            (r"^有\s*(\d+)\s*张图片找不到，已跳过。$", r"\1 missing images were skipped."),
            (r"^“(.+)”尚未保存。$", r"“\1” has not been saved."),
        )
    else:
        patterns = (
            (r"^Images\s+(\d+)$", r"图片 \1"),
            (r"^Page\s+(\d+)/(\d+)$", r"页面 \1/\2"),
            (r"^Canvas\s+(.+)$", lambda m: f"画布 {translate_ui_text(m.group(1), language)}"),
            (r"^Current:\s+(\d+)\s+images$", r"当前 \1 张"),
            (r"^Current:\s+(\d+)\s+images\s*·\s*(\d+)\s+groups$", r"当前 \1 张 · \2 组"),
            (r"^Images\s+(\d+)/(\d+)$", r"图片 \1/\2"),
            (r"^(\d+)\s+images selected$", r"已选择 \1 张图片"),
            (r"^Logo:\s*(.+)$", r"Logo：\1"),
            (r"^Current theme:\s*(.+)\nClick to choose another theme$", lambda m: f"当前主题：{translate_ui_text(m.group(1), language)}\n点击选择其他主题"),
            (r"^Theme changed to:\s*(.+)$", lambda m: f"主题已切换为：{translate_ui_text(m.group(1), language)}"),
            (r"^Click to collapse (.+)$", lambda m: "点击收起" + translate_ui_text(m.group(1), language)),
            (r"^Click to expand (.+)$", lambda m: "点击展开" + translate_ui_text(m.group(1), language)),
            (r"^Page\s+(\d+)$", r"第 \1 页"),
            (r"^(\d+) groups · Mode: (.+)$", lambda m: f"共 {m.group(1)} 个分组 · 当前模式：{translate_ui_text(m.group(2), language)}"),
            (r"^Horizontal range:\s*(.+)$", r"当前水平范围：\1"),
            (r"^Vertical range:\s*(.+)$", r"当前垂直范围：\1"),
            (r"^Page:\s*(.+?)\s*·\s*Group:\s*(.+)$", lambda m: f"当前页：{translate_ui_text(m.group(1), language)} · 当前组：{translate_ui_text(m.group(2), language)}"),
            (r"^Undone:\s*(.+)$", r"已撤销：\1"),
            (r"^Redone:\s*(.+)$", r"已重做：\1"),
            (r"^Located group:\s*(.+)$", r"已定位到分组：\1"),
            (r"^Duplicated\s+(\d+)\s+images$", r"已复制 \1 张图片"),
            (r"^Deleted\s+(\d+)\s+images$", r"已删除 \1 张图片"),
            (r"^(\d+) missing images were skipped\.$", r"有 \1 张图片找不到，已跳过。"),
            (r"^“(.+)” has not been saved\.$", r"“\1”尚未保存。"),
        )

    for pattern, replacement in patterns:
        if re.fullmatch(pattern, value):
            return re.sub(pattern, replacement, value)

    # Rich text is application-authored, so phrase replacement is safe here.
    if "<" in value and ">" in value:
        ordered = sorted(
            (item for item in table.items() if len(item[0]) > 1),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for source, target in ordered:
            value = value.replace(source, target)
    return value


class _ThumbnailTaskSignals(QObject):
    completed = Signal(object)


class _ThumbnailDecodeTask(QRunnable):
    """
    所有图片格式统一使用的后台缩略图任务。

    后台线程只创建 QImage；QPixmap 与 QListWidgetItem 更新
    始终留在主线程。
    """

    def __init__(
        self,
        cache,
        *,
        generation,
        request_id,
        token,
        path,
        width,
        height,
        heavy,
    ):
        super().__init__()
        self.setAutoDelete(True)
        self.cache = cache
        self.generation = int(
            generation
        )
        self.request_id = int(
            request_id
        )
        self.token = int(token)
        self.path = str(path)
        self.width = int(width)
        self.height = int(height)
        self.heavy = bool(heavy)
        self.signals = (
            _ThumbnailTaskSignals()
        )

    @Slot()
    def run(self):
        image = QImage()
        error = ""

        try:
            image = self.cache.thumbnail_image(
                self.path,
                self.width,
                self.height,
            )
        except Exception as exception:
            error = (
                f"{type(exception).__name__}: "
                f"{exception}"
            )

        self.signals.completed.emit(
            {
                "generation": self.generation,
                "request_id": self.request_id,
                "token": self.token,
                "path": self.path,
                "width": self.width,
                "height": self.height,
                "heavy": self.heavy,
                "image": image,
                "error": error,
            }
        )


THEME_META = {
    "极光浅色": {
        "dark": False,
        "window": "#F1F4F8",
        "panel": "#FFFFFF",
        "panel_alt": "#F7F9FC",
        "input": "#FBFCFE",
        "border": "#DCE2EA",
        "border_strong": "#C8D0DC",
        "text": "#1B2430",
        "muted": "#687386",
        "accent": "#4E63D8",
        "accent_hover": "#3F51C4",
        "accent_text": "#FFFFFF",
        "selection": "#E4E8FF",
        "scroll": "#BAC4D2",
        "scroll_hover": "#96A3B5",
        "canvas": "#E8EDF4",
        "stage": "#DDE4ED",
        "slide": "#FFFFFF",
        "slot": "#F6F8FB",
    },
    "雾银灰": {
        "dark": False,
        "window": "#ECEEF1",
        "panel": "#F8F9FA",
        "panel_alt": "#F1F2F4",
        "input": "#FFFFFF",
        "border": "#D2D5DA",
        "border_strong": "#BABFC7",
        "text": "#25282D",
        "muted": "#6F747C",
        "accent": "#3F4752",
        "accent_hover": "#2E343C",
        "accent_text": "#FFFFFF",
        "selection": "#E0E3E7",
        "scroll": "#B2B7BF",
        "scroll_hover": "#9299A3",
        "canvas": "#E1E4E8",
        "stage": "#D5D9DE",
        "slide": "#FFFFFF",
        "slot": "#F3F4F6",
    },
    "深空暗色": {
        "dark": True,
        "window": "#111419",
        "panel": "#1A1E25",
        "panel_alt": "#151920",
        "input": "#12161C",
        "border": "#2B323C",
        "border_strong": "#3A4350",
        "text": "#EDF1F7",
        "muted": "#98A2B2",
        "accent": "#7C8CF2",
        "accent_hover": "#93A0FF",
        "accent_text": "#0D1020",
        "selection": "#2B3459",
        "scroll": "#404957",
        "scroll_hover": "#596575",
        "canvas": "#0E1116",
        "stage": "#151A21",
        "slide": "#20252D",
        "slot": "#272D36",
    },
    "海洋蓝": {
        "dark": False,
        "window": "#F1F4F6",
        "panel": "#FFFFFF",
        "panel_alt": "#F5F8F9",
        "input": "#FAFCFD",
        "border": "#D4DEE2",
        "border_strong": "#BCCBD0",
        "text": "#1B2D33",
        "muted": "#65787F",
        "accent": "#147D91",
        "accent_hover": "#0C687B",
        "accent_text": "#FFFFFF",
        "selection": "#DCEEEF",
        "scroll": "#AABCC2",
        "scroll_hover": "#849DA5",
        "canvas": "#E8EEF0",
        "stage": "#DDE6E9",
        "slide": "#FFFFFF",
        "slot": "#F5F8F9",
    },
    "珊瑚暮色": {
        "dark": True,
        "window": "#151416",
        "panel": "#201D20",
        "panel_alt": "#1A181B",
        "input": "#131215",
        "border": "#393338",
        "border_strong": "#52474D",
        "text": "#F4EFF1",
        "muted": "#B1A5AA",
        "accent": "#F06A6A",
        "accent_hover": "#FF8580",
        "accent_text": "#211011",
        "selection": "#44292E",
        "scroll": "#564A50",
        "scroll_hover": "#706168",
        "canvas": "#111114",
        "stage": "#18171A",
        "slide": "#252125",
        "slot": "#2B262B",
    },
}

THEME_ALIASES = {
    "石墨专业": "雾银灰",
    "翡翠绿": "海洋蓝",
    "赛博青": "深空暗色",
    "紫晶夜": "珊瑚暮色",
}


def normalize_theme_name(name):
    value = THEME_ALIASES.get(str(name or ""), str(name or ""))
    return value if value in THEME_META else "极光浅色"


def build_theme_qss(name: str) -> str:
    """
    UI-05-35A 专业视觉系统。

    只统一外观、尺寸和视觉层级，不改变现有功能逻辑。
    """
    c = THEME_META.get(
        name,
        THEME_META["极光浅色"],
    )

    arrow_path = resource_path(
        "resources/chevron-down.svg"
    ).replace(chr(92), "/")

    return f"""
* {{
    outline: none;
}}

QMainWindow,
QWidget#Root,
QDialog {{
    background-color: {c["window"]};
    color: {c["text"]};
}}

QWidget {{
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    color: {c["text"]};
}}

QWidget#LeftPanel,
QWidget#RightPanel {{
    background-color: transparent;
}}

QScrollArea#LeftPanelScroll,
QScrollArea#LeftPanelScroll > QWidget > QWidget {{
    background-color: transparent;
    border: none;
}}

/* =========================================================
   UI-05-42B FIX03
   Compact left sidebar
   ========================================================= */

QWidget#LeftPanel {{
    font-size: 11px;
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader {{
    min-height: 29px;
    max-height: 29px;
    border-radius: 7px;
    padding: 0 7px;
    font-size: 11px;
    font-weight: 700;
}}

QWidget#LeftPanel QLabel#SectionTitle {{
    font-size: 11px;
    min-height: 18px;
    max-height: 18px;
    padding-bottom: 0;
}}

QWidget#LeftPanel QLabel#ImportLead {{
    font-size: 11px;
    padding: 0;
}}

QWidget#LeftPanel QLabel#ImportHint {{
    font-size: 9px;
    padding: 0;
}}

QWidget#LeftPanel QLabel#ImportCountBadge {{
    min-height: 18px;
    max-height: 18px;
    border-radius: 7px;
    padding: 0 6px;
    font-size: 9px;
}}

QWidget#LeftPanel QPushButton#ImageImportPrimary {{
    min-height: 31px;
    max-height: 31px;
    border-radius: 8px;
    padding: 0 8px;
    font-size: 11px;
}}

QWidget#LeftPanel QPushButton#ImageImportSecondary {{
    min-height: 31px;
    max-height: 31px;
    border-radius: 8px;
    padding: 0 8px;
    font-size: 11px;
}}

QWidget#LeftPanel QLineEdit,
QWidget#LeftPanel QComboBox,
QWidget#LeftPanel QSpinBox,
QWidget#LeftPanel QDoubleSpinBox {{
    min-height: 24px;
    padding: 3px 5px;
    border-radius: 7px;
    font-size: 11px;
}}

QWidget#LeftPanel QComboBox::drop-down {{
    width: 22px;
}}

QWidget#LeftPanel QCheckBox {{
    min-height: 22px;
    spacing: 5px;
    font-size: 10px;
}}

QWidget#LeftPanel QPushButton {{
    min-height: 28px;
    padding: 2px 7px;
    border-radius: 7px;
    font-size: 10px;
}}

QWidget#LeftPanel QLabel#HeroSub {{
    font-size: 10px;
}}

QWidget#LeftPanel QLabel#InfoBadge {{
    padding: 2px 6px;
    font-size: 9px;
    border-radius: 7px;
}}

QWidget#LeftPanel QSlider {{
    min-height: 16px;
    max-height: 18px;
}}

QWidget#LeftPanel QLabel#PanelSubhead {{
    color: {c["muted"]};
    font-size: 9px;
    font-weight: 700;
    padding: 2px 0 0 0;
}}

QWidget#LeftPanel QLabel#FieldCaption {{
    color: {c["muted"]};
    font-size: 9px;
    padding: 0 0 1px 1px;
}}

QWidget#LeftPanel QFrame#PanelDivider {{
    min-height: 1px;
    max-height: 1px;
    background-color: {c["border"]};
    border: none;
    margin: 1px 0;
}}

QWidget#LeftPanel QDoubleSpinBox#CompactField {{
    min-width: 0;
    min-height: 25px;
    max-height: 27px;
    padding: 1px 17px 1px 4px;
    border-radius: 7px;
    font-size: 9px;
}}

QWidget#LeftPanel QDoubleSpinBox#CompactField::up-button,
QWidget#LeftPanel QDoubleSpinBox#CompactField::down-button {{
    width: 15px;
}}

QWidget#LeftPanel QComboBox#CompactField {{
    min-height: 28px;
    max-height: 30px;
}}

QWidget#LeftPanel QPushButton#CompactUtility {{
    min-width: 0;
    min-height: 25px;
    max-height: 27px;
    padding: 1px 5px;
}}

QWidget#LeftPanel QSlider#TransformSlider {{
    min-height: 20px;
    max-height: 22px;
}}

/* =========================================================
   Top command area
   ========================================================= */

QFrame#CommandBar {{
    background-color: {c["panel"]};
    border: 1px solid {c["border"]};
    border-radius: 12px;
}}

QFrame#ToolbarDivider {{
    background-color: {c["border"]};
    border: none;
    min-width: 1px;
    max-width: 1px;
}}

QLabel#CompactTitle {{
    font-size: 17px;
    font-weight: 800;
    color: {c["text"]};
}}

QLabel#CompactSubTitle {{
    font-size: 10px;
    font-weight: 500;
    color: {c["muted"]};
}}

QPushButton#CompactCommandButton {{
    min-width: 48px;
    min-height: 32px;
    padding: 0 10px;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {c["text"]};
    font-weight: 600;
}}

QPushButton#CompactCommandButton:hover {{
    background-color: {c["panel_alt"]};
    border-color: {c["border"]};
}}

QPushButton#CompactCommandButton:pressed {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
}}

QPushButton#CompactCommandButton:disabled {{
    color: {c["muted"]};
    background-color: transparent;
    border-color: transparent;
}}

QToolButton#ThemeIconButton {{
    background-color: {c["panel_alt"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 9px;
    padding: 3px;
}}

QToolButton#ThemeIconButton:hover {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
}}

QToolButton#ThemeIconButton:pressed {{
    background-color: {c["border"]};
}}

QToolButton#ThemeIconButton::menu-indicator {{
    image: none;
    width: 0;
    height: 0;
}}

QToolButton#ImportSplitButton {{
    min-height: 32px;
    color: {c["accent_text"]};
    background-color: {c["accent"]};
    border: 1px solid {c["accent"]};
    border-radius: 9px;
    padding: 0 27px 0 13px;
    font-size: 12px;
    font-weight: 800;
}}

QToolButton#ImportSplitButton:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
}}

QToolButton#ImportSplitButton:pressed {{
    background-color: {c["accent"]};
}}

QToolButton#ImportSplitButton::menu-button {{
    width: 24px;
    border-left: 1px solid {c["border_strong"]};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}

QToolButton#ImportSplitButton::menu-arrow {{
    image: url("{arrow_path}");
    width: 11px;
    height: 11px;
}}

/* =========================================================
   Cards and collapsible panels
   ========================================================= */

QFrame#Card,
QFrame#ProjectCard,
QFrame#ImageImportCard,
QFrame#AssetCard,
QFrame#WorkspaceCard,
QFrame#CountStrip,
QFrame#ThumbnailControl {{
    background-color: {c["panel"]};
    border: 1px solid {c["border"]};
    border-radius: 11px;
}}

QFrame#WorkspaceCard {{
    border-color: {c["border_strong"]};
}}

QFrame#PageNavigatorStrip {{
    background-color: transparent;
    border: none;
}}

QLabel#NavigatorSideTitle {{
    color: {c["muted"]};
    background-color: {c["panel_alt"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 2px 1px;
    font-size: 9px;
    font-weight: 700;
}}

QFrame#ImageImportCard {{
    background-color: {c["panel"]};
    border: 1px solid {c["accent"]};
    border-radius: 13px;
}}

QLabel#ImportLead {{
    color: {c["text"]};
    font-size: 12px;
    font-weight: 700;
    padding: 0 2px;
}}

QLabel#ImportHint {{
    color: {c["muted"]};
    font-size: 10px;
    line-height: 1.4;
    padding: 0 2px;
}}

QLabel#ImportCountBadge {{
    color: {c["accent"]};
    background-color: {c["selection"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 9px;
    min-height: 22px;
    padding: 0 9px;
    font-size: 10px;
    font-weight: 800;
}}

QPushButton#ImageImportPrimary {{
    min-height: 44px;
    color: {c["accent_text"]};
    background-color: {c["accent"]};
    border: 1px solid {c["accent"]};
    border-radius: 10px;
    padding: 0 16px;
    font-size: 14px;
    font-weight: 800;
}}

QPushButton#ImageImportPrimary:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
}}

QPushButton#ImageImportPrimary:pressed {{
    background-color: {c["accent"]};
    padding-top: 2px;
}}

QPushButton#ImageImportSecondary {{
    min-height: 38px;
    color: {c["text"]};
    background-color: {c["panel_alt"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 10px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 750;
}}

QPushButton#ImageImportSecondary:hover {{
    color: {c["accent"]};
    background-color: {c["selection"]};
    border-color: {c["accent"]};
}}

QPushButton#ImageImportSecondary:pressed {{
    background-color: {c["border"]};
    padding-top: 2px;
}}

QToolButton#CollapsibleHeader {{
    min-height: 36px;
    background-color: transparent;
    color: {c["text"]};
    border: none;
    border-radius: 9px;
    padding: 0 11px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
}}

QToolButton#CollapsibleHeader:hover {{
    background-color: {c["panel_alt"]};
}}

QToolButton#CollapsibleHeader:checked {{
    color: {c["accent"]};
}}

QToolButton#CollapsibleHeader:pressed {{
    background-color: {c["selection"]};
}}

QWidget#CollapsibleContent {{
    background-color: transparent;
    border: none;
}}

QLabel {{
    background: transparent;
    color: {c["text"]};
}}

QLabel#HeroTitle {{
    font-size: 20px;
    font-weight: 800;
    color: {c["text"]};
}}

QLabel#HeroSub {{
    color: {c["muted"]};
}}

QLabel#SectionTitle {{
    font-size: 13px;
    font-weight: 750;
    color: {c["text"]};
    padding-bottom: 1px;
}}

QLabel#MiniSectionTitle {{
    font-size: 11px;
    font-weight: 650;
    color: {c["muted"]};
}}

QLabel#InfoBadge {{
    background-color: {c["selection"]};
    color: {c["accent"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 700;
}}

/* =========================================================
   Input controls
   ========================================================= */

QLineEdit,
QTextEdit,
QPlainTextEdit,
QListWidget,
QTreeWidget,
QTableWidget,
QComboBox,
QSpinBox,
QDoubleSpinBox {{
    background-color: {c["input"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {c["selection"]};
    selection-color: {c["text"]};
}}

QLineEdit {{
    min-height: 20px;
}}

QLineEdit:hover,
QComboBox:hover,
QSpinBox:hover,
QDoubleSpinBox:hover {{
    border-color: {c["accent"]};
}}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QListWidget:focus,
QTreeWidget:focus,
QTableWidget:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {{
    border: 1px solid {c["accent"]};
}}

QLineEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {{
    color: {c["muted"]};
    background-color: {c["panel_alt"]};
    border-color: {c["border"]};
}}

QLineEdit#ImageSearch {{
    min-height: 24px;
    border-radius: 9px;
    padding-left: 10px;
}}

QAbstractItemView {{
    background-color: {c["input"]};
    color: {c["text"]};
    alternate-background-color: {c["panel_alt"]};
    border: 1px solid {c["border_strong"]};
    selection-background-color: {c["selection"]};
    selection-color: {c["text"]};
}}

QAbstractItemView::item {{
    background-color: transparent;
    color: {c["text"]};
    border-radius: 7px;
    padding: 5px;
}}

QAbstractItemView::item:hover {{
    background-color: {c["panel_alt"]};
}}

QAbstractItemView::item:selected {{
    background-color: {c["selection"]};
    color: {c["text"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 29px;
    border-left: 1px solid {c["border_strong"]};
    background-color: {c["panel_alt"]};
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}}

QComboBox::down-arrow {{
    image: url("{arrow_path}");
    width: 13px;
    height: 13px;
}}

QComboBox QAbstractItemView {{
    background-color: {c["panel"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    padding: 4px;
    selection-background-color: {c["selection"]};
}}

QSpinBox#PageJump {{
    min-width: 54px;
    background-color: {c["input"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 8px;
    padding: 5px 7px;
}}

/* =========================================================
   Buttons
   ========================================================= */

QPushButton {{
    min-height: 20px;
    background-color: {c["panel_alt"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 8px;
    padding: 6px 11px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
}}

QPushButton:pressed {{
    background-color: {c["border"]};
}}

QPushButton:disabled {{
    color: {c["muted"]};
    background-color: {c["panel_alt"]};
    border-color: {c["border"]};
}}

QPushButton#Primary,
QToolButton#Primary {{
    min-height: 34px;
    color: {c["accent_text"]};
    font-weight: 800;
    border: 1px solid {c["accent"]};
    border-radius: 9px;
    padding: 0 14px;
    background-color: {c["accent"]};
}}

QPushButton#Primary:hover,
QToolButton#Primary:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
}}

QPushButton#Primary:pressed,
QToolButton#Primary:pressed {{
    background-color: {c["accent"]};
}}

QToolButton#Primary::menu-indicator {{
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: right center;
}}

QPushButton#IconActionButton {{
    min-height: 34px;
    font-size: 20px;
    font-weight: 750;
    padding: 2px;
    border-radius: 8px;
}}

QPushButton#IconActionButton:hover {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
}}

QPushButton#CompactStepperButton {{
    background-color: {c["panel_alt"]};
    color: {c["accent"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 0;
    padding: 0;
    font-size: 15px;
    font-weight: 800;
}}

QPushButton#CompactStepperButton:hover {{
    background-color: {c["selection"]};
}}

QSpinBox#CompactStepperValue,
QDoubleSpinBox#CompactStepperValue {{
    background-color: {c["input"]};
    color: {c["text"]};
    border-top: 1px solid {c["border_strong"]};
    border-bottom: 1px solid {c["border_strong"]};
    border-left: none;
    border-right: none;
    border-radius: 0;
    padding: 3px;
}}

QPushButton#StepperButton {{
    border-radius: 0;
    border: 1px solid {c["border_strong"]};
    background-color: {c["panel_alt"]};
    color: {c["accent"]};
    font-size: 16px;
    font-weight: 800;
    padding: 3px;
}}

QPushButton#StepperButton:hover {{
    background-color: {c["selection"]};
}}

QSpinBox#StepperValue,
QDoubleSpinBox#StepperValue {{
    border-radius: 0;
    border-left: none;
    border-right: none;
    background-color: {c["input"]};
    color: {c["text"]};
    padding: 5px;
}}

/* =========================================================
   Checkboxes, sliders and progress
   ========================================================= */

QCheckBox {{
    background: transparent;
    color: {c["text"]};
    spacing: 7px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c["border_strong"]};
    border-radius: 4px;
    background-color: {c["input"]};
}}

QCheckBox::indicator:hover {{
    border-color: {c["accent"]};
}}

QCheckBox::indicator:checked {{
    background-color: {c["accent"]};
    border-color: {c["accent"]};
}}

QSlider::groove:horizontal {{
    height: 5px;
    background-color: {c["border_strong"]};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background-color: {c["accent"]};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background-color: {c["panel"]};
    border: 2px solid {c["accent"]};
}}

QSlider::handle:horizontal:hover {{
    background-color: {c["selection"]};
}}

QProgressBar {{
    background-color: {c["border"]};
    border: none;
    border-radius: 3px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: 3px;
    background-color: {c["accent"]};
}}

/* =========================================================
   Asset list
   ========================================================= */

QListWidget#ImageList {{
    background-color: {c["input"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 9px;
    padding: 3px;
}}

QListWidget#ImageList::item {{
    min-height: 0;
    padding: 4px 6px;
    margin: 1px 0;
    border: 1px solid transparent;
    border-radius: 7px;
}}

QListWidget#ImageList::item:hover {{
    background-color: {c["panel_alt"]};
    border-color: {c["border"]};
}}

QListWidget#ImageList::item:selected {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
    color: {c["text"]};
}}

QListWidget#PageNavigatorList {{
    border: none;
    background: transparent;
    padding: 2px;
}}

QListWidget#PageNavigatorList::item {{
    border: 1px solid {c["border"]};
    border-radius: 6px;
    background: {c["panel"]};
    padding: 3px;
    margin: 1px;
    color: {c["muted"]};
}}

QListWidget#PageNavigatorList::item:hover {{
    border-color: {c["border_strong"]};
    background: {c["panel_alt"]};
    color: {c["text"]};
}}

QListWidget#PageNavigatorList::item:selected {{
    border: 2px solid {c["accent"]};
    background: {c["selection"]};
    color: {c["text"]};
}}

QPushButton#PageNavigatorAddButton {{
    font-size: 25px;
    font-weight: 900;
    border: 1px solid {c["border_strong"]};
    border-bottom: 3px solid {c["border_strong"]};
    border-radius: 12px;
    background: {c["panel"]};
    color: {c["text"]};
    padding: 0;
}}

QPushButton#PageNavigatorAddButton:hover {{
    border-color: {c["accent"]};
    color: {c["accent"]};
    background: {c["selection"]};
}}

QPushButton#PageNavigatorAddButton:pressed {{
    border-bottom-width: 1px;
    background: {c["panel_alt"]};
    padding-top: 2px;
}}

/* =========================================================
   Menus, toolbars and scrollbars
   ========================================================= */

QToolBar {{
    background-color: {c["panel"]};
    color: {c["text"]};
    border: none;
    border-bottom: 1px solid {c["border"]};
    padding: 6px;
    spacing: 6px;
}}

QToolBar QToolButton {{
    background-color: transparent;
    color: {c["text"]};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 9px;
}}

QToolBar QToolButton:hover {{
    background-color: {c["selection"]};
    border-color: {c["border_strong"]};
}}

QMenuBar {{
    background-color: {c["panel"]};
    color: {c["text"]};
}}

QMenuBar::item:selected {{
    background-color: {c["selection"]};
}}

QMenu {{
    background-color: {c["panel"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 8px;
    padding: 5px;
}}

QMenu::item {{
    min-height: 24px;
    padding: 5px 28px 5px 10px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background-color: {c["selection"]};
    color: {c["text"]};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c["border"]};
    margin: 5px 7px;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 2px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {c["scroll"]};
    min-height: 34px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c["scroll_hover"]};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 2px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {c["scroll"]};
    min-width: 34px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c["scroll_hover"]};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* =========================================================
   Workspace, splitters, docks and status
   ========================================================= */

QSplitter::handle {{
    background-color: transparent;
}}

QSplitter::handle:hover {{
    background-color: {c["accent"]};
}}

QFrame#WorkspaceFooter {{
    background-color: {c["panel_alt"]};
    border: 1px solid {c["border"]};
    border-radius: 9px;
}}

QToolButton#PageNavButton,
QToolButton#IconActionButton,
QToolButton#PanelMenuButton {{
    background-color: transparent;
    color: {c["text"]};
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0;
    font-weight: 750;
}}

QToolButton#PageNavButton:hover,
QToolButton#IconActionButton:hover,
QToolButton#PanelMenuButton:hover {{
    background-color: {c["selection"]};
    border-color: {c["border_strong"]};
}}

QToolButton#PanelMenuButton::menu-indicator {{
    image: none;
    width: 0;
}}

QLabel#PageTotal {{
    color: {c["muted"]};
    padding: 0 2px;
}}

QDockWidget {{
    background-color: {c["window"]};
    color: {c["text"]};
    border: 1px solid {c["border"]};
}}

QDockWidget::title {{
    background-color: {c["panel"]};
    color: {c["text"]};
    border-bottom: 1px solid {c["border"]};
    padding: 8px 12px;
    font-weight: 700;
}}

QStatusBar {{
    min-height: 25px;
    background-color: {c["panel"]};
    color: {c["muted"]};
    border-top: 1px solid {c["border"]};
}}

QStatusBar QLabel {{
    color: {c["muted"]};
    padding: 0 7px;
}}

QLabel#StatusMetric {{
    color: {c["muted"]};
    border-left: 1px solid {c["border"]};
}}

QLabel#StatusProjectMetric {{
    color: {c["accent"]};
    font-weight: 700;
    border-left: 1px solid {c["border"]};
}}

QTabWidget#Ribbon {{
    background-color: transparent;
}}

QTabWidget#Ribbon::pane {{
    background-color: {c["panel"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
}}

QTabWidget#Ribbon QTabBar::tab {{
    background-color: {c["panel_alt"]};
    color: {c["text"]};
    padding: 7px 17px;
    border: 1px solid {c["border"]};
    border-bottom: none;
}}

QTabWidget#Ribbon QTabBar::tab:selected {{
    background-color: {c["panel"]};
    color: {c["accent"]};
}}

QToolTip {{
    background-color: {c["panel"]};
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-radius: 6px;
    padding: 6px 8px;
}}

QMessageBox {{
    background-color: {c["window"]};
}}

QMessageBox QLabel {{
    color: {c["text"]};
}}

QMessageBox QPushButton {{
    min-width: 82px;
}}
"""




def shorten_filename(filename, max_length=24):
    """UI-05-10 文件名显示截断"""
    if not filename:
        return ""
    if len(filename) <= max_length:
        return filename
    return filename[:max_length] + "..."



# UI-05-14-A External Image Drop Support
# Enable external image files from Windows Explorer to be accepted by image list.

IMAGE_DROP_EXTENSIONS = set(
    SUPPORTED_IMAGE_EXTENSIONS
)

def is_supported_image_path(path):
    return is_supported_media_path(path)



class ExternalImageListWidget(QListWidget):
    """
    UI-05-23A 右侧图片列表拖入增强。

    - 内部拖动：继续调整图片顺序。
    - 外部拖入：鼠标移动时只显示插入线。
    - 只有松开鼠标后才真正导入。
    - 可拖入单张或多张图片。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_window = parent
        self._external_drop_row = -1
        self._internal_drop_row = -1
        self._internal_drop_affinity = ""

        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(True)
        # UI-05-39D：
        # InternalMove 在部分Windows / Qt组合中，
        # 列表已有项目后会拒绝后续外部文件拖入。
        #
        # DragDrop同时保留：
        # - 列表内部 MoveAction 排序；
        # - 外部资源管理器 CopyAction 连续导入。
        self.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self._restore_drop_ready_state()

    def _external_paths(self, event):
        paths = []

        if not event.mimeData().hasUrls():
            return paths

        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_image_path(path):
                paths.append(path)

        return paths

    def supportedDropActions(self):
        return (
            Qt.DropAction.CopyAction
            | Qt.DropAction.MoveAction
        )

    def startDrag(self, supported_actions):
        """Start one canonical FrameDeck drag for list and canvas targets."""
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag

        rows = sorted(
            {
                self.row(item)
                for item in self.selectedItems()
                if self.row(item) >= 0
            }
        )
        if not rows and self.currentRow() >= 0:
            rows = [self.currentRow()]
        if not rows:
            return

        indexes = [
            self.model().index(row, 0)
            for row in rows
            if self.model().index(row, 0).isValid()
        ]
        try:
            mime = self.model().mimeData(indexes) if indexes else None
        except Exception:
            mime = None
        if mime is None:
            mime = QMimeData()
        mime.setData(INTERNAL_IMAGE_ROWS_MIME, encode_drag_rows(rows))

        drag = QDrag(self)
        drag.setMimeData(mime)
        try:
            item = self.item(rows[0])
            if item is not None:
                size = self.iconSize()
                pixmap = item.icon().pixmap(max(56, size.width()), max(42, size.height()))
                if not pixmap.isNull():
                    drag.setPixmap(pixmap)
        except Exception:
            pass

        drag.exec(
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            Qt.DropAction.CopyAction,
        )

    def _is_internal_drag(self, event):
        return event.source() in {
            self,
            self.viewport(),
        }

    def _restore_drop_ready_state(self):
        """
        每次drop完成后恢复外部拖入状态。

        修复第一次拖入成功后，QListWidget残留在内部移动状态，
        导致第二次及后续拖入无效。
        """
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )
        self.setDropIndicatorShown(True)

    def _drop_target_at(self, pos, *, allow_swap=True):
        """
        返回：
            (插入行, 亲和方向)

        before：
            鼠标位于目标项上半部，目标组取“后一个项所属组”。

        after：
            鼠标位于目标项下半部，目标组取“前一个项所属组”。

        这样拖到两个分组交界处时：
        - 放在上一组最后一张图片下半部 -> 加入上一组
        - 放在下一组第一张图片上半部 -> 加入下一组
        """
        index = self.indexAt(
            pos
        )

        if not index.isValid():
            return (
                self.count(),
                "after",
            )

        row = index.row()
        rect = self.visualRect(
            index
        )

        relative_y = pos.y() - rect.top()
        edge_height = max(6, int(rect.height() * 0.25))

        if allow_swap and edge_height <= relative_y < rect.height() - edge_height:
            return (row, "swap")

        if relative_y >= rect.height() - edge_height:
            return (
                max(
                    0,
                    min(
                        row + 1,
                        self.count(),
                    ),
                ),
                "after",
            )

        return (
            max(
                0,
                min(
                    row,
                    self.count(),
                ),
            ),
            "before",
        )

    def _drop_row_at(self, pos):
        row, _affinity = (
            self._drop_target_at(
                pos,
                allow_swap=False,
            )
        )
        return row

    def _clear_internal_indicator(self):
        if self._internal_drop_row != -1 or self._internal_drop_affinity:
            self._internal_drop_row = -1
            self._internal_drop_affinity = ""
            self.viewport().update()

    def _clear_external_indicator(self):
        if self._external_drop_row != -1:
            self._external_drop_row = -1
            self.viewport().update()

    def dragEnterEvent(self, event):
        if self._is_internal_drag(event):
            # 内部拖拽仍使用Qt默认指示器；
            # 最终落点由FrameDeck手动处理。
            super().dragEnterEvent(event)

            if event.isAccepted():
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
            row, affinity = self._drop_target_at(event.position().toPoint())
            self._internal_drop_row = row
            self._internal_drop_affinity = affinity
            self.viewport().update()
            return

        paths = self._external_paths(event)

        if not paths:
            event.ignore()
            return

        self._external_drop_row = self._drop_row_at(
            event.position().toPoint()
        )
        self.viewport().update()

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragMoveEvent(self, event):
        if self._is_internal_drag(event):
            super().dragMoveEvent(event)

            if event.isAccepted():
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
            row, affinity = self._drop_target_at(event.position().toPoint())
            if (row, affinity) != (
                self._internal_drop_row,
                self._internal_drop_affinity,
            ):
                self._internal_drop_row = row
                self._internal_drop_affinity = affinity
                self.viewport().update()
            return

        paths = self._external_paths(event)

        if not paths:
            self._clear_external_indicator()
            event.ignore()
            return

        row = self._drop_row_at(
            event.position().toPoint()
        )

        if row != self._external_drop_row:
            self._external_drop_row = row
            self.viewport().update()

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._clear_external_indicator()
        self._clear_internal_indicator()
        self._restore_drop_ready_state()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self._restore_drop_ready_state()

    def dropEvent(self, event):
        """
        列表内部拖动继续排序；外部文件可连续拖入。

        无论成功、重复图片、无效格式或异常，
        都在finally中重新恢复拖放状态。
        """
        try:
            if self._is_internal_drag(event):
                self._clear_external_indicator()

                insert_row, affinity = (
                    self._drop_target_at(
                        event.position().toPoint()
                    )
                )

                selected_rows = sorted(
                    {
                        self.row(item)
                        for item in self.selectedItems()
                        if self.row(item) >= 0
                    }
                )

                handled = False

                if (
                    selected_rows
                    and self.main_window
                    and hasattr(
                        self.main_window,
                        "handle_image_list_internal_drop",
                    )
                ):
                    handled = bool(
                        self.main_window
                        .handle_image_list_internal_drop(
                            selected_rows,
                            insert_row,
                            affinity=affinity,
                        )
                    )

                if handled:
                    # UI-05-43D FIX01：
                    # FrameDeck 已经在
                    # handle_image_list_internal_drop()
                    # 中手动完成：
                    # - QListWidget项目重排
                    # - 分组归属更新
                    # - 分页边界更新
                    #
                    # 这里不能再向 Qt 返回 MoveAction。
                    # QAbstractItemView 的拖动源收到 MoveAction 后，
                    # 会继续执行一次“删除源项目”的默认清理，
                    # 结果就是跨组拖拽成功后图片又被删掉。
                    #
                    # 返回 CopyAction 仅用于阻止 Qt 二次删除；
                    # FrameDeck 数据层实际仍然是移动操作。
                    event.setDropAction(
                        Qt.DropAction.CopyAction
                    )
                    event.accept()
                else:
                    event.ignore()

                return

            paths = self._external_paths(event)
            insert_row = self._drop_row_at(
                event.position().toPoint()
            )
            self._clear_external_indicator()

            if not paths:
                event.ignore()
                return

            if (
                self.main_window
                and hasattr(
                    self.main_window,
                    "handle_image_list_external_drop",
                )
            ):
                inserted = (
                    self.main_window
                    .handle_image_list_external_drop(
                        paths,
                        insert_row,
                    )
                )

                # 重复图片也需要完整结束本次外部拖动。
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
                event.accept()

                if inserted:
                    self.setCurrentRow(
                        max(
                            0,
                            min(
                                insert_row,
                                self.count() - 1,
                            ),
                        )
                    )
                return

            event.ignore()

        finally:
            self._clear_external_indicator()
            self._clear_internal_indicator()
            self._restore_drop_ready_state()


    def paintEvent(self, event):
        super().paintEvent(event)

        if self._internal_drop_row >= 0:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            accent = QColor("#4F6CFF")
            painter.setPen(QPen(accent, 3))
            row = min(self._internal_drop_row, max(0, self.count() - 1))
            item = self.item(row) if self.count() else None
            if item is not None:
                rect = self.visualItemRect(item).adjusted(2, 2, -2, -2)
                if self._internal_drop_affinity == "swap":
                    painter.setBrush(QColor(79, 108, 255, 42))
                    painter.drawRoundedRect(rect, 4, 4)
                else:
                    y = rect.bottom() + 2 if self._internal_drop_affinity == "after" else rect.top() - 2
                    painter.drawLine(8, y, max(28, self.viewport().width() - 8), y)
            painter.end()

        row = self._external_drop_row
        if row < 0:
            return

        painter = QPainter(self.viewport())
        accent = QColor("#5B5CE2")
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )
        painter.setPen(
            QPen(
                accent,
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )

        left = 8
        right = max(left + 20, self.viewport().width() - 8)

        if self.count() <= 0:
            y = 12
        elif row <= 0:
            rect = self.visualItemRect(self.item(0))
            y = rect.top()
        elif row >= self.count():
            rect = self.visualItemRect(
                self.item(self.count() - 1)
            )
            y = rect.bottom() + 1
        else:
            rect = self.visualItemRect(self.item(row))
            y = rect.top()

        painter.drawLine(left, y, right, y)

class PPTWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = dict(settings or {})

    def _compatible_generate_kwargs(self):
        """
        根据当前 core.ppt_generator.generate_ppt() 的真实签名，
        自动移除界面预览专用或旧版本不支持的参数。

        这样即使主界面和 ppt_generator.py 版本稍有差异，
        也不会因为 show_grid 等无效关键字导致生成中断。
        """
        call_kwargs = dict(self.settings)
        call_kwargs["progress_callback"] = (
            self.progress.emit
        )
        call_kwargs["log_callback"] = self.log.emit

        try:
            signature = inspect.signature(
                generate_ppt
            )
        except (TypeError, ValueError):
            return call_kwargs, []

        parameters = signature.parameters

        accepts_var_kwargs = any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

        if accepts_var_kwargs:
            return call_kwargs, []

        accepted_names = {
            name
            for name, parameter in parameters.items()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }

        filtered = {
            name: value
            for name, value in call_kwargs.items()
            if name in accepted_names
        }
        ignored = sorted(
            set(call_kwargs) - set(filtered)
        )

        return filtered, ignored

    def run(self):
        try:
            call_kwargs, ignored = (
                self._compatible_generate_kwargs()
            )

            if ignored:
                self.log.emit(
                    "已忽略当前 PPT 生成器不支持的参数："
                    + ", ".join(ignored)
                )

            result = generate_ppt(**call_kwargs)
            self.finished_ok.emit(result)

        except PermissionError as error:
            self.failed.emit(
                "PPT_OUTPUT_PERMISSION::"
                + str(error)
            )

        except Exception:
            self.failed.emit(
                traceback.format_exc()
            )


class PPTImportWorker(QThread):
    """
    PPT图片提取后台线程。

    PPT解析、媒体读取和文件写入都不阻塞主界面。
    """
    progress = Signal(int, int, str)
    finished_ok = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        ppt_path,
        parent=None,
    ):
        super().__init__(parent)
        self.ppt_path = str(
            ppt_path
        )

    def run(self):
        try:
            result = extract_ppt_images(
                self.ppt_path,
                progress_callback=(
                    self.progress.emit
                ),
                cancel_callback=(
                    self.isInterruptionRequested
                ),
            )

            if result.get(
                "cancelled"
            ):
                self.cancelled.emit()
                return

            self.finished_ok.emit(
                result
            )

        except Exception:
            self.failed.emit(
                traceback.format_exc()
            )


class DropLineEdit(QLineEdit):
    folder_dropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖入图片文件夹，或点击浏览")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.setText(path)
                self.folder_dropped.emit(path)


class CollapsibleCard(QFrame):
    """
    可折叠功能卡片。

    标题栏整行都可以点击，折叠后只保留标题，
    展开后显示原有功能控件。
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        expanded: bool = True,
        parent=None,
    ):
        super().__init__(parent)

        self._title = str(title)
        self._language = "zh_CN"
        self.setObjectName("Card")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.header_button = QToolButton(self)
        self.header_button.setObjectName(
            "CollapsibleHeader"
        )
        self.header_button.setCheckable(True)
        self.header_button.setAutoRaise(False)
        self.header_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.header_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.header_button.setMinimumHeight(29)
        self.header_button.setMaximumHeight(29)
        self.header_button.toggled.connect(
            self._on_header_toggled
        )

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName(
            "CollapsibleContent"
        )
        self.content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.content_layout = QVBoxLayout(
            self.content_widget
        )
        self.content_layout.setContentsMargins(
            7,
            0,
            7,
            6,
        )
        self.content_layout.setSpacing(5)

        root_layout.addWidget(self.header_button)
        root_layout.addWidget(self.content_widget)

        self.set_expanded(
            expanded,
            emit_signal=False,
        )

    def _update_header_text(self):
        arrow = "▾" if self.is_expanded() else "▸"
        display_title = translate_ui_text(
            self._title,
            self._language,
        )
        self.header_button.setText(
            f"{arrow}  {display_title}"
        )
        state_text = (
            "收起"
            if self.is_expanded()
            else "展开"
        )
        self.header_button.setToolTip(
            translate_ui_text(
                f"点击{state_text}{self._title}",
                self._language,
            )
        )

    def set_language(self, language):
        self._language = (
            "en_US"
            if str(language).lower().startswith("en")
            else "zh_CN"
        )
        self._update_header_text()

    def _on_header_toggled(self, expanded):
        expanded = bool(expanded)
        self.content_widget.setVisible(
            expanded
        )

        if expanded:
            # 先解除旧约束，重新激活布局。
            self.setMinimumHeight(
                self.header_button.height()
            )
            self.content_layout.invalidate()
            self.content_layout.activate()
            self.content_widget.adjustSize()

            self.setMinimumHeight(
                self.header_button.height()
                + self.content_widget.sizeHint().height()
            )
        else:
            self.setMinimumHeight(
                self.header_button.height()
            )

        self._update_header_text()
        self.updateGeometry()
        self.toggled.emit(
            expanded
        )

    def set_expanded(
        self,
        expanded: bool,
        *,
        emit_signal: bool = True,
    ):
        expanded = bool(expanded)

        previous = self.header_button.blockSignals(
            not emit_signal
        )
        self.header_button.setChecked(expanded)
        self.header_button.blockSignals(previous)

        self.content_widget.setVisible(
            expanded
        )

        if expanded:
            self.setMinimumHeight(
                self.header_button.height()
            )
            self.content_layout.invalidate()
            self.content_layout.activate()
            self.content_widget.adjustSize()

            self.setMinimumHeight(
                self.header_button.height()
                + self.content_widget.sizeHint().height()
            )
        else:
            self.setMinimumHeight(
                self.header_button.height()
            )

        self._update_header_text()
        self.updateGeometry()

        if emit_signal:
            self.toggled.emit(expanded)

    def is_expanded(self) -> bool:
        return self.header_button.isChecked()



class GroupManagerDialog(QDialog):
    """UI-05-45A 精简分组整理器。"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

        self.setWindowTitle("整理分组")
        self.setModal(True)
        self.resize(560, 460)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("当前工程分组")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("ImportHint")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.group_list = QListWidget()
        self.group_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.group_list.setAlternatingRowColors(True)
        self.group_list.setMinimumHeight(250)
        root.addWidget(self.group_list, 1)

        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self.locate_btn = QPushButton("定位")
        self.rename_btn = QPushButton("重命名")
        self.split_btn = QPushButton("当前页设为新分组")

        row1.addWidget(self.locate_btn)
        row1.addWidget(self.rename_btn)
        row1.addWidget(self.split_btn, 1)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self.merge_prev_btn = QPushButton("与上一组合并")
        self.merge_next_btn = QPushButton("与下一组合并")
        self.close_btn = QPushButton("关闭")

        row2.addWidget(self.merge_prev_btn)
        row2.addWidget(self.merge_next_btn)
        row2.addStretch(1)
        row2.addWidget(self.close_btn)
        root.addLayout(row2)

        note = QLabel(
            "说明：分组只记录图片归属与分页边界；不会复制、删除或修改原图片。"
        )
        note.setObjectName("ImportHint")
        note.setWordWrap(True)
        root.addWidget(note)

        self.group_list.currentItemChanged.connect(self._sync_buttons)
        self.group_list.itemDoubleClicked.connect(
            lambda _item: self._rename_selected()
        )

        self.locate_btn.clicked.connect(self._locate_selected)
        self.rename_btn.clicked.connect(self._rename_selected)
        self.split_btn.clicked.connect(self._split_current_page)
        self.merge_prev_btn.clicked.connect(
            lambda: self._merge_selected(-1)
        )
        self.merge_next_btn.clicked.connect(
            lambda: self._merge_selected(1)
        )
        self.close_btn.clicked.connect(self.accept)

        self.refresh()

    def _selected_group_id(self):
        item = self.group_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def refresh(self, *, select_group_id=""):
        rows = self.main_window._group_manager_rows()

        current_group_id = str(
            select_group_id
            or self._selected_group_id()
            or self.main_window._current_group_id_for_manager()
            or ""
        )

        self.group_list.blockSignals(True)
        self.group_list.clear()

        selected_row = -1
        english = self.main_window._language == "en_US"

        for row_index, row in enumerate(rows):
            lock_prefix = (
                ("[Lock] " if english else "[锁] ")
                if row.get(
                    "locked",
                    False,
                )
                else ""
            )

            if english:
                item_text = (
                    f"{row['ordinal']:02d}  {lock_prefix}{row['name']}\n"
                    f"      {row['image_count']} images"
                    f" · about {row['page_count']} pages"
                    f" · range {row['start'] + 1}–{row['end']}"
                )
                item_tip = (
                    f"Group: {row['name']}\n"
                    f"Image index: {row['start'] + 1}–{row['end']}\n"
                    f"Image count: {row['image_count']}"
                )
            else:
                item_text = (
                    f"{row['ordinal']:02d}  {lock_prefix}{row['name']}\n"
                    f"      图片 {row['image_count']} 张"
                    f" · 约 {row['page_count']} 页"
                    f" · 范围 {row['start'] + 1}–{row['end']}"
                )
                item_tip = (
                    f"分组：{row['name']}\n"
                    f"图片索引：{row['start'] + 1}–{row['end']}\n"
                    f"图片数量：{row['image_count']}"
                )

            item = QListWidgetItem(item_text)
            item.setData(
                Qt.ItemDataRole.UserRole,
                row["id"],
            )
            item.setToolTip(item_tip)
            self.group_list.addItem(item)

            if row["id"] == current_group_id:
                selected_row = row_index

        self.group_list.blockSignals(False)

        if selected_row < 0 and self.group_list.count() > 0:
            selected_row = 0

        if selected_row >= 0:
            self.group_list.setCurrentRow(selected_row)

        if english:
            self.summary_label.setText(
                f"{len(rows)} groups\n"
                "Drag images in the right list for everyday rearranging. "
                "Use these controls only to rename or change group boundaries."
            )
        else:
            self.summary_label.setText(
                (
                    f"共 {len(rows)} 个分组\n"
                    "日常调整直接在右侧列表拖动图片；这里只用于重命名或整理分组边界。"
                )
            )

        self._sync_buttons()

    def _sync_buttons(self, *_args):
        row = self.group_list.currentRow()
        count = self.group_list.count()
        has_selection = 0 <= row < count

        self.locate_btn.setEnabled(has_selection)
        self.rename_btn.setEnabled(has_selection)
        self.merge_prev_btn.setEnabled(has_selection and row > 0)
        self.merge_next_btn.setEnabled(
            has_selection and row < count - 1
        )
        self.split_btn.setEnabled(
            bool(self.main_window.visible_images())
        )

    def _locate_selected(self):
        group_id = self._selected_group_id()
        if group_id:
            self.main_window._locate_group(group_id)

    def _rename_selected(self):
        group_id = self._selected_group_id()
        if not group_id:
            return

        row = self.main_window._group_manager_row_by_id(group_id)
        if row is None:
            return

        new_name, accepted = QInputDialog.getText(
            self,
            "重命名分组",
            "分组名称：",
            QLineEdit.EchoMode.Normal,
            row["name"],
        )

        if not accepted:
            return

        new_name = str(new_name).strip()

        if not new_name:
            QMessageBox.information(
                self,
                "分组名称",
                "分组名称不能为空。",
            )
            return

        if self.main_window._rename_group(group_id, new_name):
            self.refresh(select_group_id=group_id)

    def _split_current_page(self):
        created_group_id = (
            self.main_window._create_group_at_current_page()
        )

        if created_group_id:
            self.refresh(select_group_id=created_group_id)

    def _merge_selected(self, direction):
        group_id = self._selected_group_id()
        if not group_id:
            return

        kept_group_id = (
            self.main_window._merge_group_with_neighbor(
                group_id,
                direction,
            )
        )

        if kept_group_id:
            self.refresh(select_group_id=kept_group_id)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.worker = None
        self._language = read_saved_language()
        self._language_runtime_ready = False
        self._language_refresh_pending = False
        self._language_refresh_roots = []

        # UI-05-41A：PPT图片素材导入任务。
        self.ppt_import_worker = None
        self.ppt_import_progress = None
        self._ppt_import_source = ""
        self._ppt_import_layout_mode = (
            PPT_IMPORT_MODE_GROUP_BY_SLIDE
        )

        self.images = []
        self.image_transforms = {}
        self.hidden_images = set()
        # 工程内图片剪贴板：保存图片项快照，不依赖系统文件剪贴板。
        self._image_clipboard = []
        self._image_clipboard_mode = "copy"
        self.current_project_file = ""

        # UI-05-37E：
        # 用工程内容签名判断关闭时是否存在未保存修改。
        self._saved_project_signature = None
        self._session_initial_signature = None
        self._close_in_progress = False

        self.selected_image_index = -1
        self.selected_image_indices: set[int] = set()
        self._selection_sync_lock = False

        # UI-05-28A：
        # 旧显式分页仍用于兼容页面操作。
        self._manual_page_breaks: set[int] = set()

        # UI-05-42A：
        # 分组分页与旧manual page breaks独立保存。
        # 精简版默认使用保留页面边界的分组排版；自动连续补满只在
        # 明确的导入流程中临时使用。
        self._pagination_mode = PAGINATION_GROUPED
        self._image_groups = []
        # 自动排版是一次可确认的排版事务。开启时保留完整工程快照：
        # 确认会固化新分页；直接取消勾选则恢复开启前版本。
        self._auto_layout_restore_state = None
        self._confirmed_auto_layout = False
        self._auto_layout_undo_depth = None

        # UI-05-42B FIX01：
        # 分组模式下，删除某页图片后保留该页原有结束位置。
        # 这是独立于 group start / manual page breaks 的页面锁，
        # 连续模式会忽略它，因此两种排版方式仍可自由切换。
        self._group_page_breaks: set[int] = set()

        # UI-05-42B FIX08：
        # 空白页被填入图片后，需要在原逻辑位置保持为独立图片页。
        # 该边界独立于旧 manual page breaks，并在连续/分组模式都生效。
        self._blank_fill_page_breaks: set[int] = set()

        # UI-05-43C：页面锁 / 分组锁
        self._page_lock_records: list[dict] = []
        self._locked_group_ids: set[str] = set()

        self._title_system = default_title_system()

        self.last_output_file = ""
        self.undo_stack = []
        self.redo_stack = []
        self._history_lock = False

        # UI-05-28A：
        # 排版参数变化使用一次性历史基线，避免滑块连续变化时
        # Ctrl+Z 无记录或产生大量重复记录。
        self._last_stable_history_state = None
        self._settings_history_pending = False

        # UI-05-30 Stage 02 crop transaction.
        self._crop_history_state = None
        self._crop_history_path = None

        # UI-05-30 Stage 02B：
        # 当前界面已经移除旧 zoom_combo，缩放状态改为独立保存。
        self._zoom_mode = "适应窗口"

        # UI-05-31A：图标式主题选择。
        self._theme_name = "极光浅色"
        self._theme_actions = {}

        # UI-05-40A：PPT / PDF / 页面图片统一选择输出文件夹。
        self._selected_export_format = "pptx"
        self._export_actions = {}
        self._last_export_directory = ""

        # Template System T-01。
        self._active_template_document = None
        self._active_template_id = ""
        self._template_actions = {}

        # UI-05-36A：高分辨率页面导出。
        # 450 DPI 的 16:9 页面约为 6000 × 3375 px。
        self._raster_export_dpi = 450

        # UI-05-37A：画布抓手拖动历史状态。
        self._canvas_pan_history_active = False

        self._raster_export_max_long_edge = 7680
        self._export_source_long_edge = 8192

        # UI-05-39B：
        # 全格式后台缩略图系统。
        self._image_cache = image_cache()
        self._thumbnail_generation = 0
        self._thumbnail_request_serial = 0
        self._thumbnail_pending = []
        self._thumbnail_item_refs = {}
        self._thumbnail_inflight = {}
        self._thumbnail_priority_dirty = True
        self._thumbnail_heavy_inflight = 0
        self._thumbnail_total = 0
        self._thumbnail_completed = 0
        self._thumbnail_failed = 0
        self._thumbnail_cancelled = False

        # 按当前电脑配置采用3个总线程；
        # HEIF/TIFF等重型解码最多同时2个。
        self._thumbnail_max_inflight = 3
        self._thumbnail_max_heavy_inflight = 2
        self._thumbnail_pool = QThreadPool(self)
        self._thumbnail_pool.setMaxThreadCount(
            self._thumbnail_max_inflight
        )
        self._thumbnail_pool.setExpiryTimeout(
            30000
        )

        self._thumbnail_dispatch_timer = QTimer(
            self
        )
        self._thumbnail_dispatch_timer.setSingleShot(
            True
        )
        self._thumbnail_dispatch_timer.timeout.connect(
            self._dispatch_thumbnail_jobs
        )

        self._thumbnail_priority_timer = QTimer(
            self
        )
        self._thumbnail_priority_timer.setSingleShot(
            True
        )
        self._thumbnail_priority_timer.setInterval(
            70
        )
        self._thumbnail_priority_timer.timeout.connect(
            self._reprioritize_thumbnail_jobs
        )

        self._thumbnail_progress_timer = QTimer(
            self
        )
        self._thumbnail_progress_timer.setSingleShot(
            True
        )
        self._thumbnail_progress_timer.setInterval(
            100
        )
        self._thumbnail_progress_timer.timeout.connect(
            self._update_thumbnail_progress_status
        )

        # Several thumbnail workers can finish within one UI frame. Merge
        # navigation invalidations so the main thread scans the image order
        # and computes its refresh signature only once per burst.
        self._thumbnail_navigation_dirty_paths = set()
        self._thumbnail_navigation_flush_timer = QTimer(self)
        self._thumbnail_navigation_flush_timer.setSingleShot(True)
        self._thumbnail_navigation_flush_timer.setInterval(160)
        self._thumbnail_navigation_flush_timer.timeout.connect(
            self._flush_navigation_thumbnail_invalidations
        )

        # UI-05-38A：避免同一次启动重复弹出HEIF依赖提示。
        self._heif_missing_notice_shown = False

        # UI-05-39A：
        # 页面导航缩略图使用独立离屏画布，不再切换真实中央画布。
        self._page_thumbnail_renderer = None
        self._page_thumbnail_render_queue = []
        self._page_thumbnail_target_signatures = {}
        self._page_thumbnail_refresh_generation = 0
        self._page_thumbnail_rendered_count = 0
        self._page_thumbnail_render_total = 0
        self._real_thumbnail_refresh_pending = False

        # 连续操作期间合并刷新请求，避免一次动作触发多轮重绘。
        self._page_thumbnail_debounce_timer = QTimer(self)
        self._page_thumbnail_debounce_timer.setSingleShot(True)
        self._page_thumbnail_debounce_timer.setInterval(180)
        self._page_thumbnail_debounce_timer.timeout.connect(
            self.refresh_real_page_thumbnails
        )

        # 每个事件循环只渲染一页导航缩略图。
        # 页面较多时仍可继续操作中央画布。
        self._page_thumbnail_render_timer = QTimer(self)
        self._page_thumbnail_render_timer.setSingleShot(True)
        self._page_thumbnail_render_timer.timeout.connect(
            self._process_page_thumbnail_queue
        )

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.refresh_preview)

        # Preview changes can arrive dozens of times while a slider is dragged.
        # Coalesce configuration persistence instead of rewriting the complete
        # JSON payload after every rendered frame.
        self._last_config_text = None
        self._config_save_timer = QTimer(self)
        self._config_save_timer.setSingleShot(True)
        self._config_save_timer.setInterval(400)
        self._config_save_timer.timeout.connect(self.save_config)
        # =====================================================
        # UI-05 Page Thumbnail Navigation
        #
        # 独立组件
        # 不影响 PreviewCanvas
        # =====================================================

        self.slide_thumbnail_bar = None

        # UI-05-29A：左侧可折叠功能区。
        self._collapsible_cards = {}

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000)
        self.autosave_timer.timeout.connect(self.autosave_project)
        self.autosave_timer.start()

        self.setWindowTitle("FrameDeck Studio · UI-05-45A FIX01")
        self.resize(1480, 920)
        self.setMinimumSize(1024, 650)

        self._build_toolbar()
        self._build_ui()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_images = QLabel("图片 0")
        self.status_page = QLabel("页面 1/1")
        self.status_zoom = QLabel("画布 100%")
        # Kept as a hidden compatibility object for older update paths.
        # Project state is shown only in the top command bar.
        self.status_project = QLabel("未保存", self)
        self.status_project.hide()

        for label in (
            self.status_images,
            self.status_page,
            self.status_zoom,
        ):
            label.setObjectName("StatusMetric")

        self.status_project.setObjectName(
            "StatusProjectMetric"
        )

        self.thumbnail_cancel_button = QPushButton(
            "停止缩略图"
        )
        self.thumbnail_cancel_button.setToolTip(
            "停止剩余后台缩略图任务；已导入图片不会被删除"
        )
        self.thumbnail_cancel_button.setFixedHeight(
            23
        )
        self.thumbnail_cancel_button.hide()
        self.thumbnail_cancel_button.clicked.connect(
            self.cancel_background_thumbnail_loading
        )

        self.status_bar.addPermanentWidget(
            self.thumbnail_cancel_button
        )
        self.status_bar.addPermanentWidget(self.status_images)
        self.status_bar.addPermanentWidget(self.status_page)
        self.status_bar.addPermanentWidget(self.status_zoom)

        self._connect_signals()
        self._build_shortcuts()
        self.disable_numeric_wheel()
        self.load_config()
        # UI-05-45A：启动即进入精简标题模型。旧工程中的副标题与
        # 页面 Logo 仍可被读取，但不再进入编辑、预览或导出流程。
        self._activate_simplified_title_model()
        self._install_language_runtime()

        # UI-05-37D：
        # 自动保存恢复必须在启动加载文件夹之前作出明确决定。
        #
        # restored：
        #   已按自动保存中的精确顺序恢复，不再调用 load_images，
        #   防止被配置文件中的旧文件夹重新覆盖。
        #
        # discarded / deferred：
        #   启动为空白工程，不再自动载入旧文件夹。
        #
        # none：
        #   没有可恢复数据，维持原来的文件夹自动加载逻辑。
        recovery_state = (
            self.maybe_offer_autosave_recovery()
        )

        self.apply_theme(
            self.current_theme_name(),
            persist=False,
        )

        # UI-05-40A：
        # 不再根据旧配置中的图片目录自动扫描文件夹。
        # 图片只通过“添加图片”、拖入、打开工程或恢复工程进入软件，
        # 避免系统隐藏文件和目录中的无关图片被自动加入。
        self.refresh_preview()

        # 记录本次启动完成后的基线。
        # 无工程文件但自动载入了图片时，仍会被视为未保存工程。
        self._session_initial_signature = (
            self._project_signature()
        )

        if self.current_project_file:
            self._saved_project_signature = (
                self._session_initial_signature
            )

        QTimer.singleShot(
            1600,
            self._prune_image_cache_if_due,
        )

    def _build_toolbar(self):
        # V11.1 uses only the Ribbon. The legacy toolbar was removed
        # to avoid duplicate menus and duplicated commands.
        self.undo_action = QAction("撤销", self)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction("重做", self)
        self.redo_action.triggered.connect(self.redo)

        self.log_action = QAction("显示日志", self)
        self.log_action.setCheckable(True)
        self.log_action.setChecked(False)
        self.log_action.triggered.connect(self.toggle_log_dock)

    def _install_language_runtime(self):
        """Install live translation for the main window and later dialogs."""
        if self._language_runtime_ready:
            return

        self._language_runtime_ready = True
        self.app.installEventFilter(self)
        self.set_language(self._language, persist=False)

    def _translate_after_event(self):
        roots = list(self._language_refresh_roots)
        self._language_refresh_roots = []
        self._language_refresh_pending = False
        for root in roots:
            try:
                self._translate_widget_tree(root)
            except RuntimeError:
                continue

    def _queue_widget_translation(self, root):
        if root is None:
            return
        if all(existing is not root for existing in self._language_refresh_roots):
            self._language_refresh_roots.append(root)
        if not self._language_refresh_pending:
            self._language_refresh_pending = True
            QTimer.singleShot(0, self._translate_after_event)

    def _translated(self, text):
        return translate_ui_text(text, self._language)

    def _translated_file_filter(self, text):
        value = str(text or "")
        if self._language != "en_US":
            return value
        for source, target in (
            ("全部支持图片", "All Supported Images"),
            ("HEIF / HEIC 图片", "HEIF / HEIC Images"),
            ("常规图片", "Standard Images"),
            ("PowerPoint 演示文稿", "PowerPoint Presentation"),
            ("启用宏的演示文稿", "Macro-enabled Presentation"),
            ("PowerPoint 文件", "PowerPoint Files"),
            ("旧版工程", "Legacy Project"),
            ("FrameDeck 工程", "FrameDeck Project"),
            ("FrameDeck 模板", "FrameDeck Template"),
        ):
            value = value.replace(source, target)
        return value

    def _translated_export_folder_title(self, label):
        if self._language == "en_US":
            return f"Choose {translate_ui_text(label, 'en_US')} Output Folder"
        return f"选择 {label} 输出文件夹"

    def _show_status(self, message, timeout=0):
        if hasattr(self, "status_bar"):
            self.status_bar.showMessage(
                translate_ui_text(message, self._language),
                timeout,
            )

    def _combo_source_text(self, combo):
        index = combo.currentIndex()
        if index < 0:
            return combo.currentText()
        source = combo.itemData(index, I18N_COMBO_SOURCE_ROLE)
        return str(source if source is not None else combo.itemText(index))

    def _find_combo_source_text(self, combo, source_text):
        source_text = str(source_text)
        for index in range(combo.count()):
            source = combo.itemData(index, I18N_COMBO_SOURCE_ROLE)
            if str(source if source is not None else combo.itemText(index)) == source_text:
                return index
        return combo.findText(source_text)

    def _translate_object(self, obj):
        language = self._language

        if isinstance(obj, QComboBox):
            # Font family names are data, not interface chrome.
            if obj is getattr(self, "title_font_combo", None):
                return
            blocked = obj.blockSignals(True)
            try:
                for index in range(obj.count()):
                    source = obj.itemData(index, I18N_COMBO_SOURCE_ROLE)
                    if source is None:
                        source = obj.itemText(index)
                        # If the combo was first discovered while English was active,
                        # recover a known Chinese source before storing it.
                        source = translate_ui_text(source, "zh_CN")
                        obj.setItemData(index, source, I18N_COMBO_SOURCE_ROLE)
                    target = (
                        translate_ui_text(source, language)
                        if language == "en_US"
                        else str(source)
                    )
                    if obj.itemText(index) != target:
                        obj.setItemText(index, target)
            finally:
                obj.blockSignals(blocked)

        elif isinstance(obj, (QLabel, QPushButton, QToolButton, QCheckBox)):
            current = obj.text()
            translated = translate_ui_text(current, language)
            if translated != current:
                obj.setText(translated)

        elif isinstance(obj, QAction):
            current = obj.text()
            translated = translate_ui_text(current, language)
            if translated != current:
                obj.setText(translated)
            for getter_name, setter_name in (
                ("toolTip", "setToolTip"),
                ("statusTip", "setStatusTip"),
            ):
                current = getattr(obj, getter_name)()
                translated = translate_ui_text(current, language)
                if translated != current:
                    getattr(obj, setter_name)(translated)

        if isinstance(obj, QMenu):
            current = obj.title()
            translated = translate_ui_text(current, language)
            if translated != current:
                obj.setTitle(translated)

        if isinstance(obj, QToolBox):
            for index in range(obj.count()):
                current = obj.itemText(index)
                translated = translate_ui_text(current, language)
                if translated != current:
                    obj.setItemText(index, translated)

        if isinstance(obj, QWidget):
            if obj.isWindow():
                current = obj.windowTitle()
                translated = translate_ui_text(current, language)
                if translated != current:
                    obj.setWindowTitle(translated)

            for getter_name, setter_name in (
                ("toolTip", "setToolTip"),
                ("statusTip", "setStatusTip"),
                ("accessibleName", "setAccessibleName"),
            ):
                getter = getattr(obj, getter_name, None)
                setter = getattr(obj, setter_name, None)
                if getter is None or setter is None:
                    continue
                current = getter()
                translated = translate_ui_text(current, language)
                if translated != current:
                    setter(translated)

            if isinstance(obj, QLineEdit):
                current = obj.placeholderText()
                translated = translate_ui_text(current, language)
                if translated != current:
                    obj.setPlaceholderText(translated)

    def _translate_widget_tree(self, root):
        self._translate_object(root)
        for obj in root.findChildren(QObject):
            self._translate_object(obj)

    def _translate_all_top_level_widgets(self):
        for widget in QApplication.topLevelWidgets():
            self._translate_widget_tree(widget)

        # QMenus and actions can remain parented but not visible.
        self._translate_widget_tree(self)

    def _sync_language_layout(self):
        """Keep translated controls readable without shrinking global text."""
        left_scroll = getattr(self, "left_scroll", None)
        splitter = getattr(self, "workspace_splitter", None)
        if left_scroll is None or splitter is None:
            return

        target_width = (
            LEFT_PANEL_WIDTH_EN
            if self._language == "en_US"
            else LEFT_PANEL_WIDTH_ZH
        )
        current_sizes = splitter.sizes()
        right_width = (
            current_sizes[2]
            if len(current_sizes) >= 3 and current_sizes[2] > 0
            else 170
        )
        total_width = sum(current_sizes)

        left_scroll.setFixedWidth(target_width)

        if total_width > 0:
            center_width = max(
                1,
                total_width - target_width - right_width,
            )
        else:
            center_width = 1110
        splitter.setSizes(
            [target_width, center_width, right_width]
        )

    def set_language(self, language, *, persist=True):
        language = "en_US" if str(language).lower().startswith("en") else "zh_CN"
        self._language = language

        for code, action in getattr(self, "_language_actions", {}).items():
            action.blockSignals(True)
            action.setChecked(code == language)
            action.blockSignals(False)

        button = getattr(self, "language_button", None)
        if button is not None:
            button.setText("EN" if language == "en_US" else "中")
            button.setToolTip(
                "Language: English" if language == "en_US" else "界面语言：中文"
            )

        for card in getattr(self, "_collapsible_cards", {}).values():
            card.set_language(language)

        self._translate_all_top_level_widgets()
        self._sync_import_button_language()
        self._sync_language_layout()
        preview = getattr(self, "preview", None)
        if preview is not None and hasattr(preview, "set_language"):
            preview.set_language(language)

        if persist:
            self.save_config()

    def _sync_import_button_language(self):
        english = self._language == "en_US"
        add_button = getattr(self, "add_images_primary_button", None)
        ppt_button = getattr(self, "import_ppt_images_button", None)
        if add_button is not None:
            add_button.setText("+  Add Images" if english else "＋  添加图片")
            add_button.setToolTip(
                "Add one or more images" if english else "添加一张或多张图片"
            )
        if ppt_button is not None:
            ppt_button.setText("▣  Import PPT" if english else "▣  导入PPT")
            ppt_button.setToolTip(
                "Extract images from PPTX/PPTM and insert them into the project"
                if english
                else "从 PPTX / PPTM 中提取图片并插入工程"
            )

    def _card(self, title):
        frame = QFrame()
        frame.setObjectName("Card")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(11, 9, 11, 11)
        layout.setSpacing(7)

        label = QLabel(title)
        label.setObjectName("SectionTitle")
        label.setMinimumHeight(22)
        layout.addWidget(label)

        return frame, layout

    def _collapsible_card(
        self,
        title,
        key,
        expanded=True,
    ):
        key = str(key)
        card = CollapsibleCard(
            title,
            expanded=expanded,
        )
        self._collapsible_cards[key] = card
        card.toggled.connect(
            lambda is_expanded, section_key=key:
            self._on_left_section_toggled(
                section_key,
                is_expanded,
            )
        )
        return card, card.content_layout

    def _left_accordion_keys(self):
        return (
            "page_layout",
            "page_title",
            "layout_spacing",
            "image_adjust",
            "display_settings",
        )

    def _on_left_section_toggled(
        self,
        active_key,
        expanded,
    ):
        """
        左侧保持固定窄宽度且不使用滚动条。
        展开一个功能区时，其它功能区自动收起，
        防止多个复杂面板同时争抢高度后互相叠压。
        """
        if not expanded:
            return

        for key in self._left_accordion_keys():
            if key == active_key:
                continue

            card = self._collapsible_cards.get(key)

            if card is not None and card.is_expanded():
                card.set_expanded(
                    False,
                    emit_signal=False,
                )

        if active_key == "page_title":
            self._refresh_title_card_height()

    def _ensure_single_left_section_expanded(
        self,
        preferred_key="page_layout",
    ):
        keys = self._left_accordion_keys()

        expanded_keys = [
            key
            for key in keys
            if (
                self._collapsible_cards.get(key) is not None
                and self._collapsible_cards[key].is_expanded()
            )
        ]

        if preferred_key in expanded_keys:
            keep_key = preferred_key
        elif expanded_keys:
            keep_key = expanded_keys[0]
        else:
            keep_key = (
                preferred_key
                if preferred_key in keys
                else keys[0]
            )

        for key in keys:
            card = self._collapsible_cards.get(key)
            if card is not None:
                card.set_expanded(
                    key == keep_key,
                    emit_signal=False,
                )

        return keep_key

    def _collapsible_state(self):
        return {
            key: card.is_expanded()
            for key, card
            in self._collapsible_cards.items()
        }

    def _apply_collapsible_state(self, state):
        if not isinstance(state, dict):
            self._ensure_single_left_section_expanded(
                "page_layout"
            )
            return

        accordion_keys = self._left_accordion_keys()

        requested = [
            key
            for key in accordion_keys
            if bool(state.get(key, False))
        ]

        preferred_key = (
            requested[0]
            if requested
            else "page_layout"
        )

        for key, expanded in state.items():
            key = str(key)

            if key in accordion_keys:
                continue

            card = self._collapsible_cards.get(key)

            if card is not None:
                card.set_expanded(
                    bool(expanded),
                    emit_signal=False,
                )

        self._ensure_single_left_section_expanded(
            preferred_key
        )

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(10, 8, 10, 7)
        main.setSpacing(6)

        command_bar = QFrame()
        command_bar.setObjectName("CommandBar")
        command_bar.setMinimumHeight(54)

        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(12, 7, 12, 7)
        command_layout.setSpacing(6)

        self.brand_logo = QLabel()
        self.brand_logo.setFixedSize(36, 36)
        logo_pixmap = QPixmap(resource_path("resources/icon.png"))
        self.brand_logo.setPixmap(
            logo_pixmap.scaled(
                34, 34,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.brand_title = QLabel("FrameDeck Studio")
        self.brand_title.setObjectName("CompactTitle")
        self.brand_title.setToolTip("FrameDeck Studio")
        self.brand_subtitle = QLabel("V12 Stable")
        self.brand_subtitle.setObjectName("CompactSubTitle")
        brand_text.addWidget(self.brand_title)
        brand_text.addWidget(self.brand_subtitle)

        command_layout.addWidget(self.brand_logo)
        command_layout.addLayout(brand_text)
        command_layout.addSpacing(8)

        command_groups = [
            [
                ("新建", self.new_project, "创建新工程"),
                ("打开", self.open_project, "打开工程文件"),
                ("保存", self.save_project, "保存当前工程"),
            ],
            [
                ("撤销", self.undo, "撤销上一步操作"),
                ("重做", self.redo, "恢复上一步操作"),
            ],
        ]

        self.command_buttons = {}

        for group_index, group in enumerate(command_groups):
            for text, slot, tooltip in group:
                button = QPushButton(text)
                button.setObjectName(
                    "CompactCommandButton"
                )
                button.setMinimumHeight(28)
                button.setToolTip(tooltip)
                button.clicked.connect(slot)
                command_layout.addWidget(button)
                self.command_buttons[text] = button

            if group_index < len(command_groups) - 1:
                separator = QFrame()
                separator.setObjectName(
                    "ToolbarDivider"
                )
                separator.setFrameShape(
                    QFrame.Shape.VLine
                )
                separator.setFixedHeight(24)
                command_layout.addSpacing(2)
                command_layout.addWidget(separator)
                command_layout.addSpacing(2)

        # 低频命令收进一个轻量菜单，给导入和中央画布留出横向空间。
        self.more_tools_menu = QMenu(self)
        recent_action = QAction("最近工程", self)
        recent_action.triggered.connect(self.show_recent_projects)
        template_action = QAction("载入模板", self)
        template_action.triggered.connect(self.load_template)
        log_action = QAction("生成日志", self)
        log_action.triggered.connect(
            lambda: self.toggle_log_dock(
                not self.log_dock.isVisible()
            )
        )
        copy_images_action = QAction("复制所选图片", self)
        copy_images_action.triggered.connect(self.shortcut_copy_images)
        cut_images_action = QAction("剪切所选图片", self)
        cut_images_action.triggered.connect(self.shortcut_cut_images)
        paste_images_action = QAction("粘贴图片到当前页", self)
        paste_images_action.triggered.connect(self.paste_images_to_current_page)
        self.more_tools_menu.addAction(copy_images_action)
        self.more_tools_menu.addAction(cut_images_action)
        self.more_tools_menu.addAction(paste_images_action)
        self.more_tools_menu.addSeparator()
        self.more_tools_menu.addAction(recent_action)
        self.more_tools_menu.addAction(template_action)
        self.more_tools_menu.addAction(log_action)

        self.more_tools_button = QToolButton(self)
        self.more_tools_button.setObjectName("PanelMenuButton")
        self.more_tools_button.setText("⋯")
        self.more_tools_button.setToolTip("更多工具")
        self.more_tools_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.more_tools_button.setMenu(self.more_tools_menu)
        self.more_tools_button.setFixedSize(34, 32)
        command_layout.addWidget(self.more_tools_button)

        # UI-05-45A Stage 01：
        # 高频图片导入保留为按钮主体，低频 PPT 导入收进下拉菜单。
        # 这样左侧不再长期占用一整块“图片素材”卡片。
        import_separator = QFrame()
        import_separator.setObjectName("ToolbarDivider")
        import_separator.setFrameShape(QFrame.Shape.VLine)
        import_separator.setFixedHeight(24)
        command_layout.addSpacing(2)
        command_layout.addWidget(import_separator)
        command_layout.addSpacing(2)

        self.import_menu = QMenu(self)
        self.import_images_action = QAction("添加图片", self)
        self.import_images_action.triggered.connect(self.add_images)
        self.import_ppt_action = QAction("从PPT导入图片", self)
        self.import_ppt_action.triggered.connect(self.import_ppt_images)
        self.import_menu.addAction(self.import_images_action)
        self.import_menu.addAction(self.import_ppt_action)

        self.add_images_primary_button = QToolButton(self)
        self.add_images_primary_button.setObjectName("ImportSplitButton")
        self.add_images_primary_button.setText("＋  添加图片")
        self.add_images_primary_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.add_images_primary_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.add_images_primary_button.setMenu(self.import_menu)
        self.add_images_primary_button.setMinimumHeight(32)
        self.add_images_primary_button.setMinimumWidth(118)
        self.add_images_primary_button.setToolTip(
            "点击主体添加图片；点击右侧箭头可从PPT导入"
        )
        self.add_images_primary_button.clicked.connect(self.add_images)
        command_layout.addWidget(self.add_images_primary_button)

        # 旧异步导入流程会同时启用/禁用这两个名称。
        # 指向同一个分体按钮可保持兼容而不重复显示控件。
        self.import_ppt_images_button = self.add_images_primary_button

        self._install_template_menu()

        command_layout.addStretch()

        self.header_layout_badge = InfoBadge("2 × 6")
        self.header_project_badge = InfoBadge("未保存")
        command_layout.addWidget(self.header_layout_badge)
        command_layout.addWidget(self.header_project_badge)

        # UI-05-31A：图标式主题选择。
        self.theme_menu = QMenu(self)
        self.theme_menu.setTitle("选择主题")
        self._theme_actions = {}

        for theme_name in THEME_META:
            action = QAction(
                self._make_theme_icon(
                    theme_name,
                    30,
                ),
                theme_name,
                self,
            )
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, name=theme_name:
                self.set_theme_selection(name)
            )
            self.theme_menu.addAction(action)
            self._theme_actions[theme_name] = action

        self.theme_button = QToolButton(self)
        self.theme_button.setObjectName(
            "ThemeIconButton"
        )
        self.theme_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.theme_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.theme_button.setMenu(self.theme_menu)
        self.theme_button.setIconSize(QSize(30, 30))
        self.theme_button.setFixedSize(46, 38)
        self.theme_button.setAccessibleName("主题选择")
        command_layout.addWidget(self.theme_button)

        # UI-05-44A：中英文界面即时切换。
        self.language_menu = QMenu(self)
        self.language_menu.setTitle("语言 / Language")
        self._language_actions = {}

        for code, title in (
            ("zh_CN", "中文"),
            ("en_US", "English"),
        ):
            action = QAction(title, self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, language_code=code:
                self.set_language(language_code)
            )
            self.language_menu.addAction(action)
            self._language_actions[code] = action

        self.language_button = QToolButton(self)
        self.language_button.setObjectName("LanguageButton")
        self.language_button.setText(
            "EN" if self._language == "en_US" else "中"
        )
        self.language_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.language_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.language_button.setMenu(self.language_menu)
        self.language_button.setFixedSize(46, 38)
        self.language_button.setAccessibleName("语言 / Language")
        command_layout.addWidget(self.language_button)

        self.export_menu = QMenu(self)
        self._export_actions = {}

        for export_format, title, tip in [
            ("pptx", "生成 PPT", "生成 PowerPoint 文件"),
            ("pdf", "生成 PDF", "生成多页 PDF 文件"),
            ("images", "生成图片", "按页面生成 PNG 图片"),
        ]:
            action = QAction(title, self)
            action.setToolTip(tip)
            action.triggered.connect(
                lambda checked=False, fmt=export_format:
                self.start_generate(fmt)
            )
            self.export_menu.addAction(action)
            self._export_actions[export_format] = action

        self.start_btn = QToolButton(self)
        self.start_btn.setObjectName("Primary")
        self.start_btn.setText("生成 PPT")
        self.start_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.start_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.start_btn.setMenu(self.export_menu)
        self.start_btn.setMinimumHeight(38)
        self.start_btn.setMinimumWidth(132)
        self.start_btn.clicked.connect(
            lambda checked=False: self.start_generate("pptx")
        )
        self.start_btn.setToolTip(
            "点击主体生成 PPT；点击右侧箭头选择 PDF 或图片"
        )
        command_layout.addWidget(self.start_btn)

        main.addWidget(command_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        self.workspace_splitter = splitter
        main.addWidget(splitter, 1)

        # 左侧
        # UI-05-42B FIX03：
        # 去掉左侧QScrollArea，使用紧凑固定侧栏。
        # 默认展开状态下的主要功能可以一次完整看到，
        # 同时明显释放中央画布横向空间。
        left = QWidget()
        left.setObjectName("LeftPanel")
        left.setMinimumWidth(0)
        left.setMaximumWidth(16777215)
        left.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        l = QVBoxLayout(left)
        l.setContentsMargins(0, 0, 3, 0)
        l.setSpacing(4)

        # UI-05-40A：
        # 旧“项目文件”卡片中的文件夹导入和输出路径输入已移除。
        # 保留隐藏字段仅用于读取旧工程/旧配置，不再显示给用户。
        self.folder_edit = DropLineEdit()
        self.folder_edit.setParent(left)
        self.folder_edit.folder_dropped.connect(
            self.on_folder_selected
        )
        self.folder_edit.hide()

        self.output_edit = QLineEdit(left)
        self.output_edit.hide()

        # UI-05-45A Stage 01：旧导入卡片已合并到顶部“添加图片”分体按钮。
        # 以下两个隐藏控件只为旧工程状态与既有刷新代码保留接口。
        self.import_count_badge = QLabel("当前 0 张", left)
        self.import_count_badge.hide()
        self.new_import_group_check = QCheckBox(
            "每次导入创建新分组",
            left,
        )
        self.new_import_group_check.setChecked(True)
        self.new_import_group_check.hide()

        grid_card, gl = self._collapsible_card(
            "页面布局",
            "page_layout",
            expanded=True,
        )
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(1, 1)

        for row_index in range(5):
            grid.setRowMinimumHeight(
                row_index,
                30,
            )

        self.row_step = ModernStepper(1, 10, 2)
        self.col_step = ModernStepper(1, 12, 6)
        self.page_combo = QComboBox()
        self.page_combo.addItems(["16:9", "4:3", "A4横版", "A4竖版"])
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["保持比例", "裁剪填充"])
        grid.addWidget(QLabel("行数"), 0, 0)
        grid.addWidget(self.row_step, 0, 1)
        grid.addWidget(QLabel("列数"), 1, 0)
        grid.addWidget(self.col_step, 1, 1)
        grid.addWidget(QLabel("页面尺寸"), 2, 0)
        grid.addWidget(self.page_combo, 2, 1)
        grid.addWidget(QLabel("图片模式"), 3, 0)
        grid.addWidget(self.mode_combo, 3, 1)

        self.auto_layout_check = QCheckBox("自动排版")
        self.auto_layout_check.setObjectName("AutoLayoutSwitch")
        self.auto_layout_check.setToolTip(
            "按当前行列连续补满页面空位"
        )
        self.confirm_auto_layout_btn = QPushButton(
            "确认此次排版",
            left,
        )
        self.confirm_auto_layout_btn.setToolTip(
            "确认当前自动排版并停止自动补位"
        )
        self.confirm_auto_layout_btn.setMinimumWidth(72)
        self.confirm_auto_layout_btn.hide()

        auto_layout_row = QHBoxLayout()
        auto_layout_row.setContentsMargins(0, 0, 0, 0)
        auto_layout_row.setSpacing(6)
        auto_layout_row.addWidget(self.auto_layout_check)
        auto_layout_row.addStretch(1)
        auto_layout_row.addWidget(
            self.confirm_auto_layout_btn,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        grid.addLayout(auto_layout_row, 4, 0, 1, 2)

        self.pagination_mode_combo = QComboBox()
        self.pagination_mode_combo.addItem(
            "连续排版 · 自动补满",
            PAGINATION_CONTINUOUS,
        )
        self.pagination_mode_combo.addItem(
            "分组排版 · 保留组尾空位",
            PAGINATION_GROUPED,
        )
        self.pagination_mode_combo.setCurrentIndex(
            self.pagination_mode_combo.findData(PAGINATION_GROUPED)
        )
        self.pagination_mode_combo.setToolTip(
            (
                "连续：自动补满。\n"
                "分组：组尾保留空位，不跨组补位。"
            )
        )
        # 保留旧值以读取历史工程，但不再把分页模式暴露为日常操作。
        self.pagination_mode_combo.hide()

        gl.addLayout(grid)

        # 分组只保留一个低频整理入口；锁定与分页模式不再暴露。
        self.group_mode_hint = QLabel(
            "拖动图片即可跨页 / 跨组调整",
            left,
        )
        self.group_mode_hint.setObjectName("ImportHint")
        self.group_mode_hint.setWordWrap(True)
        self.group_manager_btn = QPushButton("整理分组…", left)
        self.group_manager_btn.setObjectName("CompactUtility")
        self.group_manager_btn.setToolTip("重命名或整理分组边界")
        self.group_manager_btn.clicked.connect(self.open_group_manager)
        self.page_lock_btn = QPushButton("锁定当前页", left)
        self.group_lock_btn = QPushButton("锁定当前组", left)
        self.lock_status_hint = QLabel("", left)

        group_tools_row = QHBoxLayout()
        group_tools_row.setContentsMargins(0, 2, 0, 0)
        group_tools_row.setSpacing(6)
        group_tools_row.addWidget(self.group_mode_hint, 1)
        group_tools_row.addWidget(self.group_manager_btn)
        gl.addLayout(group_tools_row)

        for legacy_widget in (
            self.page_lock_btn,
            self.group_lock_btn,
            self.lock_status_hint,
        ):
            legacy_widget.hide()

        l.addWidget(grid_card)

        title_card, title_layout = self._collapsible_card(
            "批量标题",
            "page_title",
            expanded=False,
        )
        self.title_card = title_card
        # FIX11：
        # 删除几个重复的分区标题后，主控件仍保持清晰，
        # 同时为底部 Logo / 页脚永久留出可见空间。
        title_layout.setSpacing(3)

        self.title_check = QCheckBox(
            "显示页面标题"
        )
        title_layout.addWidget(
            self.title_check
        )

        title_hint = QLabel(
            "双击标题或画布上的“＋ 标题”即可编辑"
        )
        title_hint.setObjectName("ImportHint")
        title_hint.setWordWrap(True)
        title_layout.addWidget(title_hint)

        self.batch_title_edit = QLineEdit()
        self.batch_title_edit.setObjectName("CompactField")
        self.batch_title_edit.setPlaceholderText("统一标题")
        self.batch_title_edit.setMinimumWidth(0)
        self.batch_title_edit.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        self.batch_title_apply_btn = QPushButton("应用全部")
        self.batch_title_apply_btn.setObjectName("CompactUtility")
        self.batch_title_apply_btn.setProperty("fdBatchTitleApply", True)
        self.batch_title_apply_btn.setFixedWidth(132)

        batch_title_row = QHBoxLayout()
        batch_title_row.setContentsMargins(0, 0, 0, 0)
        batch_title_row.setSpacing(6)
        batch_title_row.addWidget(self.batch_title_edit, 1)
        batch_title_row.addWidget(self.batch_title_apply_btn)
        title_layout.addLayout(batch_title_row)

        self.title_content_mode_combo = QComboBox()
        self.title_content_mode_combo.setObjectName(
            "CompactField"
        )
        self.title_content_mode_combo.addItem(
            "全局统一",
            "global",
        )
        self.title_content_mode_combo.addItem(
            "按分组",
            "group",
        )
        self.title_content_mode_combo.addItem(
            "每页独立",
            "page",
        )
        self.title_content_mode_combo.setToolTip(
            (
                "全局统一：所有页面使用同一标题。\n"
                "按分组：同组页面使用同一标题，未填写时继承全局标题。\n"
                "每页独立：当前页可单独填写，未填写时继承分组/全局标题。"
            )
        )
        self.title_content_mode_combo.setCurrentIndex(
            self.title_content_mode_combo.findData("page")
        )
        self.title_content_mode_combo.hide()

        self.title_context_label = QLabel(
            "当前范围：全部页面"
        )
        self.title_context_label.setObjectName(
            "ImportHint"
        )
        self.title_context_label.setWordWrap(
            False
        )
        self.title_context_label.setMinimumHeight(
            18
        )
        self.title_context_label.hide()

        self.title_edit = QLineEdit()
        self.title_edit.setMinimumHeight(
            30
        )
        self.title_edit.setPlaceholderText(
            "主标题"
        )

        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setMinimumHeight(
            30
        )
        self.subtitle_edit.setPlaceholderText(
            "副标题（可选）"
        )
        self.title_edit.hide()
        self.subtitle_edit.hide()

        style_scope_row = QHBoxLayout()
        style_scope_row.setContentsMargins(
            0, 0, 0, 0
        )
        style_scope_row.setSpacing(5)

        self.title_style_scope_combo = QComboBox()
        self.title_style_scope_combo.setObjectName(
            "CompactField"
        )
        self.title_style_scope_combo.addItem(
            "样式：全部页面",
            "global",
        )
        self.title_style_scope_combo.addItem(
            "样式：当前分组",
            "group",
        )
        self.title_style_scope_combo.addItem(
            "样式：当前页",
            "page",
        )
        self.title_style_scope_combo.setCurrentIndex(
            self.title_style_scope_combo.findData("global")
        )
        self.title_style_scope_combo.hide()

        self.title_style_inherit_btn = QPushButton(
            "恢复继承"
        )
        self.title_style_inherit_btn.setObjectName(
            "CompactUtility"
        )
        self.title_style_inherit_btn.setToolTip(
            (
                "删除当前分组或当前页的样式覆盖，"
                "恢复继承上一级标题样式"
            )
        )
        self.title_style_inherit_btn.setMaximumWidth(
            72
        )
        self.title_style_inherit_btn.hide()

        self.title_font_combo = QComboBox()
        self.title_font_combo.setObjectName(
            "CompactField"
        )
        self.title_font_combo.setEditable(
            True
        )
        self.title_font_combo.setMinimumWidth(
            0
        )
        self.title_font_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        self.title_font_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.title_font_combo.setMinimumContentsLength(5)
        self.title_font_combo.addItems(
            [
                "Microsoft YaHei",
                "Microsoft YaHei UI",
                "微软雅黑",
                "DengXian",
                "等线",
                "SimHei",
                "黑体",
                "SimSun",
                "宋体",
                "FangSong",
                "仿宋",
                "KaiTi",
                "楷体",
                "Aptos",
                "Calibri",
                "Arial",
                "Times New Roman",
            ]
        )
        self.title_font_combo.setToolTip(
            "可直接输入电脑中已安装的其它字体名称"
        )

        font_row = QHBoxLayout()
        font_row.setContentsMargins(
            0, 0, 0, 0
        )
        font_row.setSpacing(
            6
        )

        font_inline_label = QLabel(
            "字体"
        )
        font_inline_label.setObjectName(
            "FieldCaption"
        )
        font_inline_label.setMinimumWidth(
            28
        )

        font_row.addWidget(
            font_inline_label
        )
        font_row.addWidget(
            self.title_font_combo,
            1,
        )
        title_layout.addLayout(
            font_row
        )

        title_style_grid = QGridLayout()
        title_style_grid.setContentsMargins(
            0, 0, 0, 0
        )
        title_style_grid.setHorizontalSpacing(
            5
        )
        title_style_grid.setVerticalSpacing(
            2
        )
        title_style_grid.setColumnStretch(
            0, 1
        )
        title_style_grid.setColumnStretch(
            1, 1
        )

        size_caption = QLabel(
            "字号"
        )
        size_caption.setObjectName(
            "FieldCaption"
        )
        color_caption = QLabel(
            "颜色"
        )
        color_caption.setObjectName(
            "FieldCaption"
        )

        self.title_font_size_input = QDoubleSpinBox()
        self.title_font_size_input.setObjectName(
            "CompactField"
        )
        self.title_font_size_input.setRange(
            6.0, 96.0
        )
        self.title_font_size_input.setDecimals(
            0
        )
        self.title_font_size_input.setSingleStep(
            1.0
        )
        self.title_font_size_input.setSuffix(
            " pt"
        )
        self.title_font_size_input.setValue(
            20.0
        )
        self.title_font_size_input.setKeyboardTracking(
            False
        )
        self.title_font_size_input.setMinimumWidth(
            0
        )
        self.title_font_size_input.setMaximumWidth(
            16777215
        )
        self.title_font_size_input.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        self.title_color_button = QPushButton(
            "■  #111827"
        )
        self.title_color_button.setObjectName(
            "CompactUtility"
        )
        self.title_color_button.setToolTip(
            "选择标题文字颜色"
        )
        self.title_color_button.setMinimumWidth(
            0
        )
        self.title_color_button.setMaximumWidth(
            16777215
        )
        self.title_color_button.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        title_style_grid.addWidget(
            size_caption,
            0,
            0,
        )
        title_style_grid.addWidget(
            color_caption,
            0,
            1,
        )
        title_style_grid.addWidget(
            self.title_font_size_input,
            1,
            0,
        )
        title_style_grid.addWidget(
            self.title_color_button,
            1,
            1,
        )
        title_layout.addLayout(
            title_style_grid
        )

        title_emphasis_row = QHBoxLayout()
        title_emphasis_row.setContentsMargins(
            0, 0, 0, 0
        )
        title_emphasis_row.setSpacing(
            8
        )

        self.title_bold_check = QCheckBox(
            "加粗"
        )
        self.title_bold_check.setChecked(
            True
        )

        self.title_alignment_combo = QComboBox()
        self.title_alignment_combo.setObjectName(
            "CompactField"
        )
        self.title_alignment_combo.addItem(
            "左对齐",
            "left",
        )
        self.title_alignment_combo.addItem(
            "居中",
            "center",
        )
        self.title_alignment_combo.addItem(
            "右对齐",
            "right",
        )
        self.title_alignment_combo.setCurrentIndex(
            1
        )
        self.title_alignment_combo.setMinimumWidth(0)
        self.title_alignment_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        title_emphasis_row.addWidget(
            self.title_bold_check
        )
        title_emphasis_row.addWidget(
            self.title_alignment_combo,
            1,
        )
        title_layout.addLayout(
            title_emphasis_row
        )

        title_geometry_grid = QGridLayout()
        title_geometry_grid.setContentsMargins(
            0, 0, 0, 0
        )
        title_geometry_grid.setHorizontalSpacing(
            5
        )
        title_geometry_grid.setVerticalSpacing(
            2
        )
        title_geometry_grid.setColumnStretch(
            0, 1
        )
        title_geometry_grid.setColumnStretch(
            1, 1
        )

        top_spacing_caption = QLabel(
            "顶部间距"
        )
        top_spacing_caption.setObjectName(
            "FieldCaption"
        )
        title_height_caption = QLabel(
            "标题高度"
        )
        title_height_caption.setObjectName(
            "FieldCaption"
        )

        self.title_top_spacing_input = QDoubleSpinBox()
        self.title_top_spacing_input.setObjectName(
            "CompactField"
        )
        self.title_top_spacing_input.setRange(
            0.0, 3.0
        )
        self.title_top_spacing_input.setDecimals(
            2
        )
        self.title_top_spacing_input.setSingleStep(
            0.1
        )
        self.title_top_spacing_input.setSuffix(
            " cm"
        )
        self.title_top_spacing_input.setValue(
            0.0
        )
        self.title_top_spacing_input.setKeyboardTracking(
            False
        )
        self.title_top_spacing_input.setMinimumWidth(0)
        self.title_top_spacing_input.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        self.title_height_input = QDoubleSpinBox()
        self.title_height_input.setObjectName(
            "CompactField"
        )
        self.title_height_input.setRange(
            math.ceil(
                minimum_title_region_height_cm(20.0, True)
                * 100.0
            ) / 100.0,
            5.0,
        )
        self.title_height_input.setDecimals(
            2
        )
        self.title_height_input.setSingleStep(
            0.1
        )
        self.title_height_input.setSuffix(
            " cm"
        )
        self.title_height_input.setValue(
            0.9
        )
        self.title_height_input.setToolTip(
            "标题区会根据字号自动保持安全高度，避免遮挡图片"
        )
        self.title_height_input.setKeyboardTracking(
            False
        )
        self.title_height_input.setMinimumWidth(0)
        self.title_height_input.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        title_geometry_grid.addWidget(
            top_spacing_caption,
            0,
            0,
        )
        title_geometry_grid.addWidget(
            title_height_caption,
            0,
            1,
        )
        title_geometry_grid.addWidget(
            self.title_top_spacing_input,
            1,
            0,
        )
        title_geometry_grid.addWidget(
            self.title_height_input,
            1,
            1,
        )
        title_layout.addLayout(
            title_geometry_grid
        )

        # -------------------------------------------------
        # 页面附加：FIX06 紧凑布局
        # -------------------------------------------------
        # 旧版“分隔线 + 页面附加标题 + Logo整行 + 页脚整行”
        # 占用过多高度，在窄侧栏内会被下方折叠卡遮挡。
        # 现在合并成一条工具行；页脚文字仅在启用时显示。

        self.logo_edit = QLineEdit(left)
        self.logo_edit.setPlaceholderText(
            "Logo 图片路径（可选）"
        )
        self.logo_edit.setReadOnly(
            True
        )
        self.logo_edit.setVisible(
            False
        )

        self.logo_status_label = QLabel("", left)
        self.logo_status_label.setObjectName(
            "FieldCaption"
        )
        self.logo_status_label.setToolTip(
            "尚未选择 Logo"
        )

        self.logo_btn = QPushButton("", left)
        self.logo_btn.setObjectName(
            "CompactUtility"
        )
        self.logo_btn.setToolTip(
            "选择 Logo 图片"
        )
        self.logo_btn.setMaximumWidth(
            48
        )
        self.logo_btn.clicked.connect(
            self.select_logo
        )

        self.clear_logo_btn = QPushButton("", left)
        self.clear_logo_btn.setObjectName(
            "CompactUtility"
        )
        self.clear_logo_btn.setToolTip(
            "取消当前 Logo"
        )
        self.clear_logo_btn.setMaximumWidth(
            48
        )
        self.clear_logo_btn.clicked.connect(
            self.clear_logo
        )
        self.clear_logo_btn.setEnabled(
            False
        )
        self.logo_status_label.hide()
        self.logo_btn.hide()
        self.clear_logo_btn.hide()

        self.footer_check = QCheckBox(
            "启用页脚"
        )

        extras_row = QHBoxLayout()
        extras_row.setContentsMargins(
            0, 1, 0, 0
        )
        extras_row.setSpacing(
            5
        )
        self.footer_edit = QLineEdit()
        self.footer_edit.setMinimumHeight(
            27
        )
        self.footer_edit.setMaximumHeight(
            29
        )
        self.footer_edit.setPlaceholderText(
            "页脚文字"
        )
        self.footer_edit.setEnabled(
            False
        )
        self.footer_edit.setVisible(
            True
        )
        self.footer_edit.setMinimumWidth(
            96
        )

        # Logo 与副标题从产品界面移除。页脚移动到“页脚与显示”卡片。

        self._set_title_controls_enabled(
            False
        )

        l.addWidget(
            title_card
        )

        space_card, sl = self._collapsible_card(
            "布局间距",
            "layout_spacing",
            expanded=False,
        )
        sl.setSpacing(
            7
        )

        spacing_hint = QLabel(
            "单位：cm"
        )
        spacing_hint.setObjectName(
            "PanelSubhead"
        )
        sl.addWidget(
            spacing_hint
        )

        def make_spacing_input(
            minimum,
            maximum,
            value,
            step=0.05,
        ):
            editor = QDoubleSpinBox()
            editor.setObjectName(
                "CompactField"
            )
            editor.setRange(
                minimum,
                maximum,
            )
            editor.setDecimals(
                2
            )
            editor.setSingleStep(
                step
            )
            editor.setValue(
                value
            )
            editor.setSuffix(
                " cm"
            )
            editor.setKeyboardTracking(
                False
            )
            editor.setMinimumWidth(
                0
            )
            editor.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )
            return editor

        self.ml = make_spacing_input(
            0.0, 5.0, 0.6
        )
        self.mr = make_spacing_input(
            0.0, 5.0, 0.6
        )
        self.mt = make_spacing_input(
            0.0, 5.0, 0.8
        )
        self.mb = make_spacing_input(
            0.0, 5.0, 0.8
        )
        self.gx = make_spacing_input(
            0.0, 3.0, 0.25
        )
        self.gy = make_spacing_input(
            0.0, 3.0, 0.35
        )
        self.lh = make_spacing_input(
            0.2, 2.0, 0.45
        )

        spacing_grid = QGridLayout()
        spacing_grid.setContentsMargins(
            0, 0, 0, 0
        )
        spacing_grid.setHorizontalSpacing(
            5
        )
        spacing_grid.setVerticalSpacing(
            3
        )
        spacing_grid.setColumnStretch(
            0, 1
        )
        spacing_grid.setColumnStretch(
            1, 1
        )

        spacing_fields = [
            (
                "左边距",
                self.ml,
                "右边距",
                self.mr,
            ),
            (
                "上边距",
                self.mt,
                "下边距",
                self.mb,
            ),
            (
                "水平间距",
                self.gx,
                "垂直间距",
                self.gy,
            ),
        ]

        grid_row = 0

        for (
            left_label,
            left_widget,
            right_label,
            right_widget,
        ) in spacing_fields:
            left_caption = QLabel(
                left_label
            )
            left_caption.setObjectName(
                "FieldCaption"
            )
            right_caption = QLabel(
                right_label
            )
            right_caption.setObjectName(
                "FieldCaption"
            )

            spacing_grid.addWidget(
                left_caption,
                grid_row,
                0,
            )
            spacing_grid.addWidget(
                right_caption,
                grid_row,
                1,
            )
            spacing_grid.addWidget(
                left_widget,
                grid_row + 1,
                0,
            )
            spacing_grid.addWidget(
                right_widget,
                grid_row + 1,
                1,
            )
            grid_row += 2

        text_height_caption = QLabel(
            "图片下方文字高度"
        )
        text_height_caption.setObjectName(
            "FieldCaption"
        )
        spacing_grid.addWidget(
            text_height_caption,
            grid_row,
            0,
            1,
            2,
        )
        spacing_grid.addWidget(
            self.lh,
            grid_row + 1,
            0,
            1,
            2,
        )

        sl.addLayout(
            spacing_grid
        )
        l.addWidget(
            space_card
        )

        ec, el = self._collapsible_card(
            "图片调整",
            "image_adjust",
            expanded=False,
        )
        el.setSpacing(
            7
        )

        top_info = QHBoxLayout()
        top_info.setContentsMargins(
            0, 0, 0, 0
        )
        top_info.setSpacing(
            5
        )

        self.selected_name_label = QLabel(
            "未选择图片"
        )
        self.selected_name_label.setObjectName(
            "HeroSub"
        )
        self.selected_name_label.setWordWrap(
            False
        )
        self.selected_name_label.setMaximumHeight(
            24
        )
        self.selected_name_label.setMinimumHeight(
            24
        )

        self.transform_status_badge = InfoBadge(
            "默认参数"
        )

        top_info.addWidget(
            self.selected_name_label,
            1,
        )
        top_info.addWidget(
            self.transform_status_badge
        )
        el.addLayout(
            top_info
        )

        transform_divider = QFrame()
        transform_divider.setObjectName(
            "PanelDivider"
        )
        transform_divider.setFrameShape(
            QFrame.Shape.HLine
        )
        el.addWidget(
            transform_divider
        )

        self.image_zoom_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.image_zoom_slider.setObjectName(
            "TransformSlider"
        )
        self.image_zoom_slider.setRange(
            10, 1000
        )
        self.image_zoom_slider.setValue(
            100
        )
        self.image_zoom_slider.setEnabled(
            False
        )
        self.image_zoom_slider.setToolTip(
            "图片缩放范围：0.10×～10.00×"
        )

        self.image_zoom_input = QDoubleSpinBox()
        self.image_zoom_input.setObjectName(
            "CompactField"
        )
        self.image_zoom_input.setRange(
            0.10, 10.00
        )
        self.image_zoom_input.setDecimals(
            2
        )
        self.image_zoom_input.setSingleStep(
            0.05
        )
        self.image_zoom_input.setSuffix(
            " ×"
        )
        self.image_zoom_input.setValue(
            1.00
        )
        self.image_zoom_input.setKeyboardTracking(
            False
        )
        self.image_zoom_input.setEnabled(
            False
        )
        self.image_zoom_input.setFixedWidth(
            82
        )

        self.offset_x_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.offset_x_slider.setObjectName(
            "TransformSlider"
        )
        self.offset_x_slider.setRange(
            -100, 100
        )
        self.offset_x_slider.setValue(
            0
        )
        self.offset_x_slider.setEnabled(
            False
        )
        self.offset_x_slider.setToolTip(
            "范围会根据图片比例和缩放倍率自动扩展"
        )

        self.offset_x_input = QDoubleSpinBox()
        self.offset_x_input.setObjectName(
            "CompactField"
        )
        self.offset_x_input.setRange(
            -5000, 5000
        )
        self.offset_x_input.setDecimals(
            0
        )
        self.offset_x_input.setSingleStep(
            1
        )
        self.offset_x_input.setSuffix(
            " %"
        )
        self.offset_x_input.setValue(
            0
        )
        self.offset_x_input.setKeyboardTracking(
            False
        )
        self.offset_x_input.setEnabled(
            False
        )
        self.offset_x_input.setFixedWidth(
            82
        )

        self.offset_y_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.offset_y_slider.setObjectName(
            "TransformSlider"
        )
        self.offset_y_slider.setRange(
            -100, 100
        )
        self.offset_y_slider.setValue(
            0
        )
        self.offset_y_slider.setEnabled(
            False
        )
        self.offset_y_slider.setToolTip(
            "范围会根据图片比例和缩放倍率自动扩展"
        )

        self.offset_y_input = QDoubleSpinBox()
        self.offset_y_input.setObjectName(
            "CompactField"
        )
        self.offset_y_input.setRange(
            -5000, 5000
        )
        self.offset_y_input.setDecimals(
            0
        )
        self.offset_y_input.setSingleStep(
            1
        )
        self.offset_y_input.setSuffix(
            " %"
        )
        self.offset_y_input.setValue(
            0
        )
        self.offset_y_input.setKeyboardTracking(
            False
        )
        self.offset_y_input.setEnabled(
            False
        )
        self.offset_y_input.setFixedWidth(
            82
        )

        transform_blocks = [
            (
                "缩放",
                self.image_zoom_slider,
                self.image_zoom_input,
            ),
            (
                "水平位置",
                self.offset_x_slider,
                self.offset_x_input,
            ),
            (
                "垂直位置",
                self.offset_y_slider,
                self.offset_y_input,
            ),
        ]

        for (
            label_text,
            slider,
            editor,
        ) in transform_blocks:
            header_row = QHBoxLayout()
            header_row.setContentsMargins(
                0, 0, 0, 0
            )
            header_row.setSpacing(
                6
            )

            label = QLabel(
                label_text
            )
            label.setObjectName(
                "FieldCaption"
            )

            header_row.addWidget(
                label
            )
            header_row.addStretch(
                1
            )
            header_row.addWidget(
                editor
            )

            el.addLayout(
                header_row
            )
            el.addWidget(
                slider
            )

        transform_divider_2 = QFrame()
        transform_divider_2.setObjectName(
            "PanelDivider"
        )
        transform_divider_2.setFrameShape(
            QFrame.Shape.HLine
        )
        el.addWidget(
            transform_divider_2
        )

        transform_ops_head = QLabel(
            "旋转与镜像"
        )
        transform_ops_head.setObjectName(
            "PanelSubhead"
        )
        el.addWidget(
            transform_ops_head
        )

        geometry_grid = QGridLayout()
        geometry_grid.setContentsMargins(
            0, 0, 0, 0
        )
        geometry_grid.setHorizontalSpacing(
            6
        )
        geometry_grid.setVerticalSpacing(
            0
        )

        for column in range(
            4
        ):
            geometry_grid.setColumnStretch(
                column,
                1,
            )

        self.rotate_left_btn = QPushButton(
            "↶"
        )
        self.rotate_right_btn = QPushButton(
            "↷"
        )
        self.flip_h_btn = QPushButton(
            "⇄"
        )
        self.flip_v_btn = QPushButton(
            "⇅"
        )

        self.rotate_left_btn.setToolTip(
            "左转 90°"
        )
        self.rotate_right_btn.setToolTip(
            "右转 90°"
        )
        self.flip_h_btn.setToolTip(
            "水平镜像"
        )
        self.flip_v_btn.setToolTip(
            "垂直翻转"
        )

        for icon_button in [
            self.rotate_left_btn,
            self.rotate_right_btn,
            self.flip_h_btn,
            self.flip_v_btn,
        ]:
            icon_button.setObjectName(
                "IconActionButton"
            )
            icon_button.setMinimumHeight(
                34
            )
            icon_button.setMaximumHeight(
                34
            )
            icon_button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        geometry_grid.addWidget(
            self.rotate_left_btn,
            0,
            0,
        )
        geometry_grid.addWidget(
            self.rotate_right_btn,
            0,
            1,
        )
        geometry_grid.addWidget(
            self.flip_h_btn,
            0,
            2,
        )
        geometry_grid.addWidget(
            self.flip_v_btn,
            0,
            3,
        )
        el.addLayout(
            geometry_grid
        )

        self.reset_transform_btn = QPushButton(
            "重置参数"
        )
        self.reset_transform_btn.setObjectName(
            "CompactUtility"
        )
        self.reset_transform_btn.setMinimumHeight(
            31
        )
        self.reset_transform_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        el.addWidget(
            self.reset_transform_btn
        )

        for button in [
            self.rotate_left_btn,
            self.rotate_right_btn,
            self.flip_h_btn,
            self.flip_v_btn,
            self.reset_transform_btn,
        ]:
            button.setEnabled(
                False
            )

        l.addWidget(
            ec
        )

        option_card, ol = self._collapsible_card(
            "页脚与显示",
            "display_settings",
            expanded=False,
        )
        self.filename_check = QCheckBox("显示文件名")
        self.index_check = QCheckBox("显示编号")
        self.page_check = QCheckBox("显示页码")
        self.border_check = QCheckBox("图片边框")
        self.page_check.setChecked(True)

        display_grid = QGridLayout()
        display_grid.setContentsMargins(0, 0, 0, 0)
        display_grid.setHorizontalSpacing(5)
        display_grid.setVerticalSpacing(4)
        display_grid.setRowMinimumHeight(0, 25)
        display_grid.setRowMinimumHeight(1, 25)
        display_grid.addWidget(self.filename_check, 0, 0)
        display_grid.addWidget(self.index_check, 0, 1)
        display_grid.addWidget(self.page_check, 1, 0)
        display_grid.addWidget(self.border_check, 1, 1)
        display_grid.setColumnStretch(0, 1)
        display_grid.setColumnStretch(1, 1)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 2)
        footer_row.setSpacing(6)
        footer_row.addWidget(self.footer_check)
        footer_row.addWidget(self.footer_edit, 1)
        ol.addLayout(footer_row)
        ol.addLayout(display_grid)
        l.addWidget(option_card)
        l.addStretch(1)
        # 左侧使用真正的滚动容器，Windows 125% / 150% 缩放时
        # 控件会自然增高并滚动，不会再互相叠压。
        left_scroll = QScrollArea()
        left_scroll.setObjectName("LeftPanelScroll")
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        left_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        left_scroll.setWidget(left)
        left_scroll.setFixedWidth(LEFT_PANEL_WIDTH_ZH)
        self.left_panel = left
        self.left_scroll = left_scroll
        splitter.addWidget(left_scroll)

        # 中间预览。页面导航标题并入导航条左侧，不再单独占一整行。
        pc = QFrame()
        pc.setObjectName("WorkspaceCard")
        pl = QVBoxLayout(pc)
        pl.setContentsMargins(8, 6, 8, 8)
        pl.setSpacing(5)
        # UI-05-02 Layout Adjustment
        # 缩放控制移动到底部导航栏，顶部保持干净

        # =====================================================
        # UI-05-01-02
        # Page Thumbnail Bar
        #
        # 插入在 PreviewCanvas 上方
        # =====================================================


        page_nav_strip = QFrame(pc)
        page_nav_strip.setObjectName("PageNavigatorStrip")
        page_nav_strip.setFixedHeight(112)
        page_nav_layout = QHBoxLayout(page_nav_strip)
        page_nav_layout.setContentsMargins(0, 0, 0, 0)
        page_nav_layout.setSpacing(5)

        self.page_preview_side_label = QLabel("页\n面\n预\n览")
        self.page_preview_side_label.setObjectName("NavigatorSideTitle")
        self.page_preview_side_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.page_preview_side_label.setFixedWidth(42)

        self.slide_thumbnail_bar = SlideThumbnailBar()
        self.slide_thumbnail_bar.setFixedHeight(108)

        page_nav_layout.addWidget(self.page_preview_side_label)
        page_nav_layout.addWidget(self.slide_thumbnail_bar, 1)
        pl.addWidget(page_nav_strip)


        self.preview = PreviewCanvas()

        # UI-05-22E：
        # 当前实际运行的 PreviewCanvas 可能没有 add_empty_page()。
        # 在 MainWindow 内安装最小兼容层，不替换中央画布文件。
        self._install_preview_page_api_compat()

        pl.addWidget(
            self.preview,
            1
        )

        # =====================================================
        # UI-05-01-02 Signal Bridge
        # =====================================================

        self.slide_thumbnail_bar.pageSelected.connect(
            self.on_thumbnail_page_selected
        )


        self.slide_thumbnail_bar.addPageRequested.connect(
            self.on_thumbnail_add_page
        )

        # UI-05-22E：连接右键复制 / 删除页面。
        if hasattr(self.slide_thumbnail_bar, "duplicatePageRequested"):
            self.slide_thumbnail_bar.duplicatePageRequested.connect(
                self.on_thumbnail_duplicate_page
            )

        if hasattr(self.slide_thumbnail_bar, "deletePageRequested"):
            self.slide_thumbnail_bar.deletePageRequested.connect(
                self.on_thumbnail_delete_page
            )

        # UI-05-24A：顶部页面缩略图拖动排序。
        if hasattr(self.slide_thumbnail_bar, "pagesReordered"):
            self.slide_thumbnail_bar.pagesReordered.connect(
                self.on_thumbnail_pages_reordered
            )

        if hasattr(self.slide_thumbnail_bar, "imageDropRequested"):
            self.slide_thumbnail_bar.imageDropRequested.connect(
                self.on_thumbnail_image_drop
            )

        # 独立占位的紧凑底栏。它属于布局的一部分，永远不会浮在画布上。
        nav_frame = QFrame()
        nav_frame.setObjectName("WorkspaceFooter")
        nav_frame.setFixedHeight(38)
        nav = QHBoxLayout(nav_frame)
        nav.setContentsMargins(5, 3, 5, 3)
        nav.setSpacing(4)

        # UI-05-02
        # 底部缩放快捷按钮（首页左侧）
        self.zoom_minus_btn = QToolButton()
        self.zoom_minus_btn.setText("−")
        self.zoom_minus_btn.setToolTip("缩小画布")
        self.zoom_minus_btn.clicked.connect(self.zoom_out)

        self.zoom_fit_btn = QToolButton()
        self.zoom_fit_btn.setText("⛶")
        self.zoom_fit_btn.setToolTip("适应窗口")
        self.zoom_fit_btn.clicked.connect(lambda: self.apply_zoom("适应窗口"))

        self.zoom_plus_btn = QToolButton()
        self.zoom_plus_btn.setText("＋")
        self.zoom_plus_btn.setToolTip("放大画布")
        self.zoom_plus_btn.clicked.connect(self.zoom_in)

        for btn in [self.zoom_minus_btn, self.zoom_fit_btn, self.zoom_plus_btn]:
            btn.setObjectName("IconActionButton")
            btn.setFixedSize(31, 30)

        nav.addWidget(self.zoom_minus_btn)
        nav.addWidget(self.zoom_fit_btn)
        nav.addWidget(self.zoom_plus_btn)

        self.first_btn = QToolButton()
        self.first_btn.setText("⇤")
        self.first_btn.setToolTip("首页")
        self.first_btn.clicked.connect(self.first_page)
        self.prev_btn = QToolButton()
        self.prev_btn.setText("‹")
        self.prev_btn.setToolTip("上一页")
        self.prev_btn.clicked.connect(self.previous_page)

        self.page_jump = QSpinBox()
        self.page_jump.setObjectName("PageJump")
        self.page_jump.setRange(1, 1)
        self.page_jump.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_jump.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_jump.setFixedSize(48, 28)
        self.page_jump.valueChanged.connect(self.jump_to_page)

        self.next_btn = QToolButton()
        self.next_btn.setText("›")
        self.next_btn.setToolTip("下一页")
        self.next_btn.clicked.connect(self.next_page)
        self.last_btn = QToolButton()
        self.last_btn.setText("⇥")
        self.last_btn.setToolTip("末页")
        self.last_btn.clicked.connect(self.last_page)

        for btn in (
            self.first_btn,
            self.prev_btn,
            self.next_btn,
            self.last_btn,
        ):
            btn.setObjectName("PageNavButton")
            btn.setFixedSize(32, 30)

        nav.addStretch()
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_jump)
        self.page_total_label = QLabel("/ 1")
        self.page_total_label.setObjectName("PageTotal")
        self.page_total_label.setMinimumWidth(30)
        nav.addWidget(self.page_total_label)
        nav.addWidget(self.next_btn)
        self.page_badge = InfoBadge("1 / 1")
        self.page_badge.hide()
        nav.addStretch()
        pl.addWidget(nav_frame)
        splitter.addWidget(pc)

        # 右侧
        right = QWidget()
        right.setObjectName("RightPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.setSpacing(6)

        ic, il = self._card("图片素材")
        ic.setObjectName("AssetCard")
        search_row = QHBoxLayout()
        self.image_search = QLineEdit()
        self.image_search.setObjectName("ImageSearch")
        self.image_search.setPlaceholderText(
            "搜索图片素材…"
        )
        self.image_search.setClearButtonEnabled(True)
        self.image_search.setToolTip(
            "输入文件名关键词实时筛选（Ctrl+F）；点击右侧 × 清除搜索"
        )
        search_row.addWidget(self.image_search, 1)

        self._thumbnail_size_value = 96
        self.image_list_view_menu = QMenu(self)
        for label, size in (
            ("小缩略图", 56),
            ("中缩略图", 96),
            ("大缩略图", 150),
        ):
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked=False, value=size:
                self._set_thumbnail_size_preset(value)
            )
            self.image_list_view_menu.addAction(action)

        self.image_list_view_button = QToolButton()
        self.image_list_view_button.setObjectName("PanelMenuButton")
        self.image_list_view_button.setText("⋯")
        self.image_list_view_button.setToolTip("列表显示")
        self.image_list_view_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.image_list_view_button.setMenu(self.image_list_view_menu)
        self.image_list_view_button.setFixedSize(30, 28)
        search_row.addWidget(self.image_list_view_button)
        il.addLayout(search_row)

        self.image_list = ExternalImageListWidget(self)
        self.image_list.setObjectName("ImageList")
        self.image_list.setAcceptDrops(True)
        self.image_list.setIconSize(QSize(96, 65))
        self.image_list.setMinimumHeight(300)

        # UI-05-25A：
        # 列表项自身已经有边框和内边距，不再额外增加大间距。
        self.image_list.setSpacing(0)
        self.image_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.image_list.setUniformItemSizes(False)
        self.image_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.image_list.setWordWrap(False)
        self.image_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.image_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.image_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.image_list.model().rowsMoved.connect(self.on_order_changed)
        self.image_list.model().rowsMoved.connect(
            self._schedule_thumbnail_priority_refresh
        )
        self.image_list.model().rowsRemoved.connect(
            self._schedule_thumbnail_priority_refresh
        )
        self.image_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.image_list.verticalScrollBar().valueChanged.connect(
            self._schedule_thumbnail_priority_refresh
        )
        self.preview.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        # Only the image list stays inside the bordered list area.
        il.addWidget(self.image_list, 1)

        rl.addWidget(ic, 4)

        # UI-05-08 Image Thumbnail Size Control
        # 移除旧版可见/总计统计栏，替换为缩略图尺寸控制

        # 隐藏控件仍需要持久 Qt 父对象。上一版未设置父对象，局部
        # thumb_control 被回收后会连带销毁 QSlider，造成 shiboken
        # "Internal C++ object already deleted" 崩溃。
        thumb_control = QFrame(right)
        thumb_control.setObjectName(
            "ThumbnailControl"
        )
        thumb_layout = QHBoxLayout(thumb_control)
        thumb_layout.setContentsMargins(10, 7, 10, 7)
        thumb_layout.setSpacing(9)

        thumb_icon = QLabel("缩略图")
        thumb_icon.setObjectName(
            "MiniSectionTitle"
        )
        thumb_icon.setToolTip(
            "调整图片列表缩略图大小"
        )
        thumb_layout.addWidget(thumb_icon)

        self.thumbnail_size_slider = QSlider(
            Qt.Orientation.Horizontal,
            thumb_control,
        )
        self.thumbnail_size_slider.setRange(56, 160)
        self.thumbnail_size_slider.setValue(96)
        self.thumbnail_size_slider.setToolTip("调整右侧图片列表▫")
        self.thumbnail_size_slider.valueChanged.connect(
            self.update_thumbnail_size
        )

        thumb_layout.addWidget(self.thumbnail_size_slider, 1)
        thumb_control.hide()


        right.setMinimumWidth(150)
        right.setMaximumWidth(210)
        self.right_panel = right
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([226, 1110, 170])

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        main.addWidget(self.progress)

        # Log is hidden by default and opened from the top toolbar.
        self.log_dock = QDockWidget("生成日志", self)
        self.log_dock.setObjectName("GenerationLogDock")
        self.log_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("生成与操作日志会显示在这里。")
        self.log_dock.setWidget(self.log_box)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()
        self.log_dock.visibilityChanged.connect(self.on_log_visibility_changed)

    def _connect_signals(self):
        self.preview.swapRequested.connect(self.swap_images)

        if hasattr(self.preview, "multiSelectionChanged"):
            self.preview.multiSelectionChanged.connect(
                self.select_images_from_canvas
            )
        else:
            self.preview.selectionChanged.connect(
                self.select_image
            )

        self.preview.zoomChanged.connect(self.set_image_zoom)

        if hasattr(self.preview, "pageTitleEditRequested"):
            self.preview.pageTitleEditRequested.connect(
                self.edit_page_title
            )

        if hasattr(self.preview, "panStarted"):
            self.preview.panStarted.connect(
                self.on_canvas_pan_started
            )
            self.preview.panChanged.connect(
                self.on_canvas_pan_changed
            )
            self.preview.panFinished.connect(
                self.on_canvas_pan_finished
            )

        if hasattr(self.preview, "cropStarted"):
            self.preview.cropStarted.connect(
                self.on_canvas_crop_started
            )
            self.preview.cropChanged.connect(
                self.on_canvas_crop_changed
            )
            self.preview.cropFinished.connect(
                self.on_canvas_crop_finished
            )

        self.image_zoom_slider.valueChanged.connect(self.slider_zoom_changed)
        self.image_zoom_input.valueChanged.connect(self.zoom_input_changed)
        self.offset_x_slider.valueChanged.connect(self.offset_x_changed)
        self.offset_x_input.valueChanged.connect(self.offset_x_input_changed)
        self.offset_y_slider.valueChanged.connect(self.offset_y_changed)
        self.offset_y_input.valueChanged.connect(self.offset_y_input_changed)
        self.rotate_left_btn.clicked.connect(lambda: self.rotate_selected(-90))
        self.rotate_right_btn.clicked.connect(lambda: self.rotate_selected(90))
        self.flip_h_btn.clicked.connect(lambda: self.flip_selected("h"))
        self.flip_v_btn.clicked.connect(lambda: self.flip_selected("v"))
        self.reset_transform_btn.clicked.connect(self.reset_selected_transform)

        self.image_list.itemSelectionChanged.connect(
            self.sync_selection_from_image_list
        )
        self.image_list.customContextMenuRequested.connect(
            self.show_image_list_context_menu
        )
        self.preview.customContextMenuRequested.connect(
            self.show_canvas_context_menu
        )

        # UI-05-25A：文件名实时搜索。
        self.image_search.textChanged.connect(
            self.filter_image_list
        )

        for w in [self.row_step, self.col_step, self.ml, self.mr, self.mt, self.mb, self.gx, self.gy, self.lh]:
            w.valueChanged.connect(self.schedule_preview)
        for w in [self.page_combo, self.mode_combo]:
            w.currentTextChanged.connect(self.schedule_preview)

        self.pagination_mode_combo.currentIndexChanged.connect(
            self.on_pagination_mode_changed
        )
        self.auto_layout_check.toggled.connect(
            self.on_auto_layout_toggled
        )
        self.confirm_auto_layout_btn.clicked.connect(
            self.confirm_auto_layout
        )

        self.title_check.toggled.connect(
            self.on_title_toggled
        )
        self.title_content_mode_combo.currentIndexChanged.connect(
            self._on_title_content_mode_changed
        )
        self.batch_title_apply_btn.clicked.connect(
            self.apply_batch_title
        )
        self.batch_title_edit.returnPressed.connect(
            self.apply_batch_title
        )

        self.title_style_scope_combo.currentIndexChanged.connect(
            self._on_title_style_scope_changed
        )
        self.title_style_inherit_btn.clicked.connect(
            self._reset_current_title_style_override
        )
        self.title_font_combo.currentTextChanged.connect(
            lambda _value: self._on_title_style_field_changed(
                "font_family"
            )
        )
        self.title_font_size_input.valueChanged.connect(
            lambda _value: self._on_title_style_field_changed(
                "font_size"
            )
        )
        self.title_color_button.clicked.connect(
            self._choose_title_color
        )
        self.title_bold_check.toggled.connect(
            lambda _value: self._on_title_style_field_changed(
                "bold"
            )
        )
        self.title_alignment_combo.currentIndexChanged.connect(
            lambda _value: self._on_title_style_field_changed(
                "alignment"
            )
        )
        self.title_top_spacing_input.valueChanged.connect(
            lambda _value: self._on_title_style_field_changed(
                "top_spacing_cm"
            )
        )
        self.title_height_input.valueChanged.connect(
            lambda _value: self._on_title_style_field_changed(
                "region_height_cm"
            )
        )

        self.footer_check.toggled.connect(self.on_footer_toggled)
        self.footer_edit.textChanged.connect(self.schedule_preview)
        for w in [self.filename_check, self.index_check, self.page_check, self.border_check]:
            w.toggled.connect(self.schedule_preview)

    # =====================================================
    # UI-05-26A Shortcut System
    # =====================================================

    def _register_shortcut(
        self,
        sequence,
        slot,
        *,
        parent=None,
        context=Qt.ShortcutContext.WindowShortcut,
        auto_repeat=True,
    ):
        """
        创建并保存 QShortcut，避免快捷键对象被 Python 回收。
        """
        if not hasattr(self, "_shortcut_objects"):
            self._shortcut_objects = []

        shortcut = QShortcut(
            QKeySequence(sequence),
            parent or self,
        )
        shortcut.setContext(context)
        shortcut.setAutoRepeat(bool(auto_repeat))
        shortcut.activated.connect(slot)

        self._shortcut_objects.append(shortcut)
        return shortcut

    def _focus_is_text_editor(self):
        """
        输入文字或数字时，不让方向类快捷键抢占编辑操作。
        """
        focus = QApplication.focusWidget()

        return isinstance(
            focus,
            (
                QLineEdit,
                QTextEdit,
                QSpinBox,
                QDoubleSpinBox,
                QComboBox,
            ),
        )

    def _focus_is_inside(self, root_widget):
        """
        判断当前焦点是否位于指定控件或其子控件内部。
        """
        if root_widget is None:
            return False

        focus = QApplication.focusWidget()

        while focus is not None:
            if focus is root_widget:
                return True
            focus = focus.parentWidget()

        return False

    def _active_shortcut_region(self):
        """
        返回复制/删除快捷键当前应该操作的区域。
        """
        if self._focus_is_inside(self.preview):
            return "canvas"

        if self._focus_is_inside(self.image_list):
            return "image_list"

        page_target = getattr(
            self.slide_thumbnail_bar,
            "page_list",
            self.slide_thumbnail_bar,
        )

        if self._focus_is_inside(page_target):
            return "page_bar"

        return "other"

    def shortcut_duplicate_by_focus(self):
        """
        Ctrl+D：
        - 中央画布或右侧图片列表：复制所选图片
        - 页面导航栏：复制当前页面
        """
        region = self._active_shortcut_region()

        if region in {"canvas", "image_list"}:
            self.duplicate_selected_images()
            return

        if region == "page_bar":
            self.shortcut_duplicate_current_page()
            return

        if hasattr(self, "status_bar"):
            self._show_status(
                "请先点击中央画布、图片列表或页面导航栏",
                2200,
            )

    def shortcut_copy_images(self):
        """Ctrl+C：复制当前选中的图片项到工程内剪贴板。"""
        rows = self._selected_image_rows()
        entries = []
        for row in rows:
            item = self.image_list.item(row)
            path = item.data(Qt.ItemDataRole.UserRole) if item else ""
            if not path:
                continue
            entries.append({
                "path": str(path),
                "transform": dict(self.get_transform(str(path))),
                "hidden": str(path) in self.hidden_images,
            })

        if not entries:
            self._show_status("请先选择要复制的图片", 2200)
            return

        self._image_clipboard = entries
        self._image_clipboard_mode = "copy"
        self._show_status(f"已复制 {len(entries)} 张图片，可切换页面后按 Ctrl+V 粘贴", 3200)

    def shortcut_cut_images(self):
        """Ctrl+X: cut selected image items into the project clipboard."""
        rows = self._selected_image_rows()
        if not rows:
            self._show_status("请先选择要剪切的图片", 2200)
            return

        visible = list(self.visible_images())
        entries = []
        involved_pages = set()
        for row in rows:
            item = self.image_list.item(row)
            path = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
            if not path:
                continue
            entries.append({
                "path": path,
                "transform": dict(self.get_transform(path)),
                "hidden": path in self.hidden_images,
            })
            if path in visible:
                involved_pages.add(
                    self._logical_page_index_for_visible_index(visible.index(path))
                )

        if not entries:
            self._show_status("请先选择要剪切的图片", 2200)
            return
        if any(self._page_lock_meta_for_logical_page(page) for page in involved_pages):
            self._show_status("选中图片所在页面已锁定，请先解锁", 2800)
            return
        if any(self._is_logical_page_in_locked_group(page) for page in involved_pages):
            self._show_status("选中图片所在分组已锁定，请先解锁", 2800)
            return

        self._image_clipboard = entries
        self._image_clipboard_mode = "cut"
        self._delete_history_label_override = (
            "剪切图片" if len(entries) == 1 else f"剪切 {len(entries)} 张图片"
        )
        self.delete_selected_image()
        self._show_status(
            f"已剪切 {len(entries)} 张图片，可切换页面后按 Ctrl+V 粘贴",
            3200,
        )

    def shortcut_paste_images(self):
        """Ctrl+V：将工程内图片剪贴板粘贴到当前页末尾。"""
        if self._active_shortcut_region() not in {"canvas", "image_list", "page_bar", "other"}:
            return
        self.paste_images_to_current_page()

    def paste_images_to_current_page(self):
        """Paste copied assets or move cut assets into the selected page."""
        entries = list(getattr(self, "_image_clipboard", []) or [])
        if not entries:
            self._show_status("剪贴板中没有项目内图片", 2200)
            return

        page_index = int(self._current_logical_page_index())
        if self._page_lock_meta_for_logical_page(page_index):
            self._show_status("当前页面已锁定，请先解锁后再粘贴", 2600)
            return
        if self._is_logical_page_in_locked_group(page_index):
            self._show_status("当前页面属于已锁定分组，请先解锁后再粘贴", 2800)
            return

        source_entries = [entry for entry in entries if Path(entry.get("path", "")).is_file()]
        if not source_entries:
            self._show_status("剪贴板中的图片已不存在，无法粘贴", 2600)
            return

        clipboard_mode = str(getattr(self, "_image_clipboard_mode", "copy"))
        new_paths = []
        created_copy_paths = []
        transform_by_new_path = {}
        try:
            for entry in source_entries:
                source = str(entry["path"])
                if clipboard_mode == "cut" and source not in self.ordered_images():
                    destination = source
                else:
                    destination = self._unique_copy_path(source)
                    shutil.copy2(source, destination)
                    destination = str(destination)
                    created_copy_paths.append(destination)
                new_paths.append(destination)
                transform_by_new_path[destination] = dict(entry.get("transform") or {})
        except Exception as error:
            for path in created_copy_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
            self._show_status(f"粘贴失败：{error}", 3000)
            return

        page_start, page_end = self._page_visible_range(page_index)
        if self._is_blank_page(page_index):
            blank_index = self._blank_page_visible_insertion_index(page_index)
            visible_insert = len(self.visible_images()) if blank_index is None else int(blank_index)
            insert_row = self._list_row_for_visible_insertion(visible_insert)
            blank_page = page_index
        else:
            page_start = int(page_start)
            page_end = int(page_end)
            page_used = max(0, page_end - page_start)
            capacity = max(1, int(self._page_capacity()))
            overflow = max(0, page_used + len(new_paths) - capacity)
            visible_insert = max(page_start, page_end - min(page_used, overflow))
            insert_row = self._list_row_for_visible_insertion(visible_insert)
            blank_page = None

        inserted = self._insert_external_images(
            new_paths,
            insert_row,
            "粘贴图片",
            boundary_belongs_to_previous=True,
            replace_blank_page_index=blank_page,
        )
        if not inserted:
            for path in created_copy_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
            return

        # 统一插入入口会先建立默认变换；此处恢复复制快照，确保
        # 粘贴后的裁切、缩放、旋转和偏移与源图片一致但彼此独立。
        for path, transform in transform_by_new_path.items():
            self.image_transforms[path] = dict(transform)

        if clipboard_mode == "cut":
            self._image_clipboard_mode = "copy"

        # 粘贴项路径唯一，因此可以安全地重新选中它们。
        self.image_list.clearSelection()
        selected_rows = []
        for row in range(self.image_list.count()):
            item = self.image_list.item(row)
            if item and str(item.data(Qt.ItemDataRole.UserRole)) in new_paths:
                item.setSelected(True)
                selected_rows.append(row)
        if selected_rows:
            self.image_list.setCurrentRow(selected_rows[0])
        self.sync_selection_from_image_list()
        self.refresh_image_list_appearance()
        self.refresh_preview()
        self._force_page_thumbnail_refresh()
        self._displayed_page_index = page_index
        self.preview.set_page_index(page_index)
        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(page_index)
        self._show_status(f"已粘贴 {inserted} 张图片到第 {page_index + 1} 页", 3200)

    def move_selected_images_to_adjacent_page(self, direction):
        """把所选图片移到相邻页，复用正式的跨页拖放事务。"""
        direction = -1 if int(direction) < 0 else 1
        rows = self._selected_image_rows()
        if not rows:
            self._show_status("请先选择要移动的图片", 2200)
            return

        current_page = int(self._current_logical_page_index())
        page_count = max(1, int(self.preview.page_count()))
        target_page = current_page + direction
        if not (0 <= target_page < page_count):
            self._show_status("已经是第一页" if direction < 0 else "已经是最后一页", 2200)
            return

        if self._is_blank_page(target_page):
            target_index = self._blank_page_visible_insertion_index(target_page)
            if target_index is None:
                target_index = len(self.visible_images())
        else:
            page_start, page_end = self._page_visible_range(target_page)
            target_index = int(page_end if direction < 0 else page_start)

        # 正式画布投放入口以当前显示页作为目标页。
        self._displayed_page_index = target_page
        self.preview.set_page_index(target_page)
        handled = bool(
            self.handle_image_list_drop_to_current_page(rows, int(target_index))
        )
        if not handled:
            self._displayed_page_index = current_page
            self.preview.set_page_index(current_page)
            self.refresh_preview()
            return

        self._displayed_page_index = target_page
        self.preview.set_page_index(target_page)
        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(target_page)
        self.refresh_preview()

    def shortcut_delete_by_focus(self):
        """
        Delete / Backspace：
        - 中央画布或右侧图片列表：删除所选图片
        - 页面导航栏：删除当前页面
        """
        region = self._active_shortcut_region()

        if region in {"canvas", "image_list"}:
            self.delete_selected_image()
            return

        if region == "page_bar":
            self.shortcut_delete_current_page()
            return

    def _build_shortcuts(self):
        """
        建立 FrameDeck Studio 常用快捷键。

        快捷键按项目、区域焦点、页面导航、图片编辑四组管理。
        """
        self._shortcut_objects = []

        # -------------------------------------------------
        # 工程与通用操作
        # -------------------------------------------------
        self._register_shortcut("Ctrl+N", self.new_project, auto_repeat=False)
        self._register_shortcut("Ctrl+O", self.open_project, auto_repeat=False)
        self._register_shortcut("Ctrl+S", self.save_project, auto_repeat=False)
        self._register_shortcut(
            "Ctrl+Shift+S",
            self.save_project_as,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+I",
            self.add_images,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Enter",
            self.start_generate,
            auto_repeat=False,
        )
        self._register_shortcut(
            "F5",
            self.start_generate,
            auto_repeat=False,
        )

        self._register_shortcut("Ctrl+Z", self.undo, auto_repeat=False)
        self._register_shortcut("Ctrl+Y", self.redo, auto_repeat=False)
        self._register_shortcut(
            "Ctrl+Shift+Z",
            self.redo,
            auto_repeat=False,
        )

        self._register_shortcut(
            "Ctrl+F",
            self.shortcut_focus_search,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Escape",
            self.shortcut_escape,
            auto_repeat=False,
        )
        self._register_shortcut(
            "F1",
            self.show_shortcuts_help,
            auto_repeat=False,
        )
        self._register_shortcut(
            "F11",
            self.shortcut_toggle_fullscreen,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Shift+L",
            self.shortcut_toggle_log,
            auto_repeat=False,
        )
        # -------------------------------------------------
        # 快速聚焦功能区
        # -------------------------------------------------
        self._register_shortcut(
            "Ctrl+1",
            self.shortcut_focus_canvas,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+2",
            self.shortcut_focus_image_list,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+3",
            self.shortcut_focus_page_bar,
            auto_repeat=False,
        )

        # -------------------------------------------------
        # 页面导航
        # -------------------------------------------------
        self._register_shortcut(
            "PageUp",
            self.shortcut_previous_page,
        )
        self._register_shortcut(
            "PageDown",
            self.shortcut_next_page,
        )
        self._register_shortcut(
            "Alt+Left",
            self.shortcut_previous_page,
        )
        self._register_shortcut(
            "Alt+Right",
            self.shortcut_next_page,
        )
        self._register_shortcut(
            "Ctrl+Home",
            self.shortcut_first_page,
        )
        self._register_shortcut(
            "Ctrl+End",
            self.shortcut_last_page,
        )

        self._register_shortcut(
            "Ctrl+Shift+N",
            self.on_thumbnail_add_page,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Shift+Delete",
            self.shortcut_delete_current_page,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Shift+Left",
            lambda: self.shortcut_move_current_page(-1),
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Shift+Right",
            lambda: self.shortcut_move_current_page(1),
            auto_repeat=False,
        )

        # -------------------------------------------------
        # 画布缩放
        # -------------------------------------------------
        self._register_shortcut("Ctrl+-", self.zoom_out)
        self._register_shortcut("Ctrl+=", self.zoom_in)
        self._register_shortcut("Ctrl++", self.zoom_in)
        self._register_shortcut(
            "Ctrl+0",
            lambda: self.apply_zoom("适应窗口"),
        )

        # -------------------------------------------------
        # 图片选择与列表排序
        # -------------------------------------------------
        self._register_shortcut(
            "Ctrl+Up",
            lambda: self.shortcut_select_image(-1),
        )
        self._register_shortcut(
            "Ctrl+Down",
            lambda: self.shortcut_select_image(1),
        )
        self._register_shortcut(
            "Ctrl+Shift+Up",
            lambda: self.shortcut_move_selected_image(-1),
        )
        self._register_shortcut(
            "Ctrl+Shift+Down",
            lambda: self.shortcut_move_selected_image(1),
        )
        # UI-05-33A：
        # Ctrl+D / Delete 只注册一次，再根据当前真实焦点分派。
        # 这样点击中央画布后不会继续复制导航栏页面。
        scoped_context = Qt.ShortcutContext.WidgetWithChildrenShortcut

        self._register_shortcut(
            "Ctrl+D",
            self.shortcut_duplicate_by_focus,
            context=Qt.ShortcutContext.WindowShortcut,
            auto_repeat=False,
        )
        # 只在画布和图片列表获得焦点时接管 Ctrl+C/X/V，避免破坏
        # 标题、搜索框等文本编辑控件的系统剪贴板行为。
        page_shortcut_target = getattr(
            self.slide_thumbnail_bar,
            "page_list",
            self.slide_thumbnail_bar,
        )
        for target in (self.preview, self.image_list):
            self._register_shortcut(
                "Ctrl+C",
                self.shortcut_copy_images,
                parent=target,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                auto_repeat=False,
            )
            self._register_shortcut(
                "Ctrl+X",
                self.shortcut_cut_images,
                parent=target,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                auto_repeat=False,
            )
            self._register_shortcut(
                "Ctrl+V",
                self.shortcut_paste_images,
                parent=target,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                auto_repeat=False,
            )
            self._register_shortcut(
                "Ctrl+PageUp",
                lambda: self.move_selected_images_to_adjacent_page(-1),
                parent=target,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                auto_repeat=False,
            )
            self._register_shortcut(
                "Ctrl+PageDown",
                lambda: self.move_selected_images_to_adjacent_page(1),
                parent=target,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                auto_repeat=False,
            )
        # 切换到第二页后焦点通常在顶部页面导航栏，允许直接 Ctrl+V。
        self._register_shortcut(
            "Ctrl+V",
            self.shortcut_paste_images,
            parent=page_shortcut_target,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Delete",
            self.shortcut_delete_by_focus,
            context=Qt.ShortcutContext.WindowShortcut,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Backspace",
            self.shortcut_delete_by_focus,
            context=Qt.ShortcutContext.WindowShortcut,
            auto_repeat=False,
        )

        for target in (self.preview, self.image_list):
            self._register_shortcut(
                "Ctrl+A",
                self.select_all_visible_images,
                parent=target,
                context=scoped_context,
                auto_repeat=False,
            )

        page_shortcut_target = getattr(
            self.slide_thumbnail_bar,
            "page_list",
            self.slide_thumbnail_bar,
        )

        # -------------------------------------------------
        # 图片精修
        # -------------------------------------------------
        self._register_shortcut(
            "Left",
            lambda: self.shortcut_nudge_selected(-0.01, 0.0),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Right",
            lambda: self.shortcut_nudge_selected(0.01, 0.0),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Up",
            lambda: self.shortcut_nudge_selected(0.0, -0.01),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Down",
            lambda: self.shortcut_nudge_selected(0.0, 0.01),
            parent=self.preview,
            context=scoped_context,
        )

        self._register_shortcut(
            "Shift+Left",
            lambda: self.shortcut_nudge_selected(-0.05, 0.0),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Shift+Right",
            lambda: self.shortcut_nudge_selected(0.05, 0.0),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Shift+Up",
            lambda: self.shortcut_nudge_selected(0.0, -0.05),
            parent=self.preview,
            context=scoped_context,
        )
        self._register_shortcut(
            "Shift+Down",
            lambda: self.shortcut_nudge_selected(0.0, 0.05),
            parent=self.preview,
            context=scoped_context,
        )

        self._register_shortcut(
            "Ctrl+Alt+Left",
            lambda: self.rotate_selected(-90),
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Alt+Right",
            lambda: self.rotate_selected(90),
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Alt+H",
            lambda: self.flip_selected("h"),
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Alt+V",
            lambda: self.flip_selected("v"),
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Alt+R",
            self.reset_selected_transform,
            auto_repeat=False,
        )

        self._register_shortcut(
            "Ctrl+Shift+C",
            self.start_crop_selected,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Ctrl+Alt+C",
            self.reset_selected_crop,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Return",
            self.confirm_canvas_crop,
            parent=self.preview,
            context=scoped_context,
            auto_repeat=False,
        )
        self._register_shortcut(
            "Enter",
            self.confirm_canvas_crop,
            parent=self.preview,
            context=scoped_context,
            auto_repeat=False,
        )

        self._apply_shortcut_tooltips()

    def _apply_shortcut_tooltips(self):
        """
        在现有控件提示中显示主要快捷键。
        """
        self.image_search.setToolTip(
            "输入文件名关键词实时筛选（Ctrl+F）；点击右侧 × 清除搜索"
        )

        self.zoom_minus_btn.setToolTip("缩小画布（Ctrl+-）")
        self.zoom_fit_btn.setToolTip("适应窗口（Ctrl+0）")
        self.zoom_plus_btn.setToolTip("放大画布（Ctrl++）")

        self.first_btn.setToolTip("首页（Ctrl+Home）")
        self.prev_btn.setToolTip("上一页（PageUp / Alt+←）")
        self.next_btn.setToolTip("下一页（PageDown / Alt+→）")
        self.last_btn.setToolTip("末页（Ctrl+End）")

        self.rotate_left_btn.setToolTip("左转 90°（Ctrl+Alt+←）")
        self.rotate_right_btn.setToolTip("右转 90°（Ctrl+Alt+→）")
        self.flip_h_btn.setToolTip("水平镜像（Ctrl+Alt+H）")
        self.flip_v_btn.setToolTip("垂直翻转（Ctrl+Alt+V）")
        self.reset_transform_btn.setToolTip(
            "重置图片参数（Ctrl+Alt+R）"
        )

        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.setToolTip(
                "点击切换页面；拖动调整页面顺序；"
                "导航栏聚焦时 Ctrl+D 复制页"
            )

    # -----------------------------------------------------
    # 快捷键处理：焦点与通用操作
    # -----------------------------------------------------

    def shortcut_focus_search(self):
        self.image_search.setFocus()
        self.image_search.selectAll()

        if hasattr(self, "status_bar"):
            self._show_status(
                "已聚焦文件名搜索",
                1500,
            )

    def shortcut_focus_canvas(self):
        self.preview.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self.preview.setFocus(
            Qt.FocusReason.ShortcutFocusReason
        )

        if hasattr(self, "status_bar"):
            self._show_status(
                "已聚焦中央画布",
                1500,
            )

    def shortcut_focus_image_list(self):
        self.image_list.setFocus(
            Qt.FocusReason.ShortcutFocusReason
        )

        current = self.image_list.currentRow()

        if current < 0 or (
            self.image_list.item(current) is not None
            and self.image_list.item(current).isHidden()
        ):
            for row in range(self.image_list.count()):
                item = self.image_list.item(row)
                if item is not None and not item.isHidden():
                    self.image_list.setCurrentRow(row)
                    break

        if hasattr(self, "status_bar"):
            self._show_status(
                "已聚焦图片列表",
                1500,
            )

    def shortcut_focus_page_bar(self):
        bar = getattr(self, "slide_thumbnail_bar", None)

        if bar is None:
            return

        target = getattr(bar, "page_list", bar)
        target.setFocus(Qt.FocusReason.ShortcutFocusReason)

        if hasattr(self, "status_bar"):
            self._show_status(
                "已聚焦页面导航",
                1500,
            )

    def clear_image_selection(self):
        self.selected_image_index = -1
        self.selected_image_indices = set()

        self.image_list.blockSignals(True)
        self.image_list.setCurrentRow(-1)
        self.image_list.clearSelection()
        self.image_list.blockSignals(False)

        if hasattr(self.preview, "set_selected_indices"):
            self.preview.set_selected_indices(
                [],
                -1,
                reveal=False,
            )
        else:
            self.preview.set_selected_index(
                -1,
                reveal=False,
            )

        self.set_transform_controls_enabled(False)
        self.selected_name_label.setText("未选择图片")
        self.transform_status_badge.setText("默认参数")
        self.preview.update()

    def shortcut_escape(self):
        """
        Esc 优先取消裁切，其次清除搜索，最后取消图片选择。
        """
        if (
            hasattr(self.preview, "is_crop_mode")
            and self.preview.is_crop_mode()
        ):
            self.preview.cancel_crop_mode()
            return

        if self.image_search.text():
            self.image_search.clear()
            self.image_list.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
            return

        self.clear_image_selection()

    def shortcut_toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def shortcut_toggle_log(self):
        self.toggle_log_dock(
            not self.log_dock.isVisible()
        )

    # -----------------------------------------------------
    # 快捷键处理：页面
    # -----------------------------------------------------

    def shortcut_previous_page(self):
        if self._focus_is_text_editor():
            return
        self.previous_page()

    def shortcut_next_page(self):
        if self._focus_is_text_editor():
            return
        self.next_page()

    def shortcut_first_page(self):
        if self._focus_is_text_editor():
            return
        self.first_page()

    def shortcut_last_page(self):
        if self._focus_is_text_editor():
            return
        self.last_page()

    def shortcut_duplicate_current_page(self):
        if self._focus_is_text_editor():
            return

        self.on_thumbnail_duplicate_page(
            self.preview.current_page()
        )

    def shortcut_delete_current_page(self):
        if self._focus_is_text_editor():
            return

        self.on_thumbnail_delete_page(
            self.preview.current_page()
        )

    def shortcut_move_current_page(self, direction):
        if self._focus_is_text_editor():
            return

        bar = getattr(self, "slide_thumbnail_bar", None)

        if (
            bar is None
            or not hasattr(bar, "page_list")
        ):
            return

        page_list = bar.page_list
        current = max(
            0,
            min(
                int(self.preview.current_page()),
                page_list.count() - 1,
            ),
        )

        if direction < 0:
            if current <= 0:
                return
            insertion_row = current - 1
        else:
            if current >= page_list.count() - 1:
                return
            insertion_row = current + 2

        if hasattr(page_list, "move_page_item"):
            page_list.setCurrentRow(current)
            page_list.move_page_item(
                current,
                insertion_row,
            )

    # -----------------------------------------------------
    # 快捷键处理：图片
    # -----------------------------------------------------

    def shortcut_select_image(self, direction):
        if self._focus_is_text_editor():
            return

        images = self.visible_images()

        if not images:
            return

        current = self.selected_image_index

        if current < 0:
            target = 0 if direction >= 0 else len(images) - 1
        else:
            target = max(
                0,
                min(current + int(direction), len(images) - 1),
            )

        self.select_image(target)

    def shortcut_move_selected_image(self, direction):
        if self._focus_is_text_editor():
            return

        images = self.visible_images()
        source = self.selected_image_index

        if not (0 <= source < len(images)):
            return

        target = source + int(direction)

        if not (0 <= target < len(images)):
            return

        self.swap_images(source, target)

    def shortcut_nudge_selected(self, dx, dy):
        """
        微调当前图片偏移。

        画布聚焦时方向键：1%
        画布聚焦时 Shift+方向键：5%
        """
        images = self.visible_images()

        if not (
            0 <= self.selected_image_index < len(images)
        ):
            return

        path = images[self.selected_image_index]
        transform = self.get_transform(path)

        if dx:
            value = float(transform.get("offset_x", 0.0)) + float(dx)
            self.set_selected_transform_value(
                "offset_x",
                value,
                "快捷键水平微调图片",
            )

        if dy:
            value = float(transform.get("offset_y", 0.0)) + float(dy)
            self.set_selected_transform_value(
                "offset_y",
                value,
                "快捷键垂直微调图片",
            )

    def show_shortcuts_help(self):
        box = QMessageBox(self)
        box.setWindowTitle("FrameDeck Studio 快捷键")
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText)

        box.setText(
            """
            <div style="min-width:680px">
            <h3>FrameDeck Studio 常用快捷键</h3>
            <table cellspacing="6" cellpadding="3">
              <tr><td><b>工程</b></td><td>
                Ctrl+N 新建　Ctrl+O 打开　Ctrl+S 保存　
                Ctrl+Shift+S 另存为　Ctrl+I 添加图片
              </td></tr>
              <tr><td><b>生成与历史</b></td><td>
                F5 / Ctrl+Enter 生成 PPT　生成按钮下拉可选 PDF/图片　Ctrl+Z 撤销　
                Ctrl+Y / Ctrl+Shift+Z 重做
              </td></tr>
              <tr><td><b>功能区焦点</b></td><td>
                Ctrl+1 中央画布　Ctrl+2 图片列表　
                Ctrl+3 页面导航　Ctrl+F 搜索文件名
              </td></tr>
              <tr><td><b>页面导航</b></td><td>
                PageUp / Alt+← 上一页　PageDown / Alt+→ 下一页　
                Ctrl+Home 首页　Ctrl+End 末页
              </td></tr>
              <tr><td><b>页面操作</b></td><td>
                Ctrl+Shift+N 新增空白页　
                导航栏聚焦后 Ctrl+D 复制当前页　
                导航栏聚焦后 Delete 删除当前页　
                Ctrl+Shift+Delete 也可删除当前页　
                Ctrl+Shift+← / → 移动当前页
              </td></tr>
              <tr><td><b>画布缩放</b></td><td>
                Ctrl+- 缩小　Ctrl++ 放大　Ctrl+0 适应窗口
              </td></tr>
              <tr><td><b>图片选择、复制与排序</b></td><td>
                Ctrl+单击 增减选择　Shift+单击 连续多选　
                Ctrl+A 全选　Ctrl+D 就地生成图片副本　
                Ctrl+C 复制图片项　Ctrl+X 剪切图片项　Ctrl+V 粘贴到当前页　
                Delete / Backspace 删除所选图片　
                快捷键按当前聚焦区域自动区分图片与页面　
                Ctrl+↑ / ↓ 选择上一张或下一张　
                Ctrl+Shift+↑ / ↓ 向前或向后移动图片　
                Ctrl+PageUp / PageDown 移到相邻页
              </td></tr>
              <tr><td><b>图片微调</b></td><td>
                画布聚焦时方向键移动 1%　
                Shift+方向键移动 5%
              </td></tr>
              <tr><td><b>图片变换与裁切</b></td><td>
                Ctrl+Alt+← / → 旋转　
                Ctrl+Alt+H / V 镜像　
                Ctrl+Alt+R 重置参数　
                Ctrl+Shift+C 进入裁切　
                Ctrl+Alt+C 重置裁切
              </td></tr>
              <tr><td><b>裁切模式</b></td><td>
                拖动边框或控制点调整范围　
                拖动框内移动　
                滚轮缩放裁切范围　
                Enter 确认　Esc 取消
              </td></tr>
              <tr><td><b>其它</b></td><td>
                Esc 清除搜索或取消选择　F11 全屏　
                Ctrl+Shift+L 日志　F1 本窗口
              </td></tr>
            </table>
            </div>
            """
        )

        box.exec()

    def _refresh_title_card_height(
        self,
        deferred=True,
    ):
        """
        FIX07：
        显隐控件后不能直接使用旧 sizeHint，否则 Qt 仍可能使用
        上一帧缓存高度，导致 Logo / 页脚被下方折叠卡遮挡。

        这里先解除旧最小高度，再强制重新计算 content layout，
        最后在事件循环下一帧再校正一次。
        """
        card = getattr(
            self,
            "title_card",
            None,
        )

        if card is None:
            return

        if not card.is_expanded():
            card.setMinimumHeight(
                card.header_button.height()
            )
            return

        # 清除旧高度约束，避免“收起页脚后仍保留旧高度”
        # 或“展开页脚后 sizeHint 还没更新”。
        card.setMinimumHeight(
            card.header_button.height()
        )
        card.content_widget.setMinimumHeight(
            0
        )

        card.content_layout.invalidate()
        card.content_layout.activate()
        card.content_widget.adjustSize()

        root_layout = card.layout()

        if root_layout is not None:
            root_layout.invalidate()
            root_layout.activate()

        content_height = max(
            0,
            card.content_widget.sizeHint().height(),
        )
        header_height = max(
            card.header_button.height(),
            card.header_button.sizeHint().height(),
        )
        target_height = (
            header_height
            + content_height
        )

        card.setMinimumHeight(
            target_height
        )
        card.updateGeometry()

        parent = card.parentWidget()

        if parent is not None:
            parent_layout = parent.layout()

            if parent_layout is not None:
                parent_layout.invalidate()
                parent_layout.activate()

            parent.updateGeometry()

        # setVisible() 后 Qt 的布局缓存可能要到下一事件循环才完全更新。
        if deferred:
            QTimer.singleShot(
                0,
                lambda:
                self._refresh_title_card_height(
                    deferred=False
                ),
            )

    def _update_logo_status_label(self):
        label = getattr(
            self,
            "logo_status_label",
            None,
        )

        if label is None:
            return

        path = str(
            self.logo_edit.text()
            if hasattr(
                self,
                "logo_edit",
            )
            else ""
        ).strip()

        if path:
            filename = Path(path).name
            display_name = (
                filename
                if len(filename) <= 16
                else filename[:13] + "..."
            )
            label.setText(
                f"Logo：{display_name}"
            )
            label.setStyleSheet(
                "font-weight: 600;"
            )
            label.setToolTip(
                path
            )
        else:
            label.setText(
                "Logo：未选择"
            )
            label.setStyleSheet(
                ""
            )
            label.setToolTip(
                "尚未选择 Logo"
            )

        clear_button = getattr(
            self,
            "clear_logo_btn",
            None,
        )

        if clear_button is not None:
            title_enabled = bool(
                self.title_check.isChecked()
                if hasattr(
                    self,
                    "title_check",
                )
                else True
            )
            clear_button.setEnabled(
                bool(path)
                and title_enabled
            )

    def _set_title_controls_enabled(
        self,
        enabled,
    ):
        enabled = bool(enabled)

        for widget_name in (
            "title_content_mode_combo",
            "title_edit",
            "title_style_scope_combo",
            "title_font_combo",
            "title_font_size_input",
            "title_color_button",
            "title_bold_check",
            "title_alignment_combo",
            "title_top_spacing_input",
            "title_height_input",
        ):
            widget = getattr(
                self,
                widget_name,
                None,
            )
            if widget is not None:
                widget.setEnabled(
                    enabled
                )

        # 批量标题输入始终可用；点击“应用”会自动开启或清除标题。
        if hasattr(self, "batch_title_edit"):
            self.batch_title_edit.setEnabled(True)
        if hasattr(self, "batch_title_apply_btn"):
            self.batch_title_apply_btn.setEnabled(True)

        self._update_title_style_inherit_button()

    def on_title_toggled(self, checked):
        self._set_title_controls_enabled(
            checked
        )
        self._sync_title_editor_context(
            force=True
        )
        self._refresh_title_card_height()
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def on_footer_toggled(self, checked):
        checked = bool(
            checked
        )

        # FIX11：
        # 页脚是独立页面功能，与“启用页面标题”无关。
        # 控件始终显示，只根据勾选状态启用文字编辑。
        self.footer_check.setVisible(
            True
        )
        self.footer_edit.setVisible(
            True
        )
        self.footer_edit.setEnabled(
            checked
        )

        self._refresh_title_card_height()
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def clear_logo(self):
        """
        FIX11：显式取消当前 Logo。
        清空路径后立即刷新中央画布、顶部缩略图和后续导出设置。
        """
        if not hasattr(
            self,
            "logo_edit",
        ):
            return

        if not self.logo_edit.text().strip():
            self._update_logo_status_label()
            return

        self.logo_edit.clear()
        self._update_logo_status_label()
        self._refresh_title_card_height()
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

        if hasattr(
            self,
            "status_bar",
        ):
            self._show_status(
                "已取消页面 Logo",
                2500,
            )

    def select_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translated("选择 Logo"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.logo_edit.setText(
                path
            )
            self._update_logo_status_label()
            self._refresh_title_card_height()
            self._force_page_thumbnail_refresh()
            self.schedule_preview()

    def eventFilter(self, obj, event):
        if (
            self._language_runtime_ready
            and self._language == "en_US"
            and event.type() in (
                QEvent.Type.Polish,
                QEvent.Type.Show,
                QEvent.Type.ShowToParent,
                QEvent.Type.ChildAdded,
            )
        ):
            if event.type() != QEvent.Type.ChildAdded:
                try:
                    self._translate_widget_tree(obj)
                except RuntimeError:
                    pass
            else:
                try:
                    root = event.child()
                except (AttributeError, RuntimeError):
                    root = obj
                self._queue_widget_translation(root)

        if isinstance(obj, (QSpinBox, QDoubleSpinBox)) and event.type() == event.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

    def _update_responsive_header(self):
        """Keep primary commands usable at the supported minimum width."""
        show_redundant_badges = self.width() >= 1180
        for name in ("header_layout_badge", "header_project_badge"):
            badge = getattr(self, name, None)
            if badge is not None:
                badge.setVisible(show_redundant_badges)
        title = getattr(self, "brand_title", None)
        if title is not None:
            title.setVisible(show_redundant_badges)
        subtitle = getattr(self, "brand_subtitle", None)
        if subtitle is not None:
            subtitle.setVisible(show_redundant_badges)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_header()

    def disable_numeric_wheel(self):
        # PySide6 findChildren accepts one QObject subclass at a time.
        numeric_widgets = [
            *self.findChildren(QSpinBox),
            *self.findChildren(QDoubleSpinBox),
        ]

        seen = set()
        for widget in numeric_widgets:
            widget_id = id(widget)
            if widget_id in seen:
                continue
            seen.add(widget_id)
            widget.installEventFilter(self)

    def schedule_preview(self, *args):
        """
        延迟刷新排版，并为常用布局/标题/边距设置建立可撤销记录。

        同一轮连续调节只加入一次历史，Ctrl+Z 会回到调节前状态。
        """
        if (
            not self._history_lock
            and not self._settings_history_pending
            and self._last_stable_history_state is not None
        ):
            self.undo_stack.append(
                (
                    "调整排版参数",
                    self._last_stable_history_state,
                )
            )

            if len(self.undo_stack) > 60:
                self.undo_stack.pop(0)

            self.redo_stack.clear()
            self._settings_history_pending = True
            self.update_history_actions()

        self.preview_timer.start(70)

    # =====================================================
    # Template System T-01
    # =====================================================

    def _install_template_menu(self):
        button = getattr(
            self,
            "command_buttons",
            {},
        ).get("模板")

        if button is None:
            return

        try:
            button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        menu = QMenu(button)
        menu.setTitle("专业模板")
        self._template_actions = {}

        catalog = template_catalog()

        for category in (
            "ai_character",
            "film_visual",
        ):
            summaries = catalog.get(
                category,
                [],
            )

            if not summaries:
                continue

            category_menu = menu.addMenu(
                CATEGORY_LABELS.get(
                    category,
                    category,
                )
            )

            for summary in summaries:
                action = category_menu.addAction(
                    summary.name
                )
                action.setToolTip(
                    (
                        f"{summary.description}\n"
                        f"推荐图片："
                        f"{summary.image_slot_count} 张"
                    )
                )
                action.triggered.connect(
                    lambda checked=False, template_id=summary.template_id:
                    self.apply_builtin_template(
                        template_id
                    )
                )
                self._template_actions[
                    summary.template_id
                ] = action

        menu.addSeparator()

        restore_action = menu.addAction(
            "恢复自由网格布局"
        )
        restore_action.triggered.connect(
            self.clear_active_template
        )

        menu.addSeparator()

        file_action = menu.addAction(
            "从 JSON 文件载入…"
        )
        file_action.triggered.connect(
            self.load_template
        )

        save_action = menu.addAction(
            "保存当前设置为模板…"
        )
        save_action.triggered.connect(
            self.save_template
        )

        button.setMenu(menu)
        button.setToolTip(
            "选择AI角色设计或电影视觉开发模板"
        )
        self.template_menu = menu

    def active_template_document(self):
        if not isinstance(
            self._active_template_document,
            dict,
        ):
            return None

        return json.loads(
            json.dumps(
                self._active_template_document,
                ensure_ascii=False,
            )
        )

    def _update_template_badge(self):
        document = self.active_template_document()

        if document:
            short_name = str(
                document.get(
                    "short_name",
                    document.get(
                        "name",
                        "专业模板",
                    ),
                )
            )
            self.header_layout_badge.setText(
                short_name[:14]
            )
            self.header_layout_badge.setToolTip(
                (
                    f"当前模板："
                    f"{document.get('name', short_name)}\n"
                    f"{document.get('description', '')}"
                )
            )
        else:
            self.header_layout_badge.setText(
                (
                    f"{self.row_step.value()} × "
                    f"{self.col_step.value()}"
                )
            )
            self.header_layout_badge.setToolTip(
                "当前为自由网格布局"
            )

    def apply_template_document(
        self,
        document,
        *,
        refresh=True,
    ):
        try:
            normalized = (
                validate_template_document(
                    document
                )
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "模板无效",
                str(error),
            )
            return False

        self._active_template_document = (
            normalized
        )
        self._active_template_id = str(
            normalized.get("id", "")
        )

        self.apply_settings(
            template_fallback_settings(
                normalized
            ),
            preserve_template=True,
        )
        self._update_template_badge()

        if refresh:
            self.refresh_preview()

        image_slots = sum(
            1
            for frame in normalized[
                "layout"
            ].get(
                "frames",
                [],
            )
            if frame.get("type") == "image"
        )
        template_name = normalized.get(
            "name",
            "专业模板",
        )

        self.log_box.append(
            (
                f"已应用模板：{template_name}"
                f"（图片框 {image_slots} 个）"
            )
        )

        if hasattr(self, "status_bar"):
            self._show_status(
                (
                    f"已应用模板：{template_name}。"
                    "当前为T-01兼容预览。"
                ),
                4200,
            )

        self.save_config()
        return True

    def apply_builtin_template(
        self,
        template_id,
    ):
        try:
            document = load_builtin_template(
                template_id
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "模板载入失败",
                str(error),
            )
            return

        self.apply_template_document(
            document
        )

    def clear_active_template(self):
        self._active_template_document = None
        self._active_template_id = ""
        self._update_template_badge()
        self.refresh_preview()
        self.save_config()

        if hasattr(self, "status_bar"):
            self._show_status(
                "已恢复自由网格布局",
                2600,
            )

    def current_zoom_mode(self):
        """
        返回当前画布缩放模式。

        兼容旧版本可能仍存在的 zoom_combo，但不再依赖它。
        """
        combo = getattr(self, "zoom_combo", None)

        if combo is not None:
            try:
                value = self._combo_source_text(combo)
                if value:
                    return value
            except Exception:
                pass

        return getattr(
            self,
            "_zoom_mode",
            "适应窗口",
        )

    def zoom_in(self):
        current = self.current_zoom_mode()
        levels = ["75%", "100%", "125%", "150%"]

        try:
            index = levels.index(current)
        except ValueError:
            index = 1

        index = min(index + 1, len(levels) - 1)
        self.apply_zoom(levels[index])

    def zoom_out(self):
        current = self.current_zoom_mode()
        levels = ["75%", "100%", "125%", "150%"]

        try:
            index = levels.index(current)
        except ValueError:
            index = 1

        index = max(index - 1, 0)
        self.apply_zoom(levels[index])

    def apply_zoom(self, text):
        mapping = {
            "适应窗口": 1.0,
            "75%": 0.75,
            "100%": 1.0,
            "125%": 1.25,
            "150%": 1.5,
        }

        text = str(text or "适应窗口")

        if text not in mapping:
            text = "适应窗口"

        self._zoom_mode = text
        self.preview.set_zoom(mapping[text])

        combo = getattr(self, "zoom_combo", None)

        if combo is not None:
            try:
                index = self._find_combo_source_text(combo, text)

                if index >= 0:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(index)
                    combo.blockSignals(False)
            except Exception:
                pass

        if hasattr(self, "status_zoom"):
            self.status_zoom.setText(
                self._translated(f"画布 {text}")
            )

    def preview_settings(self):
        resolved_title_pages = self._resolved_title_pages()
        if resolved_title_pages:
            current_page = max(
                0,
                min(
                    int(self._current_title_page_index()),
                    len(resolved_title_pages) - 1,
                ),
            )
            current_title = dict(resolved_title_pages[current_page])
        else:
            current_title = resolve_title_context(
                self._title_system,
                page_index=0,
            )
        current_style = dict(
            current_title.get(
                "style",
                {},
            )
        )
        return {
            "language": self._language,
            "rows": self.row_step.value(), "cols": self.col_step.value(),
            "page_size": self._combo_source_text(self.page_combo),
            "image_mode": self._combo_source_text(self.mode_combo),
            "show_title": self.title_check.isChecked(),
            "title_text": str(
                current_title.get(
                    "title",
                    "",
                )
            ).strip(),
            "subtitle_text": "",
            "title_height": float(
                current_style.get(
                    "region_height_cm",
                    0.9,
                )
            ),
            "title_style": current_style,
            "resolved_title_pages": resolved_title_pages,
            "logo_path": "",
            "show_footer": self.footer_check.isChecked(),
            "footer_text": self.footer_edit.text().strip(),
            "show_grid": False,
            "show_filename": self.filename_check.isChecked(),
            "show_index": self.index_check.isChecked(),
            "show_page_number": self.page_check.isChecked(),
            "add_border": self.border_check.isChecked(),
            "margin_left": self.ml.value(), "margin_right": self.mr.value(),
            "margin_top": self.mt.value(), "margin_bottom": self.mb.value(),
            "gap_x": self.gx.value(), "gap_y": self.gy.value(),
            "label_height": self.lh.value(),
            "layout_template": (
                self.active_template_document()
                or {}
            ),
        }

    def ordered_images(self):
        return [
            self.image_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.image_list.count())
        ]

    def visible_images(self):
        return [path for path in self.ordered_images() if path not in self.hidden_images]

    def generation_settings(self):
        preview_data = dict(
            self.preview_settings()
        )

        # “网格”已经从产品功能中移除，它只属于旧预览参数，
        # 不能再传给 core.ppt_generator.generate_ppt()。
        preview_data.pop("show_grid", None)

        # T-01 先保存框架结构，T-02 再交给PPT模板引擎。
        preview_data.pop(
            "layout_template",
            None,
        )

        return {
            "image_paths": self.ordered_images(),
            "image_transforms": {
                path: dict(value)
                for path, value
                in self.image_transforms.items()
            },
            "hidden_images": list(
                self.hidden_images
            ),
            "output_file": (
                self.output_edit.text().strip()
            ),
            "page_breaks": (
                self._effective_page_breaks()
            ),
            "pagination_mode": (
                self._current_pagination_mode()
            ),
            "image_groups": list(
                self._normalize_image_groups()
            ),
            "group_page_breaks": sorted(
                self._normalize_group_page_breaks()
            ),
            "blank_fill_page_breaks": sorted(
                self._normalize_blank_fill_page_breaks()
            ),
            "blank_page_positions": (
                self._blank_page_positions()
            ),
            "title_system": (
                self._title_system_payload()
            ),
            **preview_data,
        }

    # =====================================================
    # UI-05-42A Grouped Pagination / Title Data Model
    # =====================================================

    def _current_pagination_mode(self):
        combo = getattr(
            self,
            "pagination_mode_combo",
            None,
        )

        if combo is not None:
            data = combo.currentData()

            if data:
                self._pagination_mode = (
                    normalize_pagination_mode(data)
                )

        return normalize_pagination_mode(
            self._pagination_mode
        )

    def _group_mode_enabled(self):
        return (
            self._current_pagination_mode()
            == PAGINATION_GROUPED
        )

    def _set_pagination_mode(
        self,
        mode,
        *,
        refresh=False,
    ):
        mode = normalize_pagination_mode(mode)
        self._pagination_mode = mode

        combo = getattr(
            self,
            "pagination_mode_combo",
            None,
        )

        if combo is not None:
            index = combo.findData(mode)

            if index >= 0:
                blocked = combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(blocked)

        auto_layout_check = getattr(
            self,
            "auto_layout_check",
            None,
        )
        if auto_layout_check is not None:
            blocked = auto_layout_check.blockSignals(True)
            auto_layout_check.setChecked(
                mode == PAGINATION_CONTINUOUS
            )
            auto_layout_check.blockSignals(blocked)

        self._update_group_ui_state()

        if refresh:
            self._force_page_thumbnail_refresh()
            self.refresh_preview()

    def _normalize_image_groups(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())
        self._image_groups = normalize_groups(
            self._image_groups,
            image_count,
        )

        self._title_system = normalize_title_system(
            self._title_system,
            group_ids=[
                item["id"]
                for item in self._image_groups
            ],
        )

        return list(
            self._image_groups
        )

    def _group_breaks(self):
        self._normalize_image_groups()

        return group_breaks(
            self._image_groups,
            len(self.visible_images()),
        )

    def _effective_page_breaks(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())
        self._normalize_manual_page_breaks(image_count)
        self._normalize_image_groups(image_count)
        self._normalize_group_page_breaks(image_count)
        self._normalize_blank_fill_page_breaks(image_count)

        # Auto Layout uses only the current rows x columns as page bounds.
        # Stored group/manual boundaries remain available after it is off.
        if (
            self._current_pagination_mode()
            == PAGINATION_CONTINUOUS
        ):
            return []

        if bool(
            getattr(
                self,
                "_confirmed_auto_layout",
                False,
            )
        ):
            # 已确认的自动排版以确认时的页面边界为唯一基准。
            # 旧分组和旧手工分页仍保留在工程中，但不会重新覆盖新版本。
            breaks = set()
        else:
            breaks = set(
                effective_page_breaks(
                    self._manual_page_breaks,
                    self._image_groups,
                    self._current_pagination_mode(),
                    image_count,
                )
            )

        # UI-05-45A：页面边界不再依赖“锁定”或可见分页模式。
        # 用户主动删除后，下一页不会悄悄向前补位。
        breaks.update(
            self._group_page_breaks
        )

        # 空白页转成图片页后，不论连续/分组模式都保持原页面位置。
        breaks.update(
            self._blank_fill_page_breaks
        )

        # UI-05-43C：页面锁 / 分组锁在两种分页模式下都生效。
        breaks.update(
            self._page_lock_breaks(image_count)
        )

        return sorted(
            breaks
        )

    def _normalize_group_page_breaks(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())

        self._group_page_breaks = {
            int(value)
            for value in getattr(
                self,
                "_group_page_breaks",
                set(),
            )
            if (
                0
                < int(value)
                < image_count
            )
        }

        return set(
            self._group_page_breaks
        )

    def _materialize_group_page_boundaries(self):
        """
        将“当前看到的页面边界”记录为分组页面锁。

        用途：
        在分组模式删除图片前先执行一次。
        例如同一组原来是 10 / 10 / 3，
        删除第1页1张后应成为 9 / 10 / 3，
        而不是重新流动成 10 / 10 / 2。
        """
        ranges = self._computed_page_ranges()
        image_count = len(
            self.visible_images()
        )

        locked = set(
            getattr(
                self,
                "_group_page_breaks",
                set(),
            )
        )

        for _start, end in ranges[:-1]:
            end = int(end)

            if 0 < end < image_count:
                locked.add(end)

        self._group_page_breaks = locked
        self._normalize_group_page_breaks()

    def _shift_group_page_breaks_for_insert(
        self,
        visible_index,
        count,
        *,
        keep_break_at_index=True,
    ):
        count = max(
            0,
            int(count),
        )

        if count <= 0:
            return

        visible_index = max(
            0,
            int(visible_index),
        )
        updated = set()

        for page_break in getattr(
            self,
            "_group_page_breaks",
            set(),
        ):
            page_break = int(
                page_break
            )

            if page_break > visible_index:
                updated.add(
                    page_break + count
                )
            elif (
                page_break == visible_index
                and not keep_break_at_index
            ):
                updated.add(
                    page_break + count
                )
            else:
                updated.add(
                    page_break
                )

        # 插入动作发生在列表实际加入之前，不在这里按旧数量归一化。
        self._group_page_breaks = updated

    def _shift_group_page_breaks_for_delete(
        self,
        deleted_indices,
        image_count_before=None,
    ):
        deleted = sorted(
            {
                int(index)
                for index in list(
                    deleted_indices or []
                )
                if int(index) >= 0
            }
        )

        if not deleted:
            return

        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        new_count = max(
            0,
            int(image_count_before)
            - len(deleted),
        )
        updated = set()

        for page_break in getattr(
            self,
            "_group_page_breaks",
            set(),
        ):
            page_break = int(
                page_break
            )
            shift = sum(
                1
                for index in deleted
                if index < page_break
            )
            new_break = (
                page_break
                - shift
            )

            if (
                0
                < new_break
                < new_count
            ):
                updated.add(
                    new_break
                )

        self._group_page_breaks = updated

    def _set_group_page_breaks_from_lengths(
        self,
        lengths,
    ):
        """
        页面重排后重新建立分组模式页面锁。
        短页仍然保留，不允许后页自动回填。
        """
        if not self._group_mode_enabled():
            return

        cumulative = 0
        breaks = set()

        for page_length in list(
            lengths or []
        )[:-1]:
            cumulative += max(
                0,
                int(page_length),
            )

            if cumulative > 0:
                breaks.add(
                    cumulative
                )

        self._group_page_breaks = breaks
        self._normalize_group_page_breaks()

    def _normalize_blank_fill_page_breaks(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())

        self._blank_fill_page_breaks = {
            int(value)
            for value in getattr(
                self,
                "_blank_fill_page_breaks",
                set(),
            )
            if (
                0
                < int(value)
                < image_count
            )
        }

        return set(
            self._blank_fill_page_breaks
        )

    def _shift_blank_fill_page_breaks_for_insert(
        self,
        visible_index,
        count,
        *,
        keep_break_at_index=True,
    ):
        count = max(
            0,
            int(count),
        )

        if count <= 0:
            return

        visible_index = max(
            0,
            int(visible_index),
        )
        updated = set()

        for page_break in getattr(
            self,
            "_blank_fill_page_breaks",
            set(),
        ):
            page_break = int(
                page_break
            )

            if page_break > visible_index:
                updated.add(
                    page_break + count
                )
            elif (
                page_break == visible_index
                and not keep_break_at_index
            ):
                updated.add(
                    page_break + count
                )
            else:
                updated.add(
                    page_break
                )

        self._blank_fill_page_breaks = updated

    def _shift_blank_fill_page_breaks_for_delete(
        self,
        deleted_indices,
        image_count_before=None,
    ):
        deleted = sorted(
            {
                int(index)
                for index in list(
                    deleted_indices or []
                )
                if int(index) >= 0
            }
        )

        if not deleted:
            return

        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        new_count = max(
            0,
            int(image_count_before)
            - len(deleted),
        )
        updated = set()

        for page_break in getattr(
            self,
            "_blank_fill_page_breaks",
            set(),
        ):
            page_break = int(
                page_break
            )
            shift = sum(
                1
                for index in deleted
                if index < page_break
            )
            new_break = (
                page_break
                - shift
            )

            if (
                0
                < new_break
                < new_count
            ):
                updated.add(
                    new_break
                )

        self._blank_fill_page_breaks = updated

    def _set_blank_fill_page_breaks_from_lengths(
        self,
        lengths,
    ):
        """
        页面拖动后按当前页面长度重建固定边界，
        避免短页被重新自动回填。
        """
        cumulative = 0
        breaks = set()

        for page_length in list(
            lengths or []
        )[:-1]:
            cumulative += max(
                0,
                int(page_length),
            )

            if cumulative > 0:
                breaks.add(
                    cumulative
                )

        self._blank_fill_page_breaks = breaks
        self._normalize_blank_fill_page_breaks()

    def _current_logical_page_index(self):
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return 0

        return max(
            0,
            int(
                getattr(
                    self,
                    "_displayed_page_index",
                    preview.current_page(),
                )
            ),
        )

    def _selected_partial_page_insert_context(
        self,
    ):
        """
        UI-05-42B FIX10：
        “添加图片”按钮使用当前选中页面作为首选插入目标。

        返回：
            None
                当前页不是可补充的未满图片页。

            dict
                {
                    "page_index": 当前逻辑页,
                    "page_start": 当前页图片起点,
                    "page_end": 当前页图片终点,
                    "used": 当前已有图片数,
                    "remaining": 当前剩余空槽,
                    "insert_row": 右侧图片列表真实插入行,
                }

        规则：
        - 空白页由 FIX08 的 replace_blank_page_index 单独处理；
        - 当前图片页 1~capacity-1 张时视为“未满页”；
        - 无论该页位于项目中间还是最后，都从该页末尾继续插入；
        - 如果选择图片超过剩余槽位，多余图片紧接当前页继续分页，
          而不是跳到整个项目最后。
        """
        current_page = (
            self._current_logical_page_index()
        )

        if self._is_blank_page(
            current_page
        ):
            return None

        page_start, page_end = (
            self._page_visible_range(
                current_page
            )
        )
        used = max(
            0,
            int(page_end)
            - int(page_start),
        )
        capacity = (
            self._page_capacity()
        )

        if not (
            0
            < used
            < capacity
        ):
            return None

        visible_insert_index = int(
            page_end
        )
        insert_row = (
            self._list_row_for_visible_insertion(
                visible_insert_index
            )
        )

        return {
            "page_index": int(
                current_page
            ),
            "page_start": int(
                page_start
            ),
            "page_end": int(
                page_end
            ),
            "used": int(
                used
            ),
            "remaining": int(
                capacity
                - used
            ),
            "insert_row": int(
                insert_row
            ),
        }

    def _blank_page_visible_insertion_index(
        self,
        logical_page_index,
    ):
        """
        把任意位置空白页映射到正确的图片插入索引。

        图片页01 / 空白页 / 图片页02：
        返回图片页02的起始图片索引，而不是项目末尾。
        """
        logical_page_index = int(
            logical_page_index
        )

        if not self._is_blank_page(
            logical_page_index
        ):
            return None

        blank_positions = (
            self._blank_page_positions()
        )
        blank_before = sum(
            1
            for value in blank_positions
            if value < logical_page_index
        )
        image_pages_before = (
            logical_page_index
            - blank_before
        )

        ranges = self._computed_page_ranges()

        if image_pages_before <= 0:
            return 0

        if image_pages_before >= len(
            ranges
        ):
            return len(
                self.visible_images()
            )

        return int(
            ranges[
                image_pages_before
            ][0]
        )

    def _shift_page_title_metadata_after_page(
        self,
        page_index,
        delta,
    ):
        """
        空白页一次加入超过一页容量的图片时，
        后续单页标题/样式随新增逻辑页整体后移。
        当前空白页自身的单页标题保持在原位置。
        """
        page_index = int(
            page_index
        )
        delta = int(
            delta
        )

        if delta == 0:
            return

        for key_name in (
            "page_titles",
            "page_styles",
        ):
            source = dict(
                self._title_system.get(
                    key_name,
                    {},
                )
                or {}
            )
            updated = {}

            for key, value in source.items():
                try:
                    old_index = int(
                        key
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                new_index = old_index

                if old_index > page_index:
                    new_index = max(
                        0,
                        old_index + delta,
                    )

                updated[
                    str(
                        new_index
                    )
                ] = value

            self._title_system[
                key_name
            ] = updated

    def _consume_blank_page_for_images(
        self,
        logical_page_index,
        inserted_image_count,
    ):
        """
        原位把空白页替换成图片页。

        <= 每页容量：
            空白页直接变成1张图片页，后续页码不变。

        > 每页容量：
            空白页扩展成多张图片页，后续空白页和单页标题整体后移。
        """
        logical_page_index = int(
            logical_page_index
        )
        inserted_image_count = max(
            1,
            int(inserted_image_count),
        )

        if not self._is_blank_page(
            logical_page_index
        ):
            return 0

        created_page_count = max(
            1,
            int(
                math.ceil(
                    inserted_image_count
                    / self._page_capacity()
                )
            ),
        )
        page_delta = (
            created_page_count
            - 1
        )

        updated_positions = []

        for value in (
            self._blank_page_positions()
        ):
            value = int(
                value
            )

            if value == logical_page_index:
                continue

            if (
                value > logical_page_index
                and page_delta
            ):
                value += page_delta

            updated_positions.append(
                value
            )

        self._set_blank_page_positions(
            updated_positions
        )

        if page_delta:
            self._shift_page_title_metadata_after_page(
                logical_page_index,
                page_delta,
            )

        return created_page_count

    def _normalize_lock_state(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())
        valid_group_ids = {
            str(item.get("id", ""))
            for item in self._normalize_image_groups(image_count)
            if item.get("id")
        }

        self._locked_group_ids = {
            str(group_id)
            for group_id in getattr(
                self,
                "_locked_group_ids",
                set(),
            )
            if str(group_id) in valid_group_ids
        }

        normalized = []
        seen = set()

        for raw in list(
            getattr(
                self,
                "_page_lock_records",
                [],
            )
            or []
        ):
            if not isinstance(raw, dict):
                continue

            try:
                start = int(raw.get("start", 0))
                end = int(raw.get("end", 0))
            except (TypeError, ValueError):
                continue

            start = max(0, min(start, image_count))
            end = max(0, min(end, image_count))

            if end <= start:
                continue

            source = str(
                raw.get("source", "page")
                or "page"
            )
            if source not in ("page", "group"):
                source = "page"

            group_id = str(
                raw.get("group_id", "")
                or ""
            )

            if source == "group":
                if (
                    not group_id
                    or group_id
                    not in self._locked_group_ids
                ):
                    continue
            else:
                group_id = ""

            key = (
                source,
                group_id,
                start,
                end,
            )

            if key in seen:
                continue

            seen.add(key)
            normalized.append(
                {
                    "source": source,
                    "group_id": group_id,
                    "start": start,
                    "end": end,
                }
            )

        self._page_lock_records = normalized
        return list(self._page_lock_records)

    def _page_lock_breaks(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())
        self._normalize_lock_state(image_count)
        breaks = set()

        for record in self._page_lock_records:
            start = int(record["start"])
            end = int(record["end"])

            if 0 < start < image_count:
                breaks.add(start)
            if 0 < end < image_count:
                breaks.add(end)

        return breaks

    def _page_lock_meta_for_logical_page(
        self,
        page_index,
    ):
        page_index = int(page_index)

        if self._is_blank_page(page_index):
            return []

        start, end = self._page_visible_range(
            page_index
        )
        self._normalize_lock_state()

        return [
            {
                "source": str(
                    item.get("source", "page")
                ),
                "group_id": str(
                    item.get("group_id", "")
                ),
            }
            for item in self._page_lock_records
            if (
                int(item.get("start", -1))
                == int(start)
                and int(item.get("end", -1))
                == int(end)
            )
        ]

    def _is_current_page_explicitly_locked(self):
        return any(
            item.get("source") == "page"
            for item in (
                self._page_lock_meta_for_logical_page(
                    self._current_logical_page_index()
                )
            )
        )

    def _logical_page_group_id(
        self,
        page_index,
    ):
        page_index = int(page_index)

        if self._is_blank_page(page_index):
            return ""

        start, end = self._page_visible_range(
            page_index
        )

        if start >= end:
            return ""

        return str(
            self._group_id_for_visible_index(
                start
            )
            or ""
        )

    def _is_logical_page_in_locked_group(
        self,
        page_index,
    ):
        group_id = self._logical_page_group_id(
            page_index
        )
        return bool(
            group_id
            and group_id in self._locked_group_ids
        )

    def _shift_page_lock_records_for_insert(
        self,
        visible_index,
        count,
        *,
        boundary_belongs_to_previous=False,
    ):
        count = max(0, int(count))
        if count <= 0:
            return

        visible_index = max(
            0,
            int(visible_index),
        )
        updated = []

        for raw in list(self._page_lock_records):
            record = dict(raw)
            start = int(record.get("start", 0))
            end = int(record.get("end", 0))

            if visible_index < start:
                start += count
                end += count
            elif visible_index == start:
                if boundary_belongs_to_previous:
                    start += count
                    end += count
                else:
                    end += count
            elif start < visible_index < end:
                end += count
            elif (
                visible_index == end
                and boundary_belongs_to_previous
            ):
                end += count

            record["start"] = start
            record["end"] = end
            updated.append(record)

        self._page_lock_records = updated

    def _shift_page_lock_records_for_delete(
        self,
        deleted_indices,
        *,
        image_count_before=None,
    ):
        deleted = sorted(
            {
                int(index)
                for index in list(
                    deleted_indices or []
                )
                if int(index) >= 0
            }
        )

        if not deleted:
            return

        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        new_count = max(
            0,
            int(image_count_before)
            - len(deleted),
        )
        updated = []

        for raw in list(self._page_lock_records):
            record = dict(raw)
            start = int(record.get("start", 0))
            end = int(record.get("end", 0))

            start -= sum(
                1
                for index in deleted
                if index < start
            )
            end -= sum(
                1
                for index in deleted
                if index < end
            )

            start = max(
                0,
                min(start, new_count),
            )
            end = max(
                0,
                min(end, new_count),
            )

            if end <= start:
                continue

            record["start"] = start
            record["end"] = end
            updated.append(record)

        self._page_lock_records = updated

    def _rebuild_page_lock_records_after_reorder(
        self,
        *,
        order,
        page_types,
        page_units,
        page_lock_meta,
    ):
        new_records = []
        cursor = 0

        for old_page_index in list(order):
            if (
                page_types[old_page_index]
                != "images"
            ):
                continue

            length = len(
                page_units[old_page_index]
            )
            start = cursor
            end = cursor + length

            for meta in (
                page_lock_meta[
                    old_page_index
                ]
            ):
                new_records.append(
                    {
                        "source": str(
                            meta.get("source", "page")
                        ),
                        "group_id": str(
                            meta.get("group_id", "")
                        ),
                        "start": start,
                        "end": end,
                    }
                )

            cursor = end

        self._page_lock_records = new_records
        self._normalize_lock_state()

    def _materialize_group_lock_records(
        self,
        group_id,
    ):
        group_id = str(group_id or "")
        if not group_id:
            return

        self._page_lock_records = [
            dict(item)
            for item in self._page_lock_records
            if not (
                item.get("source") == "group"
                and str(
                    item.get("group_id", "")
                )
                == group_id
            )
        ]

        total_pages = max(
            1,
            int(
                self._real_logical_page_count()
            ),
        )

        for page_index in range(total_pages):
            if self._is_blank_page(page_index):
                continue

            start, end = self._page_visible_range(
                page_index
            )

            if start >= end:
                continue

            if (
                self._group_id_for_visible_index(
                    start
                )
                != group_id
            ):
                continue

            self._page_lock_records.append(
                {
                    "source": "group",
                    "group_id": group_id,
                    "start": int(start),
                    "end": int(end),
                }
            )

        self._normalize_lock_state()

    def _update_lock_ui_state(self):
        page_button = getattr(
            self,
            "page_lock_btn",
            None,
        )
        group_button = getattr(
            self,
            "group_lock_btn",
            None,
        )
        hint = getattr(
            self,
            "lock_status_hint",
            None,
        )

        if (
            page_button is None
            or group_button is None
        ):
            return

        if not self.visible_images():
            page_button.setEnabled(False)
            group_button.setEnabled(False)
            page_button.setText("锁定当前页")
            group_button.setText("锁定当前组")
            if hint is not None:
                hint.setText(
                    "当前页：无图片 · 当前组：无"
                )
            return

        self._normalize_lock_state()
        page_index = (
            self._current_logical_page_index()
        )

        if self._is_blank_page(page_index):
            page_button.setEnabled(False)
            page_button.setText("空白页独立")
            group_button.setEnabled(False)
            group_button.setText("锁定当前组")
            if hint is not None:
                hint.setText(
                    "当前页：空白页无需锁定 · 当前组：无"
                )
            return

        group_id = self._logical_page_group_id(
            page_index
        )
        group_locked = bool(
            group_id
            and group_id
            in self._locked_group_ids
        )
        page_locked = (
            self._is_current_page_explicitly_locked()
        )

        group_button.setEnabled(
            bool(group_id)
        )
        group_button.setText(
            "解锁当前组"
            if group_locked
            else "锁定当前组"
        )

        if group_locked:
            page_button.setEnabled(False)
            page_button.setText(
                "本页随组锁定"
            )
        else:
            page_button.setEnabled(True)
            page_button.setText(
                "解锁当前页"
                if page_locked
                else "锁定当前页"
            )

        if hint is not None:
            page_state = (
                "随组锁定"
                if group_locked
                else (
                    "已锁定"
                    if page_locked
                    else "未锁定"
                )
            )

            group_state = (
                "已锁定"
                if group_locked
                else "未锁定"
            )
            hint.setText(
                f"当前页：{page_state}"
                f" · 当前组：{group_state}"
            )

    def toggle_current_page_lock(self):
        if not self.visible_images():
            return

        page_index = (
            self._current_logical_page_index()
        )

        if self._is_blank_page(page_index):
            QMessageBox.information(
                self,
                "页面锁定",
                "空白页本身就是独立页面，不需要额外锁定。",
            )
            return

        if self._is_logical_page_in_locked_group(
            page_index
        ):
            QMessageBox.information(
                self,
                "页面锁定",
                (
                    "当前页已随分组锁定。\n"
                    "如需单独控制，请先解锁当前组。"
                ),
            )
            return

        start, end = self._page_visible_range(
            page_index
        )
        is_locked = (
            self._is_current_page_explicitly_locked()
        )

        self.push_history(
            "解锁当前页"
            if is_locked
            else "锁定当前页"
        )

        if is_locked:
            self._page_lock_records = [
                dict(item)
                for item in self._page_lock_records
                if not (
                    item.get("source") == "page"
                    and int(item.get("start", -1))
                    == int(start)
                    and int(item.get("end", -1))
                    == int(end)
                )
            ]
            message = (
                f"已解锁第 {page_index + 1} 页"
            )
        else:
            self._page_lock_records.append(
                {
                    "source": "page",
                    "group_id": "",
                    "start": int(start),
                    "end": int(end),
                }
            )
            message = (
                f"已锁定第 {page_index + 1} 页"
                " · 删除图片后不会从后页自动补位"
            )

        self._normalize_lock_state()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                message,
                3200,
            )

    def toggle_current_group_lock(self):
        if not self.visible_images():
            return

        page_index = (
            self._current_logical_page_index()
        )
        group_id = (
            self._logical_page_group_id(
                page_index
            )
        )

        if not group_id:
            QMessageBox.information(
                self,
                "分组锁定",
                "当前页不属于可锁定的图片分组。",
            )
            return

        group_row = (
            self._group_manager_row_by_id(
                group_id
            )
        )
        group_name = (
            group_row["name"]
            if group_row
            else "当前分组"
        )
        is_locked = (
            group_id
            in self._locked_group_ids
        )

        self.push_history(
            "解锁当前组"
            if is_locked
            else "锁定当前组"
        )

        if is_locked:
            self._locked_group_ids.discard(
                group_id
            )
            self._page_lock_records = [
                dict(item)
                for item in self._page_lock_records
                if not (
                    item.get("source") == "group"
                    and str(
                        item.get(
                            "group_id",
                            "",
                        )
                    )
                    == group_id
                )
            ]
            message = (
                f"已解锁分组：{group_name}"
            )
        else:
            self._set_pagination_mode(
                PAGINATION_GROUPED,
                refresh=False,
            )
            self._locked_group_ids.add(
                group_id
            )
            self._materialize_group_lock_records(
                group_id
            )
            message = (
                f"已锁定分组：{group_name}"
                " · 组内当前页面结构已固定"
            )

        self._normalize_lock_state()
        self._update_group_ui_state()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                message,
                3400,
            )

    def _group_manager_rows(self):
        groups = self._normalize_image_groups()
        image_count = len(self.visible_images())
        capacity = self._page_capacity()
        rows = []

        for index, group in enumerate(groups):
            start = int(group.get("start", 0))
            end = (
                int(groups[index + 1].get("start", image_count))
                if index + 1 < len(groups)
                else image_count
            )
            count = max(0, end - start)

            rows.append(
                {
                    "ordinal": index + 1,
                    "id": str(group.get("id", "")),
                    "name": str(
                        group.get("name", "")
                        or f"分组 {index + 1:02d}"
                    ),
                    "start": start,
                    "end": end,
                    "image_count": count,
                    "page_count": (
                        max(1, math.ceil(count / capacity))
                        if count
                        else 0
                    ),
                    "locked": (
                        str(
                            group.get(
                                "id",
                                "",
                            )
                        )
                        in self._locked_group_ids
                    ),
                }
            )

        return rows

    def _group_manager_row_by_id(self, group_id):
        group_id = str(group_id or "")

        for row in self._group_manager_rows():
            if row["id"] == group_id:
                return row

        return None

    def _current_group_id_for_manager(self):
        image_count = len(self.visible_images())

        if image_count <= 0:
            return ""

        page_index = self._current_logical_page_index()

        if self._is_blank_page(page_index):
            return ""

        start, end = self._page_visible_range(page_index)

        if start >= end:
            return ""

        return self._group_id_for_visible_index(start)

    def _refresh_after_group_edit(
        self,
        *,
        status_message="",
    ):
        self._normalize_image_groups()
        self._normalize_group_page_breaks()
        self._normalize_lock_state()

        self._title_system = normalize_title_system(
            self._title_system,
            group_ids=[
                item["id"]
                for item in self._image_groups
            ],
        )

        self._sync_title_editor_context(force=True)
        self._update_group_ui_state()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if status_message and hasattr(self, "status_bar"):
            self._show_status(
                status_message,
                3200,
            )

    def open_group_manager(self):
        if not self.visible_images():
            QMessageBox.information(
                self,
                "分组管理",
                "当前工程还没有图片。",
            )
            return

        self._normalize_image_groups()
        dialog = GroupManagerDialog(self)
        dialog.exec()

    def _rename_group(
        self,
        group_id,
        new_name,
    ):
        group_id = str(group_id or "")
        new_name = str(new_name or "").strip()

        if not group_id or not new_name:
            return False

        group = next(
            (
                item
                for item in self._normalize_image_groups()
                if str(item.get("id", "")) == group_id
            ),
            None,
        )

        if group is None:
            return False

        if str(group.get("name", "")) == new_name:
            return True

        self.push_history("重命名分组")

        for item in self._image_groups:
            if str(item.get("id", "")) == group_id:
                item["name"] = new_name
                break

        self._refresh_after_group_edit(
            status_message=f"分组已重命名：{new_name}",
        )
        return True

    def _create_group_at_current_page(self):
        page_index = self._current_logical_page_index()

        if self._is_blank_page(page_index):
            QMessageBox.information(
                self,
                "建立分组",
                "空白页没有图片，不能作为图片分组起点。",
            )
            return ""

        start, end = self._page_visible_range(page_index)
        image_count = len(self.visible_images())

        if (
            start >= end
            or not (0 <= start < image_count)
        ):
            return ""

        groups = self._normalize_image_groups()

        existing = next(
            (
                item
                for item in groups
                if int(item.get("start", -1)) == int(start)
            ),
            None,
        )

        if existing is not None:
            QMessageBox.information(
                self,
                "建立分组",
                (
                    "当前页已经是一个分组的起始页：\n"
                    f"{existing.get('name', '')}"
                ),
            )
            return str(existing.get("id", ""))

        source_group = group_for_index(
            groups,
            start,
            image_count,
        )

        source_group_id = (
            str(
                source_group.get(
                    "id",
                    "",
                )
            )
            if source_group
            else ""
        )

        if (
            source_group_id
            and source_group_id
            in self._locked_group_ids
        ):
            QMessageBox.information(
                self,
                "分组已锁定",
                (
                    "当前分组处于锁定状态。\n"
                    "请先解锁当前组，再建立新的分组边界。"
                ),
            )
            return ""

        base_name = (
            str(source_group.get("name", ""))
            if source_group
            else "分组"
        )
        default_name = f"{base_name} · 新分组"

        new_name, accepted = QInputDialog.getText(
            self,
            "建立新分组",
            "新分组名称：",
            QLineEdit.EchoMode.Normal,
            default_name,
        )

        if not accepted:
            return ""

        new_name = str(new_name).strip()

        if not new_name:
            return ""

        self.push_history("当前页建立新分组")

        new_groups = [
            dict(item)
            for item in groups
        ]
        new_groups.append(
            {
                "name": new_name,
                "start": int(start),
            }
        )

        self._image_groups = normalize_groups(
            new_groups,
            image_count,
        )

        new_group = next(
            (
                item
                for item in self._image_groups
                if int(item.get("start", -1)) == int(start)
            ),
            None,
        )

        new_group_id = (
            str(new_group.get("id", ""))
            if new_group
            else ""
        )

        self._refresh_after_group_edit(
            status_message=(
                f"已从第 {page_index + 1} 页建立新分组：{new_name}"
            ),
        )

        return new_group_id

    def _merge_group_with_neighbor(
        self,
        group_id,
        direction,
    ):
        group_id = str(group_id or "")
        direction = -1 if int(direction) < 0 else 1

        groups = self._normalize_image_groups()

        index = next(
            (
                i
                for i, item in enumerate(groups)
                if str(item.get("id", "")) == group_id
            ),
            -1,
        )

        if index < 0:
            return ""

        if direction < 0:
            if index <= 0:
                return ""
            remove_index = index
            keep_index = index - 1
        else:
            if index >= len(groups) - 1:
                return ""
            remove_index = index + 1
            keep_index = index

        keep_group = dict(groups[keep_index])
        remove_group = dict(groups[remove_index])

        if (
            str(
                keep_group.get(
                    "id",
                    "",
                )
            )
            in self._locked_group_ids
            or str(
                remove_group.get(
                    "id",
                    "",
                )
            )
            in self._locked_group_ids
        ):
            QMessageBox.information(
                self,
                "分组已锁定",
                (
                    "参与合并的分组中存在已锁定分组。\n"
                    "请先解锁分组，再执行合并。"
                ),
            )
            return ""

        answer = QMessageBox.question(
            self,
            "合并分组",
            (
                f"将“{remove_group.get('name', '')}”"
                f"合并到“{keep_group.get('name', '')}”？\n\n"
                "图片顺序不会改变，只会删除两个分组之间的边界。"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.Yes,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return ""

        self.push_history("合并分组")

        removed_id = str(remove_group.get("id", ""))
        kept_id = str(keep_group.get("id", ""))

        self._image_groups = [
            dict(item)
            for item in groups
            if str(item.get("id", "")) != removed_id
        ]
        self._normalize_image_groups()

        for key_name in (
            "group_titles",
            "group_styles",
        ):
            mapping = dict(
                self._title_system.get(key_name, {})
                or {}
            )
            mapping.pop(removed_id, None)
            self._title_system[key_name] = mapping

        self._refresh_after_group_edit(
            status_message=(
                f"已合并分组：{keep_group.get('name', '')}"
            ),
        )

        return kept_id

    def _locate_group(self, group_id):
        row = self._group_manager_row_by_id(group_id)

        if row is None:
            return False

        start = int(row["start"])
        ranges = self._computed_page_ranges()
        image_page_index = 0

        for index, (page_start, page_end) in enumerate(ranges):
            if int(page_start) <= start < int(page_end):
                image_page_index = index
                break

        logical_page_index = (
            self._logical_page_index_for_image_page(
                image_page_index
            )
        )

        self._displayed_page_index = logical_page_index
        self.preview.set_page_index(logical_page_index)
        self._sync_title_editor_context(force=True)
        self._sync_slide_navigator_selection(
            logical_page_index
        )

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已定位到分组：{row['name']}",
                2200,
            )

        return True

    def _group_id_for_visible_index(
        self,
        visible_index,
    ):
        group = group_for_index(
            self._image_groups,
            visible_index,
            len(self.visible_images()),
        )

        return (
            str(group.get("id", ""))
            if group
            else ""
        )

    def _should_start_new_import_group(self):
        checkbox = getattr(
            self,
            "new_import_group_check",
            None,
        )

        return bool(
            self._group_mode_enabled()
            and checkbox is not None
            and checkbox.isChecked()
        )

    def _next_group_name(self, suggested=""):
        suggested = str(suggested or "").strip()

        if suggested:
            return suggested

        return f"分组 {len(self._image_groups) + 1:02d}"

    def _shift_image_groups_for_insert(
        self,
        visible_index,
        count,
        *,
        boundary_belongs_to_previous=False,
        create_new_group=False,
        new_group_name="",
        image_count_before=None,
    ):
        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        self._image_groups = shift_groups_for_insert(
            self._image_groups,
            visible_index,
            count,
            image_count_before,
            boundary_belongs_to_previous=(
                boundary_belongs_to_previous
            ),
            create_new_group=create_new_group,
            new_group_name=(
                self._next_group_name(
                    new_group_name
                )
            ),
        )

    def _shift_image_groups_for_delete(
        self,
        deleted_indices,
        *,
        image_count_before=None,
    ):
        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        self._image_groups = shift_groups_for_delete(
            self._image_groups,
            deleted_indices,
            image_count_before,
        )

    def _rebuild_groups_from_reordered_pages(
        self,
        page_lengths,
        page_group_ids,
    ):
        if not self._group_mode_enabled():
            return

        old_meta = {
            str(item.get("id", "")): dict(item)
            for item in self._image_groups
        }

        new_groups = []
        cursor = 0
        previous_original_id = None
        already_used_original_ids = set()

        for page_length, original_id in zip(
            list(page_lengths or []),
            list(page_group_ids or []),
        ):
            page_length = max(
                0,
                int(page_length),
            )

            if page_length <= 0:
                continue

            original_id = str(original_id or "")

            if (
                not new_groups
                or original_id
                != previous_original_id
            ):
                meta = dict(
                    old_meta.get(
                        original_id,
                        {},
                    )
                )

                # 同一原分组被用户拆成不连续的两个页面段时，
                # 后面的段创建新ID，避免一个ID对应两个不连续区域。
                if (
                    not original_id
                    or original_id
                    in already_used_original_ids
                ):
                    meta.pop("id", None)

                meta["start"] = cursor
                new_groups.append(meta)
                already_used_original_ids.add(
                    original_id
                )
                previous_original_id = original_id

            cursor += page_length

        self._image_groups = normalize_groups(
            new_groups,
            len(self.visible_images()),
        )

    def _title_system_payload(self):
        self._normalize_image_groups()

        self._title_system = normalize_title_system(
            self._title_system,
            group_ids=[
                item["id"]
                for item in self._image_groups
            ],
        )

        return json.loads(
            json.dumps(
                self._title_system,
                ensure_ascii=False,
                default=str,
            )
        )

    def _load_title_system(self, value):
        self._normalize_image_groups()

        incoming = (
            value
            if isinstance(value, dict)
            else {}
        )

        if not incoming:
            self._title_system = normalize_title_system(
                {},
                global_title=(
                    self.title_edit.text().strip()
                ),
                global_subtitle=(
                    self.subtitle_edit.text().strip()
                ),
                title_height=(
                    self.title_height_input.value()
                ),
                title_enabled=(
                    self.title_check.isChecked()
                ),
                group_ids=[
                    item["id"]
                    for item in self._image_groups
                ],
            )
        else:
            self._title_system = normalize_title_system(
                incoming,
                group_ids=[
                    item["id"]
                    for item in self._image_groups
                ],
            )

        self._activate_simplified_title_model()

    def _activate_simplified_title_model(self):
        """Use one shared title plus optional per-page overrides."""
        self._title_system = normalize_title_system(
            self._title_system,
            group_ids=[
                item["id"]
                for item in self._image_groups
            ],
        )
        self._title_system["content_mode"] = "page"
        self._title_system["global_subtitle"] = ""
        # 标题样式只保留一套全局样式，左侧调整会稳定作用于全部页。
        self._title_system["group_styles"] = {}
        self._title_system["page_styles"] = {}

        for collection_name in ("group_titles", "page_titles"):
            collection = self._title_system.get(collection_name, {})
            if not isinstance(collection, dict):
                continue
            for record in collection.values():
                if isinstance(record, dict):
                    record["subtitle"] = ""

        mode_combo = getattr(self, "title_content_mode_combo", None)
        if mode_combo is not None:
            blocked = mode_combo.blockSignals(True)
            index = mode_combo.findData("page")
            if index >= 0:
                mode_combo.setCurrentIndex(index)
            mode_combo.blockSignals(blocked)

        style_combo = getattr(self, "title_style_scope_combo", None)
        if style_combo is not None:
            blocked = style_combo.blockSignals(True)
            index = style_combo.findData("global")
            if index >= 0:
                style_combo.setCurrentIndex(index)
            style_combo.blockSignals(blocked)

        batch_editor = getattr(self, "batch_title_edit", None)
        if batch_editor is not None and not batch_editor.hasFocus():
            blocked = batch_editor.blockSignals(True)
            batch_editor.setText(
                str(self._title_system.get("global_title", "") or "")
            )
            batch_editor.blockSignals(blocked)

        self._sync_title_editor_context(force=True)

    def apply_batch_title(self):
        """Apply the shared title explicitly; typing alone never overwrites pages."""
        title = self.batch_title_edit.text().strip()
        self.push_history("批量设置页面标题")
        self._title_system["content_mode"] = "page"
        self._title_system["global_title"] = title
        self._title_system["global_subtitle"] = ""
        self._title_system["group_titles"] = {}
        self._title_system["page_titles"] = {}

        blocked = self.title_check.blockSignals(True)
        self.title_check.setChecked(bool(title))
        self.title_check.blockSignals(blocked)
        self._set_title_controls_enabled(bool(title))
        self._activate_simplified_title_model()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()
        self._show_status(
            "已将统一标题应用到全部页面"
            if title
            else "已清除全部页面标题",
            2800,
        )

    def edit_page_title(self, page_index):
        """Open a focused editor from the canvas for one logical page."""
        page_index = max(0, int(page_index))
        context = self._resolved_title_context_for_page(page_index)
        current_title = str(context.get("title", "") or "")
        dialog_title = self._translated("编辑页面标题")
        if self._language == "en_US":
            prompt = f"Title for page {page_index + 1}:"
        else:
            prompt = f"第 {page_index + 1} 页标题："

        title, accepted = QInputDialog.getText(
            self,
            dialog_title,
            prompt,
            QLineEdit.EchoMode.Normal,
            current_title,
        )
        if not accepted:
            return

        title = str(title).strip()
        self.push_history("编辑单页标题")
        self._title_system["content_mode"] = "page"
        self._title_system["global_subtitle"] = ""
        page_titles = self._title_system.setdefault("page_titles", {})
        inherited = str(self._title_system.get("global_title", "") or "")

        if not title or title == inherited:
            page_titles.pop(str(page_index), None)
        else:
            page_titles[str(page_index)] = {
                "title": title,
                "subtitle": "",
            }

        has_any_title = bool(inherited) or any(
            str(record.get("title", "") or "").strip()
            for record in page_titles.values()
            if isinstance(record, dict)
        )
        blocked = self.title_check.blockSignals(True)
        self.title_check.setChecked(has_any_title)
        self.title_check.blockSignals(blocked)
        self._set_title_controls_enabled(has_any_title)
        self._activate_simplified_title_model()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if self._language == "en_US":
            message = f"Page {page_index + 1} title updated"
        else:
            message = f"已更新第 {page_index + 1} 页标题"
        self._show_status(message, 2600)

    def _title_content_mode(self):
        combo = getattr(
            self,
            "title_content_mode_combo",
            None,
        )
        if combo is None:
            return "global"

        mode = str(
            combo.currentData()
            or "global"
        )
        if mode not in {
            "global",
            "group",
            "page",
        }:
            mode = "global"
        return mode

    def _title_style_scope(self):
        combo = getattr(
            self,
            "title_style_scope_combo",
            None,
        )
        if combo is None:
            return "global"

        scope = str(
            combo.currentData()
            or "global"
        )
        if scope not in {
            "global",
            "group",
            "page",
        }:
            scope = "global"
        return scope

    def _current_title_page_index(self):
        preview = getattr(
            self,
            "preview",
            None,
        )
        if preview is None:
            return 0

        try:
            return max(
                0,
                int(
                    preview.current_page()
                ),
            )
        except Exception:
            return 0

    def _current_title_group(self):
        page_index = (
            self._current_title_page_index()
        )
        start, end = (
            self._page_visible_range(
                page_index
            )
        )

        if start >= end:
            return None

        return group_for_index(
            self._image_groups,
            start,
            len(
                self.visible_images()
            ),
        )

    def _current_title_group_id(self):
        group = self._current_title_group()
        return (
            str(
                group.get(
                    "id",
                    "",
                )
            )
            if group
            else ""
        )

    def _current_title_group_name(self):
        group = self._current_title_group()
        return (
            str(
                group.get(
                    "name",
                    "",
                )
            )
            if group
            else ""
        )

    def _sync_title_mode_control(self):
        combo = getattr(
            self,
            "title_content_mode_combo",
            None,
        )
        if combo is None:
            return

        mode = str(
            self._title_system.get(
                "content_mode",
                "global",
            )
            or "global"
        )
        if mode == "none":
            mode = "global"

        index = combo.findData(mode)
        if index < 0:
            index = combo.findData(
                "global"
            )

        blocked = combo.blockSignals(True)
        try:
            combo.setCurrentIndex(
                max(0, index)
            )
        finally:
            combo.blockSignals(blocked)

    def _sync_title_editor_context(
        self,
        *,
        force=False,
    ):
        if not hasattr(
            self,
            "title_edit",
        ):
            return

        self._title_system = normalize_title_system(
            self._title_system,
            group_ids=[
                item["id"]
                for item in self._image_groups
            ],
        )

        mode = self._title_content_mode()
        page_index = (
            self._current_title_page_index()
        )
        group_id = (
            self._current_title_group_id()
        )
        group_name = (
            self._current_title_group_name()
        )

        if mode == "global":
            context_text = (
                "当前范围：全部页面"
            )
        elif mode == "group":
            context_text = (
                "当前分组："
                + (
                    group_name
                    or "当前页没有图片分组"
                )
            )
        else:
            context_text = (
                f"当前页：第 {page_index + 1} 页"
            )
            if group_name:
                context_text += (
                    f" · {group_name}"
                )

        self.title_context_label.setText(
            context_text
        )

        raw = title_record_for_scope(
            self._title_system,
            mode,
            group_id=group_id,
            page_index=page_index,
        )

        if mode == "global":
            inherited = {
                "title": "",
                "subtitle": "",
            }
        else:
            inherited = inherited_title_record(
                self._title_system,
                group_id=group_id,
                page_index=page_index,
                exclude_scope=mode,
            )

        for widget, value in (
            (
                self.title_edit,
                raw.get(
                    "title",
                    "",
                ),
            ),
            (
                self.subtitle_edit,
                raw.get(
                    "subtitle",
                    "",
                ),
            ),
        ):
            blocked = widget.blockSignals(True)
            try:
                widget.setText(
                    str(
                        value
                        or ""
                    )
                )
            finally:
                widget.blockSignals(blocked)

        if mode == "global":
            self.title_edit.setPlaceholderText(
                "所有页面统一主标题"
            )
            self.subtitle_edit.setPlaceholderText(
                "所有页面统一副标题（可选）"
            )
        else:
            inherited_title = str(
                inherited.get(
                    "title",
                    "",
                )
                or ""
            )
            inherited_subtitle = str(
                inherited.get(
                    "subtitle",
                    "",
                )
                or ""
            )
            self.title_edit.setPlaceholderText(
                (
                    "未填写时继承："
                    + inherited_title
                )
                if inherited_title
                else "当前范围主标题"
            )
            self.subtitle_edit.setPlaceholderText(
                (
                    "未填写时继承："
                    + inherited_subtitle
                )
                if inherited_subtitle
                else "当前范围副标题（可选）"
            )

        content_available = bool(
            mode != "group"
            or group_id
        )
        enabled = bool(
            self.title_check.isChecked()
            and content_available
        )
        self.title_edit.setEnabled(
            enabled
        )
        self.subtitle_edit.setEnabled(
            enabled
        )

        self._sync_title_style_controls()

    def _on_title_content_mode_changed(
        self,
        *_args,
    ):
        mode = self._title_content_mode()
        self._title_system[
            "content_mode"
        ] = mode
        self.push_history(
            "调整标题内容方式"
        )
        self._sync_title_editor_context(
            force=True
        )
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def _on_title_content_edited(
        self,
        *_args,
    ):
        mode = self._title_content_mode()
        page_index = (
            self._current_title_page_index()
        )
        group_id = (
            self._current_title_group_id()
        )
        title = self.title_edit.text()
        subtitle = self.subtitle_edit.text()

        self._title_system[
            "content_mode"
        ] = mode

        if mode == "global":
            self._title_system[
                "global_title"
            ] = title
            self._title_system[
                "global_subtitle"
            ] = subtitle

        elif mode == "group" and group_id:
            self._title_system.setdefault(
                "group_titles",
                {},
            )[
                group_id
            ] = {
                "title": title,
                "subtitle": subtitle,
            }

        elif mode == "page":
            self._title_system.setdefault(
                "page_titles",
                {},
            )[
                str(page_index)
            ] = {
                "title": title,
                "subtitle": subtitle,
            }

        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def _effective_title_style_for_scope(
        self,
        scope,
    ):
        page_index = (
            self._current_title_page_index()
        )
        group_id = (
            self._current_title_group_id()
        )
        global_style = normalize_title_style(
            self._title_system.get(
                "global_style",
                {},
            )
        )

        if scope == "global":
            return global_style

        if scope == "group":
            raw = dict(
                self._title_system.get(
                    "group_styles",
                    {},
                ).get(
                    group_id,
                    {},
                )
                or {}
            )
            return normalize_title_style(
                raw,
                global_style,
            )

        return resolve_title_style(
            self._title_system,
            group_id=group_id,
            page_index=page_index,
        )

    def _sync_title_style_controls(self):
        if not hasattr(
            self,
            "title_font_combo",
        ):
            return

        scope = self._title_style_scope()
        style = (
            self._effective_title_style_for_scope(
                scope
            )
        )

        controls = [
            self.title_font_combo,
            self.title_font_size_input,
            self.title_bold_check,
            self.title_alignment_combo,
            self.title_top_spacing_input,
            self.title_height_input,
        ]
        previous = [
            widget.blockSignals(True)
            for widget in controls
        ]

        try:
            self.title_font_combo.setCurrentText(
                str(
                    style[
                        "font_family"
                    ]
                )
            )
            self.title_font_size_input.setValue(
                float(
                    style[
                        "font_size"
                    ]
                )
            )
            self.title_bold_check.setChecked(
                bool(
                    style[
                        "bold"
                    ]
                )
            )
            safe_title_height = math.ceil(
                minimum_title_region_height_cm(
                    style["font_size"],
                    bool(style["bold"]),
                )
                * 100.0
            ) / 100.0
            self.title_height_input.setMinimum(safe_title_height)

            align_index = (
                self.title_alignment_combo.findData(
                    style[
                        "alignment"
                    ]
                )
            )
            if align_index >= 0:
                self.title_alignment_combo.setCurrentIndex(
                    align_index
                )

            self.title_top_spacing_input.setValue(
                float(
                    style[
                        "top_spacing_cm"
                    ]
                )
            )
            self.title_height_input.setValue(
                max(
                    safe_title_height,
                    float(style["region_height_cm"]),
                )
            )
        finally:
            for widget, blocked in zip(
                controls,
                previous,
            ):
                widget.blockSignals(
                    blocked
                )

        self._set_title_color_button(
            style[
                "color"
            ]
        )
        self._update_title_style_inherit_button()

    def _title_style_field_value(
        self,
        field_name,
    ):
        if field_name == "font_family":
            return (
                self.title_font_combo.currentText().strip()
                or "Microsoft YaHei"
            )
        if field_name == "font_size":
            return self.title_font_size_input.value()
        if field_name == "color":
            return str(
                self.title_color_button.property(
                    "titleColor"
                )
                or "#111827"
            )
        if field_name == "bold":
            return self.title_bold_check.isChecked()
        if field_name == "alignment":
            return (
                self.title_alignment_combo.currentData()
                or "center"
            )
        if field_name == "top_spacing_cm":
            return self.title_top_spacing_input.value()
        if field_name == "region_height_cm":
            return self.title_height_input.value()
        return None

    def _enforce_title_height_for_font(self, *, notify=False):
        safe_height = math.ceil(
            minimum_title_region_height_cm(
                self.title_font_size_input.value(),
                self.title_bold_check.isChecked(),
            )
            * 100.0
        ) / 100.0
        expanded = self.title_height_input.value() < safe_height
        self.title_height_input.setMinimum(safe_height)
        if expanded:
            self.title_height_input.setValue(safe_height)
            if notify:
                self._show_status(
                    f"标题高度已自动调整为 {safe_height:.2f} cm，避免遮挡图片",
                    3200,
                )
        return expanded

    def _on_title_style_field_changed(
        self,
        field_name,
    ):
        if not self.title_check.isChecked():
            return

        if field_name in {"font_size", "bold"}:
            self._enforce_title_height_for_font(notify=True)

        scope = self._title_style_scope()
        group_id = (
            self._current_title_group_id()
        )
        page_index = (
            self._current_title_page_index()
        )
        value = self._title_style_field_value(
            field_name
        )

        if scope == "global":
            style = normalize_title_style(
                self._title_system.get(
                    "global_style",
                    {},
                )
            )
            style[
                field_name
            ] = value
            self._title_system[
                "global_style"
            ] = normalize_title_style(
                style
            )

        elif scope == "group" and group_id:
            override = dict(
                self._title_system.setdefault(
                    "group_styles",
                    {},
                ).get(
                    group_id,
                    {},
                )
                or {}
            )
            override[
                field_name
            ] = value
            self._title_system[
                "group_styles"
            ][
                group_id
            ] = override

        elif scope == "page":
            key = str(
                page_index
            )
            override = dict(
                self._title_system.setdefault(
                    "page_styles",
                    {},
                ).get(
                    key,
                    {},
                )
                or {}
            )
            override[
                field_name
            ] = value
            self._title_system[
                "page_styles"
            ][
                key
            ] = override

        self._update_title_style_inherit_button()
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def _set_title_color_button(
        self,
        color,
    ):
        color = str(
            color
            or "#111827"
        ).upper()
        qcolor = QColor(
            color
        )
        if not qcolor.isValid():
            color = "#111827"
            qcolor = QColor(
                color
            )

        self.title_color_button.setProperty(
            "titleColor",
            color,
        )
        self.title_color_button.setText(
            f"■  {color}"
        )

        luminance = (
            0.299 * qcolor.red()
            + 0.587 * qcolor.green()
            + 0.114 * qcolor.blue()
        )
        foreground = (
            "#111827"
            if luminance > 170
            else "#FFFFFF"
        )
        self.title_color_button.setStyleSheet(
            (
                "QPushButton {"
                f"background: {color};"
                f"color: {foreground};"
                "border-radius: 7px;"
                "padding: 4px 8px;"
                "font-weight: 700;"
                "}"
            )
        )

    def _choose_title_color(self):
        current = QColor(
            str(
                self.title_color_button.property(
                    "titleColor"
                )
                or "#111827"
            )
        )
        chosen = QColorDialog.getColor(
            current,
            self,
            "选择标题颜色",
        )
        if not chosen.isValid():
            return

        self._set_title_color_button(
            chosen.name().upper()
        )
        self._on_title_style_field_changed(
            "color"
        )

    def _update_title_style_inherit_button(
        self,
    ):
        button = getattr(
            self,
            "title_style_inherit_btn",
            None,
        )
        if button is None:
            return

        scope = self._title_style_scope()
        enabled = bool(
            self.title_check.isChecked()
            and scope != "global"
        )
        if scope == "group":
            enabled = bool(
                enabled
                and self._current_title_group_id()
            )

        button.setEnabled(
            enabled
        )

    def _reset_current_title_style_override(
        self,
    ):
        scope = self._title_style_scope()
        group_id = (
            self._current_title_group_id()
        )
        page_index = (
            self._current_title_page_index()
        )

        if scope == "group":
            self._title_system.setdefault(
                "group_styles",
                {},
            ).pop(
                group_id,
                None,
            )
        elif scope == "page":
            self._title_system.setdefault(
                "page_styles",
                {},
            ).pop(
                str(page_index),
                None,
            )
        else:
            return

        self.push_history(
            "恢复标题样式继承"
        )
        self._sync_title_style_controls()
        self._force_page_thumbnail_refresh()
        self.schedule_preview()

    def _on_title_style_scope_changed(
        self,
        *_args,
    ):
        self._sync_title_style_controls()

    def _resolved_title_pages(self):
        self._normalize_image_groups()
        visible_images = list(self.visible_images())
        image_count = len(visible_images)
        groups = list(self._image_groups)

        total_page_count = max(
            1,
            (
                int(
                    self.preview.page_count()
                )
                if getattr(
                    self,
                    "preview",
                    None,
                ) is not None
                else (
                    len(
                        self._computed_page_ranges()
                    )
                    + self._compat_blank_page_count()
                )
            ),
        )
        page_ranges = self._logical_page_ranges_snapshot(
            total_page_count,
            image_ranges=self._computed_page_ranges(),
            image_count=image_count,
        )
        contexts = []

        for page_index in range(
            total_page_count
        ):
            start, end = page_ranges[page_index]
            group_id = ""

            if start < end:
                image_index = max(0, min(int(start), max(0, image_count - 1)))
                for group in groups:
                    if int(group.get("start", 0)) > image_index:
                        break
                    group_id = str(group.get("id", ""))

            context = resolve_title_context(
                self._title_system,
                group_id=group_id,
                page_index=page_index,
            )
            context["subtitle"] = ""
            contexts.append(context)

        return contexts

    def _resolved_title_context_for_page(
        self,
        page_index=None,
    ):
        contexts = (
            self._resolved_title_pages()
        )

        if not contexts:
            return resolve_title_context(
                self._title_system,
                page_index=0,
            )

        if page_index is None:
            page_index = (
                self._current_title_page_index()
            )

        page_index = max(
            0,
            min(
                int(page_index),
                len(contexts) - 1,
            ),
        )
        return dict(
            contexts[
                page_index
            ]
        )

    def _update_group_ui_state(self):
        grouped = (
            normalize_pagination_mode(
                self._pagination_mode
            )
            == PAGINATION_GROUPED
        )

        checkbox = getattr(
            self,
            "new_import_group_check",
            None,
        )

        if checkbox is not None:
            checkbox.setEnabled(grouped)

        hint = getattr(self, "group_mode_hint", None)
        if hint is not None:
            hint.setText(
                self._translated(
                    "拖动图片即可跨页 / 跨组调整"
                )
            )

        auto_layout_check = getattr(
            self,
            "auto_layout_check",
            None,
        )
        if auto_layout_check is not None:
            blocked = auto_layout_check.blockSignals(True)
            auto_layout_check.setChecked(not grouped)
            auto_layout_check.blockSignals(blocked)

        confirm_button = getattr(
            self,
            "confirm_auto_layout_btn",
            None,
        )
        if confirm_button is not None:
            confirm_button.setVisible(not grouped)

        if auto_layout_check is not None:
            auto_layout_check.setToolTip(
                self._translated(
                    "取消勾选将恢复开启自动排版前的版本"
                    if not grouped
                    and getattr(
                        self,
                        "_auto_layout_restore_state",
                        None,
                    ) is not None
                    else "按当前行列连续补满页面空位"
                )
            )

    def on_auto_layout_toggled(self, checked):
        checked = bool(checked)

        if checked:
            if (
                self._current_pagination_mode()
                != PAGINATION_CONTINUOUS
                and self._auto_layout_restore_state is None
            ):
                self._auto_layout_restore_state = deepcopy(
                    self.snapshot_state()
                )
                self._auto_layout_undo_depth = len(
                    self.undo_stack
                )
            self._confirmed_auto_layout = False
        elif self._auto_layout_restore_state is not None:
            restore_state = self._auto_layout_restore_state
            self._auto_layout_restore_state = None
            if self._auto_layout_undo_depth is not None:
                del self.undo_stack[
                    int(self._auto_layout_undo_depth):
                ]
                self.redo_stack.clear()
            self._auto_layout_undo_depth = None
            self.restore_state(restore_state)
            self._show_status(
                "已恢复开启自动排版前的版本",
                3000,
            )
            return

        mode = (
            PAGINATION_CONTINUOUS
            if checked
            else PAGINATION_GROUPED
        )
        combo = getattr(self, "pagination_mode_combo", None)
        if combo is None:
            return

        index = combo.findData(mode)
        if index < 0:
            return

        if combo.currentIndex() == index:
            self._update_group_ui_state()
            return

        combo.setCurrentIndex(index)

    def confirm_auto_layout(self):
        if (
            self._current_pagination_mode()
            != PAGINATION_CONTINUOUS
        ):
            return

        self.push_history("确认自动排版")
        ranges = list(self._computed_page_ranges())
        image_count = len(self.visible_images())
        self._group_page_breaks = {
            int(end)
            for _start, end in ranges[:-1]
            if 0 < int(end) < image_count
        }
        self._confirmed_auto_layout = True
        self._auto_layout_restore_state = None
        self._auto_layout_undo_depth = None
        self._set_pagination_mode(
            PAGINATION_GROUPED,
            refresh=False,
        )
        self._normalize_group_page_breaks()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()
        self._show_status(
            "已保留此次自动排版，后续删除不会自动补位",
            3500,
        )

    def on_pagination_mode_changed(
        self,
        *_args,
    ):
        mode = normalize_pagination_mode(
            self.pagination_mode_combo.currentData()
        )

        if mode == self._pagination_mode:
            self._update_group_ui_state()
            return

        if (
            mode == PAGINATION_CONTINUOUS
            and self._locked_group_ids
        ):
            QMessageBox.information(
                self,
                "存在锁定分组",
                (
                    "当前工程存在已锁定分组。\n"
                    "请先解锁所有分组，再切换到连续排版。"
                ),
            )
            self._set_pagination_mode(
                PAGINATION_GROUPED,
                refresh=False,
            )
            self._update_lock_ui_state()
            return

        self.push_history(
            "关闭自动排版"
            if mode == PAGINATION_GROUPED
            else "开启自动排版"
        )

        self._pagination_mode = mode
        if mode == PAGINATION_CONTINUOUS:
            # Explicit blank pages conflict with a gap-free continuous flow.
            self._set_blank_page_positions([])
        self._normalize_image_groups()
        self._update_group_ui_state()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

    # =====================================================
    # UI-05-22E PreviewCanvas Page API Compatibility
    # =====================================================

    def _install_preview_page_api_compat(self):
        """
        UI-05-42B FIX02：
        新 PreviewCanvas 原生支持任意位置空白页。
        旧 PreviewCanvas 仍保留尾部计数兼容，避免开发目录中
        文件版本不一致时软件无法启动。
        """
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return

        if (
            hasattr(
                preview,
                "set_blank_page_positions",
            )
            and hasattr(
                preview,
                "blank_page_positions",
            )
        ):
            return

        if getattr(
            preview,
            "_fd_page_compat_installed",
            False,
        ):
            return

        original_page_count = (
            preview.page_count
        )

        preview._fd_page_compat_installed = True
        preview._fd_original_page_count = (
            original_page_count
        )
        preview._fd_blank_pages = 0

        def compat_page_count(
            instance,
        ):
            try:
                base_count = max(
                    1,
                    int(
                        instance._fd_original_page_count()
                    ),
                )
            except Exception:
                base_count = 1

            blank_count = max(
                0,
                int(
                    getattr(
                        instance,
                        "_fd_blank_pages",
                        0,
                    )
                ),
            )
            return (
                base_count
                + blank_count
            )

        def compat_add_empty_page(
            instance,
        ):
            instance._fd_blank_pages = (
                max(
                    0,
                    int(
                        getattr(
                            instance,
                            "_fd_blank_pages",
                            0,
                        )
                    ),
                )
                + 1
            )
            instance._page_index = (
                compat_page_count(
                    instance
                )
                - 1
            )
            instance._selected_index = -1
            instance.update()
            return True

        preview.page_count = (
            compat_page_count.__get__(
                preview,
                type(preview),
            )
        )
        preview.add_empty_page = (
            compat_add_empty_page.__get__(
                preview,
                type(preview),
            )
        )

    def _blank_page_positions(self):
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return []

        getter = getattr(
            preview,
            "blank_page_positions",
            None,
        )

        if callable(
            getter
        ):
            try:
                return sorted(
                    {
                        int(value)
                        for value in getter()
                        if int(value) >= 0
                    }
                )
            except Exception:
                return []

        # 旧兼容层只能表达尾部空白页。
        blank_count = max(
            0,
            int(
                getattr(
                    preview,
                    "_fd_blank_pages",
                    0,
                )
            ),
        )
        base_count = max(
            1,
            int(
                getattr(
                    preview,
                    "_fd_original_page_count",
                    preview.page_count,
                )()
            ),
        )

        return list(
            range(
                base_count,
                base_count
                + blank_count,
            )
        )

    def _set_blank_page_positions(
        self,
        positions,
    ):
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return

        setter = getattr(
            preview,
            "set_blank_page_positions",
            None,
        )

        if callable(
            setter
        ):
            setter(
                sorted(
                    {
                        int(value)
                        for value in list(
                            positions or []
                        )
                        if int(value) >= 0
                    }
                )
            )
            return

        # 旧兼容层退化为尾部空白页数量。
        preview._fd_blank_pages = len(
            list(
                positions
                or []
            )
        )

    def _compat_blank_page_count(self):
        return len(
            self._blank_page_positions()
        )

    def _set_compat_blank_page_count(
        self,
        count,
    ):
        """
        旧工程兼容：
        只有 blank_pages 数量、没有位置数据时，
        将这些页面恢复到图片页尾部。
        """
        count = max(
            0,
            int(count),
        )
        base_count = len(
            self._computed_page_ranges()
        )

        self._set_blank_page_positions(
            range(
                base_count,
                base_count
                + count,
            )
        )

    def _is_blank_page(
        self,
        page_index,
    ):
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return False

        checker = getattr(
            preview,
            "is_blank_page",
            None,
        )

        if callable(
            checker
        ):
            try:
                return bool(
                    checker(
                        int(
                            page_index
                        )
                    )
                )
            except Exception:
                pass

        return int(
            page_index
        ) in set(
            self._blank_page_positions()
        )

    def _base_image_page_count(self):
        """
        真实图片形成的页面数量，不包含任意位置的空白页。
        """
        return max(
            1,
            len(
                self._computed_page_ranges()
            ),
        )

    def _image_page_index_for_logical(
        self,
        logical_page_index,
    ):
        preview = getattr(
            self,
            "preview",
            None,
        )

        mapper = getattr(
            preview,
            "image_page_index_for_logical",
            None,
        )

        if callable(
            mapper
        ):
            try:
                return mapper(
                    int(
                        logical_page_index
                    )
                )
            except Exception:
                pass

        logical_page_index = int(
            logical_page_index
        )

        if self._is_blank_page(
            logical_page_index
        ):
            return None

        blank_before = sum(
            1
            for value in (
                self._blank_page_positions()
            )
            if value
            < logical_page_index
        )

        image_page_index = (
            logical_page_index
            - blank_before
        )

        if (
            0
            <= image_page_index
            < len(
                self._computed_page_ranges()
            )
        ):
            return image_page_index

        return None

    def _logical_page_index_for_image_page(
        self,
        image_page_index,
    ):
        preview = getattr(
            self,
            "preview",
            None,
        )

        mapper = getattr(
            preview,
            "logical_page_index_for_image_page",
            None,
        )

        if callable(
            mapper
        ):
            try:
                return int(
                    mapper(
                        int(
                            image_page_index
                        )
                    )
                )
            except Exception:
                pass

        logical = max(
            0,
            int(
                image_page_index
            ),
        )

        for blank_index in (
            self._blank_page_positions()
        ):
            if (
                blank_index
                <= logical
            ):
                logical += 1
            else:
                break

        return logical

    def _insert_blank_page_position(
        self,
        insert_at,
    ):
        total_before = max(
            1,
            int(
                self.preview.page_count()
            ),
        )
        insert_at = max(
            0,
            min(
                int(
                    insert_at
                ),
                total_before,
            ),
        )

        positions = []

        for value in (
            self._blank_page_positions()
        ):
            positions.append(
                value + 1
                if value >= insert_at
                else value
            )

        positions.append(
            insert_at
        )
        self._set_blank_page_positions(
            positions
        )
        return insert_at

    def _remove_blank_page_position(
        self,
        page_index,
    ):
        page_index = int(
            page_index
        )
        positions = (
            self._blank_page_positions()
        )

        if (
            page_index
            not in positions
        ):
            return False

        updated = []

        for value in positions:
            if value == page_index:
                continue

            updated.append(
                value - 1
                if value > page_index
                else value
            )

        self._set_blank_page_positions(
            updated
        )
        return True

    def _shift_page_title_metadata_for_insert(
        self,
        page_index,
    ):
        page_index = int(
            page_index
        )

        for key_name in (
            "page_titles",
            "page_styles",
        ):
            source = dict(
                self._title_system.get(
                    key_name,
                    {},
                )
                or {}
            )
            updated = {}

            for key, value in (
                source.items()
            ):
                try:
                    old_index = int(
                        key
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                new_index = (
                    old_index + 1
                    if old_index
                    >= page_index
                    else old_index
                )
                updated[
                    str(
                        new_index
                    )
                ] = value

            self._title_system[
                key_name
            ] = updated

    def _shift_page_title_metadata_for_delete(
        self,
        page_index,
    ):
        page_index = int(
            page_index
        )

        for key_name in (
            "page_titles",
            "page_styles",
        ):
            source = dict(
                self._title_system.get(
                    key_name,
                    {},
                )
                or {}
            )
            updated = {}

            for key, value in (
                source.items()
            ):
                try:
                    old_index = int(
                        key
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if old_index == page_index:
                    continue

                new_index = (
                    old_index - 1
                    if old_index
                    > page_index
                    else old_index
                )
                updated[
                    str(
                        new_index
                    )
                ] = value

            self._title_system[
                key_name
            ] = updated

    def _page_capacity(self):
        return max(
            1,
            int(self.row_step.value()) * int(self.col_step.value())
        )

    def _repair_unexpected_page_gaps(
        self,
        *,
        notify=False,
    ):
        """
        修复由历史显式分页点造成的中间空槽。

        FrameDeck 的正常排版规则是按 rows × cols 连续填充。
        只有位于自然页边界上的分页点才不会制造空白槽；
        其余分页点会让当前页提前结束，导致图片被推到下一页。

        兼容层真正的空白页由 blank_pages 单独管理，不受此处影响。
        """
        if not self._manual_page_breaks:
            return False

        capacity = self._page_capacity()
        image_count = len(
            self.visible_images()
        )

        original = {
            int(value)
            for value in self._manual_page_breaks
            if 0 < int(value) < image_count
        }

        # 自然页边界不会造成空槽；其他中间分页点自动清除。
        repaired = {
            value
            for value in original
            if value % capacity == 0
        }

        if repaired == original:
            self._manual_page_breaks = repaired
            return False

        removed = sorted(
            original - repaired
        )
        self._manual_page_breaks = repaired

        if hasattr(
            self,
            "log_box",
        ):
            self.log_box.append(
                (
                    "已自动修复异常分页空槽："
                    f"移除 {len(removed)} 个旧分页点"
                )
            )

        if (
            notify
            and hasattr(
                self,
                "status_bar",
            )
        ):
            self._show_status(
                (
                    "已自动修复中间空白框，"
                    "图片顺序已连续回填"
                ),
                3500,
            )

        return True

    def _normalize_manual_page_breaks(self, image_count=None):
        if image_count is None:
            image_count = len(self.visible_images())
        self._manual_page_breaks = {
            int(value)
            for value in self._manual_page_breaks
            if 0 < int(value) < image_count
        }

    def _computed_page_ranges(self):
        """
        UI-05-42A 页面范围统一入口。

        连续模式：所有图片连续补满。
        分组模式：各分组独立分页，组尾允许不满。
        """
        return compute_page_ranges(
            len(self.visible_images()),
            self._page_capacity(),
            self._effective_page_breaks(),
        )

    def _logical_page_ranges_snapshot(
        self,
        page_count,
        *,
        image_ranges=None,
        image_count=None,
    ):
        """Resolve all logical page ranges once, including inserted blank pages."""
        if image_ranges is None:
            image_ranges = list(self._computed_page_ranges())
        else:
            image_ranges = list(image_ranges)
        if image_count is None:
            image_count = len(self.visible_images())

        blank_positions = set(self._blank_page_positions())
        result = []
        blank_before = 0
        for logical_page in range(max(0, int(page_count))):
            if logical_page in blank_positions:
                result.append((int(image_count), int(image_count)))
                blank_before += 1
                continue
            image_page = logical_page - blank_before
            if 0 <= image_page < len(image_ranges):
                result.append(tuple(image_ranges[image_page]))
            else:
                result.append((int(image_count), int(image_count)))
        return result

    def _page_visible_range(self, page_index):
        ranges = self._computed_page_ranges()
        logical_page_index = int(
            page_index
        )
        image_page_index = (
            self._image_page_index_for_logical(
                logical_page_index
            )
        )

        if (
            image_page_index is not None
            and 0
            <= image_page_index
            < len(ranges)
        ):
            return ranges[
                image_page_index
            ]

        end = len(
            self.visible_images()
        )
        return end, end

    def _visible_index_before_list_row(self, row):
        row = max(
            0,
            min(int(row), self.image_list.count()),
        )
        visible_index = 0

        for current_row in range(row):
            item = self.image_list.item(current_row)
            path = item.data(Qt.ItemDataRole.UserRole)

            if path not in self.hidden_images:
                visible_index += 1

        return visible_index

    def _list_row_for_visible_insertion(self, visible_index):
        visible_rows = self._visible_image_rows()
        visible_index = max(
            0,
            min(int(visible_index), len(visible_rows)),
        )

        if visible_index >= len(visible_rows):
            return self.image_list.count()

        return visible_rows[visible_index]

    def _shift_page_breaks_for_insert(
        self,
        visible_index,
        count,
        *,
        keep_break_at_index=True,
    ):
        if count <= 0:
            return

        updated = set()

        for page_break in self._manual_page_breaks:
            if page_break > visible_index:
                updated.add(page_break + count)
            elif (
                page_break == visible_index
                and not keep_break_at_index
            ):
                updated.add(page_break + count)
            else:
                updated.add(page_break)

        # 插入通常发生在列表项目真正加入之前，此时不能按旧图片数量
        # 立即归一化，否则向后移动的分页点会被误删。
        self._manual_page_breaks = updated

    def _shift_page_breaks_for_delete(
        self,
        deleted_indices,
        image_count_before=None,
    ):
        deleted = sorted(
            {
                int(index)
                for index in deleted_indices
                if int(index) >= 0
            }
        )

        if not deleted:
            return

        if image_count_before is None:
            image_count_before = len(
                self.visible_images()
            )

        new_count = max(
            0,
            int(image_count_before) - len(deleted),
        )
        updated = set()

        for page_break in self._manual_page_breaks:
            shift = sum(
                1
                for index in deleted
                if index < page_break
            )
            new_break = page_break - shift

            if 0 < new_break < new_count:
                updated.add(new_break)

        self._manual_page_breaks = updated

    def _set_page_breaks_from_lengths(self, lengths):
        """
        页面顺序调整后只保留自然页边界。

        旧逻辑会把短页长度也写成显式分页点，
        当短页处于中间时便产生不可操作的空白框。
        """
        cumulative = 0
        capacity = self._page_capacity()
        breaks = set()

        for page_length in list(lengths or [])[:-1]:
            cumulative += max(
                0,
                int(page_length),
            )

            if (
                cumulative > 0
                and cumulative % capacity == 0
            ):
                breaks.add(cumulative)

        self._manual_page_breaks = breaks
        self._normalize_manual_page_breaks()

    def _visible_image_rows(self):
        """
        返回右侧列表中参与页面排版的项目行号。
        隐藏图片不计入页面。
        """
        rows = []

        for row in range(self.image_list.count()):
            item = self.image_list.item(row)
            path = item.data(Qt.ItemDataRole.UserRole)

            if path not in self.hidden_images:
                rows.append(row)

        return rows

    def _force_page_thumbnail_refresh(self):
        self._last_real_thumbnail_signature = None
        self._pending_real_thumbnail_signature = None

    def refresh_preview(self):
        if getattr(self, "_close_in_progress", False):
            return

        # UI-05-39C：
        # 先修复旧工程或页面操作遗留的非自然分页点。
        # 否则页面会提前结束，出现无法选择的空白槽，
        # 对应图片则被推到下一页。
        self._repair_unexpected_page_gaps(
            notify=True
        )

        self.images = self.visible_images()
        self.preview.set_images(self.images)

        if hasattr(
            self.preview,
            "set_blank_page_positions",
        ):
            self.preview.set_blank_page_positions(
                self._blank_page_positions()
            )

        self.preview.set_image_transforms(
            self.image_transforms
        )
        self.preview.set_settings(
            self.preview_settings()
        )

        image_count = len(self.images)
        effective_breaks = self._effective_page_breaks(image_count)

        if hasattr(self.preview, "set_page_breaks"):
            self.preview.set_page_breaks(
                effective_breaks
            )

        self._update_group_ui_state()
        self._update_lock_ui_state()

        count = max(1, int(self.preview.page_count()))
        current = max(0, min(self.preview.current_page(), count - 1))

        # UI-05-22C：
        # 记录中央画布当前实际显示页。
        # 批量渲染缩略图结束后，必须恢复到这个页面。
        self._displayed_page_index = current
        self._schedule_thumbnail_priority_refresh()

        self.preview.set_page_index(current)
        self._sync_title_editor_context()

        # Selection is only painted; it must not force the canvas back to its page.
        if self.selected_image_index < 0:
            self.selected_image_indices = set()
        elif self.selected_image_index not in self.selected_image_indices:
            self.selected_image_indices = {
                self.selected_image_index
            }

        self.selected_image_indices = {
            index
            for index in self.selected_image_indices
            if 0 <= index < len(self.images)
        }

        if hasattr(self.preview, "set_selected_indices"):
            self.preview.set_selected_indices(
                sorted(self.selected_image_indices),
                self.selected_image_index,
                reveal=False,
            )
        else:
            self.preview.set_selected_index(
                self.selected_image_index,
                reveal=False,
            )

        # =====================================================
        # UI-05-22A Page Count / Current Page Sync
        #
        # 仅同步页面数量与当前页，不抓取 Canvas，不生成真实缩略图。
        # 当页面数量没有变化时，不重建导航栏，避免闪烁和状态重置。
        # =====================================================
        if self.slide_thumbnail_bar is not None:
            try:
                nav_count = self.slide_thumbnail_bar.page_count()
            except (AttributeError, TypeError):
                nav_count = -1

            if nav_count != count:
                self.slide_thumbnail_bar.set_pages([None] * count)

                # UI-05-22F：
                # 页面卡片被重建后，旧缩略图缓存不能继续复用。
                self._page_thumbnail_signatures = {}

            self.slide_thumbnail_bar.set_current_page(current)

            # UI-05-22B：页面内容变化后，延迟生成真实页面缩略图。
            # 使用 PreviewCanvas 已有缩略图接口；没有接口时继续保留占位卡片。
            self.schedule_real_thumbnail_refresh()

        self.page_badge.setText(f"{current + 1} / {count}")
        if hasattr(self, "page_total_label"):
            self.page_total_label.setText(f"/ {count}")
        if hasattr(
            self,
            "import_count_badge",
        ):
            if self._group_mode_enabled():
                group_count = len(self._image_groups)
                self.import_count_badge.setText(
                    (
                        f"当前 {self.image_list.count()} 张"
                        f" · {group_count} 组"
                    )
                )
            else:
                self.import_count_badge.setText(
                    f"当前 {self.image_list.count()} 张"
                )

        if hasattr(self, "status_images"):
            self.status_images.setText(
                self._translated(
                    f"图片 {image_count}/{self.image_list.count()}"
                )
            )
            self.status_page.setText(
                self._translated(f"页面 {current + 1}/{count}")
            )
            self.status_project.setText(
                self._translated(
                    Path(self.current_project_file).name
                    if self.current_project_file
                    else "未保存"
                )
            )
        self._update_template_badge()
        self.header_project_badge.setText(
            self._translated(
                Path(self.current_project_file).name
                if self.current_project_file
                else "未保存工程"
            )
        )
        self.page_jump.blockSignals(True)
        self.page_jump.setRange(1, count)
        self.page_jump.setValue(current + 1)
        self.page_jump.blockSignals(False)

        self.first_btn.setEnabled(current > 0)
        self.prev_btn.setEnabled(current > 0)
        self.next_btn.setEnabled(current < count - 1)
        self.last_btn.setEnabled(current < count - 1)
        self.update_history_actions()
        self.request_config_save()

        if not self._history_lock:
            self._last_stable_history_state = (
                self.snapshot_state()
            )
            self._settings_history_pending = False

    # =====================================================
    # UI-05-22F Full-Page Thumbnail Rendering
    # =====================================================

    def _real_thumbnail_signature(self):
        """
        生成全局缩略图刷新签名。

        页面内容、精修参数、布局、主题或空白页发生变化时，
        才安排缩略图刷新。
        """
        try:
            payload = {
                "count": max(1, int(self.preview.page_count())),
                "images": list(self.images),
                "transforms": self.image_transforms,
                "settings": self.preview_settings(),
                "theme": self.current_theme_name(),
                "blank_pages": self._compat_blank_page_count(),
                "blank_page_positions": (
                    self._blank_page_positions()
                ),
                "page_breaks": self._effective_page_breaks(),
                "pagination_mode": (
                    self._current_pagination_mode()
                ),
                "image_groups": self._image_groups,
            }
            return json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return None

    def _thumbnail_signature_context(self):
        settings = dict(self.preview_settings() or {})
        resolved_pages = settings.pop("resolved_title_pages", [])
        for key in (
            "title_text",
            "subtitle_text",
            "title_height",
            "title_style",
        ):
            settings.pop(key, None)
        return {
            "settings": settings,
            "resolved_title_pages": resolved_pages,
            "theme": self.current_theme_name(),
            "page_ranges": self._logical_page_ranges_snapshot(
                max(1, int(self.preview.page_count()))
            ),
        }

    def _page_thumbnail_signature(self, page_index, context=None):
        """
        Build one page-local signature from a context shared by the refresh pass.
        """
        try:
            page_index = int(page_index)
            context = context or self._thumbnail_signature_context()
            ranges = context.get("page_ranges", [])
            if 0 <= page_index < len(ranges):
                start, end = ranges[page_index]
            else:
                start, end = self._page_visible_range(page_index)
            page_images = list(
                self.images[start:end]
            )

            page_transforms = {
                path: self.image_transforms.get(path, {})
                for path in page_images
            }

            payload = {
                "page": page_index,
                "images": page_images,
                "transforms": page_transforms,
                "settings": context.get("settings", {}),
                "title_context": (
                    context.get("resolved_title_pages", [])[page_index]
                    if 0 <= page_index < len(context.get("resolved_title_pages", []))
                    else {}
                ),
                "theme": context.get("theme", self.current_theme_name()),
                "is_blank_page": (
                    self._is_blank_page(
                        page_index
                    )
                ),
            }

            return json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return None

    def _page_thumbnail_signature_map(self, page_count):
        context = self._thumbnail_signature_context()
        return {
            page_index: self._page_thumbnail_signature(page_index, context)
            for page_index in range(max(0, int(page_count)))
        }

    def schedule_real_thumbnail_refresh(self):
        """
        合并短时间内连续发生的缩略图刷新请求。

        中央画布继续实时更新；只有顶部页面缩略图延迟约180ms，
        因此拖动、删除、复制和页面操作不会连续阻塞界面。
        """
        if getattr(self, "_thumbnail_refresh_suspended", False):
            self._real_thumbnail_refresh_pending = True
            return

        signature = self._real_thumbnail_signature()

        if (
            signature is not None
            and signature
            == getattr(
                self,
                "_last_real_thumbnail_signature",
                None,
            )
            and not self._page_thumbnail_render_queue
        ):
            return

        self._pending_real_thumbnail_signature = signature
        self._real_thumbnail_refresh_pending = True

        # 新操作会重新计时，只保留最终状态。
        self._page_thumbnail_debounce_timer.start()


    def _ensure_page_thumbnail_renderer(self):
        """
        创建独立的隐藏 PreviewCanvas。

        该画布只负责顶部导航缩略图，不接收鼠标、键盘或焦点，
        不会改变中央画布当前页、选区、缩放、裁切或抓手状态。
        """
        renderer = getattr(
            self,
            "_page_thumbnail_renderer",
            None,
        )

        if renderer is not None:
            return renderer

        renderer = PreviewCanvas(self)
        renderer.setObjectName(
            "OffscreenPageThumbnailRenderer"
        )
        renderer.setAttribute(
            Qt.WidgetAttribute.WA_DontShowOnScreen,
            True,
        )
        renderer.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        renderer.setAcceptDrops(False)
        renderer.setMouseTracking(False)
        renderer.resize(
            QSize(480, 304)
        )
        renderer.hide()

        if hasattr(
            renderer,
            "set_navigation_thumbnail_mode",
        ):
            renderer.set_navigation_thumbnail_mode(
                True,
                THUMBNAIL_WORK_WIDTH,
                THUMBNAIL_WORK_HEIGHT,
            )
        elif hasattr(
            renderer,
            "set_render_quality_override",
        ):
            renderer.set_render_quality_override(
                1280
            )

        self._page_thumbnail_renderer = (
            renderer
        )
        return renderer

    def _sync_page_thumbnail_renderer(self):
        renderer = (
            self._ensure_page_thumbnail_renderer()
        )

        renderer.set_images(
            list(self.images)
        )

        if hasattr(
            renderer,
            "set_blank_page_positions",
        ):
            renderer.set_blank_page_positions(
                self._blank_page_positions()
            )

        renderer.set_image_transforms(
            self.image_transforms
        )
        renderer.set_settings(
            self.preview_settings()
        )

        if hasattr(
            renderer,
            "set_page_breaks",
        ):
            renderer.set_page_breaks(
                self._effective_page_breaks()
            )

        renderer.set_zoom(1.0)
        renderer.set_theme(
            self.current_theme_name(),
            THEME_META.get(
                self.current_theme_name(),
                THEME_META["极光浅色"],
            ),
        )

        if hasattr(
            renderer,
            "set_selected_indices",
        ):
            renderer.set_selected_indices(
                [],
                -1,
                reveal=False,
            )
        else:
            renderer.set_selected_index(
                -1,
                reveal=False,
            )

        return renderer

    def _blank_page_thumbnail(self, page_index):
        """
        为兼容层空白页生成独立缩略图，不借用中央画布。
        """
        settings = self.preview_settings()
        page_name = settings.get(
            "page_size",
            "16:9",
        )
        slide_w, slide_h = PAGE_SIZES.get(
            page_name,
            PAGE_SIZES["16:9"],
        )
        ratio = float(slide_w) / max(
            0.0001,
            float(slide_h),
        )

        width = 300
        height = max(
            1,
            round(width / ratio),
        )

        palette = THEME_META.get(
            self.current_theme_name(),
            THEME_META["极光浅色"],
        )

        image = QImage(
            width,
            height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(
            QColor(
                palette.get(
                    "slide",
                    "#FFFFFF",
                )
            )
        )

        painter = QPainter(image)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        painter.setPen(
            QPen(
                QColor(
                    palette.get(
                        "border_strong",
                        "#C7D2E0",
                    )
                ),
                2,
            )
        )
        painter.drawRect(
            image.rect().adjusted(
                1,
                1,
                -2,
                -2,
            )
        )
        painter.setPen(
            QColor(
                palette.get(
                    "muted",
                    "#667085",
                )
            )
        )
        painter.drawText(
            image.rect(),
            Qt.AlignmentFlag.AlignCenter,
            f"空白页\n{page_index + 1:02d}",
        )
        painter.end()

        return QPixmap.fromImage(image)

    def _preview_slide_crop_rect(self, preview, pixmap):
        """
        按 PreviewCanvas 的实际页面比例计算幻灯片区域。

        返回 QPixmap.copy() 使用的像素坐标：
            x, y, width, height
        """
        try:
            settings = self.preview_settings()
            page_name = settings.get("page_size", "16:9")
            slide_w, slide_h = PAGE_SIZES.get(
                page_name,
                PAGE_SIZES["16:9"],
            )
            ratio = float(slide_w) / float(slide_h)

            widget_rect = preview.rect()
            outer = widget_rect.adjusted(
                30,
                26,
                -30,
                -26,
            )

            zoom = float(
                getattr(preview, "_zoom", 1.0)
            )
            max_w = max(1.0, outer.width() * zoom)
            max_h = max(1.0, outer.height() * zoom)

            if max_w / max_h > ratio:
                height = max_h
                width = height * ratio
            else:
                width = max_w
                height = width / ratio

            x = widget_rect.center().x() - width / 2
            y = widget_rect.center().y() - height / 2

            # QWidget.grab() 在高 DPI 环境中可能返回带 DPR 的像素图。
            dpr = max(
                1.0,
                float(pixmap.devicePixelRatio()),
            )

            px = int(round(x * dpr))
            py = int(round(y * dpr))
            pw = int(round(width * dpr))
            ph = int(round(height * dpr))

            px = max(0, min(px, pixmap.width() - 1))
            py = max(0, min(py, pixmap.height() - 1))
            pw = max(
                1,
                min(pw, pixmap.width() - px),
            )
            ph = max(
                1,
                min(ph, pixmap.height() - py),
            )

            return px, py, pw, ph

        except Exception:
            return (
                0,
                0,
                max(1, pixmap.width()),
                max(1, pixmap.height()),
            )

    def _capture_full_page_thumbnail(self, page_index):
        """
        使用独立离屏 PreviewCanvas 渲染页面缩略图。

        该过程不切换、不抓取真实中央画布，因此不会出现页面闪动。
        """
        try:
            page_index = int(page_index)

            if self._is_blank_page(
                page_index
            ):
                return self._blank_page_thumbnail(
                    page_index
                )

            renderer = (
                self._ensure_page_thumbnail_renderer()
            )
            renderer.set_page_index(
                page_index
            )

            logical_size = renderer.size()
            image = QImage(
                max(1, logical_size.width()),
                max(1, logical_size.height()),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            image.fill(
                Qt.GlobalColor.transparent
            )

            painter = QPainter(image)
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing,
                True,
            )
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform,
                True,
            )

            try:
                renderer.render(
                    painter,
                    QPoint(0, 0),
                )
            finally:
                painter.end()

            pixmap = QPixmap.fromImage(image)

            if pixmap.isNull():
                return None

            x, y, width, height = (
                self._preview_slide_crop_rect(
                    renderer,
                    pixmap,
                )
            )

            page_pixmap = pixmap.copy(
                x,
                y,
                width,
                height,
            )

            if page_pixmap.isNull():
                page_pixmap = pixmap

            return page_pixmap.scaled(
                300,
                190,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        except Exception as error:
            print(
                "[UI-05-39A offscreen thumbnail error]",
                page_index,
                error,
            )
            return None


    def refresh_real_page_thumbnails(self):
        """
        计算真正发生变化的页面并建立离屏渲染队列。

        不再一次同步渲染全部页面。
        """
        self._real_thumbnail_refresh_pending = False

        bar = getattr(
            self,
            "slide_thumbnail_bar",
            None,
        )
        preview = getattr(
            self,
            "preview",
            None,
        )

        if bar is None or preview is None:
            return

        try:
            count = max(
                1,
                int(preview.page_count()),
            )
            current = max(
                0,
                min(
                    int(
                        getattr(
                            self,
                            "_displayed_page_index",
                            preview.current_page(),
                        )
                    ),
                    count - 1,
                ),
            )
        except Exception:
            return

        try:
            if bar.page_count() != count:
                bar.set_pages(
                    [None] * count
                )
                self._page_thumbnail_signatures = {}
        except Exception:
            return

        previous_signatures = dict(
            getattr(
                self,
                "_page_thumbnail_signatures",
                {},
            )
        )
        next_signatures = self._page_thumbnail_signature_map(count)
        dirty_pages = []

        for page_index in range(count):
            page_signature = next_signatures.get(page_index)

            if (
                page_signature is None
                or previous_signatures.get(
                    page_index
                )
                != page_signature
            ):
                dirty_pages.append(
                    page_index
                )

        if not dirty_pages:
            self._page_thumbnail_signatures = (
                next_signatures
            )
            self._last_real_thumbnail_signature = (
                self._real_thumbnail_signature()
            )
            self._pending_real_thumbnail_signature = (
                None
            )
            bar.set_current_page(current)
            return

        # 当前页优先，其余按距离当前页从近到远。
        dirty_pages.sort(
            key=lambda page: (
                0 if page == current else 1,
                abs(page - current),
                page,
            )
        )

        self._page_thumbnail_render_timer.stop()
        self._page_thumbnail_refresh_generation += 1
        self._page_thumbnail_render_queue = (
            dirty_pages
        )
        self._page_thumbnail_target_signatures = (
            next_signatures
        )
        self._page_thumbnail_render_total = len(
            dirty_pages
        )
        self._page_thumbnail_rendered_count = 0

        self._sync_page_thumbnail_renderer()

        # 当前页立即更新，其他页逐帧静默更新。
        self._process_page_thumbnail_queue()

    def _process_page_thumbnail_queue(self):
        """
        每次只渲染一个页面缩略图，然后把控制权交回Qt事件循环。
        """
        bar = getattr(
            self,
            "slide_thumbnail_bar",
            None,
        )

        if bar is None:
            self._page_thumbnail_render_queue = []
            return

        if not self._page_thumbnail_render_queue:
            self._page_thumbnail_signatures = dict(
                self._page_thumbnail_target_signatures
            )
            self._last_real_thumbnail_signature = (
                self._real_thumbnail_signature()
            )
            self._pending_real_thumbnail_signature = (
                None
            )

            current = max(
                0,
                min(
                    int(
                        getattr(
                            self,
                            "_displayed_page_index",
                            0,
                        )
                    ),
                    max(
                        0,
                        bar.page_count() - 1,
                    ),
                ),
            )
            bar.set_current_page(current)

            if (
                self._page_thumbnail_render_total
                >= 4
                and hasattr(
                    self,
                    "status_bar",
                )
            ):
                self._show_status(
                    (
                        "页面缩略图已静默更新："
                        f"{self._page_thumbnail_render_total} 页"
                    ),
                    1600,
                )

            return

        page_index = (
            self._page_thumbnail_render_queue.pop(
                0
            )
        )
        thumbnail = (
            self._capture_full_page_thumbnail(
                page_index
            )
        )

        if thumbnail is not None:
            bar.update_page_thumbnail(
                page_index,
                thumbnail,
            )

        self._page_thumbnail_signatures[
            page_index
        ] = (
            self._page_thumbnail_target_signatures.get(
                page_index
            )
        )
        self._page_thumbnail_rendered_count += 1

        # 约16ms后继续下一页，中央画布和鼠标保持响应。
        self._page_thumbnail_render_timer.start(
            8
        )


    def swap_images(self, source_index, target_index):
        """
        中央画布内部移动图片。

        UI-05-24A 修复：
        当拖动当前页最后一张图片向前移动时，QListWidget 在 take/insert
        过程中会发出 currentRowChanged，旧逻辑会调用 reveal=True，
        从而把中央画布跳到下一页。

        新逻辑在移动期间屏蔽列表与模型信号，并明确锁定原当前页。
        """
        visible = self.visible_images()

        if not (
            0 <= source_index < len(visible)
            and 0 <= target_index < len(visible)
        ):
            return

        if source_index == target_index:
            return

        current_page = max(
            0,
            int(self.preview.current_page()),
        )

        source_path = visible[source_index]
        target_path = visible[target_index]
        all_paths = self.ordered_images()

        try:
            source_all = all_paths.index(source_path)
            target_all = all_paths.index(target_path)
        except ValueError:
            return

        self.push_history("移动图片")

        list_was_blocked = self.image_list.blockSignals(True)
        model = self.image_list.model()
        model_was_blocked = model.blockSignals(True)

        try:
            source_item = self.image_list.takeItem(source_all)
            if source_item is None:
                return

            self.image_list.insertItem(
                target_all,
                source_item,
            )

            # 移动完成后，在信号屏蔽状态下选中被移动的项目。
            new_row = self.image_list.row(source_item)
            self.image_list.setCurrentRow(new_row)

        finally:
            model.blockSignals(model_was_blocked)
            self.image_list.blockSignals(list_was_blocked)

        # 根据移动后的真实可见顺序确定选择索引。
        new_visible = self.visible_images()

        try:
            new_selected_index = new_visible.index(source_path)
        except ValueError:
            new_selected_index = -1

        self.selected_image_index = new_selected_index
        self.selected_image_indices = (
            {new_selected_index}
            if new_selected_index >= 0
            else set()
        )

        # 强制保留拖动前的当前页，不允许选择信号把页面带到下一页。
        page_count = max(
            1,
            int(self.preview.page_count()),
        )
        current_page = max(
            0,
            min(current_page, page_count - 1),
        )
        self._displayed_page_index = current_page
        self.preview.set_page_index(current_page)
        self.preview.set_selected_index(
            self.selected_image_index,
            reveal=False,
        )

        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        # refresh_preview 之后再次锁定，防止延迟信号改变页码。
        self._displayed_page_index = current_page
        self.preview.set_page_index(current_page)

        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(current_page)

        if hasattr(self, "status_bar"):
            self._show_status(
                "图片位置已调整",
                2000,
            )


    def _full_row_for_visible_index(self, visible_index):
        visible = self.visible_images()

        if not (0 <= visible_index < len(visible)):
            return -1

        path = visible[visible_index]

        for row in range(self.image_list.count()):
            item = self.image_list.item(row)

            if (
                item.data(Qt.ItemDataRole.UserRole)
                == path
            ):
                return row

        return -1

    def _update_multi_selection_ui(self):
        count = len(self.selected_image_indices)
        visible = self.visible_images()

        if count <= 0:
            self.selected_image_index = -1
            self.selected_name_label.setText("未选择图片")
            self.transform_status_badge.setText("默认参数")
            self.set_transform_controls_enabled(False)
            return

        if (
            self.selected_image_index
            not in self.selected_image_indices
        ):
            self.selected_image_index = min(
                self.selected_image_indices
            )

        if count == 1:
            index = self.selected_image_index

            if not (0 <= index < len(visible)):
                self.selected_image_indices = set()
                self._update_multi_selection_ui()
                return

            path = visible[index]
            transform = self.get_transform(path)

            self.selected_name_label.setText("已选择图片")
            self.set_transform_controls_enabled(True)
            self.update_transform_controls(transform)
            return

        self.selected_name_label.setText(
            f"已选择 {count} 张图片"
        )
        self.transform_status_badge.setText("多选状态")

        self.set_transform_controls_enabled(False)

    def _apply_image_selection(
        self,
        indices,
        primary_index=-1,
        *,
        reveal=False,
        sync_list=True,
        sync_canvas=True,
    ):
        if self._selection_sync_lock:
            return

        visible = self.visible_images()
        valid = {
            int(index)
            for index in list(indices or [])
            if 0 <= int(index) < len(visible)
        }

        if primary_index not in valid:
            primary_index = min(valid) if valid else -1

        self._selection_sync_lock = True

        try:
            self.selected_image_indices = valid
            self.selected_image_index = int(primary_index)

            if sync_list:
                self.image_list.blockSignals(True)

                try:
                    self.image_list.clearSelection()

                    primary_row = (
                        self._full_row_for_visible_index(
                            self.selected_image_index
                        )
                    )

                    if primary_row >= 0:
                        self.image_list.setCurrentRow(
                            primary_row
                        )

                    for index in sorted(valid):
                        row = self._full_row_for_visible_index(
                            index
                        )

                        if row >= 0:
                            self.image_list.item(
                                row
                            ).setSelected(True)

                finally:
                    self.image_list.blockSignals(False)

            if sync_canvas:
                if hasattr(
                    self.preview,
                    "set_selected_indices",
                ):
                    self.preview.set_selected_indices(
                        sorted(valid),
                        self.selected_image_index,
                        reveal=reveal,
                    )
                else:
                    self.preview.set_selected_index(
                        self.selected_image_index,
                        reveal=reveal,
                    )

            self._update_multi_selection_ui()

        finally:
            self._selection_sync_lock = False

        self.refresh_preview()

    def select_images_from_canvas(
        self,
        indices,
        primary_index,
    ):
        self._apply_image_selection(
            indices,
            primary_index,
            reveal=False,
            sync_list=True,
            sync_canvas=False,
        )

    def sync_selection_from_image_list(self):
        if self._selection_sync_lock:
            return

        visible = self.visible_images()
        indices = set()

        for item in self.image_list.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)

            if path in self.hidden_images:
                continue

            try:
                indices.add(visible.index(path))
            except ValueError:
                pass

        primary = -1
        current_item = self.image_list.currentItem()

        if current_item is not None:
            current_path = current_item.data(
                Qt.ItemDataRole.UserRole
            )

            try:
                current_index = visible.index(
                    current_path
                )

                if current_index in indices:
                    primary = current_index
            except ValueError:
                pass

        self._apply_image_selection(
            indices,
            primary,
            reveal=True,
            sync_list=False,
            sync_canvas=True,
        )

    def select_image(self, index):
        if not (0 <= index < len(self.visible_images())):
            self._apply_image_selection(
                [],
                -1,
                reveal=False,
            )
            return

        self._apply_image_selection(
            [index],
            index,
            reveal=True,
        )

    def select_image_from_list(self, index):
        if 0 <= index < self.image_list.count():
            self.image_list.setCurrentRow(index)
            self.sync_selection_from_image_list()

    def select_all_visible_images(self):
        visible = self.visible_images()

        if not visible:
            return

        self._apply_image_selection(
            range(len(visible)),
            self.selected_image_index
            if 0 <= self.selected_image_index < len(visible)
            else 0,
            reveal=False,
        )


    def set_transform_controls_enabled(self, enabled):
        enabled = bool(enabled)
        for widget in [
            self.image_zoom_slider, self.image_zoom_input,
            self.offset_x_slider, self.offset_x_input,
            self.offset_y_slider, self.offset_y_input,
            self.rotate_left_btn, self.rotate_right_btn,
            self.flip_h_btn, self.flip_v_btn,
            self.reset_transform_btn,
        ]:
            widget.setEnabled(enabled)

        # Explicitly keep numeric inputs editable when an image is selected.
        self.image_zoom_input.setReadOnly(not enabled)
        self.offset_x_input.setReadOnly(not enabled)
        self.offset_y_input.setReadOnly(not enabled)

    def get_transform(self, path):
        result = default_transform()
        existing = dict(
            self.image_transforms.get(path, {})
        )
        result.update(existing)
        result["crop"] = normalize_crop(
            existing.get("crop")
        )
        return result

    def update_transform_status(self, transform):
        modified = (
            abs(float(transform.get("zoom", 1.0)) - 1.0) > 0.001
            or abs(float(transform.get("offset_x", 0.0))) > 0.001
            or abs(float(transform.get("offset_y", 0.0))) > 0.001
            or int(transform.get("rotation", 0)) % 360 != 0
            or bool(transform.get("flip_h", False))
            or bool(transform.get("flip_v", False))
        )
        self.transform_status_badge.setText(
            "" if modified else "默认参数"
        )

    def _selected_pan_limits(
        self,
        *,
        zoom_override=None,
    ):
        index = int(
            self.selected_image_index
        )

        if (
            index >= 0
            and hasattr(
                self.preview,
                "pan_limits_for_index",
            )
        ):
            try:
                return (
                    self.preview.pan_limits_for_index(
                        index,
                        zoom_override=zoom_override,
                    )
                )
            except Exception:
                pass

        return 50.0, 50.0

    @staticmethod
    def _range_percent(
        normalized_limit,
    ):
        return max(
            100,
            min(
                5000,
                int(
                    math.ceil(
                        float(normalized_limit)
                        * 10.0
                    )
                    * 10
                ),
            ),
        )

    def _update_offset_control_ranges(
        self,
        *,
        zoom_override=None,
    ):
        limit_x, limit_y = (
            self._selected_pan_limits(
                zoom_override=zoom_override
            )
        )
        x_percent = self._range_percent(
            limit_x
        )
        y_percent = self._range_percent(
            limit_y
        )

        self.offset_x_slider.blockSignals(
            True
        )
        self.offset_y_slider.blockSignals(
            True
        )
        self.offset_x_slider.setRange(
            -x_percent,
            x_percent,
        )
        self.offset_y_slider.setRange(
            -y_percent,
            y_percent,
        )
        self.offset_x_slider.blockSignals(
            False
        )
        self.offset_y_slider.blockSignals(
            False
        )

        self.offset_x_slider.setToolTip(
            (
                "当前水平范围："
                f"-{x_percent}%～{x_percent}%"
            )
        )
        self.offset_y_slider.setToolTip(
            (
                "当前垂直范围："
                f"-{y_percent}%～{y_percent}%"
            )
        )

        return limit_x, limit_y

    def update_transform_controls(self, transform):
        self._update_offset_control_ranges(
            zoom_override=float(
                transform.get("zoom", 1.0)
            )
        )

        zoom_value = float(transform["zoom"])
        x_value = round(float(transform["offset_x"]) * 100)
        y_value = round(float(transform["offset_y"]) * 100)

        controls = [
            (self.image_zoom_slider, round(zoom_value * 100)),
            (self.image_zoom_input, zoom_value),
            (self.offset_x_slider, x_value),
            (self.offset_x_input, x_value),
            (self.offset_y_slider, y_value),
            (self.offset_y_input, y_value),
        ]
        for widget, value in controls:
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.update_transform_status(transform)

    def slider_zoom_changed(self, value):
        if self.selected_image_index < 0:
            return
        self.set_image_zoom(self.selected_image_index, float(value) / 100.0)

    def zoom_input_changed(self, value):
        if self.selected_image_index < 0:
            return
        self.set_image_zoom(self.selected_image_index, float(value))

    def offset_x_input_changed(self, value):
        if self.selected_image_index < 0:
            return
        self.set_selected_transform_value(
            "offset_x", float(value) / 100.0, "水平移动图片"
        )

    def offset_y_input_changed(self, value):
        if self.selected_image_index < 0:
            return
        self.set_selected_transform_value(
            "offset_y", float(value) / 100.0, "垂直移动图片"
        )

    def set_image_zoom(self, index, zoom):
        visible = self.visible_images()
        if not (0 <= index < len(visible)):
            return

        path = visible[index]
        transform = self.get_transform(path)
        zoom = max(
            0.10,
            min(
                10.00,
                round(float(zoom), 2),
            ),
        )

        if abs(float(transform["zoom"]) - zoom) < 0.001:
            self.update_transform_controls(transform)
            return

        if not self._history_lock:
            self.push_history("调整图片缩放")

        transform["zoom"] = zoom

        # UI-05-37C：
        # 恢复到原始 1.00× 时同时回到水平/垂直中心。
        # 避免保留高倍放大阶段的旧位移，导致恢复尺寸后图片偏在一侧。
        restored_to_original = (
            abs(zoom - 1.0) < 0.001
        )

        if restored_to_original:
            transform["offset_x"] = 0.0
            transform["offset_y"] = 0.0

        self.image_transforms[path] = transform
        self.selected_image_index = index

        # 先传递新缩放，再根据实际图像溢出重新计算可移动边界。
        self.preview.set_image_transforms(
            self.image_transforms
        )
        limit_x, limit_y = (
            self._selected_pan_limits(
                zoom_override=zoom
            )
        )
        transform["offset_x"] = max(
            -limit_x,
            min(
                limit_x,
                float(
                    transform.get(
                        "offset_x",
                        0.0,
                    )
                ),
            ),
        )
        transform["offset_y"] = max(
            -limit_y,
            min(
                limit_y,
                float(
                    transform.get(
                        "offset_y",
                        0.0,
                    )
                ),
            ),
        )
        self.image_transforms[path] = transform

        self.update_transform_controls(transform)
        self.preview.set_image_transforms(
            self.image_transforms
        )
        self.preview.set_selected_index(
            index,
            reveal=False,
        )
        self.preview.update()
        self.save_config()

        if (
            restored_to_original
            and hasattr(
                self,
                "status_bar",
            )
        ):
            self._show_status(
                "图片已恢复 1.00× 并自动居中",
                2200,
            )

    def on_canvas_pan_started(self, index):
        visible = self.visible_images()

        if not (0 <= index < len(visible)):
            return

        if not self._history_lock:
            self.push_history("拖动图片可见区域")

        self._canvas_pan_history_active = True
        self.selected_image_index = index

    def on_canvas_pan_changed(
        self,
        index,
        offset_x,
        offset_y,
    ):
        visible = self.visible_images()

        if not (0 <= index < len(visible)):
            return

        path = visible[index]
        transform = self.get_transform(path)
        self.selected_image_index = index

        limit_x, limit_y = (
            self._selected_pan_limits(
                zoom_override=float(
                    transform.get(
                        "zoom",
                        1.0,
                    )
                )
            )
        )
        transform["offset_x"] = max(
            -limit_x,
            min(
                limit_x,
                round(float(offset_x), 4),
            ),
        )
        transform["offset_y"] = max(
            -limit_y,
            min(
                limit_y,
                round(float(offset_y), 4),
            ),
        )

        self.image_transforms[path] = transform
        self.selected_image_index = index
        self.selected_image_indices = {index}

        self.update_transform_controls(transform)
        self.preview.set_image_transforms(
            self.image_transforms
        )
        self.preview.set_selected_index(
            index,
            reveal=False,
        )
        self.preview.update()

    def on_canvas_pan_finished(
        self,
        index,
        offset_x,
        offset_y,
    ):
        self.on_canvas_pan_changed(
            index,
            offset_x,
            offset_y,
        )
        self._canvas_pan_history_active = False
        self.save_config()

        if hasattr(self, "status_bar"):
            self._show_status(
                "图片可见区域已调整",
                1800,
            )

    def offset_x_changed(self, value):
        self.set_selected_transform_value("offset_x", value / 100.0, "水平移动图片")

    def offset_y_changed(self, value):
        self.set_selected_transform_value("offset_y", value / 100.0, "垂直移动图片")

    def set_selected_transform_value(self, key, value, label):
        visible = self.visible_images()
        if not (0 <= self.selected_image_index < len(visible)):
            return

        path = visible[self.selected_image_index]
        transform = self.get_transform(path)

        limit_x, limit_y = (
            self._selected_pan_limits(
                zoom_override=float(
                    transform.get(
                        "zoom",
                        1.0,
                    )
                )
            )
        )
        limit = (
            limit_x
            if key == "offset_x"
            else limit_y
        )
        value = max(
            -limit,
            min(
                limit,
                round(float(value), 2),
            ),
        )

        if abs(float(transform.get(key, 0.0)) - value) < 0.001:
            self.update_transform_controls(transform)
            return

        if not self._history_lock:
            self.push_history(label)

        transform[key] = value
        self.image_transforms[path] = transform
        self.update_transform_controls(transform)
        self.preview.set_image_transforms(self.image_transforms)
        self.preview.set_selected_index(self.selected_image_index, reveal=False)
        self.preview.update()
        self.save_config()

    def rotate_selected(self, degrees):
        visible = self.visible_images()
        if not (0 <= self.selected_image_index < len(visible)):
            return
        self.push_history("旋转图片")
        path = visible[self.selected_image_index]
        transform = self.get_transform(path)
        transform["rotation"] = (int(transform["rotation"]) + degrees) % 360
        self.image_transforms[path] = transform
        self.preview.set_image_transforms(self.image_transforms)
        self.preview.update()
        self.save_config()

    def flip_selected(self, axis):
        visible = self.visible_images()
        if not (0 <= self.selected_image_index < len(visible)):
            return
        self.push_history("镜像图片")
        path = visible[self.selected_image_index]
        transform = self.get_transform(path)
        key = "flip_h" if axis == "h" else "flip_v"
        transform[key] = not bool(transform[key])
        self.image_transforms[path] = transform
        self.preview.set_image_transforms(self.image_transforms)
        self.preview.update()
        self.save_config()

    # =====================================================
    # UI-05-30 Stage 02 - Crop bridge
    # =====================================================

    def start_crop_selected(self):
        visible = self.visible_images()

        if len(self.selected_image_indices) != 1:
            QMessageBox.information(
                self,
                "无法进入裁切",
                "请先只选择一张图片。",
            )
            return

        if not (
            0 <= self.selected_image_index < len(visible)
        ):
            QMessageBox.information(
                self,
                "未选择图片",
                "请先选择需要裁切的图片。",
            )
            return

        if not self.preview.begin_crop_mode(
            self.selected_image_index
        ):
            QMessageBox.warning(
                self,
                "无法进入裁切",
                "当前图片无法读取或暂时不能裁切。",
            )
            return

        self.preview.setFocus(
            Qt.FocusReason.ShortcutFocusReason
        )

        if hasattr(self, "status_bar"):
            self._show_status(
                "裁切模式：拖动边框、控制点或框内区域；右上角 ✓ 确认，× 取消；Enter / Esc 仍可使用",
                6500,
            )

    def confirm_canvas_crop(self):
        if (
            hasattr(self.preview, "is_crop_mode")
            and self.preview.is_crop_mode()
        ):
            self.preview.confirm_crop_mode()

    def reset_selected_crop(self):
        if (
            hasattr(self.preview, "is_crop_mode")
            and self.preview.is_crop_mode()
        ):
            self.preview.reset_crop_in_editor()
            return

        visible = self.visible_images()

        if not (
            0 <= self.selected_image_index < len(visible)
        ):
            QMessageBox.information(
                self,
                "未选择图片",
                "请先选择需要重置裁切的图片。",
            )
            return

        path = visible[self.selected_image_index]
        transform = self.get_transform(path)
        current_crop = normalize_crop(
            transform.get("crop")
        )

        if current_crop == default_crop():
            if hasattr(self, "status_bar"):
                self._show_status(
                    "当前图片没有裁切",
                    1800,
                )
            return

        self.push_history("重置图片裁切")
        transform["crop"] = default_crop()
        self.image_transforms[path] = transform

        self.preview.set_image_transforms(
            self.image_transforms
        )
        self._force_page_thumbnail_refresh()
        self.refresh_preview()
        self.save_config()

        if hasattr(self, "status_bar"):
            self._show_status(
                "图片裁切已重置",
                2200,
            )

    def on_canvas_crop_started(self, index):
        visible = self.visible_images()
        index = int(index)

        if not (0 <= index < len(visible)):
            return

        self._crop_history_state = self.snapshot_state()
        self._crop_history_path = visible[index]

    def on_canvas_crop_changed(self, index, crop):
        visible = self.visible_images()
        index = int(index)

        if not (0 <= index < len(visible)):
            return

        path = visible[index]
        transform = self.get_transform(path)
        transform["crop"] = normalize_crop(crop)
        self.image_transforms[path] = transform

        self.preview.set_image_transforms(
            self.image_transforms
        )
        self.preview.update()

    def on_canvas_crop_finished(self, index, accepted):
        accepted = bool(accepted)
        path = self._crop_history_path
        history_state = self._crop_history_state

        if accepted and history_state is not None and path:
            previous_crop = normalize_crop(
                history_state.get(
                    "transforms",
                    {},
                ).get(
                    path,
                    {},
                ).get("crop")
            )
            current_crop = normalize_crop(
                self.image_transforms.get(
                    path,
                    {},
                ).get("crop")
            )

            if previous_crop != current_crop:
                self.undo_stack.append(
                    ("裁切图片", history_state)
                )

                if len(self.undo_stack) > 60:
                    self.undo_stack.pop(0)

                self.redo_stack.clear()
                self.update_history_actions()

        self._crop_history_state = None
        self._crop_history_path = None

        self._force_page_thumbnail_refresh()
        self.refresh_preview()
        self.save_config()

        if hasattr(self, "status_bar"):
            self._show_status(
                "图片裁切已确认"
                if accepted
                else "已取消图片裁切",
                2500,
            )

    def reset_selected_transform(self):
        visible = self.visible_images()
        if not (0 <= self.selected_image_index < len(visible)):
            QMessageBox.information(
                self, "未选择图片", "请先在预览或图片列表中选择一张图片。"
            )
            return

        path = visible[self.selected_image_index]
        current = self.get_transform(path)
        reset_transform = default_transform()

        if current == reset_transform:
            self.transform_status_badge.setText("已经是默认参数")
            return

        self.push_history("重置当前图片精修")
        self.image_transforms[path] = dict(reset_transform)

        self.update_transform_controls(reset_transform)
        self.update_transform_status(reset_transform)
        self.preview.set_image_transforms(self.image_transforms)
        self.preview.set_selected_index(self.selected_image_index, reveal=False)
        self.preview.update()
        self.save_config()

    def _selected_image_rows(self):
        rows = sorted(
            {
                self.image_list.row(item)
                for item in self.image_list.selectedItems()
                if self.image_list.row(item) >= 0
            }
        )

        if rows:
            return rows

        row = self._full_row_for_visible_index(
            self.selected_image_index
        )
        return [row] if row >= 0 else []

    def _copied_asset_directory(self):
        if self.current_project_file:
            project_path = Path(
                self.current_project_file
            )
            directory = (
                project_path.parent
                / f"{project_path.stem}_assets"
                / "copies"
            )
        else:
            directory = (
                Path.home()
                / "FrameDeck Studio Assets"
                / "Copied Images"
            )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        return directory

    def _unique_copy_path(self, source_path):
        source = Path(source_path)
        directory = self._copied_asset_directory()

        candidate = directory / (
            f"{source.stem}_副本{source.suffix}"
        )
        number = 2

        while candidate.exists():
            candidate = directory / (
                f"{source.stem}_副本_{number}"
                f"{source.suffix}"
            )
            number += 1

        return candidate

    def duplicate_selected_images(self):
        """
        复制画布或右侧列表中选中的一张或多张图片。
        复制件插入到最后一个选中项目之后。
        """
        rows = self._selected_image_rows()

        if not rows:
            if hasattr(self, "status_bar"):
                self._show_status(
                    "请先选择要复制的图片",
                    2500,
                )
            return

        source_entries = []

        for row in rows:
            item = self.image_list.item(row)

            if item is None:
                continue

            path = item.data(Qt.ItemDataRole.UserRole)

            if path and Path(str(path)).is_file():
                source_entries.append(
                    (row, str(path))
                )

        if not source_entries:
            return

        created = []
        errors = []

        for _row, source_path in source_entries:
            try:
                destination = self._unique_copy_path(
                    source_path
                )
                shutil.copy2(
                    source_path,
                    destination,
                )
                created.append(
                    (source_path, str(destination))
                )
            except Exception as error:
                errors.append(
                    f"{Path(source_path).name}: {error}"
                )

        if not created:
            QMessageBox.warning(
                self,
                "复制失败",
                "\n".join(errors[:5])
                if errors
                else "未能创建图片副本。",
            )
            return

        self.push_history(
            "复制图片"
            if len(created) == 1
            else f"复制 {len(created)} 张图片"
        )

        insert_row = max(rows) + 1
        visible_insert_index = (
            self._visible_index_before_list_row(
                insert_row
            )
        )
        self._shift_page_breaks_for_insert(
            visible_insert_index,
            len(created),
            keep_break_at_index=True,
        )
        self._shift_image_groups_for_insert(
            visible_insert_index,
            len(created),
            boundary_belongs_to_previous=True,
            image_count_before=len(
                self.visible_images()
            ),
        )
        self._shift_page_lock_records_for_insert(
            visible_insert_index,
            len(created),
            boundary_belongs_to_previous=True,
        )
        new_rows = []

        self.image_list.blockSignals(True)

        try:
            for offset, (
                source_path,
                copied_path,
            ) in enumerate(created):
                item = self._create_external_image_item(
                    copied_path
                )
                row = insert_row + offset
                self.image_list.insertItem(row, item)
                new_rows.append(row)

                self.image_transforms[copied_path] = dict(
                    self.get_transform(source_path)
                )

            self.image_list.clearSelection()

            if new_rows:
                self.image_list.setCurrentRow(
                    new_rows[0]
                )

                for row in new_rows:
                    item = self.image_list.item(row)

                    if item is not None:
                        item.setSelected(True)

        finally:
            self.image_list.blockSignals(False)

        self.refresh_image_list_appearance()
        self.sync_selection_from_image_list()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已复制 {len(created)} 张图片",
                3000,
            )

        if errors:
            QMessageBox.warning(
                self,
                "部分图片复制失败",
                "\n".join(errors[:5]),
            )

    def delete_selected_image(self):
        """删除所选的一张或多张图片。"""
        rows = self._selected_image_rows()

        if not rows:
            return

        paths = []

        for row in rows:
            item = self.image_list.item(row)

            if item is not None:
                path = item.data(
                    Qt.ItemDataRole.UserRole
                )

                if path:
                    paths.append(path)

        if not paths:
            return

        visible_before = self.visible_images()
        deleted_visible_indices = sorted(
            {
                visible_before.index(path)
                for path in paths
                if path in visible_before
            }
        )

        history_label = getattr(self, "_delete_history_label_override", "")
        self._delete_history_label_override = ""
        self.push_history(
            history_label
            or (
                "删除图片"
                if len(paths) == 1
                else f"删除 {len(paths)} 张图片"
            )
        )

        # UI-05-45A：删除前自动记住当前页面边界；无需用户先锁页。
        # 删除后边界随索引移动，因此下一页图片不会向前补位。
        self._materialize_group_page_boundaries()

        for path in paths:
            self.image_transforms.pop(path, None)
            self.hidden_images.discard(path)

        self._shift_page_breaks_for_delete(
            deleted_visible_indices,
            image_count_before=len(visible_before),
        )
        self._shift_image_groups_for_delete(
            deleted_visible_indices,
            image_count_before=len(
                visible_before
            ),
        )
        self._shift_group_page_breaks_for_delete(
            deleted_visible_indices,
            image_count_before=len(
                visible_before
            ),
        )
        self._shift_blank_fill_page_breaks_for_delete(
            deleted_visible_indices,
            image_count_before=len(
                visible_before
            ),
        )
        self._shift_page_lock_records_for_delete(
            deleted_visible_indices,
            image_count_before=len(
                visible_before
            ),
        )

        self.image_list.blockSignals(True)

        try:
            for row in sorted(rows, reverse=True):
                self.image_list.takeItem(row)

            self.image_list.clearSelection()
            self.image_list.setCurrentRow(-1)

        finally:
            self.image_list.blockSignals(False)

        self.selected_image_index = -1
        self.selected_image_indices = set()
        self.selected_name_label.setText("未选择图片")
        self.refresh_image_list_appearance()
        self.set_transform_controls_enabled(False)
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已删除 {len(paths)} 张图片",
                2500,
            )


    def toggle_selected_hidden(self):
        visible = self.visible_images()
        if not (0 <= self.selected_image_index < len(visible)):
            return
        self.push_history("隐藏图片")
        path = visible[self.selected_image_index]
        self.hidden_images.add(path)
        self.selected_image_index = -1
        self.refresh_image_list_appearance()
        self.refresh_preview()

    def restore_all_hidden(self):
        if not self.hidden_images:
            QMessageBox.information(
                self, "没有隐藏图片", "当前没有被隐藏的图片。"
            )
            return
        self.push_history("恢复隐藏图片")
        self.hidden_images.clear()
        self.refresh_image_list_appearance()
        self.refresh_preview()

    # =====================================================
    # UI-05-45B - 右侧真实缩略图尺寸
    # =====================================================
    def _image_list_metrics(self, size=None):
        # 小 / 中 / 大不仅改变行高，也改变 QIcon 内实际图片像素尺寸。
        if size is None:
            size = getattr(
                self,
                "_thumbnail_size_value",
                96,
            )
            slider = getattr(
                self,
                "thumbnail_size_slider",
                None,
            )
            if slider is not None:
                try:
                    size = slider.value()
                except RuntimeError:
                    pass

        width = max(
            56,
            min(160, int(size)),
        )
        icon_height = max(
            38,
            int(round(width * 0.68)),
        )
        item_height = max(
            54,
            icon_height + 12,
        )

        return (
            width,
            icon_height,
            item_height,
        )

    def _apply_image_list_item_metrics(self):
        # 从 360x240 工作缓存重新生成每个 QIcon，
        # 避免“大/中图”只是把列表项目撑高。
        (
            width,
            icon_height,
            item_height,
        ) = self._image_list_metrics()

        self.image_list.setIconSize(
            QSize(
                width,
                icon_height,
            )
        )
        self.image_list.setSpacing(
            0 if width <= 150 else 1
        )

        for index in range(
            self.image_list.count()
        ):
            item = self.image_list.item(
                index
            )
            if item is None:
                continue

            item.setSizeHint(
                QSize(
                    0,
                    item_height,
                )
            )

            path = str(
                item.data(
                    Qt.ItemDataRole.UserRole
                )
                or ""
            )
            source_pixmap = QPixmap()

            if path:
                try:
                    source_pixmap = (
                        self._image_cache.cached_thumbnail_pixmap(
                            path,
                            THUMBNAIL_WORK_WIDTH,
                            THUMBNAIL_WORK_HEIGHT,
                        )
                    )
                except Exception:
                    source_pixmap = QPixmap()

            # 后台缓存尚未完成时暂用现有图标；
            # 后台任务完成后仍会按当前 iconSize 自动刷新。
            if source_pixmap.isNull():
                try:
                    source_pixmap = (
                        item.icon().pixmap(
                            THUMBNAIL_WORK_WIDTH,
                            THUMBNAIL_WORK_HEIGHT,
                        )
                    )
                except Exception:
                    source_pixmap = QPixmap()

            if not source_pixmap.isNull():
                item.setIcon(
                    QIcon(
                        source_pixmap.scaled(
                            width,
                            icon_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                )

        self.image_list.doItemsLayout()
        self.image_list.viewport().update()

    def update_thumbnail_size(self, value):
        self._thumbnail_size_value = max(
            56,
            min(160, int(value)),
        )
        self._apply_image_list_item_metrics()

    def _set_thumbnail_size_preset(self, value):
        value = max(
            56,
            min(160, int(value)),
        )
        self._thumbnail_size_value = value
        slider = getattr(
            self,
            "thumbnail_size_slider",
            None,
        )

        if slider is not None:
            try:
                if slider.value() != value:
                    slider.setValue(value)
                    return
            except RuntimeError:
                pass

        self.update_thumbnail_size(
            value
        )

    def filter_image_list(self, text=None):
        """
        按真实文件名实时筛选右侧图片列表。

        搜索只影响显示，不改变图片顺序、分页、隐藏状态或导出内容。
        """
        if text is None:
            text = self.image_search.text()

        query = str(text or "").strip().casefold()
        match_count = 0

        for index in range(self.image_list.count()):
            item = self.image_list.item(index)
            path = item.data(Qt.ItemDataRole.UserRole)

            if not path:
                item.setHidden(bool(query))
                continue

            path_obj = Path(str(path))
            searchable = " ".join(
                [
                    path_obj.name,
                    path_obj.stem,
                    str(path_obj),
                ]
            ).casefold()

            matched = not query or query in searchable
            item.setHidden(not matched)

            if matched:
                match_count += 1

        if hasattr(self, "image_search"):
            if query:
                self.image_search.setToolTip(
                    f"找到 {match_count} 张图片（Ctrl+F）；点击右侧 × 清除搜索"
                )
            else:
                self.image_search.setToolTip(
                    "输入文件名关键词实时筛选（Ctrl+F）；点击右侧 × 清除搜索"
                )

    def refresh_image_list_appearance(self):
        """
        刷新文件名、隐藏标记、项目高度，并保留当前搜索条件。

        UI-05-43D：
        Tooltip 同时显示所属分组，方便跨组拖拽时确认目标。
        """
        visible_index = 0
        image_count = len(
            self.visible_images()
        )
        groups = (
            self._normalize_image_groups()
            if image_count > 0
            else []
        )

        for index in range(self.image_list.count()):
            item = self.image_list.item(index)
            path = item.data(Qt.ItemDataRole.UserRole)

            if not path:
                continue

            name = Path(str(path)).name
            item.setText(
                f"⦸ {name}"
                if path in self.hidden_images
                else name
            )

            if path in self.hidden_images:
                item.setToolTip(
                    (
                        "已隐藏素材\n"
                        f"{path}"
                    )
                )
                continue

            group = group_for_index(
                groups,
                visible_index,
                image_count,
            )
            group_name = (
                str(
                    group.get(
                        "name",
                        "",
                    )
                )
                if group
                else ""
            )

            item.setToolTip(
                (
                    (
                        f"分组：{group_name}\n"
                        if group_name
                        else ""
                    )
                    + f"图片位置：{visible_index + 1}\n"
                    + str(path)
                )
            )
            visible_index += 1

        self._apply_image_list_item_metrics()
        self.filter_image_list()


    def snapshot_state(self):
        """
        创建可完整恢复的工程快照。

        旧版本只保存图片顺序，撤销删除/复制时无法重新创建列表项目。
        本版本保存完整图片路径序列，并在 restore_state 中重建列表。
        """
        return {
            "order": list(self.ordered_images()),
            "transforms": {
                path: dict(value)
                for path, value in self.image_transforms.items()
            },
            "hidden": list(self.hidden_images),
            "settings": self.preview_settings(),
            "page": self.preview.current_page(),
            "selected": self.selected_image_index,
            "selected_indices": sorted(
                self.selected_image_indices
            ),
            "blank_pages": self._compat_blank_page_count(),
            "blank_page_positions": (
                self._blank_page_positions()
            ),
            "page_breaks": sorted(
                self._manual_page_breaks
            ),
            "pagination_mode": (
                self._current_pagination_mode()
            ),
            "confirmed_auto_layout": bool(
                getattr(
                    self,
                    "_confirmed_auto_layout",
                    False,
                )
            ),
            "auto_layout_restore_state": deepcopy(
                getattr(
                    self,
                    "_auto_layout_restore_state",
                    None,
                )
            ),
            "image_groups": list(
                self._normalize_image_groups()
            ),
            "group_page_breaks": sorted(
                self._normalize_group_page_breaks()
            ),
            "blank_fill_page_breaks": sorted(
                self._normalize_blank_fill_page_breaks()
            ),
            # 页面锁 / 分组锁已从精简交互模型中移除。
            "page_lock_records": [],
            "locked_group_ids": [],
            "title_system": (
                self._title_system_payload()
            ),
        }


    def push_history(self, label="操作"):
        if self._history_lock:
            return

        self._settings_history_pending = False
        self.undo_stack.append((label, self.snapshot_state()))
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_history_actions()

    def restore_state(self, state):
        """
        完整恢复历史快照。

        支持撤销/重做：
        - 图片复制
        - 图片删除
        - 外部拖入
        - 页面复制/删除/排序
        - 图片顺序
        - 精修参数
        - 显式分页
        """
        self._history_lock = True

        try:
            order = [
                str(path)
                for path in state.get("order", [])
                if path and Path(str(path)).is_file()
            ]

            self._reset_image_thumbnail_queue()
            self.image_list.blockSignals(True)

            try:
                self.image_list.clear()

                for image_path in order:
                    self.image_list.addItem(
                        self._create_external_image_item(
                            image_path
                        )
                    )

            finally:
                self.image_list.blockSignals(False)

            self.image_transforms = {
                str(path): dict(value)
                for path, value in state.get(
                    "transforms",
                    {},
                ).items()
            }
            self.hidden_images = set(
                state.get("hidden", [])
            )
            self._manual_page_breaks = {
                int(value)
                for value in state.get(
                    "page_breaks",
                    [],
                )
            }
            self._image_groups = list(
                state.get(
                    "image_groups",
                    [],
                )
            )
            self._group_page_breaks = {
                int(value)
                for value in state.get(
                    "group_page_breaks",
                    [],
                )
            }
            self._blank_fill_page_breaks = {
                int(value)
                for value in state.get(
                    "blank_fill_page_breaks",
                    [],
                )
            }
            # 锁功能已取消；撤销 / 重做也不再恢复不可见锁。
            self._page_lock_records = []
            self._locked_group_ids = set()
            self._confirmed_auto_layout = bool(
                state.get(
                    "confirmed_auto_layout",
                    False,
                )
            )
            self._auto_layout_restore_state = deepcopy(
                state.get(
                    "auto_layout_restore_state",
                    None,
                )
            )
            self._auto_layout_undo_depth = None
            self._set_pagination_mode(
                state.get(
                    "pagination_mode",
                    PAGINATION_CONTINUOUS,
                ),
                refresh=False,
            )

            self.apply_settings(
                state.get("settings", {})
            )

            self.selected_image_index = int(
                state.get("selected", -1)
            )
            self.selected_image_indices = {
                int(index)
                for index in state.get(
                    "selected_indices",
                    [self.selected_image_index]
                    if self.selected_image_index >= 0
                    else [],
                )
            }

            saved_blank_positions = state.get(
                "blank_page_positions",
                None,
            )

            if saved_blank_positions is None:
                self._set_compat_blank_page_count(
                    state.get(
                        "blank_pages",
                        0,
                    )
                )
            else:
                self._set_blank_page_positions(
                    saved_blank_positions
                )

            self._normalize_image_groups()
            self._normalize_group_page_breaks()
            self._normalize_blank_fill_page_breaks()
            self._normalize_lock_state()
            self._load_title_system(
                state.get(
                    "title_system",
                    {},
                )
            )
            self._normalize_manual_page_breaks()
            self.refresh_image_list_appearance()
            self.refresh_preview()

            page_count = max(
                1,
                int(self.preview.page_count()),
            )
            target_page = max(
                0,
                min(
                    int(state.get("page", 0)),
                    page_count - 1,
                ),
            )
            self.preview.set_page_index(
                target_page
            )
            self._displayed_page_index = target_page

            self._apply_image_selection(
                self.selected_image_indices,
                self.selected_image_index,
                reveal=False,
            )

            self._force_page_thumbnail_refresh()
            self.refresh_preview()

        finally:
            self._history_lock = False
            self._last_stable_history_state = (
                self.snapshot_state()
            )
            self._settings_history_pending = False


    def undo(self):
        if (
            hasattr(self.preview, "is_crop_mode")
            and self.preview.is_crop_mode()
        ):
            self.preview.cancel_crop_mode()
            return

        if not self.undo_stack:
            if hasattr(self, "status_bar"):
                self._show_status(
                    "没有可撤销的操作",
                    1800,
                )
            return

        label, state = self.undo_stack.pop()
        self.redo_stack.append(
            (label, self.snapshot_state())
        )
        self.restore_state(state)
        self.log_box.append(f"已撤销：{label}")

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已撤销：{label}",
                2200,
            )

        self.update_history_actions()

    def redo(self):
        if not self.redo_stack:
            if hasattr(self, "status_bar"):
                self._show_status(
                    "没有可重做的操作",
                    1800,
                )
            return

        label, state = self.redo_stack.pop()
        self.undo_stack.append(
            (label, self.snapshot_state())
        )
        self.restore_state(state)
        self.log_box.append(f"已重做：{label}")

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已重做：{label}",
                2200,
            )

        self.update_history_actions()

    def update_history_actions(self):
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(bool(self.undo_stack))
            self.redo_action.setEnabled(bool(self.redo_stack))

    def reset_layout(self):
        self.push_history("重置排版")
        defaults = {
            "rows": 2, "cols": 6, "page_size": "16:9",
            "image_mode": "保持比例",
            "show_title": False,
            "title_text": "",
            "subtitle_text": "",
            "title_height": 0.9,
            "logo_path": "",
            "show_footer": False,
            "footer_text": "",
            "show_grid": False,
            "show_filename": False, "show_index": False,
            "show_page_number": True, "add_border": False,
            "margin_left": 0.6, "margin_right": 0.6,
            "margin_top": 0.8, "margin_bottom": 0.8,
            "gap_x": 0.25, "gap_y": 0.35,
            "label_height": 0.45,
        }
        self.apply_settings(defaults)
        self.image_transforms = {
            path: {
                "zoom": 1.0, "offset_x": 0.0, "offset_y": 0.0,
                "rotation": 0, "flip_h": False, "flip_v": False,
            }
            for path in self.ordered_images()
        }
        self.hidden_images.clear()
        self.refresh_image_list_appearance()
        self.preview.set_page_index(0)
        self.refresh_preview()

    def on_order_changed(self, *args):
        """
        兼容Qt其它内部移动信号。

        UI-05-43D 的鼠标拖拽已经由
        handle_image_list_internal_drop() 完整接管。
        """
        self.sync_selection_from_image_list()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

    def first_page(self):
        self.preview.set_page_index(0)
        self.refresh_preview()

    def previous_page(self):
        current = self.preview.current_page()
        if current > 0:
            self.preview.set_page_index(current - 1)
            self.refresh_preview()

    def next_page(self):
        current = self.preview.current_page()
        count = self.preview.page_count()
        if current < count - 1:
            self.preview.set_page_index(current + 1)
            self.refresh_preview()

    def last_page(self):
        self.preview.set_page_index(max(0, self.preview.page_count() - 1))
        self.refresh_preview()

    def jump_to_page(self, page_number):
        target = max(0, min(int(page_number) - 1, self.preview.page_count() - 1))
        if target != self.preview.current_page():
            self.preview.set_page_index(target)
            self.refresh_preview()

    # =====================================================
    # UI-05-38A HEIF / HEIC Support
    # =====================================================

    def _show_heif_dependency_notice(
        self,
        *,
        force=False,
    ):
        if (
            self._heif_missing_notice_shown
            and not force
        ):
            return

        self._heif_missing_notice_shown = True

        QMessageBox.warning(
            self,
            "需要安装 HEIF 支持",
            missing_dependency_message(),
        )

    def _filter_decodable_image_paths(
        self,
        paths,
        *,
        notify=True,
    ):
        valid = []
        missing_heif = []

        for path in paths:
            if not path:
                continue

            if not os.path.isfile(path):
                continue

            if not is_supported_media_path(
                path
            ):
                continue

            if is_heif_path(path):
                if not heif_support_available():
                    missing_heif.append(path)
                    continue

            if can_decode_image_path(path):
                valid.append(str(path))

        if missing_heif and notify:
            self._show_heif_dependency_notice()

            if hasattr(self, "log_box"):
                self.log_box.append(
                    (
                        "HEIF/HEIC未导入："
                        f"{len(missing_heif)} 个文件。"
                        "请安装 pillow-heif。"
                    )
                )

        return valid

    # =====================================================
    # UI-05-43A PPT Page-Aware Import
    # =====================================================

    def _ppt_import_mode_label(
        self,
        mode,
    ):
        mapping = {
            PPT_IMPORT_MODE_FLAT: (
                "全部图片 · 一个分组"
            ),
            PPT_IMPORT_MODE_GROUP_BY_SLIDE: (
                "原PPT每页 · 一个分组"
            ),
            PPT_IMPORT_MODE_PAGE_BY_SLIDE: (
                "原PPT每页 · 对应页面"
            ),
        }

        return mapping.get(
            mode,
            "原PPT每页 · 一个分组",
        )

    def _ppt_slide_summaries(
        self,
        result,
        *,
        allowed_paths=None,
    ):
        """
        兼容 UI-05-41A 的旧 importer 结果；
        新 importer 直接提供 slides。
        """
        slide_count = max(
            0,
            int(
                result.get(
                    "slide_count",
                    0,
                )
                or 0
            ),
        )

        allowed = (
            {
                str(path)
                for path in allowed_paths
            }
            if allowed_paths is not None
            else None
        )

        raw_slides = list(
            result.get(
                "slides",
                [],
            )
            or []
        )

        if raw_slides:
            by_slide = {
                int(
                    item.get(
                        "slide_index",
                        0,
                    )
                    or 0
                ): dict(item)
                for item in raw_slides
                if isinstance(
                    item,
                    dict,
                )
            }
        else:
            by_slide = {}

        extracted = list(
            result.get(
                "extracted",
                [],
            )
            or []
        )

        fallback_paths = {
            slide_index: []
            for slide_index in range(
                1,
                slide_count + 1,
            )
        }

        for item in extracted:
            if not isinstance(
                item,
                dict,
            ):
                continue

            try:
                slide_index = int(
                    item.get(
                        "slide_index",
                        0,
                    )
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            path = str(
                item.get(
                    "path",
                    "",
                )
                or ""
            )

            if (
                1
                <= slide_index
                <= slide_count
                and path
            ):
                fallback_paths[
                    slide_index
                ].append(
                    (
                        int(
                            item.get(
                                "visual_order",
                                0,
                            )
                            or 0
                        ),
                        path,
                    )
                )

        summaries = []

        for slide_index in range(
            1,
            slide_count + 1,
        ):
            raw = dict(
                by_slide.get(
                    slide_index,
                    {},
                )
            )

            paths = [
                str(path)
                for path in raw.get(
                    "paths",
                    [],
                )
                if path
            ]

            if not paths:
                paths = [
                    path
                    for _, path in sorted(
                        fallback_paths.get(
                            slide_index,
                            [],
                        )
                    )
                ]

            if allowed is not None:
                paths = [
                    path
                    for path in paths
                    if path in allowed
                ]

            summaries.append(
                {
                    "slide_index": (
                        slide_index
                    ),
                    "picture_object_count": int(
                        raw.get(
                            "picture_object_count",
                            len(paths),
                        )
                        or 0
                    ),
                    "extracted_count": len(
                        paths
                    ),
                    "skipped_count": int(
                        raw.get(
                            "skipped_count",
                            0,
                        )
                        or 0
                    ),
                    "paths": paths,
                }
            )

        return summaries

    def _real_logical_page_count(
        self,
    ):
        image_count = len(
            self.visible_images()
        )
        blank_count = len(
            self._blank_page_positions()
        )

        if (
            image_count <= 0
            and blank_count <= 0
        ):
            return 0

        image_pages = (
            len(
                self._computed_page_ranges()
            )
            if image_count > 0
            else 0
        )

        return (
            image_pages
            + blank_count
        )

    def _apply_ppt_import_groups(
        self,
        *,
        import_start,
        slide_summaries,
        source_name,
        single_group=False,
    ):
        """
        建立PPT来源分组元数据。
        即使当前处于连续模式，也先保存分组信息；
        后续切换分组排版时仍可正确恢复。
        """
        image_count = len(
            self.visible_images()
        )

        if image_count <= 0:
            return 0

        self._normalize_image_groups()
        groups = [
            dict(item)
            for item in self._image_groups
        ]

        starts_and_names = []

        if single_group:
            has_any = any(
                item.get(
                    "paths"
                )
                for item in slide_summaries
            )

            if has_any:
                starts_and_names.append(
                    (
                        int(import_start),
                        str(source_name),
                    )
                )

        else:
            cursor = int(
                import_start
            )

            for item in slide_summaries:
                paths = list(
                    item.get(
                        "paths",
                        [],
                    )
                    or []
                )

                if not paths:
                    continue

                slide_index = int(
                    item.get(
                        "slide_index",
                        0,
                    )
                    or 0
                )

                starts_and_names.append(
                    (
                        cursor,
                        (
                            f"{source_name} · "
                            f"第 {slide_index:02d} 页"
                        ),
                    )
                )
                cursor += len(
                    paths
                )

        created = 0

        for start, name in starts_and_names:
            start = int(
                start
            )

            if not (
                0
                <= start
                < image_count
            ):
                continue

            existing = next(
                (
                    item
                    for item in groups
                    if int(
                        item.get(
                            "start",
                            -1,
                        )
                    )
                    == start
                ),
                None,
            )

            if existing is not None:
                existing["name"] = (
                    str(name)
                )
            else:
                groups.append(
                    {
                        "name": str(
                            name
                        ),
                        "start": start,
                    }
                )

            created += 1

        self._image_groups = (
            normalize_groups(
                groups,
                image_count,
            )
        )
        self._normalize_image_groups()

        return created

    def _apply_ppt_page_mapping(
        self,
        *,
        import_start,
        base_logical_page_count,
        slide_summaries,
    ):
        """
        原PPT每页直接映射到FrameDeck逻辑页面。

        - 原PPT空页 -> FrameDeck空白页；
        - 原PPT有图页 -> 建立固定页边界；
        - 图片超过当前 rows×cols 容量 -> 自动续页；
        - 不与前一个已有FrameDeck页面混排。
        """
        capacity = (
            self._page_capacity()
        )
        image_count = len(
            self.visible_images()
        )
        cursor = int(
            import_start
        )
        fixed_breaks = set(
            self._blank_fill_page_breaks
        )

        if (
            0
            < cursor
            < image_count
        ):
            fixed_breaks.add(
                cursor
            )

        new_blank_positions = []
        logical_cursor = int(
            base_logical_page_count
        )
        overflow_slide_count = 0

        for item in slide_summaries:
            paths = list(
                item.get(
                    "paths",
                    [],
                )
                or []
            )
            count = len(
                paths
            )

            if count <= 0:
                new_blank_positions.append(
                    logical_cursor
                )
                logical_cursor += 1
                continue

            if (
                0
                < cursor
                < image_count
            ):
                fixed_breaks.add(
                    cursor
                )

            cursor += count

            if (
                0
                < cursor
                < image_count
            ):
                fixed_breaks.add(
                    cursor
                )

            pages_for_slide = max(
                1,
                int(
                    math.ceil(
                        count
                        / capacity
                    )
                ),
            )

            if pages_for_slide > 1:
                overflow_slide_count += 1

            logical_cursor += (
                pages_for_slide
            )

        self._blank_fill_page_breaks = {
            int(value)
            for value in fixed_breaks
            if (
                0
                < int(value)
                < image_count
            )
        }
        self._normalize_blank_fill_page_breaks()

        existing_blanks = (
            self._blank_page_positions()
        )
        self._set_blank_page_positions(
            existing_blanks
            + new_blank_positions
        )

        return {
            "new_blank_pages": len(
                new_blank_positions
            ),
            "overflow_slide_count": (
                overflow_slide_count
            ),
            "logical_pages_added": max(
                0,
                logical_cursor
                - int(
                    base_logical_page_count
                ),
            ),
        }

    # UI-05-41A / UI-05-43A PPT Image Import
    # =====================================================

    def import_ppt_images(self):
        """
        从PPT中提取图片素材并追加到当前工程。

        UI-05-43A 支持：
        - 全部图片作为一个分组；
        - 原PPT每页作为一个分组；
        - 原PPT每页直接对应FrameDeck页面。
        """
        if (
            self.ppt_import_worker is not None
            and self.ppt_import_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "PPT图片正在导入",
                "请等待当前PPT图片提取完成，或在进度窗口中取消。",
            )
            return

        ppt_path, _ = QFileDialog.getOpenFileName(
            self,
            self._translated("选择要提取图片的PPT"),
            "",
            self._translated_file_filter((
                "PowerPoint 文件 "
                "(*.pptx *.pptm);;"
                "PowerPoint 演示文稿 (*.pptx);;"
                "启用宏的演示文稿 (*.pptm)"
            )),
        )

        if not ppt_path:
            return

        suffix = Path(
            ppt_path
        ).suffix.lower()

        if suffix == ".ppt":
            QMessageBox.warning(
                self,
                "暂不支持旧版PPT",
                (
                    "旧版 .ppt 是二进制格式。\n\n"
                    "请先使用WPS或PowerPoint另存为 .pptx，"
                    "再执行图片导入。"
                ),
            )
            return

        if suffix not in SUPPORTED_PPT_EXTENSIONS:
            QMessageBox.warning(
                self,
                "文件格式不支持",
                "当前支持 .pptx 和 .pptm。",
            )
            return

        confirmation = QMessageBox(self)
        confirmation.setWindowTitle(
            "PPT导入方式"
        )
        confirmation.setIcon(
            QMessageBox.Icon.Information
        )
        confirmation.setText(
            (
                "请选择原PPT页面结构的保留方式：\n"
                f"{ppt_path}"
            )
        )
        confirmation.setInformativeText(
            (
                "图片始终按“原页码 → 页面视觉顺序”提取。\n\n"
                "全部图片 · 一个分组：合并为一个导入批次。\n"
                "原PPT每页 · 一个分组：每个有图片的原页建立独立分组，"
                "并切换到分组排版。\n"
                "原PPT每页 · 对应页面：保留原页边界；"
                "无图片原页生成空白页。\n\n"
                "若某一原页图片数超过当前页面容量，"
                "会紧接该原页自动续页。\n"
                "原PPT不会被修改。"
            )
        )

        flat_button = confirmation.addButton(
            "全部图片 · 一个分组",
            QMessageBox.ButtonRole.ActionRole,
        )
        group_button = confirmation.addButton(
            "原PPT每页 · 一个分组",
            QMessageBox.ButtonRole.AcceptRole,
        )
        page_button = confirmation.addButton(
            "原PPT每页 · 对应页面",
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_button = confirmation.addButton(
            "取消",
            QMessageBox.ButtonRole.RejectRole,
        )
        confirmation.setDefaultButton(
            group_button
        )
        confirmation.setEscapeButton(
            cancel_button
        )
        confirmation.exec()

        clicked_button = (
            confirmation.clickedButton()
        )

        if clicked_button is cancel_button:
            return

        if clicked_button is flat_button:
            import_layout_mode = (
                PPT_IMPORT_MODE_FLAT
            )
        elif clicked_button is page_button:
            import_layout_mode = (
                PPT_IMPORT_MODE_PAGE_BY_SLIDE
            )
        else:
            import_layout_mode = (
                PPT_IMPORT_MODE_GROUP_BY_SLIDE
            )

        self._ppt_import_layout_mode = (
            import_layout_mode
        )

        self._ppt_import_source = str(
            ppt_path
        )
        self.import_ppt_images_button.setEnabled(
            False
        )
        self.add_images_primary_button.setEnabled(
            False
        )

        progress = QProgressDialog(
            "正在扫描PPT……",
            "取消导入",
            0,
            100,
            self,
        )
        progress.setWindowTitle(
            "导入PPT图片"
        )
        progress.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        progress.setMinimumDuration(
            0
        )
        progress.setAutoClose(
            False
        )
        progress.setAutoReset(
            False
        )
        progress.setValue(
            0
        )
        progress.show()

        worker = PPTImportWorker(
            ppt_path,
            self,
        )
        worker.progress.connect(
            self._on_ppt_import_progress
        )
        worker.finished_ok.connect(
            self._on_ppt_import_finished
        )
        worker.failed.connect(
            self._on_ppt_import_failed
        )
        worker.cancelled.connect(
            self._on_ppt_import_cancelled
        )
        progress.canceled.connect(
            worker.requestInterruption
        )

        self.ppt_import_progress = progress
        self.ppt_import_worker = worker
        worker.start()

    def _on_ppt_import_progress(
        self,
        current,
        total,
        message,
    ):
        progress = (
            self.ppt_import_progress
        )

        if progress is None:
            return

        total = max(
            1,
            int(total),
        )
        current = max(
            0,
            min(
                int(current),
                total,
            ),
        )
        percent = round(
            current / total * 100
        )
        progress.setLabelText(
            str(message)
        )
        progress.setValue(
            percent
        )

    def _close_ppt_import_progress(
        self,
    ):
        progress = (
            self.ppt_import_progress
        )
        self.ppt_import_progress = None

        if progress is not None:
            progress.close()
            progress.deleteLater()

        self.import_ppt_images_button.setEnabled(
            True
        )
        self.add_images_primary_button.setEnabled(
            True
        )

    def _on_ppt_import_finished(
        self,
        result,
    ):
        self._close_ppt_import_progress()

        worker = self.ppt_import_worker
        self.ppt_import_worker = None

        if worker is not None:
            worker.deleteLater()

        extracted = list(
            result.get(
                "extracted",
                [],
            )
        )
        paths = [
            str(item.get("path", ""))
            for item in extracted
            if item.get("path")
        ]

        import_mode = getattr(
            self,
            "_ppt_import_layout_mode",
            PPT_IMPORT_MODE_GROUP_BY_SLIDE,
        )
        source_name = Path(
            self._ppt_import_source
            or result.get(
                "source_file",
                "",
            )
            or "PPT导入"
        ).stem

        import_start = len(
            self.visible_images()
        )
        base_logical_page_count = (
            self._real_logical_page_count()
        )

        # “原PPT每页对应页面”即使PPT没有任何图片，
        # 也应该能导入其空白页面结构。
        if not paths:
            slide_summaries = (
                self._ppt_slide_summaries(
                    result
                )
            )

            if (
                import_mode
                == PPT_IMPORT_MODE_PAGE_BY_SLIDE
                and slide_summaries
            ):
                self.push_history(
                    "导入PPT页面结构"
                )

                page_result = (
                    self._apply_ppt_page_mapping(
                        import_start=(
                            import_start
                        ),
                        base_logical_page_count=(
                            base_logical_page_count
                        ),
                        slide_summaries=(
                            slide_summaries
                        ),
                    )
                )

                self._displayed_page_index = (
                    base_logical_page_count
                )
                self._force_page_thumbnail_refresh()
                self.refresh_preview()

                QMessageBox.information(
                    self,
                    "PPT页面结构导入完成",
                    (
                        f"原PPT页数："
                        f"{len(slide_summaries)}\n"
                        f"新增空白页："
                        f"{page_result['new_blank_pages']} 页"
                    ),
                )
                return

            warnings = list(
                result.get(
                    "warnings",
                    [],
                )
            )
            detail = (
                "\n".join(
                    warnings[:8]
                )
                if warnings
                else "该PPT中没有发现可提取的图片对象。"
            )
            QMessageBox.information(
                self,
                "没有可导入图片",
                detail,
            )
            return

        # 三种模式都由43A统一建立分组/页面边界，
        # 所以禁用旧的“每次导入创建新分组”自动路径，
        # 防止重复创建边界。
        inserted = self._insert_external_images(
            paths,
            self.image_list.count(),
            "导入PPT图片",
            consume_compat_blank_page=False,
            start_new_group=False,
            new_group_name=source_name,
        )

        inserted_path_set = set(
            self.ordered_images()
        )
        slide_summaries = (
            self._ppt_slide_summaries(
                result,
                allowed_paths=(
                    inserted_path_set
                ),
            )
        )

        group_count = 0
        page_result = {
            "new_blank_pages": 0,
            "overflow_slide_count": 0,
            "logical_pages_added": 0,
        }

        if (
            import_mode
            == PPT_IMPORT_MODE_FLAT
        ):
            group_count = (
                self._apply_ppt_import_groups(
                    import_start=(
                        import_start
                    ),
                    slide_summaries=(
                        slide_summaries
                    ),
                    source_name=(
                        source_name
                    ),
                    single_group=True,
                )
            )

        elif (
            import_mode
            == PPT_IMPORT_MODE_GROUP_BY_SLIDE
        ):
            group_count = (
                self._apply_ppt_import_groups(
                    import_start=(
                        import_start
                    ),
                    slide_summaries=(
                        slide_summaries
                    ),
                    source_name=(
                        source_name
                    ),
                    single_group=False,
                )
            )
            self._set_pagination_mode(
                PAGINATION_GROUPED,
                refresh=False,
            )

        elif (
            import_mode
            == PPT_IMPORT_MODE_PAGE_BY_SLIDE
        ):
            group_count = (
                self._apply_ppt_import_groups(
                    import_start=(
                        import_start
                    ),
                    slide_summaries=(
                        slide_summaries
                    ),
                    source_name=(
                        source_name
                    ),
                    single_group=False,
                )
            )
            page_result = (
                self._apply_ppt_page_mapping(
                    import_start=(
                        import_start
                    ),
                    base_logical_page_count=(
                        base_logical_page_count
                    ),
                    slide_summaries=(
                        slide_summaries
                    ),
                )
            )

        # 应用PPT中的非破坏性图片参数。
        applied = 0

        for item in extracted:
            path = str(
                item.get(
                    "path",
                    "",
                )
            )

            if (
                not path
                or path
                not in self.ordered_images()
            ):
                continue

            transform = self.get_transform(
                path
            )
            source_transform = dict(
                item.get(
                    "transform",
                    {},
                )
            )

            for key in (
                "zoom",
                "offset_x",
                "offset_y",
                "rotation",
                "flip_h",
                "flip_v",
            ):
                if key in source_transform:
                    transform[key] = (
                        source_transform[key]
                    )

            if "crop" in source_transform:
                transform["crop"] = (
                    normalize_crop(
                        source_transform.get(
                            "crop"
                        )
                    )
                )

            self.image_transforms[
                path
            ] = transform
            applied += 1

        if (
            applied
            or group_count
            or import_mode
            == PPT_IMPORT_MODE_PAGE_BY_SLIDE
        ):
            self._displayed_page_index = max(
                0,
                int(
                    base_logical_page_count
                ),
            )
            self._force_page_thumbnail_refresh()
            self.refresh_preview()

        warnings = list(
            result.get(
                "warnings",
                [],
            )
        )
        slide_count = int(
            result.get(
                "slide_count",
                0,
            )
        )
        skipped_count = int(
            result.get(
                "skipped_count",
                0,
            )
        )
        output_directory = str(
            result.get(
                "output_directory",
                "",
            )
        )

        if hasattr(
            self,
            "log_box",
        ):
            self.log_box.append(
                (
                    "PPT图片导入完成："
                    f"{slide_count}页，"
                    f"提取{len(paths)}张，"
                    f"加入工程{inserted}张，"
                    f"模式={self._ppt_import_mode_label(import_mode)}"
                )
            )

            if output_directory:
                self.log_box.append(
                    (
                        "PPT提取文件保存于："
                        f"{output_directory}"
                    )
                )

            for warning in warnings[:20]:
                self.log_box.append(
                    "PPT导入提示："
                    + str(warning)
                )

        empty_slide_count = sum(
            1
            for item in slide_summaries
            if not item.get(
                "paths"
            )
        )

        message = (
            f"PPT页数：{slide_count}\n"
            f"提取图片：{len(paths)} 张\n"
            f"加入工程：{inserted} 张\n"
            f"导入方式："
            f"{self._ppt_import_mode_label(import_mode)}"
        )

        if (
            import_mode
            == PPT_IMPORT_MODE_GROUP_BY_SLIDE
        ):
            message += (
                f"\n建立分组：{group_count} 个"
                "\n分页方式：已切换为分组排版"
            )

        elif (
            import_mode
            == PPT_IMPORT_MODE_FLAT
        ):
            message += (
                f"\n建立分组：{group_count} 个"
            )

        elif (
            import_mode
            == PPT_IMPORT_MODE_PAGE_BY_SLIDE
        ):
            message += (
                f"\n原页空白页："
                f"{page_result['new_blank_pages']} 页"
                f"\n新增逻辑页："
                f"{page_result['logical_pages_added']} 页"
            )

            if (
                page_result[
                    "overflow_slide_count"
                ]
            ):
                message += (
                    "\n超过当前页面容量并自动续页："
                    f"{page_result['overflow_slide_count']} 个原PPT页"
                )

        if empty_slide_count:
            message += (
                f"\n原PPT无图片页："
                f"{empty_slide_count} 页"
            )

        if skipped_count:
            message += (
                f"\n跳过对象：{skipped_count} 个"
            )

        if warnings:
            message += (
                "\n\n部分对象未能完整提取，"
                "详细信息已写入日志面板。"
            )

        QMessageBox.information(
            self,
            "PPT图片导入完成",
            message,
        )

    def _on_ppt_import_failed(
        self,
        error,
    ):
        self._close_ppt_import_progress()

        worker = self.ppt_import_worker
        self.ppt_import_worker = None

        if worker is not None:
            worker.deleteLater()

        error = str(
            error or ""
        )

        if hasattr(
            self,
            "log_box",
        ):
            self.log_box.append(
                error
            )
            self.log_dock.show()
            self.log_dock.raise_()

        QMessageBox.critical(
            self,
            "PPT图片导入失败",
            (
                "PPT解析或图片提取失败。\n\n"
                "原PPT和当前工程没有被修改，"
                "详细错误已写入日志面板。"
            ),
        )

    def _on_ppt_import_cancelled(
        self,
    ):
        self._close_ppt_import_progress()

        worker = self.ppt_import_worker
        self.ppt_import_worker = None

        if worker is not None:
            worker.deleteLater()

        if hasattr(
            self,
            "status_bar",
        ):
            self._show_status(
                "已取消PPT图片导入",
                2800,
            )

    def add_images(self):
        """UI-05-18-A 统一添加图片

        Windows 文件选择器直接支持：
        - 单张选择
        - Ctrl 多选
        - Shift 连选
        """

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self._translated("添加图片"),
            "",
            self._translated_file_filter((
                "全部支持图片 ("
                + ALL_IMAGE_FILE_FILTER
                + ");;"
                "HEIF / HEIC 图片 "
                "(*.heic *.heics *.heif *.heifs *.hif);;"
                "常规图片 "
                "(*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)"
            )),
        )

        if paths:
            self._add_selected_images(paths)


    def _add_selected_images(self, paths):
        valid = (
            self._filter_decodable_image_paths(
                paths,
                notify=True,
            )
        )

        if not valid:
            return

        group_name = ""

        try:
            parent_names = {
                str(Path(path).parent)
                for path in valid
            }

            if len(parent_names) == 1:
                group_name = Path(
                    valid[0]
                ).parent.name
        except Exception:
            group_name = ""

        current_page = (
            self._current_logical_page_index()
        )
        replace_blank_page_index = (
            current_page
            if self._is_blank_page(
                current_page
            )
            else None
        )

        partial_page_context = (
            None
            if replace_blank_page_index
            is not None
            else self._selected_partial_page_insert_context()
        )

        if partial_page_context is not None:
            # FIX10：
            # 选中的普通图片页尚未填满时，“添加图片”与中央拖入保持一致，
            # 从当前页末尾继续补图。
            insert_row = int(
                partial_page_context[
                    "insert_row"
                ]
            )

            # 明确选择未满页补图时，当前操作属于当前页/当前分组，
            # “每次导入创建新分组”不应强制把它拆成新页面。
            start_new_group = False
            boundary_belongs_to_previous = True
            history_label = (
                f"补充第 "
                f"{partial_page_context['page_index'] + 1} 页"
            )

        else:
            insert_row = (
                self.image_list.count()
            )
            start_new_group = (
                self._should_start_new_import_group()
            )
            boundary_belongs_to_previous = False
            history_label = (
                "填充空白页"
                if replace_blank_page_index
                is not None
                else "添加图片"
            )

        inserted = self._insert_external_images(
            valid,
            insert_row,
            history_label,
            consume_compat_blank_page=False,
            start_new_group=(
                start_new_group
            ),
            new_group_name=group_name,
            boundary_belongs_to_previous=(
                boundary_belongs_to_previous
            ),
            replace_blank_page_index=(
                replace_blank_page_index
            ),
        )

        if (
            inserted
            and partial_page_context
            is not None
            and hasattr(
                self,
                "status_bar",
            )
        ):
            remaining = int(
                partial_page_context[
                    "remaining"
                ]
            )
            filled_here = min(
                inserted,
                remaining,
            )
            overflow = max(
                0,
                inserted
                - remaining,
            )

            message = (
                f"已从第 "
                f"{partial_page_context['page_index'] + 1} 页"
                f"继续添加 {inserted} 张"
                f" · 填充空位 {filled_here} 张"
            )

            if overflow:
                message += (
                    f" · 其余 {overflow} 张紧接当前页继续分页"
                )

            self._show_status(
                message,
                4200,
            )


    @staticmethod
    def _is_hidden_or_system_import_file(
        path,
    ):
        """
        兼容旧工程的目录扫描保护。

        即使旧配置仍调用load_images，也跳过：
        - 点号隐藏文件；
        - Windows Hidden / System属性文件；
        - desktop.ini、Thumbs.db等系统文件。
        """
        path = Path(path)
        lower_name = path.name.lower()

        if (
            path.name.startswith(".")
            or lower_name in {
                "desktop.ini",
                "thumbs.db",
                "ehthumbs.db",
                "folder.jpg",
                "albumartsmall.jpg",
            }
        ):
            return True

        try:
            attributes = int(
                getattr(
                    path.stat(),
                    "st_file_attributes",
                    0,
                )
            )

            # Windows FILE_ATTRIBUTE_HIDDEN = 0x2
            # Windows FILE_ATTRIBUTE_SYSTEM = 0x4
            if attributes & 0x2:
                return True

            if attributes & 0x4:
                return True

        except OSError:
            return True

        return False

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self._translated("选择图片目录"),
        )
        if folder:
            self.on_folder_selected(folder)

    def on_folder_selected(self, folder):
        self.folder_edit.setText(folder)
        self.output_edit.setText(str(Path(folder) / "output.pptx"))
        self.load_images()


    # =====================================================
    # UI-05-14-B FIX04
    # Canvas external drop receiver
    #
    # PreviewCanvas 已成功收到路径，
    # 这里负责进入项目图片数据层并刷新中央画布。
    # =====================================================

    # =====================================================
    # UI-05-39B All-format Background Thumbnail Loading
    # =====================================================

    @staticmethod
    def _thumbnail_is_heavy(path):
        suffix = Path(path).suffix.lower()
        return bool(
            suffix in HEIF_EXTENSIONS
            or suffix in {
                ".tif",
                ".tiff",
            }
        )

    def _reset_image_thumbnail_queue(self):
        """
        取消旧工程的待处理任务。

        已经开始解码的任务可能自然完成，但由于 generation 已变化，
        完成结果会被安全忽略。
        """
        self._thumbnail_generation += 1
        self._thumbnail_cancelled = False

        self._thumbnail_dispatch_timer.stop()
        self._thumbnail_priority_timer.stop()
        self._thumbnail_progress_timer.stop()
        self._thumbnail_navigation_flush_timer.stop()

        self._thumbnail_pending.clear()
        self._thumbnail_item_refs.clear()
        self._thumbnail_inflight.clear()
        self._thumbnail_priority_dirty = True
        self._thumbnail_navigation_dirty_paths.clear()
        self._thumbnail_heavy_inflight = 0
        self._thumbnail_total = 0
        self._thumbnail_completed = 0
        self._thumbnail_failed = 0

        try:
            self._thumbnail_pool.clear()
        except Exception:
            pass

        if hasattr(
            self,
            "thumbnail_cancel_button",
        ):
            self.thumbnail_cancel_button.hide()

    def _queue_image_thumbnail(
        self,
        item,
        path,
    ):
        self._thumbnail_request_serial += 1
        request_id = (
            self._thumbnail_request_serial
        )
        token = request_id

        item.setData(
            THUMBNAIL_ITEM_TOKEN_ROLE,
            token,
        )

        entry = {
            "generation": (
                self._thumbnail_generation
            ),
            "request_id": request_id,
            "token": token,
            "path": str(path),
            "heavy": (
                self._thumbnail_is_heavy(
                    path
                )
            ),
        }

        self._thumbnail_item_refs[
            token
        ] = item
        self._thumbnail_pending.append(
            entry
        )
        self._thumbnail_priority_dirty = True
        self._thumbnail_total += 1

        if (
            self._thumbnail_total >= 20
            and hasattr(
                self,
                "thumbnail_cancel_button",
            )
        ):
            self.thumbnail_cancel_button.show()

        # item通常尚未插入列表，延迟到事件循环后再调度。
        self._thumbnail_dispatch_timer.start(
            0
        )

    def _visible_image_list_row_range(self):
        if self.image_list.count() <= 0:
            return 0, -1

        viewport = self.image_list.viewport()
        top_index = self.image_list.indexAt(
            QPoint(4, 4)
        )
        bottom_index = self.image_list.indexAt(
            QPoint(
                4,
                max(
                    4,
                    viewport.height() - 4,
                ),
            )
        )

        top_row = (
            top_index.row()
            if top_index.isValid()
            else max(
                0,
                self.image_list.currentRow(),
            )
        )
        bottom_row = (
            bottom_index.row()
            if bottom_index.isValid()
            else min(
                self.image_list.count() - 1,
                top_row + 14,
            )
        )

        return (
            max(0, top_row),
            max(top_row, bottom_row),
        )

    def _current_page_thumbnail_paths(self):
        try:
            start, end = (
                self.preview.page_range()
            )
            return set(
                self.images[
                    max(0, start):
                    max(0, end)
                ]
            )
        except Exception:
            return set()

    def _thumbnail_priority_context(self):
        top_row, bottom_row = (
            self._visible_image_list_row_range()
        )
        return {
            "top": top_row,
            "bottom": bottom_row,
            "page_paths": (
                self._current_page_thumbnail_paths()
            ),
        }

    def _thumbnail_entry_priority(
        self,
        entry,
        context,
    ):
        row = context["row_by_token"].get(
            entry["token"],
            -1,
        )

        if row < 0:
            return (
                99,
                entry["request_id"],
            )

        path = entry["path"]
        top_row = context["top"]
        bottom_row = context["bottom"]

        if path in context["page_paths"]:
            band = 0
            distance = 0
        elif top_row <= row <= bottom_row:
            band = 1
            distance = 0
        elif (
            top_row - 12
            <= row
            <= bottom_row + 12
        ):
            band = 2
            distance = min(
                abs(row - top_row),
                abs(row - bottom_row),
            )
        else:
            band = 3
            distance = row

        return (
            band,
            distance,
            entry["request_id"],
        )

    def _reprioritize_thumbnail_jobs(
        self,
        *,
        schedule_dispatch=True,
    ):
        if not self._thumbnail_pending:
            return

        if not self._thumbnail_priority_dirty:
            if schedule_dispatch:
                self._thumbnail_dispatch_timer.start(0)
            return

        context = (
            self._thumbnail_priority_context()
        )
        row_by_token = {}

        # QListWidget.row(item) can scan the model. Build one token map in
        # O(N) instead of performing that lookup from every sort key.
        for row in range(self.image_list.count()):
            item = self.image_list.item(row)

            if item is None:
                continue

            try:
                token = int(
                    item.data(
                        THUMBNAIL_ITEM_TOKEN_ROLE
                    )
                )
            except (TypeError, ValueError):
                continue

            row_by_token[token] = row

        context["row_by_token"] = row_by_token
        self._thumbnail_pending.sort(
            key=lambda entry: (
                self._thumbnail_entry_priority(
                    entry,
                    context,
                )
            ),
            reverse=True,
        )
        self._thumbnail_priority_dirty = False

        if schedule_dispatch:
            self._thumbnail_dispatch_timer.start(0)

    def _schedule_thumbnail_priority_refresh(
        self,
        *_args,
    ):
        if self._thumbnail_pending:
            self._thumbnail_priority_dirty = True
            self._thumbnail_priority_timer.start()

    def _next_thumbnail_entry(self):
        if not self._thumbnail_pending:
            return None

        self._reprioritize_thumbnail_jobs(
            schedule_dispatch=False
        )

        for index in range(
            len(self._thumbnail_pending) - 1,
            -1,
            -1,
        ):
            entry = self._thumbnail_pending[index]

            if (
                entry["heavy"]
                and self._thumbnail_heavy_inflight
                >= self._thumbnail_max_heavy_inflight
            ):
                continue

            return self._thumbnail_pending.pop(
                index
            )

        return None

    def _dispatch_thumbnail_jobs(self):
        if self._thumbnail_cancelled:
            return

        while (
            len(self._thumbnail_inflight)
            < self._thumbnail_max_inflight
        ):
            entry = (
                self._next_thumbnail_entry()
            )

            if entry is None:
                break

            item = self._thumbnail_item_refs.get(
                entry["token"]
            )

            try:
                valid_item = (
                    item is not None
                    and self.image_list.row(item)
                    >= 0
                    and int(
                        item.data(
                            THUMBNAIL_ITEM_TOKEN_ROLE
                        )
                    )
                    == entry["token"]
                    and str(
                        item.data(
                            Qt.ItemDataRole.UserRole
                        )
                    )
                    == entry["path"]
                )
            except Exception:
                valid_item = False

            if not valid_item:
                self._thumbnail_item_refs.pop(
                    entry["token"],
                    None,
                )
                self._thumbnail_completed += 1
                continue

            task = _ThumbnailDecodeTask(
                self._image_cache,
                generation=entry[
                    "generation"
                ],
                request_id=entry[
                    "request_id"
                ],
                token=entry["token"],
                path=entry["path"],
                width=THUMBNAIL_WORK_WIDTH,
                height=THUMBNAIL_WORK_HEIGHT,
                heavy=entry["heavy"],
            )
            task.signals.completed.connect(
                self._on_thumbnail_task_finished,
                Qt.ConnectionType.QueuedConnection,
            )

            self._thumbnail_inflight[
                entry["request_id"]
            ] = (
                task,
                entry,
            )

            if entry["heavy"]:
                self._thumbnail_heavy_inflight += 1

            self._thumbnail_pool.start(
                task
            )

        self._thumbnail_progress_timer.start()

    @Slot(object)
    def _on_thumbnail_task_finished(
        self,
        result,
    ):
        request_id = int(
            result.get(
                "request_id",
                -1,
            )
        )
        inflight = (
            self._thumbnail_inflight.pop(
                request_id,
                None,
            )
        )

        if inflight is not None:
            _task, entry = inflight

            if entry.get("heavy"):
                self._thumbnail_heavy_inflight = max(
                    0,
                    self._thumbnail_heavy_inflight - 1,
                )

        if (
            int(
                result.get(
                    "generation",
                    -1,
                )
            )
            != self._thumbnail_generation
        ):
            self._thumbnail_dispatch_timer.start(
                0
            )
            return

        token = int(
            result.get(
                "token",
                -1,
            )
        )
        path = str(
            result.get(
                "path",
                "",
            )
        )
        item = self._thumbnail_item_refs.pop(
            token,
            None,
        )
        image = result.get(
            "image"
        )

        try:
            valid_item = (
                item is not None
                and self.image_list.row(item)
                >= 0
                and int(
                    item.data(
                        THUMBNAIL_ITEM_TOKEN_ROLE
                    )
                )
                == token
                and str(
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                )
                == path
            )
        except Exception:
            valid_item = False

        image_valid = (
            isinstance(image, QImage)
            and not image.isNull()
        )

        if valid_item and image_valid:
            source_pixmap = QPixmap.fromImage(
                image
            )
            self._image_cache.remember_thumbnail_pixmap(
                path,
                THUMBNAIL_WORK_WIDTH,
                THUMBNAIL_WORK_HEIGHT,
                source_pixmap,
            )

            icon_size = self.image_list.iconSize()
            item.setIcon(
                QIcon(
                    source_pixmap.scaled(
                        max(
                            32,
                            icon_size.width(),
                        ),
                        max(
                            24,
                            icon_size.height(),
                        ),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            )
            self._thumbnail_completed += 1
            self._invalidate_navigation_thumbnail_for_path(
                path
            )
        else:
            self._thumbnail_failed += 1

            error = str(
                result.get(
                    "error",
                    "",
                )
            ).strip()

            if error and hasattr(
                self,
                "log_box",
            ):
                self.log_box.append(
                    (
                        "缩略图生成失败："
                        f"{Path(path).name} · "
                        f"{error}"
                    )
                )

        self._thumbnail_progress_timer.start()
        self._thumbnail_dispatch_timer.start(
            0
        )

    def _invalidate_navigation_thumbnail_for_path(
        self,
        path,
    ):
        """
        Collect completed paths and invalidate their pages once per burst.
        """
        path = str(path or "")

        if not path:
            return

        self._thumbnail_navigation_dirty_paths.add(path)
        self._thumbnail_navigation_flush_timer.start()

    def _flush_navigation_thumbnail_invalidations(self):
        dirty_paths = set(
            self._thumbnail_navigation_dirty_paths
        )
        self._thumbnail_navigation_dirty_paths.clear()

        if not dirty_paths:
            return

        try:
            # The widget order is authoritative while an import or reorder is
            # still settling; one batched scan is inexpensive and avoids
            # dropping a just-imported path from navigation invalidation.
            visible = self.visible_images()
            page_count = max(
                1,
                int(self.preview.page_count()),
            )
            page_ranges = self._logical_page_ranges_snapshot(
                page_count,
                image_ranges=self.preview.page_ranges(),
                image_count=len(visible),
            )
        except Exception:
            return

        dirty_pages = set()

        for page_index, (start, end) in enumerate(page_ranges):
            if any(
                path in dirty_paths
                for path in visible[
                    max(0, int(start)):
                    max(0, int(end))
                ]
            ):
                dirty_pages.add(page_index)

        if not dirty_pages:
            return

        for page_index in dirty_pages:
            self._page_thumbnail_signatures.pop(
                page_index,
                None,
            )

        self._last_real_thumbnail_signature = (
            None
        )
        self.schedule_real_thumbnail_refresh()

    def _update_thumbnail_progress_status(self):
        remaining = (
            len(self._thumbnail_pending)
            + len(self._thumbnail_inflight)
        )
        done = (
            self._thumbnail_completed
            + self._thumbnail_failed
        )

        if remaining > 0:
            if (
                self._thumbnail_total >= 20
                and hasattr(
                    self,
                    "status_bar",
                )
            ):
                self._show_status(
                    (
                        "后台生成缩略图："
                        f"{done}/{self._thumbnail_total}"
                        "（软件可继续操作）"
                    )
                )

            if hasattr(
                self,
                "thumbnail_cancel_button",
            ):
                self.thumbnail_cancel_button.setVisible(
                    self._thumbnail_total >= 20
                )

            return

        if hasattr(
            self,
            "thumbnail_cancel_button",
        ):
            self.thumbnail_cancel_button.hide()

        if (
            self._thumbnail_total >= 20
            and hasattr(
                self,
                "status_bar",
            )
        ):
            self._show_status(
                (
                    "缩略图后台缓存完成："
                    f"{self._thumbnail_completed} 张"
                ),
                2400,
            )

    def cancel_background_thumbnail_loading(
        self,
    ):
        if (
            not self._thumbnail_pending
            and not self._thumbnail_inflight
        ):
            return

        self._thumbnail_generation += 1
        self._thumbnail_cancelled = True
        self._thumbnail_pending.clear()
        self._thumbnail_item_refs.clear()
        self._thumbnail_inflight.clear()
        self._thumbnail_priority_dirty = True
        self._thumbnail_navigation_dirty_paths.clear()
        self._thumbnail_navigation_flush_timer.stop()
        self._thumbnail_heavy_inflight = 0

        try:
            self._thumbnail_pool.clear()
        except Exception:
            pass

        if hasattr(
            self,
            "thumbnail_cancel_button",
        ):
            self.thumbnail_cancel_button.hide()

        if hasattr(
            self,
            "status_bar",
        ):
            self._show_status(
                (
                    "已停止剩余缩略图后台加载；"
                    "图片和工程内容仍然保留"
                ),
                3500,
            )


    def _prune_image_cache_if_due(self):
        try:
            result = self._image_cache.prune_if_due(
                interval_hours=24,
                max_bytes=1024 * 1024 * 1024,
                max_age_days=60,
            )

            if result and result.get("deleted_files", 0):
                freed_mb = (
                    result.get("freed_bytes", 0)
                    / 1024
                    / 1024
                )
                self.log_box.append(
                    (
                        "缓存自动清理："
                        f"删除 {result['deleted_files']} 个文件，"
                        f"释放 {freed_mb:.1f} MB"
                    )
                )

        except Exception as error:
            print(
                "[FrameDeck cache prune warning]",
                error,
            )

    def _logical_page_index_for_visible_index(
        self,
        visible_index,
    ):
        visible_index = int(
            visible_index
        )
        ranges = (
            self._computed_page_ranges()
        )

        for image_page_index, (
            start,
            end,
        ) in enumerate(
            ranges
        ):
            if (
                int(start)
                <= visible_index
                < int(end)
            ):
                return (
                    self._logical_page_index_for_image_page(
                        image_page_index
                    )
                )

        if ranges:
            return (
                self._logical_page_index_for_image_page(
                    max(
                        0,
                        len(ranges) - 1,
                    )
                )
            )

        return 0

    def _capture_page_lock_paths(
        self,
        visible_paths=None,
    ):
        """
        以图片路径捕获页面锁。

        跨组移动会改变可见索引，
        用路径恢复比按 +/- 索引更稳定。
        """
        visible = list(
            visible_paths
            if visible_paths is not None
            else self.visible_images()
        )
        captured = []

        for record in (
            self._normalize_lock_state()
        ):
            start = int(
                record.get(
                    "start",
                    0,
                )
            )
            end = int(
                record.get(
                    "end",
                    0,
                )
            )

            paths = visible[
                max(
                    0,
                    start,
                ):
                max(
                    0,
                    end,
                )
            ]

            if not paths:
                continue

            captured.append(
                {
                    "source": str(
                        record.get(
                            "source",
                            "page",
                        )
                    ),
                    "group_id": str(
                        record.get(
                            "group_id",
                            "",
                        )
                    ),
                    "paths": list(
                        paths
                    ),
                }
            )

        return captured

    def _restore_page_lock_paths(
        self,
        captured,
        visible_paths=None,
    ):
        visible = list(
            visible_paths
            if visible_paths is not None
            else self.visible_images()
        )
        index_by_path = {
            str(path): index
            for index, path in enumerate(
                visible
            )
        }

        restored = []

        for item in list(
            captured or []
        ):
            paths = [
                str(path)
                for path in item.get(
                    "paths",
                    [],
                )
                if str(path)
                in index_by_path
            ]

            if not paths:
                continue

            indices = sorted(
                index_by_path[path]
                for path in paths
            )

            # 锁定页中的图片应保持连续。
            # 如果未来某种操作把它们拆散，
            # 宁可取消该锁，也不建立跨页错误锁。
            if indices != list(
                range(
                    indices[0],
                    indices[-1] + 1,
                )
            ):
                continue

            restored.append(
                {
                    "source": str(
                        item.get(
                            "source",
                            "page",
                        )
                    ),
                    "group_id": str(
                        item.get(
                            "group_id",
                            "",
                        )
                    ),
                    "start": int(
                        indices[0]
                    ),
                    "end": int(
                        indices[-1] + 1
                    ),
                }
            )

        self._page_lock_records = (
            restored
        )
        self._normalize_lock_state()

    def _remap_breaks_after_internal_move(
        self,
        breaks,
        *,
        old_visible,
        new_visible,
        clear_ranges=None,
    ):
        """
        用“分页点右侧第一张图片”作为锚点，
        在列表内部重排后恢复分页点。

        clear_ranges：
            对跨组拖拽涉及的来源组/目标组，
            可主动清理软分页，让它们重新自动填满。
        """
        old_visible = list(
            old_visible
        )
        new_visible = list(
            new_visible
        )
        clear_ranges = list(
            clear_ranges or []
        )

        new_index = {
            str(path): index
            for index, path in enumerate(
                new_visible
            )
        }
        remapped = set()

        for raw_break in set(
            breaks or set()
        ):
            try:
                page_break = int(
                    raw_break
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if not (
                0
                < page_break
                < len(
                    old_visible
                )
            ):
                continue

            if any(
                int(start)
                < page_break
                <= int(end)
                for start, end
                in clear_ranges
            ):
                continue

            right_path = str(
                old_visible[
                    page_break
                ]
            )

            if right_path not in new_index:
                continue

            mapped = int(
                new_index[
                    right_path
                ]
            )

            if (
                0
                < mapped
                < len(
                    new_visible
                )
            ):
                remapped.add(
                    mapped
                )

        return remapped

    def _group_ranges_by_id(
        self,
    ):
        return {
            str(
                row["id"]
            ): (
                int(
                    row["start"]
                ),
                int(
                    row["end"]
                ),
            )
            for row in (
                self._group_manager_rows()
            )
        }

    def _rebuild_groups_from_image_membership(
        self,
        new_visible,
        membership_by_path,
        old_meta,
    ):
        """
        根据每张图片当前所属组重建分组边界。

        跨组拖入的图片会继承目标组ID；
        来源组如果被搬空，会自然消失。
        """
        new_groups = []
        previous_group_id = None

        for index, path in enumerate(
            list(
                new_visible
            )
        ):
            group_id = str(
                membership_by_path.get(
                    str(path),
                    "",
                )
                or ""
            )

            if not group_id:
                continue

            if (
                group_id
                == previous_group_id
            ):
                continue

            meta = dict(
                old_meta.get(
                    group_id,
                    {},
                )
            )
            meta["id"] = (
                group_id
            )
            meta["start"] = int(
                index
            )

            if not str(
                meta.get(
                    "name",
                    "",
                )
            ).strip():
                meta["name"] = (
                    f"分组 {len(new_groups) + 1:02d}"
                )

            new_groups.append(
                meta
            )
            previous_group_id = (
                group_id
            )

        self._image_groups = (
            normalize_groups(
                new_groups,
                len(
                    new_visible
                ),
            )
        )
        self._normalize_image_groups()

    def _internal_drop_target_group(
        self,
        *,
        selected_rows,
        insert_row,
        affinity,
        all_paths,
        old_visible,
        group_by_path,
    ):
        """
        解析目标组。

        交界处使用鼠标上/下半区区分：
        after  -> 优先前一个可见图片
        before -> 优先后一个可见图片
        """
        selected_set = set(
            int(row)
            for row in selected_rows
        )

        remaining_rows = [
            row
            for row in range(
                len(all_paths)
            )
            if row not in selected_set
        ]
        remaining_paths = [
            str(
                all_paths[row]
            )
            for row in remaining_rows
        ]

        adjusted_row = (
            int(insert_row)
            - sum(
                1
                for row in selected_set
                if row < int(
                    insert_row
                )
            )
        )
        adjusted_row = max(
            0,
            min(
                adjusted_row,
                len(
                    remaining_paths
                ),
            ),
        )

        visible_set = set(
            str(path)
            for path in old_visible
        )

        candidate = ""

        if str(
            affinity
        ) == "after":
            for index in range(
                adjusted_row - 1,
                -1,
                -1,
            ):
                path = str(
                    remaining_paths[
                        index
                    ]
                )

                if path in visible_set:
                    candidate = path
                    break

            if not candidate:
                for index in range(
                    adjusted_row,
                    len(
                        remaining_paths
                    ),
                ):
                    path = str(
                        remaining_paths[
                            index
                        ]
                    )

                    if path in visible_set:
                        candidate = path
                        break

        else:
            for index in range(
                adjusted_row,
                len(
                    remaining_paths
                ),
            ):
                path = str(
                    remaining_paths[
                        index
                    ]
                )

                if path in visible_set:
                    candidate = path
                    break

            if not candidate:
                for index in range(
                    adjusted_row - 1,
                    -1,
                    -1,
            ):
                    path = str(
                        remaining_paths[
                            index
                        ]
                    )

                    if path in visible_set:
                        candidate = path
                        break

        return (
            str(
                group_by_path.get(
                    candidate,
                    "",
                )
                or ""
            ),
            candidate,
            adjusted_row,
        )

    def _crosses_locked_group(
        self,
        source_group_ids,
        target_group_id,
    ):
        """
        如果跨组移动需要穿过一个锁定组，
        会改变该锁定组的逻辑页位置，因此拒绝。
        """
        rows = (
            self._group_manager_rows()
        )
        position_by_id = {
            str(
                row["id"]
            ): index
            for index, row in enumerate(
                rows
            )
        }

        if (
            target_group_id
            not in position_by_id
        ):
            return False

        target_pos = (
            position_by_id[
                target_group_id
            ]
        )

        for source_group_id in (
            source_group_ids
        ):
            if (
                source_group_id
                not in position_by_id
            ):
                continue

            source_pos = (
                position_by_id[
                    source_group_id
                ]
            )
            low = min(
                source_pos,
                target_pos,
            )
            high = max(
                source_pos,
                target_pos,
            )

            for row in rows[
                low:
                high + 1
            ]:
                group_id = str(
                    row["id"]
                )

                if (
                    group_id
                    in self._locked_group_ids
                ):
                    return True

        return False

    def handle_image_list_internal_drop(
        self,
        selected_rows,
        insert_row,
        *,
        affinity="before",
    ):
        """
        UI-05-43D：
        右侧图片列表支持真正的跨组拖拽。

        行为：
        - 同组：任意位置重新排序；
        - 跨组：拖入图片改归目标组；
        - 目标组未满页：自动填补空位；
        - 目标组满页：后续图片顺延；
        - 超过容量：自动形成新的页面；
        - 来源组图片数同步减少；
        - 分组名称/ID保持；
        - Undo/Redo可恢复。
        """
        selected_rows = sorted(
            {
                int(row)
                for row in list(
                    selected_rows or []
                )
                if (
                    0
                    <= int(row)
                    < self.image_list.count()
                )
            }
        )

        if not selected_rows:
            return False

        # UI-05-50: a drop in the center of an item is an explicit slot
        # swap.  Keep page boundaries and group ownership unchanged; this
        # avoids the old "linear order did not change" no-op at page edges.
        if str(affinity).lower() == "swap":
            return self._swap_image_list_slots(selected_rows, int(insert_row))

        search = getattr(
            self,
            "image_search",
            None,
        )

        if (
            search is not None
            and search.text().strip()
        ):
            QMessageBox.information(
                self,
                "图片拖动",
                (
                    "当前图片列表正在搜索筛选。\\n"
                    "请先清除搜索内容，再进行跨组拖拽。"
                ),
            )
            return False

        all_paths = [
            str(
                self.image_list.item(
                    row
                ).data(
                    Qt.ItemDataRole.UserRole
                )
                or ""
            )
            for row in range(
                self.image_list.count()
            )
        ]

        moved_paths = [
            str(
                all_paths[row]
            )
            for row in (
                selected_rows
            )
            if all_paths[row]
        ]

        if not moved_paths:
            return False

        if any(
            path
            in self.hidden_images
            for path in moved_paths
        ):
            QMessageBox.information(
                self,
                "图片拖动",
                (
                    "选中的图片中包含已隐藏素材。\\n"
                    "请先恢复显示，再执行跨组拖动。"
                ),
            )
            return False

        old_visible = list(
            self.visible_images()
        )

        if not old_visible:
            return False

        page_start_transfer_boundary = None
        if str(affinity).lower() == "before" and 0 <= int(insert_row) < len(all_paths):
            raw_target_path = str(all_paths[int(insert_row)])
            if raw_target_path in old_visible:
                raw_target_index = old_visible.index(raw_target_path)
                raw_target_page = self._logical_page_index_for_visible_index(
                    raw_target_index
                )
                raw_start, _raw_end = self._page_visible_range(raw_target_page)
                raw_start = int(raw_start)
                moved_visible_indices = [
                    old_visible.index(path)
                    for path in moved_paths
                    if path in old_visible
                ]
                moved_before_raw = sum(
                    1 for index in moved_visible_indices if index < raw_start
                )
                if (
                    raw_target_index == raw_start
                    and moved_before_raw > 0
                    and any(
                        self._logical_page_index_for_visible_index(index)
                        < raw_target_page
                        for index in moved_visible_indices
                    )
                ):
                    page_start_transfer_boundary = max(
                        1,
                        raw_start - moved_before_raw,
                    )

        old_groups = (
            self._normalize_image_groups()
        )
        old_meta = {
            str(
                item.get(
                    "id",
                    "",
                )
            ): dict(
                item
            )
            for item in old_groups
        }
        old_group_ranges = (
            self._group_ranges_by_id()
        )

        group_by_path = {
            str(path): str(
                self._group_id_for_visible_index(
                    index
                )
                or ""
            )
            for index, path in enumerate(
                old_visible
            )
        }

        # UI-05-46A disables user-facing groups in the stable continuous
        # layout.  The older drag transaction still expects a non-empty
        # membership id, so use an internal id for this calculation only.
        # _normalize_image_groups remains authoritative and keeps groups off.
        if not self._group_mode_enabled():
            group_by_path = {
                str(path): "__continuous_layout__"
                for path in old_visible
            }

        source_group_ids = {
            group_by_path.get(
                path,
                "",
            )
            for path in moved_paths
            if group_by_path.get(
                path,
                "",
            )
        }

        (
            target_group_id,
            target_neighbor_path,
            adjusted_row,
        ) = self._internal_drop_target_group(
            selected_rows=(
                selected_rows
            ),
            insert_row=int(
                insert_row
            ),
            affinity=str(
                affinity
            ),
            all_paths=all_paths,
            old_visible=old_visible,
            group_by_path=group_by_path,
        )

        # UI-05-45B：
        # 后页图片拖到前一未满页末尾空槽时，
        # 即使线性图片顺序没有变化，也必须消耗该页尾分页断点。
        fill_target_boundary = None
        fill_target_page_index = None

        try:
            selected_set_for_fill = {
                int(row)
                for row in selected_rows
            }
            remaining_for_fill = [
                str(path)
                for row, path in enumerate(
                    all_paths
                )
                if row not in selected_set_for_fill
            ]
            adjusted_for_fill = (
                int(insert_row)
                - sum(
                    1
                    for row in selected_set_for_fill
                    if row < int(insert_row)
                )
            )
            adjusted_for_fill = max(
                0,
                min(
                    adjusted_for_fill,
                    len(remaining_for_fill),
                ),
            )

            old_visible_set = {
                str(path)
                for path in old_visible
            }
            insertion_visible_index = sum(
                1
                for path in remaining_for_fill[:adjusted_for_fill]
                if str(path) in old_visible_set
            )

            old_index_for_fill = {
                str(path): index
                for index, path in enumerate(old_visible)
            }
            source_pages_for_fill = {
                self._logical_page_index_for_visible_index(
                    old_index_for_fill[path]
                )
                for path in moved_paths
                if path in old_index_for_fill
            }

            per_page = max(
                1,
                int(self.row_step.value())
                * int(self.col_step.value()),
            )
            page_count_for_fill = max(
                1,
                int(self.preview.page_count()),
            )

            for page_index in range(page_count_for_fill):
                page_start, page_end = self._page_visible_range(
                    page_index
                )
                page_start = int(page_start)
                page_end = int(page_end)
                page_used = max(0, page_end - page_start)

                if not (0 < page_used < per_page):
                    continue

                # 未满页的空槽在列表中的等价落点，就是该页 page_end。
                if int(insertion_visible_index) != page_end:
                    continue

                # 只处理“从后页往前页填空”，不干扰普通同页排序。
                if not any(
                    int(source_page) > int(page_index)
                    for source_page in source_pages_for_fill
                ):
                    continue

                fill_target_boundary = page_end
                fill_target_page_index = page_index
                adjusted_row = adjusted_for_fill

                # 边界处 affinity 可能把邻居识别成下一页。
                # 强制以未满页最后一张图作为真正目标页/组。
                if page_end > page_start:
                    target_neighbor_path = str(
                        old_visible[page_end - 1]
                    )
                    fill_group_id = str(
                        group_by_path.get(
                            target_neighbor_path,
                            "",
                        )
                        or ""
                    )
                    if fill_group_id:
                        target_group_id = fill_group_id

                break

        except Exception:
            # 兼容性异常时回退原拖拽逻辑，避免影响普通排序和启动。
            fill_target_boundary = None
            fill_target_page_index = None

        if not target_group_id:
            # 所有图片都被选中时，排序没有跨组意义；
            # 保持原组。
            if len(
                source_group_ids
            ) == 1:
                target_group_id = next(
                    iter(
                        source_group_ids
                    )
                )
            else:
                return False

        cross_group = any(
            group_id
            != target_group_id
            for group_id in (
                source_group_ids
            )
        )

        # 锁定组不允许收发图片。
        if (
            target_group_id
            in self._locked_group_ids
            or any(
                group_id
                in self._locked_group_ids
                for group_id in (
                    source_group_ids
                )
            )
            or (
                cross_group
                and self._crosses_locked_group(
                    source_group_ids,
                    target_group_id,
                )
            )
        ):
            QMessageBox.information(
                self,
                "分组已锁定",
                (
                    "本次拖动涉及已锁定分组。\\n"
                    "请先解锁相关分组，再移动图片。"
                ),
            )
            return False

        old_index_by_path = {
            str(path): index
            for index, path in enumerate(
                old_visible
            )
        }

        source_page_indices = {
            self._logical_page_index_for_visible_index(
                old_index_by_path[
                    path
                ]
            )
            for path in moved_paths
            if path
            in old_index_by_path
        }

        target_page_index = None

        if (
            target_neighbor_path
            and target_neighbor_path
            in old_index_by_path
        ):
            target_page_index = (
                self._logical_page_index_for_visible_index(
                    old_index_by_path[
                        target_neighbor_path
                    ]
                )
            )

        # 显式页面锁：
        # 同一锁定页内部排序允许；
        # 任何跨页收发都必须先解锁。
        locked_source_pages = {
            page_index
            for page_index in (
                source_page_indices
            )
            if self._page_lock_meta_for_logical_page(
                page_index
            )
        }
        target_locked = bool(
            target_page_index
            is not None
            and self._page_lock_meta_for_logical_page(
                target_page_index
            )
        )

        if (
            locked_source_pages
            or target_locked
        ):
            same_locked_page = bool(
                len(
                    source_page_indices
                )
                == 1
                and target_page_index
                in source_page_indices
                and not cross_group
            )

            if not same_locked_page:
                QMessageBox.information(
                    self,
                    "页面已锁定",
                    (
                        "本次拖动会改变已锁定页面的图片归属。\\n"
                        "请先解锁相关页面，再执行跨页/跨组拖动。"
                    ),
                )
                return False

        # 判断是否只是拖回原位置。
        selected_set = set(
            selected_rows
        )
        remaining_paths = [
            path
            for row, path in enumerate(
                all_paths
            )
            if row not in selected_set
        ]
        moving_paths_in_row_order = [
            all_paths[row]
            for row in selected_rows
        ]
        adjusted_row = max(
            0,
            min(
                int(
                    adjusted_row
                ),
                len(
                    remaining_paths
                ),
            ),
        )
        new_all_paths = (
            remaining_paths[
                :adjusted_row
            ]
            + moving_paths_in_row_order
            + remaining_paths[
                adjusted_row:
            ]
        )

        if (
            new_all_paths == all_paths
            and fill_target_boundary is None
            and page_start_transfer_boundary is None
        ):
            return True

        lock_capture = (
            self._capture_page_lock_paths(
                old_visible
            )
        )

        old_group_page_breaks = set(
            self._group_page_breaks
        )
        old_blank_fill_breaks = set(
            self._blank_fill_page_breaks
        )
        old_manual_breaks = set(
            self._manual_page_breaks
        )

        if fill_target_boundary is not None:
            # 用户主动填补前页空槽时，分页重新服从固定 rows × cols 容量。
            old_group_page_breaks.discard(
                int(fill_target_boundary)
            )
            old_blank_fill_breaks.discard(
                int(fill_target_boundary)
            )
            old_manual_breaks.discard(
                int(fill_target_boundary)
            )

        self.push_history(
            (
                "填充前页空位"
                if fill_target_boundary is not None
                else (
                    "跨组移动图片"
                    if cross_group
                    else "调整图片顺序"
                )
            )
        )

        # 把拖动图片明确归入目标组。
        membership_by_path = dict(
            group_by_path
        )

        for path in moved_paths:
            membership_by_path[
                path
            ] = target_group_id

        list_was_blocked = (
            self.image_list.blockSignals(
                True
            )
        )
        model = (
            self.image_list.model()
        )
        model_was_blocked = (
            model.blockSignals(
                True
            )
        )

        try:
            items = [
                self.image_list.takeItem(
                    0
                )
                for _ in range(
                    self.image_list.count()
                )
            ]

            item_by_path = {
                str(
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                    or ""
                ): item
                for item in items
                if item is not None
            }

            for path in new_all_paths:
                item = (
                    item_by_path.get(
                        str(path)
                    )
                )

                if item is not None:
                    self.image_list.addItem(
                        item
                    )

            self.image_list.clearSelection()

            first_moved_row = -1

            for path in moved_paths:
                item = (
                    item_by_path.get(
                        str(path)
                    )
                )

                if item is None:
                    continue

                row = self.image_list.row(
                    item
                )

                if row >= 0:
                    item.setSelected(
                        True
                    )

                    if first_moved_row < 0:
                        first_moved_row = (
                            row
                        )

            if first_moved_row >= 0:
                self.image_list.setCurrentRow(
                    first_moved_row
                )

        finally:
            model.blockSignals(
                model_was_blocked
            )
            self.image_list.blockSignals(
                list_was_blocked
            )

        new_visible = list(
            self.visible_images()
        )

        self._rebuild_groups_from_image_membership(
            new_visible,
            membership_by_path,
            old_meta,
        )

        affected_group_ids = set(
            source_group_ids
        )
        affected_group_ids.add(
            target_group_id
        )

        clear_ranges = [
            old_group_ranges[
                group_id
            ]
            for group_id in (
                affected_group_ids
            )
            if group_id
            in old_group_ranges
        ]

        # 跨组拖拽视为用户主动重新排版来源组/目标组：
        # 这两个组内旧的“软分页空槽”清理，
        # 从而能真正填满空位并在满页后自然续页。
        self._group_page_breaks = (
            self._remap_breaks_after_internal_move(
                old_group_page_breaks,
                old_visible=old_visible,
                new_visible=new_visible,
                clear_ranges=(
                    clear_ranges
                    if cross_group
                    else []
                ),
            )
        )
        self._blank_fill_page_breaks = (
            self._remap_breaks_after_internal_move(
                old_blank_fill_breaks,
                old_visible=old_visible,
                new_visible=new_visible,
                clear_ranges=(
                    clear_ranges
                    if cross_group
                    else []
                ),
            )
        )
        self._manual_page_breaks = (
            self._remap_breaks_after_internal_move(
                old_manual_breaks,
                old_visible=old_visible,
                new_visible=new_visible,
                clear_ranges=[],
            )
        )

        if page_start_transfer_boundary is not None:
            self._blank_fill_page_breaks.add(
                int(page_start_transfer_boundary)
            )
            self._normalize_blank_fill_page_breaks(
                len(new_visible)
            )

        self._restore_page_lock_paths(
            lock_capture,
            new_visible,
        )

        # 如果某个来源组被完全搬空，自动清理其标题/样式/锁ID。
        self._normalize_image_groups()
        valid_group_ids = {
            str(
                item.get(
                    "id",
                    "",
                )
            )
            for item in (
                self._image_groups
            )
        }
        self._locked_group_ids = {
            group_id
            for group_id in (
                self._locked_group_ids
            )
            if group_id
            in valid_group_ids
        }
        self._title_system = (
            normalize_title_system(
                self._title_system,
                group_ids=list(
                    valid_group_ids
                ),
            )
        )

        # 重新选择被移动图片。
        selected_visible_indices = {
            index
            for index, path in enumerate(
                new_visible
            )
            if path in set(
                moved_paths
            )
        }
        self.selected_image_indices = (
            selected_visible_indices
        )
        self.selected_image_index = (
            min(
                selected_visible_indices
            )
            if selected_visible_indices
            else -1
        )

        if self.selected_image_index >= 0:
            target_logical_page = (
                self._logical_page_index_for_visible_index(
                    self.selected_image_index
                )
            )
            self._displayed_page_index = (
                target_logical_page
            )
            self.preview.set_page_index(
                target_logical_page
            )

        self.refresh_image_list_appearance()
        self._update_group_ui_state()
        self._update_lock_ui_state()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if self.selected_image_index >= 0:
            self.preview.set_selected_index(
                self.selected_image_index,
                reveal=False,
            )

        if hasattr(
            self,
            "status_bar",
        ):
            target_row = (
                self._group_manager_row_by_id(
                    target_group_id
                )
            )
            target_name = (
                target_row["name"]
                if target_row
                else "目标分组"
            )

            if cross_group:
                self._show_status(
                    (
                        f"已移动 {len(moved_paths)} 张图片到"
                        f"“{target_name}”"
                        " · 空位优先填充，满页后自动续页"
                    ),
                    4200,
                )
            else:
                self._show_status(
                    (
                        f"已调整 {len(moved_paths)} 张图片顺序"
                    ),
                    2600,
                )

        return True

    def _swap_image_list_slots(self, selected_rows, target_row):
        """Swap one or more selected list items with a target slot."""
        rows = sorted({int(row) for row in list(selected_rows or [])})
        if len(rows) != 1 or not (0 <= rows[0] < self.image_list.count()):
            return False
        target_row = int(target_row)
        if not (0 <= target_row < self.image_list.count()) or target_row == rows[0]:
            return True
        source_item = self.image_list.item(rows[0])
        target_item = self.image_list.item(target_row)
        if source_item is None or target_item is None:
            return False
        source_path = str(source_item.data(Qt.ItemDataRole.UserRole) or "")
        target_path = str(target_item.data(Qt.ItemDataRole.UserRole) or "")
        if not source_path or not target_path:
            return False
        visible = list(self.visible_images())
        try:
            source_visible = visible.index(source_path)
            target_visible = visible.index(target_path)
        except ValueError:
            return False
        old_groups = self._normalize_image_groups()
        old_meta = {
            str(row.get("id", "")): dict(row)
            for row in old_groups
        }
        membership = {
            path: str(self._group_id_for_visible_index(index) or "")
            for index, path in enumerate(visible)
        }
        source_group_id = membership.get(source_path, "")
        target_group_id = membership.get(target_path, "")
        source_page = self._logical_page_index_for_visible_index(source_visible)
        target_page = self._logical_page_index_for_visible_index(target_visible)
        if source_page != target_page:
            if self._page_lock_meta_for_logical_page(source_page) or self._page_lock_meta_for_logical_page(target_page):
                self._show_status("涉及已锁定页面，请先解锁后交换图片", 2600)
                return False
            if self._is_logical_page_in_locked_group(source_page) or self._is_logical_page_in_locked_group(target_page):
                self._show_status("涉及已锁定分组，请先解锁后交换图片", 2600)
                return False
        if source_group_id in self._locked_group_ids or target_group_id in self._locked_group_ids:
            self._show_status("涉及已锁定分组，请先解锁后交换图片", 2600)
            return False
        self.push_history("交换图片位置")
        list_blocked = self.image_list.blockSignals(True)
        model = self.image_list.model()
        model_blocked = model.blockSignals(True)
        try:
            items = [self.image_list.takeItem(0) for _ in range(self.image_list.count())]
            items[rows[0]], items[target_row] = items[target_row], items[rows[0]]
            for item in items:
                self.image_list.addItem(item)
            self.image_list.clearSelection()
            moved = self.image_list.item(target_row)
            if moved is not None:
                moved.setSelected(True)
                self.image_list.setCurrentItem(moved)
        finally:
            model.blockSignals(model_blocked)
            self.image_list.blockSignals(list_blocked)
        new_visible = list(self.visible_images())
        if source_group_id != target_group_id:
            membership[source_path] = target_group_id
            membership[target_path] = source_group_id
            self._rebuild_groups_from_image_membership(
                new_visible,
                membership,
                old_meta,
            )
            self._normalize_image_groups()
        self.selected_image_indices = {new_visible.index(source_path)} if source_path in new_visible else set()
        self.selected_image_index = min(self.selected_image_indices) if self.selected_image_indices else -1
        self._force_page_thumbnail_refresh()
        self.refresh_preview()
        self.refresh_image_list_appearance()
        self._update_group_ui_state()
        self._update_lock_ui_state()
        self._show_status("图片已交换位置", 2200)
        return True


    def _create_external_image_item(self, path):
        item = QListWidgetItem(Path(path).name)
        item.setData(
            Qt.ItemDataRole.UserRole,
            str(path),
        )
        item.setSizeHint(
            QSize(
                0,
                self._image_list_metrics()[2],
            )
        )

        # 先创建列表项，缩略图随后按时间片加载。
        self._queue_image_thumbnail(
            item,
            str(path),
        )

        return item

    def _visible_target_to_list_row(self, target_index):
        """
        把中央画布的“可见图片索引”转换为右侧完整列表行号。
        """
        visible = self.visible_images()
        target_index = max(
            0,
            min(int(target_index), len(visible)),
        )

        if target_index >= len(visible):
            return self.image_list.count()

        target_path = visible[target_index]

        for row in range(self.image_list.count()):
            item = self.image_list.item(row)
            if (
                item.data(Qt.ItemDataRole.UserRole)
                == target_path
            ):
                return row

        return self.image_list.count()

    def _insert_external_images(
        self,
        paths,
        insert_row,
        history_label,
        consume_compat_blank_page=False,
        *,
        start_new_group=False,
        new_group_name="",
        boundary_belongs_to_previous=False,
        replace_blank_page_index=None,
    ):
        """
        外部图片统一插入入口。

        数据只在 dropEvent 调用此方法时改变。
        """
        if not paths:
            self._rearm_external_drop_surfaces()
            return 0

        existing = {
            os.path.normcase(
                os.path.abspath(str(path))
            )
            for path in self.ordered_images()
        }
        valid_paths = []
        seen = set()
        duplicate_instance_count = 0
        duplicate_copy_errors = []

        decodable_paths = (
            self._filter_decodable_image_paths(
                paths,
                notify=True,
            )
        )

        for path in decodable_paths:
            source_path = str(path)
            normalized = os.path.normcase(
                os.path.abspath(
                    source_path
                )
            )

            # UI-05-42A FIX01：
            # 相同图片允许再次加入，但不能直接使用相同path作为两个实例，
            # 否则两份图片会共享裁切/缩放/隐藏等状态。
            #
            # 当源图片已经存在于工程，或同一次拖入出现重复路径时，
            # 自动创建独立副本，再作为新的图片实例加入。
            if (
                normalized in existing
                or normalized in seen
            ):
                try:
                    duplicate_path = (
                        self._unique_copy_path(
                            source_path
                        )
                    )
                    shutil.copy2(
                        source_path,
                        duplicate_path,
                    )
                    source_path = str(
                        duplicate_path
                    )
                    duplicate_instance_count += 1

                    if hasattr(
                        self,
                        "log_box",
                    ):
                        self.log_box.append(
                            (
                                "重复图片已作为独立素材加入："
                                f"{Path(path).name} → "
                                f"{Path(source_path).name}"
                            )
                        )

                except Exception as error:
                    duplicate_copy_errors.append(
                        (
                            f"{Path(path).name}: "
                            f"{error}"
                        )
                    )
                    continue

            final_normalized = os.path.normcase(
                os.path.abspath(
                    source_path
                )
            )
            seen.add(
                normalized
            )
            existing.add(
                final_normalized
            )
            valid_paths.append(
                source_path
            )

        if not valid_paths:
            if hasattr(
                self,
                "status_bar",
            ):
                self._show_status(
                    (
                        "没有可加入的图片"
                        if not duplicate_copy_errors
                        else "重复图片副本创建失败"
                    ),
                    3000,
                )

            if (
                duplicate_copy_errors
                and hasattr(
                    self,
                    "log_box",
                )
            ):
                for error in (
                    duplicate_copy_errors[:10]
                ):
                    self.log_box.append(
                        "重复图片加入失败："
                        + error
                    )

            self._rearm_external_drop_surfaces()
            return 0

        blank_replace_index = (
            int(replace_blank_page_index)
            if replace_blank_page_index
            is not None
            else None
        )

        if (
            blank_replace_index is not None
            and self._is_blank_page(
                blank_replace_index
            )
        ):
            visible_blank_insert_index = (
                self._blank_page_visible_insertion_index(
                    blank_replace_index
                )
            )

            if visible_blank_insert_index is not None:
                insert_row = (
                    self._list_row_for_visible_insertion(
                        visible_blank_insert_index
                    )
                )

        insert_row = max(
            0,
            min(int(insert_row), self.image_list.count()),
        )
        current_page = max(
            0,
            int(
                getattr(
                    self,
                    "_displayed_page_index",
                    self.preview.current_page(),
                )
            ),
        )

        self.push_history(history_label)

        first_row = insert_row
        visible_insert_index = (
            self._visible_index_before_list_row(
                insert_row
            )
        )
        image_count_before = len(
            self.visible_images()
        )

        self._shift_page_breaks_for_insert(
            visible_insert_index,
            len(valid_paths),
            keep_break_at_index=(
                not boundary_belongs_to_previous
            ),
        )
        self._shift_image_groups_for_insert(
            visible_insert_index,
            len(valid_paths),
            boundary_belongs_to_previous=(
                boundary_belongs_to_previous
            ),
            create_new_group=bool(
                start_new_group
                and self._group_mode_enabled()
            ),
            new_group_name=new_group_name,
            image_count_before=image_count_before,
        )
        self._shift_group_page_breaks_for_insert(
            visible_insert_index,
            len(valid_paths),
            keep_break_at_index=(
                not boundary_belongs_to_previous
            ),
        )
        self._shift_blank_fill_page_breaks_for_insert(
            visible_insert_index,
            len(valid_paths),
            keep_break_at_index=(
                not boundary_belongs_to_previous
            ),
        )
        self._shift_page_lock_records_for_insert(
            visible_insert_index,
            len(valid_paths),
            boundary_belongs_to_previous=(
                boundary_belongs_to_previous
            ),
        )

        for offset, path in enumerate(valid_paths):
            item = self._create_external_image_item(path)
            self.image_list.insertItem(
                insert_row + offset,
                item,
            )
            self.image_transforms[path] = self.get_transform(path)

        blank_was_replaced = bool(
            blank_replace_index is not None
            and self._is_blank_page(
                blank_replace_index
            )
        )

        if blank_was_replaced:
            image_count_after = (
                image_count_before
                + len(valid_paths)
            )
            segment_start = (
                visible_insert_index
            )
            segment_end = (
                visible_insert_index
                + len(valid_paths)
            )

            if 0 < segment_start < image_count_after:
                self._blank_fill_page_breaks.add(
                    segment_start
                )

            if 0 < segment_end < image_count_after:
                self._blank_fill_page_breaks.add(
                    segment_end
                )

            self._consume_blank_page_for_images(
                blank_replace_index,
                len(valid_paths),
            )

        if (
            consume_compat_blank_page
            and self._compat_blank_page_count() > 0
        ):
            self._set_compat_blank_page_count(
                self._compat_blank_page_count() - 1
            )

        self.selected_image_index = -1
        self._displayed_page_index = (
            blank_replace_index
            if blank_was_replaced
            else current_page
        )

        self.refresh_image_list_appearance()
        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        # 导入完成后再选中新图片；拖动过程中不会提前改变选择。
        if self.image_list.count() > first_row:
            self.image_list.setCurrentRow(first_row)

        if hasattr(self, "status_bar"):
            message = (
                (
                    f"已填充第 {blank_replace_index + 1} 页空白页"
                    f" · {len(valid_paths)} 张图片"
                )
                if blank_was_replaced
                else f"已插入 {len(valid_paths)} 张图片"
            )

            if duplicate_instance_count:
                message += (
                    f" · {duplicate_instance_count} 张"
                    "重复素材已建立独立副本"
                )

            self._show_status(
                message,
                3500,
            )

        if (
            duplicate_copy_errors
            and hasattr(
                self,
                "log_box",
            )
        ):
            for error in (
                duplicate_copy_errors[:10]
            ):
                self.log_box.append(
                    "重复图片加入失败："
                    + error
                )

        self._rearm_external_drop_surfaces()

        # refresh_preview之后再恢复一次，防止Qt在当前drop事件
        # 完成阶段重新写回旧的内部拖放状态。
        QTimer.singleShot(
            0,
            self._rearm_external_drop_surfaces,
        )

        return len(valid_paths)

    def handle_canvas_multi_drop(self, paths, target_index=-1):
        """
        外部图片拖入中央画布指定区域。

        target_index < 0 时直接取消，
        不再自动追加到图片列表末尾。
        """
        if not paths or target_index < 0:
            return

        current_page = (
            self._current_logical_page_index()
        )
        replace_blank_page_index = (
            current_page
            if self._is_blank_page(
                current_page
            )
            else None
        )
        consume_blank = False

        if replace_blank_page_index is not None:
            blank_visible_index = (
                self._blank_page_visible_insertion_index(
                    replace_blank_page_index
                )
            )
            insert_row = (
                self._list_row_for_visible_insertion(
                    blank_visible_index
                    if blank_visible_index
                    is not None
                    else len(
                        self.visible_images()
                    )
                )
            )
        else:
            insert_row = self._visible_target_to_list_row(
                target_index
            )

        page_start, page_end = (
            self._page_visible_range(
                current_page
            )
        )
        boundary_belongs_to_previous = bool(
            target_index == page_end
            and (
                page_end - page_start
                < self._page_capacity()
            )
            and (
                (
                    self._group_mode_enabled()
                    and (
                        page_end
                        in self._group_breaks()
                        or page_end
                        in self._normalize_group_page_breaks()
                    )
                )
                or page_end
                in self._normalize_blank_fill_page_breaks()
            )
        )

        inserted = self._insert_external_images(
            paths,
            insert_row,
            "画布指定区域插入图片",
            consume_compat_blank_page=consume_blank,
            boundary_belongs_to_previous=(
                boundary_belongs_to_previous
            ),
            replace_blank_page_index=(
                replace_blank_page_index
            ),
        )
        self._rearm_external_drop_surfaces()
        return inserted

    def _rearm_external_drop_surfaces(self):
        """
        恢复右侧图片列表和中央画布的外部文件拖入能力。
        """
        image_list = getattr(
            self,
            "image_list",
            None,
        )

        if image_list is not None:
            if hasattr(
                image_list,
                "_restore_drop_ready_state",
            ):
                image_list._restore_drop_ready_state()
            else:
                image_list.setAcceptDrops(True)
                image_list.viewport().setAcceptDrops(
                    True
                )

        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is not None:
            if hasattr(
                preview,
                "rearm_external_drop",
            ):
                preview.rearm_external_drop()
            else:
                preview.setAcceptDrops(True)

    def handle_image_list_external_drop(
        self,
        paths,
        insert_row=None,
    ):
        """
        外部图片拖入右侧列表。

        鼠标所在位置决定插入行；
        拖到列表空白区域则插入末尾。
        """
        if insert_row is None:
            insert_row = self.image_list.count()

        inserted = self._insert_external_images(
            paths,
            insert_row,
            "右侧图片列表拖入图片",
            consume_compat_blank_page=False,
        )
        self._rearm_external_drop_surfaces()
        return inserted


    def load_images(self):
        folder = self.folder_edit.text().strip()
        paths = []

        if folder and os.path.isdir(folder):
            candidates = natsorted(
                str(p)
                for p in Path(folder).iterdir()
                if (
                    p.is_file()
                    and not self._is_hidden_or_system_import_file(
                        p
                    )
                    and is_supported_media_path(
                        p
                    )
                )
            )
            paths = (
                self._filter_decodable_image_paths(
                    candidates,
                    notify=True,
                )
            )

        # =====================================================
        # UI-05-01-02
        # Image change sync
        # =====================================================

        try:

            self.refresh_slide_thumbnail()


        except Exception as e:


            print(
                "[UI-05 sync warning]",
                e
            )

        self._set_blank_page_positions([])
        self._manual_page_breaks = set()
        self._image_groups = []
        self._group_page_breaks = set()
        self._blank_fill_page_breaks = set()
        self._page_lock_records = []
        self._locked_group_ids = set()
        self._title_system = default_title_system()
        self._confirmed_auto_layout = False
        self._auto_layout_restore_state = None
        self._auto_layout_undo_depth = None
        self._set_pagination_mode(
            PAGINATION_GROUPED,
            refresh=False,
        )

        self._reset_image_thumbnail_queue()
        self.image_list.clear()

        for path in paths:
            self.image_list.addItem(
                self._create_external_image_item(
                    path
                )
            )
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.image_transforms = {
            path: self.get_transform(path)
            for path in paths
        }
        self.hidden_images = {path for path in self.hidden_images if path in paths}
        self.selected_image_index = -1
        self.selected_name_label.setText("未选择图片")
        self.set_transform_controls_enabled(False)
        self.refresh_image_list_appearance()
        self.preview.set_page_index(0)
        self.refresh_preview()

    # =====================================================
    # UI-05-32A Multi-format export
    # =====================================================

    def _normalized_export_format(self, export_format):
        value = str(
            export_format
            or self._selected_export_format
            or "pptx"
        ).lower()

        if value not in {"pptx", "pdf", "images"}:
            value = "pptx"

        return value

    def _export_format_label(self, export_format):
        return {
            "pptx": "PPT",
            "pdf": "PDF",
            "images": "页面图片",
        }.get(export_format, "PPT")

    def _set_export_format(self, export_format):
        export_format = self._normalized_export_format(
            export_format
        )
        self._selected_export_format = export_format

    def _safe_export_base_name(self):
        """
        自动生成PPT/PDF/页面图片的基础名称。

        优先级：
        1. 当前已保存工程文件名；
        2. 第一张图片所在文件夹名称；
        3. FrameDeck_Export。
        """
        if self.current_project_file:
            base_name = Path(
                self.current_project_file
            ).stem
        else:
            images = self.ordered_images()

            if images:
                base_name = (
                    Path(images[0]).parent.name
                    or Path(images[0]).stem
                )
            else:
                base_name = "FrameDeck_Export"

        base_name = re.sub(
            r'[<>:"/\\|?*]+',
            "_",
            str(base_name),
        )
        base_name = base_name.strip(
            " ._"
        )

        return (
            base_name
            or "FrameDeck_Export"
        )

    def _export_directory_hint(self):
        current = (
            self._last_export_directory
            or self.output_edit.text().strip()
        )

        if current:
            path = Path(current)

            if path.suffix:
                path = path.parent

            if str(path).strip():
                return path

        if self.current_project_file:
            return Path(
                self.current_project_file
            ).parent

        images = self.ordered_images()

        if images:
            return Path(
                images[0]
            ).parent

        return Path.cwd()

    def _select_export_directory(
        self,
        export_format,
    ):
        export_format = (
            self._normalized_export_format(
                export_format
            )
        )
        label = self._export_format_label(
            export_format
        )
        suggested = (
            self._export_directory_hint()
        )

        folder = QFileDialog.getExistingDirectory(
            self,
            self._translated_export_folder_title(label),
            str(suggested),
        )

        if not folder:
            return ""

        self._last_export_directory = str(
            folder
        )

        # 隐藏字段仅用于配置兼容和“打开输出文件夹”功能。
        self.output_edit.setText(
            str(folder)
        )
        self.save_config()

        return str(folder)

    def _output_path_in_directory(
        self,
        export_format,
        export_directory,
    ):
        export_format = (
            self._normalized_export_format(
                export_format
            )
        )
        export_directory = Path(
            export_directory
        )
        base_name = (
            self._safe_export_base_name()
        )

        if export_format == "pptx":
            return (
                export_directory
                / f"{base_name}.pptx"
            )

        if export_format == "pdf":
            return (
                export_directory
                / f"{base_name}.pdf"
            )

        return (
            export_directory
            / f"{base_name}_页面图片"
        )

    def _default_export_base_path(self):
        return self._output_path_in_directory(
            self._selected_export_format,
            self._export_directory_hint(),
        )

    def _derived_output_path(self, export_format):
        return self._output_path_in_directory(
            export_format,
            self._export_directory_hint(),
        )

    def select_output(self):
        """
        兼容旧入口：现在统一选择输出文件夹，而不是输入文件路径。
        """
        return self._select_export_directory(
            self._selected_export_format
        )

    def _prepare_output_path(
        self,
        export_format,
        export_directory=None,
    ):
        if not export_directory:
            export_directory = (
                self._export_directory_hint()
            )

        output = self._output_path_in_directory(
            export_format,
            export_directory,
        )
        return output

    def start_generate(self, export_format="pptx"):
        export_format = self._normalized_export_format(
            export_format
        )
        self._set_export_format(export_format)

        settings = self.generation_settings()

        if not settings["image_paths"]:
            QMessageBox.warning(
                self,
                "无法生成",
                "请先添加图片。",
            )
            return

        if not self.visible_images():
            QMessageBox.warning(
                self,
                "无法生成",
                "所有图片都已隐藏，请先恢复至少一张图片。",
            )
            return

        export_directory = (
            self._select_export_directory(
                export_format
            )
        )

        if not export_directory:
            return

        output = self._prepare_output_path(
            export_format,
            export_directory,
        )

        if export_format == "images":
            old_pages = (
                list(output.glob("page_*.png"))
                if output.exists() and output.is_dir()
                else []
            )

            if old_pages:
                result = QMessageBox.question(
                    self,
                    "覆盖图片",
                    (
                        f"{output.name} 中已有 "
                        f"{len(old_pages)} 张页面图片，"
                        "是否覆盖？"
                    ),
                )

                if result != QMessageBox.StandardButton.Yes:
                    return

        elif output.exists():
            result = QMessageBox.question(
                self,
                "覆盖文件",
                f"{output.name} 已存在，是否覆盖？",
            )

            if result != QMessageBox.StandardButton.Yes:
                return

        if export_format == "pptx":
            settings["output_file"] = str(output)
            self._start_ppt_export(settings)
        else:
            self._start_raster_export(
                export_format,
                output,
            )

    def _preflight_ppt_export_path(
        self,
        output_file,
    ):
        """
        在生成几十页PPT之前检查目标文件是否可写。

        目标PPT正被WPS/PowerPoint打开时，立即提示，
        避免完成全部页面后才在最终保存阶段失败。
        """
        try:
            preflight_ppt_output(
                output_file
            )
            return True

        except PermissionError as error:
            QMessageBox.warning(
                self,
                "PPT文件正在使用或无法写入",
                str(error),
            )

            if hasattr(
                self,
                "log_box",
            ):
                self.log_box.append(
                    str(error)
                )
                self.log_dock.show()
                self.log_dock.raise_()

            return False

        except Exception as error:
            QMessageBox.critical(
                self,
                "输出路径检查失败",
                str(error),
            )
            return False

    def _start_ppt_export(self, settings):
        output_file = str(
            settings.get(
                "output_file",
                "",
            )
        ).strip()

        if not self._preflight_ppt_export_path(
            output_file
        ):
            return

        self.progress.setValue(0)
        self.log_box.clear()
        self.log_box.append(
            "已确认当前预览与图片顺序，开始生成 PPT..."
        )
        self.start_btn.setEnabled(False)

        self.worker = PPTWorker(settings)
        self.worker.progress.connect(
            self.progress.setValue
        )
        self.worker.log.connect(
            self.log_box.append
        )
        self.worker.finished_ok.connect(
            lambda output: self.on_finished(
                output,
                "pptx",
            )
        )
        self.worker.failed.connect(
            self.on_failed
        )
        self.worker.start()

    def _preview_slide_logical_rect(self):
        settings = self.preview_settings()
        page_name = settings.get("page_size", "16:9")
        slide_w, slide_h = PAGE_SIZES.get(
            page_name,
            PAGE_SIZES["16:9"],
        )
        ratio = float(slide_w) / float(slide_h)

        widget_rect = self.preview.rect()
        outer = widget_rect.adjusted(30, 26, -30, -26)
        zoom = float(
            getattr(self.preview, "_zoom", 1.0)
        )
        max_w = max(1.0, outer.width() * zoom)
        max_h = max(1.0, outer.height() * zoom)

        if max_w / max_h > ratio:
            height = max_h
            width = height * ratio
        else:
            width = max_w
            height = width / ratio

        return QRectF(
            widget_rect.center().x() - width / 2,
            widget_rect.center().y() - height / 2,
            width,
            height,
        )

    def _raster_export_pixel_size(self):
        page_name = self.preview_settings().get(
            "page_size",
            "16:9",
        )
        slide_w_cm, slide_h_cm = PAGE_SIZES.get(
            page_name,
            PAGE_SIZES["16:9"],
        )

        width_px = max(
            1,
            round(
                slide_w_cm
                / 2.54
                * self._raster_export_dpi
            ),
        )
        height_px = max(
            1,
            round(
                slide_h_cm
                / 2.54
                * self._raster_export_dpi
            ),
        )

        long_edge = max(
            width_px,
            height_px,
        )

        if long_edge > self._raster_export_max_long_edge:
            ratio = (
                self._raster_export_max_long_edge
                / long_edge
            )
            width_px = max(
                1,
                round(width_px * ratio),
            )
            height_px = max(
                1,
                round(height_px * ratio),
            )

        return width_px, height_px

    def _capture_export_page(
        self,
        page_index,
        target_long_edge=None,
    ):
        self.preview.set_page_index(int(page_index))
        self.preview.repaint()
        QApplication.processEvents()

        slide_rect = self._preview_slide_logical_rect()
        export_width, export_height = (
            self._raster_export_pixel_size()
        )

        if target_long_edge:
            requested_long_edge = max(
                1,
                int(target_long_edge),
            )
        else:
            requested_long_edge = max(
                export_width,
                export_height,
            )

        logical_long_edge = max(
            slide_rect.width(),
            slide_rect.height(),
        )

        # 旧版限制为 5 倍，较小窗口无法真正生成 450 DPI。
        # 新版按目标像素精确放大，最高允许 14 倍。
        scale = min(
            14.0,
            max(
                1.0,
                float(requested_long_edge)
                / max(
                    1.0,
                    logical_long_edge,
                ),
            ),
        )

        rendered = QImage(
            max(1, round(self.preview.width() * scale)),
            max(1, round(self.preview.height() * scale)),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        rendered.fill(
            QColor(
                THEME_META[
                    self.current_theme_name()
                ]["window"]
            )
        )

        painter = QPainter(rendered)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )
        painter.scale(scale, scale)

        try:
            # PySide6 的 QWidget.render(QPainter, ...) 重载要求显式传入
            # targetOffset；只传 QPainter 会触发参数类型错误。
            self.preview.render(
                painter,
                QPoint(0, 0),
            )
        finally:
            painter.end()

        crop_rect = QRect(
            max(0, round(slide_rect.left() * scale)),
            max(0, round(slide_rect.top() * scale)),
            max(1, round(slide_rect.width() * scale)),
            max(1, round(slide_rect.height() * scale)),
        ).intersected(rendered.rect())

        page_image = rendered.copy(
            crop_rect
        ).convertToFormat(
            QImage.Format.Format_RGB32
        )

        # 保证最终像素尺寸严格匹配页面DPI目标。
        if (
            page_image.width() != export_width
            or page_image.height() != export_height
        ):
            page_image = page_image.scaled(
                export_width,
                export_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        return page_image

    def _capture_all_export_pages(
        self,
        output_directory,
    ):
        output_directory = Path(output_directory)
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            hasattr(self.preview, "is_crop_mode")
            and self.preview.is_crop_mode()
        ):
            self.preview.confirm_crop_mode()

        page_count = max(
            1,
            int(self.preview.page_count()),
        )
        original_page = int(
            self.preview.current_page()
        )
        original_zoom = float(
            getattr(self.preview, "_zoom", 1.0)
        )
        original_selected = int(
            self.selected_image_index
        )
        original_selected_indices = sorted(
            self.selected_image_indices
        )
        original_quality_override = (
            self.preview.render_quality_override()
            if hasattr(
                self.preview,
                "render_quality_override",
            )
            else 0
        )

        page_paths = []

        try:
            self.preview.set_zoom(1.0)

            if hasattr(
                self.preview,
                "set_render_quality_override",
            ):
                self.preview.set_render_quality_override(
                    self._export_source_long_edge
                )

            if hasattr(
                self.preview,
                "set_selected_indices",
            ):
                self.preview.set_selected_indices(
                    [],
                    -1,
                    reveal=False,
                )
            else:
                self.preview.set_selected_index(
                    -1,
                    reveal=False,
                )

            for page_index in range(page_count):
                self.log_box.append(
                    f"正在渲染第 {page_index + 1}/{page_count} 页"
                )

                page_image = self._capture_export_page(
                    page_index
                )
                page_path = (
                    output_directory
                    / f"page_{page_index + 1:03d}.png"
                )

                if not page_image.save(
                    str(page_path),
                    "PNG",
                    100,
                ):
                    raise RuntimeError(
                        f"无法保存页面图片：{page_path}"
                    )

                page_paths.append(page_path)
                self.progress.setValue(
                    round(
                        (page_index + 1)
                        / page_count
                        * 90
                    )
                )
                QApplication.processEvents()

        finally:
            if hasattr(
                self.preview,
                "set_render_quality_override",
            ):
                self.preview.set_render_quality_override(
                    original_quality_override
                )

            self.preview.set_zoom(original_zoom)
            self.preview.set_page_index(original_page)

            if hasattr(
                self.preview,
                "set_selected_indices",
            ):
                self.preview.set_selected_indices(
                    original_selected_indices,
                    original_selected,
                    reveal=False,
                )
            else:
                self.preview.set_selected_index(
                    original_selected,
                    reveal=False,
                )

            self.preview.update()
            self._displayed_page_index = original_page

            if self.slide_thumbnail_bar is not None:
                self.slide_thumbnail_bar.set_current_page(
                    original_page
                )

        return page_paths

    def _write_pdf_from_png_pages(
        self,
        page_paths,
        output_file,
    ):
        pages = []

        try:
            for path in page_paths:
                with Image.open(path) as opened:
                    pages.append(
                        opened.convert("RGB").copy()
                    )

            if not pages:
                raise RuntimeError(
                    "没有可用于生成 PDF 的页面。"
                )

            output_file = Path(output_file)
            output_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            page_name = self.preview_settings().get(
                "page_size",
                "16:9",
            )
            slide_width_cm = PAGE_SIZES.get(
                page_name,
                PAGE_SIZES["16:9"],
            )[0]
            resolution = max(
                72.0,
                pages[0].width
                / max(1.0, slide_width_cm / 2.54),
            )

            first_page, *remaining_pages = pages
            # Pillow 的PDF编码对RGB页面通常使用JPEG。
            # 显式使用最高质量并关闭色度抽样，避免文字和细节发糊。
            first_page.save(
                output_file,
                "PDF",
                resolution=resolution,
                save_all=True,
                append_images=remaining_pages,
                quality=100,
                subsampling=0,
                optimize=False,
            )

        finally:
            for page in pages:
                try:
                    page.close()
                except Exception:
                    pass

    def _start_raster_export(
        self,
        export_format,
        output,
    ):
        label = self._export_format_label(
            export_format
        )

        self.progress.setValue(0)
        self.log_box.clear()
        export_width, export_height = (
            self._raster_export_pixel_size()
        )
        self.log_box.append(
            (
                f"已确认当前预览与图片顺序，开始生成{label}..."
                f" 输出尺寸：{export_width} × {export_height}px，"
                f"约 {self._raster_export_dpi} DPI"
            )
        )
        self.start_btn.setEnabled(False)

        try:
            if export_format == "images":
                output.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                for old_page in output.glob(
                    "page_*.png"
                ):
                    try:
                        old_page.unlink()
                    except OSError:
                        pass

                page_paths = (
                    self._capture_all_export_pages(
                        output
                    )
                )
                result_path = output
                self.log_box.append(
                    f"完成：共生成 {len(page_paths)} 张 PNG 页面图片"
                )

            else:
                output.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with tempfile.TemporaryDirectory(
                    prefix="framedeck_pdf_"
                ) as temporary:
                    page_paths = (
                        self._capture_all_export_pages(
                            temporary
                        )
                    )
                    self.progress.setValue(94)
                    self.log_box.append(
                        "正在写入多页 PDF..."
                    )
                    QApplication.processEvents()

                    self._write_pdf_from_png_pages(
                        page_paths,
                        output,
                    )

                result_path = output
                self.log_box.append(
                    f"完成：{output}"
                )

            self.progress.setValue(100)
            self.on_finished(
                str(result_path),
                export_format,
            )

        except Exception:
            self.on_failed(
                traceback.format_exc()
            )

        finally:
            self.start_btn.setEnabled(True)

    def on_finished(
        self,
        output,
        export_format="pptx",
    ):
        self.last_output_file = output
        self.progress.setValue(100)
        self.start_btn.setEnabled(True)

        label = self._export_format_label(
            export_format
        )
        message = (
            f"页面图片已生成：\n{output}"
            if export_format == "images"
            else f"{label} 已生成：\n{output}"
        )

        if hasattr(
            self,
            "log_box",
        ):
            self.log_box.append(
                f"输出位置：{output}"
            )

        QMessageBox.information(
            self,
            "完成",
            message,
        )

    def on_failed(self, error):
        self.start_btn.setEnabled(True)
        error = str(error or "")

        permission_prefix = (
            "PPT_OUTPUT_PERMISSION::"
        )

        if error.startswith(
            permission_prefix
        ):
            message = error[
                len(permission_prefix):
            ].strip()

            self.log_box.append(
                message
            )
            self.log_dock.show()
            self.log_dock.raise_()

            title = (
                "PPT已生成到恢复文件"
                if "完整PPT已保存在" in message
                else "PPT文件无法写入"
            )

            QMessageBox.warning(
                self,
                title,
                message,
            )
            return

        self.log_box.append(error)
        self.log_dock.show()
        self.log_dock.raise_()
        QMessageBox.critical(
            self,
            "生成失败",
            "生成失败，日志面板已自动打开。",
        )

    def open_output_folder(self):
        target = (
            self.last_output_file
            or self.output_edit.text().strip()
        )

        if not target:
            return

        path = Path(target)
        folder = path if path.is_dir() else path.parent

        if folder.is_dir():
            subprocess.Popen(
                ["explorer", str(folder)]
            )


    def toggle_log_dock(self, checked):
        checked = bool(checked)

        if checked:
            self.log_dock.show()
            self.log_dock.raise_()
        else:
            self.log_dock.hide()

    def on_log_visibility_changed(self, visible):
        self.log_action.blockSignals(True)
        self.log_action.setChecked(bool(visible))
        self.log_action.blockSignals(False)


    def _build_image_context_menu(self):
        menu = QMenu(self)
        menu.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )
        menu.setMinimumWidth(250)
        menu.setStyleSheet(
            """
            QMenu {
                padding: 6px;
            }
            QMenu::item {
                min-width: 210px;
                padding: 7px 34px 7px 14px;
            }
            QMenu::separator {
                height: 1px;
                margin: 5px 8px;
            }
            """
        )

        duplicate_action = menu.addAction(
            "复制所选图片副本"
        )
        duplicate_action.setShortcut(
            QKeySequence("Ctrl+D")
        )
        duplicate_action.setShortcutVisibleInContextMenu(
            True
        )
        duplicate_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        copy_action = menu.addAction("复制到项目剪贴板")
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.setShortcutVisibleInContextMenu(True)
        copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)

        cut_action = menu.addAction("剪切到项目剪贴板")
        cut_action.setShortcut(QKeySequence("Ctrl+X"))
        cut_action.setShortcutVisibleInContextMenu(True)
        cut_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)

        paste_action = menu.addAction("粘贴到当前页")
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.setShortcutVisibleInContextMenu(True)
        paste_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        paste_action.setEnabled(bool(getattr(self, "_image_clipboard", [])))

        move_previous_page_action = menu.addAction("移到上一页末尾")
        move_previous_page_action.setShortcut(QKeySequence("Ctrl+PageUp"))
        move_previous_page_action.setShortcutVisibleInContextMenu(True)
        move_next_page_action = menu.addAction("移到下一页开头")
        move_next_page_action.setShortcut(QKeySequence("Ctrl+PageDown"))
        move_next_page_action.setShortcutVisibleInContextMenu(True)

        delete_action = menu.addAction(
            "删除所选图片"
        )
        delete_action.setShortcut(
            QKeySequence("Delete")
        )
        delete_action.setShortcutVisibleInContextMenu(
            True
        )
        delete_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        menu.addSeparator()

        crop_action = menu.addAction(
            "进入裁切模式"
        )
        crop_action.setShortcut(
            QKeySequence("Ctrl+Shift+C")
        )
        crop_action.setShortcutVisibleInContextMenu(
            True
        )
        crop_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        reset_crop_action = menu.addAction(
            "重置图片裁切"
        )
        reset_crop_action.setShortcut(
            QKeySequence("Ctrl+Alt+C")
        )
        reset_crop_action.setShortcutVisibleInContextMenu(
            True
        )
        reset_crop_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        menu.addSeparator()

        select_all_action = menu.addAction(
            "全选图片"
        )
        select_all_action.setShortcut(
            QKeySequence("Ctrl+A")
        )
        select_all_action.setShortcutVisibleInContextMenu(
            True
        )
        select_all_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        clear_action = menu.addAction(
            "取消选择"
        )
        clear_action.setShortcut(
            QKeySequence("Esc")
        )
        clear_action.setShortcutVisibleInContextMenu(
            True
        )
        clear_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        has_selection = bool(
            self._selected_image_rows()
        )
        current_page = int(self._current_logical_page_index())
        page_count = max(1, int(self.preview.page_count()))
        move_previous_page_action.setEnabled(has_selection and current_page > 0)
        move_next_page_action.setEnabled(
            has_selection and current_page < page_count - 1
        )
        copy_action.setEnabled(has_selection)
        cut_action.setEnabled(has_selection)
        delete_action.setEnabled(has_selection)

        single_selection = (
            len(self.selected_image_indices) == 1
        )
        crop_action.setEnabled(single_selection)
        reset_crop_action.setEnabled(single_selection)

        duplicate_action.triggered.connect(
            self.duplicate_selected_images
        )
        copy_action.triggered.connect(self.shortcut_copy_images)
        cut_action.triggered.connect(self.shortcut_cut_images)
        paste_action.triggered.connect(self.paste_images_to_current_page)
        move_previous_page_action.triggered.connect(
            lambda: self.move_selected_images_to_adjacent_page(-1)
        )
        move_next_page_action.triggered.connect(
            lambda: self.move_selected_images_to_adjacent_page(1)
        )
        delete_action.triggered.connect(
            self.delete_selected_image
        )
        crop_action.triggered.connect(
            self.start_crop_selected
        )
        reset_crop_action.triggered.connect(
            self.reset_selected_crop
        )
        select_all_action.triggered.connect(
            self.select_all_visible_images
        )
        clear_action.triggered.connect(
            self.clear_image_selection
        )

        return menu


    def show_image_list_context_menu(self, position):
        self.image_list.setFocus(
            Qt.FocusReason.MouseFocusReason
        )
        item = self.image_list.itemAt(position)

        if item is not None and not item.isSelected():
            self.image_list.blockSignals(True)

            try:
                self.image_list.clearSelection()
                self.image_list.setCurrentItem(item)
                item.setSelected(True)
            finally:
                self.image_list.blockSignals(False)

            self.sync_selection_from_image_list()

        menu = self._build_image_context_menu()
        menu.exec(
            self.image_list.viewport().mapToGlobal(
                position
            )
        )

    def show_canvas_context_menu(self, position):
        self.preview.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self.preview.setFocus(
            Qt.FocusReason.MouseFocusReason
        )

        if hasattr(self.preview, "_index_at"):
            index = self.preview._index_at(position)

            if (
                index >= 0
                and index not in self.selected_image_indices
            ):
                self._apply_image_selection(
                    [index],
                    index,
                    reveal=False,
                )

        menu = self._build_image_context_menu()
        menu.exec(
            self.preview.mapToGlobal(position)
        )

    def selected_paths(self):
        paths = []

        for row in self._selected_image_rows():
            item = self.image_list.item(row)

            if item is not None:
                path = item.data(
                    Qt.ItemDataRole.UserRole
                )

                if path:
                    paths.append(path)

        return paths

    def batch_rotate(self, degrees):
        paths = self.selected_paths()
        if not paths:
            QMessageBox.information(self, "批量操作", "请先在图片列表中多选图片。")
            return
        self.push_history("批量旋转")
        for path in paths:
            transform = self.get_transform(path)
            transform["rotation"] = (int(transform["rotation"]) + degrees) % 360
            self.image_transforms[path] = transform
        self.preview.set_image_transforms(self.image_transforms)
        self.refresh_preview()

    def batch_hide_selected(self):
        paths = self.selected_paths()
        if not paths:
            QMessageBox.information(self, "批量操作", "请先在图片列表中多选图片。")
            return
        self.push_history("批量隐藏")
        self.hidden_images.update(paths)
        self.refresh_image_list_appearance()
        self.refresh_preview()

    def batch_reset_selected(self):
        paths = self.selected_paths()
        if not paths:
            QMessageBox.information(self, "批量操作", "请先在图片列表中多选图片。")
            return
        self.push_history("批量重置")
        default = {
            "zoom": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "rotation": 0,
            "flip_h": False,
            "flip_v": False,
        }
        for path in paths:
            self.image_transforms[path] = dict(default)
        self.preview.set_image_transforms(self.image_transforms)
        self.refresh_preview()

    def show_about(self):
        QMessageBox.information(
            self,
            "FrameDeck Studio V12 Stable",
            "Compact Professional Image Layout & PPT Composer\n\n"
            "支持批量图片排版、可视化预览、单图调整、批量编辑、"
            "页面标题、页脚、工程与模板管理。",
        )

    def autosave_project(self):
        try:
            AUTOSAVE_FILE.write_text(
                json.dumps(
                    {
                        "format": "FrameDeck Studio Autosave",
                        "version": 12,
                        **self.project_data(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def current_theme_name(self):
        name = normalize_theme_name(
            getattr(
                self,
                "_theme_name",
                "极光浅色",
            )
        )

        return name

    def _make_theme_icon(
        self,
        name,
        size=30,
    ):
        """
        生成主题色板图标，不依赖外部图片文件。
        """
        meta = THEME_META.get(
            name,
            THEME_META["极光浅色"],
        )
        size = max(24, int(size))

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setPen(
            QPen(
                QColor(meta["border_strong"]),
                1,
            )
        )
        painter.setBrush(
            QColor(meta["window"])
        )
        painter.drawRoundedRect(
            1,
            1,
            size - 2,
            size - 2,
            7,
            7,
        )

        inset = max(4, round(size * 0.18))
        panel_size = size - inset * 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QColor(meta["panel"])
        )
        painter.drawRoundedRect(
            inset,
            inset,
            panel_size,
            panel_size,
            5,
            5,
        )

        accent_size = max(
            8,
            round(size * 0.34),
        )
        accent_x = size - accent_size - 3
        accent_y = size - accent_size - 3

        painter.setBrush(
            QColor(meta["accent"])
        )
        painter.drawEllipse(
            accent_x,
            accent_y,
            accent_size,
            accent_size,
        )

        painter.end()
        return QIcon(pixmap)

    def _update_theme_selector(self):
        name = self.current_theme_name()

        for theme_name, action in getattr(
            self,
            "_theme_actions",
            {},
        ).items():
            action.blockSignals(True)
            action.setChecked(
                theme_name == name
            )
            action.blockSignals(False)

        button = getattr(
            self,
            "theme_button",
            None,
        )

        if button is not None:
            button.setIcon(
                self._make_theme_icon(
                    name,
                    30,
                )
            )
            button.setToolTip(
                f"当前主题：{name}\n点击选择其他主题"
            )

    def set_theme_selection(
        self,
        name,
        *,
        persist=True,
    ):
        self.apply_theme(
            name,
            persist=persist,
        )

    def apply_theme(
        self,
        name,
        *,
        persist=True,
    ):
        name = normalize_theme_name(name)

        # QApplication owns the complete theme. A window-local stylesheet
        # would freeze parts of the UI on the previously selected palette.
        self.setStyleSheet("")

        self._theme_name = name
        meta = THEME_META[name]

        self.app.setStyleSheet(
            build_theme_qss(name)
        )

        palette = QPalette()
        palette.setColor(
            QPalette.ColorRole.Window,
            QColor(meta["window"]),
        )
        palette.setColor(
            QPalette.ColorRole.WindowText,
            QColor(meta["text"]),
        )
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(meta["input"]),
        )
        palette.setColor(
            QPalette.ColorRole.AlternateBase,
            QColor(meta["panel_alt"]),
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipBase,
            QColor(meta["panel"]),
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipText,
            QColor(meta["text"]),
        )
        palette.setColor(
            QPalette.ColorRole.Text,
            QColor(meta["text"]),
        )
        palette.setColor(
            QPalette.ColorRole.Button,
            QColor(meta["panel_alt"]),
        )
        palette.setColor(
            QPalette.ColorRole.ButtonText,
            QColor(meta["text"]),
        )
        palette.setColor(
            QPalette.ColorRole.BrightText,
            QColor(meta["accent"]),
        )
        palette.setColor(
            QPalette.ColorRole.Highlight,
            QColor(meta["selection"]),
        )
        palette.setColor(
            QPalette.ColorRole.HighlightedText,
            QColor(meta["text"]),
        )
        palette.setColor(
            QPalette.ColorRole.PlaceholderText,
            QColor(meta["muted"]),
        )
        self.app.setPalette(palette)

        if hasattr(self.preview, "set_theme"):
            self.preview.set_theme(
                name,
                meta,
            )

        if (
            self.slide_thumbnail_bar is not None
            and hasattr(
                self.slide_thumbnail_bar,
                "set_theme",
            )
        ):
            self.slide_thumbnail_bar.set_theme(
                meta
            )

        self.app.setProperty(
            "activeTheme",
            name,
        )
        self._update_theme_selector()

        for widget in (
            self,
            getattr(self, "preview", None),
            getattr(
                self,
                "slide_thumbnail_bar",
                None,
            ),
        ):
            if widget is None:
                continue

            try:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            except Exception:
                pass

        self._page_thumbnail_signatures = {}
        self._force_page_thumbnail_refresh()
        self.schedule_real_thumbnail_refresh()

        if persist:
            self.save_config()

        if hasattr(self, "status_bar"):
            self._show_status(
                f"主题已切换为：{name}",
                1800,
            )

    def new_project(self):
        result = QMessageBox.question(
            self, "新建工程", "确定清空当前工程并重新开始吗？"
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._active_template_document = None
        self._active_template_id = ""
        self.folder_edit.clear()
        self.output_edit.clear()
        self.image_list.clear()
        self.images = []
        self.image_transforms = {}
        self.hidden_images.clear()
        self.current_project_file = ""
        self.selected_image_index = -1
        self.selected_image_indices = set()
        self._manual_page_breaks = set()
        self._image_groups = []
        self._group_page_breaks = set()
        self._blank_fill_page_breaks = set()
        self._page_lock_records = []
        self._locked_group_ids = set()
        self._title_system = default_title_system()
        self._confirmed_auto_layout = False
        self._auto_layout_restore_state = None
        self._auto_layout_undo_depth = None
        self._set_pagination_mode(
            PAGINATION_GROUPED,
            refresh=False,
        )
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.preview.set_images([])
        # UI-05 thumbnail refresh

        self.refresh_slide_thumbnail()
        self.preview.set_page_index(0)
        self.set_transform_controls_enabled(False)
        self.refresh_preview()

        self._saved_project_signature = None
        self._session_initial_signature = (
            self._project_signature()
        )

    # =====================================================
    # UI-05-01-02
    # Slide Thumbnail Refresh
    # =====================================================

    def refresh_slide_thumbnail(
        self
    ):
        """
        兼容入口：只同步页面卡片数量和当前页。

        真实缩略图由离屏队列更新。
        """
        if not self.slide_thumbnail_bar:
            return

        count = max(
            1,
            int(self.preview.page_count()),
        )
        current = max(
            0,
            min(
                int(self.preview.current_page()),
                count - 1,
            ),
        )

        if (
            self.slide_thumbnail_bar.page_count()
            != count
        ):
            self.slide_thumbnail_bar.set_pages(
                [None] * count
            )
            self._page_thumbnail_signatures = {}

        self.slide_thumbnail_bar.set_current_page(
            current
        )
        self._force_page_thumbnail_refresh()
        self.schedule_real_thumbnail_refresh()


    def on_thumbnail_page_selected(self, index):
        """UI-05-22A：点击顶部页面卡片时切换中央画布页面。"""
        page_target = getattr(
            self.slide_thumbnail_bar,
            "page_list",
            self.slide_thumbnail_bar,
        )
        page_target.setFocus(
            Qt.FocusReason.MouseFocusReason
        )
        count = max(1, int(self.preview.page_count()))
        target = max(0, min(int(index), count - 1))

        if target != self.preview.current_page():
            self.preview.set_page_index(target)

        self.refresh_preview()

    def on_thumbnail_image_drop(self, page_index, selected_rows, edge):
        """Move list images to the start or end slot of a thumbnail page."""
        rows = sorted(
            {
                int(row)
                for row in list(selected_rows or [])
                if 0 <= int(row) < self.image_list.count()
            }
        )
        if not rows:
            return False

        page_count = max(1, int(self.preview.page_count()))
        target_page = max(0, min(int(page_index), page_count - 1))
        edge = "start" if str(edge).lower() == "start" else "end"
        visible_before = list(self.visible_images())
        moved_paths = []
        for row in rows:
            item = self.image_list.item(row)
            path = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
            if path and path in visible_before:
                moved_paths.append(path)
        if not moved_paths:
            return False

        index_by_path = {path: index for index, path in enumerate(visible_before)}
        source_pages = {
            self._logical_page_index_for_visible_index(index_by_path[path])
            for path in moved_paths
        }
        involved_pages = set(source_pages)
        involved_pages.add(target_page)
        if any(self._page_lock_meta_for_logical_page(page) for page in involved_pages):
            self._show_status("涉及已锁定页面，请先解锁后移动图片", 3000)
            return False
        if any(self._is_logical_page_in_locked_group(page) for page in involved_pages):
            self._show_status("涉及已锁定分组，请先解锁后移动图片", 3000)
            return False

        old_groups = self._normalize_image_groups()
        old_meta = {str(row.get("id", "")): dict(row) for row in old_groups}
        membership = {
            path: str(self._group_id_for_visible_index(index) or "")
            for index, path in enumerate(visible_before)
        }
        page_start, page_end = self._page_visible_range(target_page)
        if edge == "start":
            removed_before_start = sum(
                1
                for path in moved_paths
                if index_by_path.get(path, len(visible_before)) < int(page_start)
            )
            target_index = min(
                int(page_end),
                int(page_start) + removed_before_start,
            )
        else:
            desired_block_start = max(
                int(page_start),
                int(page_end) - len(moved_paths),
            )
            removed_before_end = sum(
                1
                for path in moved_paths
                if index_by_path.get(path, len(visible_before)) < int(page_end)
            )
            target_index = min(
                int(page_end),
                desired_block_start + removed_before_end,
            )
        neighbor_index = (
            int(page_start)
            if edge == "start"
            else int(page_end) - 1
        )
        target_group_id = ""
        if 0 <= neighbor_index < len(visible_before):
            target_group_id = membership.get(visible_before[neighbor_index], "")

        self._displayed_page_index = target_page
        self.preview.set_page_index(target_page)
        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(target_page)

        handled = bool(
            self.handle_image_list_drop_to_current_page(rows, target_index)
        )
        if not handled:
            return False

        if target_group_id:
            for path in moved_paths:
                membership[path] = target_group_id
            self._rebuild_groups_from_image_membership(
                list(self.visible_images()),
                membership,
                old_meta,
            )
            self._normalize_image_groups()
            self._update_group_ui_state()
            self._force_page_thumbnail_refresh()
            self.refresh_preview()

        side = "页首" if edge == "start" else "页尾"
        self._show_status(
            f"已将 {len(moved_paths)} 张图片移动到第 {target_page + 1} 页{side}",
            3200,
        )
        return True
    # =====================================================
    # UI-05-01-02
    # Add Page Placeholder
    # =====================================================

    def _restore_thumbnail_order_after_reject(self, current_page):
        """
        恢复导航栏标准顺序，并安排真实缩略图重新生成。
        """
        bar = getattr(self, "slide_thumbnail_bar", None)
        if bar is None:
            return

        if hasattr(bar, "reset_visual_order"):
            bar.reset_visual_order(current_page)
        else:
            count = max(1, int(self.preview.page_count()))
            bar.set_pages([None] * count)
            bar.set_current_page(current_page)

        self._page_thumbnail_signatures = {}
        self._force_page_thumbnail_refresh()
        self.schedule_real_thumbnail_refresh()

    def on_thumbnail_pages_reordered(self, order):
        """
        顶部页面拖动排序。

        显式分页模式下，已填满与未填满页面都可以作为完整页面单元移动。
        """
        if getattr(self, "_page_reorder_lock", False):
            return

        preview = getattr(self, "preview", None)
        bar = getattr(self, "slide_thumbnail_bar", None)

        if preview is None or bar is None:
            return

        total_count = max(
            1,
            int(preview.page_count()),
        )
        order = [
            int(value)
            for value in list(order or [])
        ]

        if (
            len(order) != total_count
            or sorted(order) != list(range(total_count))
        ):
            current_page = max(
                0,
                int(preview.current_page()),
            )
            self._restore_thumbnail_order_after_reject(
                current_page
            )
            return

        selected_row = max(
            0,
            min(
                int(bar.page_list.currentRow()),
                total_count - 1,
            ),
        )

        if order == list(range(total_count)):
            if hasattr(bar, "commit_current_order"):
                bar.commit_current_order()
            bar.set_current_page(selected_row)
            return

        image_ranges = self._computed_page_ranges()
        image_page_count = len(image_ranges)
        blank_count = self._compat_blank_page_count()

        page_group_ids = [
            self._group_id_for_visible_index(
                start
            )
            for start, end in image_ranges
        ]

        page_types = [
            (
                "blank"
                if self._is_blank_page(
                    page_index
                )
                else "images"
            )
            for page_index in range(
                total_count
            )
        ]

        reordered_types = [
            page_types[index]
            for index in order
        ]

        page_lock_meta = [
            self._page_lock_meta_for_logical_page(
                page_index
            )
            for page_index in range(
                total_count
            )
        ]

        for old_page_index in range(
            total_count
        ):
            if not self._is_logical_page_in_locked_group(
                old_page_index
            ):
                continue

            new_page_index = order.index(
                old_page_index
            )

            if (
                new_page_index
                != old_page_index
            ):
                QMessageBox.information(
                    self,
                    "分组已锁定",
                    (
                        "拖动操作会改变已锁定分组的页面位置。\n"
                        "请先解锁该分组再调整页面顺序。"
                    ),
                )
                self._restore_thumbnail_order_after_reject(
                    self.preview.current_page()
                )
                return

        # UI-05-42B FIX02：
        # 空白页与图片页现在都是完整页面单元，可自由交错拖动。
        self.push_history("调整页面顺序")

        # UI-05-42B：
        # 单页标题与单页样式跟随页面重排。
        old_page_titles = dict(
            self._title_system.get(
                "page_titles",
                {},
            )
            or {}
        )
        old_page_styles = dict(
            self._title_system.get(
                "page_styles",
                {},
            )
            or {}
        )
        new_page_titles = {}
        new_page_styles = {}

        for new_index, old_index in enumerate(
            order
        ):
            old_key = str(
                old_index
            )
            new_key = str(
                new_index
            )

            if old_key in old_page_titles:
                new_page_titles[
                    new_key
                ] = old_page_titles[
                    old_key
                ]

            if old_key in old_page_styles:
                new_page_styles[
                    new_key
                ] = old_page_styles[
                    old_key
                ]

        self._title_system[
            "page_titles"
        ] = new_page_titles
        self._title_system[
            "page_styles"
        ] = new_page_styles

        self._page_reorder_lock = True

        list_was_blocked = self.image_list.blockSignals(
            True
        )
        model = self.image_list.model()
        model_was_blocked = model.blockSignals(True)

        try:
            all_items = []

            while self.image_list.count():
                all_items.append(
                    self.image_list.takeItem(0)
                )

            visible_items = []
            hidden_by_position = {}

            for position, item in enumerate(all_items):
                path = item.data(
                    Qt.ItemDataRole.UserRole
                )

                if path in self.hidden_images:
                    hidden_by_position[position] = item
                else:
                    visible_items.append(item)

            page_units = []
            logical_group_ids = []
            image_page_cursor = 0

            for unit_type in page_types:
                if (
                    unit_type == "images"
                    and image_page_cursor
                    < image_page_count
                ):
                    start, end = image_ranges[
                        image_page_cursor
                    ]
                    page_units.append(
                        visible_items[
                            start:end
                        ]
                    )
                    logical_group_ids.append(
                        page_group_ids[
                            image_page_cursor
                        ]
                    )
                    image_page_cursor += 1
                else:
                    page_units.append(
                        []
                    )
                    logical_group_ids.append(
                        ""
                    )

            reordered_units = [
                page_units[index]
                for index in order
            ]

            reordered_visible = []
            page_lengths = []
            reordered_image_group_ids = []

            for original_page_index in order:
                if (
                    page_types[
                        original_page_index
                    ]
                    == "images"
                ):
                    unit_items = page_units[
                        original_page_index
                    ]
                    reordered_visible.extend(
                        unit_items
                    )
                    page_lengths.append(
                        len(
                            unit_items
                        )
                    )
                    reordered_image_group_ids.append(
                        logical_group_ids[
                            original_page_index
                        ]
                    )

            visible_iter = iter(reordered_visible)
            total_items = (
                len(reordered_visible)
                + len(hidden_by_position)
            )

            for position in range(total_items):
                if position in hidden_by_position:
                    self.image_list.addItem(
                        hidden_by_position[position]
                    )
                else:
                    try:
                        self.image_list.addItem(
                            next(visible_iter)
                        )
                    except StopIteration:
                        pass

            for remaining_item in visible_iter:
                self.image_list.addItem(
                    remaining_item
                )

            self._set_page_breaks_from_lengths(
                page_lengths
            )

            new_blank_positions = [
                index
                for index, unit_type
                in enumerate(
                    reordered_types
                )
                if unit_type == "blank"
            ]
            self._set_blank_page_positions(
                new_blank_positions
            )

            self._rebuild_groups_from_reordered_pages(
                page_lengths,
                reordered_image_group_ids,
            )
            self._set_group_page_breaks_from_lengths(
                page_lengths
            )
            self._set_blank_fill_page_breaks_from_lengths(
                page_lengths
            )
            self._rebuild_page_lock_records_after_reorder(
                order=order,
                page_types=page_types,
                page_units=page_units,
                page_lock_meta=page_lock_meta,
            )

        finally:
            model.blockSignals(model_was_blocked)
            self.image_list.blockSignals(
                list_was_blocked
            )

        try:
            self.selected_image_index = -1
            self.selected_image_indices = set()
            self._displayed_page_index = selected_row

            self.refresh_image_list_appearance()

            if hasattr(bar, "commit_current_order"):
                bar.commit_current_order()

            selected_row = min(
                selected_row,
                max(
                    0,
                    preview.page_count() - 1,
                ),
            )
            preview.set_page_index(
                selected_row
            )
            bar.set_current_page(
                selected_row
            )
            self._displayed_page_index = (
                selected_row
            )

            self._force_page_thumbnail_refresh()
            self.refresh_preview()

            if hasattr(self, "status_bar"):
                self._show_status(
                    "页面顺序已调整",
                    2500,
                )

        finally:
            self._page_reorder_lock = False


    def on_thumbnail_add_page(self):
        """
        UI-05-42B FIX02：
        在当前选中页之后插入空白页。

        新空白页是完整页面单元：
        - 可以插在任意图片页之间；
        - 可以连续插入多个空白页；
        - 可以在顶部缩略图栏自由拖动；
        - 不改变图片顺序和分组边界。
        """
        preview = getattr(
            self,
            "preview",
            None,
        )

        if preview is None:
            return

        old_count = max(
            1,
            int(
                preview.page_count()
            ),
        )
        current_page = max(
            0,
            min(
                int(
                    preview.current_page()
                ),
                old_count - 1,
            ),
        )
        insert_at = (
            current_page
            + 1
        )

        try:
            self.push_history(
                "在当前页后添加空白页面"
            )
            self._shift_page_title_metadata_for_insert(
                insert_at
            )
            self._insert_blank_page_position(
                insert_at
            )

            new_count = max(
                1,
                int(
                    preview.page_count()
                ),
            )

            if (
                new_count
                <= old_count
            ):
                if self.undo_stack:
                    self.undo_stack.pop()

                raise RuntimeError(
                    "页面数量没有增加"
                )

            self._displayed_page_index = (
                insert_at
            )
            preview.set_page_index(
                insert_at
            )
            preview.set_selected_index(
                -1,
                reveal=False,
            )
            self.selected_image_index = -1
            self.selected_image_indices = set()

            self._force_page_thumbnail_refresh()
            self.refresh_preview()

            if hasattr(
                self,
                "status_bar",
            ):
                self._show_status(
                    (
                        f"已在第 {current_page + 1} 页后"
                        f"插入空白页（新第 {insert_at + 1} 页）"
                    ),
                    3200,
                )

        except Exception as error:
            if self.undo_stack:
                self.undo_stack.pop()

            print(
                "[UI-05-42B FIX02 add blank page error]",
                error,
            )
            QMessageBox.warning(
                self,
                "添加页面失败",
                (
                    "在当前页后创建空白页面时发生错误：\n"
                    f"{error}"
                ),
            )

    def on_thumbnail_duplicate_page(self, page_index):
        """
        复制任意图片页面，包括未填满页面。

        复制图片会生成独立文件，并通过显式分页起点建立独立新页面，
        不再要求源页面必须填满。
        """
        preview = getattr(self, "preview", None)

        if preview is None:
            return

        count = max(
            1,
            int(preview.page_count()),
        )
        page_index = max(
            0,
            min(int(page_index), count - 1),
        )

        if self._is_logical_page_in_locked_group(
            page_index
        ):
            QMessageBox.information(
                self,
                "分组已锁定",
                (
                    "当前页面属于已锁定分组。\n"
                    "请先解锁当前组，再复制页面。"
                ),
            )
            return

        # 空白页复制后仍为空白页，并插在源空白页之后。
        if self._is_blank_page(
            page_index
        ):
            preview.set_page_index(
                page_index
            )
            self.on_thumbnail_add_page()
            return

        image_page_index = (
            self._image_page_index_for_logical(
                page_index
            )
        )

        if image_page_index is None:
            return

        start, end = self._page_visible_range(
            page_index
        )
        visible = self.visible_images()
        source_paths = list(visible[start:end])

        if not source_paths:
            self.on_thumbnail_add_page()
            return

        created = []
        errors = []

        for source_path in source_paths:
            try:
                destination = self._unique_copy_path(
                    source_path
                )
                shutil.copy2(
                    source_path,
                    destination,
                )
                created.append(
                    (source_path, str(destination))
                )
            except Exception as error:
                errors.append(
                    f"{Path(source_path).name}: {error}"
                )

        if not created:
            QMessageBox.warning(
                self,
                "复制页面失败",
                "\n".join(errors[:5])
                if errors
                else "未能创建页面图片副本。",
            )
            return

        self.push_history("复制页面")

        insert_visible_index = end
        insert_row = self._list_row_for_visible_insertion(
            insert_visible_index
        )
        copy_count = len(created)

        # 原有后续分页向后移动；新副本从 end 位置开始成为独立页面。
        shifted_breaks = set()

        for page_break in self._manual_page_breaks:
            shifted_breaks.add(
                page_break + copy_count
                if page_break >= insert_visible_index
                else page_break
            )

        shifted_breaks.add(insert_visible_index)
        self._manual_page_breaks = shifted_breaks

        self._shift_page_lock_records_for_insert(
            insert_visible_index,
            copy_count,
            boundary_belongs_to_previous=False,
        )

        self._shift_image_groups_for_insert(
            insert_visible_index,
            copy_count,
            boundary_belongs_to_previous=True,
            image_count_before=len(
                self.visible_images()
            ),
        )

        self.image_list.blockSignals(True)

        try:
            for offset, (
                source_path,
                copied_path,
            ) in enumerate(created):
                item = self._create_external_image_item(
                    copied_path
                )
                self.image_list.insertItem(
                    insert_row + offset,
                    item,
                )
                self.image_transforms[copied_path] = dict(
                    self.get_transform(source_path)
                )

        finally:
            self.image_list.blockSignals(False)

        target_page = page_index + 1
        self.selected_image_index = -1
        self.selected_image_indices = set()
        self._displayed_page_index = target_page

        self.refresh_image_list_appearance()

        target_page = min(
            target_page,
            max(
                0,
                self.preview.page_count() - 1,
            ),
        )
        preview.set_page_index(
            target_page
        )
        self._displayed_page_index = (
            target_page
        )

        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(
                target_page
            )

        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已复制第 {page_index + 1} 页"
                f"（{len(created)} 张图片）",
                3000,
            )

        if errors:
            QMessageBox.warning(
                self,
                "部分图片复制失败",
                "\n".join(errors[:5]),
            )


    def on_thumbnail_delete_page(
        self,
        page_index,
        *,
        record_history=True,
    ):
        """
        删除任意页面，并同步维护显式分页边界。
        """
        preview = getattr(self, "preview", None)

        if preview is None:
            return

        total_count = max(
            1,
            int(preview.page_count()),
        )

        if total_count <= 1:
            QMessageBox.information(
                self,
                "无法删除",
                "工程中至少需要保留一个页面。",
            )
            return

        page_index = max(
            0,
            min(int(page_index), total_count - 1),
        )

        if (
            not self._is_blank_page(
                page_index
            )
            and self._page_lock_meta_for_logical_page(
                page_index
            )
        ):
            QMessageBox.information(
                self,
                "页面已锁定",
                (
                    "当前页面处于锁定状态。\n"
                    "请先解锁当前页或当前组，再删除整页。"
                ),
            )
            return

        if record_history:
            self.push_history("删除页面")

        if self._is_blank_page(
            page_index
        ):
            self._remove_blank_page_position(
                page_index
            )
            self._shift_page_title_metadata_for_delete(
                page_index
            )

        else:
            start, end = self._page_visible_range(
                page_index
            )
            visible_rows = self._visible_image_rows()
            rows_to_remove = visible_rows[start:end]
            deleted_visible_indices = list(
                range(start, end)
            )

            image_count_before = len(
                self.visible_images()
            )
            self._shift_page_breaks_for_delete(
                deleted_visible_indices,
                image_count_before=image_count_before,
            )
            self._shift_image_groups_for_delete(
                deleted_visible_indices,
                image_count_before=image_count_before,
            )
            self._shift_group_page_breaks_for_delete(
                deleted_visible_indices,
                image_count_before=image_count_before,
            )
            self._shift_blank_fill_page_breaks_for_delete(
                deleted_visible_indices,
                image_count_before=image_count_before,
            )
            self._shift_page_lock_records_for_delete(
                deleted_visible_indices,
                image_count_before=image_count_before,
            )

            self.image_list.blockSignals(True)

            try:
                for row in reversed(rows_to_remove):
                    self.image_list.takeItem(row)

            finally:
                self.image_list.blockSignals(False)

            remaining_paths = set(
                self.ordered_images()
            )

            for path in list(self.image_transforms):
                if path not in remaining_paths:
                    self.image_transforms.pop(
                        path,
                        None,
                    )
                    self.hidden_images.discard(path)

        self.selected_image_index = -1
        self.selected_image_indices = set()

        self.refresh_image_list_appearance()

        new_count = max(
            1,
            int(preview.page_count()),
        )
        target_page = min(
            page_index,
            new_count - 1,
        )
        self._displayed_page_index = (
            target_page
        )
        preview.set_page_index(
            target_page
        )
        preview.set_selected_index(
            -1,
            reveal=False,
        )

        if self.slide_thumbnail_bar is not None:
            self.slide_thumbnail_bar.set_current_page(
                target_page
            )

        self._force_page_thumbnail_refresh()
        self.refresh_preview()

        if hasattr(self, "status_bar"):
            self._show_status(
                f"已删除第 {page_index + 1} 页",
                3000,
            )


    # =====================================================
    # UI-05-37E Unsaved Project Detection
    # =====================================================

    def _project_signature(self):
        """
        返回当前工程内容的稳定签名。

        列表顺序、图片参数、布局、模板、页面与导出设置发生变化，
        都会反映到签名中。
        """
        try:
            data = dict(
                self.project_data()
            )
            data["hidden_images"] = sorted(
                str(path)
                for path in data.get(
                    "hidden_images",
                    [],
                )
            )

            return json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )

        except Exception:
            return ""

    def _project_has_meaningful_content(self):
        """
        判断当前是否已经形成需要保存的工程内容。
        """
        return bool(
            self.ordered_images()
            or self.image_transforms
            or self.hidden_images
            or self._compat_blank_page_count() > 0
            or self._manual_page_breaks
            or (
                self._image_groups
                and self.ordered_images()
            )
            or self.active_template_document()
        )

    def _has_unsaved_project_changes(self):
        current_signature = (
            self._project_signature()
        )

        if self.current_project_file:
            if (
                self._saved_project_signature
                is None
            ):
                return True

            return (
                current_signature
                != self._saved_project_signature
            )

        # 没有工程文件但已有图片、模板或页面内容，
        # 始终属于“尚未保存为工程文件”。
        if self._project_has_meaningful_content():
            return True

        if (
            self._session_initial_signature
            is None
        ):
            return False

        return (
            current_signature
            != self._session_initial_signature
        )

    def _mark_project_saved(self):
        signature = self._project_signature()
        self._saved_project_signature = (
            signature
        )
        self._session_initial_signature = (
            signature
        )

    @staticmethod
    def _remove_autosave_file():
        try:
            AUTOSAVE_FILE.unlink(
                missing_ok=True
            )
        except OSError:
            pass

    def project_data(self):
        return {
            "app": "FrameDeck Studio",
            "version": 12,
            "folder": self.folder_edit.text().strip(),
            "output": self.output_edit.text().strip(),
            "export_format": self._selected_export_format,
            "theme": self.current_theme_name(),
            "zoom_mode": self.current_zoom_mode(),
            "order": self.ordered_images(),
            "image_transforms": self.image_transforms,
            "hidden_images": list(self.hidden_images),
            "settings": self.preview_settings(),
            "blank_pages": self._compat_blank_page_count(),
            "blank_page_positions": (
                self._blank_page_positions()
            ),
            "page_breaks": sorted(
                self._manual_page_breaks
            ),
            "pagination_mode": (
                self._current_pagination_mode()
            ),
            "confirmed_auto_layout": bool(
                getattr(
                    self,
                    "_confirmed_auto_layout",
                    False,
                )
            ),
            "auto_layout_restore_state": deepcopy(
                getattr(
                    self,
                    "_auto_layout_restore_state",
                    None,
                )
            ),
            "image_groups": list(
                self._normalize_image_groups()
            ),
            "group_page_breaks": sorted(
                self._normalize_group_page_breaks()
            ),
            "blank_fill_page_breaks": sorted(
                self._normalize_blank_fill_page_breaks()
            ),
            # UI-05-45A：不再把已取消的锁写回新工程。
            "page_lock_records": [],
            "locked_group_ids": [],
            "title_system": (
                self._title_system_payload()
            ),
        }

    def save_project_as(self):
        """
        另存当前工程，不覆盖原工程路径。

        返回：
            True  保存成功
            False 用户取消或保存失败
        """
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translated("FrameDeck 工程另存为"),
            (
                Path(
                    self.current_project_file
                ).name
                if self.current_project_file
                else "project.fds"
            ),
            self._translated_file_filter("FrameDeck 工程 (*.fds)"),
        )

        if not path:
            return False

        path = normalize_project_path(
            path
        )

        try:
            self.current_project_file = (
                save_project_file(
                    path,
                    self.project_data(),
                )
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "保存失败",
                str(error),
            )
            return False

        self._mark_project_saved()
        self._remove_autosave_file()

        self.header_project_badge.setText(
            Path(path).name
        )
        self.log_box.append(
            f"工程已另存为：{path}"
        )
        self.refresh_recent_state()

        if hasattr(self, "status_bar"):
            self._show_status(
                (
                    "工程已另存为："
                    f"{Path(path).name}"
                ),
                3000,
            )

        return True

    def save_project(self):
        """
        保存当前工程。

        返回：
            True  保存成功
            False 用户取消或保存失败
        """
        path = self.current_project_file

        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self,
                self._translated("保存 FrameDeck 工程"),
                "project.fds",
                self._translated_file_filter("FrameDeck 工程 (*.fds)"),
            )

        if not path:
            return False

        path = normalize_project_path(
            path
        )

        try:
            self.current_project_file = (
                save_project_file(
                    path,
                    self.project_data(),
                )
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "保存失败",
                str(error),
            )
            return False

        self._mark_project_saved()
        self._remove_autosave_file()

        self.header_project_badge.setText(
            Path(path).name
        )
        self.log_box.append(
            f"工程已保存：{path}"
        )
        self.refresh_recent_state()

        if hasattr(self, "status_bar"):
            self._show_status(
                (
                    "工程已保存："
                    f"{Path(path).name}"
                ),
                3000,
            )

        return True

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translated("打开 FrameDeck 工程"),
            "",
            self._translated_file_filter(
                "FrameDeck 工程 (*.fds);;旧版工程 (*.framedeck.json *.json)"
            ),
        )
        if path:
            self.open_project_path(path)

    def show_recent_projects(self):
        projects = load_recent_projects()
        if not projects:
            QMessageBox.information(self, "最近工程", "暂无最近工程。")
            return

        menu = QMenu(self)
        for project_path in projects:
            action = menu.addAction(Path(project_path).name)
            action.setToolTip(project_path)
            action.triggered.connect(
                lambda checked=False, p=project_path: self.open_project_path(p)
            )
        menu.exec(self.mapToGlobal(self.rect().topLeft()))

    def open_project_path(self, path):
        try:
            data = load_project_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return

        self._apply_project_data(data, path)

    def _apply_project_data(self, data, path):
        order = [
            str(p)
            for p in data.get("order", [])
            if Path(p).is_file()
        ]
        missing = [
            str(p)
            for p in data.get("order", [])
            if not Path(p).is_file()
        ]

        # UI-05-42A FIX01：
        # 分组信息必须在图片列表重建完成之后再恢复。
        # 如果提前写入 self._image_groups，主题/缩略图刷新可能在
        # image_list 仍为空时触发 _normalize_image_groups()，
        # 从而把已经保存的 10/5/4 分组边界清空。
        saved_pagination_mode = normalize_pagination_mode(
            data.get(
                "pagination_mode",
                PAGINATION_CONTINUOUS,
            )
        )
        saved_confirmed_auto_layout = bool(
            data.get(
                "confirmed_auto_layout",
                False,
            )
        )
        saved_auto_layout_restore_state = deepcopy(
            data.get(
                "auto_layout_restore_state",
                None,
            )
        )
        saved_image_groups = [
            dict(item)
            for item in data.get(
                "image_groups",
                [],
            )
            if isinstance(item, dict)
        ]
        saved_group_page_breaks = {
            int(value)
            for value in data.get(
                "group_page_breaks",
                [],
            )
        }
        saved_blank_fill_page_breaks = {
            int(value)
            for value in data.get(
                "blank_fill_page_breaks",
                [],
            )
        }
        saved_page_lock_records = [
            dict(item)
            for item in data.get(
                "page_lock_records",
                [],
            )
            if isinstance(
                item,
                dict,
            )
        ]
        saved_locked_group_ids = {
            str(value)
            for value in data.get(
                "locked_group_ids",
                [],
            )
            if value
        }
        saved_blank_page_positions = (
            data.get(
                "blank_page_positions",
                None,
            )
        )
        saved_blank_page_count = max(
            0,
            int(
                data.get(
                    "blank_pages",
                    0,
                )
            ),
        )
        saved_title_system = dict(
            data.get(
                "title_system",
                {},
            )
            or {}
        )

        self.folder_edit.setText(
            data.get("folder", "")
        )
        self.output_edit.setText(
            data.get("output", "")
        )
        self._set_export_format(
            data.get("export_format", "pptx")
        )
        self.image_transforms = {
            str(p): dict(v)
            for p, v in data.get(
                "image_transforms",
                {},
            ).items()
        }
        self.hidden_images = set(
            data.get(
                "hidden_images",
                [],
            )
        )

        # 在加载布局、主题和缩放期间，不让待恢复的分组数据参与任何
        # 空列表状态下的归一化。
        self._image_groups = []
        self._group_page_breaks = set()
        self._blank_fill_page_breaks = set()
        self._page_lock_records = []
        self._locked_group_ids = set()
        self._pagination_mode = (
            PAGINATION_CONTINUOUS
        )
        self._confirmed_auto_layout = False
        self._auto_layout_restore_state = None
        self._title_system = (
            default_title_system()
        )

        self.apply_settings(
            data.get(
                "settings",
                {},
            )
        )
        self._set_blank_page_positions(
            []
        )
        self._manual_page_breaks = {
            int(value)
            for value in data.get(
                "page_breaks",
                [],
            )
        }

        self.set_theme_selection(
            data.get(
                "theme",
                "极光浅色",
            ),
            persist=False,
        )

        self.apply_zoom(
            data.get(
                "zoom_mode",
                data.get(
                    "zoom",
                    "适应窗口",
                ),
            )
        )

        self._reset_image_thumbnail_queue()
        self.image_list.blockSignals(True)

        try:
            self.image_list.clear()

            for image_path in order:
                self.image_list.addItem(
                    self._create_external_image_item(
                        image_path
                    )
                )
        finally:
            self.image_list.blockSignals(False)

        # 图片数量已经稳定，现在恢复分组边界。
        self._image_groups = (
            saved_image_groups
        )
        self._group_page_breaks = set(
            saved_group_page_breaks
        )
        self._blank_fill_page_breaks = set(
            saved_blank_fill_page_breaks
        )
        # 打开旧工程时释放历史锁，避免没有“解锁”入口却仍被限制。
        self._page_lock_records = []
        self._locked_group_ids = set()
        self._normalize_image_groups()
        self._normalize_group_page_breaks()
        self._normalize_blank_fill_page_breaks()
        self._normalize_lock_state()

        if saved_blank_page_positions is None:
            self._set_compat_blank_page_count(
                saved_blank_page_count
            )
        else:
            self._set_blank_page_positions(
                saved_blank_page_positions
            )

        self._confirmed_auto_layout = (
            saved_confirmed_auto_layout
        )
        self._auto_layout_restore_state = (
            saved_auto_layout_restore_state
        )
        self._auto_layout_undo_depth = None
        self._set_pagination_mode(
            saved_pagination_mode,
            refresh=False,
        )
        self._load_title_system(
            saved_title_system
        )
        self._normalize_manual_page_breaks()
        self._update_group_ui_state()

        self.current_project_file = path
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.refresh_image_list_appearance()
        self.preview.set_page_index(0)
        self.refresh_preview()
        self.refresh_recent_state()

        if path:
            self._mark_project_saved()
        else:
            # 自动保存恢复没有正式工程文件，关闭时仍需提示保存。
            self._saved_project_signature = None
            self._session_initial_signature = (
                self._project_signature()
            )

        if missing:
            QMessageBox.warning(
                self,
                "部分图片缺失",
                f"有 {len(missing)} 张图片找不到，已跳过。",
            )

    def refresh_recent_state(self):
        if hasattr(self, "header_project_badge"):
            self.header_project_badge.setText(
                self._translated(
                    Path(self.current_project_file).name
                    if self.current_project_file
                    else "未保存工程"
                )
            )

    def _reset_startup_session_to_blank(
        self,
        *,
        clear_folder=True,
    ):
        """
        清空本次启动的工程内容，但保留主题、界面布局等偏好。

        主要用于用户明确选择“放弃恢复”后，防止 load_config
        中保存的旧图片文件夹再次把同一个未保存工程载入。
        """
        self._reset_image_thumbnail_queue()

        if clear_folder:
            self.folder_edit.clear()

        self.image_list.clear()
        self.images = []
        self.image_transforms = {}
        self.hidden_images.clear()
        self.current_project_file = ""
        self.selected_image_index = -1
        self.selected_image_indices = set()
        self._manual_page_breaks = set()
        self._image_groups = []
        self._group_page_breaks = set()
        self._blank_fill_page_breaks = set()
        self._page_lock_records = []
        self._locked_group_ids = set()
        self._title_system = default_title_system()
        self._confirmed_auto_layout = False
        self._auto_layout_restore_state = None
        self._auto_layout_undo_depth = None
        self._set_pagination_mode(
            PAGINATION_GROUPED,
            refresh=False,
        )
        self._set_blank_page_positions([])

        self.undo_stack.clear()
        self.redo_stack.clear()

        self.preview.set_images([])
        self.preview.set_image_transforms({})
        self.preview.set_selected_index(
            -1,
            reveal=False,
        )
        self.preview.set_page_index(0)

        self.selected_name_label.setText(
            "未选择图片"
        )
        self.set_transform_controls_enabled(
            False
        )
        self.refresh_recent_state()
        self.refresh_slide_thumbnail()
        self.refresh_preview()

        self._saved_project_signature = None
        self._session_initial_signature = (
            self._project_signature()
        )

    def maybe_offer_autosave_recovery(self):
        """
        返回：
            none       没有有效自动保存
            restored   用户恢复了自动保存
            discarded  用户明确放弃恢复
            deferred   用户关闭了对话框，本次先进入空白工程
        """
        autosave = autosave_file()

        if not autosave.exists():
            return "none"

        try:
            data = json.loads(
                autosave.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            # 无法解析的自动保存不能反复干扰启动。
            try:
                autosave.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return "none"

        order = [
            str(path)
            for path in data.get(
                "order",
                [],
            )
            if Path(path).is_file()
        ]

        if not order:
            try:
                autosave.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return "none"

        message_box = QMessageBox(self)
        message_box.setWindowTitle(
            "恢复自动保存"
        )
        message_box.setIcon(
            QMessageBox.Icon.Question
        )
        message_box.setText(
            "检测到上次自动保存的工程。"
        )
        message_box.setInformativeText(
            (
                f"可恢复图片：{len(order)} 张\n\n"
                "选择“恢复工程”将载入自动保存内容；"
                "选择“放弃恢复”将进入空白工程。"
            )
        )

        restore_button = (
            message_box.addButton(
                "恢复工程",
                QMessageBox.ButtonRole.AcceptRole,
            )
        )
        discard_button = (
            message_box.addButton(
                "放弃恢复",
                QMessageBox.ButtonRole.DestructiveRole,
            )
        )
        message_box.setDefaultButton(
            restore_button
        )
        message_box.exec()

        clicked = message_box.clickedButton()

        if clicked is restore_button:
            self._apply_project_data(
                data,
                "",
            )

            if hasattr(
                self,
                "status_bar",
            ):
                self._show_status(
                    (
                        "已恢复上次自动保存："
                        f"{len(order)} 张图片"
                    ),
                    3500,
                )

            return "restored"

        if clicked is discard_button:
            try:
                autosave.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            self._reset_startup_session_to_blank(
                clear_folder=True
            )

            # 清除配置中的旧文件夹路径，避免下一次启动又自动载入。
            self.save_config()

            if hasattr(
                self,
                "status_bar",
            ):
                self._show_status(
                    "已放弃自动保存，进入空白工程",
                    3000,
                )

            return "discarded"

        # 点击窗口右上角关闭：
        # 不删除自动保存，但本次进入空白工程，防止未经确认就恢复。
        self._reset_startup_session_to_blank(
            clear_folder=True
        )

        if hasattr(
            self,
            "status_bar",
        ):
            self._show_status(
                "本次未恢复自动保存",
                2600,
            )

        return "deferred"

    def save_template(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translated("保存 FrameDeck 模板"),
            "FrameDeck-Template.json",
            self._translated_file_filter("FrameDeck 模板 (*.json)"),
        )

        if not path:
            return

        if not path.lower().endswith(
            ".json"
        ):
            path += ".json"

        document = create_user_template(
            name=Path(path).stem,
            settings=self.preview_settings(),
            description=(
                "用户保存的自由网格排版模板"
            ),
        )

        Path(path).write_text(
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        if hasattr(self, "status_bar"):
            self._show_status(
                (
                    "模板已保存："
                    f"{Path(path).name}"
                ),
                3000,
            )

    def load_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translated("载入 FrameDeck 模板"),
            "",
            self._translated_file_filter("FrameDeck 模板 (*.json)"),
        )

        if not path:
            return

        try:
            document = load_template_file(
                path
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "模板载入失败",
                str(error),
            )
            return

        self.apply_template_document(
            document
        )


    def apply_settings(
        self,
        data,
        *,
        preserve_template=False,
    ):
        data = dict(data or {})

        template_document = data.get(
            "layout_template"
        )

        if (
            not preserve_template
            and isinstance(
                template_document,
                dict,
            )
            and template_document
        ):
            try:
                active_template = (
                    validate_template_document(
                        template_document
                    )
                )
            except Exception:
                active_template = None

            self._active_template_document = (
                active_template
            )
            self._active_template_id = (
                str(
                    active_template.get(
                        "id",
                        "",
                    )
                )
                if active_template
                else ""
            )

        elif not preserve_template:
            self._active_template_document = None
            self._active_template_id = ""

        self.row_step.setValue(data.get("rows", 2))
        self.col_step.setValue(data.get("cols", 6))
        for combo, value in [(self.page_combo, data.get("page_size", "16:9")),
                             (self.mode_combo, data.get("image_mode", "保持比例"))]:
            idx = self._find_combo_source_text(combo, value)
            if idx >= 0: combo.setCurrentIndex(idx)
        self.title_check.setChecked(
            data.get(
                "show_title",
                False,
            )
        )
        self.title_edit.setText(
            data.get(
                "title_text",
                "",
            )
        )
        self.subtitle_edit.setText(
            ""
        )
        self.title_height_input.setValue(
            data.get(
                "title_height",
                0.9,
            )
        )
        self.logo_edit.setText(
            ""
        )

        self.footer_check.setChecked(
            data.get(
                "show_footer",
                False,
            )
        )
        self.footer_edit.setText(
            data.get(
                "footer_text",
                "",
            )
        )

        self._set_title_controls_enabled(
            self.title_check.isChecked()
        )

        footer_enabled = (
            self.footer_check.isChecked()
        )

        self.footer_check.setVisible(
            True
        )
        self.footer_edit.setEnabled(
            footer_enabled
        )
        self.footer_edit.setVisible(
            True
        )

        self.logo_status_label.hide()
        self.logo_btn.hide()
        self.clear_logo_btn.hide()
        self._refresh_title_card_height()

        self.filename_check.setChecked(data.get("show_filename", False))
        self.index_check.setChecked(data.get("show_index", False))
        self.page_check.setChecked(data.get("show_page_number", True))
        self.border_check.setChecked(data.get("add_border", False))
        self.ml.setValue(data.get("margin_left", 0.6))
        self.mr.setValue(data.get("margin_right", 0.6))
        self.mt.setValue(data.get("margin_top", 0.8))
        self.mb.setValue(data.get("margin_bottom", 0.8))
        self.gx.setValue(data.get("gap_x", 0.25))
        self.gy.setValue(data.get("gap_y", 0.35))
        self.lh.setValue(data.get("label_height", 0.45))
        self._update_template_badge()

    def request_config_save(self):
        """Coalesce rapid preview-driven configuration writes."""
        timer = getattr(self, "_config_save_timer", None)
        if timer is None:
            self.save_config()
            return
        timer.start()

    def save_config(self):
        try:
            timer = getattr(self, "_config_save_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
            data = {
                "language": self._language,
                "folder": self.folder_edit.text().strip(),
                "output": self.output_edit.text().strip(),
                "export_format": self._selected_export_format,
                "theme": self.current_theme_name(),
                "zoom": self.current_zoom_mode(),
                "image_transforms": self.image_transforms,
                "hidden_images": list(self.hidden_images),
                "settings": self.preview_settings(),
                "title_system": (
                    self._title_system_payload()
                ),
                "collapsible_sections": (
                    self._collapsible_state()
                ),
            }
            config_text = json.dumps(data, ensure_ascii=False, indent=2)
            if config_text == self._last_config_text:
                return
            CONFIG_FILE.write_text(config_text, encoding="utf-8")
            self._last_config_text = config_text
        except Exception:
            pass

    def _finish_clean_close(self):
        """
        执行确认关闭后的清理。
        """
        self._remove_autosave_file()
        self.save_config()

        if hasattr(self, "preview_timer"):
            self.preview_timer.stop()

        if hasattr(
            self,
            "autosave_timer",
        ):
            self.autosave_timer.stop()

        if (
            self.ppt_import_worker is not None
            and self.ppt_import_worker.isRunning()
        ):
            self.ppt_import_worker.requestInterruption()
            self.ppt_import_worker.wait(
                600
            )

        if self.ppt_import_progress is not None:
            self.ppt_import_progress.close()
            self.ppt_import_progress.deleteLater()
            self.ppt_import_progress = None

        if hasattr(
            self,
            "_thumbnail_dispatch_timer",
        ):
            self._thumbnail_dispatch_timer.stop()

        if hasattr(
            self,
            "_thumbnail_priority_timer",
        ):
            self._thumbnail_priority_timer.stop()

        if hasattr(
            self,
            "_thumbnail_progress_timer",
        ):
            self._thumbnail_progress_timer.stop()

        if hasattr(
            self,
            "_thumbnail_navigation_flush_timer",
        ):
            self._thumbnail_navigation_flush_timer.stop()

        if hasattr(
            self,
            "_thumbnail_pool",
        ):
            try:
                self._thumbnail_pool.clear()
                self._thumbnail_pool.waitForDone(
                    350
                )
            except Exception:
                pass

        if hasattr(
            self,
            "_page_thumbnail_debounce_timer",
        ):
            self._page_thumbnail_debounce_timer.stop()

        if hasattr(
            self,
            "_page_thumbnail_render_timer",
        ):
            self._page_thumbnail_render_timer.stop()

        if (
            hasattr(
                self,
                "_page_thumbnail_renderer",
            )
            and self._page_thumbnail_renderer
            is not None
        ):
            self._page_thumbnail_renderer.deleteLater()
            self._page_thumbnail_renderer = None

        if hasattr(
            self,
            "slide_thumbnail_bar",
        ):
            self.slide_thumbnail_bar.deleteLater()

    def closeEvent(self, event):
        """
        关闭软件时处理未保存工程：

        保存工程：
            保存成功后关闭；取消文件对话框则继续留在软件中。

        不保存：
            丢弃当前工程和自动保存，下一次启动进入空白工程。

        取消关闭：
            返回软件继续工作。
        """
        if self._close_in_progress:
            event.accept()
            return

        if not self._has_unsaved_project_changes():
            self._close_in_progress = True
            self._finish_clean_close()
            event.accept()
            return

        project_name = (
            Path(
                self.current_project_file
            ).name
            if self.current_project_file
            else "未保存工程"
        )

        message_box = QMessageBox(self)
        message_box.setWindowTitle(
            "保存工程"
        )
        message_box.setIcon(
            QMessageBox.Icon.Warning
        )
        message_box.setText(
            f"“{project_name}”尚未保存。"
        )
        message_box.setInformativeText(
            (
                "关闭软件前是否保存当前工程？\n\n"
                "保存工程会保留图片顺序、页面、模板、"
                "裁切、缩放和位置调整。"
            )
        )

        save_button = message_box.addButton(
            "保存工程",
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = message_box.addButton(
            "不保存",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = message_box.addButton(
            "取消关闭",
            QMessageBox.ButtonRole.RejectRole,
        )

        message_box.setDefaultButton(
            save_button
        )
        message_box.setEscapeButton(
            cancel_button
        )
        message_box.exec()

        clicked = message_box.clickedButton()

        if clicked is save_button:
            if not self.save_project():
                # 用户取消保存路径，或保存发生错误。
                event.ignore()
                return

            self._close_in_progress = True
            self._finish_clean_close()
            event.accept()
            return

        if clicked is discard_button:
            # 明确放弃时删除自动保存并清空工程型配置，
            # 防止下次启动重新载入刚刚放弃的未保存工程。
            if hasattr(
                self,
                "autosave_timer",
            ):
                self.autosave_timer.stop()

            self._remove_autosave_file()
            self._reset_startup_session_to_blank(
                clear_folder=True
            )
            self._close_in_progress = True
            self._finish_clean_close()
            event.accept()
            return

        # 点击“取消关闭”或直接关闭提示窗口。
        event.ignore()


    def load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            config_text = CONFIG_FILE.read_text(encoding="utf-8")
            data = json.loads(config_text)
            self._last_config_text = json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
            self.folder_edit.setText(data.get("folder", ""))
            self.output_edit.setText(data.get("output", ""))
            self._set_export_format(
                data.get("export_format", "pptx")
            )
            self.set_theme_selection(
                data.get("theme", "极光浅色"),
                persist=False,
            )

            self.apply_zoom(
                data.get("zoom", "适应窗口")
            )

            self.image_transforms = {
                str(path): dict(value)
                for path, value in data.get("image_transforms", {}).items()
            }
            self.hidden_images = set(data.get("hidden_images", []))
            self.apply_settings(
                data.get(
                    "settings",
                    {},
                )
            )
            self._load_title_system(
                data.get(
                    "title_system",
                    {},
                )
            )
            self._apply_collapsible_state(
                data.get(
                    "collapsible_sections",
                    {},
                )
            )
        except Exception:
            pass



# ============================================================
# UI-05-45C FIX02 - EVENT FILTER LIST -> CURRENT PAGE DRAG
#
# 目的：
#   不再依赖运行时 monkey-patch Qt 虚函数。
#   使用 QObject.eventFilter 直接接管：
#       右侧列表 鼠标按下/移动 -> 自建 QDrag
#       中央画布 DragEnter/DragMove/Drop -> 当前页移动
#
# 这样可以绕开 Windows + PySide6 下 startDrag / dragEnterEvent
# 动态替换未进入 C++ 虚函数回调的问题。
# ============================================================

_FD_UI0545C_FIX02_MAIN_INIT_ORIGINAL = (
    MainWindow.__init__
)


class _FrameDeckCurrentPageDragFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)

        self.main_window = main_window
        self.image_list = getattr(
            main_window,
            "image_list",
            None,
        )
        self.preview = getattr(
            main_window,
            "preview",
            None,
        )

        self._press_pos = None
        self._drag_active = False

    # --------------------------------------------------------
    # MIME
    # --------------------------------------------------------
    def _mime_rows(self, mime):
        return rows_from_mime(mime)

    def _selected_rows(self):
        if self.image_list is None:
            return []

        rows = sorted(
            {
                self.image_list.row(item)
                for item
                in self.image_list.selectedItems()
                if self.image_list.row(item)
                >= 0
            }
        )

        if rows:
            return rows

        current = self.image_list.currentRow()

        if current >= 0:
            return [current]

        if self._press_pos is not None:
            try:
                index = self.image_list.indexAt(
                    self._press_pos
                )

                if index.isValid():
                    return [index.row()]
            except Exception:
                pass

        return []

    # --------------------------------------------------------
    # 右侧列表：主动建立 QDrag
    # --------------------------------------------------------
    def _start_list_drag(self):
        if (
            self.image_list is None
            or self._drag_active
        ):
            return False

        if not self._selected_rows():
            return False

        self._drag_active = True

        try:
            self.image_list.startDrag(
                Qt.DropAction.CopyAction
                | Qt.DropAction.MoveAction
            )
        finally:
            self._drag_active = False
            self._press_pos = None

            # 现有列表 drop finally 可能恢复 DragDrop 状态；
            # EventFilter 仍作为下一次拖动的第一入口。
            try:
                self.image_list.setAcceptDrops(
                    True
                )
                self.image_list.viewport().setAcceptDrops(
                    True
                )
            except Exception:
                pass

        return True

    # --------------------------------------------------------
    # 中央画布：当前页目标
    # --------------------------------------------------------
    def _main_window_receiver(self):
        return self.main_window

    def _target_at_preview(
        self,
        event,
        *,
        allow_page_fallback=True,
    ):
        preview = self.preview

        if preview is None:
            return -1, None

        try:
            preview._refresh_external_drop_geometry()
        except Exception:
            try:
                preview.repaint()
            except Exception:
                pass

        target_index = -1
        target_rect = None

        try:
            target_index, target_rect = (
                preview._external_target_at(
                    event.position().toPoint()
                )
            )
        except Exception:
            target_index = -1
            target_rect = None

        # 新交互是“拖到当前页”，并不要求一定精确命中某张照片。
        # 若落在中央当前页画布内但不是具体槽位，默认插到当前页末尾。
        if (
            target_index < 0
            and allow_page_fallback
        ):
            try:
                current_page = int(
                    self.main_window
                    ._current_logical_page_index()
                )

                if (
                    self.main_window
                    ._is_blank_page(
                        current_page
                    )
                ):
                    insertion = (
                        self.main_window
                        ._blank_page_visible_insertion_index(
                            current_page
                        )
                    )

                    if insertion is not None:
                        target_index = int(
                            insertion
                        )
                else:
                    _start, end = (
                        self.main_window
                        ._page_visible_range(
                            current_page
                        )
                    )
                    target_index = int(
                        end
                    )
            except Exception:
                target_index = -1

        return (
            int(target_index),
            target_rect,
        )

    def _update_preview_indicator(
        self,
        target_index,
        target_rect,
    ):
        preview = self.preview

        if preview is None:
            return

        try:
            preview._external_drop_target_index = (
                int(target_index)
            )

            if (
                target_rect is not None
                and hasattr(
                    target_rect,
                    "isNull",
                )
                and not target_rect.isNull()
            ):
                preview._external_drop_target_rect = (
                    QRectF(
                        target_rect
                    )
                )
            else:
                preview._external_drop_target_rect = (
                    QRectF()
                )

            preview.update()
        except Exception:
            pass

    def _clear_preview_indicator(self):
        if self.preview is None:
            return

        try:
            self.preview._clear_external_drop_target()
        except Exception:
            try:
                self.preview.update()
            except Exception:
                pass

    # --------------------------------------------------------
    # Event Filter
    # --------------------------------------------------------
    def eventFilter(
        self,
        watched,
        event,
    ):
        from PySide6.QtCore import QEvent

        if getattr(self.main_window, "_close_in_progress", False):
            return False

        try:
            event_type = event.type()
            image_list = self.image_list
            image_viewport = (
                image_list.viewport()
                if image_list is not None
                else None
            )
        except RuntimeError:
            return False

        # ====================================================
        # A. 右侧列表 viewport 鼠标拖动
        # ====================================================
        if (
            image_list is not None
            and watched
            in {
                image_list,
                image_viewport,
            }
        ):
            if (
                event_type
                == QEvent.Type.MouseButtonPress
                and event.button()
                == Qt.MouseButton.LeftButton
            ):
                try:
                    self._press_pos = (
                        event.position().toPoint()
                    )
                except Exception:
                    self._press_pos = None

                # 让 QListWidget 先正常完成选择。
                return False

            if (
                event_type
                == QEvent.Type.MouseButtonRelease
            ):
                self._press_pos = None
                return False

            if (
                event_type
                == QEvent.Type.MouseMove
                and (
                    event.buttons()
                    & Qt.MouseButton.LeftButton
                )
                and self._press_pos is not None
                and not self._drag_active
            ):
                try:
                    current_pos = (
                        event.position().toPoint()
                    )
                    distance = (
                        current_pos
                        - self._press_pos
                    ).manhattanLength()
                except Exception:
                    distance = 0

                if (
                    distance
                    >= QApplication.startDragDistance()
                ):
                    # 直接消费这个 MouseMove，
                    # 不再让 QListWidget 默认 startDrag 接管。
                    self._start_list_drag()
                    return True

        # ====================================================
        # B. 中央 PreviewCanvas 的拖放
        # ====================================================
        if (
            self.preview is not None
            and watched is self.preview
        ):
            rows = self._mime_rows(
                event.mimeData()
            ) if hasattr(
                event,
                "mimeData",
            ) else []

            if not rows:
                return False

            if (
                event_type
                == QEvent.Type.DragEnter
            ):
                try:
                    self.preview.setAcceptDrops(
                        True
                    )
                except Exception:
                    pass

                # 进入中央画布即接受，
                # 不要求 dragEnter 阶段已经命中具体槽位。
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
                event.accept()
                return True

            if (
                event_type
                == QEvent.Type.DragMove
            ):
                target_index, target_rect = (
                    self._target_at_preview(
                        event,
                        allow_page_fallback=True,
                    )
                )

                self._update_preview_indicator(
                    target_index,
                    target_rect,
                )

                # 整个中央当前页都视为有效目标。
                event.setDropAction(
                    Qt.DropAction.CopyAction
                )
                event.accept()
                return True

            if (
                event_type
                == QEvent.Type.DragLeave
            ):
                self._clear_preview_indicator()
                event.accept()
                return True

            if (
                event_type
                == QEvent.Type.Drop
            ):
                target_index, target_rect = (
                    self._target_at_preview(
                        event,
                        allow_page_fallback=True,
                    )
                )

                handled = False

                if (
                    target_index >= 0
                    and hasattr(
                        self.main_window,
                        "handle_image_list_drop_to_current_page",
                    )
                ):
                    try:
                        handled = bool(
                            self.main_window
                            .handle_image_list_drop_to_current_page(
                                rows,
                                target_index,
                            )
                        )
                    except Exception:
                        traceback.print_exc()
                        handled = False

                self._clear_preview_indicator()

                try:
                    self.preview.rearm_external_drop()
                except Exception:
                    try:
                        self.preview.setAcceptDrops(
                            True
                        )
                    except Exception:
                        pass

                if handled:
                    event.setDropAction(
                        Qt.DropAction.CopyAction
                    )
                    event.accept()
                else:
                    event.ignore()

                return True

        return False


def _fd_ui0545c_fix02_install(
    window,
):
    # 避免重复安装。
    if getattr(
        window,
        "_fd_ui0545c_fix02_filter",
        None,
    ) is not None:
        return

    image_list = getattr(
        window,
        "image_list",
        None,
    )
    preview = getattr(
        window,
        "preview",
        None,
    )

    if image_list is None or preview is None:
        return

    drag_filter = (
        _FrameDeckCurrentPageDragFilter(
            window
        )
    )

    window._fd_ui0545c_fix02_filter = (
        drag_filter
    )

    # 鼠标事件实际落在 QListWidget viewport，
    # 两层都安装，避免平台差异。
    image_list.installEventFilter(
        drag_filter
    )
    image_list.viewport().installEventFilter(
        drag_filter
    )

    # PreviewCanvas 是普通 QWidget，
    # 直接拦截其 DragEnter / DragMove / Drop。
    preview.installEventFilter(
        drag_filter
    )
    preview.setAcceptDrops(
        True
    )

    # 保留现有列表接收外部文件与内部排序能力。
    image_list.setAcceptDrops(
        True
    )
    image_list.viewport().setAcceptDrops(
        True
    )

def _fd_ui0545c_fix02_main_init(
    self,
    *args,
    **kwargs,
):
    _FD_UI0545C_FIX02_MAIN_INIT_ORIGINAL(
        self,
        *args,
        **kwargs,
    )

    _fd_ui0545c_fix02_install(
        self
    )


MainWindow.__init__ = (
    _fd_ui0545c_fix02_main_init
)

# ============================================================
# End UI-05-45C FIX02
# ============================================================


# ============================================================
# UI-05-46A - REMOVE GROUP UI + SIMPLIFY PPT IMPORT
# ============================================================
_FD_UI0546A_MAIN_INIT_ORIGINAL = MainWindow.__init__
_FD_UI0546A_CURRENT_PAGINATION_MODE_ORIGINAL = (
    MainWindow._current_pagination_mode
)
_FD_UI0546A_GROUP_MODE_ENABLED_ORIGINAL = (
    MainWindow._group_mode_enabled
)
_FD_UI0546A_GROUP_ID_FOR_VISIBLE_INDEX_ORIGINAL = (
    MainWindow._group_id_for_visible_index
)
_FD_UI0546A_NORMALIZE_IMAGE_GROUPS_ORIGINAL = (
    MainWindow._normalize_image_groups
)
_FD_UI0546A_UPDATE_GROUP_UI_STATE_ORIGINAL = (
    MainWindow._update_group_ui_state
)

def _fd_ui0546a_force_continuous(self):
    try:
        self._pagination_mode = PAGINATION_CONTINUOUS
    except Exception:
        pass
    combo = getattr(self, "pagination_mode_combo", None)
    if combo is not None:
        try:
            index = combo.findData(PAGINATION_CONTINUOUS)
            if index >= 0:
                blocked = combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(blocked)
            combo.hide()
            combo.setEnabled(False)
        except Exception:
            pass

def _fd_ui0546a_hide_group_ui(self):
    for name in (
        "group_mode_hint",
        "group_manager_btn",
        "page_lock_btn",
        "group_lock_btn",
        "lock_status_hint",
        "new_import_group_check",
        "pagination_mode_combo",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            try:
                widget.hide()
                widget.setEnabled(False)
            except Exception:
                pass

def _fd_ui0546a_main_init(self, *args, **kwargs):
    _FD_UI0546A_MAIN_INIT_ORIGINAL(self, *args, **kwargs)
    _fd_ui0546a_hide_group_ui(self)
    _FD_UI0546A_UPDATE_GROUP_UI_STATE_ORIGINAL(self)

def _fd_ui0546a_current_pagination_mode(self):
    return _FD_UI0546A_CURRENT_PAGINATION_MODE_ORIGINAL(self)

def _fd_ui0546a_group_mode_enabled(self):
    return _FD_UI0546A_GROUP_MODE_ENABLED_ORIGINAL(self)

def _fd_ui0546a_should_start_new_import_group(self):
    return False

def _fd_ui0546a_group_id_for_visible_index(self, visible_index):
    return _FD_UI0546A_GROUP_ID_FOR_VISIBLE_INDEX_ORIGINAL(
        self,
        visible_index,
    )

def _fd_ui0546a_normalize_image_groups(self, image_count=None):
    return _FD_UI0546A_NORMALIZE_IMAGE_GROUPS_ORIGINAL(
        self,
        image_count,
    )

def _fd_ui0546a_apply_ppt_import_groups(self, *args, **kwargs):
    return 0

def _fd_ui0546a_update_group_ui_state(self):
    _FD_UI0546A_UPDATE_GROUP_UI_STATE_ORIGINAL(self)
    _fd_ui0546a_hide_group_ui(self)

def _fd_ui0546a_open_group_manager(self):
    _fd_ui0546a_hide_group_ui(self)
    return

def _fd_ui0546a_import_ppt_images(self):
    if self.ppt_import_worker is not None and self.ppt_import_worker.isRunning():
        QMessageBox.information(
            self,
            "PPT图片正在导入",
            "请等待当前PPT图片提取完成，或在进度窗口中取消。",
        )
        return

    ppt_path, _ = QFileDialog.getOpenFileName(
        self,
        "选择要提取图片的PPT",
        "",
        (
            "PowerPoint 文件 (*.pptx *.pptm);;"
            "PowerPoint 演示文稿 (*.pptx);;"
            "启用宏的演示文稿 (*.pptm)"
        ),
    )
    if not ppt_path:
        return

    suffix = Path(ppt_path).suffix.lower()
    if suffix == ".ppt":
        QMessageBox.warning(
            self,
            "暂不支持旧版PPT",
            "旧版 .ppt 是二进制格式。\n\n请先使用WPS或PowerPoint另存为 .pptx，再执行图片导入。",
        )
        return
    if suffix not in SUPPORTED_PPT_EXTENSIONS:
        QMessageBox.warning(self, "文件格式不支持", "当前支持 .pptx 和 .pptm。")
        return

    confirmation = QMessageBox(self)
    confirmation.setWindowTitle("导入PPT图片")
    confirmation.setIcon(QMessageBox.Icon.Information)
    confirmation.setText(
        "请选择PPT图片的导入方式：\n" + str(ppt_path)
    )
    confirmation.setInformativeText(
        "图片始终按‘原PPT页码 → 页面视觉顺序’提取。\n\n"
        "连续导入：\n"
        "提取全部图片后，按当前固定行列连续自动排版，前页有空位时会自动补满。\n\n"
        "保留原PPT页结构：\n"
        "保留原PPT的页面边界；无图片的原页生成空白页。"
        "若某一原页的图片数量超过当前页面容量，会紧接该原页自动续页。\n\n"
        "只提取图片对象；不导入文字、形状、动画、视频和母版。\n"
        "原PPT不会被修改。"
    )

    continuous_button = confirmation.addButton(
        "连续导入", QMessageBox.ButtonRole.AcceptRole
    )
    page_button = confirmation.addButton(
        "保留原PPT页结构", QMessageBox.ButtonRole.ActionRole
    )
    cancel_button = confirmation.addButton(
        "取消", QMessageBox.ButtonRole.RejectRole
    )
    confirmation.setDefaultButton(continuous_button)
    confirmation.setEscapeButton(cancel_button)
    confirmation.exec()

    clicked = confirmation.clickedButton()
    if clicked is cancel_button:
        return

    self._ppt_import_layout_mode = (
        PPT_IMPORT_MODE_PAGE_BY_SLIDE
        if clicked is page_button
        else PPT_IMPORT_MODE_FLAT
    )
    _fd_ui0546a_force_continuous(self)
    self._ppt_import_source = str(ppt_path)

    self.import_ppt_images_button.setEnabled(False)
    self.add_images_primary_button.setEnabled(False)

    progress = QProgressDialog(
        "正在扫描PPT……", "取消导入", 0, 100, self
    )
    progress.setWindowTitle("导入PPT图片")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setValue(0)
    progress.show()

    worker = PPTImportWorker(ppt_path, self)
    worker.progress.connect(self._on_ppt_import_progress)
    worker.finished_ok.connect(self._on_ppt_import_finished)
    worker.failed.connect(self._on_ppt_import_failed)
    worker.cancelled.connect(self._on_ppt_import_cancelled)
    progress.canceled.connect(worker.requestInterruption)

    self.ppt_import_progress = progress
    self.ppt_import_worker = worker
    worker.start()

MainWindow.__init__ = _fd_ui0546a_main_init
MainWindow._current_pagination_mode = _fd_ui0546a_current_pagination_mode
MainWindow._group_mode_enabled = _fd_ui0546a_group_mode_enabled
MainWindow._should_start_new_import_group = _fd_ui0546a_should_start_new_import_group
MainWindow._group_id_for_visible_index = _fd_ui0546a_group_id_for_visible_index
MainWindow._normalize_image_groups = _fd_ui0546a_normalize_image_groups
MainWindow._apply_ppt_import_groups = _fd_ui0546a_apply_ppt_import_groups
MainWindow._update_group_ui_state = _fd_ui0546a_update_group_ui_state
MainWindow.open_group_manager = _fd_ui0546a_open_group_manager
MainWindow.import_ppt_images = _fd_ui0546a_import_ppt_images
# ============================================================
# End UI-05-46A
# ============================================================


# ============================================================
# UI-05-46B - CURRENT PAGE SLOT INSERT + PARTIAL NAV REFRESH
#
# 1. 右侧列表 -> 中央当前页：
#    - 已有照片槽位也显示明确虚线高亮；
#    - 松开时插入到该照片之前，后续照片自动顺延；
#    - 空槽位真正扩展当前页边界，不再“有框但不填入”；
#    - 部分页只按本次实际移入张数扩展，不会把下一页其它照片
#      无条件全部吸进来；
#    - 满页仍按固定行列向后顺延；
#    - 不自动创建空白页。
#
# 2. 顶部导航缩略图：
#    - 每页签名只包含该页真正相关的数据；
#    - 某一页标题/图片/精修变化，不再因为整套标题列表变化
#      导致所有页面缩略图同时重绘。
# ============================================================


# ------------------------------------------------------------
# A. EventFilter：强化中央画布槽位命中
# ------------------------------------------------------------
def _fd_ui0546b_target_at_preview(
    self,
    event,
    *,
    allow_page_fallback=True,
):
    preview = self.preview

    if preview is None:
        return -1, None

    try:
        point = event.position().toPoint()
    except Exception:
        return -1, None

    try:
        preview._refresh_external_drop_geometry()
    except Exception:
        pass

    def find_target():
        # 先使用“外部拖入槽位表”：
        # 它同时包含已有图片槽位和当前页空槽位。
        try:
            for insertion_index, rect in list(
                getattr(
                    preview,
                    "_external_drop_slot_rects",
                    [],
                )
                or []
            ):
                rect = QRectF(rect)

                if rect.contains(point):
                    return (
                        int(insertion_index),
                        rect,
                    )
        except Exception:
            pass

        # 再使用真实图片槽位兜底。
        # 某些版本在拖动刚开始时 external slot 表可能尚未刷新，
        # 但 _slot_rects 已经存在。
        try:
            for absolute_index, rect in list(
                getattr(
                    preview,
                    "_slot_rects",
                    [],
                )
                or []
            ):
                rect = QRectF(rect)

                if rect.contains(point):
                    return (
                        int(absolute_index),
                        rect,
                    )
        except Exception:
            pass

        return -1, None

    target_index, target_rect = find_target()

    # 第一次没有命中时强制重绘一次槽位几何，再重试。
    if target_index < 0:
        try:
            preview.repaint()
        except Exception:
            pass

        target_index, target_rect = find_target()

    # 鼠标在当前页其它区域时仍允许投放：
    # 默认插到当前页末尾，但不显示一个假的槽位框。
    if (
        target_index < 0
        and allow_page_fallback
    ):
        try:
            current_page = int(
                self.main_window
                ._current_logical_page_index()
            )

            if (
                self.main_window
                ._is_blank_page(
                    current_page
                )
            ):
                insertion = (
                    self.main_window
                    ._blank_page_visible_insertion_index(
                        current_page
                    )
                )

                if insertion is not None:
                    target_index = int(
                        insertion
                    )
            else:
                _start, end = (
                    self.main_window
                    ._page_visible_range(
                        current_page
                    )
                )
                target_index = int(end)
        except Exception:
            target_index = -1

    return int(target_index), target_rect


if "_FrameDeckCurrentPageDragFilter" in globals():
    _FrameDeckCurrentPageDragFilter._target_at_preview = (
        _fd_ui0546b_target_at_preview
    )


# ------------------------------------------------------------
# B. PreviewCanvas：在已有照片上也强制绘制插入目标框
# ------------------------------------------------------------
_FD_UI0546B_PREVIEW_PAINT_ORIGINAL = (
    PreviewCanvas.paintEvent
)


def _fd_ui0546b_preview_paint(
    self,
    event,
):
    _FD_UI0546B_PREVIEW_PAINT_ORIGINAL(
        self,
        event,
    )

    try:
        target_index = int(
            getattr(
                self,
                "_external_drop_target_index",
                -1,
            )
        )
        target_rect = QRectF(
            getattr(
                self,
                "_external_drop_target_rect",
                QRectF(),
            )
        )

        if (
            target_index < 0
            or target_rect.isNull()
            or target_rect.width() <= 0
            or target_rect.height() <= 0
        ):
            return

        # 离屏导航渲染器不需要交互高亮。
        if bool(
            getattr(
                self,
                "_navigation_thumbnail_mode",
                False,
            )
        ):
            return

        palette = (
            getattr(
                self,
                "_palette",
                {},
            )
            or {}
        )
        accent = QColor(
            palette.get(
                "accent",
                "#22D3EE",
            )
        )
        fill = QColor(accent)
        fill.setAlpha(58)

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        painter.setBrush(fill)
        painter.setPen(
            QPen(
                accent,
                3,
                Qt.PenStyle.DashLine,
            )
        )
        painter.drawRoundedRect(
            target_rect.adjusted(
                2,
                2,
                -2,
                -2,
            ),
            7,
            7,
        )
        painter.end()

    except Exception:
        # 高亮属于视觉反馈，任何绘制异常都不能影响主画布。
        pass


PreviewCanvas.paintEvent = (
    _fd_ui0546b_preview_paint
)


# ------------------------------------------------------------
# C. 部分页边界：按实际移入数量扩展
# ------------------------------------------------------------
def _fd_ui0546b_replace_boundary(
    self,
    old_boundary,
    new_boundary,
    *,
    page_start,
    capacity,
    image_count,
):
    """
    将当前“未满页”的结束边界向后扩展。

    例如：
        容量4，第一页原来 3 张，边界=3；
        从后页拖入1张 -> 边界扩到4。
    达到满页时不再需要显式边界，让固定行列自然分页。
    """
    old_boundary = int(old_boundary)
    new_boundary = int(new_boundary)
    page_start = int(page_start)
    capacity = max(1, int(capacity))
    image_count = max(0, int(image_count))

    full_boundary = (
        page_start
        + capacity
    )

    changed = False

    for attr_name in (
        "_manual_page_breaks",
        "_blank_fill_page_breaks",
        "_group_page_breaks",
    ):
        raw = getattr(
            self,
            attr_name,
            set(),
        )

        try:
            values = {
                int(value)
                for value in raw
            }
        except Exception:
            values = set()

        if old_boundary not in values:
            continue

        values.discard(
            old_boundary
        )

        # 未达到当前页容量时，保留一个新的明确页面边界；
        # 达到满页后由 rows × cols 的自然容量分页。
        if (
            0
            < new_boundary
            < image_count
            and new_boundary
            < full_boundary
        ):
            values.add(
                new_boundary
            )

        setattr(
            self,
            attr_name,
            values,
        )
        changed = True

    if changed:
        try:
            self._normalize_manual_page_breaks()
        except Exception:
            pass

        try:
            self._normalize_blank_fill_page_breaks()
        except Exception:
            pass

        try:
            self._normalize_group_page_breaks()
        except Exception:
            pass

    return changed


# ------------------------------------------------------------
# D. 右侧列表 -> 当前页：直接完成“移动 + 插入”
# ------------------------------------------------------------
def _fd_ui0546b_current_page_drop(
    self,
    selected_rows,
    target_index=-1,
):
    rows = sorted(
        {
            int(row)
            for row in list(
                selected_rows
                or []
            )
            if (
                0
                <= int(row)
                < self.image_list.count()
            )
        }
    )

    if not rows:
        return False

    # 搜索过滤状态下视觉行号与完整列表不一致，不做隐式重排。
    search = getattr(
        self,
        "image_search",
        None,
    )

    if (
        search is not None
        and str(
            search.text()
        ).strip()
    ):
        if hasattr(
            self,
            "_show_status",
        ):
            self._show_status(
                "请先清除图片搜索，再拖动到中央页面",
                3000,
            )
        return False

    current_page = max(
        0,
        int(
            self._current_logical_page_index()
        ),
    )
    capacity = max(
        1,
        int(
            self._page_capacity()
        ),
    )
    page_was_blank = bool(
        self._is_blank_page(
            current_page
        )
    )

    visible_before = list(
        self.visible_images()
    )

    # 记录操作前“每页真正内容签名”。
    # 这样本次操作结束后只会重绘实际变化的页面。
    page_signatures_before = {}

    try:
        old_page_count = max(
            1,
            int(
                self.preview.page_count()
            ),
        )

        page_signatures_before = self._page_thumbnail_signature_map(
            old_page_count
        )
    except Exception:
        page_signatures_before = dict(
            getattr(
                self,
                "_page_thumbnail_signatures",
                {},
            )
        )

    moved_paths = []

    for row in rows:
        item = self.image_list.item(
            row
        )

        if item is None:
            continue

        path = str(
            item.data(
                Qt.ItemDataRole.UserRole
            )
            or ""
        )

        if not path:
            continue

        # 隐藏图片不参与页面位置计算。
        if path in getattr(
            self,
            "hidden_images",
            set(),
        ):
            continue

        moved_paths.append(
            path
        )

    if not moved_paths:
        return False

    old_visible_index = {
        str(path): index
        for index, path in enumerate(
            visible_before
        )
    }

    if page_was_blank:
        target_visible = (
            self._blank_page_visible_insertion_index(
                current_page
            )
        )

        if target_visible is None:
            return False

        target_visible = int(
            target_visible
        )
        page_start_before = (
            target_visible
        )
        page_end_before = (
            target_visible
        )
        page_used_before = 0

    else:
        (
            page_start_before,
            page_end_before,
        ) = self._page_visible_range(
            current_page
        )

        page_start_before = int(
            page_start_before
        )
        page_end_before = int(
            page_end_before
        )
        page_used_before = max(
            0,
            page_end_before
            - page_start_before,
        )

        # 无论落在已有照片还是空白槽位，都限制在当前页。
        target_visible = max(
            page_start_before,
            min(
                int(target_index),
                page_end_before,
            ),
        )

    # 本次真正从“其它页”移入当前页的图片数量。
    moved_from_outside = 0

    if not page_was_blank:
        for path in moved_paths:
            old_index = (
                old_visible_index.get(
                    path
                )
            )

            if old_index is None:
                continue

            if not (
                page_start_before
                <= int(old_index)
                < page_end_before
            ):
                moved_from_outside += 1

    insert_row = int(
        self._list_row_for_visible_insertion(
            target_visible
        )
    )

    old_items = [
        self.image_list.item(index)
        for index in range(
            self.image_list.count()
        )
    ]
    selected_set = set(
        rows
    )
    moving_items = [
        old_items[row]
        for row in rows
        if (
            0
            <= row
            < len(old_items)
            and old_items[row]
            is not None
        )
    ]

    if not moving_items:
        return False

    remaining_items = [
        item
        for row, item in enumerate(
            old_items
        )
        if (
            row not in selected_set
            and item is not None
        )
    ]

    adjusted_row = (
        insert_row
        - sum(
            1
            for row in rows
            if row < insert_row
        )
    )
    adjusted_row = max(
        0,
        min(
            int(adjusted_row),
            len(
                remaining_items
            ),
        ),
    )

    new_items = (
        remaining_items[
            :adjusted_row
        ]
        + moving_items
        + remaining_items[
            adjusted_row:
        ]
    )

    # 如果当前页未满，本次从其它页移入多少张，
    # 就只扩展多少个槽位；不会把下一页其它照片一起吸进来。
    boundary_changed = False

    if (
        not page_was_blank
        and 0
        <= page_used_before
        < capacity
        and moved_from_outside
        > 0
        and page_end_before
        < len(
            visible_before
        )
    ):
        remaining_slots = max(
            0,
            capacity
            - page_used_before,
        )
        growth = min(
            moved_from_outside,
            remaining_slots,
        )

        if growth > 0:
            new_boundary = (
                page_end_before
                + growth
            )

            boundary_changed = (
                _fd_ui0546b_replace_boundary(
                    self,
                    page_end_before,
                    new_boundary,
                    page_start=(
                        page_start_before
                    ),
                    capacity=capacity,
                    image_count=len(
                        visible_before
                    ),
                )
            )

    order_changed = any(
        left is not right
        for left, right in zip(
            old_items,
            new_items,
        )
    )

    if (
        not order_changed
        and not boundary_changed
        and not page_was_blank
    ):
        # 拖回原位置也视为一次已处理的有效Drop，
        # 避免Qt显示禁止状态。
        return True

    self.push_history(
        "移动图片到当前页"
    )

    list_blocked = (
        self.image_list.blockSignals(
            True
        )
    )
    model = (
        self.image_list.model()
    )
    model_blocked = (
        model.blockSignals(
            True
        )
    )

    try:
        # 只取出项目对象，不复制图片、不重新生成缩略图。
        while (
            self.image_list.count()
            > 0
        ):
            self.image_list.takeItem(
                0
            )

        for item in new_items:
            self.image_list.addItem(
                item
            )

        self.image_list.clearSelection()

        for item in moving_items:
            item.setSelected(
                True
            )

        if moving_items:
            first_row = (
                self.image_list.row(
                    moving_items[0]
                )
            )

            if first_row >= 0:
                self.image_list.setCurrentRow(
                    first_row
                )

    finally:
        model.blockSignals(
            model_blocked
        )
        self.image_list.blockSignals(
            list_blocked
        )

    # 手动空白页：用户主动把图片拖入后，原位转为图片页。
    # 不额外创建任何空白页。
    if page_was_blank:
        self._consume_blank_page_for_images(
            current_page,
            min(
                len(moved_paths),
                capacity,
            ),
        )

    # 在刷新前恢复“操作前”的逐页签名基准。
    # refresh_real_page_thumbnails() 会据此精确判断哪些页真的变化。
    if page_signatures_before:
        self._page_thumbnail_signatures = dict(
            page_signatures_before
        )

    self.refresh_preview()

    page_count = max(
        1,
        int(
            self.preview.page_count()
        ),
    )
    current_page = max(
        0,
        min(
            int(current_page),
            page_count - 1,
        ),
    )

    # 始终停留在用户正在编辑的目标页。
    self._displayed_page_index = (
        current_page
    )
    self.preview.set_page_index(
        current_page
    )

    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if bar is not None:
        try:
            bar.set_current_page(
                current_page
            )
        except Exception:
            pass

    new_visible = list(
        self.visible_images()
    )
    moved_set = set(
        moved_paths
    )
    selected_indices = {
        index
        for index, path in enumerate(
            new_visible
        )
        if path in moved_set
    }

    self.selected_image_indices = (
        selected_indices
    )
    self.selected_image_index = (
        min(
            selected_indices
        )
        if selected_indices
        else -1
    )

    try:
        if hasattr(
            self.preview,
            "set_selected_indices",
        ):
            self.preview.set_selected_indices(
                sorted(
                    selected_indices
                ),
                self.selected_image_index,
                reveal=False,
            )
        else:
            self.preview.set_selected_index(
                self.selected_image_index,
                reveal=False,
            )
        self.preview.update()
    except Exception:
        pass

    # 不清空逐页签名，不调用“全量缩略图刷新”。
    # 由新的 page-local signature 精确刷新真正变化的页面。
    try:
        self.schedule_real_thumbnail_refresh()
    except Exception:
        pass

    if hasattr(
        self,
        "_show_status",
    ):
        if page_was_blank:
            message = (
                f"已将 {len(moved_paths)} 张图片插入第 "
                f"{current_page + 1} 页"
            )
        elif (
            page_used_before
            < capacity
        ):
            message = (
                f"已插入当前第 {current_page + 1} 页 · "
                "空位按实际拖入数量填充"
            )
        else:
            message = (
                f"已插入当前第 {current_page + 1} 页 · "
                "满页内容自动向后顺延"
            )

        self._show_status(
            message,
            3200,
        )

    return True


MainWindow.handle_image_list_drop_to_current_page = (
    _fd_ui0546b_current_page_drop
)




# ============================================================
# End UI-05-46B
# ============================================================


# ============================================================
# UI-05-46C - RESERVED BLANK PAGE FLOW
#
# 空白页新语义：
# 1. 用户手动新建的空白页 = 预留页面位。
# 2. 前一页发生顺延时，如果紧邻下一页是空白页，
#    顺延内容优先进入该空白页，而不是跳过它进入原下一图片页。
# 3. 从其它页把图片拖入空白页时：
#    - 空白页原位置变成独立图片页；
#    - 自动建立前后分页边界；
#    - 不与前页/后页合并。
# 4. 不自动创建新的空白页；需要更多承接页时仍由用户手动新建。
# ============================================================


def _fd_ui0546c_add_segment_boundaries(
    self,
    segment_start,
    segment_end,
):
    """
    把 [segment_start, segment_end) 固定成一个独立图片页段。

    使用 _blank_fill_page_breaks：
    这是现有工程中专门用于“空白页转图片页后保持原页面位置”的
    持久边界集合，会参与保存/撤销/导出。
    """
    image_count = len(
        self.visible_images()
    )

    segment_start = max(
        0,
        min(
            int(segment_start),
            image_count,
        ),
    )
    segment_end = max(
        segment_start,
        min(
            int(segment_end),
            image_count,
        ),
    )

    if (
        0
        < segment_start
        < image_count
    ):
        self._blank_fill_page_breaks.add(
            segment_start
        )

    if (
        0
        < segment_end
        < image_count
    ):
        self._blank_fill_page_breaks.add(
            segment_end
        )

    try:
        self._normalize_blank_fill_page_breaks()
    except Exception:
        pass


def _fd_ui0546c_visible_segment_for_items(
    self,
    items,
):
    """
    返回这些 QListWidgetItem 在当前完整列表中的可见图片段：
        (start, end)

    46B 插入时 moving_items 始终连续插入，因此这里得到的就是
    目标空白页应占用的独立图片范围。
    """
    if not items:
        return None

    first_row = self.image_list.row(
        items[0]
    )

    if first_row < 0:
        return None

    start = int(
        self._visible_index_before_list_row(
            first_row
        )
    )

    visible_count = 0

    for item in items:
        if item is None:
            continue

        path = str(
            item.data(
                Qt.ItemDataRole.UserRole
            )
            or ""
        )

        if (
            path
            and path
            not in self.hidden_images
        ):
            visible_count += 1

    if visible_count <= 0:
        return None

    return (
        start,
        start + visible_count,
    )


def _fd_ui0546c_current_page_drop(
    self,
    selected_rows,
    target_index=-1,
):
    """
    UI-05-46C：
    46B 精确插入基础上增加“预留空白页承接顺延”。
    """
    rows = sorted(
        {
            int(row)
            for row in list(
                selected_rows
                or []
            )
            if (
                0
                <= int(row)
                < self.image_list.count()
            )
        }
    )

    if not rows:
        return False

    search = getattr(
        self,
        "image_search",
        None,
    )

    if (
        search is not None
        and str(
            search.text()
        ).strip()
    ):
        if hasattr(
            self,
            "_show_status",
        ):
            self._show_status(
                "请先清除图片搜索，再拖动到中央页面",
                3000,
            )
        return False

    current_page = max(
        0,
        int(
            self._current_logical_page_index()
        ),
    )
    capacity = max(
        1,
        int(
            self._page_capacity()
        ),
    )
    page_was_blank = bool(
        self._is_blank_page(
            current_page
        )
    )

    # 记录“目标页后面是否紧邻用户预留空白页”。
    #
    # 只有目标本身不是空白页时才判断；
    # 目标空白页走“原位转独立图片页”分支。
    reserved_blank_after = (
        current_page + 1
        if (
            not page_was_blank
            and self._is_blank_page(
                current_page + 1
            )
        )
        else None
    )

    visible_before = list(
        self.visible_images()
    )

    page_signatures_before = {}

    try:
        old_page_count = max(
            1,
            int(
                self.preview.page_count()
            ),
        )

        page_signatures_before = self._page_thumbnail_signature_map(
            old_page_count
        )
    except Exception:
        page_signatures_before = dict(
            getattr(
                self,
                "_page_thumbnail_signatures",
                {},
            )
        )

    moved_paths = []

    for row in rows:
        item = self.image_list.item(
            row
        )

        if item is None:
            continue

        path = str(
            item.data(
                Qt.ItemDataRole.UserRole
            )
            or ""
        )

        if not path:
            continue

        if path in getattr(
            self,
            "hidden_images",
            set(),
        ):
            continue

        moved_paths.append(
            path
        )

    if not moved_paths:
        return False

    old_visible_index = {
        str(path): index
        for index, path in enumerate(
            visible_before
        )
    }

    if page_was_blank:
        target_visible = (
            self._blank_page_visible_insertion_index(
                current_page
            )
        )

        if target_visible is None:
            return False

        target_visible = int(
            target_visible
        )
        page_start_before = (
            target_visible
        )
        page_end_before = (
            target_visible
        )
        page_used_before = 0

    else:
        (
            page_start_before,
            page_end_before,
        ) = self._page_visible_range(
            current_page
        )

        page_start_before = int(
            page_start_before
        )
        page_end_before = int(
            page_end_before
        )
        page_used_before = max(
            0,
            page_end_before
            - page_start_before,
        )

        target_visible = max(
            page_start_before,
            min(
                int(target_index),
                page_end_before,
            ),
        )

    # 统计真正从其它页移入目标页的图片数量。
    moved_from_outside = 0

    if not page_was_blank:
        for path in moved_paths:
            old_index = (
                old_visible_index.get(
                    path
                )
            )

            if old_index is None:
                continue

            if not (
                page_start_before
                <= int(old_index)
                < page_end_before
            ):
                moved_from_outside += 1

    # 本次理论上会从目标页向后挤出的数量。
    #
    # 例如：
    #   容量4，当前已有4张，移入1张 -> overflow=1
    #   容量4，当前已有3张，移入2张 -> overflow=1
    overflow_count = 0

    if not page_was_blank:
        overflow_count = max(
            0,
            (
                page_used_before
                + moved_from_outside
                - capacity
            ),
        )

    insert_row = int(
        self._list_row_for_visible_insertion(
            target_visible
        )
    )

    old_items = [
        self.image_list.item(index)
        for index in range(
            self.image_list.count()
        )
    ]

    selected_set = set(
        rows
    )

    moving_items = [
        old_items[row]
        for row in rows
        if (
            0
            <= row
            < len(old_items)
            and old_items[row]
            is not None
        )
    ]

    if not moving_items:
        return False

    remaining_items = [
        item
        for row, item in enumerate(
            old_items
        )
        if (
            row not in selected_set
            and item is not None
        )
    ]

    adjusted_row = (
        insert_row
        - sum(
            1
            for row in rows
            if row < insert_row
        )
    )

    adjusted_row = max(
        0,
        min(
            int(adjusted_row),
            len(
                remaining_items
            ),
        ),
    )

    new_items = (
        remaining_items[
            :adjusted_row
        ]
        + moving_items
        + remaining_items[
            adjusted_row:
        ]
    )

    boundary_changed = False

    # 继续保留46B的“未满页按实际移入数量扩展”。
    if (
        not page_was_blank
        and 0
        <= page_used_before
        < capacity
        and moved_from_outside
        > 0
        and page_end_before
        < len(
            visible_before
        )
    ):
        remaining_slots = max(
            0,
            capacity
            - page_used_before,
        )
        growth = min(
            moved_from_outside,
            remaining_slots,
        )

        if growth > 0:
            new_boundary = (
                page_end_before
                + growth
            )

            boundary_changed = (
                _fd_ui0546b_replace_boundary(
                    self,
                    page_end_before,
                    new_boundary,
                    page_start=(
                        page_start_before
                    ),
                    capacity=capacity,
                    image_count=len(
                        visible_before
                    ),
                )
            )

    order_changed = (
        len(old_items)
        != len(new_items)
        or any(
            left is not right
            for left, right in zip(
                old_items,
                new_items,
            )
        )
    )

    # 即使顺序恰好没变化，只要后面的预留空白页需要承接，
    # 仍必须继续执行边界转换。
    blank_flow_needed = bool(
        reserved_blank_after
        is not None
        and overflow_count > 0
    )

    if (
        not order_changed
        and not boundary_changed
        and not page_was_blank
        and not blank_flow_needed
    ):
        return True

    self.push_history(
        (
            "图片顺延到预留空白页"
            if blank_flow_needed
            else (
                "图片插入预留空白页"
                if page_was_blank
                else "移动图片到当前页"
            )
        )
    )

    list_blocked = (
        self.image_list.blockSignals(
            True
        )
    )
    model = (
        self.image_list.model()
    )
    model_blocked = (
        model.blockSignals(
            True
        )
    )

    try:
        while (
            self.image_list.count()
            > 0
        ):
            self.image_list.takeItem(
                0
            )

        for item in new_items:
            self.image_list.addItem(
                item
            )

        self.image_list.clearSelection()

        for item in moving_items:
            item.setSelected(
                True
            )

        if moving_items:
            first_row = (
                self.image_list.row(
                    moving_items[0]
                )
            )

            if first_row >= 0:
                self.image_list.setCurrentRow(
                    first_row
                )

    finally:
        model.blockSignals(
            model_blocked
        )
        self.image_list.blockSignals(
            list_blocked
        )

    # ========================================================
    # 情况1：直接把图片拖入“空白页”
    #
    # 旧逻辑只删除 blank_page_position，
    # 所以图片会重新并入前后页面。
    #
    # 新逻辑：
    #   先给移动进来的图片段建立前/后硬边界，
    #   再把 blank placeholder 转成图片页。
    # ========================================================
    if page_was_blank:
        segment = (
            _fd_ui0546c_visible_segment_for_items(
                self,
                moving_items,
            )
        )

        if segment is not None:
            (
                segment_start,
                segment_end,
            ) = segment

            _fd_ui0546c_add_segment_boundaries(
                self,
                segment_start,
                segment_end,
            )

        self._consume_blank_page_for_images(
            current_page,
            min(
                len(moved_paths),
                capacity,
            ),
        )

    # ========================================================
    # 情况2：在“空白页前一页”插入图片并发生顺延
    #
    # 如果紧邻下一页是用户手动空白页：
    #   - 用空白页接住本次被挤出的内容；
    #   - 在挤出段前后建立边界；
    #   - 将空白页原位转换成图片页；
    #   - 原来的下一图片页继续留在其后。
    # ========================================================
    elif blank_flow_needed:
        # 46B处理完成后，当前页应该保持固定容量；
        # 被挤出的内容紧跟在当前页之后。
        try:
            (
                current_start_after,
                current_end_after,
            ) = self._page_visible_range(
                current_page
            )

            current_start_after = int(
                current_start_after
            )
            current_end_after = int(
                current_end_after
            )
        except Exception:
            current_start_after = (
                page_start_before
            )
            current_end_after = min(
                len(
                    self.visible_images()
                ),
                (
                    page_start_before
                    + capacity
                ),
            )

        image_count_after = len(
            self.visible_images()
        )

        reserve_count = min(
            max(
                1,
                int(
                    overflow_count
                ),
            ),
            capacity,
            max(
                0,
                image_count_after
                - current_end_after,
            ),
        )

        if reserve_count > 0:
            overflow_start = (
                current_end_after
            )
            overflow_end = min(
                image_count_after,
                overflow_start
                + reserve_count,
            )

            _fd_ui0546c_add_segment_boundaries(
                self,
                overflow_start,
                overflow_end,
            )

            # 消费的只是用户已经手动创建的这一张空白页。
            # 不会自动再建空白页。
            self._consume_blank_page_for_images(
                reserved_blank_after,
                reserve_count,
            )

    if page_signatures_before:
        self._page_thumbnail_signatures = dict(
            page_signatures_before
        )

    self.refresh_preview()

    page_count = max(
        1,
        int(
            self.preview.page_count()
        ),
    )

    current_page = max(
        0,
        min(
            int(current_page),
            page_count - 1,
        ),
    )

    self._displayed_page_index = (
        current_page
    )
    self.preview.set_page_index(
        current_page
    )

    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if bar is not None:
        try:
            bar.set_current_page(
                current_page
            )
        except Exception:
            pass

    new_visible = list(
        self.visible_images()
    )
    moved_set = set(
        moved_paths
    )

    selected_indices = {
        index
        for index, path in enumerate(
            new_visible
        )
        if path in moved_set
    }

    self.selected_image_indices = (
        selected_indices
    )
    self.selected_image_index = (
        min(
            selected_indices
        )
        if selected_indices
        else -1
    )

    try:
        if hasattr(
            self.preview,
            "set_selected_indices",
        ):
            self.preview.set_selected_indices(
                sorted(
                    selected_indices
                ),
                self.selected_image_index,
                reveal=False,
            )
        else:
            self.preview.set_selected_index(
                self.selected_image_index,
                reveal=False,
            )

        self.preview.update()
    except Exception:
        pass

    try:
        self.schedule_real_thumbnail_refresh()
    except Exception:
        pass

    if hasattr(
        self,
        "_show_status",
    ):
        if page_was_blank:
            message = (
                f"第 {current_page + 1} 页已由空白页转换为独立图片页"
            )
        elif blank_flow_needed:
            message = (
                "顺延图片已进入后方预留空白页，"
                "原下一页内容保持独立"
            )
        elif (
            page_used_before
            < capacity
        ):
            message = (
                f"已插入当前第 {current_page + 1} 页 · "
                "空位按实际拖入数量填充"
            )
        else:
            message = (
                f"已插入当前第 {current_page + 1} 页 · "
                "内容自动向后顺延"
            )

        self._show_status(
            message,
            3600,
        )

    return True


MainWindow.handle_image_list_drop_to_current_page = (
    _fd_ui0546c_current_page_drop
)

# ============================================================
# End UI-05-46C
# ============================================================


# ============================================================
# UI-05-47A - MULTI IMPORT PLACEMENT + PPT BUTTON + PANEL HEADERS
# ============================================================

# A. 左侧功能区标题统一加粗
_FD_UI0547A_BUILD_THEME_QSS_ORIGINAL = build_theme_qss

def _fd_ui0547a_build_theme_qss(name):
    qss = _FD_UI0547A_BUILD_THEME_QSS_ORIGINAL(name)
    c = THEME_META.get(name, THEME_META.get("极光浅色", {}))
    text = c.get("text", "#E6EDF7")
    panel_alt = c.get("panel_alt", "#0D1422")
    selection = c.get("selection", "#123A46")
    border = c.get("border", "#263247")
    accent = c.get("accent", "#22D3EE")
    qss += f"""
/* UI-05-47A */
QWidget#LeftPanel QToolButton#CollapsibleHeader {{
    min-height: 31px;
    max-height: 31px;
    padding: 0 9px;
    border: 1px solid {border};
    border-radius: 7px;
    background-color: {panel_alt};
    color: {text};
    font-size: 12px;
    font-weight: 800;
    text-align: left;
}}
QWidget#LeftPanel QToolButton#CollapsibleHeader:hover {{
    border-color: {accent};
    background-color: {selection};
}}
QWidget#LeftPanel QToolButton#CollapsibleHeader:checked {{
    border-color: {border};
    background-color: {panel_alt};
    color: {text};
    font-weight: 800;
}}
QWidget#LeftPanel QPushButton#ImageImportPrimary,
QWidget#LeftPanel QPushButton#ImageImportSecondary,
QWidget#LeftPanel QToolButton#ImageImportPrimary,
QWidget#LeftPanel QToolButton#ImageImportSecondary {{
    min-height: 32px;
    max-height: 32px;
    font-size: 11px;
    font-weight: 800;
}}
"""
    return qss

build_theme_qss = _fd_ui0547a_build_theme_qss


# B. 导入位置选择

def _fd_ui0547a_has_project_content(self):
    try:
        if self.visible_images():
            return True
    except Exception:
        pass
    try:
        if self._blank_page_positions():
            return True
    except Exception:
        pass
    return False


def _fd_ui0547a_current_page(self):
    try:
        page = int(self._current_logical_page_index())
    except Exception:
        page = int(getattr(self, "_displayed_page_index", self.preview.current_page()))
    total = max(1, int(self.preview.page_count()))
    return max(0, min(page, total - 1))


def _fd_ui0547a_visible_boundary_for_page(self, page_index, *, after):
    page_index = int(page_index)
    if self._is_blank_page(page_index):
        value = self._blank_page_visible_insertion_index(page_index)
        if value is not None:
            return int(value)
    try:
        start, end = self._page_visible_range(page_index)
        return int(end if after else start)
    except Exception:
        return len(self.visible_images())


def _fd_ui0547a_capture_import_plan(self, mode):
    if not _fd_ui0547a_has_project_content(self):
        return {
            "mode": "end",
            "logical_insert_index": 0,
            "visible_insert_index": 0,
            "first_import": True,
            "selected_page": 0,
        }

    current = _fd_ui0547a_current_page(self)
    total = max(1, int(self.preview.page_count()))

    if mode == "before":
        logical = current
        visible = _fd_ui0547a_visible_boundary_for_page(
            self, current, after=False
        )
    elif mode == "after":
        logical = min(total, current + 1)
        visible = _fd_ui0547a_visible_boundary_for_page(
            self, current, after=True
        )
    else:
        mode = "end"
        logical = total
        visible = len(self.visible_images())

    return {
        "mode": mode,
        "logical_insert_index": int(logical),
        "visible_insert_index": int(visible),
        "first_import": False,
        "selected_page": int(current),
    }


# C. 逻辑页面元数据整体后移

def _fd_ui0547a_shift_logical_metadata(
    self,
    logical_insert_index,
    page_count,
    *,
    existing_blank_positions=None,
    new_blank_positions=None,
    first_import=False,
):
    page_count = max(0, int(page_count))
    logical_insert_index = max(0, int(logical_insert_index))
    if existing_blank_positions is None:
        existing_blank_positions = list(self._blank_page_positions())
    if new_blank_positions is None:
        new_blank_positions = []

    if first_import:
        shifted = list(existing_blank_positions)
    else:
        shifted = [
            int(v) + page_count if int(v) >= logical_insert_index else int(v)
            for v in existing_blank_positions
        ]
        for _ in range(page_count):
            try:
                self._shift_page_title_metadata_for_insert(logical_insert_index)
            except Exception:
                break

    self._set_blank_page_positions(
        shifted + [int(v) for v in new_blank_positions]
    )


def _fd_ui0547a_focus_imported_page(self, logical_page_index):
    self.refresh_preview()
    total = max(1, int(self.preview.page_count()))
    target = max(0, min(int(logical_page_index), total - 1))
    self._displayed_page_index = target
    self.preview.set_page_index(target)
    try:
        self.preview.set_selected_index(-1, reveal=False)
    except Exception:
        pass
    self.selected_image_index = -1
    self.selected_image_indices = set()
    bar = getattr(self, "slide_thumbnail_bar", None)
    if bar is not None:
        try:
            bar.set_current_page(target)
        except Exception:
            pass
    try:
        self._force_page_thumbnail_refresh()
    except Exception:
        try:
            self.schedule_real_thumbnail_refresh()
        except Exception:
            pass
    self.refresh_preview()


# D. 普通图片批量插入

def _fd_ui0547a_insert_image_batch(self, paths, plan, *, history_label="添加图片"):
    if not paths or not plan:
        return 0

    start = max(
        0,
        min(
            int(plan.get("visible_insert_index", len(self.visible_images()))),
            len(self.visible_images()),
        ),
    )
    logical = max(0, int(plan.get("logical_insert_index", 0)))
    old_blanks = list(self._blank_page_positions())
    insert_row = int(self._list_row_for_visible_insertion(start))

    inserted = self._insert_external_images(
        paths,
        insert_row,
        history_label,
        consume_compat_blank_page=False,
        start_new_group=False,
        new_group_name="",
        boundary_belongs_to_previous=False,
        replace_blank_page_index=None,
    )
    if not inserted:
        return 0

    end = min(len(self.visible_images()), start + int(inserted))
    _fd_ui0546c_add_segment_boundaries(self, start, end)

    capacity = max(1, int(self._page_capacity()))
    pages_added = max(1, int(math.ceil(int(inserted) / capacity)))
    _fd_ui0547a_shift_logical_metadata(
        self,
        logical,
        pages_added,
        existing_blank_positions=old_blanks,
        first_import=bool(plan.get("first_import", False)),
    )
    _fd_ui0547a_focus_imported_page(self, logical)

    if hasattr(self, "_show_status"):
        where = {
            "before": "选中页之前",
            "after": "选中页之后",
            "end": "最后一页之后",
        }.get(plan.get("mode", "end"), "最后一页之后")
        self._show_status(f"已加入 {inserted} 张图片 · 插入{where}", 3600)
    return int(inserted)


def _fd_ui0547a_add_selected_images(self, paths):
    valid = self._filter_decodable_image_paths(paths, notify=True)
    if not valid:
        return
    plan = _fd_ui0547a_choose_import_plan(self, "本次添加的图片")
    if plan is None:
        return
    _fd_ui0547a_insert_image_batch(self, valid, plan, history_label="添加图片")

MainWindow._add_selected_images = _fd_ui0547a_add_selected_images


# E. PPT独立入口（可重复调用）

def _fd_ui0547a_import_ppt_images(self):
    if self.ppt_import_worker is not None and self.ppt_import_worker.isRunning():
        QMessageBox.information(
            self,
            "PPT图片正在导入",
            "请等待当前PPT图片提取完成，或在进度窗口中取消。",
        )
        return

    ppt_path, _ = QFileDialog.getOpenFileName(
        self,
        "选择要提取图片的PPT",
        "",
        "PowerPoint 文件 (*.pptx *.pptm);;PowerPoint 演示文稿 (*.pptx);;启用宏的演示文稿 (*.pptm)",
    )
    if not ppt_path:
        return

    suffix = Path(ppt_path).suffix.lower()
    if suffix == ".ppt":
        QMessageBox.warning(
            self,
            "暂不支持旧版PPT",
            "旧版 .ppt 是二进制格式。\n\n请先使用WPS或PowerPoint另存为 .pptx，再执行图片导入。",
        )
        return
    if suffix not in SUPPORTED_PPT_EXTENSIONS:
        QMessageBox.warning(self, "文件格式不支持", "当前支持 .pptx 和 .pptm。")
        return

    plan = _fd_ui0547a_choose_import_plan(self, "本次PPT内容")
    if plan is None:
        return

    mode_box = QMessageBox(self)
    mode_box.setWindowTitle("PPT导入方式")
    mode_box.setIcon(QMessageBox.Icon.Information)
    mode_box.setText(f"请选择原PPT页面结构的处理方式：\n{ppt_path}")
    mode_box.setInformativeText(
        "图片按“原页码 → 页面视觉顺序”提取。\n\n"
        "连续导入：把全部图片作为一个独立批次连续排版。\n"
        "保留原PPT页结构：保留原页边界；无图片原页保留为空白页。\n\n"
        "原PPT不会被修改。"
    )
    flat_btn = mode_box.addButton("连续导入", QMessageBox.ButtonRole.AcceptRole)
    page_btn = mode_box.addButton("保留原PPT页结构", QMessageBox.ButtonRole.ActionRole)
    cancel_btn = mode_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    mode_box.setDefaultButton(flat_btn)
    mode_box.setEscapeButton(cancel_btn)
    mode_box.exec()
    clicked = mode_box.clickedButton()
    if clicked is cancel_btn:
        return

    self._ppt_import_layout_mode = (
        PPT_IMPORT_MODE_PAGE_BY_SLIDE if clicked is page_btn else PPT_IMPORT_MODE_FLAT
    )
    self._ppt_import_source = str(ppt_path)
    self._fd_ui0547a_pending_ppt_plan = dict(plan)

    self.import_ppt_images_button.setEnabled(False)
    self.add_images_primary_button.setEnabled(False)

    progress = QProgressDialog("正在扫描PPT……", "取消导入", 0, 100, self)
    progress.setWindowTitle("导入PPT图片")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setValue(0)
    progress.show()

    worker = PPTImportWorker(ppt_path, self)
    worker.progress.connect(self._on_ppt_import_progress)
    worker.finished_ok.connect(self._on_ppt_import_finished)
    worker.failed.connect(self._on_ppt_import_failed)
    worker.cancelled.connect(self._on_ppt_import_cancelled)
    progress.canceled.connect(worker.requestInterruption)
    self.ppt_import_progress = progress
    self.ppt_import_worker = worker
    worker.start()

MainWindow.import_ppt_images = _fd_ui0547a_import_ppt_images


# F. PPT原页结构插入任意位置

def _fd_ui0547a_slide_actual_counts(slide_summaries, inserted_count):
    remaining = max(0, int(inserted_count))
    records = []
    for item in list(slide_summaries or []):
        source_count = len(list(item.get("paths", []) or []))
        if source_count <= 0:
            actual = 0
            source_had_images = False
        else:
            actual = min(source_count, remaining)
            remaining -= actual
            source_had_images = True
        records.append({
            "item": item,
            "actual_count": int(actual),
            "source_had_images": bool(source_had_images),
        })
    if remaining > 0:
        target = next(
            (r for r in reversed(records) if r["source_had_images"]),
            None,
        )
        if target is None:
            target = {
                "item": {"slide_index": len(records) + 1, "paths": []},
                "actual_count": 0,
                "source_had_images": True,
            }
            records.append(target)
        target["actual_count"] += remaining
    return records


def _fd_ui0547a_apply_ppt_structure_at(
    self,
    *,
    plan,
    import_start,
    slide_summaries,
    inserted_count,
    old_blank_positions,
):
    capacity = max(1, int(self._page_capacity()))
    image_count = len(self.visible_images())
    logical_insert = int(plan.get("logical_insert_index", 0))
    records = _fd_ui0547a_slide_actual_counts(slide_summaries, inserted_count)

    total_pages = 0
    for record in records:
        count = int(record["actual_count"])
        total_pages += 1 if count <= 0 else max(1, int(math.ceil(count / capacity)))
    total_pages = max(1, total_pages)

    cursor = int(import_start)
    logical_cursor = logical_insert
    fixed_breaks = set(self._blank_fill_page_breaks)
    new_blanks = []
    overflow_count = 0

    for record in records:
        count = int(record["actual_count"])
        if count <= 0:
            new_blanks.append(logical_cursor)
            logical_cursor += 1
            continue

        if 0 < cursor < image_count:
            fixed_breaks.add(cursor)
        cursor += count
        if 0 < cursor < image_count:
            fixed_breaks.add(cursor)

        pages_for_slide = max(1, int(math.ceil(count / capacity)))
        if pages_for_slide > 1:
            overflow_count += 1
        logical_cursor += pages_for_slide

    self._blank_fill_page_breaks = {
        int(v) for v in fixed_breaks if 0 < int(v) < image_count
    }
    self._normalize_blank_fill_page_breaks()

    # 全空PPT作为第一次导入时，PreviewCanvas自身始终保留一个基础空页。
    # 因此显式空白页少记一张，避免多出第N+1页。
    if (
        bool(plan.get("first_import", False))
        and int(inserted_count) <= 0
        and new_blanks
    ):
        new_blanks = new_blanks[:-1]
        total_pages = max(1, total_pages - 1)

    _fd_ui0547a_shift_logical_metadata(
        self,
        logical_insert,
        total_pages,
        existing_blank_positions=old_blank_positions,
        new_blank_positions=new_blanks,
        first_import=bool(plan.get("first_import", False)),
    )
    return {
        "logical_pages_added": total_pages,
        "new_blank_pages": len(new_blanks),
        "overflow_slide_count": overflow_count,
    }


# G. PPT完成处理：按所选位置插入

def _fd_ui0547a_on_ppt_import_finished(self, result):
    self._close_ppt_import_progress()
    worker = self.ppt_import_worker
    self.ppt_import_worker = None
    if worker is not None:
        worker.deleteLater()

    plan = getattr(self, "_fd_ui0547a_pending_ppt_plan", None)
    self._fd_ui0547a_pending_ppt_plan = None
    if not plan:
        plan = _fd_ui0547a_capture_import_plan(self, "end")

    extracted = list(result.get("extracted", []) or [])
    paths = [str(x.get("path", "") or "") for x in extracted if x.get("path")]
    import_mode = getattr(self, "_ppt_import_layout_mode", PPT_IMPORT_MODE_FLAT)
    slide_summaries = self._ppt_slide_summaries(result)
    start = max(
        0,
        min(
            int(plan.get("visible_insert_index", len(self.visible_images()))),
            len(self.visible_images()),
        ),
    )
    logical = max(0, int(plan.get("logical_insert_index", 0)))
    old_blanks = list(self._blank_page_positions())
    page_result = None
    inserted = 0
    actual_inserted_paths = []

    if not paths and import_mode == PPT_IMPORT_MODE_PAGE_BY_SLIDE and slide_summaries:
        self.push_history("导入PPT页面结构")
        page_result = _fd_ui0547a_apply_ppt_structure_at(
            self,
            plan=plan,
            import_start=start,
            slide_summaries=slide_summaries,
            inserted_count=0,
            old_blank_positions=old_blanks,
        )
        _fd_ui0547a_focus_imported_page(self, logical)
        QMessageBox.information(
            self,
            "PPT页面结构导入完成",
            f"原PPT页数：{len(slide_summaries)}\n新增空白页：{page_result['new_blank_pages']} 页",
        )
        return

    if not paths:
        warnings = list(result.get("warnings", []) or [])
        detail = "\n".join(str(v) for v in warnings[:8]) if warnings else "该PPT中没有发现可提取的图片对象。"
        QMessageBox.information(self, "没有可导入图片", detail)
        return

    insert_row = int(self._list_row_for_visible_insertion(start))
    inserted = self._insert_external_images(
        paths,
        insert_row,
        "导入PPT图片",
        consume_compat_blank_page=False,
        start_new_group=False,
        new_group_name="",
        boundary_belongs_to_previous=False,
        replace_blank_page_index=None,
    )

    if inserted:
        visible_after = list(self.visible_images())
        actual_inserted_paths = list(visible_after[start:start + int(inserted)])

    if inserted and import_mode != PPT_IMPORT_MODE_PAGE_BY_SLIDE:
        end = min(len(self.visible_images()), start + int(inserted))
        _fd_ui0546c_add_segment_boundaries(self, start, end)
        capacity = max(1, int(self._page_capacity()))
        pages_added = max(1, int(math.ceil(int(inserted) / capacity)))
        _fd_ui0547a_shift_logical_metadata(
            self,
            logical,
            pages_added,
            existing_blank_positions=old_blanks,
            first_import=bool(plan.get("first_import", False)),
        )
    elif inserted and import_mode == PPT_IMPORT_MODE_PAGE_BY_SLIDE:
        page_result = _fd_ui0547a_apply_ppt_structure_at(
            self,
            plan=plan,
            import_start=start,
            slide_summaries=slide_summaries,
            inserted_count=inserted,
            old_blank_positions=old_blanks,
        )

    extracted_with_paths = [x for x in extracted if x.get("path")]
    for actual_path, item in zip(actual_inserted_paths, extracted_with_paths):
        transform = self.get_transform(actual_path)
        source_transform = dict(item.get("transform", {}) or {})
        for key in ("zoom", "offset_x", "offset_y", "rotation", "flip_h", "flip_v"):
            if key in source_transform:
                transform[key] = source_transform[key]
        if "crop" in source_transform:
            transform["crop"] = normalize_crop(source_transform.get("crop"))
        self.image_transforms[actual_path] = transform

    if inserted:
        _fd_ui0547a_focus_imported_page(self, logical)

    warnings = list(result.get("warnings", []) or [])
    slide_count = int(result.get("slide_count", 0) or 0)
    skipped_count = int(result.get("skipped_count", 0) or 0)
    output_directory = str(result.get("output_directory", "") or "")

    if hasattr(self, "log_box"):
        self.log_box.append(
            f"PPT图片导入完成：{slide_count}页，提取{len(paths)}张，加入工程{inserted}张"
        )
        if output_directory:
            self.log_box.append("PPT提取文件保存于：" + output_directory)
        for warning in warnings[:20]:
            self.log_box.append("PPT导入提示：" + str(warning))

    where = {
        "before": "选中页之前",
        "after": "选中页之后",
        "end": "最后一页之后",
    }.get(plan.get("mode", "end"), "最后一页之后")
    message = (
        f"PPT页数：{slide_count}\n"
        f"提取图片：{len(paths)} 张\n"
        f"加入工程：{inserted} 张\n"
        f"插入位置：{where}"
    )
    if page_result is not None and import_mode == PPT_IMPORT_MODE_PAGE_BY_SLIDE:
        message += f"\n保留空白页：{page_result['new_blank_pages']} 页"
        if page_result["overflow_slide_count"]:
            message += (
                f"\n有 {page_result['overflow_slide_count']} 个原PPT页面"
                "因图片超过当前容量而自动续页"
            )
    if skipped_count:
        message += f"\n跳过对象：{skipped_count} 个"
    if warnings:
        message += "\n\n部分对象未能完整提取，详细信息已写入日志面板。"
    QMessageBox.information(self, "PPT图片导入完成", message)

MainWindow._on_ppt_import_finished = _fd_ui0547a_on_ppt_import_finished


# H. PPT失败/取消时清除待插入位置
_FD_UI0547A_PPT_FAILED_ORIGINAL = MainWindow._on_ppt_import_failed
_FD_UI0547A_PPT_CANCELLED_ORIGINAL = MainWindow._on_ppt_import_cancelled

def _fd_ui0547a_ppt_failed(self, error):
    self._fd_ui0547a_pending_ppt_plan = None
    return _FD_UI0547A_PPT_FAILED_ORIGINAL(self, error)

def _fd_ui0547a_ppt_cancelled(self):
    self._fd_ui0547a_pending_ppt_plan = None
    return _FD_UI0547A_PPT_CANCELLED_ORIGINAL(self)

MainWindow._on_ppt_import_failed = _fd_ui0547a_ppt_failed
MainWindow._on_ppt_import_cancelled = _fd_ui0547a_ppt_cancelled


# I. PPT按钮固定放在“添加图片”右侧

def _fd_ui0547a_find_layout_for_widget(layout, widget):
    if layout is None:
        return None
    try:
        count = layout.count()
    except Exception:
        return None
    for index in range(count):
        item = layout.itemAt(index)
        if item is None:
            continue
        if item.widget() is widget:
            return layout
        child = item.layout()
        if child is not None:
            found = _fd_ui0547a_find_layout_for_widget(child, widget)
            if found is not None:
                return found
    return None


def _fd_ui0547a_prepare_import_buttons(self):
    add_btn = getattr(self, "add_images_primary_button", None)
    ppt_btn = getattr(self, "import_ppt_images_button", None)
    if add_btn is None:
        return

    if ppt_btn is None:
        ppt_btn = QPushButton("▣  导入PPT图片", add_btn.parentWidget())
        ppt_btn.setObjectName("ImageImportSecondary")
        ppt_btn.setToolTip(
            "从 .pptx / .pptm 中按页码和视觉位置提取图片，并加入当前工程"
        )
        ppt_btn.clicked.connect(self.import_ppt_images)
        self.import_ppt_images_button = ppt_btn

    add_btn.setText("＋  添加图片")
    ppt_btn.setText("▣  导入PPT图片")
    add_btn.setObjectName("ImageImportPrimary")
    ppt_btn.setObjectName("ImageImportSecondary")
    add_btn.show()
    ppt_btn.show()
    add_btn.setEnabled(True)
    ppt_btn.setEnabled(True)

    parent = add_btn.parentWidget()
    root_layout = parent.layout() if parent is not None else None
    add_layout = _fd_ui0547a_find_layout_for_widget(root_layout, add_btn)
    if add_layout is None:
        return
    old_layout = _fd_ui0547a_find_layout_for_widget(root_layout, ppt_btn)
    try:
        if old_layout is not None:
            old_layout.removeWidget(ppt_btn)
    except Exception:
        pass
    try:
        add_index = add_layout.indexOf(add_btn)
        if hasattr(add_layout, "insertWidget"):
            add_layout.insertWidget(add_index + 1, ppt_btn, 1)
        else:
            add_layout.addWidget(ppt_btn)
        if hasattr(add_layout, "setStretch"):
            add_layout.setStretch(add_layout.indexOf(add_btn), 1)
            add_layout.setStretch(add_layout.indexOf(ppt_btn), 1)
    except Exception:
        try:
            add_layout.addWidget(ppt_btn)
        except Exception:
            pass
    ppt_btn.raise_()


_FD_UI0547A_MAINWINDOW_INIT_ORIGINAL = MainWindow.__init__

def _fd_ui0547a_mainwindow_init(self, *args, **kwargs):
    _FD_UI0547A_MAINWINDOW_INIT_ORIGINAL(self, *args, **kwargs)
    self._fd_ui0547a_pending_ppt_plan = None
    _fd_ui0547a_prepare_import_buttons(self)

MainWindow.__init__ = _fd_ui0547a_mainwindow_init

# ============================================================
# End UI-05-47A
# ============================================================


# ============================================================
# UI-05-47B - COMPACT IMPORT PROMPT + TOP IMPORT PAIR + CLEAR LEFT PANEL
#
# 1. 二次导入位置提示按钮缩短：
#       插入尾部 / 插入之后 / 插入之前 / 取消
# 2. 顶部导入区域恢复到 UI-05-45A 原位置：
#       [＋ 添加图片] [▣ 导入PPT]
#    两个真正独立按钮，并排、同高、醒目。
# 3. 左侧五个功能区标题：
#       页面布局 / 批量标题 / 布局间距 / 图片调整 / 页脚与显示
#    统一字体、字号、粗细、高度；内部文字同步提高可读性。
# ============================================================


# ------------------------------------------------------------
# A. 二次/多次导入：简化位置提示
# ------------------------------------------------------------
def _fd_ui0547b_choose_import_plan(
    self,
    source_label,
):
    if not _fd_ui0547a_has_project_content(
        self
    ):
        return (
            _fd_ui0547a_capture_import_plan(
                self,
                "end",
            )
        )

    current_page = (
        _fd_ui0547a_current_page(
            self
        )
    )

    box = QMessageBox(self)
    box.setWindowTitle(
        "选择插入位置"
    )
    box.setIcon(
        QMessageBox.Icon.Information
    )
    box.setText(
        (
            f"{source_label}插入位置\n"
            f"当前选中：第 {current_page + 1} 页"
        )
    )
    box.setInformativeText(
        (
            "新导入内容作为独立页面插入，"
            "原有页面保持顺序整体后移。"
        )
    )

    # 按钮文字故意缩短，避免窄窗口 / Windows DPI 缩放时被截断。
    end_button = box.addButton(
        "插入尾部",
        QMessageBox.ButtonRole.AcceptRole,
    )
    after_button = box.addButton(
        "插入之后",
        QMessageBox.ButtonRole.ActionRole,
    )
    before_button = box.addButton(
        "插入之前",
        QMessageBox.ButtonRole.ActionRole,
    )
    cancel_button = box.addButton(
        "取消",
        QMessageBox.ButtonRole.RejectRole,
    )

    for button in (
        end_button,
        after_button,
        before_button,
        cancel_button,
    ):
        try:
            button.setMinimumWidth(92)
            button.setMinimumHeight(36)
        except Exception:
            pass

    box.setDefaultButton(
        end_button
    )
    box.setEscapeButton(
        cancel_button
    )
    box.exec()

    clicked = box.clickedButton()

    if clicked is cancel_button:
        return None

    if clicked is before_button:
        mode = "before"
    elif clicked is after_button:
        mode = "after"
    else:
        mode = "end"

    return (
        _fd_ui0547a_capture_import_plan(
            self,
            mode,
        )
    )


# 47A 的添加图片和PPT入口均在运行时查找这个全局函数，
# 因此直接替换即可，同时保留已经测试通过的三种真实插入逻辑。
_fd_ui0547a_choose_import_plan = (
    _fd_ui0547b_choose_import_plan
)


# ------------------------------------------------------------
# B. 顶部：恢复两个真正独立的导入按钮
# ------------------------------------------------------------
def _fd_ui0547b_find_command_layout(
    self,
):
    """
    优先从“更多工具”按钮寻找顶部 CommandBar。
    UI-05-45A 中原导入按钮就在 more_tools_button 后面的分隔线之后。
    """
    more_button = getattr(
        self,
        "more_tools_button",
        None,
    )

    if more_button is not None:
        parent = (
            more_button.parentWidget()
        )

        if parent is not None:
            layout = parent.layout()

            if layout is not None:
                return layout

    # 兼容兜底：从旧导入按钮所在父布局寻找。
    old_button = getattr(
        self,
        "add_images_primary_button",
        None,
    )

    if old_button is not None:
        parent = old_button.parentWidget()

        if parent is not None:
            layout = parent.layout()

            if layout is not None:
                return layout

    return None


def _fd_ui0547b_remove_widget_from_layout(
    layout,
    widget,
):
    if (
        layout is None
        or widget is None
    ):
        return

    try:
        layout.removeWidget(
            widget
        )
    except Exception:
        pass

    try:
        widget.hide()
    except Exception:
        pass


def _fd_ui0547b_import_insert_index(
    self,
    layout,
):
    """
    找到 UI-05-45A 原导入区：
        更多工具 -> 小间距 -> ToolbarDivider -> 小间距 -> 导入按钮

    将两个新按钮插到该分隔线之后。
    """
    more_button = getattr(
        self,
        "more_tools_button",
        None,
    )

    if more_button is None:
        return max(
            0,
            layout.count() // 2,
        )

    more_index = layout.indexOf(
        more_button
    )

    if more_index < 0:
        return max(
            0,
            layout.count() // 2,
        )

    divider_index = -1

    for index in range(
        more_index + 1,
        layout.count(),
    ):
        item = layout.itemAt(
            index
        )

        if item is None:
            continue

        widget = item.widget()

        if (
            widget is not None
            and isinstance(
                widget,
                QFrame,
            )
            and widget.objectName()
            == "ToolbarDivider"
        ):
            divider_index = index
            break

        # 到了右侧 badge / stretch 区就不再继续向后寻找。
        if (
            widget is getattr(
                self,
                "header_layout_badge",
                None,
            )
        ):
            break

    if divider_index >= 0:
        # 原代码 divider 后还有一个 2px spacing。
        return min(
            layout.count(),
            divider_index + 2,
        )

    return min(
        layout.count(),
        more_index + 1,
    )


def _fd_ui0547b_build_top_import_pair(
    self,
):
    layout = (
        _fd_ui0547b_find_command_layout(
            self
        )
    )

    if layout is None:
        return

    old_add = getattr(
        self,
        "add_images_primary_button",
        None,
    )
    old_ppt = getattr(
        self,
        "import_ppt_images_button",
        None,
    )

    # 47A 基于 45A 时，这两个引用原本可能仍指向同一个 QToolButton。
    old_widgets = []

    for widget in (
        old_add,
        old_ppt,
    ):
        if (
            widget is not None
            and widget not in old_widgets
        ):
            old_widgets.append(
                widget
            )

    for widget in old_widgets:
        _fd_ui0547b_remove_widget_from_layout(
            layout,
            widget,
        )

    insert_index = (
        _fd_ui0547b_import_insert_index(
            self,
            layout,
        )
    )

    image_button = QToolButton(
        layout.parentWidget()
        if hasattr(
            layout,
            "parentWidget",
        )
        else self
    )
    image_button.setObjectName(
        "TopImageImportButton"
    )
    image_button.setText(
        "＋  添加图片"
    )
    image_button.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextOnly
    )
    image_button.setMinimumSize(
        108,
        36,
    )
    image_button.setMaximumWidth(
        128
    )
    image_button.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
    image_button.setToolTip(
        "添加一张或多张图片"
    )
    image_button.clicked.connect(
        self.add_images
    )

    ppt_button = QToolButton(
        layout.parentWidget()
        if hasattr(
            layout,
            "parentWidget",
        )
        else self
    )
    ppt_button.setObjectName(
        "TopPptImportButton"
    )
    ppt_button.setText(
        "▣  导入PPT"
    )
    ppt_button.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextOnly
    )
    ppt_button.setMinimumSize(
        104,
        36,
    )
    ppt_button.setMaximumWidth(
        124
    )
    ppt_button.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
    ppt_button.setToolTip(
        "从 PPTX / PPTM 中提取图片并插入工程"
    )
    ppt_button.clicked.connect(
        self.import_ppt_images
    )

    try:
        layout.insertWidget(
            insert_index,
            image_button,
        )
        layout.insertWidget(
            insert_index + 1,
            ppt_button,
        )
    except Exception:
        layout.addWidget(
            image_button
        )
        layout.addWidget(
            ppt_button
        )

    self.add_images_primary_button = (
        image_button
    )
    self.import_ppt_images_button = (
        ppt_button
    )

    # 旧45A分体导入菜单不再需要在界面上承担入口。
    try:
        self.import_menu.clear()
    except Exception:
        pass

    for widget in old_widgets:
        try:
            widget.deleteLater()
        except Exception:
            pass


# ------------------------------------------------------------
# C. 左侧功能区：直接统一字体，不再只依赖QSS
# ------------------------------------------------------------
def _fd_ui0547b_apply_left_panel_fonts(
    self,
):
    from PySide6.QtGui import QFont

    left = getattr(
        self,
        "left_panel",
        None,
    )

    if left is None:
        left = self.findChild(
            QWidget,
            "LeftPanel",
        )

    if left is None:
        return

    # 整个左侧基础文字略加粗，解决当前浅色主题下偏细的问题。
    for label in left.findChildren(
        QLabel
    ):
        try:
            font = label.font()
            font.setFamily(
                "Microsoft YaHei UI"
            )
            font.setWeight(
                QFont.Weight.DemiBold
            )
            label.setFont(font)
        except Exception:
            pass

    for checkbox in left.findChildren(
        QCheckBox
    ):
        try:
            font = checkbox.font()
            font.setFamily(
                "Microsoft YaHei UI"
            )
            font.setWeight(
                QFont.Weight.DemiBold
            )
            checkbox.setFont(font)
        except Exception:
            pass

    # 五个折叠功能区标题全部使用完全相同的字体参数。
    # 不按当前语言筛选，避免中英文切换后保留旧版 17px 字体。
    for button in left.findChildren(
        QToolButton
    ):
        if (
            button.objectName()
            != "CollapsibleHeader"
        ):
            continue

        try:
            font = button.font()
            font.setFamily(
                "Microsoft YaHei UI"
            )
            # 使用像素字号避免 pointSize == -1 的字体警告。
            font.setPixelSize(
                12
            )
            font.setWeight(
                QFont.Weight.DemiBold
            )
            button.setFont(
                font
            )
            button.setMinimumHeight(
                36
            )
            button.setMaximumHeight(
                36
            )
        except Exception:
            pass

    # 内容里的普通按钮也统一稍加粗，但保持层级低于功能区标题。
    for button in left.findChildren(
        QPushButton
    ):
        try:
            font = button.font()
            font.setFamily(
                "Microsoft YaHei UI"
            )
            font.setWeight(
                QFont.Weight.DemiBold
            )
            button.setFont(
                font
            )
        except Exception:
            pass


# ------------------------------------------------------------
# D. 样式：顶部双导入按钮 + 统一左侧标题
# ------------------------------------------------------------
_FD_UI0547B_BUILD_THEME_QSS_ORIGINAL = (
    build_theme_qss
)


def _fd_ui0547b_build_theme_qss(
    name,
):
    qss = (
        _FD_UI0547B_BUILD_THEME_QSS_ORIGINAL(
            name
        )
    )

    c = THEME_META.get(
        name,
        THEME_META.get(
            "极光浅色",
            {},
        ),
    )

    accent = c.get(
        "accent",
        "#059669",
    )
    accent_hover = c.get(
        "accent_hover",
        accent,
    )
    accent_text = c.get(
        "accent_text",
        "#FFFFFF",
    )
    text = c.get(
        "text",
        "#16352A",
    )
    panel = c.get(
        "panel",
        "#FFFFFF",
    )
    panel_alt = c.get(
        "panel_alt",
        "#F5FBF8",
    )
    selection = c.get(
        "selection",
        "#DCF5E9",
    )
    border = c.get(
        "border",
        "#CDE6D9",
    )
    border_strong = c.get(
        "border_strong",
        "#B7D7C7",
    )

    qss += f"""
/* =========================================================
   UI-05-47B Top Import Pair
   ========================================================= */

QToolButton#TopImageImportButton {{
    min-height: 36px;
    max-height: 36px;
    padding: 0 14px;
    border: 1px solid {accent};
    border-radius: 9px;
    background-color: {accent};
    color: {accent_text};
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 800;
}}

QToolButton#TopImageImportButton:hover {{
    background-color: {accent_hover};
    border-color: {accent_hover};
}}

QToolButton#TopImageImportButton:pressed {{
    padding-top: 2px;
}}

QToolButton#TopPptImportButton {{
    min-height: 36px;
    max-height: 36px;
    padding: 0 14px;
    border: 2px solid {accent};
    border-radius: 9px;
    background-color: {selection};
    color: {text};
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 800;
}}

QToolButton#TopPptImportButton:hover {{
    background-color: {accent};
    color: {accent_text};
    border-color: {accent};
}}

QToolButton#TopPptImportButton:pressed {{
    background-color: {accent_hover};
    color: {accent_text};
}}

/* =========================================================
   UI-05-47B Unified Left Functional Area
   ========================================================= */

QWidget#LeftPanel QToolButton#CollapsibleHeader {{
    min-height: 40px;
    max-height: 40px;
    padding: 0 12px;
    border: 1px solid {border};
    border-radius: 9px;
    background-color: {panel_alt};
    color: {text};
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
    font-weight: 800;
    text-align: left;
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:hover {{
    background-color: {selection};
    border-color: {accent};
    color: {text};
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:checked {{
    background-color: {panel_alt};
    border-color: {border_strong};
    color: {text};
    font-weight: 800;
}}

QWidget#LeftPanel QLabel {{
    font-family: "Microsoft YaHei UI";
    font-weight: 600;
}}

QWidget#LeftPanel QCheckBox {{
    font-family: "Microsoft YaHei UI";
    font-weight: 600;
}}

QWidget#LeftPanel QPushButton {{
    font-family: "Microsoft YaHei UI";
    font-weight: 600;
}}
"""

    return qss


build_theme_qss = (
    _fd_ui0547b_build_theme_qss
)


# ------------------------------------------------------------
# E. MainWindow初始化后修正真实控件结构
# ------------------------------------------------------------
_FD_UI0547B_MAIN_INIT_ORIGINAL = (
    MainWindow.__init__
)


def _fd_ui0547b_main_init(
    self,
    *args,
    **kwargs,
):
    _FD_UI0547B_MAIN_INIT_ORIGINAL(
        self,
        *args,
        **kwargs,
    )

    _fd_ui0547b_build_top_import_pair(
        self
    )
    _fd_ui0547b_apply_left_panel_fonts(
        self
    )

    # 新按钮在初始化最后阶段创建，重新让当前主题QSS应用一次。
    try:
        theme_name = (
            self.current_theme_name()
        )

        self.setStyleSheet(
            build_theme_qss(
                theme_name
            )
        )
    except Exception:
        try:
            self.style().unpolish(
                self
            )
            self.style().polish(
                self
            )
        except Exception:
            pass


MainWindow.__init__ = (
    _fd_ui0547b_main_init
)

# ============================================================
# End UI-05-47B
# ============================================================


# ============================================================
# UI-05-48A - MULTI PAGE DELETE + NAV CACHE STABILITY
#
# 1. 顶部导航多选页面统一删除
# 2. Delete / Backspace 在页面导航聚焦时删除“所选页面”
# 3. 删除前先原位移除对应缩略图卡片，避免 refresh_preview
#    因页数变化而把整个导航栏重建为空白占位图
# 4. 删除页之后，仅让受影响位置及后续页面后台重绘；
#    已有缩略图先保留显示，不出现整栏闪白
# ============================================================


_FD_UI0548A_DELETE_PAGE_ORIGINAL = (
    MainWindow.on_thumbnail_delete_page
)
_FD_UI0548A_SHORTCUT_DELETE_PAGE_ORIGINAL = (
    MainWindow.shortcut_delete_current_page
)
_FD_UI0548A_MAIN_INIT_ORIGINAL = (
    MainWindow.__init__
)


def _fd_ui0548a_selected_nav_pages(
    self,
):
    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if bar is None:
        return []

    getter = getattr(
        bar,
        "selected_pages",
        None,
    )

    if callable(getter):
        try:
            return sorted(
                {
                    int(value)
                    for value in getter()
                }
            )
        except Exception:
            pass

    page_list = getattr(
        bar,
        "page_list",
        None,
    )

    if page_list is None:
        return []

    rows = []

    try:
        for item in page_list.selectedItems():
            row = page_list.row(
                item
            )

            if row >= 0:
                rows.append(
                    row
                )
    except Exception:
        return []

    return sorted(
        set(rows)
    )


def _fd_ui0548a_preflight_delete_pages(
    self,
    page_indices,
):
    preview = getattr(
        self,
        "preview",
        None,
    )

    if preview is None:
        return None

    try:
        total = max(
            1,
            int(
                preview.page_count()
            ),
        )
    except Exception:
        return None

    pages = sorted(
        {
            int(page)
            for page in (
                page_indices
                or []
            )
            if (
                0
                <= int(page)
                < total
            )
        }
    )

    if not pages:
        return None

    if total <= 1:
        QMessageBox.information(
            self,
            "无法删除",
            "工程中至少需要保留一个页面。",
        )
        return None

    if len(pages) >= total:
        QMessageBox.information(
            self,
            "无法删除",
            (
                "工程中至少需要保留一个页面。\n"
                "请取消选择至少一页后再删除。"
            ),
        )
        return None

    locked_pages = []

    for page in pages:
        try:
            is_blank = bool(
                self._is_blank_page(
                    page
                )
            )
        except Exception:
            is_blank = False

        if is_blank:
            continue

        checker = getattr(
            self,
            "_page_lock_meta_for_logical_page",
            None,
        )

        if not callable(
            checker
        ):
            continue

        try:
            if checker(page):
                locked_pages.append(
                    page
                )
        except Exception:
            pass

    if locked_pages:
        display = "、".join(
            str(page + 1)
            for page in locked_pages[:12]
        )

        if (
            len(locked_pages)
            > 12
        ):
            display += "……"

        QMessageBox.information(
            self,
            "页面已锁定",
            (
                "所选页面中包含已锁定页面："
                f"{display}\n"
                "请先解锁相关页面或分组，再执行删除。"
            ),
        )
        return None

    return pages


def _fd_ui0548a_cancel_old_nav_render_queue(
    self,
):
    timer = getattr(
        self,
        "_page_thumbnail_render_timer",
        None,
    )

    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass

    try:
        self._page_thumbnail_render_queue = []
    except Exception:
        pass

    # 让正在等待的旧代次失效。
    if hasattr(
        self,
        "_page_thumbnail_refresh_generation",
    ):
        try:
            self._page_thumbnail_refresh_generation += 1
        except Exception:
            pass


def _fd_ui0548a_invalidate_thumbnail_state_after(
    self,
    page_index,
):
    """
    删除页面后：
    - 删除点之前的页面内容和页码都没有变化，可继续复用签名；
    - 删除点及之后页面的逻辑页码发生变化，需要后台重新绘制。
    """
    page_index = max(
        0,
        int(page_index),
    )

    for name in (
        "_page_thumbnail_signatures",
        "_page_thumbnail_target_signatures",
    ):
        mapping = getattr(
            self,
            name,
            None,
        )

        if not isinstance(
            mapping,
            dict,
        ):
            continue

        kept = {}

        for key, value in mapping.items():
            try:
                index = int(key)
            except (
                TypeError,
                ValueError,
            ):
                continue

            if index < page_index:
                kept[index] = value

        setattr(
            self,
            name,
            kept,
        )

    # 全局签名强制重新核对，但不会清掉导航栏已有图标。
    self._last_real_thumbnail_signature = (
        None
    )
    self._pending_real_thumbnail_signature = (
        None
    )


def _fd_ui0548a_prepare_nav_for_delete(
    self,
    page_index,
    target_page,
):
    _fd_ui0548a_cancel_old_nav_render_queue(
        self
    )
    _fd_ui0548a_invalidate_thumbnail_state_after(
        self,
        page_index,
    )

    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if bar is None:
        return

    remover = getattr(
        bar,
        "remove_pages",
        None,
    )

    if callable(remover):
        try:
            remover(
                [page_index],
                current_index=target_page,
            )
            return
        except Exception as error:
            print(
                "[UI-05-48A nav remove error]",
                error,
            )


def _fd_ui0548a_delete_one_stable(
    self,
    page_index,
):
    preview = getattr(
        self,
        "preview",
        None,
    )

    if preview is None:
        return

    try:
        total = max(
            1,
            int(
                preview.page_count()
            ),
        )
    except Exception:
        return

    pages = (
        _fd_ui0548a_preflight_delete_pages(
            self,
            [page_index],
        )
    )

    if not pages:
        return

    page_index = pages[0]
    target_page = min(
        page_index,
        max(
            0,
            total - 2,
        ),
    )

    # 先把对应导航卡片原位拿掉。
    # 这样原删除逻辑 refresh_preview() 时，导航页数已经与新数据一致，
    # 不会触发 set_pages([None] * count) 的整栏重建。
    _fd_ui0548a_prepare_nav_for_delete(
        self,
        page_index,
        target_page,
    )

    return _FD_UI0548A_DELETE_PAGE_ORIGINAL(
        self,
        page_index,
    )


def _fd_ui0548a_delete_pages(
    self,
    page_indices,
):
    """
    一次撤销记录删除多页。

    使用倒序删除，保证前面页面的逻辑索引在删除过程中保持有效。
    每一步仍复用已经稳定的单页删除数据逻辑。
    """
    pages = (
        _fd_ui0548a_preflight_delete_pages(
            self,
            page_indices,
        )
    )

    if not pages:
        return

    if len(pages) == 1:
        return _fd_ui0548a_delete_one_stable(
            self,
            pages[0],
        )

    preview = getattr(
        self,
        "preview",
        None,
    )

    if preview is None:
        return

    _fd_ui0548a_cancel_old_nav_render_queue(
        self
    )

    # 多页删除只建立一条撤销记录。
    self.push_history(
        f"删除 {len(pages)} 个页面"
    )

    old_refresh_suspended = bool(
        getattr(self, "_thumbnail_refresh_suspended", False)
    )
    self._thumbnail_refresh_suspended = True
    self._fd_ui0548a_batch_delete = (
        True
    )

    deleted_count = 0

    try:
        # 倒序：删除后面的页不会改变前面待删页的索引。
        for page_index in sorted(
            pages,
            reverse=True,
        ):
            try:
                current_total = max(
                    1,
                    int(
                        preview.page_count()
                    ),
                )
            except Exception:
                break

            if current_total <= 1:
                break

            target_page = min(
                page_index,
                max(
                    0,
                    current_total - 2,
                ),
            )

            _fd_ui0548a_prepare_nav_for_delete(
                self,
                page_index,
                target_page,
            )

            before = current_total

            _FD_UI0548A_DELETE_PAGE_ORIGINAL(
                self,
                page_index,
                record_history=False,
            )

            try:
                after = max(
                    1,
                    int(
                        preview.page_count()
                    ),
                )
            except Exception:
                after = before

            if after < before:
                deleted_count += (
                    before - after
                )

    finally:
        self._fd_ui0548a_batch_delete = (
            False
        )
        self._thumbnail_refresh_suspended = old_refresh_suspended

    try:
        new_count = max(
            1,
            int(
                preview.page_count()
            ),
        )
    except Exception:
        new_count = 1

    target_page = min(
        min(pages),
        new_count - 1,
    )
    target_page = max(
        0,
        target_page,
    )

    self._displayed_page_index = (
        target_page
    )

    try:
        preview.set_page_index(
            target_page
        )
        preview.set_selected_index(
            -1,
            reveal=False,
        )
    except Exception:
        pass

    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if bar is not None:
        try:
            bar.set_current_page(
                target_page
            )
        except Exception:
            pass

    # 最后只启动一次缩略图后台刷新。
    self._force_page_thumbnail_refresh()
    self.refresh_preview()

    message = (
        f"已删除 {deleted_count or len(pages)} 页"
    )

    if hasattr(
        self,
        "_show_status",
    ):
        try:
            self._show_status(
                message,
                3000,
            )
            return
        except Exception:
            pass

    if hasattr(
        self,
        "status_bar",
    ):
        self.status_bar.showMessage(
            message,
            3000,
        )


def _fd_ui0548a_on_thumbnail_delete_page(
    self,
    page_index,
):
    # 右键“删除所选页面”仍复用原来的 deletePageRequested(int) 信号。
    # 如果当前导航是多选，就在 MainWindow 层自动升级为批量删除。
    if not getattr(
        self,
        "_fd_ui0548a_batch_delete",
        False,
    ):
        selected = (
            _fd_ui0548a_selected_nav_pages(
                self
            )
        )

        try:
            page_value = int(
                page_index
            )
        except Exception:
            page_value = -1

        if (
            len(selected) > 1
            and page_value in selected
        ):
            return _fd_ui0548a_delete_pages(
                self,
                selected,
            )

    return _fd_ui0548a_delete_one_stable(
        self,
        page_index,
    )


def _fd_ui0548a_shortcut_delete_current_page(
    self,
):
    if self._focus_is_text_editor():
        return

    selected = (
        _fd_ui0548a_selected_nav_pages(
            self
        )
    )

    if len(selected) > 1:
        return _fd_ui0548a_delete_pages(
            self,
            selected,
        )

    if len(selected) == 1:
        return _fd_ui0548a_on_thumbnail_delete_page(
            self,
            selected[0],
        )

    return _FD_UI0548A_SHORTCUT_DELETE_PAGE_ORIGINAL(
        self
    )


def _fd_ui0548a_main_init(
    self,
    *args,
    **kwargs,
):
    _FD_UI0548A_MAIN_INIT_ORIGINAL(
        self,
        *args,
        **kwargs,
    )

    bar = getattr(
        self,
        "slide_thumbnail_bar",
        None,
    )

    if (
        bar is not None
        and hasattr(
            bar,
            "page_list",
        )
    ):
        try:
            bar.page_list.setToolTip(
                (
                    "单击切换页面；"
                    "Ctrl+左键增减多选；"
                    "Shift+左键连续多选；"
                    "Delete删除所选页；"
                    "单页可拖动排序"
                )
            )
        except Exception:
            pass


MainWindow.on_thumbnail_delete_pages = (
    _fd_ui0548a_delete_pages
)
MainWindow.on_thumbnail_delete_page = (
    _fd_ui0548a_on_thumbnail_delete_page
)
MainWindow.shortcut_delete_current_page = (
    _fd_ui0548a_shortcut_delete_current_page
)
MainWindow.__init__ = (
    _fd_ui0548a_main_init
)

# ============================================================
# End UI-05-48A main window patch
# ============================================================


# ============================================================
# UI-05-49A - SOFT DEPTH BUTTON SYSTEM
#
# 视觉升级，不改变任何业务逻辑：
# 1. 主界面按钮统一增加轻微立体层次、圆角、Hover / Press反馈。
# 2. 左侧五个功能区折叠标题保持47B统一字体，并增加柔和层次。
# 3. QSpinBox / QDoubleSpinBox 上下数值按键改为圆角分段按钮。
# 4. ModernStepper / ModernDoubleStepper / CompactNumberStepper
#    内部 +/- 按钮单独加强圆角和按压反馈。
# 5. 图片调整旋转/镜像/重置、底部/顶部工具按钮统一精修。
# 6. 顶部“添加图片 / 导入PPT”保留醒目层级，但增加轻微立体感。
# 7. 页面导航“+”按钮跟随当前主题做圆角立体处理。
# ============================================================


# ------------------------------------------------------------
# A. 主题QSS：主界面按钮统一视觉
# ------------------------------------------------------------
_FD_UI0549A_BUILD_THEME_QSS_ORIGINAL = (
    build_theme_qss
)


def _fd_ui0549a_build_theme_qss(
    name,
):
    qss = (
        _FD_UI0549A_BUILD_THEME_QSS_ORIGINAL(
            name
        )
    )

    c = THEME_META.get(
        name,
        THEME_META.get(
            "极光浅色",
            {},
        ),
    )

    text = c.get(
        "text",
        "#16352A",
    )
    muted = c.get(
        "muted",
        "#6B7F75",
    )
    panel = c.get(
        "panel",
        "#FFFFFF",
    )
    panel_alt = c.get(
        "panel_alt",
        "#F4F9F6",
    )
    input_color = c.get(
        "input",
        panel,
    )
    selection = c.get(
        "selection",
        "#DFF3E8",
    )
    border = c.get(
        "border",
        "#D0E4D8",
    )
    border_strong = c.get(
        "border_strong",
        "#AFCFBE",
    )
    accent = c.get(
        "accent",
        "#059669",
    )
    accent_hover = c.get(
        "accent_hover",
        accent,
    )
    accent_text = c.get(
        "accent_text",
        "#FFFFFF",
    )

    qss += f"""
/* =========================================================
   UI-05-49A · Soft Depth Button System
   ========================================================= */

/* ---------- 通用按钮：轻微立体，不做厚重拟物 ---------- */
QPushButton,
QToolButton {{
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    border-radius: 9px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
    color: {text};
}}

QPushButton:hover,
QToolButton:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {selection}
    );
}}

QPushButton:pressed,
QToolButton:pressed {{
    border: 1px solid {accent};
    border-bottom: 1px solid {accent};
    background-color: {selection};
    padding-top: 1px;
}}

QPushButton:disabled,
QToolButton:disabled {{
    color: {muted};
    border-color: {border};
    border-bottom-color: {border};
    background-color: {panel_alt};
}}


/* ---------- 左侧五个功能区标题 ---------- */
QWidget#LeftPanel QToolButton#CollapsibleHeader {{
    min-height: 40px;
    max-height: 40px;
    padding: 0 12px;
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    border-radius: 11px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
    color: {text};
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
    font-weight: 800;
    text-align: left;
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {selection}
    );
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:checked {{
    color: {text};
    border-color: {accent};
    border-bottom: 2px solid {accent};
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {selection}
    );
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:pressed {{
    border-bottom-width: 1px;
    padding-top: 1px;
}}


/* ---------- 图片调整：旋转 / 镜像 / 重置 ---------- */
QPushButton#IconActionButton,
QToolButton#IconActionButton,
QPushButton#CompactUtility,
QToolButton#CompactUtility {{
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    border-radius: 10px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
    color: {text};
    font-weight: 700;
}}

QPushButton#IconActionButton:hover,
QToolButton#IconActionButton:hover,
QPushButton#CompactUtility:hover,
QToolButton#CompactUtility:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background-color: {selection};
}}

QPushButton#IconActionButton:pressed,
QToolButton#IconActionButton:pressed,
QPushButton#CompactUtility:pressed,
QToolButton#CompactUtility:pressed {{
    border-bottom-width: 1px;
    background-color: {selection};
    padding-top: 1px;
}}


/* ---------- 页码/底栏/面板小工具按钮 ---------- */
QToolButton#PageNavButton,
QToolButton#PanelMenuButton {{
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    border-radius: 9px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
}}

QToolButton#PageNavButton:hover,
QToolButton#PanelMenuButton:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background-color: {selection};
}}

QToolButton#PageNavButton:pressed,
QToolButton#PanelMenuButton:pressed {{
    border-bottom-width: 1px;
    padding-top: 1px;
}}


/* ---------- 顶部两个主要导入按钮 ---------- */
QToolButton#TopImageImportButton {{
    border: 1px solid {accent_hover};
    border-bottom: 3px solid {accent_hover};
    border-radius: 10px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {accent},
        stop: 1 {accent_hover}
    );
    color: {accent_text};
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 800;
}}

QToolButton#TopImageImportButton:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
}}

QToolButton#TopImageImportButton:pressed {{
    border-bottom-width: 1px;
    padding-top: 2px;
}}

QToolButton#TopPptImportButton {{
    border: 1px solid {accent};
    border-bottom: 3px solid {accent};
    border-radius: 10px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {selection}
    );
    color: {text};
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 800;
}}

QToolButton#TopPptImportButton:hover {{
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {selection},
        stop: 1 {accent}
    );
    color: {accent_text};
}}

QToolButton#TopPptImportButton:pressed {{
    border-bottom-width: 1px;
    padding-top: 2px;
}}


/* =========================================================
   数值输入：原生 QSpinBox / QDoubleSpinBox
   ========================================================= */
QSpinBox,
QDoubleSpinBox {{
    min-height: 31px;
    border: 1px solid {border_strong};
    border-radius: 10px;
    background-color: {input_color};
    color: {text};
    padding-left: 9px;
    padding-right: 31px;
}}

QSpinBox:hover,
QDoubleSpinBox:hover {{
    border-color: {accent};
}}

QSpinBox:focus,
QDoubleSpinBox:focus {{
    border: 1px solid {accent};
}}

/* 上半部按钮 */
QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid {border};
    border-bottom: 1px solid {border};
    border-top-right-radius: 9px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
}}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover {{
    border-left-color: {accent};
    border-bottom-color: {accent};
    background-color: {selection};
}}

QSpinBox::up-button:pressed,
QDoubleSpinBox::up-button:pressed {{
    background-color: {accent};
}}

/* 下半部按钮 */
QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 25px;
    border-left: 1px solid {border};
    border-top: 1px solid {border};
    border-bottom-right-radius: 9px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel_alt},
        stop: 1 {selection}
    );
}}

QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{
    border-left-color: {accent};
    border-top-color: {accent};
    background-color: {selection};
}}

QSpinBox::down-button:pressed,
QDoubleSpinBox::down-button:pressed {{
    background-color: {accent};
}}


/* =========================================================
   自定义 +/- 数值按钮
   通过运行时 dynamic property 标记，不影响普通按钮。
   ========================================================= */
QPushButton[fdNumericStepButton="true"],
QToolButton[fdNumericStepButton="true"] {{
    min-width: 29px;
    max-width: 34px;
    min-height: 29px;
    max-height: 34px;
    padding: 0;
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    border-radius: 10px;
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
    color: {accent};
    font-family: "Microsoft YaHei UI";
    font-size: 15px;
    font-weight: 900;
}}

QPushButton[fdNumericStepButton="true"]:hover,
QToolButton[fdNumericStepButton="true"]:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background-color: {selection};
}}

QPushButton[fdNumericStepButton="true"]:pressed,
QToolButton[fdNumericStepButton="true"]:pressed {{
    border-bottom-width: 1px;
    background-color: {selection};
    padding-top: 1px;
}}

QPushButton[fdNumericStepButton="true"]:disabled,
QToolButton[fdNumericStepButton="true"]:disabled {{
    color: {muted};
    border-color: {border};
    border-bottom-color: {border};
    background-color: {panel_alt};
}}


/* ---------- 对话框按钮也保持同一圆角系统 ---------- */
QMessageBox QPushButton {{
    min-width: 82px;
    min-height: 32px;
    border-radius: 9px;
    border: 1px solid {border_strong};
    border-bottom: 2px solid {border_strong};
    background: qlineargradient(
        x1: 0, y1: 0,
        x2: 0, y2: 1,
        stop: 0 {panel},
        stop: 1 {panel_alt}
    );
    color: {text};
    font-weight: 700;
}}

QMessageBox QPushButton:hover {{
    border-color: {accent};
    border-bottom-color: {accent};
    background-color: {selection};
}}

QMessageBox QPushButton:pressed {{
    border-bottom-width: 1px;
    padding-top: 1px;
}}
"""

    return qss


build_theme_qss = (
    _fd_ui0549a_build_theme_qss
)


# ------------------------------------------------------------
# B. 标记自定义 Stepper 内部 +/- 按钮
# ------------------------------------------------------------
def _fd_ui0549a_mark_numeric_step_buttons(
    self,
):
    stepper_types = (
        ModernStepper,
        ModernDoubleStepper,
        CompactNumberStepper,
    )

    for stepper_type in stepper_types:
        try:
            steppers = self.findChildren(
                stepper_type
            )
        except Exception:
            steppers = []

        for stepper in steppers:
            try:
                stepper.setProperty(
                    "fdNumericControl",
                    True,
                )
            except Exception:
                pass

            for button_type in (
                QPushButton,
                QToolButton,
            ):
                try:
                    buttons = (
                        stepper.findChildren(
                            button_type
                        )
                    )
                except Exception:
                    buttons = []

                for button in buttons:
                    # 只标记自定义数值组件内部按钮；
                    # 不改业务连接和文字。
                    try:
                        button.setProperty(
                            "fdNumericStepButton",
                            True,
                        )
                        button.style().unpolish(
                            button
                        )
                        button.style().polish(
                            button
                        )
                    except Exception:
                        pass

    # Native numeric editors in the left panel use explicit +/- symbols.
    # Custom steppers already hide these native subcontrols.
    left_panel = getattr(self, "left_panel", None)
    if left_panel is not None:
        for spin_type in (QSpinBox, QDoubleSpinBox):
            for spin in left_panel.findChildren(spin_type):
                try:
                    if (
                        spin.buttonSymbols()
                        != spin_type.ButtonSymbols.NoButtons
                    ):
                        spin.setButtonSymbols(
                            spin_type.ButtonSymbols.PlusMinus
                        )
                except (AttributeError, RuntimeError):
                    continue


# ------------------------------------------------------------
# C. 主题切换后同步数值控件标记
# ------------------------------------------------------------
_FD_UI0549A_APPLY_THEME_ORIGINAL = (
    MainWindow.apply_theme
)


def _fd_ui0549a_apply_theme(
    self,
    name,
    *args,
    **kwargs,
):
    result = (
        _FD_UI0549A_APPLY_THEME_ORIGINAL(
            self,
            name,
            *args,
            **kwargs,
        )
    )

    _fd_ui0549a_mark_numeric_step_buttons(
        self
    )
    return result


MainWindow.apply_theme = (
    _fd_ui0549a_apply_theme
)


# ------------------------------------------------------------
# D. 初始化后补一次标记和主题刷新
# ------------------------------------------------------------
_FD_UI0549A_MAIN_INIT_ORIGINAL = (
    MainWindow.__init__
)


def _fd_ui0549a_main_init(
    self,
    *args,
    **kwargs,
):
    _FD_UI0549A_MAIN_INIT_ORIGINAL(
        self,
        *args,
        **kwargs,
    )

    _fd_ui0549a_mark_numeric_step_buttons(
        self
    )

    try:
        theme_name = (
            self.current_theme_name()
        )
    except Exception:
        theme_name = "极光浅色"

    # 47B / 48A 之后再统一套用49A视觉层。
    try:
        self.apply_theme(
            theme_name,
            persist=False,
        )
    except Exception:
        pass

    # Import buttons are created by earlier compatibility initializers after
    # the base language runtime has started, so synchronize them once here.
    self._sync_import_button_language()


MainWindow.__init__ = (
    _fd_ui0549a_main_init
)

# ============================================================
# End UI-05-49A
# ============================================================


# ============================================================
# UI-05-50A - 500 IMAGE RESPONSIVENESS
#
# 目标：
# - 500张图片以内，列表滚动 / 选择 / 拖拽 / 参数调整尽量保持流畅
# - 不修改分页、空白页、跨页插入、导航多选、PPT导出等业务规则
#
# 优化：
# 1. 右侧图片列表启用 UniformItemSizes + Batched layout。
# 2. 提升 Qt QPixmapCache 上限，减少缩略图反复解码/缩放。
# 3. 保留现有后台缩略图线程池、导航缩略图缓存和48A增量导航。
# ============================================================


# ------------------------------------------------------------
# A. Qt Pixmap Cache
# ------------------------------------------------------------
try:
    from PySide6.QtGui import QPixmapCache

    # 单位 KiB。这里只提高缓存上限，不会立即占满内存。
    QPixmapCache.setCacheLimit(
        128 * 1024
    )
except Exception:
    QPixmapCache = None


# ------------------------------------------------------------
# B. Runtime tuning after MainWindow initialization
# ------------------------------------------------------------
_FD_UI0550A_MAIN_INIT_ORIGINAL = (
    MainWindow.__init__
)


def _fd_ui0550a_main_init(
    self,
    *args,
    **kwargs,
):
    _FD_UI0550A_MAIN_INIT_ORIGINAL(
        self,
        *args,
        **kwargs,
    )

    image_list = getattr(
        self,
        "image_list",
        None,
    )

    if image_list is not None:
        # 所有图片行在当前设计里都使用相同高度，
        # Qt 无需为500项逐项计算高度。
        try:
            image_list.setUniformItemSizes(
                True
            )
        except Exception:
            pass

        # 分批完成列表布局，避免大量图片一次性阻塞事件循环。
        try:
            from PySide6.QtWidgets import QListView

            image_list.setLayoutMode(
                QListView.LayoutMode.Batched
            )
            image_list.setBatchSize(
                48
            )
        except Exception:
            pass

        # 大项目下关闭不必要的自动拖动滚屏过度敏感。
        try:
            image_list.setAutoScrollMargin(
                24
            )
        except Exception:
            pass

    # 保留现有后台缩略图架构，仅稍微增加Pixmap缓存复用能力。
    try:
        pool = getattr(
            self,
            "_thumbnail_pool",
            None,
        )

        # 不盲目增加并发：CPU/磁盘繁忙反而会拖慢界面。
        # 现有3线程作为交互优先策略继续保留。
        if pool is not None:
            current_threads = int(
                pool.maxThreadCount()
            )
            if current_threads > 4:
                pool.setMaxThreadCount(4)
    except Exception:
        pass


MainWindow.__init__ = (
    _fd_ui0550a_main_init
)

# ============================================================
# End UI-05-50A
# ============================================================


# ============================================================
# UI-05-52 - UNIFIED VISUAL SYSTEM
# ============================================================
_FD_UI0552_BUILD_THEME_QSS_ORIGINAL = build_theme_qss


def _fd_ui0552_build_theme_qss(name):
    name = normalize_theme_name(name)
    qss = _FD_UI0552_BUILD_THEME_QSS_ORIGINAL(name)
    c = THEME_META[name]
    numeric_plus_path = resource_path(
        "resources/plus-small.svg"
    ).replace(chr(92), "/")
    numeric_minus_path = resource_path(
        "resources/minus-small.svg"
    ).replace(chr(92), "/")
    return qss + f"""
/* UI-05-52: final typography and control normalization layer */
QWidget {{
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 400;
}}

QLabel,
QCheckBox,
QRadioButton {{
    font-size: 12px;
    font-weight: 400;
}}

QLabel#CompactTitle {{
    font-size: 17px;
    font-weight: 700;
}}

QLabel#CompactSubTitle,
QLabel#HeroSub,
QLabel#ImportHint,
QLabel#FieldCaption,
QLabel#PanelSubhead,
QLabel#PageTotal,
QStatusBar QLabel {{
    font-size: 11px;
    font-weight: 400;
    color: {c["muted"]};
}}

QLabel#SectionTitle,
QLabel#MiniSectionTitle,
QLabel#ImportLead {{
    font-size: 13px;
    font-weight: 600;
    color: {c["text"]};
}}

QLabel#InfoBadge,
QLabel#ImportCountBadge,
QLabel#StatusProjectMetric {{
    font-size: 11px;
    font-weight: 600;
}}

QFrame#CommandBar,
QFrame#Card,
QFrame#ProjectCard,
QFrame#ImageImportCard,
QFrame#AssetCard,
QFrame#WorkspaceCard,
QFrame#CountStrip,
QFrame#ThumbnailControl,
QFrame#WorkspaceFooter {{
    border-radius: 8px;
}}

QPushButton,
QToolButton {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {c["panel"]},
        stop: 1 {c["panel_alt"]}
    );
    color: {c["text"]};
    border: 1px solid {c["border_strong"]};
    border-bottom: 2px solid {c["border_strong"]};
    border-radius: 7px;
    font-size: 12px;
    font-weight: 500;
}}

QWidget#LeftPanel QPushButton#CompactUtility[fdBatchTitleApply="true"] {{
    min-width: 132px;
    max-width: 132px;
}}

QPushButton {{
    min-height: 32px;
    padding: 0 11px;
}}

QPushButton:hover,
QToolButton:hover {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {c["panel"]},
        stop: 1 {c["selection"]}
    );
    border-color: {c["accent"]};
    border-bottom-color: {c["accent"]};
    color: {c["text"]};
}}

QPushButton:pressed,
QToolButton:pressed {{
    background-color: {c["border"]};
    border: 1px solid {c["accent"]};
    border-bottom: 1px solid {c["accent"]};
    padding-top: 1px;
}}

QPushButton:disabled,
QToolButton:disabled {{
    color: {c["muted"]};
    background-color: {c["panel_alt"]};
    border-color: {c["border"]};
    border-bottom-color: {c["border"]};
}}

QPushButton#CompactCommandButton {{
    min-height: 34px;
    max-height: 34px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {c["panel"]},
        stop: 1 {c["panel_alt"]}
    );
    border: 1px solid {c["border"]};
    border-bottom: 2px solid {c["border_strong"]};
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#CompactCommandButton:hover {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {c["panel"]},
        stop: 1 {c["selection"]}
    );
    border-color: {c["accent"]};
    border-bottom-color: {c["accent"]};
}}

QPushButton#CompactCommandButton:pressed {{
    background-color: {c["selection"]};
    border: 1px solid {c["accent"]};
    padding-top: 1px;
}}

QToolButton#TopImageImportButton,
QToolButton#ImportSplitButton,
QPushButton#Primary,
QToolButton#Primary {{
    min-height: 36px;
    max-height: 36px;
    border: 1px solid {c["accent"]};
    border-bottom: 2px solid {c["accent_hover"]};
    border-radius: 8px;
    background-color: {c["accent"]};
    color: {c["accent_text"]};
    font-size: 12px;
    font-weight: 600;
}}

QToolButton#TopImageImportButton:hover,
QToolButton#ImportSplitButton:hover,
QPushButton#Primary:hover,
QToolButton#Primary:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
    color: {c["accent_text"]};
}}

QToolButton#TopPptImportButton {{
    min-height: 36px;
    max-height: 36px;
    border: 1px solid {c["accent"]};
    border-bottom: 2px solid {c["accent"]};
    border-radius: 8px;
    background-color: {c["panel"]};
    color: {c["accent"]};
    font-size: 12px;
    font-weight: 600;
}}

QToolButton#TopPptImportButton:hover {{
    background-color: {c["selection"]};
    color: {c["accent"]};
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader {{
    min-height: 36px;
    max-height: 36px;
    padding: 0 8px;
    border: 1px solid {c["border"]};
    border-radius: 7px;
    background-color: {c["panel"]};
    color: {c["text"]};
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:hover {{
    background-color: {c["panel_alt"]};
    border-color: {c["accent"]};
}}

QWidget#LeftPanel QToolButton#CollapsibleHeader:checked {{
    background-color: {c["selection"]};
    border-color: {c["accent"]};
    color: {c["text"]};
}}

QWidget#LeftPanel QLabel,
QWidget#LeftPanel QCheckBox,
QWidget#LeftPanel QPushButton,
QWidget#LeftPanel QComboBox,
QWidget#LeftPanel QSpinBox,
QWidget#LeftPanel QDoubleSpinBox {{
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 400;
}}

QWidget#LeftPanel QLabel#FieldCaption,
QWidget#LeftPanel QLabel#PanelSubhead,
QWidget#LeftPanel QLabel#ImportHint {{
    font-size: 11px;
    font-weight: 400;
}}

QWidget#LeftPanel QCheckBox#AutoLayoutSwitch {{
    min-height: 30px;
    padding: 0 8px;
    border: 1px solid {c["border_strong"]};
    border-radius: 7px;
    background-color: {c["panel_alt"]};
    color: {c["text"]};
    font-weight: 600;
}}

QWidget#LeftPanel QCheckBox#AutoLayoutSwitch:checked {{
    border-color: {c["accent"]};
    background-color: {c["selection"]};
}}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {{
    min-height: 30px;
    border-radius: 7px;
    font-size: 12px;
}}

QWidget#LeftPanel QLineEdit,
QWidget#LeftPanel QComboBox,
QWidget#LeftPanel QSpinBox,
QWidget#LeftPanel QDoubleSpinBox {{
    min-height: 28px;
    font-size: 12px;
}}

QWidget#LeftPanel QSpinBox::up-button,
QWidget#LeftPanel QDoubleSpinBox::up-button {{
    width: 25px;
    border-left: 1px solid {c["accent_hover"]};
    border-bottom: 1px solid {c["accent_hover"]};
    background-color: {c["accent"]};
}}

QWidget#LeftPanel QSpinBox::down-button,
QWidget#LeftPanel QDoubleSpinBox::down-button {{
    width: 25px;
    border-left: 1px solid {c["accent_hover"]};
    border-top: 1px solid {c["accent_hover"]};
    background-color: {c["accent"]};
}}

QWidget#LeftPanel QSpinBox::up-button:hover,
QWidget#LeftPanel QDoubleSpinBox::up-button:hover,
QWidget#LeftPanel QSpinBox::down-button:hover,
QWidget#LeftPanel QDoubleSpinBox::down-button:hover {{
    background-color: {c["accent_hover"]};
}}

QWidget#LeftPanel QSpinBox::up-arrow,
QWidget#LeftPanel QDoubleSpinBox::up-arrow {{
    image: url("{numeric_plus_path}");
    width: 11px;
    height: 11px;
}}

QWidget#LeftPanel QSpinBox::down-arrow,
QWidget#LeftPanel QDoubleSpinBox::down-arrow {{
    image: url("{numeric_minus_path}");
    width: 11px;
    height: 11px;
}}

QPushButton#IconActionButton,
QToolButton#IconActionButton,
QToolButton#PageNavButton,
QToolButton#PanelMenuButton,
QToolButton#ThemeIconButton {{
    border: 1px solid {c["border_strong"]};
    border-radius: 7px;
    background-color: {c["panel"]};
    font-weight: 600;
}}

QPushButton#CompactUtility,
QToolButton#CompactUtility {{
    min-height: 30px;
    max-height: 30px;
    border: 1px solid {c["border_strong"]};
    border-radius: 7px;
    background-color: {c["panel_alt"]};
    font-size: 12px;
    font-weight: 500;
}}

QPushButton[fdNumericStepButton="true"],
QToolButton[fdNumericStepButton="true"] {{
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    border: 1px solid {c["accent_hover"]};
    border-bottom: 2px solid {c["accent_hover"]};
    border-radius: 7px;
    background-color: {c["accent"]};
    color: {c["accent_text"]};
    font-size: 16px;
    font-weight: 700;
}}

QPushButton#StepperButton[fdNumericStepButton="true"],
QPushButton#CompactStepperButton[fdNumericStepButton="true"] {{
    border: 1px solid {c["accent_hover"]};
    border-bottom: 2px solid {c["accent_hover"]};
    background-color: {c["accent"]};
    color: {c["accent_text"]};
}}

QPushButton[fdNumericStepButton="true"]:hover,
QToolButton[fdNumericStepButton="true"]:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
    color: {c["accent_text"]};
}}

QPushButton[fdNumericStepButton="true"]:pressed,
QToolButton[fdNumericStepButton="true"]:pressed {{
    background-color: {c["accent_hover"]};
    border: 1px solid {c["accent"]};
    padding-top: 1px;
}}

QPushButton#PageNavigatorAddButton {{
    border: 1px solid {c["border_strong"]};
    border-radius: 8px;
    background-color: {c["panel"]};
    color: {c["accent"]};
    font-size: 22px;
    font-weight: 500;
}}

QMenu {{
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    min-height: 28px;
    padding: 5px 30px 5px 11px;
    border-radius: 6px;
    font-size: 12px;
}}

QMessageBox QPushButton {{
    min-width: 84px;
    min-height: 32px;
    border: 1px solid {c["border_strong"]};
    border-radius: 7px;
    background-color: {c["panel_alt"]};
    font-size: 12px;
    font-weight: 500;
}}
"""


build_theme_qss = _fd_ui0552_build_theme_qss


_FD_UI0552_APPLY_THEME_ORIGINAL = MainWindow.apply_theme


def _fd_ui0552_apply_theme(self, name, *args, **kwargs):
    return _FD_UI0552_APPLY_THEME_ORIGINAL(
        self,
        normalize_theme_name(name),
        *args,
        **kwargs,
    )


MainWindow.apply_theme = _fd_ui0552_apply_theme

# ============================================================
# End UI-05-52
# ============================================================
