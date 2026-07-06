import pytest


def test_nq_returns_correct_params():
    from asset_params import get_asset_params
    params = get_asset_params("NQ1!")
    assert params["tick_size"] == 0.25
    assert params["min_fvg_ticks"] == 2


def test_eth_returns_correct_params():
    from asset_params import get_asset_params
    params = get_asset_params("ETHUSDT")
    assert params["tick_size"] == 0.01
    assert params["min_fvg_ticks"] == 4


def test_btc_returns_correct_params():
    from asset_params import get_asset_params
    params = get_asset_params("BTCUSDT")
    assert params["tick_size"] == 0.10
    assert params["min_fvg_ticks"] == 3


def test_unknown_asset_returns_default():
    from asset_params import get_asset_params
    params = get_asset_params("XYZ")
    assert params["tick_size"] == 0.01
    assert params["min_fvg_ticks"] == 2


def test_case_insensitive():
    from asset_params import get_asset_params
    params_lower = get_asset_params("ethusdt")
    params_upper = get_asset_params("ETHUSDT")
    assert params_lower == params_upper


def test_validate_fvg_uses_asset_params_for_eth():
    from decision_engine import _validate_fvg
    payload = {
        "asset": "ETHUSDT",
        "action": "BUY",
        "fvg_top": 1740.05,
        "fvg_bottom": 1740.01,
        "sl_level": 1739.90,
    }
    ok, reason = _validate_fvg(payload)
    assert ok is True


def test_validate_fvg_rejects_tiny_eth_fvg():
    from decision_engine import _validate_fvg
    payload = {
        "asset": "ETHUSDT",
        "action": "BUY",
        "fvg_top": 1740.02,
        "fvg_bottom": 1740.01,
        "sl_level": 1739.90,
    }
    ok, reason = _validate_fvg(payload)
    assert ok is False
    assert reason == "INVALID_STRUCTURE"
