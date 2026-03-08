"""ASR 引擎抽象層單元測試。

涵蓋：
  - ASREngine Protocol 一致性（需求：ASR Engine Protocol）
  - ASRResult、PartialResult、HotWord、ASRSegment 資料模型
  - ASREngineRegistry 登錄、取得、切換（需求：Engine Registry、Runtime Engine Switching）
  - load_default_engine（需求：Load Default Engine from Configuration）
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Mock ASR 引擎（Task 3.1）
# ---------------------------------------------------------------------------


class MockASREngine:
    """實作 ASREngine Protocol 所有方法的 mock 引擎，供測試使用。"""

    def __init__(self) -> None:
        self.loaded = False
        self.unloaded = False
        self._hot_words: list = []
        self._context: str = ""

    def load_model(self, model_path: str, config: dict) -> None:
        self.loaded = True

    def recognize(self, audio: np.ndarray):
        from airtype.core.asr_engine import ASRResult

        return ASRResult(text="mock result", language="zh-TW", confidence=0.9)

    def recognize_stream(self, chunk: np.ndarray):
        from airtype.core.asr_engine import PartialResult

        return PartialResult(text="mock partial", is_final=False)

    def set_hot_words(self, words: list) -> None:
        self._hot_words = words

    def set_context(self, context_text: str) -> None:
        self._context = context_text

    def get_supported_languages(self) -> list[str]:
        return ["zh-TW", "en"]

    @property
    def supports_hot_words(self) -> bool:
        return True

    def unload(self) -> None:
        self.unloaded = True


class IncompleteEngine:
    """缺少 recognize 方法的不完整引擎，用於驗證 Protocol 拒絕不符合的類別。"""

    def load_model(self, model_path: str, config: dict) -> None:
        pass

    def recognize_stream(self, chunk: np.ndarray):
        pass

    def set_hot_words(self, words: list) -> None:
        pass

    def set_context(self, context_text: str) -> None:
        pass

    def get_supported_languages(self) -> list[str]:
        return []

    def unload(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 夾具
# ---------------------------------------------------------------------------


@pytest.fixture
def registry():
    from airtype.core.asr_engine import ASREngineRegistry

    return ASREngineRegistry()


# ---------------------------------------------------------------------------
# 3.1 Protocol 一致性測試
# ---------------------------------------------------------------------------


def test_mock_engine_conforms_to_protocol():
    """完整實作所有方法的 mock 引擎應符合 ASREngine Protocol。"""
    from airtype.core.asr_engine import ASREngine

    assert isinstance(MockASREngine(), ASREngine)


def test_incomplete_engine_does_not_conform_to_protocol():
    """缺少 recognize 方法的引擎不應符合 ASREngine Protocol。"""
    from airtype.core.asr_engine import ASREngine

    assert not isinstance(IncompleteEngine(), ASREngine)


# ---------------------------------------------------------------------------
# 3.2 ASREngineRegistry 登錄檔測試
# ---------------------------------------------------------------------------


def test_register_and_get_engine(registry):
    """登錄工廠後 get_engine 應回傳有效引擎實例。"""
    registry.register_engine("mock", MockASREngine)
    engine = registry.get_engine("mock")
    assert isinstance(engine, MockASREngine)


def test_get_engine_returns_new_instance_each_time(registry):
    """get_engine 每次呼叫應回傳不同的新實例。"""
    registry.register_engine("mock", MockASREngine)
    e1 = registry.get_engine("mock")
    e2 = registry.get_engine("mock")
    assert e1 is not e2


def test_get_unregistered_engine_raises_key_error(registry):
    """取得未登錄引擎 ID 應拋出 KeyError。"""
    with pytest.raises(KeyError, match="nonexistent"):
        registry.get_engine("nonexistent")


def test_set_active_engine(registry):
    """set_active_engine 後 active_engine 應為新引擎實例。"""
    registry.register_engine("mock", MockASREngine)
    registry.set_active_engine("mock")
    assert isinstance(registry.active_engine, MockASREngine)
    assert registry.active_engine_id == "mock"


def test_switch_active_engine_unloads_previous(registry):
    """切換引擎時應先呼叫前一個引擎的 unload()。"""
    registry.register_engine("engine-a", MockASREngine)
    registry.register_engine("engine-b", MockASREngine)
    registry.set_active_engine("engine-a")
    first_engine = registry.active_engine

    registry.set_active_engine("engine-b")

    assert first_engine.unloaded
    assert registry.active_engine_id == "engine-b"


def test_set_active_unregistered_engine_raises_and_preserves_current(registry):
    """切換至未登錄引擎應拋出 KeyError，且不卸載現有引擎。"""
    registry.register_engine("mock", MockASREngine)
    registry.set_active_engine("mock")
    current = registry.active_engine

    with pytest.raises(KeyError):
        registry.set_active_engine("nonexistent")

    assert not current.unloaded          # 未被卸載
    assert registry.active_engine_id == "mock"  # 仍為舊引擎


def test_registered_ids(registry):
    """registered_ids 應列出所有已登錄 ID。"""
    registry.register_engine("a", MockASREngine)
    registry.register_engine("b", MockASREngine)
    assert set(registry.registered_ids) == {"a", "b"}


def test_initial_active_engine_is_none(registry):
    """初始狀態下 active_engine 應為 None。"""
    assert registry.active_engine is None
    assert registry.active_engine_id is None


def test_load_default_engine_valid(registry):
    """設定指定有效引擎時 load_default_engine 應正確載入（直接匹配引擎 ID）。"""
    registry.register_engine("qwen3-asr-0.6b", MockASREngine)
    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-asr-0.6b"
    cfg.voice.asr_inference_backend = "auto"
    registry.load_default_engine(cfg)
    assert registry.active_engine_id == "qwen3-asr-0.6b"


def test_load_default_engine_unknown_logs_warning(registry):
    """設定指定未登錄引擎時應記錄警告並保持無作用中引擎。"""
    cfg = MagicMock()
    cfg.voice.asr_model = "nonexistent"
    cfg.voice.asr_inference_backend = "auto"
    with patch("airtype.core.asr_engine.logger") as mock_logger:
        registry.load_default_engine(cfg)
    mock_logger.warning.assert_called_once()
    assert registry.active_engine is None


# ---------------------------------------------------------------------------
# 4.x 模型名稱解析測試（fix-asr-engine-resolution）
# ---------------------------------------------------------------------------


def test_manifest_resolves_to_correct_engine(registry):
    """manifest 的 inference_engine 應決定使用哪個引擎。

    模型 qwen3-asr-0.6b 在 manifest 中的 inference_engine 是 chatllm-vulkan，
    經別名轉換後應解析為 qwen3-vulkan。即使 qwen3-openvino 也已登錄，
    仍應優先選擇 manifest 指定的引擎。
    """
    from airtype.core.asr_engine import ASREngineRegistry

    registry.register_engine("qwen3-openvino", MockASREngine)
    registry.register_engine("qwen3-vulkan", MockASREngine)
    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-asr-0.6b"
    cfg.voice.asr_inference_backend = "auto"
    # manifest 中 qwen3-asr-0.6b → chatllm-vulkan → 別名 qwen3-vulkan
    with patch.object(
        ASREngineRegistry, "_resolve_engine_from_manifest", return_value="qwen3-vulkan"
    ):
        registry.load_default_engine(cfg)
    assert registry.active_engine_id == "qwen3-vulkan"


def test_manifest_engine_not_registered_falls_to_family_map(registry):
    """manifest 指定的引擎未登錄時，應 fallback 到家族映射。

    Scenario: Model Name Resolves to Registered Engine via Auto Backend
    """
    from airtype.core.asr_engine import ASREngineRegistry

    registry.register_engine("qwen3-openvino", MockASREngine)
    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-asr-0.6b"
    cfg.voice.asr_inference_backend = "auto"
    # manifest 指定 qwen3-vulkan 但未登錄
    with patch.object(
        ASREngineRegistry, "_resolve_engine_from_manifest", return_value="qwen3-vulkan"
    ):
        registry.load_default_engine(cfg)
    # fallback 到 _MODEL_ENGINE_MAP，qwen3-openvino 排第一且已登錄
    assert registry.active_engine_id == "qwen3-openvino"


def test_model_name_resolves_via_specific_backend(registry):
    """模型名稱 + 特定 backend 應解析至含 backend 子字串的引擎。

    Scenario: Model Name Resolves via Specific Backend
    """
    from airtype.core.asr_engine import ASREngineRegistry

    registry.register_engine("qwen3-openvino", MockASREngine)
    registry.register_engine("qwen3-vulkan", MockASREngine)
    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-asr-0.6b"
    cfg.voice.asr_inference_backend = "openvino"
    # manifest 解析為 vulkan，但已登錄所以會在階段 2 選中。
    # 不過 backend=openvino 時使用者意圖明確，需 manifest 未登錄才到階段 3。
    # 這裡模擬 manifest 無結果的情境以測試家族映射。
    with patch.object(
        ASREngineRegistry, "_resolve_engine_from_manifest", return_value=None
    ):
        registry.load_default_engine(cfg)
    assert registry.active_engine_id == "qwen3-openvino"


def test_direct_engine_id_still_works(registry):
    """直接使用引擎 ID 作為 asr_model 應向下相容直接載入。

    Scenario: Direct Engine ID Still Works
    """
    registry.register_engine("qwen3-vulkan", MockASREngine)
    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-vulkan"
    cfg.voice.asr_inference_backend = "auto"
    registry.load_default_engine(cfg)
    assert registry.active_engine_id == "qwen3-vulkan"


def test_model_name_no_registered_backend(registry):
    """模型名稱但無已登錄後端應記錄 WARNING 且 active_engine 為 None。

    Scenario: Model Name With No Registered Backend
    """
    from airtype.core.asr_engine import ASREngineRegistry

    cfg = MagicMock()
    cfg.voice.asr_model = "qwen3-asr-0.6b"
    cfg.voice.asr_inference_backend = "auto"
    with patch.object(
        ASREngineRegistry, "_resolve_engine_from_manifest", return_value=None
    ), patch("airtype.core.asr_engine.logger") as mock_logger:
        registry.load_default_engine(cfg)
    mock_logger.warning.assert_called_once()
    assert registry.active_engine is None


def test_unknown_model_name_logs_warning(registry):
    """未知模型名稱（非引擎 ID 也不在映射表中）應記錄 WARNING。

    Scenario: Configuration Specifies an Unknown Model
    """
    from airtype.core.asr_engine import ASREngineRegistry

    cfg = MagicMock()
    cfg.voice.asr_model = "nonexistent-model"
    cfg.voice.asr_inference_backend = "auto"
    with patch.object(
        ASREngineRegistry, "_resolve_engine_from_manifest", return_value=None
    ), patch("airtype.core.asr_engine.logger") as mock_logger:
        registry.load_default_engine(cfg)
    mock_logger.warning.assert_called_once()
    assert registry.active_engine is None


def test_resolve_engine_from_manifest_with_alias():
    """_resolve_engine_from_manifest 應正確處理別名映射。"""
    import json
    from unittest.mock import mock_open
    from airtype.core.asr_engine import ASREngineRegistry

    manifest_data = json.dumps({
        "models": [
            {"id": "qwen3-asr-0.6b", "inference_engine": "chatllm-vulkan"},
            {"id": "qwen3-asr-0.6b-openvino", "inference_engine": "qwen3-openvino"},
        ]
    })
    with patch("airtype.core.asr_engine._MANIFEST_PATH") as mock_path:
        mock_path.open = mock_open(read_data=manifest_data)
        # chatllm-vulkan 應別名為 qwen3-vulkan
        assert ASREngineRegistry._resolve_engine_from_manifest("qwen3-asr-0.6b") == "qwen3-vulkan"
        # qwen3-openvino 無需別名
        assert ASREngineRegistry._resolve_engine_from_manifest("qwen3-asr-0.6b-openvino") == "qwen3-openvino"
        # 不存在的模型
        assert ASREngineRegistry._resolve_engine_from_manifest("nonexistent") is None


# ---------------------------------------------------------------------------
# 3.3 資料模型測試
# ---------------------------------------------------------------------------


def test_asr_result_required_fields():
    """ASRResult 應正確儲存 text、language、confidence，segments 預設為空清單。"""
    from airtype.core.asr_engine import ASRResult

    result = ASRResult(text="你好世界", language="zh-TW", confidence=0.95)
    assert result.text == "你好世界"
    assert result.language == "zh-TW"
    assert result.confidence == 0.95
    assert result.segments == []


def test_asr_result_with_segments():
    """ASRResult 應能包含 ASRSegment 時間段列表。"""
    from airtype.core.asr_engine import ASRResult, ASRSegment

    seg = ASRSegment(text="你好", start=0.0, end=0.5)
    result = ASRResult(text="你好", language="zh-TW", confidence=0.9, segments=[seg])
    assert len(result.segments) == 1
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 0.5


def test_partial_result_not_final():
    """串流部分結果的 is_final 應為 False。"""
    from airtype.core.asr_engine import PartialResult

    r = PartialResult(text="你好", is_final=False)
    assert r.text == "你好"
    assert not r.is_final


def test_partial_result_final():
    """串流最終結果的 is_final 應為 True。"""
    from airtype.core.asr_engine import PartialResult

    r = PartialResult(text="你好世界", is_final=True)
    assert r.is_final


def test_hot_word_dataclass():
    """HotWord 應正確儲存 word 與 weight。"""
    from airtype.core.asr_engine import HotWord

    hw = HotWord(word="鼎新 Workflow", weight=8)
    assert hw.word == "鼎新 Workflow"
    assert hw.weight == 8


def test_asr_segment_dataclass():
    """ASRSegment 應正確儲存文字與起止時間。"""
    from airtype.core.asr_engine import ASRSegment

    seg = ASRSegment(text="hello world", start=1.0, end=2.5)
    assert seg.text == "hello world"
    assert seg.start == 1.0
    assert seg.end == 2.5


def test_confidence_range():
    """ASRResult.confidence 應允許 0.0–1.0 範圍。"""
    from airtype.core.asr_engine import ASRResult

    r0 = ASRResult(text="", language="en", confidence=0.0)
    r1 = ASRResult(text="", language="en", confidence=1.0)
    assert r0.confidence == 0.0
    assert r1.confidence == 1.0


# ---------------------------------------------------------------------------
# 4.1–4.3 Hot Words Engine Sync 測試
# ---------------------------------------------------------------------------


class MockASREngineWithHotWords(MockASREngine):
    """支援 supports_hot_words 的 mock 引擎。"""

    @property
    def supports_hot_words(self) -> bool:
        return True


class MockASREngineNoHotWords(MockASREngine):
    """不支援 supports_hot_words 的 mock 引擎。"""

    @property
    def supports_hot_words(self) -> bool:
        return False


def test_supports_hot_words_in_protocol():
    """supports_hot_words 應為 ASREngine Protocol 屬性。"""
    from airtype.core.asr_engine import ASREngine

    engine = MockASREngineWithHotWords()
    assert isinstance(engine, ASREngine)
    assert engine.supports_hot_words is True


def test_sherpa_engine_supports_hot_words():
    """SherpaOnnxEngine.supports_hot_words 應回傳 True。"""
    from airtype.core.asr_sherpa import SherpaOnnxEngine

    engine = SherpaOnnxEngine(model_type="sensevoice")
    assert engine.supports_hot_words is True


def test_on_engine_changed_callback_invoked(registry):
    """set_active_engine() 完成後應呼叫 on_engine_changed callback。"""
    callback_calls = []
    registry.on_engine_changed = lambda eid: callback_calls.append(eid)
    registry.register_engine("engine-a", MockASREngineWithHotWords)
    registry.register_engine("engine-b", MockASREngineNoHotWords)

    registry.set_active_engine("engine-a")
    assert callback_calls == ["engine-a"]

    registry.set_active_engine("engine-b")
    assert callback_calls == ["engine-a", "engine-b"]


def test_on_engine_changed_none_no_error(registry):
    """on_engine_changed 為 None 時切換引擎不應出錯。"""
    registry.register_engine("mock", MockASREngineWithHotWords)
    assert registry.on_engine_changed is None
    registry.set_active_engine("mock")


def test_qwen_openvino_no_hot_words():
    """QwenOpenVinoEngine.supports_hot_words 應回傳 False。"""
    from airtype.core.asr_qwen_openvino import QwenOpenVinoEngine

    assert QwenOpenVinoEngine().supports_hot_words is False


def test_qwen_pytorch_no_hot_words():
    """QwenPyTorchEngine.supports_hot_words 應回傳 False。"""
    from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

    assert QwenPyTorchEngine().supports_hot_words is False


def test_qwen_vulkan_no_hot_words():
    """QwenVulkanEngine.supports_hot_words 應回傳 False。"""
    from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

    assert QwenVulkanEngine().supports_hot_words is False


def test_breeze_no_hot_words():
    """BreezeAsrEngine.supports_hot_words 應回傳 False。"""
    from airtype.core.asr_breeze import BreezeAsrEngine

    assert BreezeAsrEngine().supports_hot_words is False
