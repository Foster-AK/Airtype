"""Qwen3-ASR Vulkan 引擎（透過 chatllm.cpp）。

使用 chatllm.cpp 以 Vulkan 後端在跨廠商 GPU（NVIDIA、AMD、Intel）上
執行 Qwen3-ASR GGUF 量化模型推理，透過 subprocess 呼叫。
若 chatllm.cpp 二進位不可用，此引擎不會在登錄檔中登錄，也不產生匯入錯誤。

符合 PRD §6.3.2（chatllm.cpp Vulkan 路徑）。
相依：06-asr-abstraction、07-numpy-preprocessor。
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import wave
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

import sys as _sys


def _hidden_subprocess_kwargs() -> dict:
    """Windows 上隱藏 subprocess console 視窗的額外參數。"""
    if _sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"creationflags": 0x08000000, "startupinfo": si}
    return {}


# ------------------------------------------------------------------
# chatllm.cpp 可用性偵測（Task 2.2）
# ------------------------------------------------------------------


def _find_chatllm_binary() -> Optional[Path]:
    """在 PATH 與常見安裝路徑中尋找 chatllm.cpp 二進位檔。

    Returns:
        chatllm 可執行檔路徑，若未找到則為 None。
    """
    import shutil

    # 嘗試 PATH 中常見名稱
    for name in ("chatllm", "chatllm.exe", "chatllm_cpp"):
        found = shutil.which(name)
        if found:
            return Path(found)

    # 嘗試專案本機路徑
    local_candidates = [
        Path("chatllm/bin/main"),
        Path("chatllm/bin/main.exe"),
        Path("chatllm/chatllm"),
        Path("chatllm/chatllm.exe"),
        Path("bin/chatllm"),
        Path("bin/chatllm.exe"),
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return candidate.resolve()

    return None


def _is_chatllm_available() -> bool:
    """確認 chatllm.cpp 二進位檔可用且可正常執行。

    Returns:
        True 若 chatllm.cpp 可執行，否則 False。
    """
    binary = _find_chatllm_binary()
    if binary is None:
        return False
    try:
        result = subprocess.run(
            [str(binary), "--help"],
            capture_output=True,
            timeout=5,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        # --help 會輸出 Usage 訊息並回傳 0
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ------------------------------------------------------------------
# 引擎實作
# ------------------------------------------------------------------


class QwenVulkanEngine:
    """Qwen3-ASR chatllm.cpp Vulkan 引擎。

    實作 ASREngine Protocol，透過 subprocess 呼叫 chatllm.cpp 二進位
    以 Vulkan 後端推理 GGUF 量化模型，支援跨廠商 GPU（NVIDIA、AMD、Intel）。
    支援延遲載入；若 chatllm.cpp 不可用，此引擎不會在登錄檔中登錄。

    典型用法（延遲載入）::

        engine = QwenVulkanEngine()
        engine.prepare("models/asr/qwen3_asr_q8.gguf")
        result = engine.recognize(audio)

    直接載入::

        engine = QwenVulkanEngine()
        engine.load_model("models/asr/qwen3_asr_q8.gguf", {})
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-vulkan"
    SUPPORTED_LANGUAGES = [
        "zh-TW", "zh-CN", "en", "ja", "ko", "fr", "de", "es", "it", "pt",
    ]

    def __init__(self) -> None:
        # 延遲載入狀態
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # chatllm.cpp 二進位路徑（載入後設定）
        self._binary: Optional[Path] = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol 方法
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """驗證 GGUF 模型檔案與 chatllm.cpp 二進位可用性。

        Args:
            model_path: GGUF 模型檔案路徑。
            config: 引擎設定（可選），支援 "timeout"（預設 60 秒）。

        Raises:
            FileNotFoundError: 模型檔案或 chatllm.cpp 二進位不存在。
        """
        model_file = Path(model_path)
        if not model_file.exists():
            raise FileNotFoundError(
                f"GGUF 模型檔案不存在：{model_path}\n"
                "請執行：python scripts/download_models.py --model qwen3-asr-gguf"
            )

        binary = _find_chatllm_binary()
        if binary is None:
            raise FileNotFoundError(
                "找不到 chatllm.cpp 二進位檔。\n"
                "請從 https://github.com/foldl/chatllm.cpp 下載，"
                "並放置於 PATH 或 ./chatllm/ 目錄。"
            )

        self._binary = binary
        self._model_path = str(model_file.resolve())
        self._config = config or {}
        self._loaded = True
        logger.info(
            "QwenVulkanEngine 已就緒（模型：%s，二進位：%s）",
            model_file.name,
            binary,
        )

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊，透過 chatllm.cpp subprocess 推理。

        首次呼叫時若模型尚未載入，自動觸發延遲載入。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            ASRResult 含辨識文字、語言代碼、信心分數與時間段。

        Raises:
            RuntimeError: 未設定模型路徑。
        """
        self._ensure_loaded()

        text = self._run_subprocess_inference(audio)
        language = self._detect_language(text)
        duration = float(len(audio)) / 16000.0

        return ASRResult(
            text=text,
            language=language,
            confidence=0.85,  # Vulkan subprocess 路徑不提供 token 層級信心分數
            segments=[ASRSegment(text=text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """Vulkan subprocess 路徑不支援串流辨識，回傳空部分結果。"""
        return PartialResult(text="", is_final=False)

    @property
    def supports_hot_words(self) -> bool:
        """Qwen3-ASR Vulkan 不支援原生熱詞偏置。"""
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        """設定熱詞列表，用於提示注入以提升辨識準確率。

        Args:
            words: HotWord 列表，含詞彙與加權分數。
        """
        self._hot_words = list(words)
        logger.debug("已設定 %d 個熱詞", len(words))

    def set_context(self, context_text: str) -> None:
        """設定語境文字，作為提示前綴注入。

        Args:
            context_text: 語境提示文字。
        """
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        """回傳此引擎支援的語言代碼清單。"""
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        """卸載引擎（subprocess 模式無持久 GPU 資源需清理）。"""
        self._binary = None
        self._loaded = False
        logger.info("QwenVulkanEngine 已卸載")

    # ------------------------------------------------------------------
    # 延遲載入
    # ------------------------------------------------------------------

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑，但不立即驗證（延遲載入）。

        首次呼叫 recognize() 時才驗證模型與二進位，以保持應用程式啟動速度。

        Args:
            model_path: GGUF 模型檔案路徑。
            config: 引擎設定（可選）。
        """
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False
        logger.debug("QwenVulkanEngine 已設定模型路徑：%s（延遲載入）", model_path)

    # ------------------------------------------------------------------
    # 內部輔助方法
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """若未載入則觸發延遲載入。"""
        if self._loaded:
            return
        if self._model_path is None:
            raise RuntimeError(
                "引擎未設定模型路徑。"
                "請先呼叫 prepare(model_path) 或 load_model(model_path, config)。"
            )
        self.load_model(self._model_path, self._config)

    def _run_subprocess_inference(self, audio: np.ndarray) -> str:
        """將音訊寫入臨時 WAV 檔並透過 chatllm.cpp subprocess 辨識。

        參考 QwenASRMiniTool 的 chatllm_engine.py 實作：
        - ``-m`` 模型路徑
        - ``-p`` WAV 檔案路徑（chatllm.cpp 的 ASR 模型自動偵測音訊輸入）
        - ``-ngl all`` GPU 全層卸載（Vulkan）
        - ``--hide_banner`` 隱藏啟動橫幅
        - ``cwd`` 設為 chatllm/bin 目錄（解決 DLL 載入問題）

        輸出格式：``language {code}<asr_text>{transcription}``

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            辨識文字字串（失敗時回傳空字串）。
        """
        # 建立臨時 WAV 檔
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        # NamedTemporaryFile 關閉後再寫入（避免 Windows 雙重開啟鎖定）
        self._write_wav(wav_path, audio)

        try:
            # chatllm/bin 目錄（DLL 所在處，必須作為 cwd）
            chatllm_dir = self._binary.parent

            # GPU 裝置 ID（預設 0）
            gpu_device = self._config.get("gpu_device", 0)

            cmd = [
                str(self._binary),
                "-m", str(self._model_path),
                "-ngl", f"{gpu_device}:all",
                "--hide_banner",
                "-p", str(Path(wav_path).resolve()),
            ]

            # 附加系統提示（熱詞 / 語境）
            sys_prompt = self._build_prompt()
            if sys_prompt:
                cmd.extend(["-s", sys_prompt])

            timeout: int = self._config.get("timeout", 120)

            # Windows：隱藏 console 視窗
            import sys
            creationflags = 0
            startupinfo = None
            if sys.platform == "win32":
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                cwd=str(chatllm_dir),
                creationflags=creationflags,
                startupinfo=startupinfo,
            )

            combined = result.stdout + result.stderr

            # chatllm.cpp 可能因 heap corruption 在退出時回傳非零 exit code，
            # 但推理結果仍在 stdout 中。優先檢查輸出是否包含有效 ASR 結果。
            if "<asr_text>" in combined:
                if result.returncode != 0:
                    logger.debug(
                        "chatllm.cpp 退出碼非零（%d）但推理結果有效，忽略退出碼",
                        result.returncode,
                    )
                return self._parse_output(combined)

            if result.returncode != 0:
                logger.warning(
                    "chatllm.cpp 推理失敗（returncode=%d）：%s",
                    result.returncode,
                    combined[:300],
                )
            return ""

        except subprocess.TimeoutExpired:
            logger.warning("chatllm.cpp 推理逾時（> %ds）", timeout)
            return ""
        except OSError as exc:
            logger.warning("chatllm.cpp 執行失敗：%s", exc)
            return ""
        finally:
            # 清除臨時 WAV 檔
            try:
                Path(wav_path).unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _write_wav(wav_path: str, audio: np.ndarray) -> None:
        """將 float32 PCM 音訊寫入 16-bit PCM WAV 檔案（16kHz mono）。

        Args:
            wav_path: 目標 WAV 檔案路徑（字串）。
            audio: 16kHz mono PCM float32 numpy 陣列，值域 [-1.0, 1.0]。
        """
        pcm_int16 = np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(1)   # mono
            wav_file.setsampwidth(2)   # 16-bit
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_int16.tobytes())

    @staticmethod
    def _parse_output(output: str) -> str:
        """解析 chatllm.cpp ASR 輸出。

        chatllm.cpp Qwen3-ASR 模型的輸出格式為：
        ``language {code}<asr_text>{transcription}``

        Args:
            output: chatllm.cpp stdout + stderr 合併字串。

        Returns:
            辨識文字字串。
        """
        if not output or "<asr_text>" not in output:
            return output.strip() if output else ""

        # 取 <asr_text> 之後的所有文字
        text = output.split("<asr_text>", 1)[1].strip()
        return text

    def _build_prompt(self) -> str:
        """建構提示字串（熱詞 + 語境）。

        Returns:
            合併的提示字串，無熱詞與語境時回傳空字串。
        """
        parts: list[str] = []
        if self._context_text:
            parts.append(self._context_text.strip())
        if self._hot_words:
            hw_text = " ".join(hw.word for hw in self._hot_words)
            parts.append(hw_text)
        return " ".join(parts)

    def _detect_language(self, text: str) -> str:
        """依文字內容偵測語言代碼（CJK 比例 > 30% → zh-TW）。"""
        return detect_language_from_cjk_ratio(text)


# ------------------------------------------------------------------
# 引擎登錄（Task 2.2 + Task 3.1）
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 chatllm.cpp 可用，將 QwenVulkanEngine 登錄至 registry。

    本函式在模組被匯入時不自動執行，需由應用程式啟動時顯式呼叫。
    若 chatllm.cpp 二進位不可用，靜默跳過登錄，不拋出錯誤。

    Args:
        registry: ASREngineRegistry 實例。

    Returns:
        True 若成功登錄，False 若 chatllm.cpp 不可用。
    """
    if not _is_chatllm_available():
        logger.debug(
            "chatllm.cpp 二進位不可用，跳過 '%s' 登錄",
            QwenVulkanEngine.ENGINE_ID,
        )
        return False

    registry.register_engine(QwenVulkanEngine.ENGINE_ID, QwenVulkanEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenVulkanEngine.ENGINE_ID)
    return True
