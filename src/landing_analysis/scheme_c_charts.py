"""Scheme C landing-point dashboard charts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .analyzer import AnalysisResult, LevelCluster
from .indicators import ensure_indicators


def decimals_for_price_span(span: float) -> int:
    if span > 500:
        return 0
    if span > 100:
        return 1
    if span > 20:
        return 2
    if span > 5:
        return 3
    if span > 1:
        return 4
    return 5


def format_price_value(value: float, span: float) -> str:
    decimals = decimals_for_price_span(span)
    return f"{value:,.{decimals}f}"


METHOD_LABELS_ZH: dict[str, str] = {
    "Fib 38.2%": "斐波那契 38.2%",
    "Fib 50.0%": "斐波那契 50%",
    "Fib 61.8%": "斐波那契 61.8%",
    "Bollinger Lower": "布林下軌",
    "Bollinger Mid": "布林中軌",
    "Bollinger Upper": "布林上軌",
    "MA20": "MA20 均線",
    "MA50": "MA50 均線",
    "Volume S1": "量能分布 S1",
    "Volume S2": "量能分布 S2",
    "Volume S3": "量能分布 S3",
    "Volume R1": "量能分布 R1",
    "Volume R2": "量能分布 R2",
    "Pivot S1": "樞軸 S1",
    "Pivot S2": "樞軸 S2",
    "Pivot R1": "樞軸 R1",
    "Pivot R2": "樞軸 R2",
    "Period Low": "區間低點",
    "Period High": "區間高點",
    "Psychological": "心理價位",
}


def format_methods_zh(methods: list[str]) -> str:
    return " · ".join(METHOD_LABELS_ZH.get(name, name) for name in methods)


def level_label_text(price: float, span: float, stars: str, methods: list[str], *, show_methods: bool) -> str:
    head = f"{format_price_value(price, span)} {stars}"
    if show_methods and methods:
        return f"{head}\n{format_methods_zh(methods)}"
    return head


def apply_price_axis_format(ax, colors: dict, *, show_ylabel: bool = False):
    ymin, ymax = ax.get_ylim()
    span = max(ymax - ymin, 1e-9)
    decimals = decimals_for_price_span(span)

    ax.yaxis.set_major_locator(MaxNLocator(nbins=9, min_n_ticks=5))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.{decimals}f}"))
    ax.set_ylabel("價格" if show_ylabel else "", color=colors["text"], fontsize=10, labelpad=10)
    ax.tick_params(axis="y", colors=colors["text"], labelsize=9, pad=4)
    ax.tick_params(axis="x", colors=colors["muted"], labelsize=8)


def refresh_level_price_labels(ax, colors: dict):
    for artist, _price, color, stars, _methods_zh in getattr(ax, "_level_labels", []):
        artist.set_text(stars)
        artist.set_color(color)


def volume_profile_data(df: pd.DataFrame, n_bins: int = 36) -> tuple[np.ndarray, np.ndarray]:
    prices = df["Close"].values
    volumes = df["Volume"].values
    lo, hi = float(prices.min()), float(prices.max())
    if hi <= lo:
        return np.array([lo]), np.array([float(volumes.sum())])

    bins = np.linspace(lo, hi, n_bins + 1)
    profile = np.zeros(n_bins)
    for price, vol in zip(prices, volumes):
        idx = min(int((price - lo) / (hi - lo) * n_bins), n_bins - 1)
        profile[idx] += vol
    centers = (bins[:-1] + bins[1:]) / 2
    return centers, profile


def format_strength_display(strength: int) -> str:
    stars = "★" * min(strength, 5)
    if strength > 5:
        return f"{stars} ({strength})"
    return stars


def _ladder_bar_width(strength: int, max_strength: int, *, max_bar: float = 3.35) -> float:
    if max_strength <= 0:
        return 0.35
    return max(0.35, max_bar * strength / max_strength)


LADDER_HALF_WIDTH = 4.2
LADDER_STAR_X = 3.75


def _line_width(strength: int) -> float:
    return {1: 1.0, 2: 1.8}.get(strength, 2.8)


def _price_band(levels: list[LevelCluster], current: float, padding: float = 0.04) -> tuple[float, float]:
    prices = [current] + [level.price for level in levels]
    lo, hi = min(prices), max(prices)
    span = max(hi - lo, current * 0.02)
    return lo - span * padding, hi + span * padding


def _style_axis(ax, colors: dict):
    ax.set_facecolor(colors["chart_bg"])
    ax.grid(True, alpha=0.18, color=colors["border"])
    for spine in ax.spines.values():
        spine.set_color(colors["border"])
    ax.tick_params(colors=colors["muted"], labelsize=8)


def _compact_share_label(value: float, _pos: int) -> str:
    abs_v = abs(value)
    sign = "-" if value < 0 else ""
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"{sign}{abs_v / 1_000:.0f}K"
    return f"{value:,.0f}"


def draw_institutional_chart(
    ax,
    inst_df: pd.DataFrame | None,
    *,
    colors: dict,
    lookback_days: int,
    ticker: str,
    is_tw: bool,
    show_foreign: bool = True,
    show_trust: bool = True,
    show_dealer: bool = True,
):
    ax.clear()
    _style_axis(ax, colors)

    if not is_tw:
        ax.set_title("三大法人買賣超", color=colors["text"], fontsize=10, fontweight="bold", pad=8)
        ax.text(
            0.5,
            0.5,
            "三大法人僅支援台股",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=colors["muted"],
            fontsize=10,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return

    if inst_df is None or inst_df.empty:
        ax.set_title("三大法人買賣超", color=colors["text"], fontsize=10, fontweight="bold", pad=8)
        ax.text(
            0.5,
            0.5,
            "未取得三大法人資料\n請確認 FINMIND_TOKEN 已設定",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=colors["muted"],
            fontsize=10,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return

    plot_df = inst_df.tail(min(len(inst_df), max(lookback_days, 30))).copy()
    dates = plot_df.index
    x = mdates.date2num(dates.to_pydatetime())

    all_series = [
        ("foreign_net", "外資", colors["accent"], show_foreign),
        ("trust_net", "投信", colors["success"], show_trust),
        ("dealer_net", "自營", colors["warning"], show_dealer),
    ]
    active = [(col, label, color) for col, label, color, show in all_series if show]
    if not active:
        ax.set_title("三大法人買賣超", color=colors["text"], fontsize=10, fontweight="bold", pad=8)
        ax.text(
            0.5,
            0.5,
            "請至少勾選一項法人",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=colors["muted"],
            fontsize=10,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return

    n = len(active)
    bar_w = 0.22 if n == 3 else (0.32 if n == 2 else 0.45)
    for idx, (col, label, color) in enumerate(active):
        offset = (idx - (n - 1) / 2) * bar_w
        values = plot_df[col].values
        bar_colors = [colors["success"] if v >= 0 else colors["danger"] for v in values]
        ax.bar(
            x + offset,
            values,
            width=bar_w * 0.95,
            color=bar_colors,
            alpha=0.82,
            edgecolor=colors["border"],
            linewidth=0.2,
            label=label,
        )

    show_total = show_foreign and show_trust and show_dealer
    if show_total:
        ax.plot(
            dates,
            plot_df["total_net"],
            color=colors["text"],
            linewidth=1.3,
            alpha=0.75,
            label="合計",
            zorder=5,
        )
    ax.axhline(0, color=colors["border"], linewidth=0.9, alpha=0.9, zorder=1)

    last = plot_df.iloc[-1]
    summary_parts = []
    if show_foreign:
        summary_parts.append(f"外資 {last['foreign_net']:+,.0f}")
    if show_trust:
        summary_parts.append(f"投信 {last['trust_net']:+,.0f}")
    if show_dealer:
        summary_parts.append(f"自營 {last['dealer_net']:+,.0f}")
    if show_total:
        summary_parts.append(f"合計 {last['total_net']:+,.0f}")
    summary = "最新  " + "  ".join(summary_parts) + " 股"
    ax.set_title(
        f"{ticker} · 三大法人買賣超（股）",
        color=colors["text"],
        fontsize=10,
        fontweight="bold",
        pad=8,
    )
    ax.text(
        0.01,
        0.98,
        summary,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7,
        color=colors["muted"],
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.yaxis.set_major_formatter(FuncFormatter(_compact_share_label))
    ax.set_ylabel("買賣超", color=colors["muted"], fontsize=8)
    ax.tick_params(axis="x", rotation=0, labelsize=7)
    ax.legend(
        loc="upper right",
        fontsize=7,
        ncol=min(4, len(active) + (1 if show_total else 0)),
        framealpha=0.92,
        facecolor=colors["surface"],
        edgecolor=colors["border"],
        labelcolor=colors["text"],
    )


def draw_empty_scheme_c(fig, ax_price, ax_ladder, ax_vp, ax_institutional, colors: dict):
    for ax in (ax_price, ax_ladder, ax_vp, ax_institutional):
        ax.clear()
        _style_axis(ax, colors)
    ax_price.set_title("方案 C · 落點分析", color=colors["text"], fontsize=12, fontweight="bold", pad=10)
    ax_price.text(
        0.5,
        0.5,
        "載入資料後將顯示\n價格落點線圖 · 落點階梯 · 成交量分布 · 三大法人",
        transform=ax_price.transAxes,
        ha="center",
        va="center",
        color=colors["muted"],
        fontsize=11,
    )
    ax_ladder.set_title("落點階梯", color=colors["text"], fontsize=10, pad=8)
    ax_vp.set_title("成交量價格分布", color=colors["text"], fontsize=10, pad=8)
    draw_institutional_chart(ax_institutional, None, colors=colors, lookback_days=42, ticker="", is_tw=False)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.94, bottom=0.10, wspace=0.32, hspace=0.42)


def draw_scheme_c(
    fig,
    ax_price,
    ax_ladder,
    ax_vp,
    ax_institutional,
    df: pd.DataFrame,
    analysis: AnalysisResult,
    *,
    ticker: str,
    strategy_name: str,
    colors: dict,
    lookback_days: int,
    inst_df: pd.DataFrame | None = None,
    is_tw: bool = False,
    inst_show_foreign: bool = True,
    inst_show_trust: bool = True,
    inst_show_dealer: bool = True,
):
    for ax in (ax_price, ax_ladder, ax_vp):
        ax.clear()
        _style_axis(ax, colors)

    plot_df = ensure_indicators(df.tail(max(180, lookback_days + 30)))
    train = df.iloc[-lookback_days:].copy()
    vp_centers, vp_profile = volume_profile_data(train)
    current = analysis.current_price
    all_levels = analysis.supports + analysis.resistances
    y_min_data = min([plot_df["Close"].min(), current] + [lv.price for lv in all_levels])
    y_max_data = max([plot_df["Close"].max(), current] + [lv.price for lv in all_levels])
    y_pad = max((y_max_data - y_min_data) * 0.06, current * 0.01)
    ax_price.set_ylim(y_min_data - y_pad, y_max_data + y_pad)
    ax_price._level_labels = []

    # --- Price + landing lines ---
    dates = plot_df.index
    ax_price.plot(dates, plot_df["Close"], color=colors["accent_dark"], linewidth=2.0, label="Price", zorder=4)
    if plot_df["MA20"].notna().any():
        ax_price.plot(dates, plot_df["MA20"], color="#9a7a45", linewidth=1.1, alpha=0.7, label="MA20", zorder=3)

    for level in analysis.supports:
        ax_price.axhline(
            level.price,
            color=colors["success"],
            linestyle="--",
            alpha=0.45,
            linewidth=_line_width(level.strength),
            zorder=2,
        )
        label = ax_price.annotate(
            format_strength_display(level.strength),
            xy=(0.01, level.price),
            xycoords=("axes fraction", "data"),
            xytext=(4, -6),
            textcoords="offset points",
            color=colors["success"],
            fontsize=8,
            va="top",
            ha="left",
            annotation_clip=False,
        )
        ax_price._level_labels.append(
            (label, level.price, colors["success"], format_strength_display(level.strength), "")
        )
    for level in analysis.resistances:
        ax_price.axhline(
            level.price,
            color=colors["danger"],
            linestyle="--",
            alpha=0.45,
            linewidth=_line_width(level.strength),
            zorder=2,
        )
        label = ax_price.annotate(
            format_strength_display(level.strength),
            xy=(1.0, level.price),
            xycoords=("axes fraction", "data"),
            xytext=(6, 0),
            textcoords="offset points",
            color=colors["danger"],
            fontsize=8,
            va="center",
            ha="left",
            annotation_clip=False,
        )
        ax_price._level_labels.append(
            (label, level.price, colors["danger"], format_strength_display(level.strength), "")
        )

    ax_price.axhline(current, color=colors["warning"], linestyle=":", linewidth=1.2, alpha=0.9, zorder=5)
    ax_price._current_price_value = current
    apply_price_axis_format(ax_price, colors)
    ax_price.set_title(
        f"{ticker} · {strategy_name} · 價格走勢 + 落點線",
        color=colors["text"],
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    legend_items = [
        Line2D([0], [0], color=colors["accent_dark"], linewidth=2, label="Price"),
        Line2D([0], [0], color="#9a7a45", linewidth=1.2, label="MA20"),
        Line2D([0], [0], color=colors["success"], linestyle="--", linewidth=1.5, label="支撐"),
        Line2D([0], [0], color=colors["danger"], linestyle="--", linewidth=1.5, label="阻力"),
        Line2D([0], [0], color=colors["warning"], linestyle=":", linewidth=1.2, label="現價"),
        Line2D([0], [0], color="none", label="★＝匯聚強度（最多 5 顆，可附數字）"),
    ]
    ax_price.legend(
        handles=legend_items,
        loc="upper left",
        fontsize=7,
        framealpha=0.92,
        facecolor=colors["surface"],
        edgecolor=colors["border"],
        labelcolor=colors["text"],
    )

    # --- Price ladder ---
    y_min, y_max = _price_band(all_levels, current)
    span = max(y_max - y_min, 1e-6)
    bar_h = span * 0.018
    max_strength = max([1] + [level.strength for level in all_levels])

    for level in analysis.supports:
        width = _ladder_bar_width(level.strength, max_strength)
        ax_ladder.barh(
            level.price,
            width,
            height=bar_h,
            left=-width,
            color=colors["success"],
            alpha=0.45 if level.strength >= 3 else 0.35,
            edgecolor=colors["border"],
            linewidth=0.4,
        )
        ax_ladder.text(
            -LADDER_STAR_X,
            level.price,
            format_strength_display(level.strength),
            ha="right",
            va="center",
            fontsize=7,
            color=colors["success"],
            clip_on=False,
        )
    for level in analysis.resistances:
        width = _ladder_bar_width(level.strength, max_strength)
        ax_ladder.barh(
            level.price,
            width,
            height=bar_h,
            left=0,
            color=colors["danger"],
            alpha=0.45 if level.strength >= 3 else 0.35,
            edgecolor=colors["border"],
            linewidth=0.4,
        )
        ax_ladder.text(
            LADDER_STAR_X,
            level.price,
            format_strength_display(level.strength),
            ha="left",
            va="center",
            fontsize=7,
            color=colors["danger"],
            clip_on=False,
        )

    ax_ladder.axhline(current, color=colors["warning"], linestyle="--", linewidth=1.2, alpha=0.95)
    ax_ladder.text(
        0.02,
        0.98,
        f"現價 {format_price_value(current, y_max - y_min)}",
        transform=ax_ladder.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color=colors["warning"],
        bbox={"boxstyle": "round,pad=0.25", "facecolor": colors["surface_elevated"], "edgecolor": colors["border"], "alpha": 0.95},
    )
    ax_ladder.set_title("落點階梯", color=colors["text"], fontsize=10, fontweight="bold", pad=8)
    ax_ladder.set_xlim(-LADDER_HALF_WIDTH, LADDER_HALF_WIDTH)
    ax_ladder.set_ylim(y_min, y_max)
    ax_ladder.set_xticks([])
    ax_ladder.set_ylabel("價位", color=colors["muted"], fontsize=8)

    # --- Volume profile ---
    if vp_profile.sum() > 0:
        max_vol = vp_profile.max()
        norm = vp_profile / max_vol if max_vol > 0 else vp_profile
        bar_colors = [colors["accent"]] * len(vp_centers)
        poc_idx = int(np.argmax(vp_profile))
        bar_colors[poc_idx] = colors["accent_dark"]
        ax_vp.barh(vp_centers, norm, height=bar_h * 1.1, color=bar_colors, alpha=0.55, edgecolor="none")
        ax_vp.axhline(vp_centers[poc_idx], color=colors["accent_dark"], linestyle="-", linewidth=1.0, alpha=0.8)
        ax_vp.text(
            0.98,
            vp_centers[poc_idx],
            f" POC {vp_centers[poc_idx]:,.2f}",
            transform=ax_vp.get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=7,
            color=colors["accent_dark"],
        )

    ax_vp.axhline(current, color=colors["warning"], linestyle="--", linewidth=1.0, alpha=0.9)
    ax_vp.set_title("成交量價格分布", color=colors["text"], fontsize=10, fontweight="bold", pad=8)
    ax_vp.set_xlabel("成交量 (相對)", color=colors["muted"], fontsize=8)
    ax_vp.set_ylim(y_min, y_max)
    ax_vp.set_yticklabels([])
    ax_vp.tick_params(axis="x", labelsize=7)

    draw_institutional_chart(
        ax_institutional,
        inst_df,
        colors=colors,
        lookback_days=lookback_days,
        ticker=ticker,
        is_tw=is_tw,
        show_foreign=inst_show_foreign,
        show_trust=inst_show_trust,
        show_dealer=inst_show_dealer,
    )

    fig.subplots_adjust(left=0.09, right=0.92, top=0.94, bottom=0.10, wspace=0.32, hspace=0.42)
