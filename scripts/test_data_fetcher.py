#!/usr/bin/env python3
"""Unit tests for market detection and ticker normalization."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.data_fetcher import detect_market_from_input, normalize_ticker_input


class DataFetcherTests(unittest.TestCase):
    def test_detect_tw_from_chinese(self):
        self.assertEqual(detect_market_from_input("台積"), "台股")
        self.assertEqual(detect_market_from_input("台積電 (2330)"), "台股")

    def test_detect_tw_from_digits(self):
        self.assertEqual(detect_market_from_input("2330"), "台股")
        self.assertEqual(detect_market_from_input("2454"), "台股")

    def test_detect_us_from_english(self):
        self.assertEqual(detect_market_from_input("AAPL"), "美股")
        self.assertEqual(detect_market_from_input("nvda"), "美股")
        self.assertEqual(detect_market_from_input("MU"), "美股")

    def test_detect_tw_from_suffix(self):
        self.assertEqual(detect_market_from_input("2330.TW"), "台股")
        self.assertEqual(detect_market_from_input("8299.TWO"), "台股")

    def test_detect_korean_digits_as_us(self):
        self.assertEqual(detect_market_from_input("005930"), "美股")
        self.assertEqual(detect_market_from_input("000660"), "美股")
        self.assertEqual(detect_market_from_input("005930.KS"), "美股")

    def test_normalize_tw_digits(self):
        self.assertEqual(normalize_ticker_input("2330"), "2330.TW")
        self.assertEqual(normalize_ticker_input("2330", "台股"), "2330.TW")

    def test_normalize_us_symbol(self):
        self.assertEqual(normalize_ticker_input("AAPL"), "AAPL")
        self.assertEqual(normalize_ticker_input("aapl"), "AAPL")

    def test_normalize_korean_digits(self):
        self.assertEqual(normalize_ticker_input("005930"), "005930.KS")
        self.assertEqual(normalize_ticker_input("005930.KS"), "005930.KS")


if __name__ == "__main__":
    unittest.main()
