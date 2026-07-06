#!/usr/bin/env python3
"""Tests for shared yfinance market data cache."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.yf_market_data import update_yf_cache


def make_ohlcv(start: date, days: int) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=days)
    close = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=idx,
    )


class YfMarketDataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    @patch("landing_analysis.yf_market_data.download_range")
    @patch("landing_analysis.yf_market_data.download_period")
    def test_initial_fetch_prefers_range(self, mock_period, mock_range):
        full = make_ohlcv(date(2023, 1, 1), 400)
        mock_range.return_value = full

        cached = update_yf_cache("AMAT", "12mo", data_dir=self.data_dir, lookback_days=120, as_of=date(2024, 7, 3))
        self.assertEqual(len(cached), 400)
        mock_range.assert_called()
        mock_period.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
