"""Local OHLCV cache stored under stock/data (backward-compatible facade)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .ohlcv_cache import (
    DEFAULT_MAX_LOOKBACK,
    PERIOD_DAYS,
    REQUIRED_COLUMNS,
    WARMUP_DAYS,
    default_data_dir,
    load_ohlcv_cache as load_cache,
    merge_ohlcv,
    normalize_ohlcv as normalize_df,
    ohlcv_cache_path as cache_path,
    period_required_calendar_days,
    required_start_date,
    save_ohlcv_cache as save_cache,
    slice_for_period,
    to_date as _to_date,
)
from .tw_market_data import download_tw_period, download_tw_range, get_tw_stock_data, is_tw_ticker, update_tw_cache
from .us_market_data import download_us_period, download_us_range, get_us_stock_data, update_us_cache


def _resolve_data_dir(data_dir: Path | None) -> Path:
    return data_dir or default_data_dir()


def download_period(ticker: str, period: str) -> pd.DataFrame:
    if is_tw_ticker(ticker):
        return download_tw_period(ticker, period)
    return download_us_period(ticker, period)


def download_range(ticker: str, start: date, end: date | None = None) -> pd.DataFrame:
    if is_tw_ticker(ticker):
        return download_tw_range(ticker, start, end)
    return download_us_range(ticker, start, end)


def update_cache(
    ticker: str,
    period: str,
    *,
    data_dir: Path | None = None,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    resolved = _resolve_data_dir(data_dir)
    if is_tw_ticker(ticker):
        return update_tw_cache(ticker, period, data_dir=resolved, lookback_days=lookback_days, as_of=as_of)
    return update_us_cache(ticker, period, data_dir=resolved, lookback_days=lookback_days, as_of=as_of)


def get_stock_data(
    ticker: str,
    period: str = "12mo",
    *,
    data_dir: Path | None = None,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    resolved = _resolve_data_dir(data_dir)
    if is_tw_ticker(ticker):
        return get_tw_stock_data(
            ticker,
            period,
            data_dir=resolved,
            lookback_days=lookback_days,
            as_of=as_of,
        )
    return get_us_stock_data(
        ticker,
        period,
        data_dir=resolved,
        lookback_days=lookback_days,
        as_of=as_of,
    )
