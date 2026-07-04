import logging
import os
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from decision_engine import process_signal
from state_manager import record_trade

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "signals.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

app = FastAPI(title="ICT Autonomous Trader")


class SignalPayload(BaseModel):
    asset: str
    action: str
    zone_hit: str
    sweep_level: float
    fvg_top: float
    fvg_bottom: float
    sl_level: float
    timestamp: datetime


@app.post("/signal")
async def receive_signal(payload: SignalPayload):
    data = payload.model_dump()
    result = process_signal(data)

    logging.info(
        "signal asset=%s action=%s zone=%s approved=%s reason=%s",
        payload.asset,
        payload.action,
        payload.zone_hit,
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
            "result":     "OPEN",
            "r":          0.0,
        })

    return {"status": "ok", **result}


@app.get("/health")
async def health():
    return {"status": "ok"}
