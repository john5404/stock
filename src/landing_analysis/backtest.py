"""Backtesting engine for landing point strategy."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .analyzer import LandingAnalyzer, LevelCluster
from .indicators import add_indicators
from .strategies import StrategyConfig


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
    strategy_name: str = ""
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
    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig(name="預設")
        self.analyzer = LandingAnalyzer()

    @property
    def tolerance(self) -> float:
        return self.config.tolerance

    @property
    def rsi_buy(self) -> float:
        return self.config.rsi_buy

    @property
    def rsi_sell(self) -> float:
        return self.config.rsi_sell

    @property
    def trail_pct(self) -> float:
        return self.config.trail_pct

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
            strategy_name=self.config.name,
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
            position, new_trade = self._step(row, analysis.supports, analysis.resistances, position)
            if new_trade:
                trades.append(new_trade)

        if position:
            final_row = enriched.iloc[-1]
            trades.append(self._close_position(position, final_row, final_row["Close"], "回測結束平倉"))

        bh_start = float(enriched["Close"].iloc[lookback_days])
        bh_end = float(enriched["Close"].iloc[-1])
        return BacktestResult(
            mode="rolling",
            strategy_name=self.config.name,
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
            trades.append(self._close_position(position, test.iloc[-1], final_price, "回測結束平倉"))
        return trades

    def _signal_filters_ok(self, row: pd.Series, for_breakout: bool = False) -> bool:
        cfg = self.config
        if for_breakout:
            checks = []
            if cfg.require_macd:
                checks.append(bool(row.get("MACD_Bull", False)) or bool(row.get("MACD_Golden", False)))
            if cfg.volume_expand_breakout:
                checks.append(bool(row.get("Vol_Expand", False)))
            if not checks:
                return True
            need = cfg.signal_confirm_min or len(checks)
            return sum(checks) >= need

        checks = []
        if cfg.require_macd:
            checks.append(bool(row.get("MACD_Bull", False)) or bool(row.get("MACD_Golden", False)))
        if cfg.require_volume_shrink:
            checks.append(bool(row.get("Vol_Shrink", False)))
        if cfg.require_candlestick:
            checks.append(bool(row.get("Bullish_Candle", False)))
        if not checks:
            return True
        need = cfg.signal_confirm_min or len(checks)
        return sum(checks) >= need

    def _try_support_entry(self, row, supports, resistances, price, low, rsi, ma50):
        zones = sorted(
            [s for s in supports if s.strength >= 1 and s.price <= price * 1.05],
            key=lambda x: -x.strength,
        )[:4]
        for zone in zones:
            trend_ok = (not self.config.trend_ma_filter) or (not pd.isna(ma50) and price > ma50)
            if (
                low <= zone.price * (1 + self.tolerance)
                and rsi < self.rsi_buy
                and trend_ok
                and self._signal_filters_ok(row, for_breakout=False)
            ):
                targets = [r.price for r in resistances if r.price > price * 1.03]
                take_profit = min(targets) if targets else price * 1.30
                return {
                    "entry_date": row.name,
                    "entry_price": price,
                    "support": zone.price,
                    "stop": price * (1 - self.config.stop_loss_pct),
                    "take_profit": take_profit,
                    "peak": price,
                }
        return None

    def _try_breakout_entry(self, row, supports, resistances, price, high, rsi, ma50):
        if not self.config.breakout_buy:
            return None
        trend_ok = (not self.config.trend_ma_filter) or (not pd.isna(ma50) and price > ma50)
        if not trend_ok or rsi <= 50:
            return None
        if not self._signal_filters_ok(row, for_breakout=True):
            return None
        broken = [
            r for r in resistances
            if r.strength >= 2 and high >= r.price * 0.995 and price > r.price * 0.99
        ]
        if not broken:
            return None
        support_price = min((s.price for s in supports), default=price * 0.9)
        return {
            "entry_date": row.name,
            "entry_price": price,
            "support": support_price,
            "stop": price * (1 - self.config.stop_loss_pct),
            "take_profit": price * 1.30,
            "peak": price,
        }

    def _step(self, row: pd.Series, supports, resistances, position):
        price = float(row["Close"])
        low = float(row["Low"])
        high = float(row["High"])
        rsi = row.get("RSI", np.nan)
        ma50 = row.get("MA50", np.nan)
        if pd.isna(rsi):
            return position, None

        if position is None:
            position = self._try_support_entry(row, supports, resistances, price, low, rsi, ma50)
            if position is None:
                position = self._try_breakout_entry(row, supports, resistances, price, high, rsi, ma50)
            return position, None

        position["peak"] = max(position["peak"], high)
        trail_stop = position["peak"] * (1 - self.trail_pct)
        reason = None
        exit_price = price

        if low <= position["stop"]:
            reason, exit_price = f"停損(-{self.config.stop_loss_pct*100:.0f}%)", position["stop"]
        elif self.config.use_resistance_tp and high >= position["take_profit"]:
            reason, exit_price = "停利(阻力)", position["take_profit"]
        elif price <= trail_stop and price > position["entry_price"]:
            reason, exit_price = "移動停利", price
        elif self.config.use_macd_exit and bool(row.get("MACD_Death", False)):
            reason, exit_price = "MACD死叉", price
        elif rsi > self.rsi_sell and not self.config.trend_ma_filter:
            reason, exit_price = "RSI超買", price

        if reason:
            return None, self._close_position(position, row, exit_price, reason)
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
