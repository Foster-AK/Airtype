; Airtype v2.0 — NSIS Windows 安裝程式腳本
; 需求：NSIS 3.x (https://nsis.sourceforge.io/)
; 用法：makensis installer\windows\airtype.nsi
;
; 建置前須先執行 PyInstaller 產生 dist\airtype\ 目錄（onedir 模式）

Unicode True

;------------------------------------------------------------------------------
; 一般設定
;------------------------------------------------------------------------------
!define APP_NAME        "Airtype"
!define APP_VERSION     "0.1.0"
!define APP_PUBLISHER   "Airtype Team"
!define APP_URL         "https://airtype.app"
!define APP_EXE         "airtype.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define DIST_DIR        "..\..\dist"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "${DIST_DIR}\AirtypeSetup-${APP_VERSION}-win64.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show

;------------------------------------------------------------------------------
; 現代 UI
;------------------------------------------------------------------------------
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\resources\icons\airtype_icon_486.ico"
!define MUI_UNICON "..\..\resources\icons\airtype_icon_486.ico"

; 安裝頁面
!insertmacro MUI_PAGE_WELCOME
; 授權頁面（建立 LICENSE 檔案後取消下方註解）
; !insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; 解除安裝頁面
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 語系
!insertmacro MUI_LANGUAGE "TradChinese"
!insertmacro MUI_LANGUAGE "English"

;------------------------------------------------------------------------------
; 版本資訊
;------------------------------------------------------------------------------
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=0 "ProductName"     "${APP_NAME}"
VIAddVersionKey /LANG=0 "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey /LANG=0 "CompanyName"     "${APP_PUBLISHER}"
VIAddVersionKey /LANG=0 "LegalCopyright"  "Copyright (c) 2025 ${APP_PUBLISHER}"
VIAddVersionKey /LANG=0 "FileDescription" "${APP_NAME} 安裝程式"
VIAddVersionKey /LANG=0 "FileVersion"     "${APP_VERSION}"

;------------------------------------------------------------------------------
; 執行中偵測（安裝/解除安裝共用）
;------------------------------------------------------------------------------
!include "LogicLib.nsh"

; 透過 tasklist 偵測程序是否執行中（不需額外外掛）
!macro _CheckAppRunningImpl
    _check_loop:
    nsExec::ExecToStack 'cmd /c tasklist /FI "IMAGENAME eq ${APP_EXE}" /NH | findstr /I "${APP_EXE}"'
    Pop $0  ; 返回碼
    Pop $1  ; 輸出
    ${If} $0 == 0
        MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION \
            "${APP_NAME} 正在執行中，請先關閉後再繼續。" \
            IDRETRY _check_loop
        Abort
    ${EndIf}
!macroend

Function CheckAppRunning
    !insertmacro _CheckAppRunningImpl
FunctionEnd

Function un.CheckAppRunning
    !insertmacro _CheckAppRunningImpl
FunctionEnd

;------------------------------------------------------------------------------
; 安裝段
;------------------------------------------------------------------------------
Section "主要程式" SecMain
    SectionIn RO  ; 必選

    ; 偵測應用程式是否執行中（安裝/升級前需先關閉）
    Call CheckAppRunning

    SetOutPath "$INSTDIR"

    ; 複製 onedir 目錄下所有檔案（執行檔 + 依賴 DLL + 資源）
    File /r "${DIST_DIR}\airtype\*.*"

    ; 寫入登錄機碼（安裝路徑）
    WriteRegStr HKLM "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\${APP_NAME}" "Version"    "${APP_VERSION}"

    ; 寫入解除安裝資訊
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"     "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"    "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayIcon"     "$INSTDIR\${APP_EXE},0"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"        1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"        1

    ; 產生解除安裝程式
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; 建立開始功能表捷徑
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\解除安裝 ${APP_NAME}.lnk" \
        "$INSTDIR\uninstall.exe"

    ; 桌面捷徑（可選）
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

    ; 設定自動啟動（可選，預設關閉）
    ; WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}" "$INSTDIR\${APP_EXE}"

SectionEnd

;------------------------------------------------------------------------------
; 解除安裝段
;------------------------------------------------------------------------------
Section "Uninstall"

    ; 偵測應用程式是否執行中（解除安裝前需先關閉）
    Call un.CheckAppRunning

    ; 遞迴移除安裝目錄（onedir 模式包含大量 DLL 與子目錄）
    RMDir /r "$INSTDIR"

    ; 移除捷徑
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\解除安裝 ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; 移除登錄機碼
    DeleteRegKey HKLM "Software\${APP_NAME}"
    DeleteRegKey HKLM "${UNINSTALL_KEY}"
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}"

SectionEnd
