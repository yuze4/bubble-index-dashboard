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

## Run with Docker

Build the image from the project root:

```bash
docker build -t bubble-index-dashboard .
```

Start the container and serve the dashboard on <http://localhost:8000>. The entrypoint will compute the latest bubble index (with placeholders unless the APIs succeed) and then expose the static site:

```bash
docker run \
  -p 8000:8000 \
  -e FINNHUB_API_KEY=YOUR_FINNHUB_API_KEY_HERE \
  -e FRED_API_KEY=YOUR_FRED_API_KEY_HERE \
  -e USE_PLACEHOLDERS=true \
  bubble-index-dashboard
```

Environment switches:

- `FINNHUB_API_KEY` – optional, needed for IPO stats (Finnhub) and price data if you later swap in a Finnhub price source.
- `FRED_API_KEY` – optional, needed for VIX and ANFCI from FRED.
- `USE_PLACEHOLDERS` – set to `false` to fail fast when a data fetch is missing (defaults to `true`).
- `MODE` – entrypoint mode. The default command is `serve` (compute then `python -m http.server 8000`). Use `compute` to run only the data refresh, or provide any other command to exec directly (e.g., `docker run bubble-index-dashboard bash`).

The generated `bubble_today.json` and `data/bubble_daily.csv` are written to the container’s `/app` directory. You can mount a local folder to persist them:

```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data bubble-index-dashboard
```
