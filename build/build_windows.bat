@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Airtype Windows Build Script
::
:: Usage: build\build_windows.bat [cpu|cuda|both|skip]
::   cpu   - install CPU build of llama-cpp-python
::   cuda  - install CUDA build of llama-cpp-python
::   both  - install both CPU and CUDA builds
::   skip  - skip llama-cpp-python (minimal package)
::   (no arg) - interactive prompt
:: ============================================================================

set "ROOT=%~dp0.."
cd /d "%ROOT%"

:: -- Argument handling --
set "LLAMA_MODE=%~1"
if "%LLAMA_MODE%"=="" (
    echo.
    echo  llama-cpp-python install options:
    echo    1^) cpu   - CPU inference
    echo    2^) cuda  - CUDA GPU inference
    echo    3^) both  - CPU + CUDA
    echo    4^) skip  - skip install ^(minimal package^)
    echo.
    set /p "LLAMA_CHOICE=Choose [1-4] (default 4): "
    if "!LLAMA_CHOICE!"=="1" set "LLAMA_MODE=cpu"
    if "!LLAMA_CHOICE!"=="2" set "LLAMA_MODE=cuda"
    if "!LLAMA_CHOICE!"=="3" set "LLAMA_MODE=both"
    if "!LLAMA_CHOICE!"=="4" set "LLAMA_MODE=skip"
    if "!LLAMA_MODE!"=="" set "LLAMA_MODE=skip"
)

echo.
echo ================================================================
echo  Airtype Windows Build - llama-cpp=%LLAMA_MODE%
echo ================================================================
echo.

:: -- Step 1: Create clean venv --
echo [1/5] Creating clean virtual environment...
if exist build_venv rmdir /s /q build_venv
python -m venv build_venv
call build_venv\Scripts\activate.bat

:: -- Step 2: Install core dependencies (no torch/transformers) --
echo [2/5] Installing core dependencies...
python -m pip install --upgrade pip
pip install -e .
pip install tokenizers>=0.15 pyinstaller>=6.0

:: -- Step 3: Optional llama-cpp-python install --
if /i "%LLAMA_MODE%"=="cpu" (
    echo [3/5] Installing llama-cpp-python (CPU)...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
) else if /i "%LLAMA_MODE%"=="cuda" (
    echo [3/5] Installing llama-cpp-python (CUDA)...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --prefer-binary
) else if /i "%LLAMA_MODE%"=="both" (
    echo [3/5] Installing llama-cpp-python (CPU + CUDA)...
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
    pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --prefer-binary
) else (
    echo [3/5] Skipping llama-cpp-python install
)

:: -- Step 4: PyInstaller packaging --
echo [4/5] Running PyInstaller (onedir mode)...
pyinstaller airtype.spec --clean --noconfirm

:: -- Step 4.5: Trim unused PySide6 Qt binaries --
echo [4.5/5] Trimming unused PySide6 Qt binaries...
python build\cleanup_dist.py dist\airtype

:: -- Step 5: Optional NSIS installer --
echo [5/5] Creating NSIS installer...
set "MAKENSIS="
where makensis >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "MAKENSIS=makensis"
) else if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
) else if exist "C:\Program Files\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files\NSIS\makensis.exe"
)
if defined MAKENSIS (
    "%MAKENSIS%" installer\windows\airtype.nsi
    echo NSIS installer created.
) else (
    echo [skip] makensis not found, skipping installer creation.
)

:: -- Done --
echo.
echo ================================================================
echo  Build complete!
echo  Output: dist\airtype\
echo ================================================================

:: Show final size
for /f "tokens=3" %%a in ('dir /s dist\airtype\ ^| findstr "File(s)"') do (
    echo  Package size: %%a bytes
)

deactivate
endlocal
