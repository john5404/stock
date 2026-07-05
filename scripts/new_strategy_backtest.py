#!/usr/bin/env python3
"""Run new-strategy backtests and print detailed performance."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_fetcher import fetch_stock_data
from landing_analysis.strategies import (
    EQUIPMENT_TEMPLATE,
    HOT_TEMPLATE,
    TEMPLATE_TICKERS,
    get_template,
)


def run_group(name: str, template, tickers: dict, period: str = "12mo", lookback: int = 42):
    print(f"\n{'='*70}")
    print(f"【{name}】新策略 · rolling · 視窗 {lookback} 日 · 資料 {period}")
    print(f"條件: {template.summary()}")
    print(f"{'='*70}")
    print(f"{'Ticker':<6} {'筆數':>4} {'勝率':>6} {'複利':>9} {'累加':>9} {'B&H':>9} {'vs B&H':>8}")
    print("-" * 70)

    rows = []
    for label, ticker in tickers.items():
        try:
            df = fetch_stock_data(ticker, period=period)
            result = BacktestEngine(template).run_rolling(df, ticker, lookback_days=lookback)
            n = len(result.trades)
            wr = result.win_rate
            cr = result.compound_return
            tr = result.total_pnl
            bh = result.buy_hold_pct
            diff = cr - bh
            rows.append((ticker, n, wr, cr, tr, bh, diff))
            print(f"{ticker:<6} {n:>4} {wr:>5.0f}% {cr:>+8.1f}% {tr:>+8.1f}% {bh:>+8.1f}% {diff:>+7.1f}%")
        except Exception as e:
            print(f"{ticker:<6} ERROR: {e}")

    if rows:
        avg_wr = sum(r[2] for r in rows) / len(rows)
        avg_cr = sum(r[3] for r in rows) / len(rows)
        avg_bh = sum(r[5] for r in rows) / len(rows)
        beat = sum(1 for r in rows if r[3] > r[5])
        print("-" * 70)
        print(f"{'平均':<6} {'':>4} {avg_wr:>5.0f}% {avg_cr:>+8.1f}% {'':>9} {avg_bh:>+8.1f}%")
        print(f"打贏 B&H: {beat}/{len(rows)} 檔")


def main():
    run_group("設備股", get_template("設備股"), TEMPLATE_TICKERS["設備股"])
    run_group("熱門股", get_template("熱門股"), TEMPLATE_TICKERS["熱門股"])

    print(f"\n{'='*70}")
    print("【新策略逐筆明細 · 熱門股】")
    print(f"{'='*70}")
    template = get_template("熱門股")
    for label, ticker in TEMPLATE_TICKERS["熱門股"].items():
        df = fetch_stock_data(ticker, period="12mo")
        result = BacktestEngine(template).run_rolling(df, ticker, lookback_days=42)
        if not result.trades:
            print(f"\n{ticker}: 無交易")
            continue
        print(f"\n{ticker} ({len(result.trades)} 筆 · 複利 {result.compound_return:+.1f}% · B&H {result.buy_hold_pct:+.1f}%)")
        for i, t in enumerate(result.trades, 1):
            ed = t.entry_date.strftime("%Y-%m-%d")
            xd = t.exit_date.strftime("%Y-%m-%d")
            print(f"  {i}. {ed} → {xd}  {t.pnl_pct:+.1f}%  [{t.reason}]  持有{t.hold_days}天")


if __name__ == "__main__":
    main()
