import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from decision_engine import process_signal
from state_manager import record_trade

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

    def model_post_init(self, __context):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@app.post("/signal")
async def receive_signal(payload: SignalPayload):
    _configure_logging()
    data = payload.model_dump()
    result = process_signal(data)

    logger.info(
        "signal asset=%s action=%s zone=%s approved=%s reason=%s",
        payload.asset.replace("\n", ""),
        payload.action.replace("\n", ""),
        payload.zone_hit.replace("\n", ""),
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
