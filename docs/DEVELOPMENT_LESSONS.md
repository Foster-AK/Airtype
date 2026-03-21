# Airtype v2.0 開發反思與踩坑經驗

> 撰寫日期：2026-03-21
> 開發期間：2026-03-03 ~ 2026-03-08（6 天）
> 規模：~15,200 行源碼 / 42 份 spec / 50 個變更 / 25 個 bug fix

---

## 一、開發流程反思

### 1.1 做得好的：Spec-Driven Development 帶來的秩序感

整個專案採用 SDD 流程，每個功能都經歷 `propose → design → specs → tasks → archive` 完整生命週期。這帶來幾個明顯好處：

- **可追溯性**：50 個變更都有清晰的「為什麼做」和「怎麼做」
- **品質把關**：先設計再實作，避免了邊寫邊改的混亂
- **知識留存**：即使三個月後回頭看，也能快速理解決策脈絡

### 1.2 做得差的：Git 被當成備份工具

6 天只有 6 次提交，第一次 commit 就把整個專案 dump 進 repo。後果：

- `git bisect` 完全無法使用
- Code review 不可能進行
- 無法 revert 單一功能

**教訓**：即使有精美的 spec 文件，如果 spec 文件遺失，整段開發歷史就無法重建。每完成一個 OpenSpec change 就應該提交一次，50 個 change 至少 50 次 commit。

### 1.3 速度與品質的取捨

6 天完成 22 個主功能 + 50 個變更，代價是端到端整合測試不足。每個模組都有 unit test，但真正打開麥克風 → VAD → ASR → LLM 潤飾 → 文字注入的完整鏈路測試幾乎沒有。

**教訓**：UI 元件先寫完程式碼和測試，卻沒有實際跑起來看效果，導致 25 個 bug 修復中大量是 UI 問題（不透明度、checkbox 渲染、滾動條、導航焦點）。

---

## 二、跨平台踩坑

### 2.1 Windows：音訊裝置的三重地獄

**問題**：Windows 上 `sounddevice.query_devices()` 會為同一支麥克風回傳多個條目（MME、DirectSound、WASAPI 各一個），導致裝置列表出現 3~4 個重複項目。

**根因**：PortAudio 在 Windows 上會暴露每個物理裝置在所有 Host API 下的版本。

**解法**：按平台偏好 Host API 過濾（Windows 上 WASAPI > DirectSound > MME），只保留首選 API 的裝置。

**延伸踩坑**：去重後用裝置名稱（字串）傳給 `sd.InputStream(device=...)`，sounddevice 內部再次查詢時仍找到多個同名裝置，拋出 `ValueError: Multiple input devices found`。最終改用裝置索引（int）徹底解決。

```python
# 錯誤做法
sd.InputStream(device="USB Microphone")  # 可能匹配到 MME + WASAPI 兩個

# 正確做法
sd.InputStream(device=3)  # 直接用 sounddevice 裝置索引
```

### 2.2 Windows WASAPI：16kHz 不是萬能的

**問題**：USB 麥克風在 WASAPI 共享模式下不支援 16kHz 取樣率，硬編碼 16kHz 導致 `PaErrorCode -9997 (Invalid sample rate)`。

**解法**：啟用 WASAPI 自動轉換旗標，讓 OS 驅動層處理取樣率轉換，零 CPU 額外開銷：

```python
import sounddevice as sd
import sys

extra = {}
if sys.platform == "win32":
    extra["extra_settings"] = sd.WasapiSettings(auto_convert=True)

stream = sd.InputStream(device=idx, samplerate=16000, **extra)
```

### 2.3 macOS PyInstaller：動態載入的模組會被吃掉

**問題**：ASR 引擎透過 `importlib.import_module()` 動態載入，PyInstaller 靜態分析無法偵測，打包後的 `.app` 完全不含引擎模組。

**解法**：在 `airtype.spec` 的 `hiddenimports` 中手動列出所有動態載入的模組：

```python
hiddenimports=[
    'airtype.core.asr_qwen_onnx',
    'airtype.core.asr_qwen_pytorch',
    'airtype.core.asr_qwen_mlx',
    'airtype.core.asr_breeze',
    'airtype.core.asr_sherpa',
    # ... 其他動態載入的模組
]
```

### 2.4 Windows RAM 偵測：wmic 已死

