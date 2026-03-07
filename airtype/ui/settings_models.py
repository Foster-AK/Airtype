"""模型管理設定頁面。

提供 SettingsModelsPage：
- QTabBar 切換 ASR / LLM 分類
- ModelCardWidget 卡片式展示各模型（名稱、描述、大小、推薦徽章、下載狀態）
- DownloadWorker（QThread）背景下載，支援取消
- 模型刪除確認對話框
- 深色/淺色主題適配

符合 specs/settings-models/spec.md。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr  # noqa: E402

try:
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QTabBar,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QThread, Signal, Slot
    from PySide6.QtGui import QColor

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------


def _format_size(size_bytes: int) -> str:
    """將 bytes 格式化為人類可讀字串（MB 或 GB）。

    Args:
        size_bytes: 檔案大小（bytes）。

    Returns:
        人類可讀字串，例如 "650 MB" 或 "1.7 GB"。
    """
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.1f} GB"
    return f"{size_bytes / 1024 ** 2:.0f} MB"


if _PYSIDE6_AVAILABLE:

    # ── 卡片 QSS 樣式 ─────────────────────────────────────────────────────────

    _CARD_QSS_LIGHT = """
QFrame#modelCard {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}
QFrame#modelCard:hover {
    background-color: #f5f5f5;
    border: 1px solid #c8c8c8;
}
"""

    _CARD_QSS_DARK = """
