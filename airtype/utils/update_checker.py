"""更新檢查模組。

透過 HTTPS 獲取版本 manifest JSON，比較目前版本並回傳更新資訊。
不執行自動下載或安裝，僅提供通知資訊。

manifest JSON 格式範例（https://airtype.app/version.json）：
{
    "latest_version": "2.1.0",
    "min_version": "1.0.0",
    "download_url": {
        "windows": "https://airtype.app/releases/AirtypeSetup-2.1.0-win64.exe",
        "macos": "https://airtype.app/releases/AirtypeInstaller-2.1.0-macOS.dmg",
        "linux": "https://airtype.app/releases/airtype-2.1.0-x86_64.AppImage"
    },
    "changelog": "- 修正若干錯誤\\n- 改善辨識準確率",
    "release_date": "2025-06-01"
}
"""

from __future__ import annotations

import json
import logging
import platform
import ssl
import sys
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

MANIFEST_URL = "https://airtype.app/version.json"
REQUEST_TIMEOUT = 8  # 秒


@dataclass
class UpdateInfo:
    """更新檢查結果。"""
    current_version: str
    latest_version: str
    is_update_available: bool
    download_url: str        # 當前平台的下載連結
    changelog: str
    release_date: str
    error: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


def _current_platform_key() -> str:
    """回傳當前平台的 manifest key（windows / macos / linux）。"""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    return "linux"


def _parse_version(version_str: str) -> tuple[int, ...]:
    """將版本字串解析為整數元組以便比較。"""
    try:
        return tuple(int(x) for x in version_str.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def check_for_update(current_version: str, manifest_url: str = MANIFEST_URL) -> UpdateInfo:
    """檢查是否有可用的新版本。

    Parameters
    ----------
    current_version:
        目前應用程式版本字串（如 "2.0.0"）。
    manifest_url:
        版本 manifest JSON 的 HTTPS URL。

    Returns
    -------
    UpdateInfo
        包含是否有更新、下載連結等資訊。若發生錯誤，error 欄位非 None。
    """
    platform_key = _current_platform_key()

    try:
        # 建立安全的 SSL context（驗證憑證）
        ssl_ctx = ssl.create_default_context()
        req = urllib.request.Request(
            manifest_url,
            headers={"User-Agent": f"Airtype/{current_version} ({sys.platform})"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ssl_ctx) as resp:
            raw = resp.read(64 * 1024)  # 最多讀取 64 KB
            data: dict = json.loads(raw)

    except HTTPError as exc:
        msg = f"HTTP 錯誤 {exc.code}：{exc.reason}"
        logger.warning("更新檢查失敗：%s", msg)
        return UpdateInfo(
            current_version=current_version,
            latest_version="",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
            error=msg,
        )
    except URLError as exc:
        msg = f"網路錯誤：{exc.reason}"
        logger.warning("更新檢查失敗：%s", msg)
        return UpdateInfo(
            current_version=current_version,
            latest_version="",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
            error=msg,
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        msg = f"manifest 格式錯誤：{exc}"
        logger.warning("更新檢查失敗：%s", msg)
        return UpdateInfo(
            current_version=current_version,
            latest_version="",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
            error=msg,
        )
    except Exception as exc:
        msg = f"未知錯誤：{exc}"
        logger.exception("更新檢查發生非預期錯誤")
        return UpdateInfo(
            current_version=current_version,
            latest_version="",
            is_update_available=False,
            download_url="",
            changelog="",
            release_date="",
            error=msg,
        )

    latest_version = data.get("latest_version", "")
    is_update_available = (
        bool(latest_version)
        and _parse_version(latest_version) > _parse_version(current_version)
    )

    # 取得當前平台的下載連結
    download_urls = data.get("download_url", {})
    if isinstance(download_urls, dict):
        download_url = download_urls.get(platform_key, download_urls.get("windows", ""))
    else:
        download_url = str(download_urls)

    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        is_update_available=is_update_available,
        download_url=download_url,
        changelog=data.get("changelog", ""),
        release_date=data.get("release_date", ""),
    )
