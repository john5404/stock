"""Taiwan market OHLCV fetching via yfinance with local cache."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .ohlcv_cache import DEFAULT_MAX_LOOKBACK
from .yf_market_data import download_period as download_tw_period
from .yf_market_data import download_range as download_tw_range
from .yf_market_data import get_yf_stock_data, update_yf_cache


def tw_stock_id(ticker: str) -> str:
    """2330.TW / 8299.TWO -> 2330 / 8299."""
    base = ticker.strip().upper().split(".")[0]
    if not base.isdigit():
        raise ValueError(f"Invalid Taiwan ticker: {ticker}")
    return base


def is_tw_ticker(ticker: str) -> bool:
    upper = ticker.strip().upper()
    return upper.endswith(".TW") or upper.endswith(".TWO")


def update_tw_cache(
    ticker: str,
    period: str,
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    if not is_tw_ticker(ticker):
        raise ValueError(f"Not a Taiwan ticker: {ticker}")
    return update_yf_cache(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
        market_label=ticker,
    )


def get_tw_stock_data(
    ticker: str,
    period: str = "12mo",
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    if not is_tw_ticker(ticker):
        raise ValueError(f"Not a Taiwan ticker: {ticker}")
    return get_yf_stock_data(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
        market_label=ticker,
    )
