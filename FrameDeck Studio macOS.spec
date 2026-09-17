# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

APP_NAME = "FrameDeck Studio"
APP_VERSION = "12.0.0"
BUNDLE_ID = "com.zidonglai.framedeckstudio"

datas = [
    ("resources", "resources"),
    ("Template", "Template"),
    ("LICENSE", "."),
    ("THIRD_PARTY_LICENSES.md", "."),
]
binaries = []
hiddenimports = []

for package in ("PySide6", "pillow_heif"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

app = BUNDLE(
    collection,
    name=f"{APP_NAME}.app",
    icon="resources/icon.icns",
    bundle_identifier=BUNDLE_ID,
    version=APP_VERSION,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleName": APP_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 ZiDongLai(紫东来)",
    },
)