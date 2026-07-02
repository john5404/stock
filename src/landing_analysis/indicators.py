"""Technical indicators and candlestick patterns."""

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


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return ma, ma - std_mult * std, ma + std_mult * std


def _body(o, c):
    return (c - o).abs()


def _upper_shadow(h, o, c):
    return h - np.maximum(o, c)


def _lower_shadow(l, o, c):
    return np.minimum(o, c) - l


def detect_hammer(df: pd.DataFrame) -> pd.Series:
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    body = _body(o, c)
    lower = _lower_shadow(l, o, c)
    upper = _upper_shadow(h, o, c)
    range_ = (h - l).replace(0, np.nan)
    return (lower >= body * 2) & (upper <= body * 0.5) & (body / range_ <= 0.35)


def detect_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    o, c = df["Open"], df["Close"]
    prev_o, prev_c = o.shift(1), c.shift(1)
    today_bull = c > o
    prev_bear = prev_c < prev_o
    engulf = (c >= prev_o) & (o <= prev_c)
    return today_bull & prev_bear & engulf


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

    macd_line, signal_line, histogram = macd(out["Close"])
    out["MACD"] = macd_line
    out["MACD_Signal"] = signal_line
    out["MACD_Hist"] = histogram
    out["MACD_Bull"] = macd_line > signal_line
    out["MACD_Golden"] = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    out["MACD_Death"] = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

    out["Vol_MA20"] = moving_average(out["Volume"], 20)
    out["Vol_Shrink"] = out["Volume"] < out["Vol_MA20"] * 0.85
    out["Vol_Expand"] = out["Volume"] > out["Vol_MA20"] * 1.10

    out["Hammer"] = detect_hammer(out)
    out["Bull_Engulf"] = detect_bullish_engulfing(out)
    out["Bullish_Candle"] = out["Hammer"] | out["Bull_Engulf"]

    return out
