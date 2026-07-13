"""
ICT Signal Poller
Polls Binance M15 data every 30 s, detects ICT signals, and feeds them
directly into the decision_engine — bypassing the TradingView webhook.

Run standalone:  python poller.py
Integrated:      imported by run.py and started as a daemon thread.
"""

import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from decision_engine import process_signal
from ict_detector import detect_ict_signal, fetch_ohlcv, fetch_pdh_pdl
from state_manager import record_trade

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "signals.log")

logger = logging.getLogger("ict_trader")

# ── Configuration ─────────────────────────────────────────────────────────────

ASSETS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
]
MODE          = "24h"
POLL_INTERVAL = 30  # seconds — catches 15m bar closes within 30 s of close

# open_time of the last bar successfully processed per symbol
_last_processed: dict[str, int] = {}


# ── Logging setup ─────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    if not logger.handlers:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _asset_name(symbol: str) -> str:
    return symbol.upper().replace("USDT", "")


def _build_payload(symbol: str, signal: dict, bar_time: datetime) -> dict:
    return {
        "asset":       _asset_name(symbol),
        "action":      signal["action"],
        "zone_hit":    signal["zone_hit"],
        "sweep_level": signal.get("sweep_level", 0.0),
        "fvg_top":     signal["fvg_top"],
        "fvg_bottom":  signal["fvg_bottom"],
        "sl_level":    signal["sl_level"],
        "timestamp":   bar_time.isoformat(),
        "mode":        signal["mode"],
    }


def _fire_signal(payload: dict) -> None:
    """Validate through decision engine; record and dispatch if approved."""
    result = process_signal(payload, mode=MODE)

    logger.info(
        "signal asset=%s action=%s zone=%s mode=%s approved=%s reason=%s",
        payload["asset"], payload["action"], payload["zone_hit"],
        payload["mode"], result["approved"], result["reason"],
    )

    if not result["approved"]:
        return

    record_trade({
        "time":       payload["timestamp"][11:16],   # "HH:MM" slice from ISO string
        "action":     payload["action"],
        "zone_hit":   payload["zone_hit"],
        "fvg_top":    payload["fvg_top"],
        "fvg_bottom": payload["fvg_bottom"],
        "sl_level":   payload["sl_level"],
        "result":     "PENDING_AI",
        "r":          0.0,
    })

    # Kick off Gemini multi-agent evaluation in a separate thread
    try:
        from autonomous_ict_trader import evaluate_and_execute_signal  # lazy import

        threading.Thread(
            target=lambda: asyncio.run(evaluate_and_execute_signal(payload)),
            daemon=True,
            name=f"ai-eval-{payload['asset']}",
        ).start()
    except Exception as exc:
        logger.warning("evaluate_and_execute_signal unavailable: %s", exc)


# ── Poll cycle ────────────────────────────────────────────────────────────────

def poll_once() -> None:
    """Check every asset for a new closed 15m bar and run ICT detection."""
    for symbol in ASSETS:
        try:
            candles = fetch_ohlcv(symbol, interval="15m", limit=60)
            if len(candles) < 22:
                continue

            latest_ts: int = candles[-1]["open_time"]
            if _last_processed.get(symbol) == latest_ts:
                continue  # already handled this bar
            _last_processed[symbol] = latest_ts

            pdh, pdl = fetch_pdh_pdl(symbol)
            signal: Optional[dict] = detect_ict_signal(symbol, candles, pdh, pdl, mode=MODE)

            if signal is None:
                continue

            bar_time = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
            payload  = _build_payload(symbol, signal, bar_time)
            _fire_signal(payload)

        except httpx.HTTPError as exc:
            logger.warning("HTTP error fetching %s: %s", symbol, exc)
        except Exception as exc:
            logger.error("Error processing %s: %s", symbol, exc, exc_info=True)


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_poll_loop() -> None:
    """Blocking loop — intended to run inside a daemon thread from run.py."""
    _configure_logging()
    logger.info(
        "ICT Poller started | assets=%s | interval=%ds | mode=%s",
        ASSETS, POLL_INTERVAL, MODE,
    )
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import sys

    _configure_logging()
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(message)s",
    )
    print(f"ICT Poller | assets={ASSETS} | interval={POLL_INTERVAL}s | Ctrl+C para parar\n")
    try:
        run_poll_loop()
    except KeyboardInterrupt:
        print("\nPoller encerrado.")
