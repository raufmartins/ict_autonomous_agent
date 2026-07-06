import logging
import math
from datetime import datetime, timedelta
import httpx
import pytz
from state_manager import get_stops_today
from asset_params import get_asset_params

logger = logging.getLogger("ict_trader")

EST = pytz.timezone("America/New_York")
FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
DAILY_STOP_LIMIT = 2


def process_signal(payload: dict, mode: str = "intraday") -> dict:
    if payload.get("action") not in {"BUY", "SELL"}:
        return {"approved": False, "reason": "INVALID_ACTION"}
    if not _in_trading_window(mode=mode):
        return {"approved": False, "reason": "OUTSIDE_WINDOW"}
    if _check_red_folder():
        return {"approved": False, "reason": "RED_FOLDER"}
    valid, reason = _validate_fvg(payload)
    if not valid:
        return {"approved": False, "reason": reason}
    if get_stops_today() >= DAILY_STOP_LIMIT:
        return {"approved": False, "reason": "DAILY_LIMIT"}
    return {"approved": True, "reason": "APPROVED"}


def _check_red_folder(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(EST)
    try:
        response = httpx.get(FOREX_FACTORY_URL, timeout=5.0)
        response.raise_for_status()
        events = response.json()
    except Exception as exc:
        logger.warning("Red Folder API error (failing safe): %s", exc)
        return True  # fail safe: block on API error
    window_start = now - timedelta(minutes=30)
    window_end = now + timedelta(minutes=30)
    for event in events:
        if event.get("impact") != "High":
            continue
        try:
            event_time = datetime.fromisoformat(event["date"]).astimezone(EST)
        except (KeyError, ValueError):
            continue
        if window_start <= event_time <= window_end:
            return True
    return False


def _in_trading_window(now: datetime = None, mode: str = "intraday") -> bool:
    if mode == "24h":
        return True
    if now is None:
        now = datetime.now(EST)
    if mode == "daily":
        start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        end   = now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return start <= now <= end
    # intraday (default)
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end   = now.replace(hour=11, minute=0,  second=0, microsecond=0)
    return start <= now <= end


def _validate_fvg(payload: dict) -> tuple[bool, str]:
    action     = payload.get("action")
    fvg_top    = payload.get("fvg_top", 0.0)
    fvg_bottom = payload.get("fvg_bottom", 0.0)
    sl_level   = payload.get("sl_level", 0.0)
    asset      = payload.get("asset") or ""

    params = get_asset_params(asset)
    tick_size = params["tick_size"]
    decimals = max(0, -math.floor(math.log10(tick_size)))
    min_gap = round(params["min_fvg_ticks"] * tick_size, decimals)

    if fvg_top <= fvg_bottom:
        return False, "INVALID_STRUCTURE"
    if round(fvg_top - fvg_bottom, decimals) < min_gap:
        return False, "INVALID_STRUCTURE"
    if action == "BUY"  and sl_level >= fvg_bottom:
        return False, "INVALID_STRUCTURE"
    if action == "SELL" and sl_level <= fvg_top:
        return False, "INVALID_STRUCTURE"
    return True, "OK"
