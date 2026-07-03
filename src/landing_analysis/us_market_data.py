"""US market OHLCV fetching via yfinance with local cache."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from .ohlcv_cache import (
    DEFAULT_MAX_LOOKBACK,
    load_ohlcv_cache,
    merge_ohlcv,
    normalize_ohlcv,
    ohlcv_cache_path,
    required_start_date,
    save_ohlcv_cache,
    slice_for_period,
    to_date,
)


def download_us_range(ticker: str, start: date, end: date | None = None) -> pd.DataFrame:
    end_exclusive = (end + timedelta(days=1)) if end else None
    raw = yf.download(
        ticker,
        start=start.isoformat(),
        end=end_exclusive.isoformat() if end_exclusive else None,
        interval="1d",
        progress=False,
        auto_adjust=False,
    )
    if raw.empty:
        return raw
    return normalize_ohlcv(raw)


def download_us_period(ticker: str, period: str) -> pd.DataFrame:
    raw = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False)
    if raw.empty:
        return raw
    return normalize_ohlcv(raw)


def update_us_cache(
    ticker: str,
    period: str,
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    path = ohlcv_cache_path(data_dir, ticker)
    as_of = as_of or date.today()
    need_from = required_start_date(period, lookback_days, as_of)

    cached = load_ohlcv_cache(path)

    if cached is None:
        fresh = download_us_period(ticker, period)
        if fresh.empty:
            raise ValueError(f"No US data returned for ticker: {ticker}")
        save_ohlcv_cache(path, fresh)
        cached = fresh
    else:
        last_date = to_date(cached.index.max())
        if last_date < as_of:
            delta = download_us_range(ticker, last_date + timedelta(days=1), as_of)
            if not delta.empty:
                cached = merge_ohlcv(cached, delta)
                save_ohlcv_cache(path, cached)

        first_date = to_date(cached.index.min())
        if first_date > need_from:
            backfill = download_us_range(ticker, need_from, first_date - timedelta(days=1))
            if not backfill.empty:
                cached = merge_ohlcv(backfill, cached)
                save_ohlcv_cache(path, cached)
            elif cached.empty:
                fresh = download_us_period(ticker, period)
                if fresh.empty:
                    raise ValueError(f"No US data returned for ticker: {ticker}")
                cached = fresh
                save_ohlcv_cache(path, cached)

    return cached


def get_us_stock_data(
    ticker: str,
    period: str = "12mo",
    *,
    data_dir: Path,
    lookback_days: int = DEFAULT_MAX_LOOKBACK,
    as_of: date | None = None,
) -> pd.DataFrame:
    cached = update_us_cache(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
    )
    return slice_for_period(cached, period, lookback_days)
