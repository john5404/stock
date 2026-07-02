#!/usr/bin/env python3
"""Compare RSI-only vs enhanced (MACD+volume+candlestick) backtests."""

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_fetcher import fetch_stock_data
from landing_analysis.strategies import (
    EQUIPMENT_TEMPLATE,
    HOT_TEMPLATE,
    StrategyConfig,
    TEMPLATE_TICKERS,
)


def legacy_config(template: StrategyConfig) -> StrategyConfig:
    """Same template but without MACD/volume/candlestick filters."""
    cfg = deepcopy(template)
    cfg.require_macd = False
    cfg.require_volume_shrink = False
    cfg.require_candlestick = False
    cfg.use_macd_exit = False
    cfg.volume_expand_breakout = False
    return cfg


def run_one(ticker: str, template: StrategyConfig, period: str = "12mo", lookback: int = 42):
    df = fetch_stock_data(ticker, period=period)
    engine = BacktestEngine(template)
    result = engine.run_rolling(df, ticker, lookback_days=lookback)
    return result


def fmt(result) -> str:
    n = len(result.trades)
    wr = result.win_rate
    cr = result.compound_return
    bh = result.buy_hold_pct
    return f"交易{n}筆 · 勝率{wr:.0f}% · 複利{cr:+.1f}% · B&H {bh:+.1f}%"


def main():
    groups = [
        ("設備股", EQUIPMENT_TEMPLATE, TEMPLATE_TICKERS["設備股"]),
        ("熱門股", HOT_TEMPLATE, TEMPLATE_TICKERS["熱門股"]),
    ]

    print("=" * 72)
    print("回測比較：舊策略(RSI+落點) vs 新策略(MACD/量縮/K棒 三選二 + MACD死叉出場)")
    print("模式: rolling · 視窗 42 日 · 資料 12mo")
    print("=" * 72)

    for group_name, template, tickers in groups:
        print(f"\n### {group_name}")
        print(f"{'Ticker':<8} {'舊策略':<42} {'新策略':<42}")
        print("-" * 92)
        for _label, ticker in tickers.items():
            try:
                old = run_one(ticker, legacy_config(template))
                new = run_one(ticker, template)
                print(f"{ticker:<8} {fmt(old):<42} {fmt(new):<42}")
            except Exception as e:
                print(f"{ticker:<8} ERROR: {e}")


if __name__ == "__main__":
    main()
