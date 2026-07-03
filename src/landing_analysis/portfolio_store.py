"""Portfolio allocation storage, calculations, and live quotes."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import yfinance as yf
import pandas as pd

from .data_fetcher import detect_market_from_input, normalize_ticker_input

TW_NAME_MAP: dict[str, str] = {
    "台積電": "2330.TW",
    "國巨": "2327.TW",
    "台耀": "4142.TW",
    "台燿": "6274.TWO",
    "群聯": "8299.TW",
    "正2": "00631L.TW",
    "聯發科": "2454.TW",
    "元大50": "0050.TW",
    "元大50正2": "00631L.TW",
}

US_NAME_MAP: dict[str, str] = {
    "GOOGLE": "GOOGL",
    "GOOG": "GOOGL",
    "DRAM-ETF": "DRAM",
    "DRAM": "DRAM",
    "FACEBOOK": "META",
    "MUU": "MUU",
}

QUOTE_CACHE_MS = 5 * 60 * 1000
QUOTE_POLL_MS = 5 * 60 * 1000
_quote_cache: dict[str, object] = {"key": "", "data": {}, "at": 0.0}
_symbol_cache: dict[str, str | None] = {}


@dataclass
class PortfolioRow:
    name: str
    note: str = ""
    position: str = "long"
    shares: float = 0.0
    cost: float = 0.0

    @property
    def position_label(self) -> str:
        return "Short" if self.position == "short" else "Long"


@dataclass
class PortfolioSection:
    id: str
    title: str
    currency: str
    has_rate: bool
    rate: float = 31.53
    rows: list[PortfolioRow] = field(default_factory=list)


@dataclass
class PortfolioRowCalc:
    row: PortfolioRow
    subtotal: float
    twd: float
    weight: float
    price: float | None = None
    pl_pct: float | None = None


@dataclass
class PortfolioSectionCalc:
    section: PortfolioSection
    items: list[PortfolioRowCalc]
    total: float
    total_twd: float


def default_portfolio_path(data_dir: Path | None = None) -> Path:
    root = data_dir or Path(__file__).resolve().parents[2] / "data" / "portfolio"
    root.mkdir(parents=True, exist_ok=True)
    return root / "股市配比.md"


def normalize_position(position: str) -> str:
    text = str(position or "").strip().lower()
    if text in {"short", "s"} or "短" in text:
        return "short"
    return "long"


def parse_position_text(text: str) -> str:
    return normalize_position(text)


def _parse_rate(header: str) -> float:
    match = re.search(r"匯率\s*([\d.]+)|rate\s*([\d.]+)", header, re.I)
    if match:
        return float(match.group(1) or match.group(2))
    return 31.53


def parse_section_header(header: str) -> PortfolioSection | None:
    text = header.strip()
    if text.startswith("台股") or text.startswith("TW Stocks"):
        return PortfolioSection(id="tw", title="TW Stocks", currency="TWD", has_rate=False)
    if "美股" in text or "US Stocks" in text:
        return PortfolioSection(
            id="us",
            title="US Stocks",
            currency="USD",
            has_rate=True,
            rate=_parse_rate(text),
        )
    return None


def parse_markdown(text: str) -> list[PortfolioSection]:
    if not text.strip():
        return []
    sections: list[PortfolioSection] = []
    for block in re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]:
        lines = block.splitlines()
        sec = parse_section_header(lines[0])
        if sec is None:
            continue
        for line in lines:
            if not line.startswith("|"):
                continue
            if any(
                token in line
                for token in ("股票名稱", "Stock", "------", "合計", "Total")
            ):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if not cols or not cols[0]:
                continue
            has_note = sec.id == "tw" and len(cols) >= 7
            has_position = len(cols) >= 6
            if has_note:
                name, note, position, shares, cost = cols[0], cols[1], cols[2], cols[3], cols[4]
            elif has_position:
                name, note, position, shares, cost = cols[0], "", cols[1], cols[2], cols[3]
            else:
                name, note, position, shares, cost = cols[0], "", "long", cols[1], cols[2]
            try:
                shares_f = float(str(shares).replace(",", ""))
                cost_f = float(str(cost).replace(",", ""))
            except ValueError:
                shares_f, cost_f = 0.0, 0.0
            sec.rows.append(
                PortfolioRow(
                    name=name,
                    note=note,
                    position=parse_position_text(position),
                    shares=shares_f,
                    cost=cost_f,
                )
            )
        if sec.rows:
            sections.append(sec)
    return sections


def load_portfolio(path: Path) -> tuple[list[PortfolioSection], float]:
    if not path.exists():
        return [], 0.0
    text = path.read_text(encoding="utf-8")
    sections = parse_markdown(text)
    budget = 0.0
    match = re.search(r"^budget:\s*([\d.]+)\s*$", text, flags=re.MULTILINE | re.I)
    if match:
        budget = float(match.group(1))
    return sections, budget


def _fmt_plain(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def to_markdown(sections: list[PortfolioSection], budget: float = 0.0) -> str:
    lines = [
        "# 股市配比",
        "",
        "> 由落點分析系統管理，修改後按「儲存配比」更新此檔案。",
        "",
    ]
    if budget > 0:
        lines.extend([f"budget: {budget}", ""])
    lines.append("---")
    lines.append("")

    for index, sec in enumerate(sections):
        calc = calc_section(sec)
        has_note = sec.id == "tw"
        if sec.has_rate:
            lines.append(f"## {sec.title}（美金，匯率 {sec.rate}）")
        else:
            lines.append(f"## {sec.title}")
        lines.append("")
        header = "| 股票名稱 | "
        divider = "| ------ | "
        if has_note:
            header += "備註 | "
            divider += "------ | "
        header += "部位 | 股數 | 成本 | 總價 | 比重 |"
        divider += "------ | ------ | ------ | ------ | ------ |"
        lines.extend([header, divider])
        for item in calc.items:
            row = item.row
            if not row.name and not row.shares and not row.cost:
                continue
            line = f"| {row.name} | "
            if has_note:
                line += f"{row.note} | "
            line += (
                f"{row.position_label} | {_fmt_plain(row.shares)} | {_fmt_plain(row.cost)} | "
                f"{_fmt_plain(item.subtotal)} | {item.weight:.2f}% |"
            )
            lines.append(line)
        lines.append(
            f"| | {'| ' if has_note else ''}| | **合計** | {_fmt_plain(calc.total)} | **100%** |"
        )
        lines.append("")
        if not sec.has_rate:
            lines.append("> 總價 = 股數 × 成本　｜　比重 = 該筆總價 ÷ 合計 × 100%")
            lines.append("")
        if index < len(sections) - 1:
            lines.extend(["---", ""])
    return "\n".join(lines).strip() + "\n"


def save_portfolio(path: Path, sections: list[PortfolioSection], budget: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(sections, budget), encoding="utf-8")


def calc_section(section: PortfolioSection) -> PortfolioSectionCalc:
    rate = section.rate if section.has_rate else 1.0
    items: list[PortfolioRowCalc] = []
    total = 0.0
    for row in section.rows:
        shares = float(row.shares or 0)
        cost = float(row.cost or 0)
        subtotal = shares * cost
        total += subtotal
        items.append(
            PortfolioRowCalc(
                row=row,
                subtotal=subtotal,
                twd=subtotal * rate,
                weight=0.0,
            )
        )
    for item in items:
        item.weight = (item.subtotal / total * 100) if total > 0 else 0.0
    return PortfolioSectionCalc(section=section, items=items, total=total, total_twd=total * rate)


def calc_position_stats(section: PortfolioSection) -> dict[str, dict[str, float]]:
    calc = calc_section(section)
    long_amount = short_amount = long_twd = short_twd = 0.0
    for item in calc.items:
        bucket_amount, bucket_twd = (short_amount, short_twd) if item.row.position == "short" else (long_amount, long_twd)
        if item.row.position == "short":
            short_amount += item.subtotal
            short_twd += item.twd
        else:
            long_amount += item.subtotal
            long_twd += item.twd
    total = calc.total
    return {
        "long": {
            "amount": long_amount if section.id == "us" else long_twd,
            "twd": long_twd,
            "weight": (long_amount / total * 100) if total > 0 else 0.0,
        },
        "short": {
            "amount": short_amount if section.id == "us" else short_twd,
            "twd": short_twd,
            "weight": (short_amount / total * 100) if total > 0 else 0.0,
        },
        "total_twd": calc.total_twd,
    }


def portfolio_total_twd(sections: list[PortfolioSection]) -> float:
    return sum(calc_section(sec).total_twd for sec in sections)


def _search_yahoo_symbol(market: str, name: str) -> str | None:
    import json
    import urllib.parse
    import urllib.request

    url = (
        "https://query2.finance.yahoo.com/v1/finance/search?q="
        + urllib.parse.quote(name)
        + "&quotesCount=10&newsCount=0"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    quotes = [q for q in payload.get("quotes", []) if isinstance(q.get("symbol"), str)]
    if not quotes:
        return None
    if market == "tw":
        for quote in quotes:
            symbol = quote["symbol"]
            if symbol.endswith(".TW") or symbol.endswith(".TWO"):
                return symbol
        return None
    for quote in quotes:
        symbol = quote["symbol"]
        if "." not in symbol and quote.get("quoteType") in {"EQUITY", "ETF", "MUTUALFUND"}:
            return symbol
    return quotes[0]["symbol"]


def _chart_price_yahoo_api(symbol: str) -> float | None:
    import json
    import urllib.parse
    import urllib.request

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?interval=1d&range=5d"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    results = payload.get("chart", {}).get("result") or []
    if not results:
        return None
    meta = results[0].get("meta", {})
    price = meta.get("regularMarketPrice")
    if price is not None:
        return float(price)
    quotes = results[0].get("indicators", {}).get("quote", [{}])
    if quotes:
        closes = [c for c in quotes[0].get("close", []) if c is not None]
        if closes:
            return float(closes[-1])
    return None


def _chart_price_yfinance(symbol: str) -> float | None:
    ticker = yf.Ticker(symbol)
    price = getattr(ticker.fast_info, "last_price", None)
    if price is not None:
        return float(price)
    hist = yf.download(symbol, period="5d", progress=False, auto_adjust=True, threads=False)
    if hist is None or hist.empty:
        return None
    if isinstance(hist.columns, pd.MultiIndex):
        close = hist["Close"]
        if isinstance(close, pd.DataFrame):
            series = close.iloc[:, 0]
        else:
            series = close
    else:
        series = hist["Close"]
    return float(series.iloc[-1])


def _chart_price(symbol: str) -> float | None:
    for fetcher in (_chart_price_yahoo_api, _chart_price_yfinance):
        try:
            price = fetcher(symbol)
            if price is not None:
                return price
        except Exception:
            continue
    return None


def _batch_prices(symbols: list[str]) -> dict[str, float]:
    unique = list(dict.fromkeys(symbols))
    prices: dict[str, float] = {}
    if not unique:
        return prices
    if len(unique) > 1:
        try:
            data = yf.download(
                unique,
                period="5d",
                progress=False,
                auto_adjust=True,
                threads=True,
                group_by="column",
            )
            if data is not None and not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    for sym in unique:
                        if sym not in data.columns.get_level_values(1,):
                            continue
                        closes = data["Close", sym].dropna()
                        if not closes.empty:
                            prices[sym] = float(closes.iloc[-1])
                elif len(unique) == 1:
                    closes = data["Close"].dropna()
                    if not closes.empty:
                        prices[unique[0]] = float(closes.iloc[-1])
        except Exception:
            pass
    for sym in unique:
        if sym not in prices:
            price = _chart_price(sym)
            if price is not None:
                prices[sym] = price
    return prices


def resolve_symbol(market: str, name: str) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    cache_key = f"{market}:{text.upper()}"
    if cache_key in _symbol_cache:
        return _symbol_cache[cache_key]

    if market == "us":
        mapped = US_NAME_MAP.get(text.upper()) or US_NAME_MAP.get(text)
        if mapped:
            _symbol_cache[cache_key] = mapped
            return mapped
        if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", text.upper()):
            _symbol_cache[cache_key] = text.upper()
            return text.upper()
        try:
            symbol = _search_yahoo_symbol(market, text)
        except Exception:
            symbol = None
        _symbol_cache[cache_key] = symbol
        return symbol

    if text in TW_NAME_MAP:
        _symbol_cache[cache_key] = TW_NAME_MAP[text]
        return TW_NAME_MAP[text]
    if re.fullmatch(r"[0-9]{4}[A-Za-z]?", text):
        code = text.upper()
        for suffix in (".TW", ".TWO"):
            symbol = f"{code}{suffix}"
            price = _chart_price(symbol)
            if price is not None:
                _symbol_cache[cache_key] = symbol
                return symbol
        symbol = f"{code}.TW"
        _symbol_cache[cache_key] = symbol
        return symbol

    market_guess = detect_market_from_input(text)
    normalized = normalize_ticker_input(text, market_guess)
    if market_guess == "台股":
        _symbol_cache[cache_key] = normalized
        return normalized
    try:
        symbol = _search_yahoo_symbol("us", text)
    except Exception:
        symbol = normalized if normalized else None
    _symbol_cache[cache_key] = symbol
    return symbol


def fetch_quotes(
    sections: list[PortfolioSection],
    *,
    force: bool = False,
) -> dict[str, dict[str, float | str]]:
    requests: list[tuple[str, str]] = []
    for sec in sections:
        for row in sec.rows:
            name = str(row.name or "").strip()
            if not name:
                continue
            key = f"{sec.id}:{name}"
            symbol = resolve_symbol(sec.id, name)
            if symbol:
                requests.append((key, symbol))

    cache_key = "|".join(sorted(f"{k}={s}" for k, s in requests))
    now = time.time()
    if (
        not force
        and _quote_cache["key"] == cache_key
        and now - float(_quote_cache["at"]) < QUOTE_CACHE_MS / 1000
    ):
        return dict(_quote_cache["data"])

    quotes: dict[str, dict[str, float | str]] = {}
    symbol_list = [s for _, s in requests]
    prices = _batch_prices(symbol_list)
    for key, symbol in requests:
        price = prices.get(symbol)
        if price is not None:
            quotes[key] = {"price": price, "symbol": symbol}

    _quote_cache["key"] = cache_key
    _quote_cache["data"] = quotes
    _quote_cache["at"] = now
    return quotes


def apply_quotes(calc: PortfolioSectionCalc, quotes: dict[str, dict[str, float | str]]) -> None:
    sec = calc.section
    for item in calc.items:
        key = f"{sec.id}:{item.row.name.strip()}"
        quote = quotes.get(key)
        if not quote:
            item.price = None
            item.pl_pct = None
            continue
        price = float(quote["price"])
        item.price = price
        if item.row.cost:
            item.pl_pct = ((price - item.row.cost) / item.row.cost) * 100
        else:
            item.pl_pct = None
