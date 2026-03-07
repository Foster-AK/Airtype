"""純 NumPy 音訊前處理器測試 — airtype.core.processor_numpy

涵蓋：
- Task 3.2  無 PyTorch/torchaudio/librosa 依賴
- Task 3.1  數值精度：vs 樸素參考實作，容差 < 1e-4
- Mel 頻譜提取（形狀、dtype、確定性、數值範圍、頻率定位）
- Mel 濾波器組載入（形狀、dtype、遺失時 FileNotFoundError）
- BPE 提示分詞（載入、前置）
"""
from __future__ import annotations

import importlib.util
import sys
import numpy as np
import pytest
from pathlib import Path


def _has_torchaudio() -> bool:
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("torchaudio") is not None
    )


# ── 常數（與 processor_numpy.py 保持一致）────────────────────────────────────
N_FFT = 400
HOP_LENGTH = 160
N_MELS = 128
SAMPLE_RATE = 16000


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def preprocessor():
    from airtype.core.processor_numpy import NumpyPreprocessor
    return NumpyPreprocessor()


# ── Task 3.2 ── 無 PyTorch 依賴 ───────────────────────────────────────────────

class TestNoPytorchDependency:
    """Task 3.2：匯入 processor_numpy 後，torch/torchaudio/librosa 不應出現於 sys.modules。"""

    def test_import_does_not_load_torch(self):
        """Importing processor_numpy must not trigger torch/torchaudio/librosa import."""
        # 清除快取的禁用模組（若存在）
        for forbidden in ("torch", "torchaudio", "librosa"):
            sys.modules.pop(forbidden, None)

        import importlib
        import airtype.core.processor_numpy as _mod
        importlib.reload(_mod)

        for forbidden in ("torch", "torchaudio", "librosa"):
            assert forbidden not in sys.modules, (
                f"'{forbidden}' 被 processor_numpy 意外匯入 — 移除此依賴"
            )


# ── Mel 頻譜提取 ──────────────────────────────────────────────────────────────

class TestMelSpectrogramExtraction:
    """驗證：Mel 頻譜提取需求（shape、dtype、確定性、數值範圍、頻率定位）。"""

    def test_output_shape_1s(self, preprocessor):
        """1 秒音訊 → 輸出 (n_frames, 128) 形狀。"""
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        result = preprocessor.extract_mel_spectrogram(audio)
        assert result.ndim == 2
        assert result.shape[1] == N_MELS

    def test_output_shape_3s(self, preprocessor):
        """3 秒音訊 → 128 個頻帶。"""
        rng = np.random.default_rng(0)
        audio = rng.standard_normal(SAMPLE_RATE * 3).astype(np.float32) * 0.1
        result = preprocessor.extract_mel_spectrogram(audio)
        assert result.shape[1] == N_MELS

    def test_output_is_float32(self, preprocessor):
        """輸出 dtype 必須為 float32。"""
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        result = preprocessor.extract_mel_spectrogram(audio)
        assert result.dtype == np.float32

    def test_deterministic(self, preprocessor):
        """相同輸入必須產生完全相同的輸出。"""
        rng = np.random.default_rng(0)
        audio = rng.standard_normal(SAMPLE_RATE).astype(np.float32)
        r1 = preprocessor.extract_mel_spectrogram(audio)
        r2 = preprocessor.extract_mel_spectrogram(audio)
        np.testing.assert_array_equal(r1, r2)

    def test_log_mel_range_is_finite(self, preprocessor):
        """Log-Mel 值必須為有限數值。"""
        rng = np.random.default_rng(1)
        audio = rng.standard_normal(SAMPLE_RATE).astype(np.float32) * 0.1
        result = preprocessor.extract_mel_spectrogram(audio)
        assert np.all(np.isfinite(result))

    def test_log_mel_floor_at_minus_10(self, preprocessor):
        """Log10(1e-10) = -10；靜音幀的值不應低於 -10。"""
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        result = preprocessor.extract_mel_spectrogram(audio)
        assert np.all(result >= -10.0)

    def test_sine_440hz_peak_in_lower_mel_bins(self, preprocessor):
        """440 Hz 正弦波的峰值 Mel 頻帶應低於第 64 個頻帶（位於 Mel 刻度下半段）。"""
        t = np.arange(SAMPLE_RATE, dtype=np.float32) / SAMPLE_RATE
        audio = np.sin(2.0 * np.pi * 440.0 * t)
        result = preprocessor.extract_mel_spectrogram(audio)
        mean_per_bin = result.mean(axis=0)
        peak_bin = int(np.argmax(mean_per_bin))
        assert peak_bin < 64, f"預期峰值低於第 64 頻帶，實際為第 {peak_bin} 頻帶"


# ── Task 3.1 ── 數值精度 ──────────────────────────────────────────────────────

