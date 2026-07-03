#!/usr/bin/env python3
"""Unit tests for backtest engine."""

import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.backtest import BacktestEngine
from landing_analysis.indicators import ensure_indicators
from landing_analysis.strategies import get_template


def make_ohlcv(start: date, days: int, *, base: float = 100.0) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=days)
    close = pd.Series(base + np.sin(np.arange(len(idx)) / 8) * 5 + np.arange(len(idx)) * 0.1, index=idx)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.2,
            "Low": close - 1.2,
            "Close": close,
            "Volume": 1_000_000 + np.arange(len(idx)) * 500,
        },
        index=idx,
    )


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.df = ensure_indicators(make_ohlcv(date(2022, 1, 1), 180))
        self.engine = BacktestEngine(get_template("設備股"))

    def test_fixed_mode_result_shape(self):
        result = self.engine.run_fixed(self.df, "TEST", lookback_days=45)
        self.assertEqual(result.mode, "fixed")
        self.assertEqual(result.strategy_name, "設備股")

    def test_rolling_mode_result_shape(self):
        result = self.engine.run_rolling(self.df, "TEST", lookback_days=45)
        self.assertEqual(result.mode, "rolling")

    def test_compound_return_with_no_trades(self):
        result = self.engine.run_fixed(self.df, "TEST", lookback_days=45)
        self.assertEqual(result.compound_return, 0.0)

    def test_enriched_df_not_recomputed(self):
        result = self.engine.run_rolling(self.df, "TEST", lookback_days=45)
        self.assertIsNotNone(result)

    def test_insufficient_data_raises(self):
        small = ensure_indicators(make_ohlcv(date(2024, 1, 1), 30))
        with self.assertRaises(ValueError):
            self.engine.run_fixed(small, "TEST", lookback_days=45)


if __name__ == "__main__":
    unittest.main(verbosity=2)
