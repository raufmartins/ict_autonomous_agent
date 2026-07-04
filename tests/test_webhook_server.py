import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

VALID_PAYLOAD = {
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
def client(tmp_path, monkeypatch):
    log_file = str(tmp_path / "signals.log")
    monkeypatch.setattr("webhook_server.LOG_FILE", log_file)
    from webhook_server import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@patch("webhook_server.process_signal", return_value={"approved": True, "reason": "APPROVED"})
@patch("webhook_server.record_trade")
def test_approved_signal_returns_200(mock_record, mock_process, client):
    r = client.post("/signal", json=VALID_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["approved"] is True
    assert data["reason"] == "APPROVED"
    mock_record.assert_called_once()


@patch("webhook_server.process_signal", return_value={"approved": False, "reason": "RED_FOLDER"})
@patch("webhook_server.record_trade")
def test_rejected_signal_does_not_record_trade(mock_record, mock_process, client):
    r = client.post("/signal", json=VALID_PAYLOAD)
    assert r.status_code == 200
    assert r.json()["approved"] is False
    mock_record.assert_not_called()


def test_missing_field_returns_422(client):
    r = client.post("/signal", json={"asset": "NQ1!"})
    assert r.status_code == 422


def test_invalid_action_still_processed(client):
    bad = {**VALID_PAYLOAD, "action": "HOLD"}
    with patch("webhook_server.process_signal", return_value={"approved": False, "reason": "INVALID_STRUCTURE"}):
        with patch("webhook_server.record_trade"):
            r = client.post("/signal", json=bad)
    assert r.status_code == 200