class TestNumericalPrecision:
    """Task 3.1：數值精度 — 與樸素參考實作的最大絕對差 < 1e-4。"""

    def test_precision_vs_naive_reference(self, preprocessor):
        """與使用相同公式的樸素 NumPy 參考實作相比，容差 < 1e-4。"""
        rng = np.random.default_rng(42)
        audio = rng.standard_normal(SAMPLE_RATE).astype(np.float32) * 0.1

        result = preprocessor.extract_mel_spectrogram(audio)
        reference = _naive_log_mel(audio, preprocessor._mel_filters)

        max_diff = float(np.max(np.abs(result - reference)))
        assert max_diff < 1e-4, (
            f"最大絕對差 {max_diff:.2e} 超過容差 1e-4"
        )

    @pytest.mark.skipif(not _has_torchaudio(), reason="需要 PyTorch + torchaudio")
    def test_precision_vs_pytorch(self, preprocessor):
        """選用：與 torchaudio.transforms.MelSpectrogram 比較（需要 torch）。"""
        torch = pytest.importorskip("torch")
        torchaudio = pytest.importorskip("torchaudio")

        rng = np.random.default_rng(42)
        audio_np = rng.standard_normal(SAMPLE_RATE).astype(np.float32) * 0.1
        result = preprocessor.extract_mel_spectrogram(audio_np)

        audio_t = torch.from_numpy(audio_np)
        transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH,
            n_mels=N_MELS, f_min=0.0, f_max=8000.0,
            norm="slaney", mel_scale="htk", power=2.0,
        )
        torch_mel = transform(audio_t).clamp(min=1e-10).log10()
        ref_pt = torch_mel.T.numpy()

        min_frames = min(result.shape[0], ref_pt.shape[0])
        max_diff = float(np.max(np.abs(result[:min_frames] - ref_pt[:min_frames])))
        assert max_diff < 1e-4, f"PyTorch 差異 = {max_diff:.2e}"


# ── 預先計算的 Mel 濾波器組 ───────────────────────────────────────────────────

class TestMelFilterbankLoading:
    """驗證：預先計算的 Mel 濾波器組需求。"""

    def test_filterbank_shape(self, preprocessor):
        """mel_filters 必須為 (128, 201) — (n_mels, n_fft // 2 + 1)。"""
        assert preprocessor._mel_filters.shape == (N_MELS, N_FFT // 2 + 1)

    def test_filterbank_dtype(self, preprocessor):
        """mel_filters 必須為 float32。"""
        assert preprocessor._mel_filters.dtype == np.float32

    def test_filterbank_nonnegative(self, preprocessor):
        """Mel 濾波器組所有值必須 >= 0。"""
        assert np.all(preprocessor._mel_filters >= 0.0)

    def test_filterbank_missing_raises_file_not_found(self, tmp_path):
        """mel_filters.npy 不存在時，應拋出含 'mel_filters.npy' 訊息的 FileNotFoundError。"""
        from airtype.core.processor_numpy import NumpyPreprocessor
        with pytest.raises(FileNotFoundError, match="mel_filters.npy"):
            NumpyPreprocessor(precomputed_dir=tmp_path)


# ── BPE 提示分詞 ──────────────────────────────────────────────────────────────

class TestBPETokenization:
    """驗證：BPE 提示分詞需求。"""

    def test_prompt_token_ids_is_list(self, preprocessor):
        """prompt_token_ids 屬性必須回傳 list。"""
        assert isinstance(preprocessor.prompt_token_ids, list)

    def test_prompt_tokens_are_integers(self, preprocessor):
        """prompt_token_ids 中所有元素必須為整數。"""
        assert all(isinstance(t, int) for t in preprocessor.prompt_token_ids)

    def test_prepend_prompt_tokens(self, preprocessor):
        """prepend_prompt_tokens 必須將提示 token ID 前置於輸入序列。"""
        input_ids = [100, 200, 300]
        result = preprocessor.prepend_prompt_tokens(input_ids)
        assert result == preprocessor.prompt_token_ids + input_ids

    def test_prepend_preserves_input_order(self, preprocessor):
        """prepend_prompt_tokens 後，原始輸入順序必須保留於尾端。"""
        input_ids = [1, 2, 3]
        result = preprocessor.prepend_prompt_tokens(input_ids)
        assert result[-len(input_ids):] == input_ids

    def test_prepend_returns_new_list(self, preprocessor):
        """prepend_prompt_tokens 必須回傳新 list，不得修改原始輸入。"""
        input_ids = [10, 20]
        original = list(input_ids)
        preprocessor.prepend_prompt_tokens(input_ids)
        assert input_ids == original


# ── 樸素參考實作（用於精度測試）─────────────────────────────────────────────

def _naive_log_mel(audio: np.ndarray, mel_filters: np.ndarray) -> np.ndarray:
    """樸素參考：與 NumpyPreprocessor 相同演算法，直接以明確迴圈撰寫。

    Args:
        audio: 1-D float32 ndarray，16kHz mono PCM
        mel_filters: (n_mels, n_fft//2+1) 預先計算的 Mel 濾波器組

    Returns:
        (n_frames, n_mels) float32 log-Mel 頻譜
    """
    n_fft = 400
    hop_length = 160

    # 週期性 Hanning 視窗（與實作一致）
    n = np.arange(n_fft, dtype=np.float32)
    window = (0.5 * (1.0 - np.cos(2.0 * np.pi * n / n_fft))).astype(np.float32)

    # 反射填充
    pad = n_fft // 2
    audio_padded = np.pad(audio.astype(np.float32), (pad, pad), mode="reflect")

    n_frames = (len(audio_padded) - n_fft) // hop_length + 1
    stft = np.zeros((n_fft // 2 + 1, n_frames), dtype=np.float32)
    for i in range(n_frames):
        start = i * hop_length
        frame = audio_padded[start: start + n_fft] * window
        spectrum = np.fft.rfft(frame, n=n_fft)
        stft[:, i] = np.abs(spectrum) ** 2

    mel_spec = mel_filters @ stft            # (n_mels, n_frames)
    log_mel = np.log10(np.maximum(mel_spec, 1e-10))
    return log_mel.T.astype(np.float32)     # (n_frames, n_mels)
