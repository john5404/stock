# stock

股票分析與研究筆記，含落點分析 Python 工具與 UI。

## 落點分析 UI

桌面視窗工具，支援：

- 載入股票資料（yfinance）
- 落點分析（Fib、MA、成交量密集區、Pivot、Bollinger、Confluence）
- 回測（固定視窗 / 滾動視窗）
- 圖表顯示支撐/阻力與買賣點

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

### 預設標的

| 名稱 | Ticker |
|------|--------|
| 美光 | MU |
| 三星電子 | 005930.KS |
| SK 海力士 | 000660.KS |

## 分析報告

### 記憶體三巨頭（2026-07-02）

| 公司 | 代號 | 報告 |
|------|------|------|
| 美光科技 | NASDAQ: MU | [股價與支撐分析](analysis/micron-MU-2026-07-02.md) |
| 三星電子 | KRX: 005930 | [股價與支撐分析](analysis/samsung-005930-2026-07-02.md) |
| SK 海力士 | KRX: 000660 | [股價與支撐分析](analysis/sk-hynix-000660-2026-07-02.md) |