**問題**：`HardwareDetector` 在 `psutil` 不可用時用 `wmic` 作為 fallback，但 Windows 11 22H2+ 已廢棄 `wmic`，所有備案方法均失敗，退回假設 4096 MB。

**解法**：

1. 把 `psutil` 加入正式依賴
2. 在 `wmic` 之前插入 ctypes `GlobalMemoryStatusEx` 作為備案（純 Windows API，不依賴外部工具）

---

## 三、UI 渲染踩坑

### 3.1 QGraphicsOpacityEffect 的陷阱

**問題**：膠囊背景在切換音訊裝置時變色或消失。

**根因**：`CapsuleOverlay.__init__` 永久掛載 `QGraphicsOpacityEffect`，即使 opacity=1.0，所有渲染仍被強制經由離屏緩衝區。Windows 上 QComboBox dropdown 開啟/關閉時離屏緩衝區未正確重繪。

**教訓**：`QGraphicsOpacityEffect` 不是用來「設好就忘」的，應該僅在動畫期間臨時建立，動畫結束後呼叫 `setGraphicsEffect(None)` 移除。

```python
# 錯誤做法：永久掛載
self._opacity_effect = QGraphicsOpacityEffect(self)
self.setGraphicsEffect(self._opacity_effect)

# 正確做法：僅在動畫期間使用
def show_animated(self):
    effect = QGraphicsOpacityEffect(self)
    self.setGraphicsEffect(effect)
    # ... 動畫 ...
    animation.finished.connect(lambda: self.setGraphicsEffect(None))
```

### 3.2 深色主題下 Checkbox 的隱形術

**問題**：辭典設定頁面的 checkbox 在深色主題下 checked 時顯示純黑框無打勾、unchecked 時方框消失。

**根因**（兩層）：

1. `QTableWidgetItem` 的 checkbox 由 `QStyle::PE_IndicatorViewItemCheck` 繪製，深色 palette 下色彩路徑異常
2. 遺漏 `ItemIsSelectable` flag，Windows PySide6 需要此 flag 才能正確渲染

**解法**：放棄 `QTableWidgetItem` 的 checkState，改用 `setCellWidget()` 注入真正的 `QCheckBox` widget：

```python
def _make_check_widget(self, checked: bool) -> QWidget:
    cb = QCheckBox()
    cb.setChecked(checked)
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(cb)
    layout.setAlignment(Qt.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    return container
```

### 3.3 QSplitter + setFixedWidth = 互相矛盾

**問題**：辭典頁面用 `QSplitter` 分隔左右兩區，同時對左側 `setFixedWidth(160)`，導致 splitter 拖動功能無效、初始位置計算錯誤、兩側出現大段空白。

**教訓**：固定寬度和可調分割器本質衝突。如果一側需要固定寬度，直接用 `QHBoxLayout` + `stretch` 即可。

---

## 四、模型管理踩坑

### 4.1 模型名稱 ≠ 引擎 ID ≠ 檔案路徑

**問題**：程式碼在三個不同的抽象層之間混淆：

| 概念 | 範例 | 用途 |
|------|------|------|
| 模型名稱 | `qwen3-asr-0.6b` | 設定檔中使用者可見的值 |
| 引擎 ID | `qwen3-vulkan` | ASREngineRegistry 的 key |
| 檔案路徑 | `~/.airtype/models/qwen3-0.6b/encoder.onnx` | 實際磁碟位置 |

`load_default_engine()` 把模型名稱直接當引擎 ID 查詢 → `KeyError`。`PolishEngine` 把模型 ID 直接當檔案路徑 → `FileNotFoundError`。

**教訓**：設計 API 時必須明確區分這三層概念，並在每一層提供明確的映射邏輯。

### 4.2 模型目錄存在 ≠ 模型完整

**問題**：模型下載中途失敗，目錄已建立但缺少關鍵檔案（如 `encoder.onnx`）。現有程式碼只檢查目錄存在就認為模型可用。

**解法**：新增 `validate_model_files()` 方法，定義每個引擎的 `REQUIRED_FILES` 清單，區分「未下載」和「不完整」兩種狀態：

```python
class QwenOnnxEngine(ASREngine):
    REQUIRED_FILES = [
        "encoder.onnx",
        "decoder.onnx",
        "embed_tokens.bin",
        "tokenizer.json",
    ]
```