QFrame#modelCard {
    background-color: #3a3a3a;
    border: 1px solid #555;
    border-radius: 8px;
}
QFrame#modelCard:hover {
    background-color: #444;
    border: 1px solid #666;
}
"""

    # ── 背景下載執行緒 ────────────────────────────────────────────────────────

    class DownloadWorker(QThread):
        """背景下載 QThread，封裝 ModelManager.download()。

        Signals:
            progress(int): 下載百分比（0-100）。
            finished(str): 下載完成，發射本地路徑。
            error(str):    下載失敗，發射錯誤訊息。
        """

        progress = Signal(int)
        finished = Signal(str)
        error = Signal(str)

        def __init__(self, model_manager, model_id: str, parent=None) -> None:
            super().__init__(parent)
            self._model_manager = model_manager
            self._model_id = model_id
            self._cancelled = False

        def cancel(self) -> None:
            """設定取消旗標，下載迴圈將在下次 callback 時中斷。"""
            self._cancelled = True

        def run(self) -> None:
            try:
                def _progress_cb(downloaded: int, total: int, percent: float, eta: float) -> None:
                    if self._cancelled:
                        raise InterruptedError("下載已取消")
                    self.progress.emit(int(percent))

                path = self._model_manager.download(self._model_id, _progress_cb)
                if not self._cancelled:
                    self.finished.emit(path)
            except InterruptedError:
                logger.info("下載已取消：%s", self._model_id)
                # 不發射 error，由呼叫方處理取消狀態
            except Exception as exc:  # noqa: BLE001
                logger.error("下載失敗（%s）：%s", self._model_id, exc)
                self.error.emit(str(exc))

    # ── 模型卡片 Widget ───────────────────────────────────────────────────────

    class ModelCardWidget(QFrame):
        """模型卡片，顯示模型資訊與下載/刪除狀態。

        Signals:
            download_requested(str): 使用者點擊下載按鈕，發射 model_id。
            delete_requested(str):   使用者確認刪除，發射 model_id。
            cancel_requested(str):   使用者點擊取消，發射 model_id。
        """

        download_requested = Signal(str)
        delete_requested = Signal(str)
        cancel_requested = Signal(str)

        def __init__(
            self,
            model_entry: dict,
            is_downloaded: bool,
            is_recommended: bool,
            config: "AirtypeConfig",
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._entry = model_entry
            self._model_id: str = model_entry.get("id", "")
            self._config = config
            self.setObjectName("modelCard")
            self._build_ui(is_downloaded, is_recommended)

        def _build_ui(self, is_downloaded: bool, is_recommended: bool) -> None:
            outer = QHBoxLayout(self)
            outer.setContentsMargins(12, 10, 12, 10)
            outer.setSpacing(8)

            # ── 左側文字區 ────────────────────────────────────────────────────
            left = QVBoxLayout()
            left.setSpacing(4)

            # 標題行（名稱 + 推薦徽章）
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            title_row.setContentsMargins(0, 0, 0, 0)
            raw_desc = self._entry.get("description", self._model_id)
            if "（" in raw_desc:
                _parts = raw_desc.split("（", 1)
                name = _parts[0]
                desc_text = _parts[1].rstrip("）").rstrip(")")
            else:
                name = raw_desc
                desc_text = ""
            self._name_label = QLabel(name)
            self._name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            title_row.addWidget(self._name_label)

            self._badge = QLabel(tr("settings.models.card.recommended"))
            self._badge.setStyleSheet(
                "background-color: #22c55e; color: white; border-radius: 4px;"
                "padding: 1px 6px; font-size: 11px;"
            )
            self._badge.setVisible(is_recommended)
            title_row.addWidget(self._badge)
            title_row.addStretch()
            left.addLayout(title_row)

            # 說明文字（括號內容）
            self._desc_label = QLabel(desc_text)
            self._desc_label.setStyleSheet("color: #888; font-size: 11px;")
            self._desc_label.setVisible(bool(desc_text))
            left.addWidget(self._desc_label)

            # 檔案大小
            size_str = _format_size(self._entry.get("size_bytes", 0))
            self._size_label = QLabel(size_str)
            self._size_label.setStyleSheet("color: #888; font-size: 11px;")
            left.addWidget(self._size_label)

            left_widget = QWidget()
            left_widget.setLayout(left)
            outer.addWidget(left_widget, stretch=1)

            # ── 右側動作區（fixedWidth ~120）─────────────────────────────────
            self._action_widget = QWidget()
            self._action_widget.setFixedWidth(90)
            action_layout = QVBoxLayout(self._action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 狀態 1：未下載 → 下載按鈕
            self._download_btn = QPushButton(tr("settings.models.card.download"))
            self._download_btn.setFixedWidth(80)
            self._download_btn.clicked.connect(lambda: self.download_requested.emit(self._model_id))
            action_layout.addWidget(self._download_btn)

            # 狀態 2：下載中 → 進度條 + 百分比 + 取消按鈕
            self._progress_container = QWidget()
            prog_layout = QVBoxLayout(self._progress_container)
            prog_layout.setContentsMargins(0, 0, 0, 0)
            prog_layout.setSpacing(2)
            self._progress_bar = QProgressBar()
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_bar.setFixedWidth(80)
            self._progress_bar.setTextVisible(False)
            prog_layout.addWidget(self._progress_bar)
            self._percent_label = QLabel("0%")
            self._percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._percent_label.setStyleSheet("font-size: 11px;")
            prog_layout.addWidget(self._percent_label)
            self._cancel_btn = QPushButton(tr("settings.models.card.cancel"))
            self._cancel_btn.setFixedWidth(80)
            self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self._model_id))
            prog_layout.addWidget(self._cancel_btn)
            action_layout.addWidget(self._progress_container)

            # 狀態 3：已下載 → 綠勾 + 刪除按鈕
            self._downloaded_container = QWidget()
            done_layout = QVBoxLayout(self._downloaded_container)
            done_layout.setContentsMargins(0, 0, 0, 0)
            done_layout.setSpacing(2)
            self._done_label = QLabel(tr("settings.models.card.downloaded"))
            self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._done_label.setStyleSheet("color: #22c55e; font-size: 11px;")
            done_layout.addWidget(self._done_label)
            self._delete_btn = QPushButton(tr("settings.models.card.delete"))
            self._delete_btn.setFixedWidth(80)
            self._delete_btn.clicked.connect(self._on_delete_clicked)
            done_layout.addWidget(self._delete_btn)
            action_layout.addWidget(self._downloaded_container)

            outer.addWidget(self._action_widget)

            # 初始狀態
            if is_downloaded:
                self._set_state("downloaded")
            else:
                self._set_state("idle")

        # ── 狀態切換 ──────────────────────────────────────────────────────────

        def _set_state(self, state: str) -> None:
            """切換卡片狀態：'idle' / 'downloading' / 'downloaded'。"""
            self._download_btn.setVisible(state == "idle")
            self._progress_container.setVisible(state == "downloading")
            self._downloaded_container.setVisible(state == "downloaded")

        def set_downloading(self) -> None:
            """切換至下載中狀態。"""
            self._set_state("downloading")
            self._progress_bar.setValue(0)
            self._percent_label.setText("0%")

        def update_progress(self, percent: int) -> None:
            """更新進度條與百分比 label。"""
            self._progress_bar.setValue(percent)
            self._percent_label.setText(f"{percent}%")

        def set_downloaded(self) -> None:
            """切換至已下載狀態。"""
            self._set_state("downloaded")

        def set_idle(self) -> None:
            """切換至未下載狀態。"""
            self._set_state("idle")

        def set_download_enabled(self, enabled: bool) -> None:
            """啟用或禁用下載按鈕（用於同時間只允許一個下載）。"""
            self._download_btn.setEnabled(enabled)

        # ── 刪除確認 ──────────────────────────────────────────────────────────

        def _on_delete_clicked(self) -> None:
            """點擊刪除按鈕：先顯示確認對話框，確認後發射 delete_requested Signal。"""
            name = self._entry.get("description", self._model_id)

            # 若模型正在使用中則顯示警告
            in_use = (
                self._config.voice.asr_model == self._model_id
                or self._config.llm.local_model == self._model_id
            )
            if in_use:
                QMessageBox.warning(
                    self,
                    tr("settings.models.confirm_delete_title"),
                    tr("settings.models.in_use_warning"),
                )

            reply = QMessageBox.question(
                self,
                tr("settings.models.confirm_delete_title"),
                tr("settings.models.confirm_delete_msg").format(name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_requested.emit(self._model_id)

        # ── 主題適配 ──────────────────────────────────────────────────────────

        def apply_theme(self, theme: str) -> None:
            """套用對應主題的 QSS。"""
            if theme == "dark":
                self.setStyleSheet(_CARD_QSS_DARK)
            else:
                self.setStyleSheet(_CARD_QSS_LIGHT)

    # ── 模型管理設定頁面 ──────────────────────────────────────────────────────

    class SettingsModelsPage(QWidget):
        """模型管理設定頁面。

        QTabBar（ASR / LLM）+ QScrollArea 卡片列表。

        Signals:
            model_downloaded(str): 模型下載完成，發射 model_id。
            model_deleted(str):    模型刪除完成，發射 model_id。
        """

        model_downloaded = Signal(str)
        model_deleted = Signal(str)

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._cards: list[ModelCardWidget] = []
            self._active_worker: Optional[DownloadWorker] = None
            self._active_model_id: Optional[str] = None
            self._model_manager = None
            self._recommended_model: Optional[str] = None
            self._init_model_manager()
            self._build_ui()
            self._populate_cards(0)

        def _init_model_manager(self) -> None:
            """初始化 ModelManager 與硬體偵測。"""
            try:
                from airtype.utils.model_manager import ModelManager
                from airtype.utils.hardware_detect import HardwareDetector, recommend_inference_path
                self._model_manager = ModelManager()
                caps = HardwareDetector().assess()
                path = recommend_inference_path(caps)
                self._recommended_model = path.model
            except Exception as exc:  # noqa: BLE001
                logger.debug("ModelManager 初始化失敗：%s", exc)

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(8)

            # 標題
            self._title_label = QLabel(tr("settings.models.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            # HuggingFace Access Token 輸入區域
            hf_frame = QFrame()
            hf_frame.setFrameShape(QFrame.Shape.StyledPanel)
            hf_layout = QVBoxLayout(hf_frame)
            hf_layout.setContentsMargins(12, 8, 12, 8)
            hf_layout.setSpacing(4)

            hf_label = QLabel(tr("settings.models.hf_token_label"))
            hf_label.setStyleSheet("font-weight: bold; font-size: 12px;")
            hf_layout.addWidget(hf_label)

            hf_desc = QLabel(tr("settings.models.hf_token_desc"))
            hf_desc.setWordWrap(True)
            hf_desc.setStyleSheet("color: #888; font-size: 11px;")
            hf_layout.addWidget(hf_desc)

            hf_input_row = QHBoxLayout()
            hf_input_row.setSpacing(6)
            self._hf_token_input = QLineEdit()
            self._hf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._hf_token_input.setPlaceholderText(tr("settings.models.hf_token_placeholder"))
            self._hf_token_input.editingFinished.connect(self._on_hf_token_save)
            hf_input_row.addWidget(self._hf_token_input)

            self._hf_token_clear_btn = QPushButton(tr("settings.models.hf_token_clear"))
            self._hf_token_clear_btn.setFixedWidth(60)
            self._hf_token_clear_btn.clicked.connect(self._on_hf_token_clear)
            hf_input_row.addWidget(self._hf_token_clear_btn)
            hf_layout.addLayout(hf_input_row)
            outer.addWidget(hf_frame)

            self._init_hf_token_display()

            # QTabBar（先建立，信號在所有子 widget 建立完畢後才連接）
            self._tab_bar = QTabBar()
            self._tab_bar.addTab(tr("settings.models.tab_asr"))
            self._tab_bar.addTab(tr("settings.models.tab_llm"))
            outer.addWidget(self._tab_bar)

            # QScrollArea
            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._cards_container = QWidget()
            self._cards_layout = QVBoxLayout(self._cards_container)
            self._cards_layout.setContentsMargins(0, 4, 0, 4)
            self._cards_layout.setSpacing(8)
            self._cards_layout.addStretch()
            self._scroll.setWidget(self._cards_container)
            outer.addWidget(self._scroll, stretch=1)

            # 所有子 widget 建立後才連接 tab 信號，避免 currentChanged 在 _cards_layout 存在前觸發
            self._tab_bar.currentChanged.connect(self._on_tab_changed)

        # ── Tab 切換 ─────────────────────────────────────────────────────────

        def _on_tab_changed(self, index: int) -> None:
            """切換分類 tab，清空並重建卡片列表。"""
            self._populate_cards(index)

        def _populate_cards(self, tab_index: int) -> None:
            """清空卡片列表並重建指定分類的卡片。"""
            # 清空現有卡片
            while self._cards_layout.count() > 1:
                item = self._cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._cards = []

            if self._model_manager is None:
                return

            category = "asr" if tab_index == 0 else "llm"
            entries = self._model_manager.list_models_by_category(category)
            theme = getattr(self._config.appearance, "theme", "light")

            for entry in entries:
                model_id = entry.get("id", "")
                is_downloaded = self._model_manager.is_downloaded(model_id)
                is_recommended = (model_id == self._recommended_model)

                card = ModelCardWidget(
                    entry,
                    is_downloaded=is_downloaded,
                    is_recommended=is_recommended,
                    config=self._config,
                    parent=self,
                )
                card.apply_theme(theme)
                card.download_requested.connect(self._on_download_requested)
                card.delete_requested.connect(self._on_delete_requested)
                card.cancel_requested.connect(self._on_cancel_requested)
                self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
                self._cards.append(card)

            # 若有 active worker（下載中），更新按鈕狀態
            if self._active_worker is not None and self._active_worker.isRunning():
                self._set_all_download_buttons(False)
                # 找到對應卡片恢復 downloading 狀態
                for card in self._cards:
                    if card._model_id == self._active_model_id:
                        card.set_downloading()

        # ── 下載處理 ─────────────────────────────────────────────────────────

        def _on_download_requested(self, model_id: str) -> None:
            """啟動背景下載。"""
            if self._model_manager is None:
                return
            if self._active_worker is not None and self._active_worker.isRunning():
                return  # 已有進行中的下載

            card = self._find_card(model_id)
            if card is None:
                return

            self._active_model_id = model_id
            worker = DownloadWorker(self._model_manager, model_id, self)
            worker.progress.connect(lambda p: self._on_download_progress(model_id, p))
            worker.finished.connect(lambda path: self._on_download_finished(model_id, path))
            worker.error.connect(lambda err: self._on_download_error(model_id, err))
            self._active_worker = worker

            card.set_downloading()
            self._set_all_download_buttons(False)
            worker.start()

        @Slot()
        def _on_cancel_requested(self, model_id: str) -> None:
            """取消下載。"""
            if self._active_worker is not None:
                self._active_worker.cancel()
                self._active_worker.wait(3000)
                self._active_worker = None
                self._active_model_id = None
            card = self._find_card(model_id)
            if card:
                card.set_idle()
            self._set_all_download_buttons(True)

        def _on_download_progress(self, model_id: str, percent: int) -> None:
            card = self._find_card(model_id)
            if card:
                card.update_progress(percent)

        def _on_download_finished(self, model_id: str, path: str) -> None:
            self._active_worker = None
            self._active_model_id = None
            card = self._find_card(model_id)
            if card:
                card.set_downloaded()
            self._set_all_download_buttons(True)
            self.model_downloaded.emit(model_id)
            logger.info("模型下載完成：%s → %s", model_id, path)

        def _init_hf_token_display(self) -> None:
            """頁面載入時顯示 HF token 是否已設定（不顯示明文）。"""
            try:
                from airtype.config import get_api_key  # noqa: PLC0415
                token = get_api_key("huggingface")
                if token:
                    self._hf_token_input.setPlaceholderText(
                        tr("settings.models.hf_token_set_placeholder")
                    )
            except Exception:  # noqa: BLE001
                pass

        def _on_hf_token_save(self) -> None:
            """輸入結束後儲存 HF token 至 keyring。"""
            text = self._hf_token_input.text().strip()
            if text:
                from airtype.config import set_api_key  # noqa: PLC0415
                set_api_key("huggingface", text)
                logger.debug("HuggingFace token 已儲存至 keyring")

        def _on_hf_token_clear(self) -> None:
            """清除 HF token（移除 keyring 並清空輸入欄）。"""
            self._hf_token_input.clear()
            from airtype.config import set_api_key  # noqa: PLC0415
            set_api_key("huggingface", "")
            self._hf_token_input.setPlaceholderText(
                tr("settings.models.hf_token_placeholder")
            )
            logger.debug("HuggingFace token 已清除")

        def _on_download_error(self, model_id: str, error: str) -> None:
            self._active_worker = None
            self._active_model_id = None
            card = self._find_card(model_id)
            if card:
                card.set_idle()
            self._set_all_download_buttons(True)
            if "401" in error:
                QMessageBox.warning(
                    self,
                    tr("settings.models.card.download"),
                    tr("settings.models.hf_token_401_error"),
                )
            else:
                QMessageBox.warning(
                    self,
                    tr("settings.models.card.download"),
                    tr("settings.models.download_error").format(error),
                )

        # ── 刪除處理 ─────────────────────────────────────────────────────────

        def _on_delete_requested(self, model_id: str) -> None:
            """執行模型刪除。"""
            if self._model_manager is None:
                return
            try:
                self._model_manager.delete_model(model_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("刪除模型失敗：%s", exc)
                return
            card = self._find_card(model_id)
            if card:
                card.set_idle()
            self.model_deleted.emit(model_id)

        # ── 主題適配 ──────────────────────────────────────────────────────────

        def apply_card_theme(self, theme: str) -> None:
            """更新所有卡片的主題 QSS。"""
            for card in self._cards:
                card.apply_theme(theme)

        # ── 工具 ─────────────────────────────────────────────────────────────

        def _find_card(self, model_id: str) -> Optional[ModelCardWidget]:
            """依 model_id 尋找卡片 widget。"""
            for card in self._cards:
                if card._model_id == model_id:
                    return card
            return None

        def _set_all_download_buttons(self, enabled: bool) -> None:
            """啟用或禁用所有卡片的下載按鈕。"""
            for card in self._cards:
                card.set_download_enabled(enabled)

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新標題與 tab 文字。"""
            self._title_label.setText(tr("settings.models.title"))
            self._tab_bar.setTabText(0, tr("settings.models.tab_asr"))
            self._tab_bar.setTabText(1, tr("settings.models.tab_llm"))

else:

    class SettingsModelsPage:  # type: ignore[no-redef]
        pass

    class DownloadWorker:  # type: ignore[no-redef]
        pass

    class ModelCardWidget:  # type: ignore[no-redef]
        pass
