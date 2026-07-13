import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from decision_engine import process_signal
from state_manager import record_trade, close_trade
from autonomous_ict_trader import evaluate_and_execute_signal

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "signals.log")

logger = logging.getLogger("ict_trader")


def _configure_logging() -> None:
    if not logger.handlers:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


app = FastAPI(title="ICT Autonomous Trader")


class SignalPayload(BaseModel):
    asset: str
    action: str
    zone_hit: str
    sweep_level: float
    fvg_top: float
    fvg_bottom: float
    sl_level: float
    timestamp: datetime = None
    mode: str = "intraday"   # "intraday" | "daily" | "24h"

    def model_post_init(self, __context):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@app.post("/signal")
async def receive_signal(payload: SignalPayload, background_tasks: BackgroundTasks):
    _configure_logging()
    data = payload.model_dump()
    result = process_signal(data, mode=payload.mode)

    logger.info(
        "signal asset=%s action=%s zone=%s mode=%s approved=%s reason=%s",
        payload.asset.replace("\n", ""),
        payload.action.replace("\n", ""),
        payload.zone_hit.replace("\n", ""),
        payload.mode,
        result["approved"],
        result["reason"],
    )

    if result["approved"]:
        record_trade({
            "time":       payload.timestamp.strftime("%H:%M"),
            "action":     payload.action,
            "zone_hit":   payload.zone_hit,
            "fvg_top":    payload.fvg_top,
            "fvg_bottom": payload.fvg_bottom,
            "sl_level":   payload.sl_level,
            "result":     "PENDING_AI",
            "r":          0.0,
        })
        background_tasks.add_task(evaluate_and_execute_signal, data)

    return {"status": "ok", **result}


class CloseTradePayload(BaseModel):
    trade_index: int
    result: str
    r: float


@app.post("/trade/close")
async def close_trade_endpoint(payload: CloseTradePayload):
    try:
        trade = close_trade(payload.trade_index, payload.result, payload.r)
    except (IndexError, ValueError) as exc:
        return {"status": "error", "reason": str(exc)}
    return {"status": "ok", "trade": trade}


@app.get("/health")
async def health():
    return {"status": "ok"}
