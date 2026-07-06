#!/usr/bin/env python3
"""Tests for Taiwan institutional data cache (FinMind)."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.tw_institutional_store import (
    institutional_cache_path,
    load_institutional_cache,
    merge_institutional,
    normalize_institutional,
    save_institutional_cache,
    tw_stock_id,
    update_institutional_cache,
)
from landing_analysis.tw_market_data import is_tw_ticker


def make_wide_row(d: date, foreign_net: float, trust_net: float, dealer_net: float) -> dict:
    return {
        "date": d.isoformat(),
        "stock_id": "2330",
        "Foreign_Investor_buy": max(foreign_net, 0),
        "Foreign_Investor_sell": max(-foreign_net, 0),
        "Foreign_Dealer_Self_buy": 0,
        "Foreign_Dealer_Self_sell": 0,
        "Investment_Trust_buy": max(trust_net, 0),
        "Investment_Trust_sell": max(-trust_net, 0),
        "Dealer_buy": max(dealer_net, 0),
        "Dealer_sell": max(-dealer_net, 0),
        "Dealer_self_buy": 0,
        "Dealer_self_sell": 0,
        "Dealer_Hedging_buy": 0,
        "Dealer_Hedging_sell": 0,
    }


class TwInstitutionalStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tw_stock_id_and_ticker_check(self):
        self.assertEqual(tw_stock_id("2330.TW"), "2330")
        self.assertEqual(tw_stock_id("8299.TWO"), "8299")
        self.assertTrue(is_tw_ticker("2330.TW"))
        self.assertFalse(is_tw_ticker("AAPL"))

    def test_normalize_institutional(self):
        raw = pd.DataFrame(
            [
                make_wide_row(date(2024, 7, 1), 1000, 200, -50),
                make_wide_row(date(2024, 7, 2), -300, 100, 20),
            ]
        )
        out = normalize_institutional(raw)
        self.assertEqual(out.loc[pd.Timestamp("2024-07-01"), "total_net"], 1150)
        self.assertEqual(out.loc[pd.Timestamp("2024-07-02"), "total_net"], -180)

    def test_save_load_roundtrip(self):
        raw = pd.DataFrame([make_wide_row(date(2024, 7, 1), 500, 100, 10)])
        norm = normalize_institutional(raw)
        path = institutional_cache_path(self.data_dir, "2330")
        save_institutional_cache(path, norm)
        loaded = load_institutional_cache(path)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(len(loaded), 1)
        self.assertAlmostEqual(float(loaded["total_net"].iloc[0]), 610.0)

    def test_merge_deduplicates_dates(self):
        a = normalize_institutional(pd.DataFrame([make_wide_row(date(2024, 7, 1), 1, 2, 3)]))
        b = normalize_institutional(pd.DataFrame([make_wide_row(date(2024, 7, 1), 9, 9, 9)]))
        merged = merge_institutional(a, b)
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(float(merged["total_net"].iloc[0]), 27.0)

    @patch("landing_analysis.tw_institutional_store.download_institutional_range")
    def test_update_cache_writes_file(self, mock_download):
        rows = [make_wide_row(date(2024, 7, d), d, d * 10, 0) for d in range(1, 6)]
        mock_download.return_value = normalize_institutional(pd.DataFrame(rows))

        cached = update_institutional_cache(
            "2330.TW",
            "12mo",
            data_dir=self.data_dir,
            lookback_days=60,
            as_of=date(2024, 7, 5),
            token="test-token",
        )
        path = institutional_cache_path(self.data_dir, "2330")
        self.assertTrue(path.exists())
        self.assertEqual(len(cached), 5)
        mock_download.assert_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
