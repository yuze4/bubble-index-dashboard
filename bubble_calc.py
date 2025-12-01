"""Core engine for the US Tech/AI Bubble Index.

This module fetches market and macro inputs, scores each dimension, and
computes a weighted bubble index. A scheduled cron job can execute this
module directly to refresh `bubble_today.json` and append to
`data/bubble_daily.csv`.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

BUBBLE_JSON = Path("bubble_today.json")
BUBBLE_CSV = DATA_DIR / "bubble_daily.csv"

DEFAULT_WEIGHTS: Dict[str, float] = {
    "priceDeviation": 0.30,
    "totalPutCall": 0.20,
    "smartDumb": 0.15,
    "vix": 0.15,
    "anfci": 0.10,
    "ipoHeat": 0.10,
}


def load_env() -> Dict[str, Optional[str]]:
    """Load environment variables from a `.env` file and the process env."""
    load_dotenv()
    return {
        "FINNHUB_API_KEY": os.getenv("FINNHUB_API_KEY"),
        "FRED_API_KEY": os.getenv("FRED_API_KEY"),
    }


# === Fetchers ===

def fetch_qqq_deviation(api_key: Optional[str]) -> Optional[float]:
    """Fetch deviation of QQQ price vs 200-day MA from Finnhub.

    Uses the daily candle API to retrieve the last ~400 calendar days of data,
    computes a 200-day simple moving average, and returns the deviation of the
    latest close from that average.
    """

    fallback_token = "d4meqc9r01qjidhvcp6gd4meqc9r01qjidhvcp70"
    token = api_key or fallback_token
    if not token:
        print("[fetch_qqq_deviation] FINNHUB_API_KEY missing; cannot compute deviation")
        return None

    now = int(time.time())
    lookback_days = 400  # buffer to ensure >=200 trading days
    params = {
        "symbol": "QQQ",
        "resolution": "D",
        "from": now - lookback_days * 24 * 60 * 60,
        "to": now,
        "token": token,
    }

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/stock/candle", params=params, timeout=15
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - network guard
        print(f"[fetch_qqq_deviation] Finnhub request failed: {exc}")
        return None

    if payload.get("s") != "ok":
        print(f"[fetch_qqq_deviation] Unexpected Finnhub response status: {payload}")
        return None

    closes = payload.get("c") or []
    if len(closes) < 200:
        print(
            f"[fetch_qqq_deviation] Insufficient candles returned ({len(closes)});"
            " need >=200"
        )
        return None

    latest_close = float(closes[-1])
    ma200 = sum(float(c) for c in closes[-200:]) / 200
    deviation = (latest_close / ma200) - 1
    print(
        f"[fetch_qqq_deviation] latest_close={latest_close:.2f}, ma200={ma200:.2f},"
        f" deviation={deviation:.4f}"
    )
    return deviation


def fetch_put_call_ratios() -> Dict[str, Optional[float]]:
    """Fetch put/call ratios from the CBOE daily statistics page.

    Returns a mapping with keys: total, equity, index.
    Currently returns placeholders and should be replaced with real scraping.
    """
    print("[fetch_put_call_ratios] TODO implement CBOE scraping; returning placeholder values")
    return {"total": 0.9, "equity": 0.8, "index": 1.1}


def fetch_vix(api_key: Optional[str]) -> Optional[float]:
    """Fetch the latest VIX close from FRED (series VIXCLS).

    Currently returns a placeholder value until the FRED request is wired up.
    """
    if not api_key:
        print("[fetch_vix] FRED_API_KEY missing; returning placeholder value")
        return 17.5

    # TODO: Implement FRED request for VIXCLS.
    print("[fetch_vix] TODO implement FRED request; returning placeholder value")
    return 17.5


def fetch_anfci(api_key: Optional[str]) -> Optional[float]:
    """Fetch the latest Adjusted National Financial Conditions Index (ANFCI).

    Currently returns a placeholder value until the FRED request is wired up.
    """
    if not api_key:
        print("[fetch_anfci] FRED_API_KEY missing; returning placeholder value")
        return -0.2

    # TODO: Implement FRED request for ANFCI.
    print("[fetch_anfci] TODO implement FRED request; returning placeholder value")
    return -0.2


def fetch_ipo_heat(api_key: Optional[str]) -> Dict[str, Optional[float]]:
    """Fetch IPO activity over the last 30 days from Finnhub.

    Returns a dict with counts and proceeds. Currently a placeholder that
    should be replaced with the real Finnhub IPO calendar call.
    """
    if not api_key:
        print("[fetch_ipo_heat] FINNHUB_API_KEY missing; returning placeholder values")
        return {"count30d": 0, "proceeds30d": 0.0}

    # TODO: Implement Finnhub IPO calendar fetch and aggregation over 30 days.
    print("[fetch_ipo_heat] TODO implement Finnhub IPO calendar request; returning placeholder values")
    return {"count30d": 0, "proceeds30d": 0.0}


# === Scoring helpers ===

def score_price_deviation(deviation: float) -> int:
    """Score QQQ deviation from 200-day MA.

    TODO: refine thresholds. Current heuristic:
    - <= 5% above MA: 0 (calm)
    - 5% to 15%: 1 (elevated)
    - > 15%: 2 (frothy)
    """
    if deviation <= 0.05:
        return 0
    if deviation <= 0.15:
        return 1
    return 2


def score_put_call(total_ratio: float) -> int:
    """Score total put/call ratio.

    TODO: refine thresholds. Current heuristic treats low ratios as frothy.
    """
    if total_ratio >= 1.0:
        return 0
    if total_ratio >= 0.8:
        return 1
    return 2


def score_smart_dumb(equity_pcr: float, index_pcr: float) -> int:
    """Score spread between equity and index put/call ratios.

    The wider equity PCR is below index PCR, the more frothy retail may be.
    TODO: refine thresholds.
    """
    spread = equity_pcr - index_pcr
    if spread >= 0.0:
        return 0
    if spread >= -0.2:
        return 1
    return 2


def score_vix(vix_level: float) -> int:
    """Score VIX level as a fear/greed proxy.

    TODO: refine thresholds.
    """
    if vix_level >= 25:
        return 0
    if vix_level >= 18:
        return 1
    return 2


def score_anfci(anfci_value: float) -> int:
    """Score financial conditions (ANFCI).

    Negative values indicate loose conditions; positive indicates tightness.
    TODO: refine thresholds.
    """
    if anfci_value >= 0.5:
        return 0
    if anfci_value >= 0.0:
        return 1
    return 2


def score_ipo_heat(ipo_count_30d: float) -> int:
    """Score IPO heat using the last 30 days IPO count.

    TODO: refine thresholds and optionally incorporate proceeds.
    """
    if ipo_count_30d <= 5:
        return 0
    if ipo_count_30d <= 15:
        return 1
    return 2


# === Orchestrator ===

def compute_bubble_index(use_placeholders: bool = True) -> Dict[str, Any]:
    """Fetch all indicators, score them, and compute the bubble index.

    Parameters
    ----------
    use_placeholders : bool, optional
        When True, placeholder values are used if live fetchers fail or are
        not implemented. Set to False in production once data fetchers are
        complete.
    """
    env = load_env()
    print("[compute_bubble_index] Starting computation")

    price_dev = fetch_qqq_deviation(env.get("FINNHUB_API_KEY"))
    ratios = fetch_put_call_ratios()
    vix_level = fetch_vix(env.get("FRED_API_KEY"))
    anfci_value = fetch_anfci(env.get("FRED_API_KEY"))
    ipo_stats = fetch_ipo_heat(env.get("FINNHUB_API_KEY"))

    raw_values: Dict[str, Any] = {
        "priceDeviation": price_dev,
        "totalPutCall": ratios.get("total"),
        "equityPutCall": ratios.get("equity"),
        "indexPutCall": ratios.get("index"),
        "vix": vix_level,
        "anfci": anfci_value,
        "ipoCount30d": ipo_stats.get("count30d"),
        "ipoProceeds30d": ipo_stats.get("proceeds30d"),
    }

    # Validate presence or fall back to placeholders.
    for key, value in raw_values.items():
        if value is None:
            if not use_placeholders:
                raise ValueError(f"Missing value for {key} and placeholders disabled")
            print(f"[compute_bubble_index] Placeholder activated for {key}")
            raw_values[key] = 0.0

    scores = {
        "priceDeviation": score_price_deviation(float(raw_values["priceDeviation"])),
        "totalPutCall": score_put_call(float(raw_values["totalPutCall"])),
        "smartDumb": score_smart_dumb(
            float(raw_values["equityPutCall"]), float(raw_values["indexPutCall"])
        ),
        "vix": score_vix(float(raw_values["vix"])),
        "anfci": score_anfci(float(raw_values["anfci"])),
        "ipoHeat": score_ipo_heat(float(raw_values["ipoCount30d"])),
    }

    weighted_score = sum(scores[k] * DEFAULT_WEIGHTS[k] for k in DEFAULT_WEIGHTS)
    bubble_index = round(weighted_score * 5)

    timestamp = datetime.utcnow().isoformat() + "Z"
    result = {
        "timestamp": timestamp,
        "raw": raw_values,
        "scores": scores,
        "weights": DEFAULT_WEIGHTS,
        "weightedScore": weighted_score,
        "bubbleIndex": bubble_index,
    }

    print(f"[compute_bubble_index] Completed with bubble index {bubble_index}")
    return result


def write_outputs(result: Dict[str, Any]) -> None:
    """Persist the latest result to JSON and append to the daily CSV."""
    with BUBBLE_JSON.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[write_outputs] Wrote {BUBBLE_JSON}")

    row = {
        "timestamp": result["timestamp"],
        "bubbleIndex": result["bubbleIndex"],
        **{f"raw_{k}": v for k, v in result["raw"].items()},
        **{f"score_{k}": v for k, v in result["scores"].items()},
    }

    df = pd.DataFrame([row])
    if BUBBLE_CSV.exists():
        df.to_csv(BUBBLE_CSV, mode="a", header=False, index=False)
    else:
        df.to_csv(BUBBLE_CSV, mode="w", header=True, index=False)
    print(f"[write_outputs] Appended row to {BUBBLE_CSV}")


if __name__ == "__main__":
    try:
        result = compute_bubble_index(use_placeholders=True)
        write_outputs(result)
    except Exception as exc:  # pragma: no cover - top level error guard
        print(f"[main] Bubble index computation failed: {exc}")
        raise
