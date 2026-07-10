#!/usr/bin/env python3
"""Discord bot exposing landing-point analysis as slash commands.

Commands (all read-only):
  /quote   <ticker>                         latest price
  /analyze <ticker> [period] [lookback]     landing-point summary embed
  /chart   <ticker> [period] [lookback] [institutional]  Scheme C chart image

Run:  python discord_bot.py   (needs DISCORD_BOT_TOKEN in env or stock/.env)
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from landing_analysis.env_config import load_local_env

load_local_env()

try:
    import discord
    from discord import app_commands
except ImportError:  # pragma: no cover - dependency hint
    sys.exit(
        "缺少 discord.py，請先安裝：pip install -r requirements.txt "
        "(或 pip install discord.py)"
    )

from landing_analysis.bot_charts import render_scheme_c_png
from landing_analysis.bot_service import (
    DEFAULT_LOOKBACK,
    MAX_LOOKBACK,
    MIN_LOOKBACK,
    VALID_PERIODS,
    AnalysisBundle,
    TickerError,
    analyze_ticker,
    get_quote,
    top_levels,
)

EMBED_ACCENT = 0x4A7FA8
EMBED_DANGER = 0xB86A62


def _fmt_price(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 50:
        return f"{value:,.2f}"
    return f"{value:,.3f}"


def _level_line(level) -> str:
    from landing_analysis.scheme_c_charts import format_methods_zh

    stars = "★" * min(level.strength, 5)
    methods = format_methods_zh(level.methods)
    return f"`{_fmt_price(level.price)}` {stars} · {methods}"


def _error_embed(message: str) -> "discord.Embed":
    return discord.Embed(title="無法處理", description=message, color=EMBED_DANGER)


def _quote_embed(quote) -> "discord.Embed":
    embed = discord.Embed(title=f"{quote.symbol} · 現價", color=EMBED_ACCENT)
    embed.add_field(name="現價", value=_fmt_price(quote.price), inline=True)
    if quote.change_pct is not None:
        arrow = "▲" if quote.change >= 0 else "▼"
        embed.add_field(
            name="漲跌",
            value=f"{arrow} {abs(quote.change):,.2f} ({quote.change_pct:+.2f}%)",
            inline=True,
        )
    embed.add_field(name="市場", value=quote.market, inline=True)
    embed.set_footer(text=f"資料日期 {quote.as_of:%Y-%m-%d}")
    return embed


def _analysis_embed(bundle: AnalysisBundle) -> "discord.Embed":
    a = bundle.analysis
    embed = discord.Embed(
        title=f"{bundle.symbol} 落點分析",
        color=EMBED_ACCENT,
    )
    embed.add_field(name="現價", value=_fmt_price(a.current_price), inline=True)
    embed.add_field(name="ATR", value=f"{a.atr:,.2f}", inline=True)
    embed.add_field(name="市場", value=bundle.market, inline=True)
    embed.add_field(
        name="波段高 / 低",
        value=f"{_fmt_price(a.swing_high)} / {_fmt_price(a.swing_low)}",
        inline=True,
    )
    embed.add_field(
        name="分析視窗",
        value=f"{bundle.lookback} 交易日 · {bundle.period}",
        inline=True,
    )

    supports = top_levels(a, "support", 3)
    resistances = top_levels(a, "resistance", 3)
    if supports:
        embed.add_field(
            name="主要支撐",
            value="\n".join(_level_line(lv) for lv in supports),
            inline=False,
        )
    if resistances:
        embed.add_field(
            name="主要阻力",
            value="\n".join(_level_line(lv) for lv in resistances),
            inline=False,
        )
    embed.set_footer(text=f"分析區間 {a.train_start:%Y-%m-%d} ~ {a.train_end:%Y-%m-%d}")
    return embed


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

_PERIOD_CHOICES = [app_commands.Choice(name=p, value=p) for p in VALID_PERIODS]


@client.event
async def on_ready():
    guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    print(f"已登入為 {client.user} · 指令已同步")


@tree.command(name="quote", description="查詢股票現價")
@app_commands.describe(ticker="股票代號，例如 MU、2330")
async def quote_command(interaction: "discord.Interaction", ticker: str):
    await interaction.response.defer(thinking=True)
    try:
        quote = await asyncio.to_thread(get_quote, ticker)
    except TickerError as exc:
        await interaction.followup.send(embed=_error_embed(str(exc)))
        return
    except Exception as exc:  # noqa: BLE001
        await interaction.followup.send(embed=_error_embed(f"查詢失敗：{exc}"))
        return
    await interaction.followup.send(embed=_quote_embed(quote))


@tree.command(name="analyze", description="落點分析摘要（支撐/阻力）")
@app_commands.describe(
    ticker="股票代號，例如 MU、2330",
    period="資料期間",
    lookback=f"分析視窗交易日（{MIN_LOOKBACK}-{MAX_LOOKBACK}）",
)
@app_commands.choices(period=_PERIOD_CHOICES)
async def analyze_command(
    interaction: "discord.Interaction",
    ticker: str,
    period: app_commands.Choice[str] | None = None,
    lookback: int | None = None,
):
    await interaction.response.defer(thinking=True)
    try:
        bundle = await asyncio.to_thread(
            analyze_ticker,
            ticker,
            period=period.value if period else None,
            lookback=lookback,
        )
    except TickerError as exc:
        await interaction.followup.send(embed=_error_embed(str(exc)))
        return
    except Exception as exc:  # noqa: BLE001
        await interaction.followup.send(embed=_error_embed(f"分析失敗：{exc}"))
        return
    await interaction.followup.send(embed=_analysis_embed(bundle))


@tree.command(name="chart", description="落點分析圖（Scheme C）")
@app_commands.describe(
    ticker="股票代號，例如 MU、2330",
    period="資料期間",
    lookback=f"分析視窗交易日（{MIN_LOOKBACK}-{MAX_LOOKBACK}）",
    institutional="台股才有效：是否顯示三大法人",
)
@app_commands.choices(period=_PERIOD_CHOICES)
async def chart_command(
    interaction: "discord.Interaction",
    ticker: str,
    period: app_commands.Choice[str] | None = None,
    lookback: int | None = None,
    institutional: bool = False,
):
    await interaction.response.defer(thinking=True)
    try:
        bundle = await asyncio.to_thread(
            analyze_ticker,
            ticker,
            period=period.value if period else None,
            lookback=lookback,
            with_institutional=institutional,
        )
        png = await asyncio.to_thread(render_scheme_c_png, bundle)
    except TickerError as exc:
        await interaction.followup.send(embed=_error_embed(str(exc)))
        return
    except Exception as exc:  # noqa: BLE001
        await interaction.followup.send(embed=_error_embed(f"繪圖失敗：{exc}"))
        return

    a = bundle.analysis
    embed = discord.Embed(title=f"{bundle.symbol} 落點分析圖", color=EMBED_ACCENT)
    embed.add_field(name="現價", value=_fmt_price(a.current_price), inline=True)
    supports = top_levels(a, "support", 1)
    resistances = top_levels(a, "resistance", 1)
    if supports:
        embed.add_field(name="最強支撐", value=_level_line(supports[0]), inline=False)
    if resistances:
        embed.add_field(name="最強阻力", value=_level_line(resistances[0]), inline=False)
    if institutional and bundle.is_tw and bundle.institutional is None:
        embed.set_footer(text="三大法人資料無法取得（需 FINMIND_TOKEN）")

    filename = f"{bundle.symbol.replace('.', '_')}_scheme_c.png"
    file = discord.File(io.BytesIO(png), filename=filename)
    embed.set_image(url=f"attachment://{filename}")
    await interaction.followup.send(embed=embed, file=file)


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        sys.exit(
            "找不到 DISCORD_BOT_TOKEN。請在 stock/.env 加入：\n"
            "DISCORD_BOT_TOKEN=你的_bot_token"
        )
    client.run(token)


if __name__ == "__main__":
    main()
