# bubble-index-dashboard

## Environment configuration

This project uses environment variables (via a `.env` file and `python-dotenv`) to load API keys for external data providers.

Create a `.env` file in the project root with:

```text
FINNHUB_API_KEY=YOUR_FINNHUB_API_KEY_HERE
FRED_API_KEY=YOUR_FRED_API_KEY_HERE
```

These keys are required to access Finnhub (for QQQ pricing and IPO data) and FRED (for VIX and ANFCI). The `.env` file is ignored by Git via `.gitignore` and should not be committed.

When running in GitHub Codespaces or GitHub Actions, you can also set `FINNHUB_API_KEY` and `FRED_API_KEY` as environment variables or repository secrets instead of using a `.env` file.

## FX triangular-arbitrage monitor

`fx_arbitrage.py` scans Yahoo Finance spot-FX quotes for triangular conversion loops such as
`USD -> EUR -> GBP -> USD`. It is a **paper-trading/monitoring tool only**: retail FX
arbitrage is extremely latency-sensitive, and apparent opportunities can be eliminated by
spreads, commissions, slippage, rejected fills, funding costs, tax, and broker limits. The
script does not guarantee daily income or "free money".

Example scan:

```bash
python fx_arbitrage.py --currencies USD,EUR,GBP,JPY --starting-amount 1000 --transaction-cost-bps 3 --min-net-profit-pct 0
```

Useful options:

- `--currencies`: comma-separated currency universe to scan. At least three currencies are required.
- `--starting-amount`: paper amount used to estimate hypothetical profit.
- `--transaction-cost-bps`: estimated spread/fee/slippage per conversion leg; triangular loops pay this three times.
- `--min-net-profit-pct`: minimum estimated net profit percentage to display.
- `--write-csv`: append displayed signals to `data/fx_arbitrage_signals.csv` for review.

For real trading, add broker-specific market data and order-routing code only after paper
trading, latency measurement, legal/compliance review, and hard risk limits.
