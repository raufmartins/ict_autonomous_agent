import json
import pytest


def test_load_state_returns_fresh_when_file_missing():
    from state_manager import load_state
    state = load_state()
    assert state["stops_today"] == 0
    assert state["trades_today"] == []
    assert "date" in state


def test_load_state_resets_when_date_is_old(isolate_state):
    import state_manager
    old = {"date": "2020-01-01", "stops_today": 2, "trades_today": [{"r": -1}]}
    with open(state_manager.STATE_FILE, "w") as f:
        json.dump(old, f)
    state = state_manager.load_state()
    assert state["stops_today"] == 0
    assert state["trades_today"] == []


def test_record_stop_increments_counter():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    assert get_stops_today() == 1


def test_record_win_does_not_increment_stops():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "WIN", "r": 3.0, "action": "BUY"})
    assert get_stops_today() == 0


def test_two_stops_then_three_signals_blocked():
    from state_manager import record_trade, get_stops_today
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    record_trade({"result": "STOP", "r": -1.0, "action": "SELL"})
    assert get_stops_today() == 2


def test_state_persists_across_calls(isolate_state):
    from state_manager import record_trade, load_state
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    state = load_state()
    assert len(state["trades_today"]) == 1
