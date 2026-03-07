"""潤飾預覽對話框。

顯示原始文字與潤飾後文字並排比對，讓使用者選擇要注入哪個版本。
僅在 config.llm.preview_before_inject 為 True 時使用。
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QRadioButton,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    class PolishPreviewDialog(QDialog):
        """並排顯示原始文字與潤飾後文字的選擇對話框。

        回傳值（exec() 後）：
        - QDialog.Accepted：使用者已選擇並確認
        - QDialog.Rejected：使用者取消

        使用 selected_text() 取得最終選擇結果。
        """

        def __init__(
            self,
            original: str,
            polished: str,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._original = original
            self._polished = polished
            self._use_polished: bool = True
            self._build_ui()

        def _build_ui(self) -> None:
            self.setWindowTitle("LLM 潤飾預覽")
            self.setMinimumWidth(600)
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )
            self.setStyleSheet(
                "QDialog { background: #1e1e1e; color: #dcdcdc; }"
                "QTextEdit { background: #2d2d2d; color: #dcdcdc; border: 1px solid #444; border-radius: 4px; }"
                "QRadioButton { color: #dcdcdc; }"
                "QRadioButton::indicator:checked { background: #0a84ff; border-radius: 5px; }"
                "QPushButton { background: #3a3a3a; color: #dcdcdc; border: 1px solid #555; "
                "border-radius: 4px; padding: 6px 16px; }"
                "QPushButton:hover { background: #4a4a4a; }"
                "QPushButton[default='true'] { background: #0a84ff; border-color: #0a84ff; }"
            )

            root = QVBoxLayout(self)
            root.setSpacing(12)
            root.setContentsMargins(16, 16, 16, 16)

            # 標題
            title = QLabel("選擇要注入的文字版本")
            title.setStyleSheet("font-size: 14px; font-weight: bold;")
            root.addWidget(title)

            # 並排文字區
            compare_layout = QHBoxLayout()
            compare_layout.setSpacing(12)

            # 原始文字欄
            orig_col = QVBoxLayout()
            self._orig_radio = QRadioButton("原始文字")
            orig_text = QTextEdit()
            orig_text.setPlainText(self._original)
            orig_text.setReadOnly(True)
            orig_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            orig_col.addWidget(self._orig_radio)
            orig_col.addWidget(orig_text)
            compare_layout.addLayout(orig_col)

            # 潤飾後文字欄
            polish_col = QVBoxLayout()
            self._polish_radio = QRadioButton("潤飾後文字")
            self._polish_radio.setChecked(True)
            polish_text = QTextEdit()
            polish_text.setPlainText(self._polished)
            polish_text.setReadOnly(True)
            polish_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            polish_col.addWidget(self._polish_radio)
            polish_col.addWidget(polish_text)
            compare_layout.addLayout(polish_col)

            root.addLayout(compare_layout)

            # Radio 互斥
            self._orig_radio.toggled.connect(
                lambda checked: setattr(self, "_use_polished", not checked)
            )
            self._polish_radio.toggled.connect(
                lambda checked: setattr(self, "_use_polished", checked)
            )

            # 按鈕列
            btn_box = QDialogButtonBox()
            ok_btn = QPushButton("注入")
            ok_btn.setProperty("default", True)
            cancel_btn = QPushButton("取消")
            btn_box.addButton(ok_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            btn_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
            btn_box.accepted.connect(self.accept)
            btn_box.rejected.connect(self.reject)
            root.addWidget(btn_box)

        def selected_text(self) -> str:
            """回傳使用者選擇的文字版本。"""
            return self._polished if self._use_polished else self._original

else:

    class PolishPreviewDialog:  # type: ignore[no-redef]
        """PySide6 不可用時的替代類別。"""

        def __init__(self, original: str, polished: str, parent=None) -> None:
            self._original = original
            self._polished = polished

        def exec(self) -> int:
            return 0

        def selected_text(self) -> str:
            return self._original
