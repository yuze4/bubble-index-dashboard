"""Foreign-exchange triangular-arbitrage monitor and paper-trading helper.

This module scans spot FX crosses for triangular-arbitrage inconsistencies such
as USD -> EUR -> GBP -> USD. It is intentionally a monitor/simulator, not an
auto-trading bot: live FX execution requires broker-specific APIs, execution
quality controls, compliance review, and careful risk management.

The output is useful for learning, alerting, and paper trading. It does not
promise profit; apparent opportunities can disappear before execution and may be
fully consumed by spreads, commissions, slippage, funding costs, and API latency.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yfinance as yf

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CURRENCIES: Tuple[str, ...] = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD")
DEFAULT_LOG_PATH = DATA_DIR / "fx_arbitrage_signals.csv"


@dataclass(frozen=True)
class RateQuote:
    """A normalized directional FX quote.

    ``base`` units are converted into ``quote`` units at ``rate``. For example,
    EUR/USD at 1.10 is represented as base="EUR", quote="USD", rate=1.10.
    """

    base: str
    quote: str
    rate: float
    symbol: str
    timestamp: str


@dataclass(frozen=True)
class ArbitrageSignal:
    """Result for one triangular conversion path."""

    path: Tuple[str, str, str, str]
    gross_return: float
    net_return: float
    gross_profit_pct: float
    net_profit_pct: float
    starting_amount: float
    ending_amount: float
    estimated_profit: float
    transaction_cost_bps: float
    timestamp: str


def yahoo_symbol(base: str, quote: str) -> str:
    """Return Yahoo Finance's spot-FX ticker for a currency pair."""
    return f"{base}{quote}=X"


