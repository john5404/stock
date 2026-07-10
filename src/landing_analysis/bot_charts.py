"""Headless (Agg) rendering of the Scheme C landing chart to PNG bytes.

Used by the Discord bot so charts can be produced on a server without a GUI.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

from .bot_service import AnalysisBundle
from .scheme_c_charts import draw_scheme_c

# Preferred CJK-capable fonts across platforms; the first installed one is used.
_CJK_FONT_CANDIDATES = (
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "PingFang TC",
    "Heiti TC",
    "Noto Sans CJK TC",
    "Noto Sans CJK SC",
    "Noto Sans TC",
    "WenQuanYi Zen Hei",
    "Source Han Sans TW",
    "Source Han Sans CN",
)


def _configure_fonts() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [name for name in _CJK_FONT_CANDIDATES if name in available]
    plt.rcParams["font.sans-serif"] = chosen + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


_configure_fonts()

# Low-contrast dark palette mirroring the desktop UI chart theme.
CHART_COLORS: dict[str, str] = {
    "bg": "#030405",
    "surface": "#080a0d",
    "surface_elevated": "#0d1014",
    "chart_bg": "#050608",
    "border": "#171c24",
    "grid": "#141820",
    "text": "#9aa3ad",
    "muted": "#5f6770",
    "accent": "#4a7fa8",
    "accent_dark": "#3d6d92",
    "success": "#3d8f7a",
    "danger": "#b86a62",
    "warning": "#b8894a",
}


def render_scheme_c_png(bundle: AnalysisBundle, *, strategy_name: str = "落點分析") -> bytes:
    """Render the 4-panel Scheme C dashboard for a bundle and return PNG bytes."""

    fig = plt.figure(figsize=(11, 8.2), dpi=110)
    fig.patch.set_facecolor(CHART_COLORS["bg"])
    grid = fig.add_gridspec(3, 2, width_ratios=[2.4, 1], height_ratios=[1.1, 1.0, 0.75])
    ax_price = fig.add_subplot(grid[0:2, 0])
    ax_ladder = fig.add_subplot(grid[0, 1])
    ax_vp = fig.add_subplot(grid[1, 1])
    ax_inst = fig.add_subplot(grid[2, :])

    try:
        draw_scheme_c(
            fig,
            ax_price,
            ax_ladder,
            ax_vp,
            ax_inst,
            bundle.df,
            bundle.analysis,
            ticker=bundle.symbol,
            strategy_name=strategy_name,
            colors=CHART_COLORS,
            lookback_days=bundle.lookback,
            inst_df=bundle.institutional,
            is_tw=bundle.is_tw,
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
        buf.seek(0)
        return buf.getvalue()
    finally:
        plt.close(fig)
