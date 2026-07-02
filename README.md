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
