#!/usr/bin/env python3
"""Diagnose which signal filters block entries."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from landing_analysis.analyzer import LandingAnalyzer
from landing_analysis.data_fetcher import fetch_stock_data
from landing_analysis.indicators import add_indicators
from landing_analysis.strategies import EQUIPMENT_TEMPLATE

TICKER = "AMAT"
LOOKBACK = 42
CFG = EQUIPMENT_TEMPLATE


def main():
    df = fetch_stock_data(TICKER, period="12mo")
    enriched = add_indicators(df)
    analyzer = LandingAnalyzer()

    counts = {
        "support_touch": 0,
        "rsi_ok": 0,
        "macd_ok": 0,
        "vol_shrink": 0,
        "candle": 0,
        "all_old": 0,
        "all_new": 0,
    }

    for i in range(LOOKBACK, len(enriched)):
        window = enriched.iloc[i - LOOKBACK : i]
        row = enriched.iloc[i]
        analysis = analyzer.analyze(window, TICKER, LOOKBACK)
        price = float(row["Close"])
        low = float(row["Low"])
        rsi = row.get("RSI", np.nan)
        if pd.isna(rsi):
            continue

        zones = sorted(
            [s for s in analysis.supports if s.strength >= 1 and s.price <= price * 1.05],
            key=lambda x: -x.strength,
        )[:4]

        for zone in zones:
            touch = low <= zone.price * (1 + CFG.tolerance)
            if not touch:
                continue
            counts["support_touch"] += 1
            if rsi < CFG.rsi_buy:
                counts["rsi_ok"] += 1
            macd_bull = bool(row.get("MACD_Bull", False)) or bool(row.get("MACD_Golden", False))
            if macd_bull:
                counts["macd_ok"] += 1
            if bool(row.get("Vol_Shrink", False)):
                counts["vol_shrink"] += 1
            if bool(row.get("Bullish_Candle", False)):
                counts["candle"] += 1
            if touch and rsi < CFG.rsi_buy:
                counts["all_old"] += 1
            if touch and rsi < CFG.rsi_buy and macd_bull and bool(row.get("Vol_Shrink", False)) and bool(row.get("Bullish_Candle", False)):
                counts["all_new"] += 1

    print(f"Diagnosis for {TICKER} (support touch events):")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
