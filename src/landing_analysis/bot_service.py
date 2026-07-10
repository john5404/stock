"""Headless orchestration layer for the Discord bot (and other non-UI callers).

This module wraps the existing analysis pipeline into small, side-effect-free
functions that return structured data. It deliberately avoids any Tkinter or
matplotlib GUI dependency so it can run on a server.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analyzer import AnalysisResult, LandingAnalyzer
from .data_fetcher import (
    fetch_stock_data,
    fetch_tw_institutional_data,
    normalize_ticker_input,
    ticker_market,
)
from .indicators import ensure_indicators

VALID_PERIODS: tuple[str, ...] = ("6mo", "12mo", "2y", "5y")
DEFAULT_PERIOD = "12mo"
DEFAULT_LOOKBACK = 42
MIN_LOOKBACK = 20
MAX_LOOKBACK = 120


class TickerError(ValueError):
    """Raised when a ticker cannot be resolved or has no usable data."""


def resolve_ticker(raw: str) -> tuple[str, str]:
    """Return ``(symbol, market)`` for a free-text ticker input.

    Accepts codes (``2330``), suffixed symbols (``2330.TW``), plain US symbols
    (``MU``) and mixed case. Chinese names are not resolved here.
    """

    text = (raw or "").strip()
    if not text:
        raise TickerError("請輸入股票代號")
    symbol = normalize_ticker_input(text)
    if not symbol:
        raise TickerError(f"無法解析代號：{raw}")
    return symbol, ticker_market(symbol)


def _normalize_period(period: str | None) -> str:
    if not period:
        return DEFAULT_PERIOD
    period = period.strip().lower()
    return period if period in VALID_PERIODS else DEFAULT_PERIOD


def _normalize_lookback(lookback: int | None) -> int:
    if not lookback:
        return DEFAULT_LOOKBACK
    return max(MIN_LOOKBACK, min(MAX_LOOKBACK, int(lookback)))


@dataclass
class Quote:
    symbol: str
    market: str
    price: float
    prev_close: float | None
    as_of: pd.Timestamp

    @property
    def change(self) -> float | None:
        if self.prev_close is None:
            return None
        return self.price - self.prev_close

    @property
    def change_pct(self) -> float | None:
        if not self.prev_close:
            return None
        return (self.price / self.prev_close - 1) * 100


def get_quote(raw: str) -> Quote:
    """Fetch the latest close (and previous close) for a ticker."""

    symbol, market = resolve_ticker(raw)
    df = fetch_stock_data(symbol, "6mo")
    if df is None or df.empty:
        raise TickerError(f"找不到標的資料：{symbol}")
    close = df["Close"].dropna()
    if close.empty:
        raise TickerError(f"找不到標的價格：{symbol}")
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) >= 2 else None
    return Quote(
        symbol=symbol,
        market=market,
        price=price,
        prev_close=prev,
        as_of=close.index[-1],
    )


@dataclass
class AnalysisBundle:
    symbol: str
    market: str
    is_tw: bool
    period: str
    lookback: int
    df: pd.DataFrame
    analysis: AnalysisResult
    institutional: pd.DataFrame | None = None


def analyze_ticker(
    raw: str,
    *,
    period: str | None = None,
    lookback: int | None = None,
    with_institutional: bool = False,
) -> AnalysisBundle:
    """Run the full landing-point analysis pipeline for a ticker."""

    symbol, market = resolve_ticker(raw)
    period = _normalize_period(period)
    lookback = _normalize_lookback(lookback)
    is_tw = market == "台股"

    df = fetch_stock_data(symbol, period)
    if df is None or df.empty:
        raise TickerError(f"找不到標的資料：{symbol}")
    df = ensure_indicators(df)

    needed = max(lookback, MIN_LOOKBACK)
    if len(df) < needed:
        raise TickerError(f"{symbol} 資料筆數不足（需 {needed}，實得 {len(df)}）")

    analysis = LandingAnalyzer().analyze(df, symbol, lookback)

    institutional: pd.DataFrame | None = None
    if with_institutional and is_tw:
        try:
            inst = fetch_tw_institutional_data(symbol, period)
            if inst is not None and not inst.empty:
                institutional = inst
        except Exception:
            institutional = None

    return AnalysisBundle(
        symbol=symbol,
        market=market,
        is_tw=is_tw,
        period=period,
        lookback=lookback,
        df=df,
        analysis=analysis,
        institutional=institutional,
    )


def top_levels(analysis: AnalysisResult, kind: str, limit: int = 3):
    """Return the strongest ``limit`` support/resistance clusters.

    Supports are ordered nearest-below current price first; resistances
    nearest-above first, then by strength.
    """

    current = analysis.current_price
    if kind == "support":
        pool = [lv for lv in analysis.supports if lv.price <= current] or list(analysis.supports)
        pool.sort(key=lambda lv: (-lv.strength, current - lv.price))
    else:
        pool = [lv for lv in analysis.resistances if lv.price >= current] or list(analysis.resistances)
        pool.sort(key=lambda lv: (-lv.strength, lv.price - current))
    return pool[:limit]
