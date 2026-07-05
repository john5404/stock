#!/usr/bin/env python3
"""Landing point analysis desktop UI."""

import signal
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.env_config import load_local_env

load_local_env()

from landing_analysis.analyzer import LandingAnalyzer, LevelCluster
from landing_analysis.backtest import BacktestEngine
from landing_analysis.data_fetcher import (
    detect_market_from_input,
    fetch_stock_data,
    fetch_tw_institutional_data,
    get_market_tickers,
    normalize_ticker_input,
    ticker_market,
)
from landing_analysis.indicators import ensure_indicators
from landing_analysis.scheme_c_charts import (
    apply_price_axis_format,
    draw_empty_scheme_c,
    draw_institutional_chart,
    draw_scheme_c,
    format_methods_zh,
    refresh_level_price_labels,
)
from landing_analysis.portfolio_store import (
    PortfolioPieSlice,
    PortfolioRow,
    PortfolioSection,
    QUOTE_POLL_MS,
    apply_quotes,
    calc_position_stats,
    calc_section,
    default_portfolio_path,
    fetch_quotes,
    load_portfolio,
    portfolio_market_slices,
    portfolio_total_twd,
    position_pie_slices,
    save_portfolio,
)
from landing_analysis.strategies import STRATEGY_TEMPLATES, TEMPLATE_TICKERS, StrategyConfig, get_template

