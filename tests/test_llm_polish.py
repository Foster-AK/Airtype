"""LLM 潤飾引擎測試。

涵蓋：
- 潤飾引擎單元測試（mock llama.cpp、測試 3 種模式、測試逾時）
- API 整合單元測試（mock httpx、測試錯誤回退）
- PolishEngine 整合行為（啟用/停用、本機/API 路由）
"""

from __future__ import annotations

import asyncio
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from airtype.config import AirtypeConfig


# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------

def _make_config(
    enabled: bool = True,
    source: str = "local",
    mode: str = "light",
    local_model: str = "/fake/model.gguf",
    custom_prompt: str | None = None,
    api_provider: str | None = "openai",
    api_key: str | None = "sk-test",
    api_endpoint: str | None = None,
) -> AirtypeConfig:
    """建立測試用 AirtypeConfig。"""
    config = AirtypeConfig()
    config.llm.enabled = enabled
    config.llm.source = source
    config.llm.mode = mode
    config.llm.local_model = local_model
    config.llm.custom_prompt = custom_prompt
    config.llm.api_provider = api_provider
    config.llm.api_endpoint = api_endpoint
    return config


# ---------------------------------------------------------------------------
# LocalLLMEngine 測試
# ---------------------------------------------------------------------------

class TestLocalLLMEngine(unittest.TestCase):
    """LocalLLMEngine 單元測試（mock llama_cpp）。"""

    def _make_engine(self, model_path: str = "/fake/model.gguf"):
        from airtype.core.llm_polish import LocalLLMEngine
        return LocalLLMEngine(model_path)

    def test_polish_returns_result(self):
        """成功推理時應回傳模型輸出。"""
        engine = self._make_engine()
        # 直接 mock _infer 方法測試 polish（不需要安裝 llama_cpp）
        # 新簽名：_infer(system_prompt, text, max_tokens) -> str
        engine._infer = MagicMock(return_value="你好，世界。")
        # 同時 mock _apply_thinking_token 以避免讀取 manifest
        engine._apply_thinking_token = MagicMock(side_effect=lambda t: t)
        result = engine.polish("你好世界", "系統提示詞")
        self.assertEqual(result, "你好，世界。")

    def test_polish_timeout_raises_polish_error(self):
        """推理超時應拋出 PolishError。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_engine()
        engine._apply_thinking_token = MagicMock(side_effect=lambda t: t)

        def slow_infer(system_prompt, text, max_tokens):
            import time
            time.sleep(10)
            return "never"

        engine._infer = slow_infer

        with self.assertRaises(PolishError):
            import airtype.core.llm_polish as module
            original = module._LOCAL_TIMEOUT_SECONDS
            module._LOCAL_TIMEOUT_SECONDS = 0.1
            try:
                engine.polish("測試文字", "系統提示詞")
            finally:
                module._LOCAL_TIMEOUT_SECONDS = original

    def test_polish_inference_error_raises_polish_error(self):
        """推理拋出例外時應包裝為 PolishError。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_engine()
        engine._apply_thinking_token = MagicMock(side_effect=lambda t: t)
        engine._infer = MagicMock(side_effect=RuntimeError("GGUF load fail"))

        with self.assertRaises(PolishError):
            engine.polish("測試", "系統提示詞")

    def test_polish_empty_choices_raises_polish_error(self):
        """模型回傳空 choices 時應拋出 PolishError。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_engine()
        engine._apply_thinking_token = MagicMock(side_effect=lambda t: t)
        engine._infer = MagicMock(side_effect=Exception("no choices"))

        with self.assertRaises(PolishError):
            engine.polish("文字", "系統提示詞")


# ---------------------------------------------------------------------------
# 提示詞模板測試
# ---------------------------------------------------------------------------

class TestPromptTemplates(unittest.TestCase):
    """PolishEngine 系統提示詞測試（Qwen2.5 few-shot 格式）。"""

    def test_light_mode_system_prompt(self):
        """輕度模式應使用標點修正系統提示詞。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        prompt = _SYSTEM_PROMPTS["light"]
        self.assertIn("標點", prompt)
        self.assertIn("直接輸出結果，不要加任何說明。", prompt)

    def test_medium_mode_system_prompt(self):
        """中度模式應包含流暢度關鍵字。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        prompt = _SYSTEM_PROMPTS["medium"]
        self.assertIn("流暢", prompt)

    def test_full_mode_system_prompt(self):
        """完整模式應包含文法關鍵字。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        prompt = _SYSTEM_PROMPTS["full"]
        self.assertIn("文法", prompt)

    def test_all_modes_have_system_prompts(self):
        """三種模式均應有對應的系統提示詞。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        for mode in ("light", "medium", "full"):
            self.assertIn(mode, _SYSTEM_PROMPTS)

    def test_custom_prompt_override(self):
        """設定自訂提示詞時應覆寫內建系統提示詞。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(custom_prompt="自訂系統提示詞")
        engine = PolishEngine(config)
        self.assertEqual(engine._get_system_prompt(), "自訂系統提示詞")

    def test_mode_routing(self):
        """未設定自訂提示詞時，各模式應使用對應的系統提示詞。"""
        from airtype.core.llm_polish import PolishEngine, _SYSTEM_PROMPTS
        for mode in ("light", "medium", "full"):
            config = _make_config(mode=mode)
            engine = PolishEngine(config)
            self.assertEqual(engine._get_system_prompt(), _SYSTEM_PROMPTS[mode])


