"""Scheme C landing-point dashboard charts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .analyzer import AnalysisResult, LevelCluster
from .indicators import add_indicators


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


def apply_price_axis_format(ax, colors: dict):
    ymin, ymax = ax.get_ylim()
    span = max(ymax - ymin, 1e-9)
    decimals = decimals_for_price_span(span)

    ax.yaxis.set_major_locator(MaxNLocator(nbins=9, min_n_ticks=5))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.{decimals}f}"))
    ax.set_ylabel("價格", color=colors["text"], fontsize=10, labelpad=10)
    ax.tick_params(axis="y", colors=colors["text"], labelsize=9, pad=4)
    ax.tick_params(axis="x", colors=colors["muted"], labelsize=8)


def refresh_level_price_labels(ax, colors: dict):
    ymin, ymax = ax.get_ylim()
    span = max(ymax - ymin, 1e-9)
    for artist, price, color, stars in getattr(ax, "_level_labels", []):
        artist.set_text(f"{format_price_value(price, span)} {stars}")
        artist.set_color(color)
    current_art = getattr(ax, "_current_price_label", None)
    current_price = getattr(ax, "_current_price_value", None)
    if current_art is not None and current_price is not None:
        current_art.set_text(f"現價 {format_price_value(current_price, span)}")


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


def draw_empty_scheme_c(fig, ax_price, ax_ladder, ax_vp, colors: dict):
    for ax in (ax_price, ax_ladder, ax_vp):
        ax.clear()
        _style_axis(ax, colors)
    ax_price.set_title("方案 C · 落點分析", color=colors["text"], fontsize=12, fontweight="bold", pad=10)
    ax_price.text(
        0.5,
        0.5,
        "載入資料後將顯示\n價格落點線圖 · 落點階梯 · 成交量分布\n\n滾輪縮放 · 雙擊重置",
        transform=ax_price.transAxes,
        ha="center",
        va="center",
        color=colors["muted"],
        fontsize=11,
    )
    ax_ladder.set_title("落點階梯", color=colors["text"], fontsize=10, pad=8)
    ax_vp.set_title("成交量價格分布", color=colors["text"], fontsize=10, pad=8)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.12, wspace=0.35)


def draw_scheme_c(
    fig,
    ax_price,
    ax_ladder,
    ax_vp,
    df: pd.DataFrame,
    analysis: AnalysisResult,
    *,
    ticker: str,
    strategy_name: str,
    colors: dict,
    lookback_days: int,
):
    for ax in (ax_price, ax_ladder, ax_vp):
        ax.clear()
        _style_axis(ax, colors)

    plot_df = add_indicators(df.tail(max(180, lookback_days + 30)))
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
    ax_price.plot(dates, plot_df["Close"], color=colors["accent_dark"], linewidth=2.0, label="Close", zorder=4)
    if plot_df["MA20"].notna().any():
        ax_price.plot(dates, plot_df["MA20"], color="#9a7a45", linewidth=1.1, alpha=0.7, label="MA20", zorder=3)

    price_span = y_max_data - y_min_data + 2 * y_pad

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
            f"{format_price_value(level.price, price_span)} {level.stars}",
            xy=(1.0, level.price),
            xycoords=("axes fraction", "data"),
            xytext=(6, 0),
            textcoords="offset points",
            color=colors["success"],
            fontsize=8,
            va="center",
            ha="left",
            annotation_clip=False,
        )
        ax_price._level_labels.append((label, level.price, colors["success"], level.stars))
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
            f"{format_price_value(level.price, price_span)} {level.stars}",
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
        ax_price._level_labels.append((label, level.price, colors["danger"], level.stars))

    ax_price.axhline(current, color=colors["warning"], linestyle=":", linewidth=1.2, alpha=0.9, zorder=5)
    ax_price._current_price_label = ax_price.annotate(
        f"現價 {format_price_value(current, price_span)}",
        xy=(0.01, current),
        xycoords=("axes fraction", "data"),
        xytext=(0, 0),
        textcoords="offset points",
        color=colors["warning"],
        fontsize=8,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": colors["surface_elevated"], "edgecolor": colors["border"], "alpha": 0.92},
    )
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
        Line2D([0], [0], color=colors["accent_dark"], linewidth=2, label="Close"),
        Line2D([0], [0], color="#9a7a45", linewidth=1.2, label="MA20"),
        Line2D([0], [0], color=colors["success"], linestyle="--", linewidth=1.5, label="支撐"),
        Line2D([0], [0], color=colors["danger"], linestyle="--", linewidth=1.5, label="阻力"),
    ]
    ax_price.legend(handles=legend_items, loc="upper left", fontsize=7, framealpha=0.92,
                    facecolor=colors["surface"], edgecolor=colors["border"], labelcolor=colors["text"])

    # --- Price ladder ---
    y_min, y_max = _price_band(all_levels, current)
    span = max(y_max - y_min, 1e-6)
    bar_h = span * 0.018

    for level in analysis.supports:
        width = level.strength * 0.9
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
            -width - 0.15,
            level.price,
            level.stars,
            ha="right",
            va="center",
            fontsize=7,
            color=colors["success"],
        )
    for level in analysis.resistances:
        width = level.strength * 0.9
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
            width + 0.15,
            level.price,
            level.stars,
            ha="left",
            va="center",
            fontsize=7,
            color=colors["danger"],
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
    ax_ladder.set_xlim(-4.2, 4.2)
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

    fig.subplots_adjust(left=0.09, right=0.92, top=0.94, bottom=0.08, wspace=0.32, hspace=0.35)
