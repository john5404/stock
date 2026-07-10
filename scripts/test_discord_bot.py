#!/usr/bin/env python3
"""Unit tests for the Discord bot service layer, chart rendering and commands."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from landing_analysis import bot_service
from landing_analysis.analyzer import LandingAnalyzer
from landing_analysis.bot_service import (
    DEFAULT_LOOKBACK,
    DEFAULT_PERIOD,
    MAX_LOOKBACK,
    MIN_LOOKBACK,
    AnalysisBundle,
    Quote,
    TickerError,
    analyze_ticker,
    get_quote,
    resolve_ticker,
    top_levels,
)
from landing_analysis.indicators import ensure_indicators

try:
    import discord  # noqa: F401

    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False


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


def make_bundle(symbol: str = "TEST", *, is_tw: bool = False) -> AnalysisBundle:
    df = ensure_indicators(make_ohlcv(date(2023, 1, 1), 160))
    analysis = LandingAnalyzer().analyze(df, symbol, DEFAULT_LOOKBACK)
    return AnalysisBundle(
        symbol=symbol,
        market="台股" if is_tw else "美股",
        is_tw=is_tw,
        period=DEFAULT_PERIOD,
        lookback=DEFAULT_LOOKBACK,
        df=df,
        analysis=analysis,
    )


class ResolveTickerTests(unittest.TestCase):
    def test_us_symbol(self):
        self.assertEqual(resolve_ticker("mu"), ("MU", "美股"))

    def test_tw_digits(self):
        self.assertEqual(resolve_ticker("2330"), ("2330.TW", "台股"))

    def test_tw_suffix_preserved(self):
        self.assertEqual(resolve_ticker("8299.TWO"), ("8299.TWO", "台股"))

    def test_blank_raises(self):
        with self.assertRaises(TickerError):
            resolve_ticker("   ")


class NormalizeTests(unittest.TestCase):
    def test_period_default_and_invalid(self):
        self.assertEqual(bot_service._normalize_period(None), DEFAULT_PERIOD)
        self.assertEqual(bot_service._normalize_period("1d"), DEFAULT_PERIOD)
        self.assertEqual(bot_service._normalize_period("2Y"), "2y")

    def test_lookback_clamped(self):
        self.assertEqual(bot_service._normalize_lookback(None), DEFAULT_LOOKBACK)
        self.assertEqual(bot_service._normalize_lookback(5), MIN_LOOKBACK)
        self.assertEqual(bot_service._normalize_lookback(9999), MAX_LOOKBACK)
        self.assertEqual(bot_service._normalize_lookback(60), 60)


class QuoteTests(unittest.TestCase):
    def test_get_quote_computes_change(self):
        df = make_ohlcv(date(2024, 1, 1), 30)
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=df) as fetch:
            quote = get_quote("MU")
        fetch.assert_called_once()
        self.assertEqual(quote.symbol, "MU")
        self.assertEqual(quote.market, "美股")
        self.assertAlmostEqual(quote.price, float(df["Close"].iloc[-1]))
        self.assertAlmostEqual(quote.change, 1.0)
        self.assertIsNotNone(quote.change_pct)

    def test_get_quote_empty_raises(self):
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=pd.DataFrame()):
            with self.assertRaises(TickerError):
                get_quote("MU")

    def test_quote_change_none_without_prev(self):
        q = Quote(symbol="X", market="美股", price=10.0, prev_close=None, as_of=pd.Timestamp("2024-01-01"))
        self.assertIsNone(q.change)
        self.assertIsNone(q.change_pct)


class AnalyzeTickerTests(unittest.TestCase):
    def test_analyze_returns_bundle(self):
        df = make_ohlcv(date(2023, 1, 1), 160)
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=df):
            bundle = analyze_ticker("MU", period="2y", lookback=50)
        self.assertEqual(bundle.symbol, "MU")
        self.assertEqual(bundle.period, "2y")
        self.assertEqual(bundle.lookback, 50)
        self.assertFalse(bundle.is_tw)
        self.assertGreater(len(bundle.analysis.supports), 0)
        self.assertIsNone(bundle.institutional)

    def test_analyze_insufficient_rows_raises(self):
        df = make_ohlcv(date(2024, 1, 1), 10)
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=df):
            with self.assertRaises(TickerError):
                analyze_ticker("MU")

    def test_analyze_empty_raises(self):
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=pd.DataFrame()):
            with self.assertRaises(TickerError):
                analyze_ticker("MU")

    def test_institutional_only_for_tw(self):
        df = make_ohlcv(date(2023, 1, 1), 160)
        inst = pd.DataFrame({"total_net": [1, 2, 3]})
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=df):
            with mock.patch.object(bot_service, "fetch_tw_institutional_data", return_value=inst) as inst_fetch:
                us_bundle = analyze_ticker("MU", with_institutional=True)
                self.assertIsNone(us_bundle.institutional)
                inst_fetch.assert_not_called()

                tw_bundle = analyze_ticker("2330", with_institutional=True)
                self.assertIsNotNone(tw_bundle.institutional)
                inst_fetch.assert_called_once()

    def test_institutional_failure_is_swallowed(self):
        df = make_ohlcv(date(2023, 1, 1), 160)
        with mock.patch.object(bot_service, "fetch_stock_data", return_value=df):
            with mock.patch.object(
                bot_service, "fetch_tw_institutional_data", side_effect=RuntimeError("quota")
            ):
                bundle = analyze_ticker("2330", with_institutional=True)
        self.assertIsNone(bundle.institutional)


class TopLevelsTests(unittest.TestCase):
    def test_supports_below_and_resistances_above(self):
        bundle = make_bundle()
        current = bundle.analysis.current_price
        supports = top_levels(bundle.analysis, "support", 3)
        resistances = top_levels(bundle.analysis, "resistance", 3)
        self.assertLessEqual(len(supports), 3)
        self.assertLessEqual(len(resistances), 3)
        if supports:
            self.assertTrue(all(lv.price <= current for lv in supports))
        if resistances:
            self.assertTrue(all(lv.price >= current for lv in resistances))


class ChartRenderTests(unittest.TestCase):
    def test_render_png_bytes(self):
        from landing_analysis.bot_charts import render_scheme_c_png

        png = render_scheme_c_png(make_bundle())
        self.assertGreater(len(png), 1000)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")


class _FakeInteraction:
    def __init__(self):
        self.response = mock.MagicMock()
        self.response.defer = mock.AsyncMock()
        self.followup = mock.MagicMock()
        self.followup.send = mock.AsyncMock()

    @property
    def sent_kwargs(self) -> dict:
        self.followup.send.assert_called_once()
        return self.followup.send.call_args.kwargs


@unittest.skipUnless(HAS_DISCORD, "discord.py not installed")
class CommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import discord_bot

        self.bot = discord_bot

    async def test_quote_command_success(self):
        quote = Quote(symbol="MU", market="美股", price=100.0, prev_close=98.0, as_of=pd.Timestamp("2024-01-02"))
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "get_quote", return_value=quote):
            await self.bot.quote_command.callback(itx, "MU")
        itx.response.defer.assert_awaited_once()
        embed = itx.sent_kwargs["embed"]
        self.assertIn("MU", embed.title)

    async def test_quote_command_ticker_error(self):
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "get_quote", side_effect=TickerError("找不到標的")):
            await self.bot.quote_command.callback(itx, "ZZZZ")
        embed = itx.sent_kwargs["embed"]
        self.assertIn("找不到標的", embed.description)

    async def test_quote_command_unexpected_error(self):
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "get_quote", side_effect=RuntimeError("boom")):
            await self.bot.quote_command.callback(itx, "MU")
        embed = itx.sent_kwargs["embed"]
        self.assertIn("查詢失敗", embed.description)

    async def test_analyze_command_success(self):
        bundle = make_bundle("MU")
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "analyze_ticker", return_value=bundle) as az:
            await self.bot.analyze_command.callback(itx, "MU", None, None)
        az.assert_called_once()
        embed = itx.sent_kwargs["embed"]
        self.assertIn("MU", embed.title)
        field_names = [f.name for f in embed.fields]
        self.assertIn("現價", field_names)

    async def test_analyze_command_error(self):
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "analyze_ticker", side_effect=TickerError("資料不足")):
            await self.bot.analyze_command.callback(itx, "MU", None, None)
        embed = itx.sent_kwargs["embed"]
        self.assertIn("資料不足", embed.description)

    async def test_chart_command_attaches_png(self):
        bundle = make_bundle("MU")
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "analyze_ticker", return_value=bundle):
            with mock.patch.object(self.bot, "render_scheme_c_png", return_value=b"\x89PNG\r\n\x1a\nfake"):
                await self.bot.chart_command.callback(itx, "MU", None, None, False)
        kwargs = itx.sent_kwargs
        self.assertIn("embed", kwargs)
        self.assertIn("file", kwargs)

    async def test_chart_command_tw_missing_institutional_footer(self):
        bundle = make_bundle("2330", is_tw=True)
        bundle.institutional = None
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "analyze_ticker", return_value=bundle):
            with mock.patch.object(self.bot, "render_scheme_c_png", return_value=b"\x89PNG\r\n\x1a\nfake"):
                await self.bot.chart_command.callback(itx, "2330", None, None, True)
        embed = itx.sent_kwargs["embed"]
        self.assertIsNotNone(embed.footer.text)
        self.assertIn("FINMIND", embed.footer.text)

    async def test_chart_command_render_error(self):
        bundle = make_bundle("MU")
        itx = _FakeInteraction()
        with mock.patch.object(self.bot, "analyze_ticker", return_value=bundle):
            with mock.patch.object(self.bot, "render_scheme_c_png", side_effect=RuntimeError("draw")):
                await self.bot.chart_command.callback(itx, "MU", None, None, False)
        embed = itx.sent_kwargs["embed"]
        self.assertIn("繪圖失敗", embed.description)


if __name__ == "__main__":
    unittest.main(verbosity=2)
