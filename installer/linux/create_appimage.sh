#!/usr/bin/env bash
# Airtype v2.0 — Linux AppDir 建立腳本
# 此腳本由 build/build_linux.sh 呼叫，準備 AppDir 供 appimagetool 使用。
#
# 用法：
#   bash installer/linux/create_appimage.sh <EXE_PATH> <APPDIR_PATH> <PROJECT_ROOT>

set -euo pipefail

EXE_PATH="$1"        # PyInstaller 產生的執行檔路徑
APPDIR="$2"          # 目標 AppDir 路徑
ROOT="$3"            # 專案根目錄

APP_NAME="airtype"
VERSION="0.1.0"

if [[ ! -f "$EXE_PATH" ]]; then
    echo "[錯誤] 找不到執行檔：$EXE_PATH"
    exit 1
fi

echo "[AppImage] 準備 AppDir：$APPDIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"

# 複製執行檔
cp "$EXE_PATH" "$APPDIR/usr/bin/$APP_NAME"
chmod +x "$APPDIR/usr/bin/$APP_NAME"

# 複製圖示（優先使用 PNG；若無則建立空白佔位）
ICON_256="$ROOT/resources/icons/airtype_256.png"
ICON_512="$ROOT/resources/icons/airtype_512.png"
ICON_FALLBACK="$ROOT/resources/icons/airtype.png"

if [[ -f "$ICON_256" ]]; then
    cp "$ICON_256" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
    cp "$ICON_256" "$APPDIR/$APP_NAME.png"
elif [[ -f "$ICON_FALLBACK" ]]; then
    cp "$ICON_FALLBACK" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
    cp "$ICON_FALLBACK" "$APPDIR/$APP_NAME.png"
else
    echo "[警告] 找不到 PNG 圖示，AppImage 將無圖示"
    touch "$APPDIR/$APP_NAME.png"
fi

if [[ -f "$ICON_512" ]]; then
    cp "$ICON_512" "$APPDIR/usr/share/icons/hicolor/512x512/apps/$APP_NAME.png"
fi

# 建立 .desktop 檔案
cat > "$APPDIR/usr/share/applications/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Airtype
Comment=跨平台離線語音即時輸入工具
Exec=$APP_NAME
Icon=$APP_NAME
Categories=Utility;Accessibility;
StartupNotify=false
NoDisplay=false
EOF

# AppDir 根目錄需要 .desktop 的符號連結
cp "$APPDIR/usr/share/applications/$APP_NAME.desktop" "$APPDIR/$APP_NAME.desktop"

# AppRun 啟動腳本
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
# AppImage AppRun — 設定執行環境並啟動 Airtype
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
exec "$HERE/usr/bin/airtype" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "[AppImage] AppDir 準備完成：$APPDIR"
