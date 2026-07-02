"""Strategy presets and configuration."""

from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class StrategyConfig:
    name: str
    description: str
    stop_loss_pct: float = 0.10
    rsi_buy: float = 45.0
    rsi_sell: float = 70.0
    trail_pct: float = 0.15
    tolerance: float = 0.015
    use_resistance_tp: bool = True
    breakout_buy: bool = False
    trend_ma_filter: bool = False
    require_macd: bool = False
    require_volume_shrink: bool = False
    require_candlestick: bool = False
    use_macd_exit: bool = False
    volume_expand_breakout: bool = False
    signal_confirm_min: int = 0  # 0 = 啟用的訊號全部通過；N = 至少 N 項通過

    def summary(self) -> str:
        tp = "阻力停利" if self.use_resistance_tp else "僅移動停利"
        extras = []
        if self.breakout_buy:
            extras.append("突破加碼")
        if self.trend_ma_filter:
            extras.append("MA50過濾")
        signal_parts = []
        if self.require_macd:
            signal_parts.append("MACD")
        if self.require_volume_shrink:
            signal_parts.append("量縮")
        if self.require_candlestick:
            signal_parts.append("K棒")
        if signal_parts:
            need = self.signal_confirm_min or len(signal_parts)
            extras.append(f"{'/'.join(signal_parts)}≥{need}")
        if self.use_macd_exit:
            extras.append("MACD死叉出場")
        extra = " · ".join(extras) if extras else "無"
        return (
            f"停損 -{self.stop_loss_pct*100:.0f}% · RSI<{self.rsi_buy:.0f} · "
            f"移動 -{self.trail_pct*100:.0f}% · {tp} · {extra}"
        )


EQUIPMENT_TEMPLATE = StrategyConfig(
    name="設備股",
    description="適用 KLAC、AMAT、ASML、LRCX 等半導體設備股",
    stop_loss_pct=0.08,
    rsi_buy=50.0,
    rsi_sell=70.0,
    trail_pct=0.12,
    use_resistance_tp=True,
    breakout_buy=False,
    trend_ma_filter=False,
    require_macd=True,
    require_volume_shrink=True,
    require_candlestick=True,
    use_macd_exit=True,
    signal_confirm_min=2,
)

HOT_TEMPLATE = StrategyConfig(
    name="熱門股",
    description="適用 MU、SNDK、MRVL、INTC 等記憶體/暴漲股",
    stop_loss_pct=0.12,
    rsi_buy=55.0,
    rsi_sell=72.0,
    trail_pct=0.20,
    use_resistance_tp=False,
    breakout_buy=True,
    trend_ma_filter=True,
    require_macd=True,
    require_volume_shrink=True,
    require_candlestick=True,
    use_macd_exit=True,
    volume_expand_breakout=True,
    signal_confirm_min=2,
)

CUSTOM_TEMPLATE = StrategyConfig(
    name="自訂",
    description="自行調整所有回測參數",
    stop_loss_pct=0.10,
    rsi_buy=45.0,
    rsi_sell=70.0,
    trail_pct=0.15,
    use_resistance_tp=True,
    breakout_buy=False,
    trend_ma_filter=False,
)

STRATEGY_TEMPLATES: dict[str, StrategyConfig] = {
    "設備股": EQUIPMENT_TEMPLATE,
    "熱門股": HOT_TEMPLATE,
    "自訂": CUSTOM_TEMPLATE,
}

TEMPLATE_TICKERS: dict[str, dict[str, str]] = {
    "設備股": {
        "KLA (KLAC)": "KLAC",
        "應材 (AMAT)": "AMAT",
        "ASML": "ASML",
        "Lam (LRCX)": "LRCX",
    },
    "熱門股": {
        "美光 (MU)": "MU",
        "SanDisk (SNDK)": "SNDK",
        "Marvell (MRVL)": "MRVL",
        "Intel (INTC)": "INTC",
        "AMD": "AMD",
        "NVIDIA (NVDA)": "NVDA",
    },
}


def get_template(name: str) -> StrategyConfig:
    return deepcopy(STRATEGY_TEMPLATES.get(name, CUSTOM_TEMPLATE))
