#!/usr/bin/env python3
"""Tests for Scheme C landing charts."""

import sys
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.analyzer import LandingAnalyzer
from landing_analysis.data_store import get_stock_data
from landing_analysis.scheme_c_charts import (
    decimals_for_price_span,
    draw_empty_scheme_c,
    draw_institutional_chart,
    draw_scheme_c,
    format_price_value,
    volume_profile_data,
)


COLORS = {
    "surface": "#080a0d",
    "surface_elevated": "#0d1014",
    "chart_bg": "#050608",
    "border": "#171c24",
    "grid": "#141820",
    "text": "#9aa3ad",
    "muted": "#5f6770",
    "accent": "#4a7fa8",
    "accent_dark": "#3d6d92",
    "success": "#3d8f7a",
    "danger": "#b86a62",
    "warning": "#b8894a",
}


class SchemeCChartTests(unittest.TestCase):
    def test_volume_profile_data(self):
        import pandas as pd

        idx = pd.bdate_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {"Close": range(100, 130), "Volume": [1000 + i * 10 for i in range(30)]},
            index=idx,
        )
        centers, profile = volume_profile_data(df, n_bins=10)
        self.assertEqual(len(centers), 10)
        self.assertEqual(len(profile), 10)
        self.assertGreater(profile.sum(), 0)

    def test_draw_scheme_c_with_analysis(self):
        df = get_stock_data("AAPL", "6mo", lookback_days=60)
        analysis = LandingAnalyzer().analyze(df, "AAPL", 42)
        fig = plt.figure(figsize=(10, 7))
        grid = fig.add_gridspec(3, 2, width_ratios=[2.4, 1], height_ratios=[1.1, 1.0, 0.75])
        ax_price = fig.add_subplot(grid[0:2, 0])
        ax_ladder = fig.add_subplot(grid[0, 1])
        ax_vp = fig.add_subplot(grid[1, 1])
        ax_inst = fig.add_subplot(grid[2, :])
        draw_scheme_c(
            fig,
            ax_price,
            ax_ladder,
            ax_vp,
            ax_inst,
            df,
            analysis,
            ticker="AAPL",
            strategy_name="設備股",
            colors=COLORS,
            lookback_days=42,
            is_tw=False,
        )
        self.assertTrue(ax_price.lines or ax_price.collections)
        plt.close(fig)

    def test_draw_institutional_chart_tw(self):
        import pandas as pd

        idx = pd.bdate_range("2024-01-01", periods=20)
        inst = pd.DataFrame(
            {
                "foreign_net": [1000, -500, 200] * 6 + [100, 200],
                "trust_net": [200, 100, -50] * 6 + [10, 20],
                "dealer_net": [-100, 50, 30] * 6 + [5, 8],
                "total_net": [1100, -350, 180] * 6 + [115, 228],
                "foreign_buy": 1,
                "foreign_sell": 1,
                "trust_buy": 1,
                "trust_sell": 1,
                "dealer_buy": 1,
                "dealer_sell": 1,
            },
            index=idx,
        )
        fig, ax = plt.subplots(figsize=(8, 2.5))
        draw_institutional_chart(ax, inst, colors=COLORS, lookback_days=20, ticker="2330.TW", is_tw=True)
        self.assertTrue(ax.patches or ax.lines)
        plt.close(fig)

    def test_price_format_precision(self):
        self.assertEqual(decimals_for_price_span(800), 0)
        self.assertEqual(decimals_for_price_span(50), 2)
        self.assertEqual(decimals_for_price_span(2), 4)
        self.assertIn(".25", format_price_value(12.25, 10))

    def test_draw_empty_scheme_c(self):
        fig = plt.figure(figsize=(10, 7))
        grid = fig.add_gridspec(3, 2, width_ratios=[2.4, 1], height_ratios=[1.1, 1.0, 0.75])
        ax_price = fig.add_subplot(grid[0:2, 0])
        ax_ladder = fig.add_subplot(grid[0, 1])
        ax_vp = fig.add_subplot(grid[1, 1])
        ax_inst = fig.add_subplot(grid[2, :])
        draw_empty_scheme_c(fig, ax_price, ax_ladder, ax_vp, ax_inst, COLORS)
        plt.close(fig)


if __name__ == "__main__":
    unittest.main(verbosity=2)
