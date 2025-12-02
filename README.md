# bubble-index-dashboard

## Environment configuration

Create a `.env` file in the project root to provide API credentials for data fetching:

```
FINNHUB_API_KEY=YOUR_FINNHUB_API_KEY_HERE
FRED_API_KEY=YOUR_FRED_API_KEY_HERE
```

These keys are required to access Finnhub (for QQQ pricing and IPO data) and FRED (for VIX and ANFCI). The `.env` file is ignored by Git via `.gitignore` and should not be committed.
