#!/usr/bin/env python3
"""Sweep strategy variants on MU & SNDK to find viable configs."""

import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_fetcher import fetch_stock_data
from landing_analysis.strategies import HOT_TEMPLATE, StrategyConfig

TICKERS = ["MU", "SNDK"]
PERIOD = "12mo"
LOOKBACK = 42

# Base = 熱門股模板參數
BASE = deepcopy(HOT_TEMPLATE)


def cfg(name: str, **kwargs) -> StrategyConfig:
    c = deepcopy(BASE)
    c.name = name
    c.description = name
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


VARIANTS: list[StrategyConfig] = [
    cfg("01-舊策略(RSI+落點)",
        require_macd=False, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, volume_expand_breakout=False, signal_confirm_min=0),

    cfg("02-新策略全開(現行)",
        require_macd=True, require_volume_shrink=True, require_candlestick=True,
        use_macd_exit=True, volume_expand_breakout=True, signal_confirm_min=2),

    cfg("03-三選二進場·無MACD出場",
        require_macd=True, require_volume_shrink=True, require_candlestick=True,
        use_macd_exit=False, volume_expand_breakout=True, signal_confirm_min=2),

    cfg("04-僅MACD進場·無MACD出場",
        require_macd=True, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, volume_expand_breakout=True, signal_confirm_min=0),

    cfg("05-MACD+量縮·無MACD出場",
        require_macd=True, require_volume_shrink=True, require_candlestick=False,
        use_macd_exit=False, volume_expand_breakout=True, signal_confirm_min=0),

    cfg("06-三選二·移動停利25%",
        trail_pct=0.25, use_macd_exit=False, signal_confirm_min=2),

    cfg("07-三選二·移動停利30%",
        trail_pct=0.30, use_macd_exit=False, signal_confirm_min=2),

    cfg("08-三選二·停損15%·移動25%",
        stop_loss_pct=0.15, trail_pct=0.25, use_macd_exit=False, signal_confirm_min=2),

    cfg("09-僅MACD進場·移動停利30%",
        require_macd=True, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, trail_pct=0.30, signal_confirm_min=0),

    cfg("10-舊策略·移動停利25%",
        require_macd=False, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, trail_pct=0.25),

    cfg("11-舊策略·移動停利30%",
        require_macd=False, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, trail_pct=0.30),

    cfg("12-舊策略·無MA50·移動30%",
        require_macd=False, trend_ma_filter=False, use_macd_exit=False, trail_pct=0.30),

    cfg("13-突破導向·MACD+放量",
        require_macd=True, require_volume_shrink=False, require_candlestick=False,
        use_macd_exit=False, breakout_buy=True, trend_ma_filter=True,
        volume_expand_breakout=True, signal_confirm_min=0, rsi_buy=60),

    cfg("14-三選二·RSI65進場·移動30%",
        rsi_buy=65, trail_pct=0.30, use_macd_exit=False, signal_confirm_min=2),

    cfg("15-三選二·一選一(寬鬆)",
        signal_confirm_min=1, use_macd_exit=False, trail_pct=0.25),
]


def run_all():
    cache: dict[str, object] = {}
    for t in TICKERS:
        cache[t] = fetch_stock_data(t, period=PERIOD)

    results = []
    for variant in VARIANTS:
        for ticker in TICKERS:
            df = cache[ticker]
            r = BacktestEngine(variant).run_rolling(df, ticker, lookback_days=LOOKBACK)
            results.append({
                "strategy": variant.name,
                "ticker": ticker,
                "trades": len(r.trades),
                "win_rate": r.win_rate,
                "compound": r.compound_return,
                "buy_hold": r.buy_hold_pct,
                "vs_bh": r.compound_return - r.buy_hold_pct,
                "bh_ratio": (r.compound_return / r.buy_hold_pct * 100) if r.buy_hold_pct else 0,
            })

    return results


