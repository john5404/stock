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
from landing_analysis.data_fetcher import (
    MARKET_TICKERS,
    fetch_stock_data,
    get_market_tickers,
    normalize_ticker_input,
    ticker_market,
)
from landing_analysis.indicators import add_indicators
from landing_analysis.strategies import STRATEGY_TEMPLATES, TEMPLATE_TICKERS, StrategyConfig, get_template

COLORS = {
    "bg": "#edf0f5",
    "surface": "#ffffff",
    "sidebar": "#131820",
    "sidebar_elevated": "#1a2130",
    "sidebar_border": "#2a3448",
    "accent": "#3b82f6",
    "accent_dark": "#2563eb",
    "accent_soft": "#dbeafe",
    "text": "#0f172a",
    "text_inverse": "#f1f5f9",
    "muted": "#64748b",
    "muted_light": "#94a3b8",
    "border": "#e2e8f0",
    "success": "#16a34a",
    "success_soft": "#dcfce7",
    "danger": "#dc2626",
    "danger_soft": "#fee2e2",
    "strength_high": "#f87171",
    "warning": "#d97706",
    "chart_bg": "#fafbfc",
    "tree_header": "#f8fafc",
    "tree_zebra": "#f1f5f9",
}

FONTS = {
    "title": ("Segoe UI", 18, "bold"),
    "subtitle": ("Segoe UI", 10),
    "section": ("Segoe UI", 10, "bold"),
    "body": ("Segoe UI", 9),
    "body_bold": ("Segoe UI", 9, "bold"),
    "caption": ("Segoe UI", 8),
    "kpi": ("Segoe UI", 12, "bold"),
}


class LandingAnalysisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("落點分析 · Landing Point Analyzer")
        self.geometry("1360x900")
        self.minsize(1140, 760)
        self.configure(bg=COLORS["bg"])

        self.df: pd.DataFrame | None = None
        self.analysis = None
        self.backtest_result = None
        self.ticker = "MU"
        self.strategy_config = get_template("設備股")

        self.analyzer = LandingAnalyzer()
        self.engine = BacktestEngine(self.strategy_config)

        self._param_vars: dict[str, tk.Variable] = {}
        self._custom_widgets: list[tk.Widget] = []
        self._ticker_catalog: dict[str, str] = {}
        self._ticker_search_values: list[str] = []

        self._setup_theme()
        self._build_ui()
        self._apply_strategy_template("設備股")

    def _setup_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["body"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["body"])
        style.configure("Surface.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONTS["caption"])
        style.configure("Header.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=FONTS["kpi"])
        style.configure("Kpi.TLabel", background=COLORS["surface"], foreground=COLORS["accent_dark"], font=FONTS["kpi"])

        style.configure(
            "Card.TLabelframe",
            background=COLORS["surface"],
            bordercolor=COLORS["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=FONTS["section"],
        )

        style.configure(
            "TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
            tabmargins=(2, 4, 2, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
            padding=(16, 8),
            font=FONTS["body_bold"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["surface"]), ("active", COLORS["surface"])],
            foreground=[("selected", COLORS["accent_dark"]), ("active", COLORS["text"])],
            expand=[("selected", (1, 1, 1, 0))],
        )

        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS["sidebar_elevated"],
            background=COLORS["sidebar_border"],
            foreground=COLORS["text_inverse"],
            arrowcolor=COLORS["muted_light"],
            bordercolor=COLORS["sidebar_border"],
            lightcolor=COLORS["sidebar_border"],
            darkcolor=COLORS["sidebar_border"],
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", COLORS["sidebar_elevated"])],
            foreground=[("readonly", COLORS["text_inverse"])],
        )

        style.configure(
            "Dark.TEntry",
            fieldbackground=COLORS["sidebar_elevated"],
            foreground=COLORS["text_inverse"],
            bordercolor=COLORS["sidebar_border"],
            lightcolor=COLORS["sidebar_border"],
            darkcolor=COLORS["sidebar_border"],
            insertcolor=COLORS["text_inverse"],
        )

        style.configure(
            "Dark.TSpinbox",
            fieldbackground=COLORS["sidebar_elevated"],
            foreground=COLORS["text_inverse"],
            arrowcolor=COLORS["muted_light"],
            bordercolor=COLORS["sidebar_border"],
            lightcolor=COLORS["sidebar_border"],
            darkcolor=COLORS["sidebar_border"],
        )

        style.configure(
            "Custom.Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=30,
            font=FONTS["body"],
            borderwidth=0,
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=COLORS["tree_header"],
            foreground=COLORS["text"],
            font=FONTS["body_bold"],
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", COLORS["accent_soft"])],
            foreground=[("selected", COLORS["accent_dark"])],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["border"],
            troughcolor=COLORS["bg"],
            bordercolor=COLORS["bg"],
            arrowcolor=COLORS["muted"],
        )

        plt.rcParams.update(
            {
                "axes.facecolor": COLORS["chart_bg"],
                "figure.facecolor": COLORS["surface"],
                "axes.edgecolor": COLORS["border"],
                "axes.labelcolor": COLORS["muted"],
                "xtick.color": COLORS["muted"],
                "ytick.color": COLORS["muted"],
                "grid.color": COLORS["border"],
                "grid.alpha": 0.55,
                "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "Segoe UI", "DejaVu Sans"],
                "axes.unicode_minus": False,
                "axes.titlesize": 12,
                "axes.titleweight": "bold",
            }
        )

    def _sidebar_label(self, parent, text: str, *, muted: bool = False, bold: bool = False) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["muted_light"] if muted else COLORS["text_inverse"],
            font=FONTS["section"] if bold else FONTS["body"],
            anchor="w",
        )

    def _sidebar_card(self, parent, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=COLORS["sidebar"], highlightthickness=0)
        outer.pack(fill=tk.X, pady=(0, 10))

        card = tk.Frame(
            outer,
            bg=COLORS["sidebar_elevated"],
            highlightbackground=COLORS["sidebar_border"],
            highlightthickness=1,
        )
        card.pack(fill=tk.X, padx=2)

        tk.Label(
            card,
            text=title,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["text_inverse"],
            font=FONTS["section"],
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(10, 6))

        body = tk.Frame(card, bg=COLORS["sidebar_elevated"])
        body.pack(fill=tk.X, padx=12, pady=(0, 12))
        return body

    def _action_button(self, parent, text: str, command, *, primary: bool = False) -> tk.Button:
        if primary:
            bg, fg, active = COLORS["accent"], "#ffffff", COLORS["accent_dark"]
            border = COLORS["accent"]
        else:
            bg, fg, active = COLORS["sidebar_elevated"], COLORS["text_inverse"], COLORS["sidebar_border"]
            border = COLORS["sidebar_border"]

        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief=tk.FLAT,
            font=FONTS["body_bold"],
            cursor="hand2",
            padx=10,
            pady=9,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
            bd=0,
        )
        btn.pack(fill=tk.X, pady=3)
        return btn

    def _bind_sidebar_scroll(self, canvas: tk.Canvas):
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind(_event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        header.pack(fill=tk.X)

        header_inner = tk.Frame(header, bg=COLORS["surface"])
        header_inner.pack(fill=tk.X, padx=20, pady=14)

        brand = tk.Frame(header_inner, bg=COLORS["accent"], width=4)
        brand.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))

        title_block = tk.Frame(header_inner, bg=COLORS["surface"])
        title_block.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(title_block, text="落點分析系統", bg=COLORS["surface"], fg=COLORS["text"], font=FONTS["title"]).pack(anchor="w")
        tk.Label(
            title_block,
            text="Landing Point Analyzer · 支撐阻力 · 策略回測",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONTS["subtitle"],
        ).pack(anchor="w", pady=(2, 0))

        self.header_ticker_var = tk.StringVar(value="尚未載入")
        tk.Label(
            header_inner,
            textvariable=self.header_ticker_var,
            bg=COLORS["accent_soft"],
            fg=COLORS["accent_dark"],
            font=FONTS["body_bold"],
            padx=14,
            pady=6,
        ).pack(side=tk.RIGHT)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        left_wrap = tk.Frame(body, bg=COLORS["sidebar"], width=320, highlightbackground=COLORS["sidebar_border"], highlightthickness=1)
        left_wrap.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        left_wrap.pack_propagate(False)

        canvas = tk.Canvas(left_wrap, width=300, bg=COLORS["sidebar"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(left_wrap, orient=tk.VERTICAL, command=canvas.yview)
        left = tk.Frame(canvas, bg=COLORS["sidebar"])
        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=left, anchor="nw", width=300)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_sidebar_scroll(canvas)

        sidebar_pad = tk.Frame(left, bg=COLORS["sidebar"])
        sidebar_pad.pack(fill=tk.X, padx=12, pady=12)

        # --- Strategy template ---
        strat_frame = self._sidebar_card(sidebar_pad, "策略模板")

        self.strategy_var = tk.StringVar(value="設備股")
        strat_combo = ttk.Combobox(
            strat_frame,
            textvariable=self.strategy_var,
            values=list(STRATEGY_TEMPLATES.keys()),
            state="readonly",
            width=28,
            style="Dark.TCombobox",
        )
        strat_combo.pack(fill=tk.X)
        strat_combo.bind("<<ComboboxSelected>>", self._on_strategy_change)

        self.strategy_desc_var = tk.StringVar()
        tk.Label(
            strat_frame,
            textvariable=self.strategy_desc_var,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["muted_light"],
            font=FONTS["body"],
            wraplength=250,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))

        self.strategy_summary_var = tk.StringVar()
        tk.Label(
            strat_frame,
            textvariable=self.strategy_summary_var,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            wraplength=250,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        # --- Ticker ---
        ticker_frame = self._sidebar_card(sidebar_pad, "標的")

        self._sidebar_label(ticker_frame, "市場").pack(anchor=tk.W)
        self.market_var = tk.StringVar(value="美股")
        market_combo = ttk.Combobox(
            ticker_frame,
            textvariable=self.market_var,
            values=list(MARKET_TICKERS.keys()),
            state="readonly",
            width=28,
            style="Dark.TCombobox",
        )
        market_combo.pack(fill=tk.X, pady=(4, 8))
        market_combo.bind("<<ComboboxSelected>>", self._on_market_change)

        self._sidebar_label(ticker_frame, "搜尋 / 選股").pack(anchor=tk.W)
        self.ticker_search_var = tk.StringVar()
        self.ticker_search_combo = ttk.Combobox(
            ticker_frame,
            textvariable=self.ticker_search_var,
            width=28,
            style="Dark.TCombobox",
        )
        self.ticker_search_combo.pack(fill=tk.X, pady=(4, 8))
        self.ticker_search_combo.bind("<<ComboboxSelected>>", self._on_ticker_search_select)
        self.ticker_search_combo.bind("<KeyRelease>", self._on_ticker_search_key)

        self._sidebar_label(ticker_frame, "自行輸入 Ticker").pack(anchor=tk.W)
        self.custom_ticker_var = tk.StringVar(value="AMAT")
        ttk.Entry(ticker_frame, textvariable=self.custom_ticker_var, width=30, style="Dark.TEntry").pack(fill=tk.X, pady=(4, 0))
        self._sidebar_label(ticker_frame, "台股輸入 2330 會自動轉為 2330.TW", muted=True).pack(anchor=tk.W, pady=(4, 0))

        # --- Custom params ---
        self.custom_frame = self._sidebar_card(sidebar_pad, "自訂參數")
        self._build_custom_params(self.custom_frame)

        # --- General settings ---
        general = self._sidebar_card(sidebar_pad, "一般設定")

        self._sidebar_label(general, "資料期間").pack(anchor=tk.W)
        self.period_var = tk.StringVar(value="12mo")
        ttk.Combobox(
            general,
            textvariable=self.period_var,
            values=["6mo", "12mo", "2y", "5y"],
            state="readonly",
            width=28,
            style="Dark.TCombobox",
        ).pack(fill=tk.X, pady=(4, 8))

        self._sidebar_label(general, "分析視窗（交易日）").pack(anchor=tk.W)
        self.lookback_var = tk.IntVar(value=42)
        ttk.Spinbox(general, from_=20, to=120, textvariable=self.lookback_var, width=28, style="Dark.TSpinbox").pack(
            fill=tk.X, pady=(4, 8)
        )

        self._sidebar_label(general, "回測模式").pack(anchor=tk.W)
        self.backtest_mode_var = tk.StringVar(value="rolling")
        ttk.Combobox(
            general,
            textvariable=self.backtest_mode_var,
            values=["rolling", "fixed"],
            state="readonly",
            width=28,
            style="Dark.TCombobox",
        ).pack(fill=tk.X, pady=(4, 0))

        actions = tk.Frame(sidebar_pad, bg=COLORS["sidebar"])
        actions.pack(fill=tk.X, pady=(4, 10))
        self._action_button(actions, "1. 載入資料", self.load_data)
        self._action_button(actions, "2. 落點分析", self.run_analysis)
        self._action_button(actions, "3. 執行回測", self.run_backtest)
        self._action_button(actions, "全部執行", self.run_all, primary=True)

        status_card = tk.Frame(
            sidebar_pad,
            bg=COLORS["sidebar_elevated"],
            highlightbackground=COLORS["sidebar_border"],
            highlightthickness=1,
        )
        status_card.pack(fill=tk.X, pady=(0, 4))

        tk.Label(status_card, text="狀態", bg=COLORS["sidebar_elevated"], fg=COLORS["muted_light"], font=FONTS["caption"]).pack(
            anchor=tk.W, padx=12, pady=(10, 2)
        )
        self.status_var = tk.StringVar(value="就緒")
        self.status_label = tk.Label(
            status_card,
            textvariable=self.status_var,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["success"],
            font=FONTS["body_bold"],
            wraplength=250,
            justify=tk.LEFT,
        )
        self.status_label.pack(anchor=tk.W, padx=12, pady=(0, 8))

        self.summary_var = tk.StringVar(value="")
        tk.Label(
            sidebar_pad,
            textvariable=self.summary_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            wraplength=270,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

        right = tk.Frame(body, bg=COLORS["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.levels_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.backtest_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.chart_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.notebook.add(self.levels_frame, text="  落點分析  ")
        self.notebook.add(self.backtest_frame, text="  回測結果  ")
        self.notebook.add(self.chart_frame, text="  圖表  ")

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
            row = tk.Frame(parent, bg=COLORS["sidebar_elevated"])
            row.pack(fill=tk.X, pady=2)
            self._sidebar_label(row, label).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=default / 100 if is_pct else default)
            self._param_vars[key] = var
            spin = ttk.Spinbox(
                row, from_=from_, to=to, textvariable=var, width=10, increment=1 if not is_pct else 1, style="Dark.TSpinbox"
            )
            spin.pack(side=tk.RIGHT)
            self._custom_widgets.append(spin)

        for key, label in [
            ("use_resistance_tp", "阻力停利"),
            ("breakout_buy", "突破加碼"),
            ("trend_ma_filter", "MA50 趨勢過濾"),
            ("require_macd", "MACD 多頭確認"),
            ("require_volume_shrink", "量縮確認"),
            ("require_candlestick", "K 棒確認"),
            ("use_macd_exit", "MACD 死叉出場"),
            ("volume_expand_breakout", "突破放量"),
        ]:
            var = tk.BooleanVar(value=False)
            self._param_vars[key] = var
            cb = tk.Checkbutton(
                parent,
                text=label,
                variable=var,
                command=self._on_custom_param_change,
                bg=COLORS["sidebar_elevated"],
                fg=COLORS["text_inverse"],
                selectcolor=COLORS["sidebar_border"],
                activebackground=COLORS["sidebar_elevated"],
                activeforeground=COLORS["text_inverse"],
                font=FONTS["body"],
                anchor="w",
            )
            cb.pack(anchor=tk.W, pady=2)
            self._custom_widgets.append(cb)

        row = tk.Frame(parent, bg=COLORS["sidebar_elevated"])
        row.pack(fill=tk.X, pady=2)
        self._sidebar_label(row, "訊號確認數").pack(side=tk.LEFT)
        var = tk.IntVar(value=0)
        self._param_vars["signal_confirm_min"] = var
        spin = ttk.Spinbox(row, from_=0, to=3, textvariable=var, width=10, command=self._on_custom_param_change, style="Dark.TSpinbox")
        spin.pack(side=tk.RIGHT)
        self._custom_widgets.append(spin)
        self._sidebar_label(parent, "0=全部通過，2=三選二", muted=True).pack(anchor=tk.W)

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
            self._param_vars["require_macd"].set(cfg.require_macd)
            self._param_vars["require_volume_shrink"].set(cfg.require_volume_shrink)
            self._param_vars["require_candlestick"].set(cfg.require_candlestick)
            self._param_vars["use_macd_exit"].set(cfg.use_macd_exit)
            self._param_vars["volume_expand_breakout"].set(cfg.volume_expand_breakout)
            self._param_vars["signal_confirm_min"].set(cfg.signal_confirm_min)

        tickers = self._template_tickers_for_market(name)

        self._refresh_ticker_options(tickers)

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
            require_macd=bool(self._param_vars["require_macd"].get()),
            require_volume_shrink=bool(self._param_vars["require_volume_shrink"].get()),
            require_candlestick=bool(self._param_vars["require_candlestick"].get()),
            use_macd_exit=bool(self._param_vars["use_macd_exit"].get()),
            volume_expand_breakout=bool(self._param_vars["volume_expand_breakout"].get()),
            signal_confirm_min=int(self._param_vars["signal_confirm_min"].get()),
        )

    def _template_tickers_for_market(self, strategy_name: str) -> dict[str, str]:
        market = self.market_var.get()
        catalog = dict(get_market_tickers(market))

        if strategy_name == "自訂":
            preferred: dict[str, str] = {}
            for group in TEMPLATE_TICKERS.values():
                for label, symbol in group.items():
                    if ticker_market(symbol) == market:
                        preferred[label] = symbol
            return {**preferred, **catalog}

        for label, symbol in TEMPLATE_TICKERS.get(strategy_name, {}).items():
            if ticker_market(symbol) == market:
                catalog[label] = symbol
        return catalog

    def _refresh_ticker_options(self, catalog: dict[str, str] | None = None):
        if catalog is None:
            catalog = self._template_tickers_for_market(self.strategy_var.get())
        self._ticker_catalog = catalog
        self._ticker_search_values = list(catalog.keys())
        self.ticker_search_combo["values"] = self._ticker_search_values
        if catalog:
            first_label = next(iter(catalog))
            self.ticker_search_var.set(first_label)
            self.custom_ticker_var.set(catalog[first_label])
        else:
            self.ticker_search_var.set("")
            self.custom_ticker_var.set("")

    def _filter_ticker_search_values(self, query: str) -> list[str]:
        q = query.strip().lower()
        if not q:
            return list(self._ticker_search_values)
        return [
            label
            for label in self._ticker_search_values
            if q in label.lower() or q in self._ticker_catalog.get(label, "").lower()
        ]

    def _on_market_change(self, _event=None):
        self._refresh_ticker_options(self._template_tickers_for_market(self.strategy_var.get()))

    def _on_ticker_search_key(self, _event=None):
        if _event is not None and _event.keysym in ("Up", "Down", "Return", "Tab"):
            return
        filtered = self._filter_ticker_search_values(self.ticker_search_var.get())
        self.ticker_search_combo["values"] = filtered

    def _on_ticker_search_select(self, _event=None):
        selected = self.ticker_search_var.get()
        if selected in self._ticker_catalog:
            self.custom_ticker_var.set(self._ticker_catalog[selected])
            return
        for label, symbol in self._ticker_catalog.items():
            if selected.lower() in label.lower() or selected.upper() == symbol.upper():
                self.ticker_search_var.set(label)
                self.custom_ticker_var.set(symbol)
                return

    def _on_ticker_preset(self, _event=None):
        self._on_ticker_search_select(_event)

    def _build_levels_tab(self):
        top = ttk.Frame(self.levels_frame, style="Surface.TFrame", padding=12)
        top.pack(fill=tk.BOTH, expand=True)
        cols = ("price", "strength", "distance", "methods")
        self.support_tree = self._make_tree(top, "支撐落點", cols, side=tk.LEFT, accent=COLORS["success"])
        self.resist_tree = self._make_tree(top, "阻力落點", cols, side=tk.RIGHT, accent=COLORS["danger"])

    def _build_backtest_tab(self):
        frame = ttk.Frame(self.backtest_frame, style="Surface.TFrame", padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        summary_card = tk.Frame(
            frame,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        summary_card.pack(fill=tk.X, pady=(0, 12))
        summary_inner = tk.Frame(summary_card, bg=COLORS["surface"])
        summary_inner.pack(fill=tk.X, padx=16, pady=14)

        tk.Label(summary_inner, text="回測摘要", bg=COLORS["surface"], fg=COLORS["muted"], font=FONTS["caption"]).pack(anchor=tk.W)
        self.backtest_summary = tk.Label(
            summary_inner,
            text="尚未執行回測",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONTS["kpi"],
            justify=tk.LEFT,
            wraplength=900,
        )
        self.backtest_summary.pack(anchor=tk.W, pady=(4, 0))

        table_card = tk.Frame(
            frame,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        table_card.pack(fill=tk.BOTH, expand=True)
        table_inner = tk.Frame(table_card, bg=COLORS["surface"])
        table_inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        cols = ("entry_date", "entry", "exit_date", "exit", "pnl", "reason", "support", "hold")
        self.trade_tree = ttk.Treeview(table_inner, columns=cols, show="headings", height=18, style="Custom.Treeview")
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
        widths = {
            "entry_date": 100,
            "entry": 80,
            "exit_date": 100,
            "exit": 80,
            "pnl": 70,
            "reason": 120,
            "support": 80,
            "hold": 70,
        }
        for col in cols:
            self.trade_tree.heading(col, text=headers[col])
            self.trade_tree.column(col, width=widths[col], anchor=tk.CENTER)
        self.trade_tree.tag_configure("gain", foreground=COLORS["success"])
        self.trade_tree.tag_configure("loss", foreground=COLORS["danger"])
        self.trade_tree.tag_configure("even", background=COLORS["tree_zebra"])
        self.trade_tree.pack(fill=tk.BOTH, expand=True)

    def _build_chart_tab(self):
        chart_card = tk.Frame(
            self.chart_frame,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        chart_card.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.fig, self.ax = plt.subplots(figsize=(9, 5), dpi=100)
        self.fig.patch.set_facecolor(COLORS["surface"])
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_card)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._draw_empty_chart()

    def _make_tree(self, parent, title, cols, side, accent: str):
        frame = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=4)

        header = tk.Frame(frame, bg=COLORS["surface"])
        header.pack(fill=tk.X, padx=12, pady=(12, 6))
        tk.Frame(header, bg=accent, width=3, height=16).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(header, text=title, bg=COLORS["surface"], fg=COLORS["text"], font=FONTS["section"]).pack(side=tk.LEFT)

        tree_wrap = tk.Frame(frame, bg=COLORS["surface"])
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 10))

        tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=20, style="Custom.Treeview")
        headers = {"price": "價位", "strength": "強度", "distance": "距現價%", "methods": "方法"}
        widths = {"price": 90, "strength": 60, "distance": 80, "methods": 280}
        for col in cols:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor=tk.W if col == "methods" else tk.CENTER)
        tree.tag_configure("stars_3", background=COLORS["strength_high"], foreground=COLORS["text"])
        tree.tag_configure("stars_2", background=COLORS["danger_soft"], foreground=COLORS["text"])
        tree.tag_configure("even", background=COLORS["tree_zebra"])
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def _level_row_tags(self, level, idx: int) -> tuple[str, ...]:
        if level.strength >= 3:
            return ("stars_3",)
        if level.strength == 2:
            return ("stars_2",)
        return ("even",) if idx % 2 else ()

    def _resolve_ticker(self) -> str:
        manual = self.custom_ticker_var.get().strip()
        if manual:
            return normalize_ticker_input(manual, self.market_var.get())
        selected = self.ticker_search_var.get().strip()
        if selected in self._ticker_catalog:
            return self._ticker_catalog[selected]
        return normalize_ticker_input(selected, self.market_var.get())

    def _set_status(self, text: str, *, tone: str = "info"):
        color = {
            "info": COLORS["success"],
            "warn": COLORS["warning"],
            "error": COLORS["danger"],
        }.get(tone, COLORS["success"])
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def load_data(self):
        try:
            self.engine = BacktestEngine(self._build_config_from_ui())
            self.ticker = self._resolve_ticker()
            self._set_status(f"正在載入 {self.ticker} ...", tone="warn")
            self.header_ticker_var.set(f"  {self.ticker}  ")
            self.df = fetch_stock_data(
                self.ticker,
                self.period_var.get(),
                lookback_days=self.lookback_var.get(),
            )
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
            self._set_status("載入失敗", tone="error")
            return
        self.run_analysis()

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
            self._set_status("分析失敗", tone="error")

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
            self._set_status("回測失敗", tone="error")

    def run_all(self):
        self.load_data()
        if self.df is not None:
            self.run_backtest()

    def _populate_levels(self):
        for tree in (self.support_tree, self.resist_tree):
            for item in tree.get_children():
                tree.delete(item)
        if not self.analysis:
            return
        current = self.analysis.current_price
        for idx, level in enumerate(self.analysis.supports):
            dist = (level.price / current - 1) * 100
            self.support_tree.insert(
                "",
                tk.END,
                values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)),
                tags=self._level_row_tags(level, idx),
            )
        for idx, level in enumerate(self.analysis.resistances):
            dist = (level.price / current - 1) * 100
            self.resist_tree.insert(
                "",
                tk.END,
                values=(f"{level.price:,.2f}", level.stars, f"{dist:+.1f}%", ", ".join(level.methods)),
                tags=self._level_row_tags(level, idx),
            )
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
                f"{result.strategy_name}  ·  {mode_label}  ·  "
                f"{len(result.trades)} 筆交易  ·  勝率 {result.win_rate:.0f}%  ·  "
                f"複利 {result.compound_return:+.1f}%  ·  Buy&Hold {result.buy_hold_pct:+.1f}%"
            )
        )
        for idx, trade in enumerate(result.trades):
            pnl = trade.pnl_pct
            tags = []
            if idx % 2:
                tags.append("even")
            tags.append("gain" if pnl >= 0 else "loss")
            self.trade_tree.insert(
                "",
                tk.END,
                values=(
                    trade.entry_date.date(),
                    f"{trade.entry_price:,.2f}",
                    trade.exit_date.date(),
                    f"{trade.exit_price:,.2f}",
                    f"{pnl:+.1f}",
                    trade.reason,
                    f"{trade.support_price:,.2f}",
                    trade.hold_days,
                ),
                tags=tuple(tags),
            )

    def _draw_empty_chart(self):
        self.ax.clear()
        self.ax.set_facecolor(COLORS["chart_bg"])
        self.ax.set_title("請載入資料後顯示圖表", color=COLORS["muted"], pad=12)
        self.ax.text(
            0.5,
            0.5,
            "載入股票資料後，這裡會顯示價格走勢、均線與買賣點",
            transform=self.ax.transAxes,
            ha="center",
            va="center",
            color=COLORS["muted"],
            fontsize=10,
        )
        self.ax.grid(True, alpha=0.35)
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["border"])
        self.canvas.draw()

    def _draw_price_chart(self):
        if self.df is None:
            self._draw_empty_chart()
            return
        self.ax.clear()
        self.ax.set_facecolor(COLORS["chart_bg"])
        plot_df = add_indicators(self.df.tail(180))
        dates = plot_df.index
        self.ax.plot(dates, plot_df["Close"], color=COLORS["accent_dark"], linewidth=2.2, label="Close", zorder=3)
        if plot_df["MA20"].notna().any():
            self.ax.plot(dates, plot_df["MA20"], color="#f59e0b", linewidth=1.2, alpha=0.85, label="MA20", zorder=2)
        if plot_df["MA50"].notna().any():
            self.ax.plot(dates, plot_df["MA50"], color="#10b981", linewidth=1.2, alpha=0.85, label="MA50", zorder=2)
        if self.analysis:
            for level in self.analysis.supports:
                self.ax.axhline(level.price, color=COLORS["success"], linestyle="--", alpha=0.4, linewidth=1, zorder=1)
            for level in self.analysis.resistances:
                self.ax.axhline(level.price, color=COLORS["danger"], linestyle="--", alpha=0.4, linewidth=1, zorder=1)
        if self.backtest_result and self.backtest_result.trades:
            for trade in self.backtest_result.trades:
                self.ax.scatter(
                    trade.entry_date,
                    trade.entry_price,
                    color=COLORS["success"],
                    s=70,
                    zorder=5,
                    edgecolors="white",
                    linewidths=0.8,
                )
                self.ax.scatter(
                    trade.exit_date,
                    trade.exit_price,
                    color=COLORS["danger"],
                    s=70,
                    zorder=5,
                    edgecolors="white",
                    linewidths=0.8,
                )
                self.ax.plot(
                    [trade.entry_date, trade.exit_date],
                    [trade.entry_price, trade.exit_price],
                    color=COLORS["muted_light"],
                    alpha=0.55,
                    linewidth=1,
                    zorder=4,
                )
        legend_items = [
            Line2D([0], [0], color=COLORS["accent_dark"], linewidth=2.2, label="Close"),
            Line2D([0], [0], color="#f59e0b", linewidth=1.2, label="MA20"),
            Line2D([0], [0], color="#10b981", linewidth=1.2, label="MA50"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["success"], markersize=8, label="Buy"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["danger"], markersize=8, label="Sell"),
        ]
        self.ax.legend(handles=legend_items, loc="upper left", frameon=True, fancybox=True, framealpha=0.95)
        self.ax.set_title(f"{self.ticker}  ·  {self.strategy_var.get()}", color=COLORS["text"], pad=12)
        self.ax.grid(True, alpha=0.35)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["border"])
        self.fig.autofmt_xdate()
        self.canvas.draw()


def main():
    app = LandingAnalysisApp()
    app.mainloop()


if __name__ == "__main__":
    main()
