# Models Manifest

`manifest.json` lists all available ASR and LLM models for Airtype.

## HuggingFace Repository 實際結構（2026-03 確認）

| Model ID | HuggingFace Repository | 狀態 | 實際檔案 |
|---|---|---|---|
| `qwen3-asr-1.7b-openvino` | `Qwen/Qwen3-ASR-1.7B-openvino-int8` | ⚠️ 尚未發布 | — |
| `qwen3-asr-0.6b-openvino` | `Qwen/Qwen3-ASR-0.6B-openvino-int8` | ⚠️ 尚未發布 | — |
| `qwen3-asr-1.7b` | `Qwen/Qwen3-ASR-1.7B` | ✅ 公開 | `model-00001-of-00002.safetensors` (4.22GB) + `model-00002-of-00002.safetensors` (478MB) |
| `qwen3-asr-0.6b` | `OpenVoiceOS/qwen3-asr-0.6b-q5-k-m` | ✅ 公開 | `qwen3-asr-0.6b-q5_k_m.gguf` (768MB) |

### OpenVINO INT8 模型說明

截至 2026-03，`Qwen/Qwen3-ASR-1.7B-openvino-int8` 與 `Qwen/Qwen3-ASR-0.6B-openvino-int8` 在 HuggingFace 上**尚未發布**。
OpenVINO 組織有提供 base Qwen3 的 int8 版（如 `OpenVINO/Qwen3-0.6B-int8-ov`），但 ASR 專用版未公開。

如需使用 OpenVINO CPU 推理路徑，目前需要：
1. 手動下載 `Qwen/Qwen3-ASR-0.6B` safetensors
2. 使用 [optimum-intel](https://github.com/huggingface/optimum-intel) 自行轉換並量化

待官方發布 OpenVINO INT8 打包版後，`manifest.json` 的 `urls` 欄位將更新。

### Qwen3-ASR-1.7B 多 shard 說明

`Qwen/Qwen3-ASR-1.7B` 模型分為 2 個 safetensors shard，共約 4.7GB，且不能只下載其中一個 shard 單獨使用。
目前 ModelManager 的單檔下載架構不直接支援此模型，需透過 `qwen-asr` 套件的 `from_pretrained` 方式載入。

## Authentication

Airtype automatically detects a HuggingFace Access Token in the following order:

1. **App settings** — Enter your token in Settings > Models > HuggingFace Access Token
2. **Environment variable** — Set `HF_TOKEN` before launching Airtype
3. **huggingface-cli cache** — Run `huggingface-cli login` beforehand

Obtain a token at: https://huggingface.co/settings/tokens

## Public Mirror Fallback

The `fallback_urls` field in `manifest.json` is currently **empty** for all Qwen3-ASR models.
No verified public mirror with matching SHA-256 checksums has been confirmed at this time.

`qwen3-asr-0.6b` 現使用 `OpenVoiceOS/qwen3-asr-0.6b-q5-k-m`（社群提供，Apache 2.0），此 repo 為公開存取，無需 HuggingFace token。