COLORS = {
    # Low-contrast OLED-style dark palette
    "bg": "#030405",
    "surface": "#080a0d",
    "surface_elevated": "#0d1014",
    "sidebar": "#030405",
    "sidebar_elevated": "#0a0c10",
    "sidebar_border": "#151a22",
    "accent": "#4a7fa8",
    "accent_dark": "#3d6d92",
    "accent_soft": "#101820",
    "text": "#9aa3ad",
    "text_inverse": "#9aa3ad",
    "muted": "#5f6770",
    "muted_light": "#4a5159",
    "border": "#171c24",
    "success": "#3d8f7a",
    "success_soft": "#0d1412",
    "danger": "#b86a62",
    "danger_soft": "#140d0c",
    "strength_high": "#8f4a4a",
    "warning": "#b8894a",
    "warning_soft": "#171008",
    "long_row": "#0a1310",
    "long_row_alt": "#081210",
    "short_row": "#150c0b",
    "short_row_alt": "#120a09",
    "long_pill": "#2f7a68",
    "short_pill": "#7a4440",
    "chart_bg": "#050608",
    "tree_header": "#0a0d11",
    "tree_zebra": "#07090c",
    "grid": "#141820",
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

LEVEL_STRENGTH_LEGEND_LINES = (
    "圖表橫線旁的 ★ 與下方「強度 ★」欄相同",
    "★ 愈多＝愈多技術指標在相近價位匯聚（±2%）",
    "1 顆＝1 項指標 · 最多顯示 5 顆",
)

PERIOD_LABELS: dict[str, str] = {
    "6mo": "6 個月",
    "12mo": "12 個月",
    "2y": "2 年",
    "5y": "5 年",
}
PERIOD_CODES: dict[str, str] = {label: code for code, label in PERIOD_LABELS.items()}

BACKTEST_MODE_LABELS: dict[str, str] = {
    "rolling": "滾動視窗",
    "fixed": "固定前 N 日",
}
BACKTEST_MODE_CODES: dict[str, str] = {label: code for code, label in BACKTEST_MODE_LABELS.items()}

APP_MODES = ("落點分析", "股市配比")

SIDEBAR_PANEL_WIDTH = 252
SIDEBAR_CONTENT_WIDTH = 236
SIDEBAR_WRAPLENGTH = 218
SIDEBAR_FIELD_WIDTH = 22
PORTFOLIO_CHART_WIDTH = 560
PORTFOLIO_PIE_FIGSIZE = (5.36, 12.5)
PORTFOLIO_COL_WIDTHS = {
    "tw": (100, 80, 48, 56, 64, 64, 56, 80, 52, 32),
    "us": (100, 48, 56, 64, 64, 56, 80, 80, 52, 32),
}
PORTFOLIO_KPI_SPECS = (
    ("grand", "總資產 (TWD)", "text"),
    ("tw", "台股", "success"),
    ("us", "美股", "accent"),
    ("budget", "預算使用", "muted"),
)


class LandingAnalysisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("落點分析 · Landing Point Analyzer")
        self.geometry("1360x900")
        self.minsize(1140, 760)
        self.configure(bg=COLORS["bg"])

        self.df: pd.DataFrame | None = None
        self.df_enriched: pd.DataFrame | None = None
        self.df_institutional: pd.DataFrame | None = None
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
        self._levels_default_xlim: tuple[float, float] | None = None
        self._levels_default_ylim: tuple[float, float] | None = None
        self._price_pan_ref: tuple[float, float, tuple[float, float], tuple[float, float]] | None = None
        self._levels_scroll_after_id: str | None = None
        self._levels_pan_after_id: str | None = None
        self._action_buttons: list[tk.Button] = []
        self._busy = False
        self._inst_note = ""
        self._portfolio_sections: list[PortfolioSection] = []
        self._portfolio_quotes: dict[str, dict] = {}
        self._portfolio_path = default_portfolio_path()
        self._portfolio_quote_after_id: str | None = None
        self._portfolio_quote_fetching = False

        self._setup_theme()
        self._build_ui()
        self._bind_shortcuts()
        self._apply_strategy_template("設備股")

        self.protocol("WM_DELETE_WINDOW", self._quit_app)
        self.bind_all("<Control-c>", lambda _e: self._quit_app())

    def _quit_app(self):
        try:
            self._stop_portfolio_quote_poll()
        except Exception:
            pass
        try:
            self.quit()
        finally:
            self.destroy()

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
            background=[("selected", COLORS["surface_elevated"]), ("active", COLORS["surface"])],
            foreground=[("selected", COLORS["accent"]), ("active", COLORS["text"])],
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
            foreground=[("selected", COLORS["text"])],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["border"],
            troughcolor=COLORS["bg"],
            bordercolor=COLORS["bg"],
            arrowcolor=COLORS["muted"],
        )
        style.configure(
            "Horizontal.TScrollbar",
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
                "grid.color": COLORS["grid"],
                "grid.alpha": 0.22,
                "text.color": COLORS["text"],
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

    def _sidebar_card_section(self, parent, title: str) -> tuple[tk.Frame, tk.Frame]:
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
        return outer, body

    def _action_button(self, parent, text: str, command, *, primary: bool = False) -> tk.Button:
        if primary:
            bg, fg, active = COLORS["accent"], "#b8c4d0", COLORS["accent_dark"]
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
        self._action_buttons.append(btn)
        return btn

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        cursor = "watch" if busy else ""
        try:
            self.configure(cursor=cursor)
        except tk.TclError:
            pass
        for btn in self._action_buttons:
            try:
                btn.configure(state=state)
            except tk.TclError:
                pass

    def _period_code(self) -> str:
        value = self.period_var.get()
        return PERIOD_CODES.get(value, value)

    def _backtest_mode_code(self) -> str:
        value = self.backtest_mode_var.get()
        return BACKTEST_MODE_CODES.get(value, value)

    def _update_market_badge(self, query: str = ""):
        text = (query or self.ticker_search_var.get()).strip()
        if not text:
            self.market_badge_var.set("")
            return
        market = detect_market_from_input(text)
        self.market_badge_var.set(market)
        badge_bg = COLORS["success_soft"] if market == "台股" else COLORS["accent_soft"]
        badge_fg = COLORS["success"] if market == "台股" else COLORS["accent"]
        self.market_badge_label.configure(bg=badge_bg, fg=badge_fg)

    def _sync_ticker_from_search(self):
        selected = self.ticker_search_var.get().strip()
        if selected in self._ticker_catalog:
            self.custom_ticker_var.set(self._ticker_catalog[selected])
        elif selected:
            self.custom_ticker_var.set(normalize_ticker_input(selected))
        self._update_market_badge(selected)

    def _bind_shortcuts(self):
        self.bind("<Control-Return>", lambda _e: self.load_data())
        self.bind("<Control-r>", lambda _e: self.run_backtest())
        self.bind("<Control-l>", lambda _e: self.run_all())

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
        self.header_ticker_var = tk.StringVar(value="尚未載入")
        self.market_badge_var = tk.StringVar(value="")
        self.market_badge_label = tk.Label(self, textvariable=self.market_badge_var)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        left_wrap = tk.Frame(body, bg=COLORS["sidebar"], width=SIDEBAR_PANEL_WIDTH, highlightbackground=COLORS["sidebar_border"], highlightthickness=1)
        left_wrap.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        left_wrap.pack_propagate(False)

        canvas = tk.Canvas(left_wrap, width=SIDEBAR_CONTENT_WIDTH, bg=COLORS["sidebar"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(left_wrap, orient=tk.VERTICAL, command=canvas.yview)
        left = tk.Frame(canvas, bg=COLORS["sidebar"])
        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=left, anchor="nw", width=SIDEBAR_CONTENT_WIDTH)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_sidebar_scroll(canvas)

        sidebar_pad = tk.Frame(left, bg=COLORS["sidebar"])
        sidebar_pad.pack(fill=tk.X, padx=12, pady=12)

        mode_frame = self._sidebar_card(sidebar_pad, "功能")
        self.app_mode_var = tk.StringVar(value=APP_MODES[0])
        mode_btn_row = tk.Frame(mode_frame, bg=COLORS["sidebar_elevated"])
        mode_btn_row.pack(fill=tk.X)
        self._mode_buttons: dict[str, tk.Button] = {}
        for mode in APP_MODES:
            btn = tk.Button(
                mode_btn_row,
                text=mode,
                command=lambda m=mode: self._set_app_mode(m),
                bg=COLORS["sidebar_elevated"],
                fg=COLORS["text_inverse"],
                activebackground=COLORS["sidebar_border"],
                activeforeground=COLORS["text_inverse"],
                relief=tk.FLAT,
                font=FONTS["body_bold"],
                cursor="hand2",
                padx=6,
                pady=8,
                highlightthickness=1,
                highlightbackground=COLORS["sidebar_border"],
                bd=0,
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4 if mode == APP_MODES[0] else 0))
            self._mode_buttons[mode] = btn

        self.analysis_sidebar = tk.Frame(sidebar_pad, bg=COLORS["sidebar"])
        self.portfolio_sidebar = tk.Frame(sidebar_pad, bg=COLORS["sidebar"])

        # --- Strategy template ---
        strat_frame = self._sidebar_card(self.analysis_sidebar, "策略模板")

        self.strategy_var = tk.StringVar(value="設備股")
        strat_combo = ttk.Combobox(
            strat_frame,
            textvariable=self.strategy_var,
            values=list(STRATEGY_TEMPLATES.keys()),
            state="readonly",
            width=SIDEBAR_FIELD_WIDTH,
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
            wraplength=SIDEBAR_WRAPLENGTH - 8,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))

        self.strategy_summary_var = tk.StringVar()
        tk.Label(
            strat_frame,
            textvariable=self.strategy_summary_var,
            bg=COLORS["sidebar_elevated"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            wraplength=SIDEBAR_WRAPLENGTH - 8,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        # --- Ticker ---
        ticker_frame = self._sidebar_card(self.analysis_sidebar, "標的")

        self._sidebar_label(ticker_frame, "股票代號 / 名稱").pack(anchor=tk.W)
        self.ticker_search_var = tk.StringVar()
        self.custom_ticker_var = tk.StringVar(value="AMAT")
        self.ticker_search_combo = ttk.Combobox(
            ticker_frame,
            textvariable=self.ticker_search_var,
            width=SIDEBAR_FIELD_WIDTH,
            style="Dark.TCombobox",
        )
        self.ticker_search_combo.pack(fill=tk.X, pady=(4, 4))
        self.ticker_search_combo.bind("<<ComboboxSelected>>", self._on_ticker_search_select)
        self.ticker_search_combo.bind("<KeyRelease>", self._on_ticker_search_key)
        self.ticker_search_combo.bind("<Return>", self._on_ticker_search_enter)
        self._sidebar_label(
            ticker_frame,
            "輸入中文或數字→台股，英文→美股 · Enter 載入",
            muted=True,
        ).pack(anchor=tk.W, pady=(0, 0))

        # --- Custom params ---
        self.custom_params_section, self.custom_frame = self._sidebar_card_section(self.analysis_sidebar, "自訂參數")
        self._build_custom_params(self.custom_frame)

        # --- General settings ---
        general = self._sidebar_card(self.analysis_sidebar, "一般設定")

        self._sidebar_label(general, "資料期間").pack(anchor=tk.W)
        self.period_var = tk.StringVar(value=PERIOD_LABELS["12mo"])
        ttk.Combobox(
            general,
            textvariable=self.period_var,
            values=list(PERIOD_LABELS.values()),
            state="readonly",
            width=SIDEBAR_FIELD_WIDTH,
            style="Dark.TCombobox",
        ).pack(fill=tk.X, pady=(4, 8))

        self._sidebar_label(general, "分析視窗（交易日）").pack(anchor=tk.W)
        self.lookback_var = tk.IntVar(value=42)
        ttk.Spinbox(general, from_=20, to=120, textvariable=self.lookback_var, width=SIDEBAR_FIELD_WIDTH, style="Dark.TSpinbox").pack(
            fill=tk.X, pady=(4, 8)
        )

        self._sidebar_label(general, "回測模式").pack(anchor=tk.W)
        self.backtest_mode_var = tk.StringVar(value=BACKTEST_MODE_LABELS["rolling"])
        ttk.Combobox(
            general,
            textvariable=self.backtest_mode_var,
            values=list(BACKTEST_MODE_LABELS.values()),
            state="readonly",
            width=SIDEBAR_FIELD_WIDTH,
            style="Dark.TCombobox",
        ).pack(fill=tk.X, pady=(4, 0))

        inst_card = self._sidebar_card(self.analysis_sidebar, "三大法人圖")
        self.inst_show_foreign_var = tk.BooleanVar(value=True)
        self.inst_show_trust_var = tk.BooleanVar(value=True)
        self.inst_show_dealer_var = tk.BooleanVar(value=True)
        for label, var in (
            ("外資", self.inst_show_foreign_var),
            ("投信", self.inst_show_trust_var),
            ("自營", self.inst_show_dealer_var),
        ):
            tk.Checkbutton(
                inst_card,
                text=label,
                variable=var,
                command=self._on_institutional_filter_change,
                bg=COLORS["sidebar_elevated"],
                fg=COLORS["text_inverse"],
                selectcolor=COLORS["sidebar_border"],
                activebackground=COLORS["sidebar_elevated"],
                activeforeground=COLORS["text_inverse"],
                font=FONTS["body"],
                anchor="w",
            ).pack(anchor=tk.W, pady=2)
        self._sidebar_label(inst_card, "三項全勾選時顯示合計線", muted=True).pack(anchor=tk.W, pady=(2, 0))

        tk.Label(
            self.analysis_sidebar,
            text="操作",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_light"],
            font=FONTS["section"],
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 4))

        actions = tk.Frame(self.analysis_sidebar, bg=COLORS["sidebar"])
        actions.pack(fill=tk.X, pady=(0, 6))
        self._action_button(actions, "載入並分析", self.load_data, primary=True)
        self._action_button(actions, "重新分析", self.run_analysis)
        self._action_button(actions, "執行回測", self.run_backtest)
        self._action_button(actions, "一鍵全流程", self.run_all)

        tk.Label(
            self.analysis_sidebar,
            text="Ctrl+Enter 載入 · Ctrl+R 回測 · Ctrl+L 全流程",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
            wraplength=SIDEBAR_WRAPLENGTH,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        self.summary_var = tk.StringVar(value="")
        self._analysis_summary_label = tk.Label(
            self.analysis_sidebar,
            textvariable=self.summary_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            wraplength=SIDEBAR_WRAPLENGTH,
            justify=tk.LEFT,
        )
        self._analysis_summary_label.pack(anchor=tk.W, pady=(6, 0))

        self._build_portfolio_sidebar(self.portfolio_sidebar)

        self._shared_sidebar = tk.Frame(sidebar_pad, bg=COLORS["sidebar"])
        status_card = tk.Frame(
            self._shared_sidebar,
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
            wraplength=SIDEBAR_WRAPLENGTH - 8,
            justify=tk.LEFT,
        )
        self.status_label.pack(anchor=tk.W, padx=12, pady=(0, 8))
        self._shared_sidebar.pack(fill=tk.X)

        right = tk.Frame(body, bg=COLORS["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.analysis_main = tk.Frame(right, bg=COLORS["bg"])
        self.portfolio_main = tk.Frame(right, bg=COLORS["bg"])
        self._build_portfolio_tab()

        self.notebook = ttk.Notebook(self.analysis_main)

        self.levels_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.backtest_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.chart_frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.notebook.add(self.levels_frame, text="  落點分析  ")
        self.notebook.add(self.backtest_frame, text="  回測結果  ")
        self.notebook.add(self.chart_frame, text="  交易走勢  ")

        self._build_levels_tab()
        self._build_backtest_tab()
        self._build_chart_tab()
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self._set_app_mode(APP_MODES[0])

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
        if enabled:
            if not self.custom_params_section.winfo_ismapped():
                self.custom_params_section.pack(fill=tk.X, pady=(0, 10))
        else:
            self.custom_params_section.pack_forget()

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

        tickers = self._catalog_for_query(self.ticker_search_var.get())

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

    def _catalog_for_query(self, query: str) -> dict[str, str]:
        market = detect_market_from_input(query)
        return self._template_tickers(self.strategy_var.get(), market)

    def _template_tickers(self, strategy_name: str, market: str) -> dict[str, str]:
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

    def _refresh_ticker_options(self, catalog: dict[str, str] | None = None, *, preserve: bool = True):
        if catalog is None:
            catalog = self._catalog_for_query(self.ticker_search_var.get())
        self._ticker_catalog = catalog
        self._ticker_search_values = list(catalog.keys())
        self.ticker_search_combo["values"] = self._ticker_search_values

        prev_symbol = self.custom_ticker_var.get().strip()
        prev_query = self.ticker_search_var.get().strip()

        if preserve and (prev_symbol or prev_query):
            if prev_symbol:
                for label, symbol in catalog.items():
                    if symbol.upper() == prev_symbol.upper():
                        self.ticker_search_var.set(label)
                        self.custom_ticker_var.set(symbol)
                        self._update_market_badge(label)
                        return
            if prev_query in catalog:
                self.ticker_search_var.set(prev_query)
                self.custom_ticker_var.set(catalog[prev_query])
                self._update_market_badge(prev_query)
                return
            for label, symbol in catalog.items():
                if prev_query and (
                    prev_query.lower() in label.lower() or prev_query.upper() == symbol.upper()
                ):
                    self.ticker_search_var.set(label)
                    self.custom_ticker_var.set(symbol)
                    self._update_market_badge(label)
                    return
            resolved = prev_symbol or normalize_ticker_input(prev_query)
            self.ticker_search_var.set(prev_query or prev_symbol)
            self.custom_ticker_var.set(resolved)
            self._update_market_badge(prev_query or prev_symbol)
            return

        if catalog:
            first_label = next(iter(catalog))
            self.ticker_search_var.set(first_label)
            self.custom_ticker_var.set(catalog[first_label])
        else:
            self.ticker_search_var.set("")
            self.custom_ticker_var.set("")
        self._update_market_badge(self.ticker_search_var.get())

    def _filter_ticker_search_values(self, query: str) -> list[str]:
        q = query.strip().lower()
        if not q:
            return list(self._ticker_search_values)
        return [
            label
            for label in self._ticker_search_values
            if q in label.lower() or q in self._ticker_catalog.get(label, "").lower()
        ]

    def _on_ticker_search_key(self, _event=None):
        if _event is not None and _event.keysym in ("Up", "Down", "Return", "Tab"):
            return
        query = self.ticker_search_var.get()
        catalog = self._catalog_for_query(query)
        self._ticker_catalog = catalog
        self._ticker_search_values = list(catalog.keys())
        filtered = self._filter_ticker_search_values(query)
        self.ticker_search_combo["values"] = filtered
        self._sync_ticker_from_search()

    def _on_ticker_search_enter(self, _event=None):
        if self._busy:
            return "break"
        self._sync_ticker_from_search()
        self.load_data()
        return "break"

    def _on_ticker_search_select(self, _event=None):
        selected = self.ticker_search_var.get()
        if selected in self._ticker_catalog:
            self.custom_ticker_var.set(self._ticker_catalog[selected])
            self._update_market_badge(selected)
            return
        for label, symbol in self._ticker_catalog.items():
            if selected.lower() in label.lower() or selected.upper() == symbol.upper():
                self.ticker_search_var.set(label)
                self.custom_ticker_var.set(symbol)
                self._update_market_badge(label)
                return
        self._sync_ticker_from_search()

    def _on_ticker_preset(self, _event=None):
        self._on_ticker_search_select(_event)

    def _build_strength_legend(self, parent: tk.Frame) -> None:
        box = tk.Frame(
            parent,
            bg=COLORS["surface_elevated"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        box.pack(fill=tk.X, padx=4, pady=(0, 8))
        inner = tk.Frame(box, bg=COLORS["surface_elevated"])
        inner.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(
            inner,
            text="★ 強度說明",
            bg=COLORS["surface_elevated"],
            fg=COLORS["text"],
            font=FONTS["body_bold"],
        ).pack(anchor=tk.W)
        for line in LEVEL_STRENGTH_LEGEND_LINES:
            tk.Label(
                inner,
                text=line,
                bg=COLORS["surface_elevated"],
                fg=COLORS["muted"],
                font=FONTS["caption"],
                wraplength=248,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(2, 0))

    def _build_level_mini_table(
        self,
        parent: tk.Frame,
        *,
        title: str,
        subtitle: str,
        tag: str,
        tag_color: str,
    ) -> ttk.Treeview:
        wrap = tk.Frame(parent, bg=COLORS["surface"])
        wrap.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        head = tk.Frame(wrap, bg=COLORS["surface"])
        head.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(head, text=title, bg=COLORS["surface"], fg=tag_color, font=FONTS["body_bold"]).pack(anchor=tk.W)
        if subtitle:
            tk.Label(head, text=subtitle, bg=COLORS["surface"], fg=COLORS["muted"], font=FONTS["caption"]).pack(anchor=tk.W)

        cols = ("price", "strength", "methods")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=6, style="Custom.Treeview")
        headers = {"price": "價位", "strength": "強度 ★", "methods": "曲線來源"}
        widths = {"price": 72, "strength": 44, "methods": 148}
        for col in cols:
            tree.heading(col, text=headers[col])
            anchor = tk.CENTER if col != "methods" else tk.W
            tree.column(col, width=widths[col], anchor=anchor, stretch=(col == "methods"))
        tree.tag_configure(tag, foreground=tag_color)
        tree.tag_configure("even", background=COLORS["tree_zebra"])
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def _build_levels_tab(self):
        toolbar = tk.Frame(self.levels_frame, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 0))

        tk.Label(
            toolbar,
            text="落點圖：滾輪縮放 · 左鍵拖曳平移 · 雙擊重置",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(side=tk.LEFT)

        reset_btn = tk.Button(
            toolbar,
            text="重置視野",
            command=self._reset_levels_zoom,
            bg=COLORS["surface_elevated"],
            fg=COLORS["text"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"],
            relief=tk.FLAT,
            font=FONTS["caption"],
            padx=10,
            pady=4,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            bd=0,
        )
        reset_btn.pack(side=tk.RIGHT)

        levels_body = tk.Frame(self.levels_frame, bg=COLORS["bg"])
        levels_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        table_card = tk.Frame(
            levels_body,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            width=292,
        )
        table_card.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        table_card.pack_propagate(False)

        table_header = tk.Frame(table_card, bg=COLORS["surface"])
        table_header.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(
            table_header,
            text="落點一覽",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONTS["section"],
        ).pack(anchor=tk.W)
        tk.Label(
            table_header,
            text="價位 · 強度 ★ · 曲線來源",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(anchor=tk.W, pady=(2, 0))

        tables_col = tk.Frame(table_card, bg=COLORS["surface"])
        tables_col.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        self._build_strength_legend(tables_col)

        self.support_tree = self._build_level_mini_table(
            tables_col,
            title="支撐價位",
            subtitle="",
            tag="support",
            tag_color=COLORS["success"],
        )
        self.resistance_tree = self._build_level_mini_table(
            tables_col,
            title="阻力價位",
            subtitle="",
            tag="resistance",
            tag_color=COLORS["danger"],
        )

        chart_card = tk.Frame(
            levels_body,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        chart_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        chart_card_inner = chart_card

        self.levels_fig = plt.figure(figsize=(11, 8.2), dpi=100)
        self.levels_fig.patch.set_facecolor(COLORS["surface"])
        grid = GridSpec(
            3,
            2,
            figure=self.levels_fig,
            width_ratios=[2.4, 1],
            height_ratios=[1.1, 1.0, 0.75],
            wspace=0.28,
            hspace=0.38,
        )
        self.ax_price_levels = self.levels_fig.add_subplot(grid[0:2, 0])
        self.ax_ladder = self.levels_fig.add_subplot(grid[0, 1])
        self.ax_volume_profile = self.levels_fig.add_subplot(grid[1, 1])
        self.ax_institutional = self.levels_fig.add_subplot(grid[2, :])

        self.levels_canvas = FigureCanvasTkAgg(self.levels_fig, master=chart_card_inner)
        self.levels_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._levels_scroll_cid = self.levels_canvas.mpl_connect("scroll_event", self._on_levels_scroll)
        self._levels_click_cid = self.levels_canvas.mpl_connect("button_press_event", self._on_levels_click)
        self._levels_motion_cid = self.levels_canvas.mpl_connect("motion_notify_event", self._on_levels_motion)
        self._levels_release_cid = self.levels_canvas.mpl_connect("button_release_event", self._on_levels_release)
        self._draw_empty_levels_chart()

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
        toolbar = tk.Frame(self.chart_frame, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 0))
        tk.Label(
            toolbar,
            text="近 180 日收盤 · 均線 · 支撐阻力 · 回測買賣點",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(side=tk.LEFT)

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

    def _draw_empty_levels_chart(self):
        draw_empty_scheme_c(
            self.levels_fig,
            self.ax_price_levels,
            self.ax_ladder,
            self.ax_volume_profile,
            self.ax_institutional,
            COLORS,
        )
        self.levels_canvas.draw()

    def _draw_levels_scheme_c(self):
        if self.df is None or not self.analysis:
            self._draw_empty_levels_chart()
            return
        draw_scheme_c(
            self.levels_fig,
            self.ax_price_levels,
            self.ax_ladder,
            self.ax_volume_profile,
            self.ax_institutional,
            self._chart_df(),
            self.analysis,
            ticker=self.ticker,
            strategy_name=self.strategy_var.get(),
            colors=COLORS,
            lookback_days=self.lookback_var.get(),
            inst_df=self.df_institutional,
            is_tw=ticker_market(self.ticker) == "台股",
            inst_show_foreign=self.inst_show_foreign_var.get(),
            inst_show_trust=self.inst_show_trust_var.get(),
            inst_show_dealer=self.inst_show_dealer_var.get(),
        )
        self._capture_levels_zoom_defaults()
        self.levels_canvas.draw()

    def _institutional_show_flags(self) -> tuple[bool, bool, bool]:
        return (
            self.inst_show_foreign_var.get(),
            self.inst_show_trust_var.get(),
            self.inst_show_dealer_var.get(),
        )

    def _redraw_institutional_chart(self):
        show_foreign, show_trust, show_dealer = self._institutional_show_flags()
        draw_institutional_chart(
            self.ax_institutional,
            self.df_institutional,
            colors=COLORS,
            lookback_days=self.lookback_var.get(),
            ticker=self.ticker,
            is_tw=ticker_market(self.ticker) == "台股",
            show_foreign=show_foreign,
            show_trust=show_trust,
            show_dealer=show_dealer,
        )
        self.levels_canvas.draw_idle()

    def _on_institutional_filter_change(self):
        if self.df is None:
            return
        self._redraw_institutional_chart()

    def _capture_levels_zoom_defaults(self):
        self._levels_default_xlim = self.ax_price_levels.get_xlim()
        self._levels_default_ylim = self.ax_price_levels.get_ylim()

    def _on_levels_scroll(self, event):
        if event.inaxes != self.ax_price_levels or event.xdata is None or event.ydata is None:
            return
        if self._levels_default_xlim is None or self._levels_default_ylim is None:
            return

        ax = self.ax_price_levels
        scale = 0.9 if event.button == "up" else 1.1

        xmin, xmax = ax.get_xlim()
        xw = xmax - xmin
        xrel = (event.xdata - xmin) / xw if xw else 0.5
        new_xw = xw * scale
        new_xmin = event.xdata - new_xw * xrel
        new_xmax = new_xmin + new_xw

        ymin, ymax = ax.get_ylim()
        yw = ymax - ymin
        yrel = (event.ydata - ymin) / yw if yw else 0.5
        new_yw = yw * scale
        new_ymin = event.ydata - new_yw * yrel
        new_ymax = new_ymin + new_yw

        def_xmin, def_xmax = self._levels_default_xlim
        def_ymin, def_ymax = self._levels_default_ylim
        min_xw = (def_xmax - def_xmin) * 0.04
        min_yw = (def_ymax - def_ymin) * 0.02
        max_xw = (def_xmax - def_xmin) * 4.0
        max_yw = (def_ymax - def_ymin) * 4.0

        new_xw = min(max(new_xw, min_xw), max_xw)
        new_yw = min(max(new_yw, min_yw), max_yw)
        new_xmin = event.xdata - new_xw * xrel
        new_xmax = new_xmin + new_xw
        new_ymin = event.ydata - new_yw * yrel
        new_ymax = new_ymin + new_yw

        ax.set_xlim(new_xmin, new_xmax)
        ax.set_ylim(new_ymin, new_ymax)
        self._schedule_levels_pan_draw()
        self._schedule_levels_axis_refresh()

    def _cancel_levels_axis_refresh(self):
        if self._levels_scroll_after_id:
            try:
                self.after_cancel(self._levels_scroll_after_id)
            except tk.TclError:
                pass
            self._levels_scroll_after_id = None

    def _schedule_levels_axis_refresh(self, delay_ms: int = 120):
        self._cancel_levels_axis_refresh()
        self._levels_scroll_after_id = self.after(delay_ms, self._finish_levels_axis_refresh)

    def _finish_levels_axis_refresh(self):
        self._levels_scroll_after_id = None
        self._refresh_price_chart_view(light=False)

    def _schedule_levels_pan_draw(self):
        if self._levels_pan_after_id:
            return
        self._levels_pan_after_id = self.after(16, self._flush_levels_pan_draw)

    def _flush_levels_pan_draw(self):
        self._levels_pan_after_id = None
        self.levels_canvas.draw_idle()

    def _on_levels_click(self, event):
        if event.inaxes != self.ax_price_levels:
            return
        if event.dblclick:
            self._reset_levels_zoom()
            return
        if event.button == 1 and event.x is not None and event.y is not None:
            ax = self.ax_price_levels
            self._price_pan_ref = (event.x, event.y, ax.get_xlim(), ax.get_ylim())

    def _on_levels_motion(self, event):
        if self._price_pan_ref is None or event.x is None or event.y is None:
            return
        ax = self.ax_price_levels
        ref_x, ref_y, (xmin, xmax), (ymin, ymax) = self._price_pan_ref
        bbox = ax.get_window_extent()
        if bbox.width <= 0 or bbox.height <= 0:
            return
        dx = -(event.x - ref_x) * (xmax - xmin) / bbox.width
        dy = (event.y - ref_y) * (ymax - ymin) / bbox.height
        ax.set_xlim(xmin + dx, xmax + dx)
        ax.set_ylim(ymin + dy, ymax + dy)
        self._schedule_levels_pan_draw()

    def _on_levels_release(self, event):
        if event.button == 1:
            self._price_pan_ref = None
            if self._levels_pan_after_id:
                try:
                    self.after_cancel(self._levels_pan_after_id)
                except tk.TclError:
                    pass
                self._levels_pan_after_id = None
            self._finish_levels_axis_refresh()

    def _refresh_price_chart_view(self, *, light: bool = False):
        ax = self.ax_price_levels
        if not light:
            apply_price_axis_format(ax, COLORS)
            refresh_level_price_labels(ax, COLORS)
        self.levels_canvas.draw_idle()

    def _reset_levels_zoom(self):
        if self._levels_default_xlim is None or self._levels_default_ylim is None:
            return
        self._cancel_levels_axis_refresh()
        if self._levels_pan_after_id:
            try:
                self.after_cancel(self._levels_pan_after_id)
            except tk.TclError:
                pass
            self._levels_pan_after_id = None
        ax = self.ax_price_levels
        ax.set_xlim(self._levels_default_xlim)
        ax.set_ylim(self._levels_default_ylim)
        self._price_pan_ref = None
        self._refresh_price_chart_view(light=False)

    def _resolve_ticker(self) -> str:
        query = self.ticker_search_var.get().strip()
        if query:
            if query in self._ticker_catalog:
                return self._ticker_catalog[query]
            return normalize_ticker_input(query)
        manual = self.custom_ticker_var.get().strip()
        if manual:
            return normalize_ticker_input(manual)
        return ""

    def _set_status(self, text: str, *, tone: str = "info"):
        color = {
            "info": COLORS["success"],
            "warn": COLORS["warning"],
            "error": COLORS["danger"],
        }.get(tone, COLORS["success"])
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def _chart_df(self) -> pd.DataFrame:
        if self.df_enriched is not None:
            return self.df_enriched
        if self.df is not None:
            return self.df
        raise ValueError("No data loaded")

    def _fetch_data_payload(self, ticker: str, period: str, lookback: int) -> dict:
        df = fetch_stock_data(ticker, period, lookback_days=lookback)
        df_institutional = None
        inst_note = ""
        if ticker_market(ticker) == "台股":
            self.after(0, lambda: self._set_status(f"正在載入 {ticker} 三大法人 ...", tone="warn"))
            try:
                df_institutional = fetch_tw_institutional_data(ticker, period, lookback_days=lookback)
                if df_institutional is not None and not df_institutional.empty:
                    last_net = df_institutional["total_net"].iloc[-1]
                    inst_note = f"\n三大法人(最新): {last_net:+,.0f} 股"
            except Exception as inst_exc:
                inst_note = f"\n三大法人: 未取得 ({inst_exc})"
        df_enriched = ensure_indicators(df)
        return {
            "ticker": ticker,
            "df": df,
            "df_enriched": df_enriched,
            "df_institutional": df_institutional,
            "inst_note": inst_note,
        }

    def load_data(self, *, on_complete=None, run_analysis_after: bool = True, blocking: bool = False):
        if self._busy:
            return
        ticker = self._resolve_ticker()
        if not ticker:
            messagebox.showwarning("提示", "請輸入股票代號")
            return

        self._set_busy(True)
        self.engine = BacktestEngine(self._build_config_from_ui())
        period = self._period_code()
        lookback = self.lookback_var.get()
        self.ticker = ticker
        self._set_status(f"正在載入 {ticker} 股價 ...", tone="warn")
        self.header_ticker_var.set(f"  {ticker}  ")

        def worker():
            try:
                payload = self._fetch_data_payload(ticker, period, lookback)
                self.after(0, lambda: self._on_load_success(payload, on_complete, run_analysis_after))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_load_error(e))

        if blocking:
            try:
                payload = self._fetch_data_payload(ticker, period, lookback)
                self._on_load_success(payload, on_complete, run_analysis_after)
            except Exception as exc:
                self._on_load_error(exc)
            return

        threading.Thread(target=worker, daemon=True).start()

    def _on_load_success(self, payload: dict, on_complete, run_analysis_after: bool):
        self.ticker = payload["ticker"]
        self.df = payload["df"]
        self.df_enriched = payload["df_enriched"]
        self.df_institutional = payload["df_institutional"]
        self._inst_note = payload.get("inst_note", "")
        start, end = self.df.index[0].date(), self.df.index[-1].date()
        last = self.df["Close"].iloc[-1]
        self.summary_var.set(
            f"模板: {self.strategy_var.get()}\n"
            f"Ticker: {self.ticker}\n"
            f"資料: {start} ~ {end}\n"
            f"筆數: {len(self.df)}\n"
            f"最新收盤: {last:,.2f}{self._inst_note}"
        )
        self._set_status(f"已載入 {self.ticker}，共 {len(self.df)} 筆")
        self._draw_price_chart()
        try:
            if run_analysis_after:
                self.run_analysis(manage_busy=False)
            if on_complete:
                on_complete()
        finally:
            self._set_busy(False)

    def _on_load_error(self, exc: Exception):
        messagebox.showerror("載入失敗", str(exc))
        self._set_status("載入失敗", tone="error")
        self._set_busy(False)

    def run_analysis(self, *, manage_busy: bool = True):
        if manage_busy and self._busy:
            return
        chart_df = self.df_enriched if self.df_enriched is not None else self.df
        if chart_df is None:
            messagebox.showwarning("提示", "請先載入資料")
            return
        try:
            if manage_busy:
                self._set_busy(True)
            self._set_status("正在分析落點 ...", tone="warn")
            self.analysis = self.analyzer.analyze(chart_df, self.ticker, self.lookback_var.get())
            self._populate_levels()
            self._draw_price_chart()
            self.notebook.select(self.levels_frame)
            self._set_status("落點分析完成")
        except Exception as exc:
            messagebox.showerror("分析失敗", str(exc))
            self._set_status("分析失敗", tone="error")
        finally:
            if manage_busy:
                self._set_busy(False)

    def run_backtest(self, *, manage_busy: bool = True):
        if manage_busy and self._busy:
            return
        chart_df = self.df_enriched if self.df_enriched is not None else self.df
        if chart_df is None:
            messagebox.showwarning("提示", "請先載入資料")
            return
        try:
            if manage_busy:
                self._set_busy(True)
            self._set_status("正在回測 ...", tone="warn")
            self.engine = BacktestEngine(self._build_config_from_ui())
            lookback = self.lookback_var.get()
            mode = self._backtest_mode_code()
            if mode == "fixed":
                self.backtest_result = self.engine.run_fixed(chart_df, self.ticker, lookback)
            else:
                self.backtest_result = self.engine.run_rolling(chart_df, self.ticker, lookback)
            self._populate_backtest()
            self._draw_price_chart()
            self.notebook.select(self.backtest_frame)
            mode_label = BACKTEST_MODE_LABELS.get(mode, mode)
            self._set_status(f"回測完成 [{self.strategy_var.get()} / {mode_label}]")
        except Exception as exc:
            messagebox.showerror("回測失敗", str(exc))
            self._set_status("回測失敗", tone="error")
        finally:
            if manage_busy:
                self._set_busy(False)

    def run_all(self):
        self.load_data(on_complete=lambda: self.run_backtest(manage_busy=False), run_analysis_after=True)

    def _populate_levels(self):
        if not self.analysis:
            self._draw_empty_levels_chart()
            self._populate_level_table()
            return
        current = self.analysis.current_price
        inst_suffix = self._inst_note or ""
        self.summary_var.set(
            f"模板: {self.strategy_var.get()}\n"
            f"Ticker: {self.ticker}\n"
            f"分析期間: {self.analysis.train_start.date()} ~ {self.analysis.train_end.date()}\n"
            f"現價: {current:,.2f}\n"
            f"支撐: {len(self.analysis.supports)}  ·  阻力: {len(self.analysis.resistances)}\n"
            f"波段: {self.analysis.swing_low:,.2f} ~ {self.analysis.swing_high:,.2f}\n"
            f"ATR: {self.analysis.atr:,.2f}{inst_suffix}"
        )
        self._populate_level_table()
        self._draw_levels_scheme_c()

    def _populate_level_table(self):
        for tree in (self.support_tree, self.resistance_tree):
            for item in tree.get_children():
                tree.delete(item)
        if not self.analysis:
            return

        def fill(tree: ttk.Treeview, levels: list[LevelCluster], tag: str):
            ordered = sorted(levels, key=lambda lv: lv.price, reverse=True)
            for idx, level in enumerate(ordered):
                tags = (tag, "even") if idx % 2 else (tag,)
                tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"{level.price:,.2f}",
                        level.stars,
                        format_methods_zh(level.methods),
                    ),
                    tags=tags,
                )

        fill(self.support_tree, self.analysis.supports, "support")
        fill(self.resistance_tree, self.analysis.resistances, "resistance")

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
        self.ax.set_title("交易走勢", color=COLORS["muted"], pad=12)
        self.ax.grid(True, alpha=0.2)
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["border"])
        self.canvas.draw()

    def _draw_price_chart(self):
        if self.df is None:
            self._draw_empty_chart()
            return
        self.ax.clear()
        self.ax.set_facecolor(COLORS["chart_bg"])
        source = self.df_enriched if self.df_enriched is not None else self.df
        plot_df = ensure_indicators(source.tail(180))
        dates = plot_df.index
        self.ax.plot(dates, plot_df["Close"], color=COLORS["accent_dark"], linewidth=2.2, label="Price", zorder=3)
        if plot_df["MA20"].notna().any():
            self.ax.plot(dates, plot_df["MA20"], color="#9a7a45", linewidth=1.2, alpha=0.7, label="MA20", zorder=2)
        if plot_df["MA50"].notna().any():
            self.ax.plot(dates, plot_df["MA50"], color="#4a8f6e", linewidth=1.2, alpha=0.7, label="MA50", zorder=2)
        if self.analysis:
            for level in self.analysis.supports:
                self.ax.axhline(level.price, color=COLORS["success"], linestyle="--", alpha=0.28, linewidth=1, zorder=1)
            for level in self.analysis.resistances:
                self.ax.axhline(level.price, color=COLORS["danger"], linestyle="--", alpha=0.28, linewidth=1, zorder=1)
        if self.backtest_result and self.backtest_result.trades:
            for trade in self.backtest_result.trades:
                self.ax.scatter(
                    trade.entry_date,
                    trade.entry_price,
                    color=COLORS["success"],
                    s=70,
                    zorder=5,
                    edgecolors=COLORS["surface"],
                    linewidths=0.8,
                )
                self.ax.scatter(
                    trade.exit_date,
                    trade.exit_price,
                    color=COLORS["danger"],
                    s=70,
                    zorder=5,
                    edgecolors=COLORS["surface"],
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
        self.ax.set_title(f"{self.ticker}  ·  {self.strategy_var.get()}", color=COLORS["text"], pad=12)
        self.ax.grid(True, alpha=0.2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["border"])
        self.fig.autofmt_xdate()
        self.canvas.draw()

    def _set_app_mode(self, mode: str):
        if mode not in APP_MODES:
            mode = APP_MODES[0]
        self.app_mode_var.set(mode)
        for name, btn in self._mode_buttons.items():
            active = name == mode
            btn.configure(
                bg=COLORS["accent"] if active else COLORS["sidebar_elevated"],
                fg="#b8c4d0" if active else COLORS["text_inverse"],
                highlightbackground=COLORS["accent"] if active else COLORS["sidebar_border"],
            )
        self._on_app_mode_change()

    def _on_app_mode_change(self, _event=None):
        is_portfolio = self.app_mode_var.get() == APP_MODES[1]
        self.analysis_sidebar.pack_forget()
        self.portfolio_sidebar.pack_forget()
        self.analysis_main.pack_forget()
        self.portfolio_main.pack_forget()
        if is_portfolio:
            self.portfolio_sidebar.pack(fill=tk.X)
            self.portfolio_main.pack(fill=tk.BOTH, expand=True)
            self._load_portfolio_data(fetch_quotes=False)
            self._start_portfolio_quote_poll()
            self._set_status("股市配比")
        else:
            self._stop_portfolio_quote_poll()
            self.analysis_sidebar.pack(fill=tk.X)
            self.analysis_main.pack(fill=tk.BOTH, expand=True)
            self._set_status("就緒")

    def _build_portfolio_sidebar(self, parent):
        budget_card = self._sidebar_card(parent, "預算")
        self._sidebar_label(budget_card, "總預算 (TWD)").pack(anchor=tk.W)
        self.portfolio_budget_var = tk.StringVar(value="")
        ttk.Entry(budget_card, textvariable=self.portfolio_budget_var, width=SIDEBAR_FIELD_WIDTH, style="Dark.TEntry").pack(
            fill=tk.X, pady=(4, 0)
        )
        self._sidebar_label(budget_card, "剩餘 = 預算 − 已投入（台股+美股台幣）", muted=True).pack(anchor=tk.W, pady=(4, 0))

        rate_card = self._sidebar_card(parent, "美股設定")
        self._sidebar_label(rate_card, "USD/TWD 匯率").pack(anchor=tk.W)
        self.portfolio_rate_var = tk.StringVar(value="31.53")
        rate_entry = ttk.Entry(rate_card, textvariable=self.portfolio_rate_var, width=SIDEBAR_FIELD_WIDTH, style="Dark.TEntry")
        rate_entry.pack(fill=tk.X, pady=(4, 0))
        rate_entry.bind("<KeyRelease>", lambda _e: self._render_portfolio())

        tk.Label(
            parent,
            text="操作",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_light"],
            font=FONTS["section"],
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 4))

        actions = tk.Frame(parent, bg=COLORS["sidebar"])
        actions.pack(fill=tk.X, pady=(0, 6))
        self._action_button(actions, "重新整理報價", self._refresh_portfolio_quotes, primary=True)
        self._action_button(actions, "儲存配比", self._save_portfolio)
        self._action_button(actions, "重新載入", self._load_portfolio_data)

        self.portfolio_quote_status_var = tk.StringVar(value="")
        tk.Label(
            parent,
            textvariable=self.portfolio_quote_status_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
            wraplength=SIDEBAR_WRAPLENGTH,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        self.portfolio_summary_var = tk.StringVar(value="")
        tk.Label(
            parent,
            textvariable=self.portfolio_summary_var,
            bg=COLORS["sidebar"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            wraplength=SIDEBAR_WRAPLENGTH,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _portfolio_kpi_card(self, parent, caption: str, var: tk.StringVar, *, tone: str = "text") -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=COLORS["surface_elevated"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        inner = tk.Frame(card, bg=COLORS["surface_elevated"])
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        tk.Label(
            inner,
            text=caption,
            bg=COLORS["surface_elevated"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
            anchor=tk.W,
        ).pack(anchor=tk.W)
        tk.Label(
            inner,
            textvariable=var,
            bg=COLORS["surface_elevated"],
            fg=COLORS.get(tone, COLORS["text"]),
            font=FONTS["kpi"],
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(4, 0))
        return card

    def _portfolio_configure_table_grid(self, table_wrap: tk.Frame, sec_id: str):
        widths = PORTFOLIO_COL_WIDTHS[sec_id]
        for col, width in enumerate(widths):
            table_wrap.grid_columnconfigure(col, minsize=width, weight=1 if col == 0 else 0)

    def _portfolio_clear_table_body(self, table_wrap: tk.Frame):
        for child in table_wrap.grid_slaves():
            if int(child.grid_info().get("row", 0)) >= 1:
                child.destroy()

    def _portfolio_cell_anchor(self, sec_id: str, col: int, total_cols: int) -> str:
        if col == 0:
            return tk.W
        if col == total_cols - 1:
            return tk.CENTER
        if sec_id == "tw" and col == 2:
            return tk.CENTER
        if sec_id == "us" and col == 1:
            return tk.CENTER
        return tk.E

    def _build_portfolio_tab(self):
        self.portfolio_row_containers: dict[str, tk.Frame] = {}
        self.portfolio_total_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.portfolio_row_refs: dict[str, list[dict]] = {"tw": [], "us": []}

        toolbar = tk.Frame(self.portfolio_main, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 0))
        tk.Label(
            toolbar,
            text="持股配比 · 直接輸入欄位 · 下方合計列自動計算",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(side=tk.LEFT)

        summary_card = tk.Frame(
            self.portfolio_main,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        summary_card.pack(fill=tk.X, padx=16, pady=(12, 0))
        summary_inner = tk.Frame(summary_card, bg=COLORS["surface"])
        summary_inner.pack(fill=tk.X, padx=16, pady=14)
        tk.Label(
            summary_inner,
            text="投資組合總覽",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(anchor=tk.W)
        kpi_row = tk.Frame(summary_inner, bg=COLORS["surface"])
        kpi_row.pack(fill=tk.X, pady=(8, 0))
        self.portfolio_kpi_vars: dict[str, tk.StringVar] = {}
        for key, caption, tone in PORTFOLIO_KPI_SPECS:
            var = tk.StringVar(value="—")
            self.portfolio_kpi_vars[key] = var
            self._portfolio_kpi_card(kpi_row, caption, var, tone=tone)
        self.portfolio_detail_var = tk.StringVar(value="")
        tk.Label(
            summary_inner,
            textvariable=self.portfolio_detail_var,
            bg=COLORS["surface"],
            fg=COLORS["muted_light"],
            font=FONTS["caption"],
            justify=tk.LEFT,
            wraplength=980,
        ).pack(anchor=tk.W, pady=(10, 0))

        content = tk.Frame(self.portfolio_main, bg=COLORS["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        table_panel = tk.Frame(content, bg=COLORS["bg"])
        table_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(table_panel, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(table_panel, orient=tk.VERTICAL, command=canvas.yview)
        scroll_inner = tk.Frame(canvas, bg=COLORS["bg"])
        scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._portfolio_canvas_window = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._portfolio_canvas_window, width=e.width),
        )
        self._bind_sidebar_scroll(canvas)

        chart_panel = tk.Frame(
            content,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            width=PORTFOLIO_CHART_WIDTH,
        )
        chart_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(16, 0))
        chart_panel.pack_propagate(False)
        chart_head = tk.Frame(chart_panel, bg=COLORS["surface"])
        chart_head.pack(fill=tk.X, padx=14, pady=(12, 4))
        tk.Label(
            chart_head,
            text="配置概覽",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONTS["section"],
        ).pack(anchor=tk.W)
        tk.Label(
            chart_head,
            text="台美股 · 長短線占比",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONTS["caption"],
        ).pack(anchor=tk.W, pady=(2, 0))
        pie_body = tk.Frame(chart_panel, bg=COLORS["surface"])
        pie_body.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))
        self.portfolio_pie_fig = plt.figure(figsize=PORTFOLIO_PIE_FIGSIZE, dpi=100)
        self.portfolio_pie_fig.patch.set_facecolor(COLORS["surface"])
        pie_grid = GridSpec(
            3,
            1,
            figure=self.portfolio_pie_fig,
            height_ratios=[1, 1, 1],
            hspace=0.78,
            top=0.98,
            bottom=0.03,
            left=0.02,
            right=0.98,
        )
        self.portfolio_pie_ax_market = self.portfolio_pie_fig.add_subplot(pie_grid[0])
        self.portfolio_pie_ax_tw_pos = self.portfolio_pie_fig.add_subplot(pie_grid[1])
        self.portfolio_pie_ax_us_pos = self.portfolio_pie_fig.add_subplot(pie_grid[2])
        us_pos = self.portfolio_pie_ax_us_pos.get_position()
        shift = 30 / (PORTFOLIO_PIE_FIGSIZE[1] * 100)
        self.portfolio_pie_ax_us_pos.set_position(
            [us_pos.x0, us_pos.y0 + shift, us_pos.width, us_pos.height]
        )
        self.portfolio_pie_canvas = FigureCanvasTkAgg(self.portfolio_pie_fig, master=pie_body)
        self.portfolio_pie_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.portfolio_section_frames: dict[str, tk.Frame] = {}
        for sec_id, title, color in (
            ("tw", "台股 TW Stocks", COLORS["success"]),
            ("us", "美股 US Stocks", COLORS["accent"]),
        ):
            card = tk.Frame(
                scroll_inner,
                bg=COLORS["surface"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
            )
            card.pack(fill=tk.X, pady=(0, 12))
            self.portfolio_section_frames[sec_id] = card

            head = tk.Frame(card, bg=COLORS["surface"])
            head.pack(fill=tk.X, padx=12, pady=(10, 6))
            tk.Label(head, text=title, bg=COLORS["surface"], fg=color, font=FONTS["section"]).pack(side=tk.LEFT)
            tk.Button(
                head,
                text="＋ 新增列",
                command=lambda sid=sec_id: self._portfolio_add_row(sid),
                bg=COLORS["accent_soft"],
                fg=COLORS["accent"],
                relief=tk.FLAT,
                font=FONTS["caption"],
                padx=8,
                pady=2,
                cursor="hand2",
            ).pack(side=tk.RIGHT)

            table_wrap = tk.Frame(card, bg=COLORS["surface"])
            table_wrap.pack(fill=tk.X, padx=8, pady=(0, 8))

            headers = self._portfolio_headers(sec_id)
            self._portfolio_configure_table_grid(table_wrap, sec_id)
            for col, text in enumerate(headers):
                tk.Label(
                    table_wrap,
                    text=text,
                    bg=COLORS["tree_header"],
                    fg=COLORS["muted_light"] if col else COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=self._portfolio_cell_anchor(sec_id, col, len(headers)),
                    padx=4,
                    pady=7,
                ).grid(row=0, column=col, sticky="nsew", padx=1, pady=(0, 1))

            self.portfolio_row_containers[sec_id] = table_wrap
            self.portfolio_total_vars[sec_id] = {
                "subtotal": tk.StringVar(value="—"),
                "twd": tk.StringVar(value="—"),
                "weight": tk.StringVar(value="100%"),
            }

    def _portfolio_headers(self, sec_id: str) -> list[str]:
        if sec_id == "tw":
            return ["股票", "備註", "部位", "股數", "成本", "現價", "損益%", "總價", "比重", ""]
        return ["股票", "部位", "股數", "成本", "現價", "損益%", "USD", "TWD", "比重", ""]

    def _portfolio_entry(self, parent, var: tk.Variable) -> ttk.Entry:
        return ttk.Entry(parent, textvariable=var, style="Dark.TEntry")

    def _portfolio_render_total_row(self, table_wrap: tk.Frame, sec_id: str, grid_row: int, headers: list[str]):
        totals = self.portfolio_total_vars[sec_id]
        bg = COLORS["surface_elevated"]
        for col in range(len(headers)):
            anchor = self._portfolio_cell_anchor(sec_id, col, len(headers))
            if col == 0:
                tk.Label(
                    table_wrap,
                    text="合計",
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            elif sec_id == "tw" and col == 7:
                tk.Label(
                    table_wrap,
                    textvariable=totals["subtotal"],
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            elif sec_id == "tw" and col == 8:
                tk.Label(
                    table_wrap,
                    textvariable=totals["weight"],
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            elif sec_id == "us" and col == 6:
                tk.Label(
                    table_wrap,
                    textvariable=totals["subtotal"],
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            elif sec_id == "us" and col == 7:
                tk.Label(
                    table_wrap,
                    textvariable=totals["twd"],
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            elif sec_id == "us" and col == 8:
                tk.Label(
                    table_wrap,
                    textvariable=totals["weight"],
                    bg=bg,
                    fg=COLORS["text"],
                    font=FONTS["body_bold"],
                    anchor=anchor,
                    padx=4,
                    pady=8,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            else:
                tk.Label(table_wrap, text="", bg=bg).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)

    def _portfolio_row_change(self, sec_id: str, row_idx: int):
        refs = self.portfolio_row_refs.get(sec_id, [])
        if row_idx < 0 or row_idx >= len(refs):
            return
        sec = self._portfolio_section(sec_id)
        if sec is None or row_idx >= len(sec.rows):
            return
        ref = refs[row_idx]
        prev_name = sec.rows[row_idx].name
        row = sec.rows[row_idx]
        row.name = ref["name"].get().strip()
        row.note = ref["note"].get().strip() if "note" in ref else ""
        pos = ref["position"].get()
        row.position = "short" if pos in ("短線", "short") else "long"
        try:
            row.shares = float(ref["shares"].get() or 0)
        except ValueError:
            row.shares = 0.0
        try:
            row.cost = float(ref["cost"].get() or 0)
        except ValueError:
            row.cost = 0.0
        self._update_portfolio_section_display(sec_id)
        self._update_portfolio_summaries()
        if row.name and row.name != prev_name:
            self._refresh_portfolio_quotes(force=True)
        self.after_idle(lambda: self._render_portfolio_rows(sec_id))

    def _sort_portfolio_section(self, sec: PortfolioSection):
        sec.rows.sort(
            key=lambda r: (
                0 if r.position != "short" else 1,
                -(float(r.shares or 0) * float(r.cost or 0)),
            )
        )

    def _portfolio_position_change(self, sec_id: str, row_idx: int):
        self._portfolio_row_change(sec_id, row_idx)

    def _portfolio_toggle_position(self, sec_id: str, row_idx: int):
        refs = self.portfolio_row_refs.get(sec_id, [])
        if not (0 <= row_idx < len(refs)):
            return
        pos_var = refs[row_idx]["position"]
        pos_var.set("短線" if pos_var.get() in ("長線", "long") else "長線")
        self._portfolio_row_change(sec_id, row_idx)

    def _render_portfolio_rows(self, sec_id: str):
        sec = self._portfolio_section(sec_id)
        table_wrap = self.portfolio_row_containers.get(sec_id)
        if sec is None or table_wrap is None:
            return
        self._sort_portfolio_section(sec)
        self._portfolio_clear_table_body(table_wrap)
        self.portfolio_row_refs[sec_id] = []
        headers = self._portfolio_headers(sec_id)
        calc = calc_section(sec)
        apply_quotes(calc, self._portfolio_quotes)

        for idx, item in enumerate(calc.items):
            row = item.row
            grid_row = idx + 1
            is_short = row.position == "short"
            if is_short:
                row_bg = COLORS["short_row_alt"] if idx % 2 else COLORS["short_row"]
            else:
                row_bg = COLORS["long_row_alt"] if idx % 2 else COLORS["long_row"]

            name_var = tk.StringVar(value=row.name)
            note_var = tk.StringVar(value=row.note)
            pos_var = tk.StringVar(value="短線" if row.position == "short" else "長線")
            shares_var = tk.StringVar(value=str(row.shares) if row.shares else "")
            cost_var = tk.StringVar(value=str(row.cost) if row.cost else "")
            price_var = tk.StringVar(value=f"{item.price:,.2f}" if item.price is not None else "—")
            pl_var = tk.StringVar(value=f"{item.pl_pct:+.2f}%" if item.pl_pct is not None else "—")
            total_var = tk.StringVar(value=f"{item.subtotal:,.2f}")
            twd_var = tk.StringVar(value=f"{item.twd:,.0f}")
            weight_var = tk.StringVar(value=f"{item.weight:.2f}%")

            col = 0
            name_entry = self._portfolio_entry(table_wrap, name_var)
            name_entry.grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            ref: dict = {"name": name_var, "position": pos_var, "shares": shares_var, "cost": cost_var}
            note_entry = None
            if sec_id == "tw":
                note_entry = self._portfolio_entry(table_wrap, note_var)
                note_entry.grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
                ref["note"] = note_var
                col += 1

            pos_pill = tk.Button(
                table_wrap,
                textvariable=pos_var,
                command=lambda sid=sec_id, i=idx: self._portfolio_toggle_position(sid, i),
                bg=COLORS["short_pill"] if is_short else COLORS["long_pill"],
                fg="#f2f5f8",
                activebackground=COLORS["short_pill"] if is_short else COLORS["long_pill"],
                activeforeground="#ffffff",
                relief=tk.FLAT,
                font=FONTS["body_bold"],
                bd=0,
                padx=4,
                pady=3,
                cursor="hand2",
            )
            pos_pill.grid(row=grid_row, column=col, sticky="nsew", padx=3, pady=3)
            ref["position_pill"] = pos_pill
            col += 1

            shares_entry = self._portfolio_entry(table_wrap, shares_var)
            shares_entry.grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            cost_entry = self._portfolio_entry(table_wrap, cost_var)
            cost_entry.grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            for var in (price_var, pl_var):
                tk.Label(
                    table_wrap,
                    textvariable=var,
                    bg=row_bg,
                    fg=COLORS["muted"],
                    font=FONTS["body"],
                    anchor=self._portfolio_cell_anchor(sec_id, col, len(headers)),
                    padx=4,
                    pady=4,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
                col += 1

            tk.Label(
                table_wrap,
                textvariable=total_var,
                bg=row_bg,
                fg=COLORS["text"],
                font=FONTS["body"],
                anchor=self._portfolio_cell_anchor(sec_id, col, len(headers)),
                padx=4,
                pady=4,
            ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            if sec_id == "us":
                tk.Label(
                    table_wrap,
                    textvariable=twd_var,
                    bg=row_bg,
                    fg=COLORS["text"],
                    font=FONTS["body"],
                    anchor=self._portfolio_cell_anchor(sec_id, col, len(headers)),
                    padx=4,
                    pady=4,
                ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
                col += 1

            tk.Label(
                table_wrap,
                textvariable=weight_var,
                bg=row_bg,
                fg=COLORS["accent"],
                font=FONTS["body_bold"],
                anchor=self._portfolio_cell_anchor(sec_id, col, len(headers)),
                padx=4,
                pady=4,
            ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            tk.Button(
                table_wrap,
                text="×",
                command=lambda sid=sec_id, i=idx: self._portfolio_delete_row(sid, i),
                bg=row_bg,
                fg=COLORS["danger"],
                relief=tk.FLAT,
                font=FONTS["body_bold"],
                width=2,
                cursor="hand2",
            ).grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)

            ref.update(
                {
                    "price": price_var,
                    "pl": pl_var,
                    "pl_label": None,
                    "total": total_var,
                    "twd": twd_var,
                    "weight": weight_var,
                }
            )
            self.portfolio_row_refs[sec_id].append(ref)

            for widget in (name_entry, shares_entry, cost_entry):
                widget.bind("<FocusOut>", lambda _e, sid=sec_id, i=idx: self._portfolio_row_change(sid, i))
            name_entry.bind("<Return>", lambda _e, sid=sec_id, i=idx: self._portfolio_row_change(sid, i))
            if note_entry is not None:
                note_entry.bind("<FocusOut>", lambda _e, sid=sec_id, i=idx: self._portfolio_row_change(sid, i))

        self._portfolio_render_total_row(table_wrap, sec_id, len(calc.items) + 1, headers)
        self._update_portfolio_section_display(sec_id)

    def _update_portfolio_section_display(self, sec_id: str):
        sec = self._portfolio_section(sec_id)
        if sec is None:
            return
        calc = calc_section(sec)
        apply_quotes(calc, self._portfolio_quotes)
        refs = self.portfolio_row_refs.get(sec_id, [])
        for idx, item in enumerate(calc.items):
            if idx >= len(refs):
                break
            ref = refs[idx]
            ref["price"].set(f"{item.price:,.2f}" if item.price is not None else "—")
            ref["pl"].set(f"{item.pl_pct:+.2f}%" if item.pl_pct is not None else "—")
            ref["total"].set(f"{item.subtotal:,.2f}")
            ref["twd"].set(f"{item.twd:,.0f}")
            ref["weight"].set(f"{item.weight:.2f}%")

        totals = self.portfolio_total_vars.get(sec_id, {})
        if totals:
            totals["subtotal"].set(f"{calc.total:,.2f}")
            totals["twd"].set(f"{calc.total_twd:,.0f}")
            totals["weight"].set("100%")

    def _portfolio_section(self, sec_id: str) -> PortfolioSection | None:
        for sec in self._portfolio_sections:
            if sec.id == sec_id:
                return sec
        return None

    def _sync_portfolio_rows_from_refs(self, sec_id: str):
        sec = self._portfolio_section(sec_id)
        refs = self.portfolio_row_refs.get(sec_id, [])
        if sec is None or not refs:
            return
        for idx, ref in enumerate(refs):
            if idx >= len(sec.rows):
                break
            row = sec.rows[idx]
            row.name = ref["name"].get().strip()
            row.note = ref["note"].get().strip() if "note" in ref else ""
            pos = ref["position"].get()
            row.position = "short" if pos in ("短線", "short") else "long"
            try:
                row.shares = float(ref["shares"].get() or 0)
            except ValueError:
                row.shares = 0.0
            try:
                row.cost = float(ref["cost"].get() or 0)
            except ValueError:
                row.cost = 0.0

    def _update_portfolio_summaries(self):
        grand = portfolio_total_twd(self._portfolio_sections)
        try:
            budget = float(self.portfolio_budget_var.get() or 0)
        except ValueError:
            budget = 0.0
        tw_total = calc_section(self._portfolio_section("tw")).total_twd if self._portfolio_section("tw") else 0
        us_total = calc_section(self._portfolio_section("us")).total_twd if self._portfolio_section("us") else 0
        remaining = budget - grand if budget > 0 else None

        self.portfolio_kpi_vars["grand"].set(f"{grand:,.0f}")
        self.portfolio_kpi_vars["tw"].set(f"{tw_total:,.0f}")
        self.portfolio_kpi_vars["us"].set(f"{us_total:,.0f}")
        if budget > 0:
            usage = grand / budget * 100
            remain_label = "剩餘" if remaining is not None and remaining >= 0 else "超支"
            remain_text = f" · {remain_label} {abs(remaining or 0):,.0f}" if remaining is not None else ""
            self.portfolio_kpi_vars["budget"].set(f"{usage:.1f}%{remain_text}")
        else:
            self.portfolio_kpi_vars["budget"].set("未設定")

        detail_parts = []
        for sec in self._portfolio_sections:
            stats = calc_position_stats(sec)
            market = "台股" if sec.id == "tw" else "美股"
            detail_parts.append(
                f"{market} 長線 {stats['long']['weight']:.1f}% / 短線 {stats['short']['weight']:.1f}%"
            )
        self.portfolio_detail_var.set("　｜　".join(detail_parts))
        self.portfolio_summary_var.set(
            "\n".join(
                f"{sec.title}: {calc_section(sec).total_twd:,.0f} TWD"
                for sec in self._portfolio_sections
            )
        )
        self._draw_portfolio_pie()

    def _portfolio_pie_color(self, slice_: PortfolioPieSlice, index: int) -> str:
        tw_shades = ("#3d8f7a", "#2f7463", "#4ea892", "#256b58", "#5cb89f", "#1f5a4a")
        us_shades = ("#4a7fa8", "#3d6d92", "#5a92b8", "#2f5f7f", "#6ba3c8", "#254f68")
        if slice_.market_id == "long":
            return COLORS["success"]
        if slice_.market_id == "short":
            return COLORS["warning"]
        if slice_.market_id == "tw":
            return tw_shades[index % len(tw_shades)]
        if slice_.market_id == "us":
            return us_shades[index % len(us_shades)]
        return COLORS["muted"]

    def _portfolio_pie_colors(self, slices: list[PortfolioPieSlice]) -> list[str]:
        tw_idx = us_idx = 0
        colors: list[str] = []
        for slice_ in slices:
            if slice_.market_id == "tw":
                colors.append(self._portfolio_pie_color(slice_, tw_idx))
                tw_idx += 1
            elif slice_.market_id == "us":
                colors.append(self._portfolio_pie_color(slice_, us_idx))
                us_idx += 1
            else:
                colors.append(self._portfolio_pie_color(slice_, 0))
        return colors

    def _render_portfolio_pie_axis(
        self,
        ax,
        slices: list[PortfolioPieSlice],
        *,
        title: str | None = None,
        empty_text: str = "無資料",
    ):
        ax.clear()
        ax.set_facecolor(COLORS["surface"])
        if title:
            ax.set_title(
                title,
                color=COLORS["muted_light"],
                fontsize=9,
                pad=3,
                loc="center",
            )
        if not slices:
            ax.text(
                0.5,
                0.5,
                empty_text,
                ha="center",
                va="center",
                color=COLORS["muted"],
                fontsize=8,
                transform=ax.transAxes,
            )
            ax.axis("off")
            return

        colors = self._portfolio_pie_colors(slices)
        sizes = [s.twd for s in slices]
        wedgeprops = {
            "width": 0.56,
            "edgecolor": COLORS["surface"],
            "linewidth": 1.4,
        }
        wedges, _texts, autotexts = ax.pie(
            sizes,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct=lambda pct: f"{pct:.0f}%",
            pctdistance=0.76,
            textprops={"color": "#ffffff", "fontsize": 11, "weight": "bold"},
            wedgeprops=wedgeprops,
        )
        for autotext in autotexts:
            autotext.set_color("#ffffff")
            autotext.set_path_effects(
                [pe.withStroke(linewidth=2.4, foreground="#000000")]
            )

        if len(slices) <= 4:
            ax.legend(
                wedges,
                [f"{s.label}" for s in slices],
                loc="upper center",
                bbox_to_anchor=(0.5, -0.08),
                ncol=min(len(slices), 2),
                fontsize=7.5,
                frameon=False,
                labelcolor=COLORS["muted"],
                handlelength=0.7,
                handletextpad=0.35,
                columnspacing=0.8,
                borderaxespad=0.0,
            )
        ax.axis("equal")
        ax.set_anchor("C")

    def _draw_portfolio_pie(self):
        if not hasattr(self, "portfolio_pie_ax_market"):
            return
        self.portfolio_pie_fig.patch.set_facecolor(COLORS["surface"])

        tw_sec = self._portfolio_section("tw")
        us_sec = self._portfolio_section("us")
        self._render_portfolio_pie_axis(
            self.portfolio_pie_ax_market,
            portfolio_market_slices(self._portfolio_sections),
            title="台美股",
        )
        self._render_portfolio_pie_axis(
            self.portfolio_pie_ax_tw_pos,
            position_pie_slices(tw_sec) if tw_sec else [],
            title="台股長短",
        )
        self._render_portfolio_pie_axis(
            self.portfolio_pie_ax_us_pos,
            position_pie_slices(us_sec) if us_sec else [],
            title="美股長短",
        )
        self.portfolio_pie_canvas.draw_idle()

    def _ensure_portfolio_sections(self):
        if not self._portfolio_sections:
            self._portfolio_sections = [
                PortfolioSection(id="tw", title="TW Stocks", currency="TWD", has_rate=False, rows=[]),
                PortfolioSection(
                    id="us",
                    title="US Stocks",
                    currency="USD",
                    has_rate=True,
                    rate=float(self.portfolio_rate_var.get() or 31.53),
                    rows=[],
                ),
            ]
        us_sec = self._portfolio_section("us")
        if us_sec is not None:
            try:
                us_sec.rate = float(self.portfolio_rate_var.get() or us_sec.rate)
            except ValueError:
                pass

    def _load_portfolio_data(self, *, fetch_quotes: bool = True):
        sections, budget = load_portfolio(self._portfolio_path)
        if sections:
            self._portfolio_sections = sections
        else:
            self._portfolio_sections = []
        self._ensure_portfolio_sections()
        if budget > 0:
            budget_text = str(int(budget)) if float(budget).is_integer() else str(budget)
            self.portfolio_budget_var.set(budget_text)
        us_sec = self._portfolio_section("us")
        if us_sec is not None:
            self.portfolio_rate_var.set(str(us_sec.rate))
        self._render_portfolio()
        if fetch_quotes:
            self._refresh_portfolio_quotes(force=True)

    def _start_portfolio_quote_poll(self):
        self._stop_portfolio_quote_poll()
        self._refresh_portfolio_quotes(force=True)
        self._schedule_portfolio_quote_poll()

    def _schedule_portfolio_quote_poll(self):
        if self._portfolio_quote_after_id:
            try:
                self.after_cancel(self._portfolio_quote_after_id)
            except tk.TclError:
                pass
        self._portfolio_quote_after_id = self.after(QUOTE_POLL_MS, self._portfolio_quote_tick)

    def _portfolio_quote_tick(self):
        if self.app_mode_var.get() != APP_MODES[1]:
            return
        self._refresh_portfolio_quotes(schedule_next=True)

    def _stop_portfolio_quote_poll(self):
        if self._portfolio_quote_after_id:
            try:
                self.after_cancel(self._portfolio_quote_after_id)
            except tk.TclError:
                pass
            self._portfolio_quote_after_id = None

    def _save_portfolio(self):
        self._ensure_portfolio_sections()
        for sec_id in ("tw", "us"):
            self._sync_portfolio_rows_from_refs(sec_id)
        try:
            budget = float(self.portfolio_budget_var.get() or 0)
        except ValueError:
            budget = 0.0
        save_portfolio(self._portfolio_path, self._portfolio_sections, budget)
        self._set_status(f"已儲存至 {self._portfolio_path.name}")
        self.portfolio_quote_status_var.set("✓ 已儲存配比")

    def _refresh_portfolio_quotes(self, *, force: bool = False, schedule_next: bool = False):
        if self._portfolio_quote_fetching:
            if schedule_next:
                self._schedule_portfolio_quote_poll()
            return
        self._ensure_portfolio_sections()
        for sec_id in ("tw", "us"):
            self._sync_portfolio_rows_from_refs(sec_id)
        self._portfolio_quote_fetching = True
        self.portfolio_quote_status_var.set("正在更新報價 ...")

        def worker():
            try:
                quotes = fetch_quotes(self._portfolio_sections, force=force)
                self.after(0, lambda: self._on_portfolio_quotes_ready(quotes, None, schedule_next))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_portfolio_quotes_ready({}, e, schedule_next))

        threading.Thread(target=worker, daemon=True).start()

    def _on_portfolio_quotes_ready(self, quotes: dict, error: Exception | None, schedule_next: bool = False):
        self._portfolio_quotes = quotes
        self._portfolio_quote_fetching = False
        self._render_portfolio(rebuild=False)
        if error:
            self.portfolio_quote_status_var.set(f"報價更新失敗: {error}")
            self._set_status("報價更新失敗", tone="error")
        else:
            from datetime import datetime

            now = datetime.now().strftime("%H:%M:%S")
            self.portfolio_quote_status_var.set(
                f"報價已更新 {now}（{len(quotes)} 檔）· 每 5 分鐘自動更新"
            )
            self._set_status(f"報價已更新（{len(quotes)} 檔）")
        if schedule_next and self.app_mode_var.get() == APP_MODES[1]:
            self._schedule_portfolio_quote_poll()

    def _render_portfolio(self, *, rebuild: bool = True):
        self._ensure_portfolio_sections()
        if rebuild or not self.portfolio_row_refs.get("tw"):
            for sec_id in ("tw", "us"):
                self._sync_portfolio_rows_from_refs(sec_id)
                self._render_portfolio_rows(sec_id)
        else:
            for sec_id in ("tw", "us"):
                self._update_portfolio_section_display(sec_id)
        self._update_portfolio_summaries()

    def _portfolio_delete_row(self, sec_id: str, row_idx: int):
        self._sync_portfolio_rows_from_refs(sec_id)
        sec = self._portfolio_section(sec_id)
        if sec is None or row_idx < 0 or row_idx >= len(sec.rows):
            return
        sec.rows.pop(row_idx)
        self._render_portfolio_rows(sec_id)
        self._update_portfolio_summaries()

    def _portfolio_add_row(self, sec_id: str):
        self._sync_portfolio_rows_from_refs(sec_id)
        sec = self._portfolio_section(sec_id)
        if sec is None:
            return
        sec.rows.append(PortfolioRow(name="", note="", position="long", shares=0, cost=0))
        self._render_portfolio_rows(sec_id)
        self._update_portfolio_summaries()


def main():
    app = LandingAnalysisApp()

    def _handle_sigint(_signum, _frame):
        app.after(0, app._quit_app)

    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except (ValueError, OSError):
        pass

    # Tk's mainloop is C code, so the Python interpreter never regains control
    # to deliver Ctrl+C (SIGINT) unless an `after` callback ticks periodically.
    def _keepalive():
        try:
            app.after(200, _keepalive)
        except tk.TclError:
            pass

    app.after(200, _keepalive)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        app._quit_app()


if __name__ == "__main__":
    main()
