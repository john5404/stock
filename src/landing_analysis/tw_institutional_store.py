"""Taiwan institutional investor data (三大法人) via FinMind with local cache."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from .env_config import load_local_env
from .ohlcv_cache import default_data_dir, period_required_calendar_days, to_date
from .tw_market_data import tw_stock_id

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
FINMIND_DATASET = "TaiwanStockInstitutionalInvestorsBuySellWide"

INSTITUTIONAL_COLUMNS = (
    "foreign_net",
    "trust_net",
    "dealer_net",
    "total_net",
    "foreign_buy",
    "foreign_sell",
    "trust_buy",
    "trust_sell",
    "dealer_buy",
    "dealer_sell",
)


def default_institutional_dir(data_dir: Path | None = None) -> Path:
    base = data_dir or default_data_dir()
    return base / "institutional"


def institutional_cache_path(data_dir: Path, stock_id: str) -> Path:
    safe = stock_id.strip()
    return data_dir / "institutional" / f"{safe}.csv"


def finmind_token() -> str:
    load_local_env()
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "FINMIND_TOKEN is not set. Register at https://finmindtrade.com and export your API token."
        )
    return token


def _net(buy: pd.Series, sell: pd.Series) -> pd.Series:
    return buy.fillna(0) - sell.fillna(0)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(0, index=df.index, dtype=float)


def normalize_institutional(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=list(INSTITUTIONAL_COLUMNS))

    df = raw.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df.index = pd.to_datetime(df.index).normalize()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()

    if "total_net" in df.columns and "Foreign_Investor_buy" not in df.columns:
        return df[list(INSTITUTIONAL_COLUMNS)]

    foreign_buy = _col(df, "Foreign_Investor_buy") + _col(df, "Foreign_Dealer_Self_buy")
    foreign_sell = _col(df, "Foreign_Investor_sell") + _col(df, "Foreign_Dealer_Self_sell")
    trust_buy = _col(df, "Investment_Trust_buy")
    trust_sell = _col(df, "Investment_Trust_sell")

    dealer_buy = (
        _col(df, "Dealer_buy")
        + _col(df, "Dealer_self_buy")
        + _col(df, "Dealer_Hedging_buy")
    )
    dealer_sell = (
        _col(df, "Dealer_sell")
        + _col(df, "Dealer_self_sell")
        + _col(df, "Dealer_Hedging_sell")
    )

    out = pd.DataFrame(index=df.index)
    out["foreign_buy"] = foreign_buy
    out["foreign_sell"] = foreign_sell
    out["trust_buy"] = trust_buy
    out["trust_sell"] = trust_sell
    out["dealer_buy"] = dealer_buy
    out["dealer_sell"] = dealer_sell
    out["foreign_net"] = _net(foreign_buy, foreign_sell)
    out["trust_net"] = _net(trust_buy, trust_sell)
    out["dealer_net"] = _net(dealer_buy, dealer_sell)
    out["total_net"] = out["foreign_net"] + out["trust_net"] + out["dealer_net"]
    return out[list(INSTITUTIONAL_COLUMNS)]


def load_institutional_cache(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    if df.empty:
        return None
    if "total_net" in df.columns:
        df.index = pd.to_datetime(df.index).normalize()
        return df[list(INSTITUTIONAL_COLUMNS)]
    return normalize_institutional(df)


def save_institutional_cache(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = normalize_institutional(df)
    out.index.name = "date"
    out.to_csv(path, date_format="%Y-%m-%d")


def merge_institutional(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return normalize_institutional(new)
    if new is None or new.empty:
        return normalize_institutional(existing)
    combined = pd.concat([existing, new])
    combined = combined[~combined.index.duplicated(keep="last")]
    return normalize_institutional(combined)


def download_institutional_range(
    stock_id: str,
    start: date,
    end: date,
    *,
    token: str | None = None,
) -> pd.DataFrame:
    token = token or finmind_token()
    params = {
        "dataset": FINMIND_DATASET,
        "data_id": stock_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(FINMIND_API_URL, params=params, headers=headers, timeout=60)
    if resp.status_code == 402:
        raise ValueError("FinMind API quota exceeded (HTTP 402). Try again later or upgrade your plan.")
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != 200:
        msg = payload.get("msg", "Unknown FinMind API error")
        raise ValueError(f"FinMind API error: {msg}")

    rows = payload.get("data") or []
    if not rows:
        return pd.DataFrame()
    return normalize_institutional(pd.DataFrame(rows))


def institutional_required_start(period: str, lookback_days: int, as_of: date | None = None) -> date:
    as_of = as_of or date.today()
    span = period_required_calendar_days(period, lookback_days)
    return as_of - timedelta(days=int(span * 1.5))


def update_institutional_cache(
    ticker: str,
    period: str,
    *,
    data_dir: Path | None = None,
    lookback_days: int = 120,
    as_of: date | None = None,
    token: str | None = None,
) -> pd.DataFrame:
    stock_id = tw_stock_id(ticker)
    base_dir = data_dir or default_data_dir()
    path = institutional_cache_path(base_dir, stock_id)
    as_of = as_of or date.today()
    need_from = institutional_required_start(period, lookback_days, as_of)

    cached = load_institutional_cache(path)

    if cached is None:
        fresh = download_institutional_range(stock_id, need_from, as_of, token=token)
        if fresh.empty:
            raise ValueError(f"No institutional data returned for {stock_id}")
        save_institutional_cache(path, fresh)
        cached = fresh
    else:
        last_date = to_date(cached.index.max())
        if last_date < as_of:
            delta = download_institutional_range(stock_id, last_date + timedelta(days=1), as_of, token=token)
            if not delta.empty:
                cached = merge_institutional(cached, delta)
                save_institutional_cache(path, cached)

        first_date = to_date(cached.index.min())
        if first_date > need_from:
            backfill = download_institutional_range(stock_id, need_from, first_date - timedelta(days=1), token=token)
            if not backfill.empty:
                cached = merge_institutional(backfill, cached)
                save_institutional_cache(path, cached)

    return cached


def get_tw_institutional_data(
    ticker: str,
    period: str = "12mo",
    *,
    data_dir: Path | None = None,
    lookback_days: int = 120,
    as_of: date | None = None,
    token: str | None = None,
) -> pd.DataFrame:
    cached = update_institutional_cache(
        ticker,
        period,
        data_dir=data_dir,
        lookback_days=lookback_days,
        as_of=as_of,
        token=token,
    )
    as_of_ts = pd.Timestamp(as_of or date.today())
    need_from = pd.Timestamp(institutional_required_start(period, lookback_days, as_of or date.today()))
    sliced = cached[(cached.index >= need_from) & (cached.index <= as_of_ts)].copy()
    if sliced.empty:
        sliced = cached.tail(max(lookback_days + 5, 30)).copy()
    return sliced