# ---------------------------------------------------------------------------
# PolishEngine 整合測試（本機路徑）
# ---------------------------------------------------------------------------

class TestPolishEngineLocal(unittest.TestCase):
    """PolishEngine 本機 LLM 路徑整合測試。"""

    def test_disabled_returns_original(self):
        """LLM 停用時應直接回傳原始文字。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(enabled=False)
        engine = PolishEngine(config)
        result = engine.polish("原始文字")
        self.assertEqual(result, "原始文字")

    def test_empty_text_returns_empty(self):
        """空白文字應直接回傳不呼叫 LLM。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config()
        engine = PolishEngine(config)
        result = engine.polish("   ")
        self.assertEqual(result, "   ")

    def test_local_engine_success(self):
        """本機引擎成功時應回傳潤飾結果。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(source="local")
        engine = PolishEngine(config)

        mock_local = MagicMock()
        mock_local.polish.return_value = "你好，世界。"
        engine._local_engine = mock_local

        result = engine.polish("你好世界")
        self.assertEqual(result, "你好，世界。")

    def test_local_engine_fallback_on_error(self):
        """本機引擎失敗時應回退至原始文字。"""
        from airtype.core.llm_polish import PolishEngine, PolishError
        config = _make_config(source="local")
        engine = PolishEngine(config)

        mock_local = MagicMock()
        mock_local.polish.side_effect = PolishError("模型推理失敗")
        engine._local_engine = mock_local

        result = engine.polish("原始文字")
        self.assertEqual(result, "原始文字")

    def test_unexpected_exception_fallback(self):
        """未預期例外時應回退至原始文字而不崩潰。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(source="local")
        engine = PolishEngine(config)

        mock_local = MagicMock()
        mock_local.polish.side_effect = RuntimeError("未知錯誤")
        engine._local_engine = mock_local

        result = engine.polish("原始文字")
        self.assertEqual(result, "原始文字")

    def test_reset_clears_engines(self):
        """reset() 應清除快取的引擎實例。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config()
        engine = PolishEngine(config)
        engine._local_engine = MagicMock()
        engine._api_engine = MagicMock()

        engine.reset()

        self.assertIsNone(engine._local_engine)
        self.assertIsNone(engine._api_engine)


# ---------------------------------------------------------------------------
# APILLMEngine 測試（mock httpx）
# ---------------------------------------------------------------------------

class TestAPILLMEngine(unittest.TestCase):
    """APILLMEngine 單元測試（mock httpx.AsyncClient）。"""

    def _make_api_engine(self, provider="openai", api_key="sk-test", endpoint=None):
        from airtype.core.llm_polish import APILLMEngine
        return APILLMEngine(provider=provider, api_key=api_key, endpoint=endpoint)

    def _mock_httpx_success(self, polished_text: str = "潤飾後文字"):
        """建立回傳成功回應的 mock httpx 模組。"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": polished_text}}
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client
        return mock_httpx

    def test_api_polish_success(self):
        """API 呼叫成功時應回傳潤飾結果。"""
        engine = self._make_api_engine()
        mock_httpx = self._mock_httpx_success("標點修正後的文字。")

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = engine.polish("測試文字", "系統提示詞")

        self.assertEqual(result, "標點修正後的文字。")

    def test_api_network_error_raises_polish_error(self):
        """網路錯誤應包裝為 PolishError。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_api_engine()

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            with self.assertRaises(PolishError):
                engine.polish("文字", "提示詞")

    def test_api_http_error_raises_polish_error(self):
        """HTTP 4xx/5xx 錯誤應包裝為 PolishError。"""
        from airtype.core.llm_polish import PolishError
        import httpx as real_httpx

        engine = self._make_api_engine()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            with self.assertRaises(PolishError):
                engine.polish("文字", "提示詞")

    def test_api_empty_choices_raises_polish_error(self):
        """API 回傳空 choices 應拋出 PolishError。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_api_engine()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": []}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            with self.assertRaises(PolishError):
                engine.polish("文字", "提示詞")

    def test_httpx_not_installed_raises_polish_error(self):
        """httpx 未安裝時應拋出 PolishError 並提示安裝資訊。"""
        from airtype.core.llm_polish import PolishError

        engine = self._make_api_engine()

        with patch.dict("sys.modules", {"httpx": None}):
            with self.assertRaises((PolishError, ImportError)):
                engine.polish("文字", "提示詞")

    def test_custom_endpoint_used(self):
        """自訂端點應正確設定 base_url。"""
        from airtype.core.llm_polish import APILLMEngine
        engine = APILLMEngine(
            provider="custom",
            api_key="key",
            endpoint="http://my-server:8080/v1",
        )
        self.assertEqual(engine._base_url, "http://my-server:8080/v1")

    def test_default_endpoint_by_provider(self):
        """各提供者應有對應的預設端點。"""
        from airtype.core.llm_polish import APILLMEngine
        from airtype.core.llm_polish import APILLMEngine

        openai_engine = APILLMEngine(provider="openai", api_key="k")
        self.assertIn("openai.com", openai_engine._base_url)

        ollama_engine = APILLMEngine(provider="ollama", api_key="k")
        self.assertIn("localhost", ollama_engine._base_url)


