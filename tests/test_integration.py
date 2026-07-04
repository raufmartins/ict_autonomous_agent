"""
Teste end-to-end: simula um webhook do TradingView chegando com um sinal válido
e verifica que o estado é atualizado e o log é escrito.
"""
import os
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime
import pytz

EST = pytz.timezone("America/New_York")

VALID_SIGNAL = {
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
    "timestamp": "2026-07-04T10:15:00",
}


@pytest.fixture
def full_client(tmp_path, monkeypatch):
    monkeypatch.setattr("state_manager.STATE_FILE", str(tmp_path / "state.json"))
    log_file = str(tmp_path / "signals.log")
    monkeypatch.setattr("webhook_server.LOG_FILE", log_file)
    from webhook_server import app
    return TestClient(app), tmp_path


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
def test_approved_signal_updates_state(mock_window, mock_rf, full_client):
    client, tmp_path = full_client
    r = client.post("/signal", json=VALID_SIGNAL)
    assert r.status_code == 200
    assert r.json()["approved"] is True

    with open(tmp_path / "state.json") as f:
        state = json.load(f)
    assert len(state["trades_today"]) == 1
    trade = state["trades_today"][0]
    assert trade["action"] == "BUY"
    assert trade["zone_hit"] == "london_low"
    assert trade["result"] == "OPEN"

    log_content = (tmp_path / "signals.log").read_text()
    assert "BUY" in log_content
    assert "APPROVED" in log_content


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
def test_two_stops_block_third_signal(mock_window, mock_rf, full_client):
    client, tmp_path = full_client
    from state_manager import record_trade
    record_trade({"result": "STOP", "r": -1.0, "action": "BUY"})
    record_trade({"result": "STOP", "r": -1.0, "action": "SELL"})

    r = client.post("/signal", json=VALID_SIGNAL)
    assert r.json()["approved"] is False
    assert r.json()["reason"] == "DAILY_LIMIT"


def test_red_folder_blocks_valid_signal(full_client):
    client, _ = full_client
    with patch("decision_engine._check_red_folder", return_value=True):
        r = client.post("/signal", json=VALID_SIGNAL)
    assert r.status_code == 200
    assert r.json()["approved"] is False
    assert r.json()["reason"] == "RED_FOLDER"
