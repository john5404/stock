"""Shared OHLCV cache helpers for local CSV storage."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PERIOD_DAYS: dict[str, int] = {
    "6mo": 183,
    "12mo": 365,
    "2y": 730,
    "5y": 1825,
}

WARMUP_DAYS = 260
DEFAULT_MAX_LOOKBACK = 120

REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def ohlcv_cache_path(data_dir: Path, ticker: str) -> Path:
    safe = ticker.strip().upper().replace("/", "_")
    return data_dir / f"{safe}.csv"


def normalize_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna().sort_index()
    df.columns = [str(c).capitalize() for c in df.columns]
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    return df[list(REQUIRED_COLUMNS)]


def to_date(ts) -> date:
    return pd.Timestamp(ts).date()


def load_ohlcv_cache(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    if df.empty:
        return None
    return normalize_ohlcv(df)


def save_ohlcv_cache(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = normalize_ohlcv(df)
    out.index.name = "Date"
    out.to_csv(path, date_format="%Y-%m-%d")


def merge_ohlcv(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return normalize_ohlcv(new)
    if new is None or new.empty:
        return normalize_ohlcv(existing)
    combined = pd.concat([existing, new])
    combined = combined[~combined.index.duplicated(keep="last")]
    return normalize_ohlcv(combined)


def period_required_calendar_days(period: str, lookback_days: int = DEFAULT_MAX_LOOKBACK) -> int:
    base = PERIOD_DAYS.get(period, PERIOD_DAYS["12mo"])
    return base + lookback_days + WARMUP_DAYS


def required_start_date(period: str, lookback_days: int, as_of: date | None = None) -> date:
    as_of = as_of or date.today()
    span = period_required_calendar_days(period, lookback_days)
    return as_of - timedelta(days=int(span * 1.5))


def slice_for_period(df: pd.DataFrame, period: str, lookback_days: int) -> pd.DataFrame:
    if df.empty:
        raise ValueError("No cached data available")

    period_days = PERIOD_DAYS.get(period, PERIOD_DAYS["12mo"])
    end = df.index.max()
    period_start = end - pd.Timedelta(days=int(period_days * 1.5))
    warmup_start = period_start - pd.Timedelta(days=int(WARMUP_DAYS * 1.5))
    sliced = df[df.index >= warmup_start].copy()

    min_rows = lookback_days + 10
    if len(sliced) < min_rows:
        sliced = df.tail(max(min_rows, len(df))).copy()
    if len(sliced) < lookback_days + 5:
        raise ValueError(
            f"Not enough data for period={period} lookback={lookback_days}; "
            f"need at least {lookback_days + 5} rows, got {len(sliced)}"
        )
    return sliced
