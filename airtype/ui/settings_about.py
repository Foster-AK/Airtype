"""關於頁面。

顯示版本資訊、系統資訊（OS/CPU/RAM/GPU）、已安裝模型清單、
授權資訊、更新檢查按鈕、回報問題連結、匯出診斷資料按鈕。
"""

from __future__ import annotations

import json
import logging
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr  # noqa: E402

APP_VERSION = "2.0.0"

from airtype.utils.update_checker import UpdateInfo, check_for_update  # noqa: E402

try:
    from PySide6.QtWidgets import (
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QThread, Signal, Slot
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


def _collect_system_info() -> dict:
    """收集系統資訊。"""
    info: dict = {
        "os": platform.platform(),
        "python": sys.version,
        "cpu": platform.processor() or platform.machine(),
    }
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        info["ram"] = f"{ram_gb:.1f} GB"
    except ImportError:
        info["ram"] = "未知"

    # GPU 偵測（嘗試 torch）
    gpu_info = "未偵測到 GPU"
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001
        # PyTorch 在 PyInstaller frozen 環境可能觸發 AttributeError（循環 import）
        pass
    info["gpu"] = gpu_info

    return info


if _PYSIDE6_AVAILABLE:

    class _UpdateWorker(QThread):
        """背景更新檢查執行緒。"""

        result_ready = Signal(object)  # 傳遞 UpdateInfo 物件

        def run(self) -> None:
            info = check_for_update(APP_VERSION)
            self.result_ready.emit(info)

    class SettingsAboutPage(QWidget):
        """關於頁面。"""

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._build_ui()

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(12)

            # 版本
            version_label = QLabel(f"<b>Airtype</b>  v{APP_VERSION}")
            version_label.setStyleSheet("font-size: 18px;")
            outer.addWidget(version_label)

            self._tagline_label = QLabel(tr("app.tagline"))
            self._tagline_label.setStyleSheet("color: #666;")
            outer.addWidget(self._tagline_label)

            outer.addWidget(self._make_separator())

            # 系統資訊
            self._sys_title_label = QLabel(tr("settings.about.system_info_title"))
            self._sys_title_label.setStyleSheet("font-weight: bold;")
            outer.addWidget(self._sys_title_label)

            sys_info = _collect_system_info()
            for key, value in sys_info.items():
                row = QLabel(f"<b>{key.upper()}：</b> {value}")
                row.setWordWrap(True)
                outer.addWidget(row)

            outer.addWidget(self._make_separator())

            # 已安裝模型
            self._models_title_label = QLabel(tr("settings.about.installed_models_title"))
            self._models_title_label.setStyleSheet("font-weight: bold;")
            outer.addWidget(self._models_title_label)

            self._models_label = QLabel(self._get_installed_models())
            self._models_label.setWordWrap(True)
            outer.addWidget(self._models_label)

            outer.addWidget(self._make_separator())

            # 授權
            self._license_label = QLabel(tr("settings.about.license"))
            outer.addWidget(self._license_label)

            outer.addWidget(self._make_separator())

            # 按鈕區
            btn_row = QHBoxLayout()
            outer.addLayout(btn_row)

            self._update_btn = QPushButton(tr("settings.about.check_update_btn"))
            self._update_btn.clicked.connect(self._check_updates)
            btn_row.addWidget(self._update_btn)

            self._issue_btn = QPushButton(tr("settings.about.report_issue_btn"))
            self._issue_btn.clicked.connect(self._open_issue_tracker)
            btn_row.addWidget(self._issue_btn)

            self._diag_btn = QPushButton(tr("settings.about.export_diag_btn"))
            self._diag_btn.clicked.connect(self._export_diagnostics)
            btn_row.addWidget(self._diag_btn)

            btn_row.addStretch()

            # 狀態訊息列
            self._status_label = QLabel("")
            self._status_label.setStyleSheet("color: #0a84ff;")
            outer.addWidget(self._status_label)

            # 更新下載連結（有新版本時才顯示）
            self._update_link_label = QLabel("")
            self._update_link_label.setOpenExternalLinks(True)
            self._update_link_label.setVisible(False)
            outer.addWidget(self._update_link_label)

            outer.addStretch()

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._tagline_label.setText(tr("app.tagline"))
            self._sys_title_label.setText(tr("settings.about.system_info_title"))
            self._models_title_label.setText(tr("settings.about.installed_models_title"))
            self._license_label.setText(tr("settings.about.license"))
            self._update_btn.setText(tr("settings.about.check_update_btn"))
            self._issue_btn.setText(tr("settings.about.report_issue_btn"))
            self._diag_btn.setText(tr("settings.about.export_diag_btn"))

        def _make_separator(self) -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            return line

        def _get_installed_models(self) -> str:
            """取得已安裝模型清單。"""
            models_dir = Path.home() / ".airtype" / "models"
            if not models_dir.exists():
                return tr("settings.about.no_models")
            entries = [p.name for p in models_dir.iterdir() if p.is_dir()]
            return "、".join(entries) if entries else tr("settings.about.no_models")

        def _check_updates(self) -> None:
            """背景執行更新檢查。"""
            self._update_btn.setEnabled(False)
            self._status_label.setText(tr("settings.about.checking_update"))
            self._worker = _UpdateWorker()
            self._worker.result_ready.connect(self._on_update_result)
            self._worker.start()

        @Slot(object)
        def _on_update_result(self, info: UpdateInfo) -> None:
            self._update_btn.setEnabled(True)
            self._update_link_label.setVisible(False)

            if info.is_error:
                self._status_label.setStyleSheet("color: #cc3300;")
                self._status_label.setText(f"無法檢查更新：{info.error}")
            elif info.is_update_available:
                self._status_label.setStyleSheet("color: #0a84ff;")
                self._status_label.setText(
                    f"有新版本可用：{info.latest_version}（目前：{info.current_version}）"
                )
                if info.download_url:
                    self._update_link_label.setText(
                        f'<a href="{info.download_url}">下載 Airtype {info.latest_version}</a>'
                    )
                    self._update_link_label.setVisible(True)
            else:
                self._status_label.setStyleSheet("color: #0a84ff;")
                self._status_label.setText(f"已是最新版本（{info.current_version}）")

        def _open_issue_tracker(self) -> None:
            QDesktopServices.openUrl(
                QUrl("https://github.com/example/airtype/issues")
            )

        def _export_diagnostics(self) -> None:
            """匯出診斷壓縮包（系統資訊、設定、日誌摘要）。"""
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                tr("settings.about.save_diag_title"),
                str(Path.home() / f"airtype_diag_{datetime.now():%Y%m%d_%H%M%S}.zip"),
                tr("settings.about.save_diag_filter"),
            )
            if not save_path:
                return

            try:
                self._create_diag_bundle(Path(save_path))
                self._status_label.setText(f"診斷資料已匯出至：{save_path}")
            except Exception as exc:
                logger.exception("匯出診斷資料失敗")
                self._status_label.setText(f"匯出失敗：{exc}")

        def _create_diag_bundle(self, dest: Path) -> None:
            """建立診斷壓縮包。"""
            sys_info = _collect_system_info()
            config_dict = self._config.to_dict()
            # API 金鑰已透過 keyring 儲存，不存在於 config_dict 中

            log_path = Path.home() / ".airtype" / "airtype.log"

            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "system_info.json",
                    json.dumps(sys_info, ensure_ascii=False, indent=2),
                )
                zf.writestr(
                    "config.json",
                    json.dumps(config_dict, ensure_ascii=False, indent=2),
                )
                if log_path.exists():
                    # 只取最後 500 行
                    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    excerpt = "\n".join(lines[-500:])
                    zf.writestr("airtype.log", excerpt)

else:

    class SettingsAboutPage:  # type: ignore[no-redef]
        pass
