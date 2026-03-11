@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================================
:: Airtype Windows 建置腳本
::
:: 用法：build\build_windows.bat [cpu|cuda|both|skip]
::   - cpu   : 安裝 CPU 版 llama-cpp-python（LLM 潤飾功能）
::   - cuda  : 安裝 CUDA 版 llama-cpp-python
::   - both  : 同時安裝 CPU + CUDA 版
::   - skip  : 不安裝 llama-cpp-python（最小打包）
::   - 不帶參數：互動式詢問
:: ============================================================================

set "ROOT=%~dp0.."
cd /d "%ROOT%"

:: ── 參數處理 ──
set "LLAMA_MODE=%~1"
if "%LLAMA_MODE%"=="" (
    echo.
    echo  llama-cpp-python 安裝選項：
    echo    1^) cpu   — CPU 推理
    echo    2^) cuda  — CUDA GPU 推理
    echo    3^) both  — CPU + CUDA
    echo    4^) skip  — 不安裝（最小打包）
    echo.
    set /p "LLAMA_CHOICE=請選擇 [1-4]（預設 4）: "
    if "!LLAMA_CHOICE!"=="1" set "LLAMA_MODE=cpu"
    if "!LLAMA_CHOICE!"=="2" set "LLAMA_MODE=cuda"
    if "!LLAMA_CHOICE!"=="3" set "LLAMA_MODE=both"
    if "!LLAMA_CHOICE!"=="4" set "LLAMA_MODE=skip"
    if "!LLAMA_MODE!"=="" set "LLAMA_MODE=skip"
)

echo.
echo ================================================================
echo  Airtype Windows Build — llama-cpp=%LLAMA_MODE%
echo ================================================================
echo.

:: ── Step 1: 建立乾淨 venv ──
echo [1/5] 建立乾淨虛擬環境...
if exist build_venv rmdir /s /q build_venv
python -m venv build_venv
call build_venv\Scripts\activate.bat

:: ── Step 2: 安裝核心依賴（不含 torch/transformers）──
echo [2/5] 安裝核心依賴...
pip install --upgrade pip
pip install -e .
pip install tokenizers>=0.15 pyinstaller>=6.0

:: ── Step 3: 可選安裝 llama-cpp-python ──
if /i "%LLAMA_MODE%"=="cpu" (
    echo [3/5] 安裝 llama-cpp-python（CPU）...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
) else if /i "%LLAMA_MODE%"=="cuda" (
    echo [3/5] 安裝 llama-cpp-python（CUDA）...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --prefer-binary
) else if /i "%LLAMA_MODE%"=="both" (
    echo [3/5] 安裝 llama-cpp-python（CPU + CUDA）...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --prefer-binary
) else (
    echo [3/5] 跳過 llama-cpp-python 安裝
)

:: ── Step 4: PyInstaller 打包 ──
echo [4/5] 執行 PyInstaller 打包（onedir 模式）...
pyinstaller airtype.spec --clean --noconfirm

:: ── Step 4.5: PySide6 二進位裁剪 ──
echo [4.5/5] 裁剪 PySide6 未使用的 Qt 二進位...
python build\cleanup_dist.py dist\airtype

:: ── Step 5: 可選建立 NSIS 安裝程式 ──
echo [5/5] 建立 NSIS 安裝程式...
where makensis >nul 2>&1
if %ERRORLEVEL% equ 0 (
    makensis installer\windows\airtype.nsi
    echo NSIS 安裝程式已建立。
) else (
    echo [跳過] 未偵測到 NSIS，略過安裝程式建立。
)

:: ── 完成 ──
echo.
echo ================================================================
echo  建置完成！
echo  產出位於：dist\airtype\
echo ================================================================

:: 顯示最終大小
for /f "tokens=3" %%a in ('dir /s dist\airtype\ ^| findstr "個檔案"') do (
    echo  打包大小：%%a bytes
)

deactivate
endlocal
