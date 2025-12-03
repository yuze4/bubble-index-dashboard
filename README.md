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
