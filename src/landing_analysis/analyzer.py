"""Landing point (support/resistance) analysis."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .indicators import add_indicators, atr, bollinger, moving_average


@dataclass
class LevelCluster:
    price: float
    methods: list[str]
    strength: int
    kind: str  # support | resistance

    @property
    def stars(self) -> str:
        return "★" * min(self.strength, 5)


@dataclass
class AnalysisResult:
    ticker: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    current_price: float
    swing_high: float
    swing_low: float
    atr: float
    supports: list[LevelCluster] = field(default_factory=list)
    resistances: list[LevelCluster] = field(default_factory=list)


def fibonacci_levels(high: float, low: float) -> dict[str, float]:
    diff = high - low
    return {
        "Fib 38.2%": high - diff * 0.382,
        "Fib 50.0%": high - diff * 0.500,
        "Fib 61.8%": high - diff * 0.618,
    }


def volume_levels(df: pd.DataFrame, n_bins: int = 30) -> list[float]:
    prices = df["Close"].values
    volumes = df["Volume"].values
    lo, hi = prices.min(), prices.max()
    if hi <= lo:
        return [float(lo)]
    bins = np.linspace(lo, hi, n_bins + 1)
    profile = np.zeros(n_bins)
    for price, vol in zip(prices, volumes):
        idx = min(int((price - lo) / (hi - lo) * n_bins), n_bins - 1)
        profile[idx] += vol
    centers = (bins[:-1] + bins[1:]) / 2
    order = np.argsort(profile)[::-1]
    return [float(centers[i]) for i in order if profile[i] > 0][:5]


def pivot_levels(df: pd.DataFrame) -> dict[str, float]:
    last = df.iloc[-1]
    pivot = (last["High"] + last["Low"] + last["Close"]) / 3
    return {
        "Pivot": pivot,
        "Pivot S1": 2 * pivot - last["High"],
        "Pivot S2": pivot - (last["High"] - last["Low"]),
        "Pivot R1": 2 * pivot - last["Low"],
        "Pivot R2": pivot + (last["High"] - last["Low"]),
    }


def cluster_levels(levels: list[tuple[float, str]], kind: str, tol: float = 0.02) -> list[LevelCluster]:
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda x: x[0])
    clusters: list[list[tuple[float, str]]] = [[sorted_levels[0]]]
    for level in sorted_levels[1:]:
        avg = np.mean([x[0] for x in clusters[-1]])
        if abs(level[0] - avg) / max(avg, 1e-9) <= tol:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    result = []
    for cluster in clusters:
        result.append(
            LevelCluster(
                price=float(np.mean([x[0] for x in cluster])),
                methods=[x[1] for x in cluster],
                strength=len(cluster),
                kind=kind,
            )
        )
    return sorted(result, key=lambda x: x.price)


class LandingAnalyzer:
    def analyze(self, df: pd.DataFrame, ticker: str, lookback_days: int = 42) -> AnalysisResult:
        if len(df) < max(lookback_days, 20):
            raise ValueError(f"Need at least {max(lookback_days, 20)} rows, got {len(df)}")

        train = df.iloc[-lookback_days:].copy()
        train = add_indicators(train)
        swing_high = float(train["High"].max())
        swing_low = float(train["Low"].min())
        current_price = float(df["Close"].iloc[-1])
        atr_val = float(atr(train).iloc[-1])

        supports: list[tuple[float, str]] = []
        resistances: list[tuple[float, str]] = []

        for name, value in fibonacci_levels(swing_high, swing_low).items():
            supports.append((value, name))

        bb_mid, bb_low, bb_up = bollinger(train["Close"])
        supports.extend(
            [
                (float(bb_low.iloc[-1]), "Bollinger Lower"),
                (float(bb_mid.iloc[-1]), "Bollinger Mid"),
            ]
        )
        resistances.append((float(bb_up.iloc[-1]), "Bollinger Upper"))

        ma20 = moving_average(train["Close"], 20).iloc[-1]
        ma50 = moving_average(train["Close"], min(50, len(train))).iloc[-1]
        if not np.isnan(ma20):
            supports.append((float(ma20), "MA20"))
        if not np.isnan(ma50):
            supports.append((float(ma50), "MA50"))

        vols = volume_levels(train)
        for idx, value in enumerate(vols[:3]):
            supports.append((value, f"Volume S{idx + 1}"))
        for idx, value in enumerate(vols[3:5]):
            resistances.append((value, f"Volume R{idx + 1}"))

        pivots = pivot_levels(train)
        supports.extend([(pivots["Pivot S1"], "Pivot S1"), (pivots["Pivot S2"], "Pivot S2")])
        resistances.extend([(pivots["Pivot R1"], "Pivot R1"), (pivots["Pivot R2"], "Pivot R2")])

        supports.append((swing_low, "Period Low"))
        resistances.append((swing_high, "Period High"))

        psych = round(current_price / 50) * 50 if current_price >= 50 else round(current_price, 1)
        supports.append((float(psych), "Psychological"))

        support_clusters = cluster_levels(supports, "support")
        resist_clusters = cluster_levels(resistances, "resistance")

        return AnalysisResult(
            ticker=ticker,
            train_start=train.index[0],
            train_end=train.index[-1],
            current_price=current_price,
            swing_high=swing_high,
            swing_low=swing_low,
            atr=atr_val,
            supports=support_clusters,
            resistances=resist_clusters,
        )
