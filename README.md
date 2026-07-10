# stock

股票分析與研究筆記，含落點分析 Python 工具與 UI。

## 落點分析 UI

桌面視窗工具，支援：

- 載入股票資料（yfinance）
- 落點分析（Fib、MA、成交量密集區、Pivot、Bollinger、Confluence）
- **策略模板**：設備股 / 熱門股 / 自訂參數
- 回測（固定視窗 / 滾動視窗）
- 圖表顯示支撐/阻力與買賣點

### 策略模板

| 模板 | 適用標的 | 停損 | 停利 | 特色 |
|------|----------|------|------|------|
| **設備股** | KLAC、AMAT、ASML、LRCX | -8% | 阻力停利 | 短線波段、快停利 |
| **熱門股** | MU、SNDK、MRVL、INTC、AMD、NVDA | -12% | 移動停利 20% | 突破加碼、MA50 過濾 |
| **自訂** | 任意 Ticker | 自行設定 | 自行設定 | 全部參數可調 |

### 安裝

```bash
pip install -r requirements.txt
```

Linux 若缺少 tkinter，請先安裝：

```bash
sudo apt install python3-tk
```

### 啟動 UI

```bash
python app.py
```

## Discord Bot

以相同的分析核心提供三個唯讀 slash 指令（不含桌面 UI 的互動與持股編輯）。

| 指令 | 說明 |
|------|------|
| `/quote <ticker>` | 查詢現價、漲跌、市場 |
| `/analyze <ticker> [period] [lookback]` | 落點摘要：現價、ATR、波段高低、主要支撐/阻力 |
| `/chart <ticker> [period] [lookback] [institutional]` | 產生落點分析圖（Scheme C）並上傳 |

- `ticker`：`MU`、`2330`、`2330.TW` 皆可（數字自動判定台股、英文判定美股）。
- `period`：`6mo` / `12mo` / `2y` / `5y`（預設 `12mo`）。
- `lookback`：分析視窗交易日 20–120（預設 42）。
- `institutional`：僅台股有效，顯示三大法人（需 `FINMIND_TOKEN`）。

### 設定與啟動

1. 安裝相依套件（含 `discord.py`）：

```bash
pip install -r requirements.txt
```

2. 複製 `.env.example` 為 `.env`，填入：

```
DISCORD_BOT_TOKEN=你的_bot_token
DISCORD_GUILD_ID=       # 選填，填伺服器 id 可即時同步指令
FINMIND_TOKEN=          # 選填，台股三大法人才需要
```

3. 到 [Discord Developer Portal](https://discord.com/developers/applications) 建立應用程式與 Bot，
   以 `applications.commands`（及 `bot`）scope 邀請進伺服器。

4. 啟動：

```bash
python discord_bot.py
```

> Linux 伺服器若圖表中文顯示為方框，請安裝中文字型（例如 `fonts-noto-cjk`）。
