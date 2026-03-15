"""LLM 文字潤飾引擎。

支援兩種後端：
- 本機：llama-cpp-python（GGUF 模型，4096 context，3 秒逾時）
  - 使用 create_chat_completion（Qwen2.5 chat 格式，無需手動組裝 ChatML）
  - 自動根據 model_size_b 降級潤飾模式
  - ASR 前處理（pre_clean）與 LLM 輸出後處理（post_clean）
  - Thinking mode 抑制（從 models/manifest.json 讀取 has_thinking_mode）
- API：OpenAI 相容端點（httpx）

三種潤飾模式：
- light（輕度）：僅修正標點符號
- medium（中度）：標點 + 流暢度
- full（完整）：標點 + 流暢度 + 文法

失敗時一律回退至原始文字。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

# ── 系統提示詞（Qwen2.5 few-shot 版） ────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "light": (
        "你是標點符號插入工具。針對輸入的繁體中文文本，僅插入標點符號，不得修改任何文字。\n"
        "\n"
        "標點規範：使用，、。！？；：「」『』（）——……，禁止使用半形標點。\n"
        "句末用「。」「？」「！」，子句間用「，」，列舉用「、」，引述用「」，嵌套引述用『』。\n"
        "\n"
        "範例：\n"
        "輸入：今天開會主管說要導入新系統大家覺得太趕了\n"
        "輸出：今天開會，主管說要導入新系統，大家覺得太趕了。\n"
        "\n"
        "直接輸出結果，不要加任何說明。"
    ),
    "medium": (
        "你是繁體中文語句流暢化工具。針對語音轉文字的文本，執行以下處理：\n"
        "(1) 插入台灣繁體中文標點（，、。！？；：「」『』）\n"
        "(2) 刪除口語贅詞（然後、就是、那個、嗯、啊、對對對）\n"
        "(3) 修正語音辨識常見錯字（在/再、的/得/地、做/作）\n"
        "(4) 微調語序使句子通順\n"
        "(5) 根據上下文調整用詞\n"
        "\n"
        "禁止：改變原意、增加內容、把口語改書面語、使用半形標點。\n"
        "\n"
        "範例：\n"
        "輸入：然後我就覺得就是那個新系統啊其實還蠻不錯的就是大家可能還不太習慣然後但是用久了應該就好了\n"
        "輸出：我覺得那個新系統其實還蠻不錯的，大家可能還不太習慣，但是用久了應該就好了。\n"
        "\n"
        "直接輸出結果，不要加任何說明。"
    ),
    "full": (
        "你是繁體中文專業文字編輯。針對語音轉文字的文本，執行完整編輯：\n"
        "(1) 插入台灣繁體中文標點（，、。！？；：「」『』）\n"
        "(2) 刪除贅詞與重複用語\n"
        "(3) 修正錯字與文法（主詞動詞搭配、的得地、在再做作、不完整句子）\n"
        "(4) 口語轉自然書面語（「我覺得」→「我認為」、「超多」→「非常多」）\n"
        "(5) 適當分段，每段一個主題\n"
        "(6) 保持原文語氣與風格\n"
        "(7) 根據上下文調整用詞\n"
        "\n"
        "禁止：增加原文沒有的資訊、刪除核心內容、改變立場、使用半形標點。\n"
        "\n"
        "範例：\n"
        "輸入：然後關於那個ERP導入的部分我跟大家報告一下就是目前進度大概完成了百分之六十然後主要卡在就是權限設定因為每個部門需求都不一樣所以我們現在在一個一個確認\n"
        "輸出：關於ERP導入的部分，向大家報告目前的進度。整體大約完成了百分之六十，主要卡在權限設定的部分，因為每個部門的需求都不一樣，所以我們正在逐一確認。\n"
        "\n"
        "直接輸出結果，不要加任何說明。"
    ),
}

# 模式能力下限（model_size_b 需達到此值才可使用該模式）
_MODE_MIN_SIZE_B: dict[str, float] = {
    "light": 0.0,   # 所有模型
    "medium": 1.5,  # 至少 1.5B
    "full": 3.0,    # 至少 3B
}

# 採樣參數（確定性任務，壓低溫度）
_LOCAL_SAMPLING_PARAMS: dict[str, object] = {
    "temperature": 0.1,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0.0,
    "repeat_penalty": 1.1,
}

_LOCAL_TIMEOUT_SECONDS: float = 15.0
_LOCAL_CONTEXT_LENGTH: int = 4096

# manifest.json 路徑（支援 PyInstaller 打包環境）
from airtype.utils.paths import get_manifest_path as _get_manifest_path

_MANIFEST_PATH = _get_manifest_path()


class PolishError(Exception):
    """潤飾失敗，應回退至原始文字。"""


# ── 本機 LLM 引擎 ─────────────────────────────────────────────────────────────

class LocalLLMEngine:
    """透過 llama-cpp-python 執行本機 GGUF 模型推理（Qwen2.5 chat 格式）。"""

    def __init__(
        self,
        model_path: str,
        model_size_b: float = 1.5,
        model_id: Optional[str] = None,
    ) -> None:
        self._model_path = model_path
        self._model_size_b = model_size_b
        self._model_id = model_id or Path(model_path).stem
        self._llm: object = None
        self._lock = threading.Lock()

    # ── 模型大小自動降級 ──────────────────────────────────────────────────────

    def _resolve_mode(self, requested: str) -> str:
        """根據模型大小自動降級潤飾模式。

        閾值：FULL≥3B、MEDIUM≥1.5B、LIGHT≥0B。
        """
        min_size = _MODE_MIN_SIZE_B.get(requested, 0.0)
        if self._model_size_b >= min_size:
            return requested
        if requested == "full" and self._model_size_b >= 1.5:
            return "medium"
        return "light"

    # ── 前/後處理 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _pre_clean(text: str) -> str:
        """ASR 輸出前處理：壓縮連續語氣詞、重複贅詞，移除多餘空白。"""
        text = re.sub(r"([嗯啊呃唔哦喔欸])\1{2,}", r"\1", text)
        text = re.sub(r"(然後|就是|那個|所以說|基本上){2,}", r"\1", text)
        text = re.sub(r"\s+", "", text)
        return text.strip()

    @staticmethod
    def _post_clean(text: str) -> str:
        """LLM 輸出後處理：移除常見廢話前綴、markdown 包裹、首尾引號。"""
        prefixes = [
            r"^好的[，,。]?\s*",
            r"^以下是[^：:]*[：:]\s*",
            r"^修[正改]後[^：:]*[：:]\s*",
            r"^輸出[：:]\s*",
            r"^結果[：:]\s*",
        ]
        for pattern in prefixes:
            text = re.sub(pattern, "", text)

        # 移除 markdown 程式碼區塊包裹
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

        # 移除首尾引號包裹（半形或全形）
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("「") and text.endswith("」")
        ):
            inner = text[1:-1]
            if inner:
                text = inner

        return text.strip()

    # ── Manifest / Thinking Mode ──────────────────────────────────────────────

    def _read_manifest(self) -> Optional[dict]:
        """讀取 models/manifest.json 並回傳對應 model_id 的條目，找不到時回傳 None。"""
        try:
            if not _MANIFEST_PATH.exists():
                return None
            with _MANIFEST_PATH.open(encoding="utf-8") as f:
                manifest = json.load(f)
            return manifest.get(self._model_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("讀取 manifest 失敗（model_id=%s）：%s", self._model_id, exc)
            return None

    def _apply_thinking_token(self, text: str) -> str:
        """若 manifest 指定 thinking_disable_token，前綴至文字。"""
        entry = self._read_manifest()
        if entry is None:
            logger.debug("manifest 無條目 model_id=%s，略過 thinking token", self._model_id)
            return text
        if entry.get("has_thinking_mode") and entry.get("thinking_disable_token"):
            token = entry["thinking_disable_token"]
            return f"{token}{text}"
        return text

    # ── 模型載入 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_optimal_threads() -> int:
        cpu_count = os.cpu_count() or 4
        return max(1, cpu_count // 2)

    def _load_model(self) -> object:
        """延遲載入 GGUF 模型（執行緒安全）。"""
        with self._lock:
            if self._llm is None:
                try:
                    from llama_cpp import Llama  # type: ignore[import]

                    self._llm = Llama(
                        model_path=self._model_path,
                        n_ctx=_LOCAL_CONTEXT_LENGTH,
                        n_threads=self._detect_optimal_threads(),
                        verbose=False,
                    )
                    logger.info("本機 LLM 模型已載入：%s", self._model_path)
                except Exception as exc:
                    raise PolishError(f"無法載入本機 LLM 模型：{exc}") from exc
            return self._llm

    # ── 推理 ──────────────────────────────────────────────────────────────────

    def _infer(self, system_prompt: str, text: str, max_tokens: int) -> str:
        """執行 chat completion 推理（Qwen2.5 格式，不需手動組裝 ChatML）。"""
        llm = self._load_model()
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            max_tokens=max_tokens,
            stop=["<|im_end|>"],
            **_LOCAL_SAMPLING_PARAMS,
        )
        choices = response.get("choices", [])
        if not choices:
            raise PolishError("本機 LLM 未回傳任何結果")
        return choices[0]["message"]["content"].strip()

    def polish(self, text: str, system_prompt: str) -> str:
        """執行推理，超過 3 秒逾時則拋出 PolishError。

        流程：pre_clean → thinking token → _infer → post_clean
        """
        cleaned = self._pre_clean(text)
        if not cleaned:
            return text

        user_text = self._apply_thinking_token(cleaned)
        max_tokens = max(int(len(cleaned) * 3), 256)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._infer, system_prompt, user_text, max_tokens)
            try:
                result = future.result(timeout=_LOCAL_TIMEOUT_SECONDS)
                return self._post_clean(result)
            except FuturesTimeoutError:
                logger.warning("本機 LLM 推理超時（>%.1f 秒）", _LOCAL_TIMEOUT_SECONDS)
                raise PolishError("本機 LLM 推理逾時")
            except Exception as exc:
                raise PolishError(f"本機 LLM 推理失敗：{exc}") from exc


# ── API 引擎 ──────────────────────────────────────────────────────────────────

class APILLMEngine:
    """透過 httpx 呼叫 OpenAI 相容 API 端點。"""

    _DEFAULT_ENDPOINTS: dict[str, str] = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "ollama": "http://localhost:11434/v1",
    }

    def __init__(
        self,
        provider: str,
        api_key: str,
        endpoint: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 10.0,
    ) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = endpoint or self._DEFAULT_ENDPOINTS.get(
            provider, "https://api.openai.com/v1"
        )

    async def _call_api(self, system_prompt: str, user_text: str) -> str:
        """發送非同步 API 請求。"""
        try:
            import httpx  # type: ignore[import]
        except ImportError as exc:
            raise PolishError("httpx 未安裝，無法使用 API 模式") from exc

        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "max_tokens": max(256, len(user_text) * 3),
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        ) as client:
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise PolishError("API 未回傳任何結果")
        return choices[0]["message"]["content"].strip()

    def polish(self, text: str, system_prompt: str) -> str:
        """同步包裝非同步 API 呼叫（在獨立執行緒中執行，避免事件迴圈衝突）。"""
        def _run() -> str:
            return asyncio.run(self._call_api(system_prompt, text))

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(_run).result()
        except PolishError:
            raise
        except Exception as exc:
            raise PolishError(f"API 呼叫失敗：{exc}") from exc


# ── 主要 PolishEngine ─────────────────────────────────────────────────────────

class PolishEngine:
    """LLM 潤飾引擎主類別。

    根據 config 選擇本機或 API 後端，套用對應的系統提示詞，
    失敗時一律回退至原始文字。
    """

    def __init__(self, config: "AirtypeConfig") -> None:
        self._config = config
        self._local_engine: Optional[LocalLLMEngine] = None
        self._api_engine: Optional[APILLMEngine] = None

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        """依模式與自訂提示詞，回傳系統提示詞字串。

        custom_prompt 設定後取代所有模式的內建 prompt（優先級最高）。
        """
        llm_cfg = self._config.llm
        if llm_cfg.custom_prompt:
            return llm_cfg.custom_prompt
        return _SYSTEM_PROMPTS.get(llm_cfg.mode, _SYSTEM_PROMPTS["light"])

    @staticmethod
    def _resolve_model_path(local_model: str) -> str:
        """將模型 ID 解析為實際檔案路徑。

        策略：
        1. 若 local_model 已是有效檔案路徑，直接使用（向下相容）
        2. 查詢 models/manifest.json，以 id 匹配取得 filename
        3. 組合 ~/.airtype/models/{filename}
        4. 找不到時拋出 PolishError
        """
        if Path(local_model).exists():
            return local_model

        try:
            with _MANIFEST_PATH.open(encoding="utf-8") as f:
                manifest = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise PolishError(
                f"無法讀取 models/manifest.json 以解析模型 ID {local_model!r}：{exc}"
            ) from exc

        for entry in manifest.get("models", []):
            if entry.get("id") == local_model:
                filename = entry["filename"]
                return str(Path.home() / ".airtype" / "models" / filename)

        raise PolishError(
            f"模型 ID {local_model!r} 在 models/manifest.json 中找不到對應條目"
        )

    def _get_local_engine(self) -> LocalLLMEngine:
        """取得（或建立）本機 LLM 引擎。"""
        if self._local_engine is None:
            llm_cfg = self._config.llm
            model_path = self._resolve_model_path(llm_cfg.local_model)
            self._local_engine = LocalLLMEngine(
                model_path=model_path,
                model_size_b=llm_cfg.model_size_b,
                model_id=llm_cfg.local_model,
            )
        return self._local_engine

    def _get_api_engine(self) -> APILLMEngine:
        """取得（或建立）API 引擎。"""
        if self._api_engine is None:
            llm_cfg = self._config.llm
            from airtype.config import get_api_key  # noqa: PLC0415
            provider = llm_cfg.api_provider or "openai"
            api_key = get_api_key(provider) or ""
            self._api_engine = APILLMEngine(
                provider=provider,
                api_key=api_key,
                endpoint=llm_cfg.api_endpoint,
            )
        return self._api_engine

    # ── 公開介面 ──────────────────────────────────────────────────────────────

    def polish(self, text: str) -> str:
        """潤飾文字，失敗時回退至原始文字。

        Args:
            text: ASR 辨識原始文字。

        Returns:
            潤飾後文字，或原始文字（失敗時）。
        """
        if not text.strip():
            return text

        if not self._config.llm.enabled:
            return text

        system_prompt = self._get_system_prompt()

        try:
            source = self._config.llm.source
            if source == "local":
                local_engine = self._get_local_engine()
                actual_mode = local_engine._resolve_mode(self._config.llm.mode)
                if actual_mode != self._config.llm.mode:
                    logger.info(
                        "LLM 模式自動降級：%s → %s（model_size_b=%.1f）",
                        self._config.llm.mode,
                        actual_mode,
                        self._config.llm.model_size_b,
                    )
                    if not self._config.llm.custom_prompt:
                        system_prompt = _SYSTEM_PROMPTS.get(actual_mode, _SYSTEM_PROMPTS["light"])
                result = local_engine.polish(text, system_prompt)
            else:
                result = self._get_api_engine().polish(text, system_prompt)

            if result:
                logger.debug(
                    "LLM 潤飾完成 [%s/%s]：%r → %r",
                    source,
                    self._config.llm.mode,
                    text[:30],
                    result[:30],
                )
                return result
            return text

        except PolishError as exc:
            logger.warning("LLM 潤飾失敗，回退至原始文字：%s", exc)
            return text
        except Exception as exc:
            logger.exception("LLM 潤飾發生未預期錯誤：%s", exc)
            return text

    def reset(self) -> None:
        """釋放引擎資源（切換設定時使用）。"""
        self._local_engine = None
        self._api_engine = None
