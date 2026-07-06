import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_trade():
    return {
        "time": "10:00",
        "action": "BUY",
        "zone_hit": "london_low",
        "fvg_top": 18360.0,
        "fvg_bottom": 18352.0,
        "sl_level": 18348.0,
        "result": "OPEN",
        "r": 0.0,
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    log_file = str(tmp_path / "signals.log")
    monkeypatch.setattr("webhook_server.LOG_FILE", log_file)
    monkeypatch.setattr("state_manager.STATE_FILE", str(tmp_path / "state.json"))
    from webhook_server import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests — state_manager.close_trade
# ---------------------------------------------------------------------------

def test_close_trade_win_updates_result():
    from state_manager import record_trade, close_trade, get_stops_today, load_state
    record_trade(_open_trade())
    updated = close_trade(0, "WIN", 3.0)
    assert updated["result"] == "WIN"
    assert updated["r"] == 3.0
    assert get_stops_today() == 0


def test_close_trade_stop_increments_stops():
    from state_manager import record_trade, close_trade, get_stops_today
    record_trade(_open_trade())
    close_trade(0, "STOP", -1.0)
    assert get_stops_today() == 1


def test_close_trade_already_closed_raises():
    from state_manager import record_trade, close_trade
    record_trade(_open_trade())
    close_trade(0, "WIN", 3.0)
    with pytest.raises(ValueError, match="already closed"):
        close_trade(0, "STOP", -1.0)


def test_close_trade_invalid_index_raises():
    from state_manager import record_trade, close_trade
    record_trade(_open_trade())
    with pytest.raises(IndexError):
        close_trade(999, "WIN", 3.0)


# ---------------------------------------------------------------------------
# Integration tests — POST /trade/close
# ---------------------------------------------------------------------------

def test_close_endpoint_win(client):
    from state_manager import record_trade
    record_trade(_open_trade())
    r = client.post("/trade/close", json={"trade_index": 0, "result": "WIN", "r": 3.0})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["trade"]["result"] == "WIN"
    assert data["trade"]["r"] == 3.0


def test_close_endpoint_stop_increments(client):
    from state_manager import record_trade, get_stops_today
    record_trade(_open_trade())
    r = client.post("/trade/close", json={"trade_index": 0, "result": "STOP", "r": -1.0})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert get_stops_today() == 1


def test_close_endpoint_already_closed(client):
    from state_manager import record_trade
    record_trade(_open_trade())
    client.post("/trade/close", json={"trade_index": 0, "result": "WIN", "r": 3.0})
    r = client.post("/trade/close", json={"trade_index": 0, "result": "STOP", "r": -1.0})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert "already closed" in data["reason"]


def test_close_endpoint_invalid_index(client):
    r = client.post("/trade/close", json={"trade_index": 999, "result": "WIN", "r": 3.0})
    assert r.status_code == 200
    assert r.json()["status"] == "error"