def fetch_direct_quote(base: str, quote: str) -> Optional[RateQuote]:
    """Fetch one direct spot-FX quote from Yahoo Finance.

    Returns ``None`` when Yahoo has no usable latest price for the pair.
    """
    symbol = yahoo_symbol(base, quote)
    ticker = yf.Ticker(symbol)
    try:
        history = ticker.history(period="2d", interval="1d", auto_adjust=False)
    except Exception as exc:  # pragma: no cover - network/provider guard
        print(f"[fetch_direct_quote] Unable to fetch {symbol}: {exc}")
        return None

    if history.empty or "Close" not in history:
        return None

    closes = history["Close"].dropna()
    if closes.empty:
        return None

    rate = float(closes.iloc[-1])
    if not math.isfinite(rate) or rate <= 0:
        return None

    return RateQuote(
        base=base,
        quote=quote,
        rate=rate,
        symbol=symbol,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def fetch_fx_quotes(currencies: Sequence[str]) -> Dict[Tuple[str, str], RateQuote]:
    """Fetch and normalize directional FX quotes for every requested pair.

    Yahoo Finance does not publish every possible orientation. This function
    stores both the direct quote and its inverse so downstream path math can use
    a simple mapping lookup.
    """
    quotes: Dict[Tuple[str, str], RateQuote] = {}

    for base, quote in itertools.combinations(sorted(set(currencies)), 2):
        direct = fetch_direct_quote(base, quote)
        if direct is None:
            inverse_direct = fetch_direct_quote(quote, base)
            if inverse_direct is None:
                continue
            inverse_rate = 1.0 / inverse_direct.rate
            quotes[(base, quote)] = RateQuote(
                base=base,
                quote=quote,
                rate=inverse_rate,
                symbol=f"inverse:{inverse_direct.symbol}",
                timestamp=inverse_direct.timestamp,
            )
            quotes[(quote, base)] = inverse_direct
            continue

        quotes[(base, quote)] = direct
        quotes[(quote, base)] = RateQuote(
            base=quote,
            quote=base,
            rate=1.0 / direct.rate,
            symbol=f"inverse:{direct.symbol}",
            timestamp=direct.timestamp,
        )

    return quotes


def path_return(path: Sequence[str], quotes: Mapping[Tuple[str, str], RateQuote]) -> Optional[float]:
    """Calculate the multiplicative return for a conversion path."""
    result = 1.0
    for start, end in zip(path, path[1:]):
        quote = quotes.get((start, end))
        if quote is None:
            return None
        result *= quote.rate
    return result


def scan_triangular_arbitrage(
    quotes: Mapping[Tuple[str, str], RateQuote],
    currencies: Sequence[str],
    *,
    starting_amount: float = 1_000.0,
    transaction_cost_bps: float = 3.0,
    min_net_profit_pct: float = 0.0,
) -> List[ArbitrageSignal]:
    """Scan all three-currency loops and return profitable paper signals.

    ``transaction_cost_bps`` is applied once per conversion leg, so triangular
    loops pay it three times. Increase this value to model retail spreads and
    slippage more conservatively.
    """
    if starting_amount <= 0:
        raise ValueError("starting_amount must be positive")
    if transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps cannot be negative")

    unique_currencies = sorted(set(currencies))
    cost_multiplier = (1.0 - transaction_cost_bps / 10_000.0) ** 3
    timestamp = datetime.now(timezone.utc).isoformat()
    signals: List[ArbitrageSignal] = []

    for a, b, c in itertools.permutations(unique_currencies, 3):
        path = (a, b, c, a)
        gross = path_return(path, quotes)
        if gross is None:
            continue

        net = gross * cost_multiplier
        gross_profit_pct = (gross - 1.0) * 100.0
        net_profit_pct = (net - 1.0) * 100.0
        if net_profit_pct < min_net_profit_pct:
            continue

        ending_amount = starting_amount * net
        signals.append(
            ArbitrageSignal(
                path=path,
                gross_return=gross,
                net_return=net,
                gross_profit_pct=gross_profit_pct,
                net_profit_pct=net_profit_pct,
                starting_amount=starting_amount,
                ending_amount=ending_amount,
                estimated_profit=ending_amount - starting_amount,
                transaction_cost_bps=transaction_cost_bps,
                timestamp=timestamp,
            )
        )

    signals.sort(key=lambda signal: signal.net_profit_pct, reverse=True)
    return signals


def append_signals(signals: Iterable[ArbitrageSignal], path: Path = DEFAULT_LOG_PATH) -> None:
    """Append signals to a CSV file for later review."""
    rows = [asdict(signal) for signal in signals]
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def parse_currencies(value: str) -> Tuple[str, ...]:
    """Parse a comma-separated currency list."""
    currencies = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    if len(currencies) < 3:
        raise argparse.ArgumentTypeError("at least three currencies are required")
    return currencies


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan Yahoo Finance FX quotes for triangular-arbitrage paper signals. "
            "This is not financial advice and does not guarantee income."
        )
    )
    parser.add_argument(
        "--currencies",
        type=parse_currencies,
        default=DEFAULT_CURRENCIES,
        help="Comma-separated currencies to scan, e.g. USD,EUR,GBP,JPY.",
    )
    parser.add_argument(
        "--starting-amount",
        type=float,
        default=1_000.0,
        help="Paper amount used to estimate profit in the first path currency.",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=3.0,
        help="Estimated spread/fee/slippage per leg in basis points.",
    )
    parser.add_argument(
        "--min-net-profit-pct",
        type=float,
        default=0.0,
        help="Only show paths whose estimated net profit percentage is at least this value.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of signals to print.",
    )
    parser.add_argument(
        "--write-csv",
        action="store_true",
        help=f"Append printed signals to {DEFAULT_LOG_PATH}.",
    )
    return parser


def main() -> None:
    """Run the CLI scanner."""
    parser = build_parser()
    args = parser.parse_args()

    quotes = fetch_fx_quotes(args.currencies)
    signals = scan_triangular_arbitrage(
        quotes,
        args.currencies,
        starting_amount=args.starting_amount,
        transaction_cost_bps=args.transaction_cost_bps,
        min_net_profit_pct=args.min_net_profit_pct,
    )[: max(args.max_results, 0)]

    payload = {
        "disclaimer": (
            "Paper-trading scan only. FX arbitrage is latency-sensitive and can lose money; "
            "profits are not guaranteed."
        ),
        "currencies": args.currencies,
        "quote_count": len(quotes),
        "signals": [asdict(signal) for signal in signals],
    }
    print(json.dumps(payload, indent=2))

    if args.write_csv:
        append_signals(signals)


if __name__ == "__main__":
    main()
