"""Market data fetching."""

import pandas as pd
import yfinance as yf

PRESET_TICKERS = {
    "美光 MU": "MU",
    "三星 005930": "005930.KS",
    "SK海力士 000660": "000660.KS",
}


def normalize_df(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna().sort_index()
    df.columns = [str(c).capitalize() for c in df.columns]
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return df


def fetch_stock_data(ticker: str, period: str = "12mo") -> pd.DataFrame:
    raw = yf.download(ticker, period=period, interval="1d", progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for ticker: {ticker}")
    return normalize_df(raw)
