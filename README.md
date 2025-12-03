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

## Run locally

The dashboard is a static page (`static/dashboard.html`) that reads `bubble_today.json` and `data/bubble_daily.csv`. Generate the data and serve the page locally with:

```bash
python bubble_calc.py
python -m http.server 8000
# open http://localhost:8000/static/dashboard.html
```

## Run with Docker

A lightweight image definition is provided in `Dockerfile` (based on `python:3.11-slim`). Build and run with your API keys and a configurable port:

```bash
docker build -t bubble-dashboard .
docker run -it --rm \
  -p 8000:8000 \
  -e FINNHUB_API_KEY=YOUR_FINNHUB_API_KEY \
  -e FRED_API_KEY=YOUR_FRED_API_KEY \
  -e PORT=8000 \
  bubble-dashboard
# open http://localhost:8000/static/dashboard.html
```

Environment variables:

- `FINNHUB_API_KEY` (optional but recommended): for QQQ price history and IPO data.
- `FRED_API_KEY` (optional but recommended): for VIX and ANFCI series.
- `PORT` (optional): HTTP server port exposed from the container (defaults to `8000`).

The container entrypoint computes the latest bubble index on startup and then serves the repo directory with Python’s built-in HTTP server for a minimal footprint.
