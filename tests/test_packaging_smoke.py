"""冒煙測試：打包與發行相關模組。

測試涵蓋：
1. update_checker 模組 — 版本比較、manifest 解析、錯誤處理
2. settings_about 模組 — 確認可匯入（不啟動 Qt）
3. PyInstaller spec 存在性 — 確認建置配置檔案就位
4. 建置腳本存在性 — 確認各平台腳本就位
5. NSIS 腳本存在性 — 確認 Windows 安裝程式腳本就位
6. 啟動冒煙測試 — 模擬 main() 呼叫流程（不啟動 GUI）
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── 專案根目錄 ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent


# ============================================================================ #
# 1. update_checker 單元測試
# ============================================================================ #

class TestUpdateChecker:
    """airtype.utils.update_checker 單元測試。"""

    def _make_manifest(
        self,
        latest: str = "2.1.0",
        win_url: str = "https://airtype.app/releases/Setup-2.1.0.exe",
    ) -> dict:
        return {
            "latest_version": latest,
            "download_url": {
                "windows": win_url,
                "macos": "https://airtype.app/releases/Airtype-2.1.0.dmg",
                "linux": "https://airtype.app/releases/airtype-2.1.0-x86_64.AppImage",
            },
            "changelog": "修正問題",
            "release_date": "2025-06-01",
        }

    def _mock_urlopen(self, manifest: dict):
        """回傳一個模擬 urllib.request.urlopen 的 context manager。"""
        import io
        raw = json.dumps(manifest).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_update_available(self):
        """新版本可用時應回傳 is_update_available=True 及下載連結。"""
        from airtype.utils.update_checker import check_for_update

        manifest = self._make_manifest(latest="2.1.0")
        mock_resp = self._mock_urlopen(manifest)

        with patch("airtype.utils.update_checker.urllib.request.urlopen", return_value=mock_resp), \
             patch("sys.platform", "win32"):
            info = check_for_update("2.0.0")

        assert info.is_update_available is True
        assert info.latest_version == "2.1.0"
        assert info.current_version == "2.0.0"
        assert "airtype.app" in info.download_url
        assert not info.is_error

    def test_already_latest(self):
        """版本相同時應回傳 is_update_available=False。"""
        from airtype.utils.update_checker import check_for_update

        manifest = self._make_manifest(latest="2.0.0")
        mock_resp = self._mock_urlopen(manifest)

        with patch("airtype.utils.update_checker.urllib.request.urlopen", return_value=mock_resp):
            info = check_for_update("2.0.0")

        assert info.is_update_available is False
        assert not info.is_error

    def test_network_error(self):
        """網路錯誤時應回傳 error 非 None 且不崩潰。"""
        from airtype.utils.update_checker import check_for_update
        from urllib.error import URLError

        with patch("airtype.utils.update_checker.urllib.request.urlopen",
                   side_effect=URLError("Connection refused")):
            info = check_for_update("2.0.0")

        assert info.is_error is True
        assert info.is_update_available is False

    def test_malformed_manifest(self):
        """manifest 格式錯誤時應回傳 error 非 None 且不崩潰。"""
        from airtype.utils.update_checker import check_for_update
        import io

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not-json!!"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("airtype.utils.update_checker.urllib.request.urlopen", return_value=mock_resp):
            info = check_for_update("2.0.0")

        assert info.is_error is True

    def test_version_comparison(self):
        """版本比較應正確識別較新版本。"""
        from airtype.utils.update_checker import _parse_version

        assert _parse_version("2.1.0") > _parse_version("2.0.0")
        assert _parse_version("2.0.10") > _parse_version("2.0.9")
        assert _parse_version("3.0.0") > _parse_version("2.99.99")
        assert _parse_version("1.0.0") == _parse_version("1.0.0")

    def test_platform_download_url(self):
        """應根據執行平台選取對應的下載連結。"""
        from airtype.utils.update_checker import check_for_update

        manifest = self._make_manifest()
        mock_resp = self._mock_urlopen(manifest)

        with patch("airtype.utils.update_checker.urllib.request.urlopen", return_value=mock_resp), \
             patch("sys.platform", "linux"):
            info = check_for_update("2.0.0")

        assert "AppImage" in info.download_url or "linux" in info.download_url.lower()


# ============================================================================ #
# 2. 建置產物存在性檢查
# ============================================================================ #

class TestBuildArtifacts:
    """確認所有建置相關檔案均已就位。"""

    def test_pyinstaller_spec_exists(self):
        """airtype.spec 必須存在。"""
        spec = ROOT / "airtype.spec"
        assert spec.exists(), f"找不到 {spec}"

    def test_pyinstaller_spec_has_analysis(self):
        """airtype.spec 必須包含 Analysis 段落（合法的 PyInstaller spec）。"""
        spec_text = (ROOT / "airtype.spec").read_text(encoding="utf-8")
        assert "Analysis(" in spec_text, "airtype.spec 缺少 Analysis 段落"
        assert "EXE(" in spec_text, "airtype.spec 缺少 EXE 段落"

    def test_build_windows_script_exists(self):
        """build/build_windows.bat 必須存在。"""
        assert (ROOT / "build" / "build_windows.bat").exists()

    def test_build_macos_script_exists(self):
        """build/build_macos.sh 必須存在。"""
        assert (ROOT / "build" / "build_macos.sh").exists()

    def test_build_linux_script_exists(self):
        """build/build_linux.sh 必須存在。"""
        assert (ROOT / "build" / "build_linux.sh").exists()

    def test_nsis_installer_script_exists(self):
        """installer/windows/airtype.nsi 必須存在。"""
        assert (ROOT / "installer" / "windows" / "airtype.nsi").exists()

    def test_macos_entitlements_exists(self):
        """installer/macos/entitlements.plist 必須存在。"""
        assert (ROOT / "installer" / "macos" / "entitlements.plist").exists()

    def test_linux_create_appimage_exists(self):
        """installer/linux/create_appimage.sh 必須存在。"""
        assert (ROOT / "installer" / "linux" / "create_appimage.sh").exists()

    # S1 — create_appimage.sh 參數介面驗證
    def test_create_appimage_script_arg_interface(self):
        """create_appimage.sh 必須接受 3 個位置參數（$1 EXE_PATH, $2 APPDIR, $3 ROOT）。"""
        script = (ROOT / "installer" / "linux" / "create_appimage.sh").read_text(encoding="utf-8")
        assert 'EXE_PATH="$1"' in script, "缺少 $1（EXE_PATH）賦值"
        assert 'APPDIR="$2"' in script, "缺少 $2（APPDIR）賦值"
        assert 'ROOT="$3"' in script, "缺少 $3（ROOT）賦值"

    def test_build_linux_calls_create_appimage_with_three_args(self):
        """build_linux.sh 呼叫 create_appimage.sh 時必須傳入 3 個參數。"""
        build_script = (ROOT / "build" / "build_linux.sh").read_text(encoding="utf-8")
        assert "create_appimage.sh" in build_script, "build_linux.sh 未呼叫 create_appimage.sh"
        # 找到呼叫行，確認傳入 3 個非空引數（以反斜線換行連接）
        import re
        call_block = re.search(
            r'bash.*create_appimage\.sh.*\\\s*\n.*\\\s*\n.*',
            build_script,
            re.MULTILINE,
        )
        assert call_block is not None, "build_linux.sh 未以 3 個引數呼叫 create_appimage.sh"


# ============================================================================ #
# 3. 啟動冒煙測試（不啟動 GUI）
# ============================================================================ #

class TestLaunchSmoke:
    """模擬應用程式啟動流程，不啟動實際 GUI。"""

    def test_config_loads(self):
        """AirtypeConfig.load() 必須能成功執行。"""
        from airtype.config import AirtypeConfig
        cfg = AirtypeConfig.load()
        assert cfg is not None
        assert hasattr(cfg, "version")
        assert hasattr(cfg, "general")
        assert hasattr(cfg, "voice")

    def test_logging_setup(self):
        """setup_logging() 必須能以各種 level 正常執行。"""
        from airtype.logging_setup import setup_logging
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            setup_logging(level)  # 不應拋出例外

    def test_main_importable(self):
        """airtype.__main__ 的 main() 必須可匯入。"""
        from airtype.__main__ import main
        assert callable(main)

    def test_update_checker_importable(self):
        """update_checker 模組必須可匯入。"""
        from airtype.utils.update_checker import check_for_update, UpdateInfo
        assert callable(check_for_update)

    def test_settings_about_importable(self):
        """settings_about 模組必須可匯入（PySide6 為 optional）。"""
        import airtype.ui.settings_about as about_module
        assert hasattr(about_module, "APP_VERSION")
        assert hasattr(about_module, "SettingsAboutPage")

    # W2 — 啟動時更新檢查整合至 CoreController
    def test_controller_has_startup_update_check_method(self):
        """CoreController 必須有 _start_background_update_check 方法。"""
        from airtype.core.controller import CoreController
        assert hasattr(CoreController, "_start_background_update_check"), \
            "CoreController 缺少 _start_background_update_check 方法"

    def test_startup_update_check_runs_without_error(self):
        """啟動更新檢查必須在網路錯誤時不拋出例外。"""
        from airtype.core.controller import CoreController
        from urllib.error import URLError

        ctrl = CoreController()
        with patch("airtype.utils.update_checker.urllib.request.urlopen",
                   side_effect=URLError("模擬網路錯誤")):
            # 直接呼叫（不透過背景執行緒，方便同步驗證）
            ctrl._start_background_update_check.__func__(ctrl)  # noqa: SLF001
            # 若沒有拋出例外即通過

    def test_startup_skips_update_check_when_notifications_disabled(self):
        """notifications=False 時，startup() 不應啟動更新檢查執行緒。"""
        import threading
        from airtype.core.controller import CoreController
        from airtype.config import AirtypeConfig

        cfg = AirtypeConfig()
        cfg.general.notifications = False

        ctrl = CoreController(config=cfg)
        called = []

        original = ctrl._start_background_update_check

        def _spy():
            called.append(True)
            original()

        ctrl._start_background_update_check = _spy
        ctrl.startup()
        assert not called, "notifications=False 時不應呼叫更新檢查"


# ============================================================================ #
# 4. S2 — UpdateInfo UI 邏輯驗證（不需 Qt）
# ============================================================================ #

class TestUpdateInfoUILogic:
    """驗證 UpdateInfo 物件的欄位正確驅動 About 頁面的顯示邏輯。"""

    def test_update_available_sets_correct_fields(self):
        """有新版本時，UpdateInfo 必須有 is_update_available=True 且 download_url 非空。"""
        from airtype.utils.update_checker import UpdateInfo
        info = UpdateInfo(
            current_version="2.0.0",
            latest_version="2.1.0",
            is_update_available=True,
            download_url="https://airtype.app/releases/Setup.exe",
            changelog="",
            release_date="",
        )
        assert info.is_update_available is True
        assert info.download_url != ""
        assert not info.is_error

    def test_no_update_sets_correct_fields(self):
        """已是最新版本時，is_update_available 必須為 False 且 error 為 None。"""
        from airtype.utils.update_checker import UpdateInfo
        info = UpdateInfo(
            current_version="2.0.0",
            latest_version="2.0.0",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
        )
        assert info.is_update_available is False
        assert not info.is_error

    def test_error_info_sets_is_error(self):
        """發生錯誤時，is_error 必須為 True 且 is_update_available 為 False。"""
        from airtype.utils.update_checker import UpdateInfo
        info = UpdateInfo(
            current_version="2.0.0",
            latest_version="",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
            error="Connection refused",
        )
        assert info.is_error is True
        assert info.is_update_available is False

    def test_download_link_label_shown_only_when_update_available_with_url(self):
        """有新版本且 download_url 非空時，下載連結才應顯示。"""
        from airtype.utils.update_checker import UpdateInfo

        # 有更新 + 有 URL → 應顯示連結
        info_with_url = UpdateInfo(
            current_version="2.0.0", latest_version="2.1.0",
            is_update_available=True,
            download_url="https://airtype.app/releases/Setup.exe",
            changelog="", release_date="",
        )
        # 邏輯對應 settings_about._on_update_result 中的條件
        should_show_link = info_with_url.is_update_available and bool(info_with_url.download_url)
        assert should_show_link is True

        # 有更新 + 無 URL → 不顯示連結
        info_no_url = UpdateInfo(
            current_version="2.0.0", latest_version="2.1.0",
            is_update_available=True,
            download_url="",
            changelog="", release_date="",
        )
        should_show_link = info_no_url.is_update_available and bool(info_no_url.download_url)
        assert should_show_link is False