def print_report(results):
    bh = {t: next(r["buy_hold"] for r in results if r["ticker"] == t) for t in TICKERS}
    print("=" * 88)
    print(f"MU / SNDK 策略掃描 · rolling {LOOKBACK}d · {PERIOD}")
    print(f"B&H 基準: MU {bh['MU']:+.1f}% · SNDK {bh['SNDK']:+.1f}%")
    print("=" * 88)

    strategies = sorted({r["strategy"] for r in results}, key=lambda s: s)
    print(f"\n{'策略':<28} {'MU複利':>9} {'MU筆':>5} {'MU勝':>5} {'SNDK複利':>10} {'SNDK筆':>6} {'SNDK勝':>6} {'平均vsB&H':>10}")
    print("-" * 88)

    ranked = []
    for s in strategies:
        mu = next(r for r in results if r["strategy"] == s and r["ticker"] == "MU")
        sn = next(r for r in results if r["strategy"] == s and r["ticker"] == "SNDK")
        avg_vs = (mu["vs_bh"] + sn["vs_bh"]) / 2
        avg_comp = (mu["compound"] + sn["compound"]) / 2
        ranked.append((s, mu, sn, avg_vs, avg_comp))
        print(f"{s:<28} {mu['compound']:>+8.1f}% {mu['trades']:>5} {mu['win_rate']:>4.0f}% "
              f"{sn['compound']:>+9.1f}% {sn['trades']:>6} {sn['win_rate']:>5.0f}% {avg_vs:>+9.1f}%")

    print("\n" + "=" * 88)
    print("【依平均複利報酬排序 TOP 5】")
    print("=" * 88)
    by_return = sorted(ranked, key=lambda x: -x[4])
    for i, (s, mu, sn, avg_vs, avg_comp) in enumerate(by_return[:5], 1):
        mu_pct = mu["compound"] / bh["MU"] * 100 if bh["MU"] else 0
        sn_pct = sn["compound"] / bh["SNDK"] * 100 if bh["SNDK"] else 0
        print(f"{i}. {s}")
        print(f"   MU   複利 {mu['compound']:+.1f}% ({mu_pct:.0f}% of B&H) · {mu['trades']}筆 · 勝率{mu['win_rate']:.0f}%")
        print(f"   SNDK 複利 {sn['compound']:+.1f}% ({sn_pct:.0f}% of B&H) · {sn['trades']}筆 · 勝率{sn['win_rate']:.0f}%")

    print("\n" + "=" * 88)
    print("【依最接近 B&H（平均 vs B&H 差距最小）TOP 5】")
    print("=" * 88)
    by_closeness = sorted(ranked, key=lambda x: -x[3])  # vs_bh less negative = closer
    for i, (s, mu, sn, avg_vs, avg_comp) in enumerate(by_closeness[:5], 1):
        print(f"{i}. {s}  (平均差距 {avg_vs:+.1f}%)")
        print(f"   MU {mu['compound']:+.1f}% vs B&H {bh['MU']:+.1f}% · SNDK {sn['compound']:+.1f}% vs B&H {bh['SNDK']:+.1f}%")

    print("\n" + "=" * 88)
    print("【打贏 B&H 的策略】")
    print("=" * 88)
    winners = [(s, mu, sn) for s, mu, sn, _, _ in ranked if mu["compound"] > mu["buy_hold"] or sn["compound"] > sn["buy_hold"]]
    if winners:
        for s, mu, sn in winners:
            flags = []
            if mu["compound"] > mu["buy_hold"]:
                flags.append(f"MU {mu['compound']:+.1f}% > B&H {mu['buy_hold']:+.1f}%")
            if sn["compound"] > sn["buy_hold"]:
                flags.append(f"SNDK {sn['compound']:+.1f}% > B&H {sn['buy_hold']:+.1f}%")
            print(f"  {s}: {', '.join(flags)}")
    else:
        print("  無任何策略在 12mo 期間打贏 B&H（記憶體暴漲行情）")

    # Best balanced: high return AND not too far from B&H
    print("\n" + "=" * 88)
    print("【綜合推薦：複利 > 200% 且 vs B&H 差距最小】")
    print("=" * 88)
    viable = [(s, mu, sn, avg_vs, avg_comp) for s, mu, sn, avg_vs, avg_comp in ranked
              if mu["compound"] >= 200 and sn["compound"] >= 200]
    viable.sort(key=lambda x: -x[3])
    if viable:
        s, mu, sn, avg_vs, avg_comp = viable[0]
        print(f"推薦: {s}")
        print(f"  MU   {mu['compound']:+.1f}% ({mu['trades']}筆, 勝率{mu['win_rate']:.0f}%)")
        print(f"  SNDK {sn['compound']:+.1f}% ({sn['trades']}筆, 勝率{sn['win_rate']:.0f}%)")
        print(f"  平均 vs B&H: {avg_vs:+.1f}%")
    else:
        # fallback: best by closeness with compound > 100
        viable2 = [(s, mu, sn, avg_vs, avg_comp) for s, mu, sn, avg_vs, avg_comp in ranked
                   if avg_comp >= 150]
        viable2.sort(key=lambda x: -x[3])
        if viable2:
            s, mu, sn, avg_vs, avg_comp = viable2[0]
            print(f"推薦: {s}")
            print(f"  MU   {mu['compound']:+.1f}% · SNDK {sn['compound']:+.1f}% · 平均 vs B&H {avg_vs:+.1f}%")
        else:
            s, mu, sn, avg_vs, avg_comp = by_closeness[0]
            print(f"最接近 B&H: {s} (MU {mu['compound']:+.1f}%, SNDK {sn['compound']:+.1f}%)")


if __name__ == "__main__":
    print_report(run_all())
