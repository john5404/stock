#!/usr/bin/env python3
"""Tests for local OHLCV cache in stock/data."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_store import (
    cache_path,
    get_stock_data,
    load_cache,
    merge_ohlcv,
    save_cache,
    slice_for_period,
    update_cache,
)
from landing_analysis.strategies import get_template


def make_ohlcv(start: date, days: int) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=days)
    close = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    df = pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=idx,
    )
    df.index = df.index.normalize()
    return df


class DataStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_and_load_roundtrip(self):
        df = make_ohlcv(date(2024, 1, 1), 30)
        path = cache_path(self.data_dir, "2330.TW")
        save_cache(path, df)
        loaded = load_cache(path)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(len(loaded), 30)
        self.assertListEqual(list(loaded.columns), ["Open", "High", "Low", "Close", "Volume"])

    def test_merge_deduplicates_dates(self):
        a = make_ohlcv(date(2024, 1, 1), 5)
        b = make_ohlcv(date(2024, 1, 4), 5)
        merged = merge_ohlcv(a, b)
        self.assertEqual(len(merged), 8)

    @patch("landing_analysis.yf_market_data.download_range")
    @patch("landing_analysis.yf_market_data.download_period")
    def test_initial_fetch_writes_cache_tw(self, mock_period, mock_range):
        full = make_ohlcv(date(2023, 1, 1), 400)
        mock_range.return_value = full

        cached = update_cache("2330.TW", "12mo", data_dir=self.data_dir, lookback_days=120, as_of=date(2024, 7, 3))
        path = cache_path(self.data_dir, "2330.TW")
        self.assertTrue(path.exists())
        self.assertEqual(len(cached), 400)
        mock_range.assert_called()
        mock_period.assert_not_called()

    @patch("landing_analysis.yf_market_data.download_range")
    @patch("landing_analysis.yf_market_data.download_period")
    def test_incremental_fetch_only_gets_new_dates_tw(self, mock_period, mock_range):
        full = make_ohlcv(date(2022, 1, 1), 700)
        existing = full[full.index <= pd.Timestamp("2024-07-03")]
        path = cache_path(self.data_dir, "2330.TW")
        save_cache(path, existing)

        new_day = make_ohlcv(date(2024, 7, 4), 1)

        def range_side_effect(ticker, start, end=None):
            if start == date(2024, 7, 4):
                return new_day
            return pd.DataFrame()

        mock_range.side_effect = range_side_effect

        cached = update_cache("2330.TW", "12mo", data_dir=self.data_dir, lookback_days=120, as_of=date(2024, 7, 4))
        mock_period.assert_not_called()
        incremental_calls = [
            call for call in mock_range.call_args_list if call.args[1] == date(2024, 7, 4)
        ]
        self.assertTrue(incremental_calls, "expected incremental download on 2024-07-04")
        self.assertEqual(len(cached), len(existing) + 1)

    def test_slice_supports_lookback_45_60_120(self):
        df = make_ohlcv(date(2022, 1, 1), 700)
        for lookback in (45, 60, 120):
            sliced = slice_for_period(df, "12mo", lookback)
            self.assertGreaterEqual(len(sliced), lookback + 5)

    def test_get_stock_data_reads_from_cache_file_tw(self):
        full = make_ohlcv(date(2020, 1, 1), 1100)
        as_of = full.index.max().date()
        path = cache_path(self.data_dir, "2330.TW")
        save_cache(path, full)

        with patch("landing_analysis.yf_market_data.download_range") as mock_range, patch(
            "landing_analysis.yf_market_data.download_period"
        ) as mock_period:
            out = get_stock_data("2330.TW", "12mo", data_dir=self.data_dir, lookback_days=120, as_of=as_of)
            self.assertGreaterEqual(len(out), 125)
            mock_range.assert_not_called()
            mock_period.assert_not_called()

        out2 = get_stock_data("2330.TW", "12mo", data_dir=self.data_dir, lookback_days=120, as_of=as_of)
        self.assertEqual(len(out), len(out2))

    @patch("landing_analysis.yf_market_data.download_period")
    def test_backtest_compatible_with_cached_data_us(self, mock_period):
        full = make_ohlcv(date(2022, 1, 1), 700)
        mock_period.return_value = full
        engine = BacktestEngine(get_template("設備股"))

        for lookback in (45, 60, 120):
            df = get_stock_data("AMAT", "12mo", data_dir=self.data_dir, lookback_days=lookback, as_of=date(2024, 7, 3))
            rolling = engine.run_rolling(df, "AMAT", lookback_days=lookback)
            fixed = engine.run_fixed(df, "AMAT", lookback_days=lookback)
            self.assertEqual(rolling.mode, "rolling")
            self.assertEqual(fixed.mode, "fixed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
