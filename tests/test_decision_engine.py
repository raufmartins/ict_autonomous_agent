from datetime import datetime
from unittest.mock import patch
import pytz
import pytest

EST = pytz.timezone("America/New_York")

VALID_BUY = {
    "asset": "NQ1!",
    "action": "BUY",
    "zone_hit": "london_low",
    "sweep_level": 18350.0,
    "fvg_top": 18360.0,
    "fvg_bottom": 18352.0,
    "sl_level": 18348.0,
}

VALID_SELL = {
    "asset": "NQ1!",
    "action": "SELL",
    "zone_hit": "london_high",
    "sweep_level": 18420.0,
    "fvg_top": 18415.0,
    "fvg_bottom": 18408.0,
    "sl_level": 18422.0,
}

_INSIDE  = datetime(2026, 7, 4, 10, 15, tzinfo=EST)
_OUTSIDE = datetime(2026, 7, 4,  8,  0, tzinfo=EST)


def test_in_trading_window_accepts_inside():
    from decision_engine import _in_trading_window
    assert _in_trading_window(_INSIDE) is True


def test_in_trading_window_rejects_outside():
    from decision_engine import _in_trading_window
    assert _in_trading_window(_OUTSIDE) is False


def test_in_trading_window_accepts_boundary_start():
    from decision_engine import _in_trading_window
    t = datetime(2026, 7, 4, 9, 30, tzinfo=EST)
    assert _in_trading_window(t) is True


def test_in_trading_window_rejects_boundary_end():
    from decision_engine import _in_trading_window
    t = datetime(2026, 7, 4, 11, 1, tzinfo=EST)
    assert _in_trading_window(t) is False


def test_validate_fvg_valid_buy():
    from decision_engine import _validate_fvg
    ok, reason = _validate_fvg(VALID_BUY)
    assert ok is True


def test_validate_fvg_valid_sell():
    from decision_engine import _validate_fvg
    ok, reason = _validate_fvg(VALID_SELL)
    assert ok is True


def test_validate_fvg_inverted_top_bottom():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "fvg_top": 18352.0, "fvg_bottom": 18360.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False
    assert reason == "INVALID_STRUCTURE"


def test_validate_fvg_too_small():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "fvg_top": 18352.25, "fvg_bottom": 18352.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


def test_validate_fvg_sl_above_fvg_bottom_on_buy():
    from decision_engine import _validate_fvg
    bad = {**VALID_BUY, "sl_level": 18355.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


def test_validate_fvg_sl_below_fvg_top_on_sell():
    from decision_engine import _validate_fvg
    bad = {**VALID_SELL, "sl_level": 18410.0}
    ok, reason = _validate_fvg(bad)
    assert ok is False


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
@patch("decision_engine.get_stops_today", return_value=0)
def test_all_clear_returns_approved(mock_stops, mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is True
    assert result["reason"] == "APPROVED"


@patch("decision_engine._check_red_folder", return_value=True)
def test_red_folder_rejects(mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "RED_FOLDER"


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=False)
def test_outside_window_rejects(mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "OUTSIDE_WINDOW"


@patch("decision_engine._check_red_folder", return_value=False)
@patch("decision_engine._in_trading_window", return_value=True)
@patch("decision_engine.get_stops_today", return_value=2)
def test_daily_limit_rejects(mock_stops, mock_window, mock_rf):
    from decision_engine import process_signal
    result = process_signal(VALID_BUY)
    assert result["approved"] is False
    assert result["reason"] == "DAILY_LIMIT"


def test_check_red_folder_returns_true_on_api_failure():
    from decision_engine import _check_red_folder
    with patch("decision_engine.httpx.get", side_effect=Exception("timeout")):
        assert _check_red_folder() is True


def test_check_red_folder_returns_false_when_no_high_impact():
    from decision_engine import _check_red_folder
    fake_events = [{"impact": "Low", "date": "2026-07-04T10:00:00-04:00"}]
    with patch("decision_engine.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json = lambda: fake_events
        assert _check_red_folder() is False
