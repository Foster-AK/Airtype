"""LLM 潤飾設定頁面。

提供 SettingsLlmPage：
- 啟用 / 停用 LLM 潤飾
- 來源選擇（本機 / API）
- 本機模型路徑
- API 提供者、端點、金鑰
- 潤飾模式（輕度 / 中度 / 完整）
- 預覽開關
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

import logging

from airtype.utils.i18n import tr

logger = logging.getLogger(__name__)

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFormLayout,
        QGroupBox,
        QLabel,
        QLineEdit,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    class SettingsLlmPage(QWidget):
        """LLM 潤飾設定頁面。"""

        _MODE_CODES = [
            ("settings.llm.mode.light", "light"),
            ("settings.llm.mode.medium", "medium"),
            ("settings.llm.mode.full", "full"),
        ]
        _PROVIDER_CODES = [
            ("settings.llm.provider.openai", "openai"),
            ("settings.llm.provider.anthropic", "anthropic"),
            ("settings.llm.provider.ollama", "ollama"),
            ("settings.llm.provider.custom", "custom"),
        ]

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._llm_manifest_entries: list[dict] = []
            self._model_manager = None
            self._init_model_manager()
            self._build_ui()
            self._check_hardware_warning()

        def _init_model_manager(self) -> None:
            """初始化 ModelManager 取得 LLM manifest 清單。"""
            try:
                from airtype.utils.model_manager import ModelManager
                self._model_manager = ModelManager()
                self._llm_manifest_entries = self._model_manager.list_models_by_category("llm")
            except Exception as exc:  # noqa: BLE001
                logger.debug("ModelManager 初始化失敗：%s", exc)

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(12)

            self._title_label = QLabel(tr("settings.llm.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            # ── 啟用開關 ──────────────────────────────────────────────────────
            self._enabled_cb = QCheckBox(tr("settings.llm.enable_cb"))
            self._enabled_cb.setChecked(self._config.llm.enabled)
            self._enabled_cb.stateChanged.connect(self._on_enabled_changed)
            outer.addWidget(self._enabled_cb)

            # ── 潤飾模式 ──────────────────────────────────────────────────────
            self._mode_form = QFormLayout()
            self._mode_form.setVerticalSpacing(8)

            self._mode_combo = QComboBox()
            for label, val in [(tr(k), v) for k, v in self._MODE_CODES]:
                self._mode_combo.addItem(label, val)
            idx = next(
                (i for i, (_, v) in enumerate(self._MODE_CODES)
                 if v == self._config.llm.mode),
                0,
            )
            self._mode_combo.setCurrentIndex(idx)
            self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
            self._mode_form.addRow(tr("settings.llm.mode"), self._mode_combo)

            self._preview_cb = QCheckBox()
            self._preview_cb.setChecked(self._config.llm.preview_before_inject)
            self._preview_cb.stateChanged.connect(self._on_preview_changed)
            self._mode_form.addRow(tr("settings.llm.preview_before_inject"), self._preview_cb)

            outer.addLayout(self._mode_form)

            # ── 來源選擇 ──────────────────────────────────────────────────────
            self._source_combo = QComboBox()
            self._source_combo.addItem(tr("settings.llm.source.local"), "local")
            self._source_combo.addItem(tr("settings.llm.source.api"), "api")
            self._source_combo.setCurrentIndex(
                0 if self._config.llm.source == "local" else 1
            )
            self._source_combo.currentIndexChanged.connect(self._on_source_changed)

            self._source_form = QFormLayout()
            self._source_form.setVerticalSpacing(8)
            self._source_form.addRow(tr("settings.llm.source"), self._source_combo)
            outer.addLayout(self._source_form)

            # ── 本機模型設定 ──────────────────────────────────────────────────
            self._local_group = QGroupBox(tr("settings.llm.local_group_title"))
            self._local_form = QFormLayout(self._local_group)
            self._local_form.setVerticalSpacing(8)

            # manifest 模型下拉 + 自訂路徑選項
            self._local_model_combo = QComboBox()
            self._local_model_combo.currentIndexChanged.connect(self._on_local_model_combo_changed)
            self._local_form.addRow(tr("settings.llm.local_model"), self._local_model_combo)

            # 自訂路徑 QLineEdit（選擇「自訂路徑…」時顯示）
            self._model_path_edit = QLineEdit()
            self._model_path_edit.setPlaceholderText(tr("settings.llm.model_path_placeholder"))
            self._model_path_edit.textChanged.connect(self._on_model_path_changed)
            self._local_form.addRow(tr("settings.llm.model_path"), self._model_path_edit)

            # 初始填充 combo 並設定初始值
            self._populate_local_model_combo()

            outer.addWidget(self._local_group)

            # ── API 設定 ──────────────────────────────────────────────────────
            self._api_group = QGroupBox(tr("settings.llm.api_group_title"))
            self._api_form = QFormLayout(self._api_group)
            self._api_form.setVerticalSpacing(8)

            self._provider_combo = QComboBox()
            for label, val in [(tr(k), v) for k, v in self._PROVIDER_CODES]:
                self._provider_combo.addItem(label, val)
            prov_idx = next(
                (i for i, (_, v) in enumerate(self._PROVIDER_CODES)
                 if v == self._config.llm.api_provider),
                0,
            )
            self._provider_combo.setCurrentIndex(prov_idx)
            self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
            self._api_form.addRow(tr("settings.llm.api_provider"), self._provider_combo)

            self._endpoint_edit = QLineEdit(self._config.llm.api_endpoint or "")
            self._endpoint_edit.setPlaceholderText(tr("settings.llm.api_endpoint_placeholder"))
            self._endpoint_edit.textChanged.connect(self._on_endpoint_changed)
            self._api_form.addRow(tr("settings.llm.api_endpoint"), self._endpoint_edit)

            from airtype.config import get_api_key  # noqa: PLC0415
            _initial_key = get_api_key(self._config.llm.api_provider or "openai") or ""
            self._api_key_edit = QLineEdit(_initial_key)
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_key_edit.setPlaceholderText(tr("settings.llm.api_key_placeholder"))
            self._api_key_edit.textChanged.connect(self._on_api_key_changed)
            self._api_form.addRow(tr("settings.llm.api_key"), self._api_key_edit)

            self._api_note = QLabel(tr("settings.llm.api_note"))
            self._api_note.setWordWrap(True)
            self._api_note.setStyleSheet("color: #f59e0b; font-size: 11px;")
            self._api_form.addRow("", self._api_note)

            outer.addWidget(self._api_group)

            outer.addStretch()
            self._update_source_visibility()

        # ── LLM 本機模型 combo ────────────────────────────────────────────────

        def _populate_local_model_combo(self) -> None:
            """填充本機 LLM 模型下拉選單（已下載模型 + 自訂路徑）。"""
            self._local_model_combo.blockSignals(True)
            self._local_model_combo.clear()

            current_value = self._config.llm.local_model or ""
            custom_label = tr("settings.llm.local_model_custom")

            downloaded = []
            if self._model_manager is not None:
                for entry in self._llm_manifest_entries:
                    model_id = entry.get("id", "")
                    if self._model_manager.is_downloaded(model_id):
                        downloaded.append(entry)

            if not downloaded:
                self._local_model_combo.addItem(tr("settings.llm.no_downloaded_models"), None)
                self._local_model_combo.setEnabled(False)
            else:
                self._local_model_combo.setEnabled(True)
                for entry in downloaded:
                    model_id = entry.get("id", "")
                    description = entry.get("description", model_id)
                    self._local_model_combo.addItem(description, model_id)

            # 「自訂路徑…」永遠是最後一項
            self._local_model_combo.addItem(custom_label, "__custom__")

            # 向後相容：嘗試匹配 current_value
            matched_idx = -1
            for i in range(self._local_model_combo.count()):
                if self._local_model_combo.itemData(i) == current_value:
                    matched_idx = i
                    break

            if matched_idx >= 0:
                self._local_model_combo.setCurrentIndex(matched_idx)
                self._model_path_edit.setVisible(False)
            else:
                # 不匹配任何 manifest model_id → 自動選自訂路徑
                custom_idx = self._local_model_combo.count() - 1
                self._local_model_combo.setCurrentIndex(custom_idx)
                self._model_path_edit.setText(current_value)
                self._model_path_edit.setVisible(True)

            self._local_model_combo.blockSignals(False)

        def refresh_llm_combo(self) -> None:
            """重建 LLM 本機模型下拉（模型下載/刪除後呼叫）。"""
            self._populate_local_model_combo()

        # ── 硬體警示 ──────────────────────────────────────────────────────────

        def _check_hardware_warning(self) -> None:
            """偵測硬體環境，若為 CPU-only 則顯示逾時警示。"""
            try:
                from airtype.utils.hardware_detect import HardwareDetector
                recommendation = HardwareDetector().recommend_llm()
                if recommendation.warning == "approaching_timeout_cpu":
                    warning_label = QLabel(tr("settings.llm.cpu_warning"))
                    warning_label.setWordWrap(True)
                    warning_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
                    # 插入至 local_group 之前
                    layout = self.layout()
                    idx = layout.indexOf(self._local_group)
                    layout.insertWidget(idx, warning_label)
            except Exception:  # noqa: BLE001
                pass  # 偵測失敗時靜默忽略

        # ── 可見性控制 ───────────────────────────────────────────────────────

        def _update_source_visibility(self) -> None:
            is_local = self._config.llm.source == "local"
            self._local_group.setVisible(is_local)
            self._api_group.setVisible(not is_local)

        # ── 儲存 ─────────────────────────────────────────────────────────────

        def _save(self) -> None:
            if callable(self._schedule_save):
                self._schedule_save()

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.llm.title"))
            self._enabled_cb.setText(tr("settings.llm.enable_cb"))
            self._mode_form.labelForField(self._mode_combo).setText(tr("settings.llm.mode"))
            self._mode_form.labelForField(self._preview_cb).setText(tr("settings.llm.preview_before_inject"))
            self._source_form.labelForField(self._source_combo).setText(tr("settings.llm.source"))
            self._source_combo.setItemText(0, tr("settings.llm.source.local"))
            self._source_combo.setItemText(1, tr("settings.llm.source.api"))
            self._local_group.setTitle(tr("settings.llm.local_group_title"))
            self._local_form.labelForField(self._local_model_combo).setText(tr("settings.llm.local_model"))
            self._local_form.labelForField(self._model_path_edit).setText(tr("settings.llm.model_path"))
            self._model_path_edit.setPlaceholderText(tr("settings.llm.model_path_placeholder"))
            # 更新 combo 最後一項「自訂路徑…」的文字
            custom_idx = self._local_model_combo.count() - 1
            if custom_idx >= 0:
                self._local_model_combo.setItemText(custom_idx, tr("settings.llm.local_model_custom"))
            self._api_group.setTitle(tr("settings.llm.api_group_title"))
            self._api_form.labelForField(self._provider_combo).setText(tr("settings.llm.api_provider"))
            self._api_form.labelForField(self._endpoint_edit).setText(tr("settings.llm.api_endpoint"))
            self._endpoint_edit.setPlaceholderText(tr("settings.llm.api_endpoint_placeholder"))
            self._api_form.labelForField(self._api_key_edit).setText(tr("settings.llm.api_key"))
            self._api_key_edit.setPlaceholderText(tr("settings.llm.api_key_placeholder"))
            self._api_note.setText(tr("settings.llm.api_note"))
            for i, (k, _) in enumerate(self._MODE_CODES):
                self._mode_combo.setItemText(i, tr(k))
            for i, (k, _) in enumerate(self._PROVIDER_CODES):
                self._provider_combo.setItemText(i, tr(k))

        # ── 事件處理 ─────────────────────────────────────────────────────────

        def _on_enabled_changed(self, state: int) -> None:
            self._config.llm.enabled = bool(state)
            self._save()
            self._reset_llm_engine()

        def _on_mode_changed(self, index: int) -> None:
            self._config.llm.mode = self._mode_combo.itemData(index)
            self._save()

        def _on_preview_changed(self, state: int) -> None:
            self._config.llm.preview_before_inject = bool(state)
            self._save()

        def _on_source_changed(self, index: int) -> None:
            self._config.llm.source = self._source_combo.itemData(index)
            self._update_source_visibility()
            self._save()

        def _on_local_model_combo_changed(self, index: int) -> None:
            """本機模型 combo 切換：自訂路徑時顯示 QLineEdit，否則儲存 model_id。"""
            data = self._local_model_combo.itemData(index)
            if data == "__custom__":
                self._model_path_edit.setVisible(True)
                # 不直接更新 config，等待使用者在 QLineEdit 輸入
            elif data is not None:
                self._model_path_edit.setVisible(False)
                self._config.llm.local_model = data
                # 同步更新 model_size_b（從 manifest 推斷）
                self._config.llm.model_size_b = self._infer_model_size_b(data)
                self._save()
                # 重置已快取的 LLM 引擎，下次推理時使用新模型
                self._reset_llm_engine()

        def _infer_model_size_b(self, model_id: str) -> float:
            """從 manifest 或模型 ID 推斷模型大小（B）。"""
            # 從 manifest 條目的 size_bytes 推斷
            for entry in self._llm_manifest_entries:
                if entry.get("id") == model_id:
                    size_bytes = entry.get("size_bytes", 0)
                    # GGUF Q4_K_M 約為原始大小的 40%，反推原始參數量
                    # 0.6B → ~350MB, 1.5B → ~1GB, 3B → ~1.9GB, 7B → ~4.4GB
                    if size_bytes > 3_500_000_000:
                        return 7.0
                    if size_bytes > 1_500_000_000:
                        return 3.0
                    if size_bytes > 700_000_000:
                        return 1.5
                    return 0.5
            # fallback：從 model_id 字串猜測
            mid = model_id.lower()
            if "7b" in mid:
                return 7.0
            if "3b" in mid:
                return 3.0
            if "1.5b" in mid:
                return 1.5
            if "0.6b" in mid or "0.5b" in mid:
                return 0.5
            return 1.5  # 保守預設

        def _reset_llm_engine(self) -> None:
            """重置 LLM 引擎快取，使下次推理使用新設定的模型。"""
            try:
                from airtype.core.controller import get_controller
                ctrl = get_controller()
                if ctrl._polish_engine is not None:
                    ctrl._polish_engine.reset()
            except Exception:
                pass

        def _on_model_path_changed(self, text: str) -> None:
            self._config.llm.local_model = text
            self._config.llm.model_size_b = self._infer_model_size_b(text)
            self._save()
            self._reset_llm_engine()

        def _on_provider_changed(self, index: int) -> None:
            self._config.llm.api_provider = self._provider_combo.itemData(index)
            self._save()

        def _on_endpoint_changed(self, text: str) -> None:
            self._config.llm.api_endpoint = text or None
            self._save()

        def _on_api_key_changed(self, text: str) -> None:
            from airtype.config import set_api_key  # noqa: PLC0415
            provider = self._config.llm.api_provider or "openai"
            set_api_key(provider, text or None)

else:

    class SettingsLlmPage:  # type: ignore[no-redef]
        pass
