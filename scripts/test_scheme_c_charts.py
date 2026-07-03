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
from landing_analysis.scheme_c_charts import draw_empty_scheme_c, draw_scheme_c, volume_profile_data


COLORS = {
    "surface": "#131a24",
    "surface_elevated": "#1a2332",
    "chart_bg": "#0d1117",
    "border": "#2d3b4f",
    "grid": "#21262d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#3d8bfd",
    "accent_dark": "#2f6fd6",
    "success": "#26a69a",
    "danger": "#ef5350",
    "warning": "#ffa726",
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
        fig = plt.figure(figsize=(10, 6))
        grid = fig.add_gridspec(2, 2, width_ratios=[2.4, 1], height_ratios=[1, 1])
        ax_price = fig.add_subplot(grid[:, 0])
        ax_ladder = fig.add_subplot(grid[0, 1])
        ax_vp = fig.add_subplot(grid[1, 1])
        draw_scheme_c(
            fig,
            ax_price,
            ax_ladder,
            ax_vp,
            df,
            analysis,
            ticker="AAPL",
            strategy_name="設備股",
            colors=COLORS,
            lookback_days=42,
        )
        self.assertTrue(ax_price.lines or ax_price.collections)
        plt.close(fig)

    def test_draw_empty_scheme_c(self):
        fig, axes = plt.subplots(1, 3, figsize=(9, 3))
        draw_empty_scheme_c(fig, axes[0], axes[1], axes[2], COLORS)
        plt.close(fig)


if __name__ == "__main__":
    unittest.main(verbosity=2)
