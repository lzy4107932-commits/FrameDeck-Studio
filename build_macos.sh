#!/bin/bash
set -euo pipefail

VERSION="12.0.0"
APP_NAME="FrameDeck Studio"
ARCH="$(uname -m)"
OUTPUT_DIR="release/v${VERSION}/macos-${ARCH}"
STAGING_DIR="build/macos-dmg-${ARCH}"

python3 -m PyInstaller --noconfirm --clean "FrameDeck Studio macOS.spec"

test -d "dist/${APP_NAME}.app"
rm -rf "${OUTPUT_DIR}" "${STAGING_DIR}"
mkdir -p "${OUTPUT_DIR}" "${STAGING_DIR}"
cp -R "dist/${APP_NAME}.app" "${STAGING_DIR}/${APP_NAME}.app"
ln -s /Applications "${STAGING_DIR}/Applications"
cp LICENSE THIRD_PARTY_LICENSES.md "${STAGING_DIR}/"

ZIP_PATH="${OUTPUT_DIR}/FrameDeck-Studio-v${VERSION}-macOS-${ARCH}.zip"
DMG_PATH="${OUTPUT_DIR}/FrameDeck-Studio-v${VERSION}-macOS-${ARCH}.dmg"

ditto -c -k --sequesterRsrc --keepParent "dist/${APP_NAME}.app" "${ZIP_PATH}"
hdiutil create -volname "FrameDeck Studio ${VERSION}" -srcfolder "${STAGING_DIR}" -ov -format UDZO "${DMG_PATH}"
shasum -a 256 "${ZIP_PATH}" "${DMG_PATH}" > "${OUTPUT_DIR}/SHA256SUMS-macOS-${ARCH}.txt"

printf "Built macOS packages for %s:\n" "${ARCH}"
printf "  %s\n  %s\n" "${ZIP_PATH}" "${DMG_PATH}"