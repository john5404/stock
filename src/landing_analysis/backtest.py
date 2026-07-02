"""Backtesting engine for landing point strategy."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .analyzer import LandingAnalyzer, LevelCluster
from .indicators import add_indicators


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    reason: str
    support_price: float
    pnl_pct: float
    hold_days: int


@dataclass
class BacktestResult:
    mode: str
    trades: list[Trade] = field(default_factory=list)
    buy_hold_pct: float = 0.0

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl_pct > 0)
        return wins / len(self.trades) * 100

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl_pct for t in self.trades)

    @property
    def compound_return(self) -> float:
        equity = 1.0
        for trade in self.trades:
            equity *= 1 + trade.pnl_pct / 100
        return (equity - 1) * 100


class BacktestEngine:
    def __init__(
        self,
        tolerance: float = 0.015,
        stop_buffer: float = 0.03,
        rsi_buy: float = 45.0,
        rsi_sell: float = 70.0,
        trail_pct: float = 0.15,
    ):
        self.tolerance = tolerance
        self.stop_buffer = stop_buffer
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.trail_pct = trail_pct
        self.analyzer = LandingAnalyzer()

    def run_fixed(
        self,
        df: pd.DataFrame,
        ticker: str,
        lookback_days: int = 42,
    ) -> BacktestResult:
        if len(df) <= lookback_days + 5:
            raise ValueError("Not enough data for fixed-window backtest")

        enriched = add_indicators(df)
        train = enriched.iloc[:lookback_days]
        test = enriched.iloc[lookback_days:]
        analysis = self.analyzer.analyze(train, ticker, lookback_days)
        trades = self._simulate(test, analysis.supports, analysis.resistances)

        bh_start = float(test["Close"].iloc[0])
        bh_end = float(test["Close"].iloc[-1])
        return BacktestResult(
            mode="fixed",
            trades=trades,
            buy_hold_pct=(bh_end / bh_start - 1) * 100,
        )

    def run_rolling(
        self,
        df: pd.DataFrame,
        ticker: str,
        lookback_days: int = 42,
    ) -> BacktestResult:
        if len(df) <= lookback_days + 5:
            raise ValueError("Not enough data for rolling backtest")

        enriched = add_indicators(df)
        trades: list[Trade] = []
        position = None

        for i in range(lookback_days, len(enriched)):
            window = enriched.iloc[i - lookback_days : i]
            row = enriched.iloc[i]
            analysis = self.analyzer.analyze(window, ticker, lookback_days)
            position, new_trade = self._step(
                row,
                analysis.supports,
                analysis.resistances,
                position,
            )
            if new_trade:
                trades.append(new_trade)

        if position:
            final_row = enriched.iloc[-1]
            trades.append(self._close_position(position, final_row, final_row["Close"], "回測結束平倉"))

        bh_start = float(enriched["Close"].iloc[lookback_days])
        bh_end = float(enriched["Close"].iloc[-1])
        return BacktestResult(
            mode="rolling",
            trades=trades,
            buy_hold_pct=(bh_end / bh_start - 1) * 100,
        )

    def _simulate(
        self,
        test: pd.DataFrame,
        supports: list[LevelCluster],
        resistances: list[LevelCluster],
    ) -> list[Trade]:
        trades: list[Trade] = []
        position = None
        for _, row in test.iterrows():
            position, new_trade = self._step(row, supports, resistances, position)
            if new_trade:
                trades.append(new_trade)
        if position:
            final_price = float(test["Close"].iloc[-1])
            trades.append(
                self._close_position(position, test.iloc[-1], final_price, "回測結束平倉")
            )
        return trades

    def _step(self, row: pd.Series, supports, resistances, position):
        price = float(row["Close"])
        low = float(row["Low"])
        high = float(row["High"])
        rsi = row.get("RSI", np.nan)
        if pd.isna(rsi):
            return position, None

        if position is None:
            entry_zones = sorted(
                [s for s in supports if s.strength >= 1 and s.price <= price * 1.05],
                key=lambda x: -x.strength,
            )[:4]
            for zone in entry_zones:
                if low <= zone.price * (1 + self.tolerance) and rsi < self.rsi_buy:
                    targets = [r.price for r in resistances if r.price > price * 1.03]
                    take_profit = min(targets) if targets else price * 1.15
                    position = {
                        "entry_date": row.name,
                        "entry_price": price,
                        "support": zone.price,
                        "stop": zone.price * (1 - self.stop_buffer),
                        "take_profit": take_profit,
                        "peak": price,
                    }
                    break
            return position, None

        position["peak"] = max(position["peak"], high)
        trail_stop = position["peak"] * (1 - self.trail_pct)
        reason = None
        exit_price = price

        if low <= position["stop"]:
            reason, exit_price = "停損", position["stop"]
        elif high >= position["take_profit"]:
            reason, exit_price = "停利(阻力)", position["take_profit"]
        elif price <= trail_stop and price > position["entry_price"]:
            reason, exit_price = "移動停利", price
        elif rsi > self.rsi_sell:
            reason, exit_price = "RSI超買", price

        if reason:
            trade = self._close_position(position, row, exit_price, reason)
            return None, trade
        return position, None

    def _close_position(self, position: dict, row: pd.Series, exit_price: float, reason: str) -> Trade:
        pnl = (exit_price / position["entry_price"] - 1) * 100
        return Trade(
            entry_date=position["entry_date"],
            entry_price=position["entry_price"],
            exit_date=row.name,
            exit_price=exit_price,
            reason=reason,
            support_price=position["support"],
            pnl_pct=pnl,
            hold_days=(row.name - position["entry_date"]).days,
        )
