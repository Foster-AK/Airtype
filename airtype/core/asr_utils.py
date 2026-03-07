"""ASR 引擎共用工具函式。

提供各 ASR 引擎共用的輕量工具，避免跨引擎重複實作。
"""
from __future__ import annotations


def detect_language_from_cjk_ratio(text: str) -> str:
    """依 CJK 字元比例偵測語言代碼。

    統計 U+4E00–U+9FFF 範圍的 CJK 統一表意字元佔比：
    > 30% 則判為中文（zh-TW），否則為英文（en）。

    支援語碼轉換文字的正確判斷（中英混合仍回傳 zh-TW）。
    目前不支援日文、韓文、法文等其他語系的精確偵測；
    語言精確性應依賴模型本身的輸出（如 language token）。

    Args:
        text: 待偵測的辨識結果文字。

    Returns:
        語言代碼字串："zh-TW"（含 CJK）或 "en"（純英文/其他）。
    """
    if not text:
        return "zh-TW"
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    if cjk_count > len(text) * 0.3:
        return "zh-TW"
    return "en"
