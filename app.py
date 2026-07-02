#!/usr/bin/env python3
"""Landing point analysis desktop UI."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.analyzer import LandingAnalyzer
from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_fetcher import PRESET_TICKERS, fetch_stock_data
from landing_analysis.indicators import add_indicators


class LandingAnalysisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("落點分析 · Landing Point Analyzer")
        self.geometry("1280x820")
        self.minsize(1024, 680)

        self.df: pd.DataFrame | None = None
        self.analysis = None
        self.backtest_result = None
        self.ticker = "MU"

        self.analyzer = LandingAnalyzer()
        self.engine = BacktestEngine()

        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#f4f6f8")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=8)

        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(container, text="控制面板", padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        ttk.Label(left, text="落點分析系統", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(left, text="股票代號").pack(anchor=tk.W)
        self.ticker_var = tk.StringVar(value="MU")
        ticker_combo = ttk.Combobox(
            left,
            textvariable=self.ticker_var,
            values=[f"{name} ({code})" for name, code in PRESET_TICKERS.items()] + ["自訂"],
            width=24,
        )
        ticker_combo.pack(fill=tk.X, pady=(0, 8))
        ticker_combo.bind("<<ComboboxSelected>>", self._on_preset_select)

        self.custom_ticker_var = tk.StringVar(value="MU")
        ttk.Label(left, text="自訂 Ticker").pack(anchor=tk.W)
        ttk.Entry(left, textvariable=self.custom_ticker_var, width=26).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(left, text="資料期間").pack(anchor=tk.W)
        self.period_var = tk.StringVar(value="12mo")
        ttk.Combobox(
            left,
            textvariable=self.period_var,
            values=["6mo", "12mo", "2y", "5y"],
            width=24,
            state="readonly",
        ).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(left, text="分析視窗（交易日）").pack(anchor=tk.W)
        self.lookback_var = tk.IntVar(value=42)
        ttk.Spinbox(left, from_=20, to=120, textvariable=self.lookback_var, width=24).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(left, text="回測模式").pack(anchor=tk.W)
        self.backtest_mode_var = tk.StringVar(value="rolling")
        ttk.Combobox(
            left,
            textvariable=self.backtest_mode_var,
            values=["rolling", "fixed"],
            width=24,
            state="readonly",
        ).pack(fill=tk.X, pady=(0, 12))

        ttk.Button(left, text="1. 載入資料", style="Action.TButton", command=self.load_data).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="2. 落點分析", style="Action.TButton", command=self.run_analysis).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="3. 執行回測", style="Action.TButton", command=self.run_backtest).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="全部執行", style="Action.TButton", command=self.run_all).pack(fill=tk.X, pady=(4, 12))

        self.status_var = tk.StringVar(value="就緒")
        ttk.Label(left, textvariable=self.status_var, wraplength=240).pack(anchor=tk.W, pady=(8, 0))

        self.summary_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.summary_var, wraplength=240, justify=tk.LEFT).pack(anchor=tk.W, pady=(12, 0))

        right = ttk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.levels_frame = ttk.Frame(self.notebook)
        self.backtest_frame = ttk.Frame(self.notebook)
        self.chart_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.levels_frame, text="落點分析")
        self.notebook.add(self.backtest_frame, text="回測結果")
        self.notebook.add(self.chart_frame, text="圖表")

        self._build_levels_tab()
        self._build_backtest_tab()
        self._build_chart_tab()

    def _build_levels_tab(self):
        top = ttk.Frame(self.levels_frame, padding=8)
        top.pack(fill=tk.BOTH, expand=True)

        cols = ("price", "strength", "distance", "methods")
        self.support_tree = self._make_tree(top, "支撐落點", cols, side=tk.LEFT)
        self.resist_tree = self._make_tree(top, "阻力落點", cols, side=tk.RIGHT)

    def _build_backtest_tab(self):
        frame = ttk.Frame(self.backtest_frame, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)

        self.backtest_summary = ttk.Label(frame, text="尚未執行回測", style="Header.TLabel")
        self.backtest_summary.pack(anchor=tk.W, pady=(0, 8))

        cols = ("entry_date", "entry", "exit_date", "exit", "pnl", "reason", "support", "hold")
        self.trade_tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)
        headers = {
            "entry_date": "買入日",
            "entry": "買價",
            "exit_date": "賣出日",
            "exit": "賣價",
            "pnl": "報酬%",
            "reason": "原因",
            "support": "支撐",
            "hold": "持有天",
        }
        widths = {"entry_date": 100, "entry": 80, "exit_date": 100, "exit": 80, "pnl": 70, "reason": 100, "support": 80, "hold": 70}
        for col in cols:
            self.trade_tree.heading(col, text=headers[col])
            self.trade_tree.column(col, width=widths[col], anchor=tk.CENTER)
        self.trade_tree.pack(fill=tk.BOTH, expand=True)

    def _build_chart_tab(self):
        self.fig, self.ax = plt.subplots(figsize=(9, 5), dpi=100)
        self.fig.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._draw_empty_chart()

    def _make_tree(self, parent, title, cols, side):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=4)
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=20)
        headers = {"price": "價位", "strength": "強度", "distance": "距現價%", "methods": "方法"}
        widths = {"price": 90, "strength": 60, "distance": 80, "methods": 280}
        for col in cols:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor=tk.W if col == "methods" else tk.CENTER)
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def _on_preset_select(self, _event=None):
        selected = self.ticker_var.get()
        for name, code in PRESET_TICKERS.items():
            if selected.startswith(name):
                self.custom_ticker_var.set(code)
                break

    def _resolve_ticker(self) -> str:
        return self.custom_ticker_var.get().strip().upper()

    def _set_status(self, text: str):
        self.status_var.set(text)
        self.update_idletasks()

    def load_data(self):
        try:
            self.ticker = self._resolve_ticker()
            self._set_status(f"正在載入 {self.ticker} ...")
            self.df = fetch_stock_data(self.ticker, self.period_var.get())
            start = self.df.index[0].date()
            end = self.df.index[-1].date()
            last = self.df["Close"].iloc[-1]
            self.summary_var.set(
                f"Ticker: {self.ticker}\n"
                f"資料: {start} ~ {end}\n"
                f"筆數: {len(self.df)}\n"
                f"最新收盤: {last:,.2f}"
            )
            self._set_status(f"已載入 {self.ticker}，共 {len(self.df)} 筆")
            self._draw_price_chart()
        except Exception as exc:
            messagebox.showerror("載入失敗", str(exc))
            self._set_status("載入失敗")

    def run_analysis(self):
        if self.df is None:
            messagebox.showwarning("提示", "請先載入資料")
            return
        try:
            lookback = self.lookback_var.get()
            self.analysis = self.analyzer.analyze(self.df, self.ticker, lookback)
            self._populate_levels()
            self._draw_price_chart()
            self.notebook.select(self.levels_frame)
            self._set_status("落點分析完成")
        except Exception as exc:
            messagebox.showerror("分析失敗", str(exc))
            self._set_status("分析失敗")

    def run_backtest(self):
        if self.df is None:
            messagebox.showwarning("提示", "請先載入資料")
            return
        try:
            lookback = self.lookback_var.get()
            mode = self.backtest_mode_var.get()
            if mode == "fixed":
                self.backtest_result = self.engine.run_fixed(self.df, self.ticker, lookback)
            else:
                self.backtest_result = self.engine.run_rolling(self.df, self.ticker, lookback)
            self._populate_backtest()
            self._draw_price_chart()
            self.notebook.select(self.backtest_frame)
            self._set_status(f"回測完成 ({mode})")
        except Exception as exc:
            messagebox.showerror("回測失敗", str(exc))
            self._set_status("回測失敗")

    def run_all(self):
        self.load_data()
        if self.df is not None:
            self.run_analysis()
            self.run_backtest()

    def _populate_levels(self):
        for tree in (self.support_tree, self.resist_tree):
            for item in tree.get_children():
                tree.delete(item)

        if not self.analysis:
            return

        current = self.analysis.current_price
        for level in self.analysis.supports:
            dist = (level.price / current - 1) * 100
            self.support_tree.insert(
                "",
                tk.END,
                values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)),
            )
        for level in self.analysis.resistances:
            dist = (level.price / current - 1) * 100
            self.resist_tree.insert(
                "",
                tk.END,
                values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)),
            )

        self.summary_var.set(
            f"Ticker: {self.ticker}\n"
            f"分析期間: {self.analysis.train_start.date()} ~ {self.analysis.train_end.date()}\n"
            f"現價: {current:,.2f}\n"
            f"波段: {self.analysis.swing_low:,.2f} ~ {self.analysis.swing_high:,.2f}\n"
            f"ATR: {self.analysis.atr:,.2f}"
        )

    def _populate_backtest(self):
        for item in self.trade_tree.get_children():
            self.trade_tree.delete(item)
        if not self.backtest_result:
            return

        result = self.backtest_result
        mode_label = "滾動視窗" if result.mode == "rolling" else "固定前N日"
        self.backtest_summary.config(
            text=(
                f"模式: {mode_label} | 交易: {len(result.trades)} 筆 | "
                f"勝率: {result.win_rate:.0f}% | 累計: {result.total_pnl:+.1f}% | "
                f"複利: {result.compound_return:+.1f}% | Buy&Hold: {result.buy_hold_pct:+.1f}%"
            )
        )
        for trade in result.trades:
            self.trade_tree.insert(
                "",
                tk.END,
                values=(
                    trade.entry_date.date(),
                    f"{trade.entry_price:,.2f}",
                    trade.exit_date.date(),
                    f"{trade.exit_price:,.2f}",
                    f"{trade.pnl_pct:+.1f}",
                    trade.reason,
                    f"{trade.support_price:,.2f}",
                    trade.hold_days,
                ),
            )

    def _draw_empty_chart(self):
        self.ax.clear()
        self.ax.set_title("請載入資料後顯示圖表")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _draw_price_chart(self):
        if self.df is None:
            self._draw_empty_chart()
            return

        self.ax.clear()
        plot_df = add_indicators(self.df.tail(180))
        dates = plot_df.index
        closes = plot_df["Close"]

        self.ax.plot(dates, closes, color="#1f77b4", linewidth=1.8, label="Close")
        if plot_df["MA20"].notna().any():
            self.ax.plot(dates, plot_df["MA20"], color="#ff9800", linewidth=1, alpha=0.8, label="MA20")
        if plot_df["MA50"].notna().any():
            self.ax.plot(dates, plot_df["MA50"], color="#4caf50", linewidth=1, alpha=0.8, label="MA50")

        if self.analysis:
            for level in self.analysis.supports:
                self.ax.axhline(level.price, color="#2e7d32", linestyle="--", alpha=0.35, linewidth=1)
            for level in self.analysis.resistances:
                self.ax.axhline(level.price, color="#c62828", linestyle="--", alpha=0.35, linewidth=1)

        if self.backtest_result and self.backtest_result.trades:
            for trade in self.backtest_result.trades:
                self.ax.scatter(trade.entry_date, trade.entry_price, color="#00c853", s=60, zorder=5)
                self.ax.scatter(trade.exit_date, trade.exit_price, color="#d50000", s=60, zorder=5)
                self.ax.plot(
                    [trade.entry_date, trade.exit_date],
                    [trade.entry_price, trade.exit_price],
                    color="#9e9e9e",
                    alpha=0.5,
                    linewidth=1,
                )

        legend_items = [
            Line2D([0], [0], color="#1f77b4", linewidth=2, label="Close"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#00c853", markersize=8, label="Buy"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#d50000", markersize=8, label="Sell"),
        ]
        self.ax.legend(handles=legend_items, loc="upper left")
        self.ax.set_title(f"{self.ticker} Price & Landing Levels")
        self.ax.grid(True, alpha=0.25)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        self.fig.autofmt_xdate()
        self.canvas.draw()


def main():
    app = LandingAnalysisApp()
    app.mainloop()


if __name__ == "__main__":
    main()
