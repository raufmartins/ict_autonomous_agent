import json
import os
from datetime import datetime
import pytz

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
EST = pytz.timezone("America/New_York")


def _today_est() -> str:
    return datetime.now(EST).strftime("%Y-%m-%d")


def _fresh_state() -> dict:
    return {"date": _today_est(), "stops_today": 0, "trades_today": []}


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return _fresh_state()
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _fresh_state()
    if data.get("date") != _today_est():
        return _fresh_state()
    return data


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def record_trade(trade: dict) -> None:
    state = load_state()
    state["trades_today"].append(trade)
    if trade.get("result") == "STOP":
        state["stops_today"] += 1
    save_state(state)


def get_stops_today() -> int:
    return load_state()["stops_today"]
