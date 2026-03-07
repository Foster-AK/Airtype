"""sherpa-onnx 引擎（SenseVoice / Paraformer）。

使用 sherpa-onnx Python 繫結搭配 OfflineRecognizer（SenseVoice / Paraformer）
執行批次語音辨識，並可選用 OnlineRecognizer 支援串流辨識。
支援透過 hotwords_file 參數注入熱詞以提升辨識準確率。
若 sherpa-onnx 不可用，此引擎不會在登錄檔中登錄，也不產生匯入錯誤。

符合 PRD §6.3.3（sherpa-onnx SenseVoice / Paraformer）。
相依：06-asr-abstraction。
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np

from airtype.core.asr_engine import (
    ASREngineRegistry,
    ASRResult,
    ASRSegment,
    HotWord,
    PartialResult,
)
from airtype.core.asr_utils import detect_language_from_cjk_ratio

logger = logging.getLogger(__name__)


class SherpaOnnxEngine:
    """sherpa-onnx SenseVoice / Paraformer 引擎。

    實作 ASREngine Protocol，使用 sherpa-onnx Python 繫結搭配
    OfflineRecognizer 執行批次辨識，OnlineRecognizer 執行串流辨識。
    支援延遲載入；若 sherpa-onnx 不可用，此引擎不會在登錄檔中登錄。

    典型用法（延遲載入）::

        engine = SherpaOnnxEngine(model_type="sensevoice")
        engine.prepare("models/asr/sherpa_sensevoice/")
        result = engine.recognize(audio)

    直接載入::

        engine = SherpaOnnxEngine(model_type="paraformer")
        engine.load_model("models/asr/sherpa_paraformer/", {})
        result = engine.recognize(audio)
    """

    SENSEVOICE_ENGINE_ID = "sherpa-sensevoice"
    PARAFORMER_ENGINE_ID = "sherpa-paraformer"
    SUPPORTED_LANGUAGES = ["zh-TW", "zh-CN", "en", "ja", "ko"]

    def __init__(self, model_type: str = "sensevoice") -> None:
        # 模型類型（"sensevoice" 或 "paraformer"）
        self._model_type: str = model_type

        # 延遲載入狀態
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # sherpa-onnx recognizer（載入後設定）
        self._offline_recognizer = None
        self._online_recognizer = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._hotwords_file_path: Optional[str] = None
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol 方法
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 sherpa-onnx 模型（OfflineRecognizer 及可選的 OnlineRecognizer）。

        Args:
            model_path: 模型目錄路徑。
            config: 引擎設定，支援：
                - "tokens"：tokens.txt 路徑（預設 model_path/tokens.txt）
                - "model"：模型 .onnx 路徑（預設 model_path/model.onnx）
                - "online_model_path"：OnlineRecognizer 模型目錄（可選，啟用串流辨識）

        Raises:
            FileNotFoundError: 模型目錄不存在。
            ImportError: sherpa-onnx 未安裝。
        """
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請執行：python scripts/download_models.py --model sherpa-onnx"
            )

        config = config or {}
        self._model_path = model_path
        self._config = config

        import sherpa_onnx  # noqa: PLC0415

        self._offline_recognizer = self._build_offline_recognizer(
            sherpa_onnx, model_dir, config
        )

        online_model_path = config.get("online_model_path")
        if online_model_path:
            self._online_recognizer = self._build_online_recognizer(
                sherpa_onnx, Path(online_model_path), config
            )

        self._loaded = True
        logger.info(
            "SherpaOnnxEngine 已就緒（model_type：%s，模型：%s）",
            self._model_type,
            model_dir.name,
        )

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊，回傳完整結果。

        首次呼叫時若模型尚未載入，自動觸發延遲載入。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            ASRResult 含辨識文字、語言代碼、信心分數與時間段。

        Raises:
            RuntimeError: 未設定模型路徑。
        """
        self._ensure_loaded()

        stream = self._offline_recognizer.create_stream()
        stream.accept_waveform(16000, audio)
        self._offline_recognizer.decode_stream(stream)
        text = str(stream.result.text).strip()

        language = self._detect_language(text)
        duration = float(len(audio)) / 16000.0

        return ASRResult(
            text=text,
            language=language,
            confidence=0.85,
            segments=[ASRSegment(text=text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """串流辨識音訊區塊。

        若未設定 OnlineRecognizer（無 online_model_path 設定），回傳空部分結果。

        Args:
            chunk: 16kHz mono PCM float32 numpy 音訊區塊。

        Returns:
            PartialResult 含目前辨識文字與端點標誌。
        """
        if self._online_recognizer is None:
            return PartialResult(text="", is_final=False)

        stream = self._online_recognizer.create_stream()
        stream.accept_waveform(16000, chunk)

        while self._online_recognizer.is_ready(stream):
            self._online_recognizer.decode_stream(stream)

        is_endpoint = bool(self._online_recognizer.is_endpoint(stream))
        result = self._online_recognizer.get_result(stream)
        text = str(result.text).strip() if hasattr(result, "text") else ""

        return PartialResult(text=text, is_final=is_endpoint)

    def set_hot_words(self, words: list[HotWord]) -> None:
        """設定熱詞列表，並寫入臨時檔案以供 OfflineRecognizer 使用。

        若引擎已載入，自動重建 OfflineRecognizer 以套用新熱詞。

        Args:
            words: HotWord 列表，含詞彙與加權分數。
        """
        self._hot_words = list(words)
        self._write_hotwords_file()
        logger.debug("已設定 %d 個熱詞", len(words))

        if self._loaded:
            self._rebuild_offline_recognizer()

    def set_context(self, context_text: str) -> None:
        """設定語境文字（sherpa-onnx 暫不直接使用，僅儲存備用）。

        Args:
            context_text: 語境提示文字。
        """
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        """回傳此引擎支援的語言代碼清單。"""
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        """卸載模型並清理資源（含熱詞臨時檔案）。"""
        self._offline_recognizer = None
        self._online_recognizer = None
        self._loaded = False

        if self._hotwords_file_path:
            try:
                Path(self._hotwords_file_path).unlink(missing_ok=True)
            except OSError:
                pass
            self._hotwords_file_path = None

        logger.info("SherpaOnnxEngine 已卸載")

    # ------------------------------------------------------------------
    # 延遲載入
    # ------------------------------------------------------------------

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑，但不立即載入（延遲載入）。

        首次呼叫 recognize() 時才載入模型，以保持應用程式啟動速度。

        Args:
            model_path: 模型目錄路徑。
            config: 引擎設定（可選）。
        """
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False
        logger.debug(
            "SherpaOnnxEngine 已設定模型路徑：%s（延遲載入）", model_path
        )

    # ------------------------------------------------------------------
    # 內部輔助方法
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """若模型尚未載入則觸發延遲載入。"""
        if self._loaded:
            return
        if self._model_path is None:
            raise RuntimeError(
                "引擎未設定模型路徑。"
                "請先呼叫 prepare(model_path) 或 load_model(model_path, config)。"
            )
        self.load_model(self._model_path, self._config)

    def _build_offline_recognizer(
        self, sherpa_onnx: Any, model_dir: Path, config: dict[str, Any]
    ) -> Any:
        """依 model_type 建構 OfflineRecognizer（使用工廠方法 API）。

        Args:
            sherpa_onnx: sherpa_onnx 模組。
            model_dir: 模型目錄路徑。
            config: 引擎設定。

        Returns:
            OfflineRecognizer 實例。
        """
        tokens = config.get("tokens", str(model_dir / "tokens.txt"))
        model_file = config.get("model", str(model_dir / "model.onnx"))

        if self._model_type == "sensevoice":
            return sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_file,
                tokens=tokens,
                language="auto",
                use_itn=False,
            )
        else:  # paraformer
            return sherpa_onnx.OfflineRecognizer.from_paraformer(
                paraformer=model_file,
                tokens=tokens,
            )

    def _build_online_recognizer(
        self, sherpa_onnx: Any, model_dir: Path, config: dict[str, Any]
    ) -> Any:
        """建構 OnlineRecognizer（串流辨識，Zipformer2 CTC 工廠方法）。

        Args:
            sherpa_onnx: sherpa_onnx 模組。
            model_dir: 線上模型目錄路徑。
            config: 引擎設定。

        Returns:
            OnlineRecognizer 實例。
        """
        tokens = config.get("online_tokens", str(model_dir / "tokens.txt"))
        encoder = config.get("online_encoder", str(model_dir / "encoder.onnx"))

        return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
            tokens=tokens,
            model=encoder,
        )

    def _rebuild_offline_recognizer(self) -> None:
        """重建 OfflineRecognizer（套用最新熱詞設定）。"""
        if self._model_path is None:
            return
        import sherpa_onnx  # noqa: PLC0415

        model_dir = Path(self._model_path)
        self._offline_recognizer = self._build_offline_recognizer(
            sherpa_onnx, model_dir, self._config
        )
        logger.debug("SherpaOnnxEngine OfflineRecognizer 已重建（含熱詞）")

    def _write_hotwords_file(self) -> None:
        """將熱詞列表寫入臨時 TXT 檔案（sherpa-onnx hotwords_file 格式，每行一詞）。"""
        # 清除舊臨時檔案
        if self._hotwords_file_path:
            try:
                Path(self._hotwords_file_path).unlink(missing_ok=True)
            except OSError:
                pass

        if not self._hot_words:
            self._hotwords_file_path = None
            return

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            for hw in self._hot_words:
                f.write(hw.word + "\n")
            self._hotwords_file_path = f.name

        logger.debug("熱詞已寫入臨時檔案：%s", self._hotwords_file_path)

    def _detect_language(self, text: str) -> str:
        """依文字內容偵測語言代碼（CJK 比例 > 30% → zh-TW）。"""
        return detect_language_from_cjk_ratio(text)


