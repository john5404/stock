#!/usr/bin/env python3
"""Unit tests for portfolio allocation store."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.portfolio_store import (
    PortfolioRow,
    PortfolioSection,
    calc_section,
    default_portfolio_path,
    load_portfolio,
    parse_markdown,
    portfolio_pie_slices,
    portfolio_market_slices,
    position_pie_slices,
    save_portfolio,
    to_markdown,
)


class PortfolioStoreTests(unittest.TestCase):
    def test_parse_sample_markdown(self):
        md = default_portfolio_path()
        if not md.exists():
            self.skipTest("portfolio markdown missing")
        sections, budget = load_portfolio(md)
        self.assertGreaterEqual(len(sections), 1)
        self.assertGreater(sum(len(sec.rows) for sec in sections), 0)

    def test_roundtrip_markdown(self):
        sections = [
            PortfolioSection(
                id="tw",
                title="TW Stocks",
                currency="TWD",
                has_rate=False,
                rows=[PortfolioRow(name="2330", note="台積電", position="long", shares=10, cost=100)],
            ),
            PortfolioSection(
                id="us",
                title="US Stocks",
                currency="USD",
                has_rate=True,
                rate=32.0,
                rows=[PortfolioRow(name="AAPL", position="long", shares=2, cost=150)],
            ),
        ]
        md = to_markdown(sections, budget=1_000_000)
        parsed = parse_markdown(md)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].rows[0].name, "2330")
        self.assertEqual(parsed[1].rows[0].name, "AAPL")

    def test_calc_section_weights(self):
        sec = PortfolioSection(
            id="tw",
            title="TW Stocks",
            currency="TWD",
            has_rate=False,
            rows=[
                PortfolioRow(name="A", shares=10, cost=100),
                PortfolioRow(name="B", shares=5, cost=200),
            ],
        )
        calc = calc_section(sec)
        self.assertAlmostEqual(calc.total, 2000)
        self.assertAlmostEqual(sum(item.weight for item in calc.items), 100.0)

    def test_portfolio_pie_slices(self):
        sections = [
            PortfolioSection(
                id="tw",
                title="TW Stocks",
                currency="TWD",
                has_rate=False,
                rows=[
                    PortfolioRow(name="A", shares=10, cost=100),
                    PortfolioRow(name="B", shares=1, cost=50),
                ],
            ),
            PortfolioSection(
                id="us",
                title="US Stocks",
                currency="USD",
                has_rate=True,
                rate=30.0,
                rows=[PortfolioRow(name="C", shares=2, cost=100)],
            ),
        ]
        slices = portfolio_pie_slices(sections, min_pct=30.0)
        self.assertEqual(len(slices), 2)
        self.assertEqual(slices[0].label, "C")
        self.assertEqual(slices[1].label, "其他")
        self.assertAlmostEqual(sum(s.pct for s in slices), 100.0)

    def test_market_and_position_pie_slices(self):
        sections = [
            PortfolioSection(
                id="tw",
                title="TW Stocks",
                currency="TWD",
                has_rate=False,
                rows=[
                    PortfolioRow(name="2330", shares=10, cost=100, position="long"),
                    PortfolioRow(name="0050", shares=5, cost=50, position="short"),
                ],
            ),
            PortfolioSection(
                id="us",
                title="US Stocks",
                currency="USD",
                has_rate=True,
                rate=30.0,
                rows=[PortfolioRow(name="AAPL", shares=2, cost=100, position="long")],
            ),
        ]
        market_slices = portfolio_market_slices(sections)
        self.assertEqual(len(market_slices), 2)
        self.assertAlmostEqual(sum(s.pct for s in market_slices), 100.0)

        tw_pos = position_pie_slices(sections[0])
        self.assertEqual(len(tw_pos), 2)
        self.assertAlmostEqual(sum(s.pct for s in tw_pos), 100.0)

        us_pos = position_pie_slices(sections[1])
        self.assertEqual(len(us_pos), 1)
        self.assertEqual(us_pos[0].label, "長線")

    def test_save_and_load(self):
        path = ROOT / "data" / "portfolio" / "_test_portfolio.md"
        sections = [
            PortfolioSection(
                id="tw",
                title="TW Stocks",
                currency="TWD",
                has_rate=False,
                rows=[PortfolioRow(name="0050", shares=100, cost=50)],
            )
        ]
        save_portfolio(path, sections, budget=500000)
        loaded, budget = load_portfolio(path)
        self.assertEqual(budget, 500000)
        self.assertEqual(loaded[0].rows[0].name, "0050")
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
