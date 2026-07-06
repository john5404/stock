#!/usr/bin/env python3
"""Unit tests for landing point analyzer."""

import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.analyzer import (
    LandingAnalyzer,
    cluster_levels,
    fibonacci_levels,
    volume_levels,
)
from landing_analysis.indicators import ensure_indicators


def make_ohlcv(start: date, days: int, *, base: float = 100.0) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=days)
    close = pd.Series(base + np.arange(len(idx)), index=idx, dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000 + np.arange(len(idx)) * 1000,
        },
        index=idx,
    )


class AnalyzerTests(unittest.TestCase):
    def test_fibonacci_levels_order(self):
        levels = fibonacci_levels(200, 100)
        self.assertGreater(levels["Fib 38.2%"], levels["Fib 61.8%"])

    def test_cluster_levels_merges_near_prices(self):
        levels = [(100.0, "A"), (101.0, "B"), (120.0, "C")]
        clusters = cluster_levels(levels, "support", tol=0.02)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].strength, 2)

    def test_volume_levels_returns_prices(self):
        df = make_ohlcv(date(2024, 1, 1), 40)
        prices = volume_levels(df, n_bins=10)
        self.assertGreater(len(prices), 0)

    def test_analyze_returns_support_and_resistance(self):
        df = ensure_indicators(make_ohlcv(date(2023, 1, 1), 120))
        result = LandingAnalyzer().analyze(df, "TEST", lookback_days=42)
        self.assertGreater(len(result.supports), 0)
        self.assertGreater(len(result.resistances), 0)
        self.assertEqual(result.ticker, "TEST")
        self.assertGreater(result.current_price, 0)

    def test_analyze_skips_recompute_when_enriched(self):
        raw = make_ohlcv(date(2023, 1, 1), 80)
        enriched = ensure_indicators(raw)
        result = LandingAnalyzer().analyze(enriched, "TEST", lookback_days=42)
        self.assertIn("MA20", enriched.columns)
        self.assertGreater(result.atr, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