# ---------------------------------------------------------------------------
# PolishEngine API 路徑整合測試
# ---------------------------------------------------------------------------

class TestPolishEngineAPI(unittest.TestCase):
    """PolishEngine API 路徑整合測試。"""

    def test_api_success_returns_polished(self):
        """API 成功時應回傳潤飾結果。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(source="api")
        engine = PolishEngine(config)

        mock_api = MagicMock()
        mock_api.polish.return_value = "API 潤飾結果。"
        engine._api_engine = mock_api

        result = engine.polish("原始文字")
        self.assertEqual(result, "API 潤飾結果。")

    def test_api_failure_fallback_to_original(self):
        """API 失敗時應回退至原始文字。"""
        from airtype.core.llm_polish import PolishEngine, PolishError
        config = _make_config(source="api")
        engine = PolishEngine(config)

        mock_api = MagicMock()
        mock_api.polish.side_effect = PolishError("API 呼叫失敗")
        engine._api_engine = mock_api

        result = engine.polish("原始文字")
        self.assertEqual(result, "原始文字")


# ---------------------------------------------------------------------------
# Thinking Mode Token Suppression 測試（Task 13 + 14）
# ---------------------------------------------------------------------------

class TestThinkingModeSuppression(unittest.TestCase):
    """Thinking Mode Token Suppression 單元測試。"""

    def _make_engine(self, model_id: str = "qwen3-instruct"):
        from airtype.core.llm_polish import LocalLLMEngine
        return LocalLLMEngine(model_path="/fake/model.gguf", model_id=model_id)

    def test_thinking_token_prepended_when_enabled(self):
        """has_thinking_mode=True 時，thinking_disable_token 應被前綴至 user 文字。"""
        engine = self._make_engine()
        manifest_entry = {
            "has_thinking_mode": True,
            "thinking_disable_token": "/no_think",
        }
        captured_texts: list[str] = []

        def fake_infer(system_prompt, text, max_tokens):
            captured_texts.append(text)
            return "結果。"

        with patch.object(engine, "_read_manifest", return_value=manifest_entry):
            engine._infer = fake_infer
            engine.polish("測試文字", "系統提示詞")

        self.assertTrue(
            captured_texts[0].startswith("/no_think"),
            f"token 應前綴至文字，實際：{captured_texts[0]!r}",
        )

    def test_no_token_when_thinking_mode_false(self):
        """has_thinking_mode=False 時，user 文字不應有 token 前綴。"""
        engine = self._make_engine()
        manifest_entry = {"has_thinking_mode": False, "thinking_disable_token": None}
        captured_texts: list[str] = []

        def fake_infer(system_prompt, text, max_tokens):
            captured_texts.append(text)
            return "結果。"

        with patch.object(engine, "_read_manifest", return_value=manifest_entry):
            engine._infer = fake_infer
            engine.polish("測試文字", "系統提示詞")

        self.assertFalse(
            captured_texts[0].startswith("/no_think"),
            "thinking_mode=False 時不應前綴 token",
        )

    def test_manifest_entry_not_found_no_exception(self):
        """manifest 條目不存在時，LocalLLMEngine 應正常運作不拋出例外。"""
        engine = self._make_engine(model_id="nonexistent-model")
        with patch.object(engine, "_read_manifest", return_value=None):
            engine._infer = MagicMock(return_value="正常結果。")
            try:
                result = engine.polish("測試文字", "系統提示詞")
                self.assertEqual(result, "正常結果。")
            except Exception as exc:
                self.fail(f"manifest 條目不存在時不應拋出例外：{exc}")

    def test_thinking_token_empty_string_no_prepend(self):
        """thinking_disable_token 為空字串時，不應前綴任何 token。"""
        engine = self._make_engine()
        manifest_entry = {"has_thinking_mode": True, "thinking_disable_token": ""}
        captured_texts: list[str] = []

        def fake_infer(system_prompt, text, max_tokens):
            captured_texts.append(text)
            return "結果。"

        with patch.object(engine, "_read_manifest", return_value=manifest_entry):
            engine._infer = fake_infer
            engine.polish("純文字", "提示詞")

        self.assertEqual(captured_texts[0], "純文字")


# ---------------------------------------------------------------------------
# Qwen2.5 精化測試（Task 19）
# ---------------------------------------------------------------------------

class TestModelSizeAutoDowngrade(unittest.TestCase):
    """Model Size Auto-Downgrade 單元測試。"""

    def _make_engine(self, model_size_b: float):
        from airtype.core.llm_polish import LocalLLMEngine
        return LocalLLMEngine(model_path="/fake/model.gguf", model_size_b=model_size_b)

    def test_05b_full_downgrades_to_light(self):
        """0.5B 模型請求 FULL → 強制降為 LIGHT。"""
        engine = self._make_engine(0.5)
        self.assertEqual(engine._resolve_mode("full"), "light")

    def test_15b_full_downgrades_to_medium(self):
        """1.5B 模型請求 FULL → 降為 MEDIUM。"""
        engine = self._make_engine(1.5)
        self.assertEqual(engine._resolve_mode("full"), "medium")

    def test_3b_full_stays_full(self):
        """3B 模型請求 FULL → 維持 FULL。"""
        engine = self._make_engine(3.0)
        self.assertEqual(engine._resolve_mode("full"), "full")

    def test_15b_medium_stays_medium(self):
        """1.5B 模型請求 MEDIUM → 維持 MEDIUM。"""
        engine = self._make_engine(1.5)
        self.assertEqual(engine._resolve_mode("medium"), "medium")

    def test_05b_medium_downgrades_to_light(self):
        """0.5B 模型請求 MEDIUM → 降為 LIGHT。"""
        engine = self._make_engine(0.5)
        self.assertEqual(engine._resolve_mode("medium"), "light")

    def test_any_size_light_stays_light(self):
        """任意大小模型請求 LIGHT → 維持 LIGHT。"""
        for size in (0.5, 1.5, 3.0, 7.0):
            engine = self._make_engine(size)
            self.assertEqual(engine._resolve_mode("light"), "light",
                             f"size={size} 時 LIGHT 應維持 LIGHT")


class TestPreClean(unittest.TestCase):
    """ASR Output Pre-cleaning 單元測試。"""

    def _pre_clean(self, text: str) -> str:
        from airtype.core.llm_polish import LocalLLMEngine
        return LocalLLMEngine._pre_clean(text)

    def test_collapses_repeated_filler_chars(self):
        """連續語氣詞應被壓縮。"""
        self.assertEqual(self._pre_clean("嗯嗯嗯啊"), "嗯啊")

    def test_collapses_repeated_filler_phrases(self):
        """連續贅詞應被壓縮。"""
        self.assertEqual(self._pre_clean("然後然後然後"), "然後")
        self.assertEqual(self._pre_clean("就是就是"), "就是")

    def test_removes_extra_whitespace(self):
        """多餘空白應被移除。"""
        self.assertEqual(self._pre_clean("你 好 世 界"), "你好世界")

    def test_normal_text_unchanged(self):
        """一般文字應保持不變。"""
        self.assertEqual(self._pre_clean("今天開會討論新系統"), "今天開會討論新系統")


class TestPostClean(unittest.TestCase):
    """LLM Output Post-cleaning 單元測試。"""

    def _post_clean(self, text: str) -> str:
        from airtype.core.llm_polish import LocalLLMEngine
        return LocalLLMEngine._post_clean(text)

    def test_removes_hao_de_prefix(self):
        """移除「好的，」前綴。"""
        self.assertEqual(
            self._post_clean("好的，今天開會，主管說要導入新系統。"),
            "今天開會，主管說要導入新系統。",
        )

    def test_removes_yi_xia_shi_prefix(self):
        """移除「以下是...：」前綴。"""
        result = self._post_clean("以下是修正後的文字：今天開會，主管說要導入新系統。")
        self.assertNotIn("以下是", result)
        self.assertIn("今天開會", result)

    def test_removes_markdown_code_block(self):
        """移除 markdown 程式碼區塊包裹。"""
        result = self._post_clean("```\n今天開會，主管說要導入新系統。\n```")
        self.assertEqual(result, "今天開會，主管說要導入新系統。")

    def test_removes_surrounding_fullwidth_quotes(self):
        """移除首尾全形引號。"""
        result = self._post_clean("「今天開會，主管說要導入新系統。」")
        self.assertEqual(result, "今天開會，主管說要導入新系統。")

    def test_removes_surrounding_halfwidth_quotes(self):
        """移除首尾半形引號。"""
        result = self._post_clean('"今天開會，主管說要導入新系統。"')
        self.assertEqual(result, "今天開會，主管說要導入新系統。")

    def test_normal_text_unchanged(self):
        """無前綴廢話的正常文字應保持不變。"""
        text = "今天開會，主管說要導入新系統，大家覺得太趕了。"
        self.assertEqual(self._post_clean(text), text)


class TestQwen25Prompts(unittest.TestCase):
    """Qwen2.5 Few-shot System Prompts 測試。"""

    def test_all_modes_have_system_prompts(self):
        """三種模式均應有對應的 system prompt。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        for mode in ("light", "medium", "full"):
            self.assertIn(mode, _SYSTEM_PROMPTS, f"模式 {mode} 應有 system prompt")

    def test_light_prompt_contains_few_shot_example(self):
        """LIGHT 模式 prompt 應包含 few-shot 範例（輸入→輸出格式）。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        prompt = _SYSTEM_PROMPTS["light"]
        self.assertIn("輸入：", prompt)
        self.assertIn("輸出：", prompt)

    def test_light_prompt_ends_with_no_explanation(self):
        """LIGHT 模式 prompt 末尾應包含「直接輸出結果，不要加任何說明。」"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        self.assertIn("直接輸出結果，不要加任何說明。", _SYSTEM_PROMPTS["light"])

    def test_medium_prompt_mentions_fluency(self):
        """MEDIUM 模式 prompt 應提及流暢度處理。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        self.assertIn("流暢", _SYSTEM_PROMPTS["medium"])

    def test_full_prompt_mentions_grammar(self):
        """FULL 模式 prompt 應提及文法修正。"""
        from airtype.core.llm_polish import _SYSTEM_PROMPTS
        self.assertIn("文法", _SYSTEM_PROMPTS["full"])

    def test_custom_prompt_overrides_system_prompt(self):
        """設定 custom_prompt 時，應取代內建 system prompt。"""
        from airtype.core.llm_polish import PolishEngine
        config = _make_config(custom_prompt="自訂系統提示詞")
        engine = PolishEngine(config)
        system_prompt = engine._get_system_prompt()
        self.assertEqual(system_prompt, "自訂系統提示詞")

    def test_no_custom_prompt_uses_mode_system_prompt(self):
        """未設定 custom_prompt 時，應使用對應模式的 _SYSTEM_PROMPTS。"""
        from airtype.core.llm_polish import PolishEngine, _SYSTEM_PROMPTS
        for mode in ("light", "medium", "full"):
            config = _make_config(mode=mode)
            engine = PolishEngine(config)
            self.assertEqual(engine._get_system_prompt(), _SYSTEM_PROMPTS[mode])


# ---------------------------------------------------------------------------
# SettingsLlmPage 硬體警示 UI 測試（W2）
# ---------------------------------------------------------------------------

class TestHardwareWarningUI(unittest.TestCase):
    """SettingsLlmPage 硬體警示標籤顯示邏輯測試。"""

    def _make_page(self, warning_value):
        """建立 SettingsLlmPage 並 mock HardwareDetector.recommend_llm()。"""
        from airtype.utils.hardware_detect import LlmRecommendation

        mock_recommendation = LlmRecommendation(warning=warning_value)
        mock_detector_instance = MagicMock()
        mock_detector_instance.recommend_llm.return_value = mock_recommendation

        mock_qt = MagicMock()
        mock_widget = MagicMock()
        mock_qt.QWidget = MagicMock(return_value=mock_widget)

        with patch(
            "airtype.utils.hardware_detect.HardwareDetector",
            return_value=mock_detector_instance,
        ):
            from airtype.ui.settings_llm import SettingsLlmPage
            page = SettingsLlmPage.__new__(SettingsLlmPage)
            page._config = _make_config()
            page._schedule_save = None
            page._inserted_labels: list = []

            # mock _build_ui 不建立真實 Qt widgets
            page._local_group = MagicMock()
            mock_layout = MagicMock()
            mock_layout.indexOf.return_value = 0
            page.layout = MagicMock(return_value=mock_layout)

            def fake_insert(idx, widget):
                page._inserted_labels.append(widget)

            mock_layout.insertWidget.side_effect = fake_insert

            mock_qlabel = MagicMock()
            with patch("airtype.ui.settings_llm.QLabel", return_value=mock_qlabel), \
                 patch(
                    "airtype.utils.hardware_detect.HardwareDetector",
                    return_value=mock_detector_instance,
                ):
                page._check_hardware_warning()

        return page

    def test_no_warning_label_for_gpu_hardware(self):
        """GPU 硬體（warning=None）時，不應插入警示標籤。"""
        page = self._make_page(warning_value=None)
        self.assertEqual(
            len(page._inserted_labels),
            0,
            "GPU 環境下不應顯示任何硬體警示標籤",
        )

    def test_warning_label_shown_for_cpu_only(self):
        """CPU-only 硬體（warning='approaching_timeout_cpu'）時，應插入警示標籤。"""
        page = self._make_page(warning_value="approaching_timeout_cpu")
        self.assertEqual(
            len(page._inserted_labels),
            1,
            "CPU-only 環境下應插入一個硬體警示標籤",
        )


# ---------------------------------------------------------------------------
# 5.x 模型 ID → 檔案路徑解析測試（fix-asr-engine-resolution）
# ---------------------------------------------------------------------------


class TestModelPathResolution(unittest.TestCase):
    """PolishEngine._resolve_model_path 單元測試。"""

    def test_model_id_resolves_via_manifest(self):
        """模型 ID 應透過 manifest 解析為 ~/.airtype/models/{filename}。

        Scenario: Loading a local model by model ID
        """
        from pathlib import Path
        from airtype.core.llm_polish import PolishEngine

        with patch("airtype.core.llm_polish.Path.exists", return_value=False), \
             patch("airtype.core.llm_polish._MANIFEST_PATH") as mock_manifest:
            mock_manifest.open = unittest.mock.mock_open(read_data='{"models": [{"id": "qwen2.5-1.5b-instruct-q4_k_m", "filename": "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"}]}')
            result = PolishEngine._resolve_model_path("qwen2.5-1.5b-instruct-q4_k_m")

        expected = str(Path.home() / ".airtype" / "models" / "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf")
        self.assertEqual(result, expected)

    def test_direct_file_path_used_directly(self):
        """已存在的檔案路徑應直接使用，不查詢 manifest。

        Scenario: Loading a local model by direct file path
        """
        from airtype.core.llm_polish import PolishEngine

        with patch("airtype.core.llm_polish.Path.exists", return_value=True):
            result = PolishEngine._resolve_model_path("/path/to/model.gguf")

        self.assertEqual(result, "/path/to/model.gguf")

    def test_model_id_not_in_manifest_raises_polish_error(self):
        """manifest 中找不到模型 ID 應拋出 PolishError。

        Scenario: Model ID not found in manifest
        """
        from airtype.core.llm_polish import PolishEngine, PolishError

        with patch("airtype.core.llm_polish.Path.exists", return_value=False), \
             patch("airtype.core.llm_polish._MANIFEST_PATH") as mock_manifest:
            mock_manifest.open = unittest.mock.mock_open(read_data='{"models": [{"id": "other-model", "filename": "other.gguf"}]}')
            with self.assertRaises(PolishError) as ctx:
                PolishEngine._resolve_model_path("nonexistent-model")
            self.assertIn("nonexistent-model", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
