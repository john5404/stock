"""Market data fetching."""

import re

import pandas as pd

from .data_store import get_stock_data
from .ohlcv_cache import DEFAULT_MAX_LOOKBACK, default_data_dir
from .tw_institutional_store import get_tw_institutional_data
from .tw_market_data import is_tw_ticker

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

US_TICKERS: dict[str, str] = {
    "美光 (MU)": "MU",
    "KLA (KLAC)": "KLAC",
    "應材 (AMAT)": "AMAT",
    "ASML": "ASML",
    "Lam (LRCX)": "LRCX",
    "SanDisk (SNDK)": "SNDK",
    "Marvell (MRVL)": "MRVL",
    "Intel (INTC)": "INTC",
    "AMD": "AMD",
    "NVIDIA (NVDA)": "NVDA",
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "三星 (005930)": "005930.KS",
    "SK海力士 (000660)": "000660.KS",
}

TW_TICKERS: dict[str, str] = {
    "台積電 (2330)": "2330.TW",
    "聯發科 (2454)": "2454.TW",
    "鴻海 (2317)": "2317.TW",
    "台達電 (2308)": "2308.TW",
    "廣達 (2382)": "2382.TW",
    "緯創 (3231)": "3231.TW",
    "大立光 (3008)": "3008.TW",
    "聯電 (2303)": "2303.TW",
    "瑞昱 (2379)": "2379.TW",
    "南亞科 (2408)": "2408.TW",
    "華邦電 (2344)": "2344.TW",
    "旺宏 (2337)": "2337.TW",
    "群聯 (8299)": "8299.TWO",
    "智原 (3035)": "3035.TW",
    "世界 (5347)": "5347.TWO",
}

MARKET_TICKERS: dict[str, dict[str, str]] = {
    "美股": US_TICKERS,
    "台股": TW_TICKERS,
}

# Backward compatibility for scripts importing PRESET_TICKERS
PRESET_TICKERS = {**US_TICKERS, **TW_TICKERS}


def detect_market_from_input(raw: str) -> str:
    text = raw.strip()
    if not text:
        return "美股"
    upper = text.upper()
    if upper.endswith(".TW") or upper.endswith(".TWO"):
        return "台股"
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return "美股"
    if _CJK_RE.search(text):
        return "台股"
    if text.isdigit():
        # Taiwan listings are typically 4 digits; 5+ digits are treated as US/KR symbols.
        return "台股" if len(text) <= 4 else "美股"
    return "美股"


def ticker_market(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith(".TW") or sym.endswith(".TWO"):
        return "台股"
    return "美股"


def normalize_ticker_input(raw: str, market: str | None = None) -> str:
    text = raw.strip().upper()
    if not text:
        return text
    if "." in text:
        return text
    mkt = market or detect_market_from_input(raw)
    if mkt == "台股" and text.isdigit():
        return f"{text}.TW"
    if mkt == "美股" and text.isdigit() and len(text) >= 5:
        return f"{text}.KS"
    return text


def get_market_tickers(market: str) -> dict[str, str]:
    return dict(MARKET_TICKERS.get(market, {}))


def fetch_stock_data(
    ticker: str,
    period: str = "12mo",
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
) -> pd.DataFrame:
    return get_stock_data(ticker, period, lookback_days=lookback_days)


def fetch_tw_institutional_data(
    ticker: str,
    period: str = "12mo",
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
) -> pd.DataFrame:
    if not is_tw_ticker(ticker):
        raise ValueError(f"Institutional data is only available for Taiwan tickers: {ticker}")
    return get_tw_institutional_data(
        ticker,
        period,
        data_dir=default_data_dir(),
        lookback_days=lookback_days,
    )
