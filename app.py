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
from landing_analysis.strategies import STRATEGY_TEMPLATES, TEMPLATE_TICKERS, StrategyConfig, get_template


class LandingAnalysisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("落點分析 · Landing Point Analyzer")
        self.geometry("1320x860")
        self.minsize(1100, 720)

        self.df: pd.DataFrame | None = None
        self.analysis = None
        self.backtest_result = None
        self.ticker = "MU"
        self.strategy_config = get_template("設備股")

        self.analyzer = LandingAnalyzer()
        self.engine = BacktestEngine(self.strategy_config)

        self._param_vars: dict[str, tk.Variable] = {}
        self._custom_widgets: list[tk.Widget] = []

        self._build_ui()
        self._apply_strategy_template("設備股")

    def _build_ui(self):
        self.configure(bg="#f4f6f8")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=8)

        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        left_wrap = ttk.Frame(container)
        left_wrap.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        canvas = tk.Canvas(left_wrap, width=300, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_wrap, orient=tk.VERTICAL, command=canvas.yview)
        left = ttk.Frame(canvas)
        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=left, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.Y)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(left, text="落點分析系統", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 12))

        # --- Strategy template ---
        strat_frame = ttk.LabelFrame(left, text="策略模板", padding=8)
        strat_frame.pack(fill=tk.X, pady=(0, 8))

        self.strategy_var = tk.StringVar(value="設備股")
        strat_combo = ttk.Combobox(
            strat_frame,
            textvariable=self.strategy_var,
            values=list(STRATEGY_TEMPLATES.keys()),
            state="readonly",
            width=26,
        )
        strat_combo.pack(fill=tk.X)
        strat_combo.bind("<<ComboboxSelected>>", self._on_strategy_change)

        self.strategy_desc_var = tk.StringVar()
        ttk.Label(strat_frame, textvariable=self.strategy_desc_var, wraplength=260, justify=tk.LEFT).pack(
            anchor=tk.W, pady=(6, 0)
        )
        self.strategy_summary_var = tk.StringVar()
        ttk.Label(strat_frame, textvariable=self.strategy_summary_var, wraplength=260, foreground="#555").pack(
            anchor=tk.W, pady=(4, 0)
        )

        # --- Custom params ---
        self.custom_frame = ttk.LabelFrame(left, text="自訂參數", padding=8)
        self.custom_frame.pack(fill=tk.X, pady=(0, 8))
        self._build_custom_params(self.custom_frame)

        # --- Ticker ---
        ticker_frame = ttk.LabelFrame(left, text="標的", padding=8)
        ticker_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(ticker_frame, text="快速選股").pack(anchor=tk.W)
        self.ticker_preset_var = tk.StringVar()
        self.ticker_preset_combo = ttk.Combobox(ticker_frame, textvariable=self.ticker_preset_var, width=26)
        self.ticker_preset_combo.pack(fill=tk.X, pady=(0, 6))
        self.ticker_preset_combo.bind("<<ComboboxSelected>>", self._on_ticker_preset)

        self.custom_ticker_var = tk.StringVar(value="AMAT")
        ttk.Label(ticker_frame, text="Ticker").pack(anchor=tk.W)
        ttk.Entry(ticker_frame, textvariable=self.custom_ticker_var, width=28).pack(fill=tk.X)

        # --- General settings ---
        general = ttk.LabelFrame(left, text="一般設定", padding=8)
        general.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(general, text="資料期間").pack(anchor=tk.W)
        self.period_var = tk.StringVar(value="12mo")
        ttk.Combobox(general, textvariable=self.period_var, values=["6mo", "12mo", "2y", "5y"], state="readonly", width=26).pack(fill=tk.X, pady=(0, 6))

        ttk.Label(general, text="分析視窗（交易日）").pack(anchor=tk.W)
        self.lookback_var = tk.IntVar(value=42)
        ttk.Spinbox(general, from_=20, to=120, textvariable=self.lookback_var, width=26).pack(fill=tk.X, pady=(0, 6))

        ttk.Label(general, text="回測模式").pack(anchor=tk.W)
        self.backtest_mode_var = tk.StringVar(value="rolling")
        ttk.Combobox(general, textvariable=self.backtest_mode_var, values=["rolling", "fixed"], state="readonly", width=26).pack(fill=tk.X)

        ttk.Button(left, text="1. 載入資料", style="Action.TButton", command=self.load_data).pack(fill=tk.X, pady=(8, 4))
        ttk.Button(left, text="2. 落點分析", style="Action.TButton", command=self.run_analysis).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="3. 執行回測", style="Action.TButton", command=self.run_backtest).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="全部執行", style="Action.TButton", command=self.run_all).pack(fill=tk.X, pady=(4, 8))

        self.status_var = tk.StringVar(value="就緒")
        ttk.Label(left, textvariable=self.status_var, wraplength=260).pack(anchor=tk.W)
        self.summary_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.summary_var, wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))

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

    def _build_custom_params(self, parent):
        specs = [
            ("stop_loss_pct", "停損 (%)", 80, 1, 25, True),
            ("rsi_buy", "RSI 買入上限", 30, 1, 70, False),
            ("rsi_sell", "RSI 賣出下限", 60, 1, 90, False),
            ("trail_pct", "移動停利 (%)", 100, 5, 35, True),
            ("tolerance", "支撐容差 (%)", 15, 5, 30, True),
        ]
        for key, label, default, from_, to, is_pct in specs:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=default / 100 if is_pct else default)
            self._param_vars[key] = var
            spin = ttk.Spinbox(row, from_=from_, to=to, textvariable=var, width=10, increment=1 if not is_pct else 1)
            spin.pack(side=tk.RIGHT)
            self._custom_widgets.append(spin)

        for key, label in [
            ("use_resistance_tp", "阻力停利"),
            ("breakout_buy", "突破加碼"),
            ("trend_ma_filter", "MA50 趨勢過濾"),
        ]:
            var = tk.BooleanVar(value=False)
            self._param_vars[key] = var
            cb = ttk.Checkbutton(parent, text=label, variable=var, command=self._on_custom_param_change)
            cb.pack(anchor=tk.W, pady=2)
            self._custom_widgets.append(cb)

    def _set_custom_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in self._custom_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _on_strategy_change(self, _event=None):
        self._apply_strategy_template(self.strategy_var.get())

    def _apply_strategy_template(self, name: str):
        cfg = get_template(name)
        self.strategy_config = cfg
        self.strategy_desc_var.set(cfg.description)
        self.strategy_summary_var.set(cfg.summary())

        is_custom = name == "自訂"
        self._set_custom_enabled(is_custom)

        if not is_custom:
            self._param_vars["stop_loss_pct"].set(cfg.stop_loss_pct * 100)
            self._param_vars["rsi_buy"].set(cfg.rsi_buy)
            self._param_vars["rsi_sell"].set(cfg.rsi_sell)
            self._param_vars["trail_pct"].set(cfg.trail_pct * 100)
            self._param_vars["tolerance"].set(cfg.tolerance * 100)
            self._param_vars["use_resistance_tp"].set(cfg.use_resistance_tp)
            self._param_vars["breakout_buy"].set(cfg.breakout_buy)
            self._param_vars["trend_ma_filter"].set(cfg.trend_ma_filter)

        tickers = TEMPLATE_TICKERS.get(name, PRESET_TICKERS)
        if name == "自訂":
            all_tickers = {}
            for group in TEMPLATE_TICKERS.values():
                all_tickers.update(group)
            all_tickers.update(PRESET_TICKERS)
            tickers = all_tickers

        self.ticker_preset_combo["values"] = list(tickers.keys())
        if tickers:
            first = next(iter(tickers.keys()))
            self.ticker_preset_var.set(first)
            self.custom_ticker_var.set(tickers[first])

        self.engine = BacktestEngine(self._build_config_from_ui())

    def _on_custom_param_change(self):
        if self.strategy_var.get() == "自訂":
            self.strategy_config = self._build_config_from_ui()
            self.strategy_summary_var.set(self.strategy_config.summary())
            self.engine = BacktestEngine(self.strategy_config)

    def _build_config_from_ui(self) -> StrategyConfig:
        name = self.strategy_var.get()
        return StrategyConfig(
            name=name,
            description=STRATEGY_TEMPLATES.get(name, get_template("自訂")).description,
            stop_loss_pct=float(self._param_vars["stop_loss_pct"].get()) / 100,
            rsi_buy=float(self._param_vars["rsi_buy"].get()),
            rsi_sell=float(self._param_vars["rsi_sell"].get()),
            trail_pct=float(self._param_vars["trail_pct"].get()) / 100,
            tolerance=float(self._param_vars["tolerance"].get()) / 100,
            use_resistance_tp=bool(self._param_vars["use_resistance_tp"].get()),
            breakout_buy=bool(self._param_vars["breakout_buy"].get()),
            trend_ma_filter=bool(self._param_vars["trend_ma_filter"].get()),
        )

    def _on_ticker_preset(self, _event=None):
        name = self.strategy_var.get()
        tickers = TEMPLATE_TICKERS.get(name, {})
        if name == "自訂":
            all_tickers = {}
            for group in TEMPLATE_TICKERS.values():
                all_tickers.update(group)
            all_tickers.update(PRESET_TICKERS)
            tickers = all_tickers
        selected = self.ticker_preset_var.get()
        if selected in tickers:
            self.custom_ticker_var.set(tickers[selected])

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
            "entry_date": "買入日", "entry": "買價", "exit_date": "賣出日", "exit": "賣價",
            "pnl": "報酬%", "reason": "原因", "support": "支撐", "hold": "持有天",
        }
        widths = {"entry_date": 100, "entry": 80, "exit_date": 100, "exit": 80, "pnl": 70, "reason": 120, "support": 80, "hold": 70}
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

    def _resolve_ticker(self) -> str:
        return self.custom_ticker_var.get().strip().upper()

    def _set_status(self, text: str):
        self.status_var.set(text)
        self.update_idletasks()

    def load_data(self):
        try:
            self.engine = BacktestEngine(self._build_config_from_ui())
            self.ticker = self._resolve_ticker()
            self._set_status(f"正在載入 {self.ticker} ...")
            self.df = fetch_stock_data(self.ticker, self.period_var.get())
            start, end = self.df.index[0].date(), self.df.index[-1].date()
            last = self.df["Close"].iloc[-1]
            self.summary_var.set(
                f"模板: {self.strategy_var.get()}\n"
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
            self.analysis = self.analyzer.analyze(self.df, self.ticker, self.lookback_var.get())
            self._populate_levels()
            self._draw_price_chart()
            self.notebook.select(self.levels_frame)
            self._set_status("落點分析完成")
        except Exception as exc:
            messagebox.showerror("分析失敗", str(exc))

    def run_backtest(self):
        if self.df is None:
            messagebox.showwarning("提示", "請先載入資料")
            return
        try:
            self.engine = BacktestEngine(self._build_config_from_ui())
            lookback = self.lookback_var.get()
            mode = self.backtest_mode_var.get()
            if mode == "fixed":
                self.backtest_result = self.engine.run_fixed(self.df, self.ticker, lookback)
            else:
                self.backtest_result = self.engine.run_rolling(self.df, self.ticker, lookback)
            self._populate_backtest()
            self._draw_price_chart()
            self.notebook.select(self.backtest_frame)
            self._set_status(f"回測完成 [{self.strategy_var.get()} / {mode}]")
        except Exception as exc:
            messagebox.showerror("回測失敗", str(exc))

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
            self.support_tree.insert("", tk.END, values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)))
        for level in self.analysis.resistances:
            dist = (level.price / current - 1) * 100
            self.resist_tree.insert("", tk.END, values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)))
        self.summary_var.set(
            f"模板: {self.strategy_var.get()}\n"
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
                f"模板: {result.strategy_name} | 模式: {mode_label} | "
                f"交易: {len(result.trades)} 筆 | 勝率: {result.win_rate:.0f}% | "
                f"複利: {result.compound_return:+.1f}% | Buy&Hold: {result.buy_hold_pct:+.1f}%"
            )
        )
        for trade in result.trades:
            self.trade_tree.insert("", tk.END, values=(
                trade.entry_date.date(), f"{trade.entry_price:,.2f}",
                trade.exit_date.date(), f"{trade.exit_price:,.2f}",
                f"{trade.pnl_pct:+.1f}", trade.reason, f"{trade.support_price:,.2f}", trade.hold_days,
            ))

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
        self.ax.plot(dates, plot_df["Close"], color="#1f77b4", linewidth=1.8, label="Close")
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
                self.ax.plot([trade.entry_date, trade.exit_date], [trade.entry_price, trade.exit_price], color="#9e9e9e", alpha=0.5, linewidth=1)
        legend_items = [
            Line2D([0], [0], color="#1f77b4", linewidth=2, label="Close"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#00c853", markersize=8, label="Buy"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#d50000", markersize=8, label="Sell"),
        ]
        self.ax.legend(handles=legend_items, loc="upper left")
        self.ax.set_title(f"{self.ticker} [{self.strategy_var.get()}]")
        self.ax.grid(True, alpha=0.25)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        self.fig.autofmt_xdate()
        self.canvas.draw()


def main():
    app = LandingAnalysisApp()
    app.mainloop()


if __name__ == "__main__":
    main()
