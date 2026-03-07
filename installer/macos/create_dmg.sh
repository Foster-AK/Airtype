#!/usr/bin/env bash
# Airtype v2.0 — macOS DMG 建立輔助腳本
# 此腳本由 build/build_macos.sh 呼叫，也可獨立執行。
#
# 用法：
#   bash installer/macos/create_dmg.sh [APP_PATH] [DIST_DIR]
#
# 預設：
#   APP_PATH  = dist/Airtype.app
#   DIST_DIR  = dist/

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="${1:-$ROOT/dist/Airtype.app}"
DIST_DIR="${2:-$ROOT/dist}"
APP_NAME="Airtype"
VERSION="0.1.0"
DMG_NAME="AirtypeInstaller-${VERSION}-macOS.dmg"
VOLUME_NAME="$APP_NAME $VERSION"

if [[ ! -d "$APP_PATH" ]]; then
    echo "[錯誤] 找不到 .app bundle：$APP_PATH"
    echo "       請先執行 build/build_macos.sh 或 pyinstaller airtype.spec"
    exit 1
fi

echo "[DMG] 建立 macOS 安裝映像：$DMG_NAME"

if command -v create-dmg &>/dev/null; then
    # 使用 create-dmg 產生精美的拖曳安裝介面
    ICON_ARG=""
    if [[ -f "$ROOT/resources/icons/airtype.icns" ]]; then
        ICON_ARG="--volicon $ROOT/resources/icons/airtype.icns"
    fi

    # shellcheck disable=SC2086
    create-dmg \
        --volname "$VOLUME_NAME" \
        $ICON_ARG \
        --window-pos 200 120 \
        --window-size 660 400 \
        --icon-size 128 \
        --icon "$APP_NAME.app" 180 190 \
        --hide-extension "$APP_NAME.app" \
        --app-drop-link 480 190 \
        --background "$ROOT/installer/macos/dmg_background.png" \
        "$DIST_DIR/$DMG_NAME" \
        "$APP_PATH"
else
    # 備用方案：hdiutil（不含拖曳箭頭背景）
    echo "[提示] 未找到 create-dmg，使用 hdiutil 建立基本 DMG"
    echo "       安裝 create-dmg 可獲得更精美效果：brew install create-dmg"

    STAGING=$(mktemp -d)
    cp -R "$APP_PATH" "$STAGING/"
    ln -s /Applications "$STAGING/Applications"

    hdiutil create \
        -volname "$VOLUME_NAME" \
        -srcfolder "$STAGING" \
        -ov \
        -format UDZO \
        "$DIST_DIR/$DMG_NAME"

    rm -rf "$STAGING"
fi

echo "[DMG] 完成：$DIST_DIR/$DMG_NAME"