### 4.3 HuggingFace Gated Model：401 的無聲失敗

**問題**：gated model 需要認證才能下載，但下載器不帶 Authorization header → HTTP 401 → 靜默失敗。

**解法**：建立 token 自動偵測鏈：keyring → 環境變數 `HF_TOKEN` → `~/.cache/huggingface/token`，並在 manifest 中為 gated model 提供公開 mirror 作為 fallback。

### 4.4 huggingface_hub tqdm 相容性炸彈

**問題**：用 `functools.partial` 包裝進度回報 class 作為 `tqdm_class` 參數，但 `huggingface_hub` 內部要求 `tqdm_class` 具備完整的 class protocol（`get_lock`、`set_lock`、`__iter__`）。

**教訓**：`functools.partial` 不是 class，不能替代真正的子類別。需要用動態子類別或工廠模式。

---

## 五、功能邏輯踩坑

### 5.1 熱詞功能的三重斷裂

**問題**：使用者在字典中加入熱詞（如「龔玉惠」權重 7），但 ASR 仍辨識為同音錯字（「公寓會」）。

**根因**（三層全斷）：

1. `__main__.py` 初始化 `DictionaryEngine` 後從未呼叫 `sync_hot_words(asr_engine)`
2. sherpa-onnx 建構 Recognizer 時未傳 `hotwords_file` 參數
3. 熱詞檔案格式缺少權重（sherpa-onnx 要求 `詞語 :weight` 格式）

**教訓**：功能開發時如果涉及多個模組的串接，必須有一個端到端測試驗證完整鏈路，不能只測每個模組的單元功能。

### 5.2 設定面板改了值但膠囊沒反應

**問題**：調整不透明度滑桿，膠囊視窗不即時反映，要重啟才生效。

**根因**：`settings_window.connect_overlay(overlay)` 這行程式碼存在但從未被執行。Signal-Slot 連接根本不存在。

**教訓**：Qt 的 Signal-Slot 機制不會在連接失敗時報錯——它只是靜默地不做任何事。必須在整合時驗證每個連接是否真的生效。

---

## 六、架構層面的教訓

### 6.1 靜默失敗是最危險的 bug

整個開發過程中最常見的 bug 模式是**靜默失敗**：

- 引擎載入失敗用 `logger.debug` 記錄（INFO 級別看不到）
- `load_default_engine` 返回 None 但外層不檢查
- Signal 未連接但不報錯
- 模型不完整但只檢查目錄存在

**原則**：關鍵路徑上的失敗應該 **大聲失敗**。至少用 `logger.warning`，最好直接向使用者顯示明確的錯誤訊息。

### 6.2 抽象層混淆是設計缺陷的訊號

當「名稱」、「ID」、「路徑」三個概念在程式碼中被交替使用時，代表抽象邊界沒有畫清楚。解法不是加更多 if-else，而是在 API 層面明確定義每個參數接受的是哪一層的值。

### 6.3 平台差異比你想的多

即使使用了 Qt 這樣的跨平台框架，仍然會遇到：

- Windows PortAudio 的 Host API 多重性
- Windows WASAPI 的取樣率限制
- macOS PyInstaller 的動態載入問題
- Windows PySide6 style engine 的 checkbox 渲染差異
- Windows `wmic` 的廢棄

**原則**：每個平台相關的功能都需要在該平台上實際測試，不能假設「Qt 處理了跨平台」。

---

## 七、改善清單

### 立即可做

- [ ] 建立 `.gitattributes` 統一 LF 換行符
- [ ] 寫一份端到端整合測試（mock 音訊 → VAD → ASR → 文字注入）
- [ ] 設定 GitHub Actions CI（pytest + linting）

### 下個迭代

- [ ] 每個 OpenSpec change 對應一個 commit
- [ ] UI 開發時加入即時視覺驗證
- [ ] 統一語言規範（spec/commit/code 用英文，UI 用 i18n）

### 長期

- [ ] 引入 `feature/*` 分支策略
- [ ] 建立預錄音訊的 ASR 回歸測試
- [ ] 穩定 Spectra 工具鏈（delta spec 格式、archive 流程）

---

## 八、一句話總結

> **Spec-Driven Development 保證了設計品質，但跨平台的魔鬼藏在細節裡，而靜默失敗是最難抓的 bug。下次開發：小步提交、大聲失敗、每個平台都要實測。**
