#!/usr/bin/env bash
# ============================================================================
# Airtype Linux 建置腳本
#
# 用法：bash build/build_linux.sh
#
# 環境變數（可選）：
#   ARCH — 目標架構（預設 x86_64）
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ARCH="${ARCH:-x86_64}"
VERSION="0.1.0"

echo ""
echo "================================================================"
echo " Airtype Linux Build (${ARCH})"
echo "================================================================"
echo ""

# ── Step 1: 建立乾淨 venv ──
echo "[1/5] 建立乾淨虛擬環境..."
rm -rf build_venv
python3 -m venv build_venv
source build_venv/bin/activate

# ── Step 2: 安裝核心依賴（不含 torch/transformers）──
echo "[2/5] 安裝核心依賴..."
pip install --upgrade pip
pip install -e .
pip install "tokenizers>=0.15" "pyinstaller>=6.0"

# ── Step 3: PyInstaller 打包 ──
echo "[3/5] 執行 PyInstaller 打包（onedir 模式）..."
pyinstaller airtype.spec --clean --noconfirm

# ── Step 3.5: PySide6 二進位裁剪 ──
echo "[3.5/5] 裁剪 PySide6 未使用的 Qt 二進位..."
python3 build/cleanup_dist.py dist/airtype

# ── Step 4: 建立 AppImage ──
echo "[4/5] 建立 AppImage..."
APPDIR="dist/AppDir"
rm -rf "$APPDIR"

if [ -f installer/linux/create_appimage.sh ]; then
    bash installer/linux/create_appimage.sh \
        dist/airtype/airtype \
        "$APPDIR" \
        "$ROOT"
else
    echo "[錯誤] 找不到 installer/linux/create_appimage.sh"
    exit 1
fi

# ── Step 5: 打包 AppImage ──
echo "[5/5] 打包 AppImage..."
APPIMAGETOOL="appimagetool-${ARCH}.AppImage"
if ! command -v appimagetool &>/dev/null && [ ! -f "$APPIMAGETOOL" ]; then
    echo "下載 appimagetool..."
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

APPIMAGETOOL_CMD="${APPIMAGETOOL_CMD:-$(command -v appimagetool 2>/dev/null || echo "./$APPIMAGETOOL")}"
ARCH="$ARCH" "$APPIMAGETOOL_CMD" "$APPDIR" "dist/airtype-${VERSION}-${ARCH}.AppImage"

# ── 完成 ──
echo ""
echo "================================================================"
echo " 建置完成！"
SIZE=$(du -sh dist/airtype/ | cut -f1)
echo " onedir 大小：${SIZE}"
if [ -f "dist/airtype-${VERSION}-${ARCH}.AppImage" ]; then
    APPIMAGE_SIZE=$(du -sh "dist/airtype-${VERSION}-${ARCH}.AppImage" | cut -f1)
    echo " AppImage 大小：${APPIMAGE_SIZE}"
fi
echo "================================================================"

deactivate