# ------------------------------------------------------------------
# 引擎登錄（Task 2.4）
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 sherpa-onnx 可用，將 SherpaOnnxEngine 登錄至 registry。

    同時登錄兩個引擎 ID：
    - "sherpa-sensevoice"：SenseVoice 模型
    - "sherpa-paraformer"：Paraformer 模型

    本函式在模組被匯入時不自動執行，需由應用程式啟動時顯式呼叫。
    若 sherpa-onnx 未安裝，靜默跳過登錄，不拋出錯誤。

    Args:
        registry: ASREngineRegistry 實例。

    Returns:
        True 若成功登錄，False 若 sherpa-onnx 不可用。
    """
    try:
        import sherpa_onnx  # noqa: F401, PLC0415
    except ImportError:
        logger.debug(
            "sherpa_onnx 套件未安裝，跳過 '%s'、'%s' 登錄",
            SherpaOnnxEngine.SENSEVOICE_ENGINE_ID,
            SherpaOnnxEngine.PARAFORMER_ENGINE_ID,
        )
        return False

    registry.register_engine(
        SherpaOnnxEngine.SENSEVOICE_ENGINE_ID,
        lambda: SherpaOnnxEngine(model_type="sensevoice"),
    )
    registry.register_engine(
        SherpaOnnxEngine.PARAFORMER_ENGINE_ID,
        lambda: SherpaOnnxEngine(model_type="paraformer"),
    )
    logger.info(
        "已登錄 ASR 引擎：%s, %s",
        SherpaOnnxEngine.SENSEVOICE_ENGINE_ID,
        SherpaOnnxEngine.PARAFORMER_ENGINE_ID,
    )
    return True
