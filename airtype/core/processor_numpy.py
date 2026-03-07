"""純 NumPy 音訊前處理器 — Qwen3-ASR Mel 頻譜提取與 BPE 提示分詞

不依賴 PyTorch、torchaudio、librosa 或任何機器學習框架。
輸入：16kHz mono float32 PCM（來自 sounddevice）
輸出：log-Mel 頻譜特徵 + 前置提示 token ID

設定（與 Qwen3-ASR / Whisper 相容）：
    n_fft = 400, hop_length = 160, n_mels = 128, sample_rate = 16000
    Mel 刻度：HTK；正規化：Slaney（面積正規化）
    log 公式：log10(max(mel_spec, 1e-10))
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

# ── 模型預設設定 ──────────────────────────────────────────────────────────────
_N_FFT: int = 400
_HOP_LENGTH: int = 160
_N_MELS: int = 128
_SAMPLE_RATE: int = 16000

# 預先計算檔案所在目錄（支援 PyInstaller 打包環境）
from airtype.utils.paths import get_bundled_root

_PRECOMPUTED_DIR: Path = get_bundled_root() / "models" / "precomputed"


class NumpyPreprocessor:
    """純 NumPy Mel 頻譜提取器與 BPE 提示分詞器。

    使用方法：
        proc = NumpyPreprocessor()
        log_mel = proc.extract_mel_spectrogram(audio)   # (n_frames, 128)
        input_ids = proc.prepend_prompt_tokens([101, 202, 303])
    """

    def __init__(
        self,
        precomputed_dir: Optional[Union[Path, str]] = None,
    ) -> None:
        """初始化前處理器，從 precomputed_dir 載入濾波器組與提示模板。

        Args:
            precomputed_dir: 包含 mel_filters.npy 與 prompt_template.json 的目錄。
                             預設為 models/precomputed/（相對於專案根目錄）。

        Raises:
            FileNotFoundError: mel_filters.npy 不存在時拋出。
        """
        if precomputed_dir is None:
            precomputed_dir = _PRECOMPUTED_DIR
        precomputed_dir = Path(precomputed_dir)

        # ── 載入 Mel 濾波器組 ─────────────────────────────────────────────────
        mel_path = precomputed_dir / "mel_filters.npy"
        if not mel_path.exists():
            raise FileNotFoundError(
                f"mel_filters.npy not found at {mel_path}. "
                "Regenerate with: python scripts/generate_precomputed.py"
            )
        self._mel_filters: np.ndarray = np.load(mel_path)  # (n_mels, n_fft//2+1)

        # ── 載入 BPE 提示模板（選用；不存在時使用空列表）────────────────────
        self._prompt_token_ids: List[int] = []
        prompt_path = precomputed_dir / "prompt_template.json"
        if prompt_path.exists():
            with prompt_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._prompt_token_ids = [int(t) for t in data.get("prompt_token_ids", [])]

        # ── 預先計算週期性 Hanning 視窗（共用，避免重複建立）────────────────
        n = np.arange(_N_FFT, dtype=np.float32)
        self._window: np.ndarray = (
            0.5 * (1.0 - np.cos(2.0 * np.pi * n / _N_FFT))
        ).astype(np.float32)

    # ── 屬性 ──────────────────────────────────────────────────────────────────

    @property
    def prompt_token_ids(self) -> List[int]:
        """預先提取的 BPE 提示 token ID 列表（唯讀複本）。"""
        return list(self._prompt_token_ids)

    # ── 公開 API ───────────────────────────────────────────────────────────────

    def extract_mel_spectrogram(self, audio: np.ndarray) -> np.ndarray:
        """從 16kHz mono float32 PCM 音訊提取 log-Mel 頻譜特徵。

        演算法：
            1. 週期性 Hanning 視窗（與 torch.hann_window 預設相符）
            2. 反射填充（左右各 n_fft // 2）
            3. STFT 功率頻譜（numpy.fft.rfft + 幅度平方）
            4. Mel 濾波器矩陣乘法
            5. log10(max(mel_spec, 1e-10))

        Args:
            audio: 1-D float32 ndarray，16kHz mono PCM

        Returns:
            2-D float32 ndarray，shape (n_frames, n_mels)
        """
        audio = np.asarray(audio, dtype=np.float32)

        # 反射填充（左右各 n_fft // 2）
        pad = _N_FFT // 2
        audio_padded = np.pad(audio, (pad, pad), mode="reflect")

        # STFT 功率頻譜
        n_frames = (len(audio_padded) - _N_FFT) // _HOP_LENGTH + 1
        stft = np.empty((_N_FFT // 2 + 1, n_frames), dtype=np.float32)
        for i in range(n_frames):
            start = i * _HOP_LENGTH
            frame = audio_padded[start: start + _N_FFT] * self._window
            spectrum = np.fft.rfft(frame, n=_N_FFT)
            stft[:, i] = np.abs(spectrum) ** 2  # 功率頻譜

        # Mel 濾波器 → log-Mel
        mel_spec = self._mel_filters @ stft             # (n_mels, n_frames)
        log_mel = np.log10(np.maximum(mel_spec, 1e-10))  # floor at 1e-10

        return log_mel.T.astype(np.float32)              # (n_frames, n_mels)

    def prepend_prompt_tokens(self, token_ids: List[int]) -> List[int]:
        """將提示 token ID 前置於輸入序列。

        Args:
            token_ids: 原始 token ID 列表

        Returns:
            新列表：[*prompt_token_ids, *token_ids]
        """
        return list(self._prompt_token_ids) + list(token_ids)
