"""US market OHLCV fetching via yfinance with local cache."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .ohlcv_cache import DEFAULT_MAX_LOOKBACK
from .yf_market_data import download_period as download_us_period
from .yf_market_data import download_range as download_us_range
from .yf_market_data import get_yf_stock_data, update_yf_cache


def update_us_cache(
    ticker: str,
    period: str,
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    return update_yf_cache(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
        market_label=ticker,
    )


def get_us_stock_data(
    ticker: str,
    period: str = "12mo",
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    return get_yf_stock_data(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
        market_label=ticker,
    )
