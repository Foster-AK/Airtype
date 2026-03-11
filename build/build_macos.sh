#!/usr/bin/env bash
# ============================================================================
# Airtype macOS 建置腳本
#
# 用法：bash build/build_macos.sh
#
# 環境變數（可選）：
#   CODESIGN_IDENTITY   — Apple Developer ID（程式碼簽署）
#   NOTARIZE_APPLE_ID   — Apple ID（公證）
#   NOTARIZE_TEAM_ID    — Team ID（公證）
#   NOTARIZE_PASSWORD    — App-specific password（公證）
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "================================================================"
echo " Airtype macOS Build"
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

# ── Step 4: 程式碼簽署（可選）──
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    echo "[4/5] 程式碼簽署..."
    codesign --force --deep --sign "$CODESIGN_IDENTITY" \
        --entitlements installer/macos/entitlements.plist \
        dist/airtype/airtype
else
    echo "[4/5] 跳過程式碼簽署（未設定 CODESIGN_IDENTITY）"
fi

# ── Step 5: 建立 DMG ──
echo "[5/5] 建立 DMG 安裝映像..."
if [ -f installer/macos/create_dmg.sh ]; then
    bash installer/macos/create_dmg.sh dist/airtype/airtype
else
    echo "[跳過] 找不到 create_dmg.sh"
fi

# ── 完成 ──
echo ""
echo "================================================================"
echo " 建置完成！"
echo " 產出位於：dist/airtype/"
SIZE=$(du -sh dist/airtype/ | cut -f1)
echo " 打包大小：${SIZE}"
echo "================================================================"

deactivate
