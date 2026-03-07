## Why

模型管理設定頁面（設定視窗 → 模型管理）出現水平 scrollbar，導致使用者每次要操作下載或刪除按鈕時，都需要先向右滑動才能看到操作區域。根因是模型卡片內的描述文字過長（如「Qwen3-ASR 0.6B GGUF Q5_K_M（Vulkan / CPU 輕量路徑，由 OpenVoiceOS 提供）」），加上右側動作區固定寬度 130px，導致卡片總寬度超出 QScrollArea 可用空間。

## What Changes

- **禁用水平捲軸**：QScrollArea 設定 `ScrollBarAlwaysOff`，消除水平 scrollbar。
- **模型描述拆為兩行**：以全形括號 `（` 為分割點，第一行顯示模型名稱（粗體），第二行顯示說明文字（灰色小字），避免單行文字過長。
- **縮減按鈕寬度**：右側動作區從 130px 縮至 90px，按鈕從 120px 縮至 80px，減少不必要的留白。

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `settings-models`：模型卡片的顯示佈局變更——描述文字由單行改為雙行顯示，動作區寬度縮減，水平捲軸行為變更。

## Impact

- 受影響程式碼：`airtype/ui/settings_models.py`（ModelCardWidget._build_ui、SettingsModelsPage._build_ui）
- 受影響規格：`settings-models`
- 無 API 或相依套件變更
