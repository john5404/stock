"""Technical indicators."""

import numpy as np
import pandas as pd


def moving_average(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return ma, ma - std_mult * std, ma + std_mult * std


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["MA20"] = moving_average(out["Close"], 20)
    out["MA50"] = moving_average(out["Close"], 50)
    out["MA200"] = moving_average(out["Close"], 200)
    out["RSI"] = rsi(out["Close"])
    out["ATR"] = atr(out)
    bb_mid, bb_low, bb_up = bollinger(out["Close"])
    out["BB_Mid"] = bb_mid
    out["BB_Low"] = bb_low
    out["BB_Up"] = bb_up
    return out
