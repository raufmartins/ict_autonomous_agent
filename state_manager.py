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


def close_trade(trade_index: int, result: str, r: float) -> dict:
    if result not in ("WIN", "STOP"):
        raise ValueError(f"result must be 'WIN' or 'STOP', got '{result}'")
    if result == "WIN" and r <= 0:
        raise ValueError(f"WIN trade must have r > 0, got {r}")
    if result == "STOP" and r > 0:
        raise ValueError(f"STOP trade must have r <= 0, got {r}")
    state = load_state()
    trades = state["trades_today"]
    if not trades:
        raise IndexError("no trades recorded today")
    if trade_index < 0 or trade_index >= len(trades):
        raise IndexError(f"trade_index {trade_index} out of range (0..{len(trades) - 1})")
    trade = trades[trade_index]
    if trade.get("result") in ("WIN", "STOP"):
        raise ValueError("trade already closed")
    if result == "STOP":
        state["stops_today"] += 1
    trade["result"] = result
    trade["r"] = r
    save_state(state)
    if result == "WIN":
        try:
            from rag_store import save_win_trade
            save_win_trade(trade)
        except Exception:
            pass
    return trade


def get_stops_today() -> int:
    return load_state()["stops_today"]


def get_recent_trades(asset: str, limit: int = 3) -> list[dict]:
    state = load_state()
    trades = [t for t in state.get("trades_today", []) if t.get("asset") == asset]
    return trades[-limit:] if trades else []
