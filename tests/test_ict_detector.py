"""Tests for ict_detector — ICT signal detection logic."""
from unittest.mock import MagicMock, patch

import pytest

from ict_detector import detect_ict_signal, fetch_ohlcv, fetch_pdh_pdl


# ── Candle factories ──────────────────────────────────────────────────────────

def _c(o, h, l, c, ts=0):
    return {"open_time": ts, "open": float(o), "high": float(h),
            "low": float(l), "close": float(c)}


def _flat(n=25, price=100.0):
    """n flat candles — establishes zone high/low at `price`."""
    return [_c(price, price, price, price, i * 900_000) for i in range(n)]


def _buy_setup():
    """
    Minimal list that fires a BUY via zone1_low sweep.

    bar[2]  low=99.0 sweeps zone_low=100.0, closes at 100.3 (back inside)
    bar[1]  bull displacement: body=1.8, range=2.0 → ratio=0.9 ≥ 0.70
    bar[0]  FVG: low=102.5 > high[2]=100.5
    bars[3+] flat at 100 → zone_low=100.0
    """
    candles = _flat(22, price=100.0)
    candles[-3] = _c(o=100.0, h=100.5, l=99.0,  c=100.3)   # sweep
    candles[-2] = _c(o=100.3, h=102.3, l=100.1, c=102.1)   # displacement
    candles[-1] = _c(o=102.1, h=104.0, l=102.5, c=103.5)   # signal / FVG
    return candles


def _sell_setup():
    """
    Minimal list that fires a SELL via zone1_high sweep.

    bar[2]  high=101.0 sweeps zone_high=100.0, closes at 99.7
    bar[1]  bear displacement: body=1.8, range=2.0 → ratio=0.9
    bar[0]  bear FVG: low[2]=99.5 > high[0]=97.5
    bars[3+] flat at 100 → zone_high=100.0
    """
    candles = _flat(22, price=100.0)
    candles[-3] = _c(o=100.0, h=101.0, l=99.5, c=99.7)    # sweep
    candles[-2] = _c(o=99.7,  h=99.9,  l=97.9, c=98.1)    # displacement
    candles[-1] = _c(o=98.1,  h=97.5,  l=96.0, c=96.5)    # signal / FVG
    return candles


def _pdl_only_setup(pdl=95.0):
    """
    BUY via PDL sweep only (zone_low set low enough that it's NOT swept).

    zone_low comes from bars[3+] all with l=89.0.
    bar[2] dips to 94.5 — below pdl=95 but above zone_low=89.
    """
    candles = [_c(90, 91, 89, 90, i * 900_000) for i in range(22)]
    candles[-3] = _c(o=96.0, h=96.5, l=94.5, c=96.2)   # sweeps pdl=95
    candles[-2] = _c(o=96.2, h=98.2, l=96.0, c=98.0)   # displacement
    candles[-1] = _c(o=98.0, h=100.0, l=98.5, c=99.5)  # FVG: low=98.5 > high[2]=96.5
    return candles


def _pdh_only_setup(pdh=105.0):
    """
    SELL via PDH sweep only (zone_high set high enough that it's NOT swept).

    bars[3+] all with h=111.0.
    bar[2] spikes to 105.5 — above pdh=105 but below zone_high=111.
    """
    candles = [_c(110, 111, 109, 110, i * 900_000) for i in range(22)]
    candles[-3] = _c(o=104.0, h=105.5, l=103.5, c=103.8)  # sweeps pdh=105
    candles[-2] = _c(o=103.8, h=104.0, l=101.8, c=102.0)  # displacement
    candles[-1] = _c(o=102.0, h=101.5, l=100.0, c=100.5)  # bear FVG: low[2]=103.5 > high[0]=101.5
    return candles


# ── detect_ict_signal ─────────────────────────────────────────────────────────

class TestDetectICTSignal:

    def test_buy_zone_sweep_fires(self):
        sig = detect_ict_signal("BTCUSDT", _buy_setup(), pdh=110.0, pdl=80.0)
        assert sig is not None
        assert sig["action"] == "BUY"
        assert sig["zone_hit"] == "zone1_low"
        assert sig["fvg_top"] == 102.5
        assert sig["fvg_bottom"] == 100.5

    def test_sell_zone_sweep_fires(self):
        sig = detect_ict_signal("BTCUSDT", _sell_setup(), pdh=110.0, pdl=80.0)
        assert sig is not None
        assert sig["action"] == "SELL"
        assert sig["zone_hit"] == "zone1_high"
        assert sig["fvg_top"] == 99.5
        assert sig["fvg_bottom"] == 97.5

    def test_buy_pdl_sweep_fires(self):
        candles = _pdl_only_setup(pdl=95.0)
        sig = detect_ict_signal("BTCUSDT", candles, pdh=120.0, pdl=95.0)
        assert sig is not None
        assert sig["action"] == "BUY"
        assert sig["zone_hit"] == "pdl"
        assert sig["sweep_level"] == 95.0

    def test_sell_pdh_sweep_fires(self):
        candles = _pdh_only_setup(pdh=105.0)
        sig = detect_ict_signal("BTCUSDT", candles, pdh=105.0, pdl=80.0)
        assert sig is not None
        assert sig["action"] == "SELL"
        assert sig["zone_hit"] == "pdh"
        assert sig["sweep_level"] == 105.0

    def test_no_signal_without_fvg(self):
        candles = _buy_setup()
        # Override bar[0]: low=99.0 < high[2]=100.5 → no FVG
        candles[-1] = _c(o=102.0, h=104.0, l=99.0, c=103.5)
        assert detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0) is None

    def test_no_signal_weak_displacement(self):
        candles = _buy_setup()
        # body=0.2, range=2.0 → ratio=0.10 < 0.70
        candles[-2] = _c(o=100.3, h=102.3, l=100.1, c=100.5)
        assert detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0) is None

    def test_no_signal_without_sweep(self):
        # bar[2].low=100.1 > zone_low=100.0 and bar[2].low > pdl=80 → no sweep
        candles = _flat(22, price=100.0)
        candles[-3] = _c(o=100.0, h=100.5, l=100.1, c=100.2)   # no sweep
        candles[-2] = _c(o=100.2, h=102.2, l=100.0, c=102.0)
        candles[-1] = _c(o=102.0, h=104.0, l=102.5, c=103.5)
        assert detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0) is None

    def test_no_signal_sweep_without_close_back(self):
        # bar[2] dips below zone but CLOSES BELOW too — not a sweep
        candles = _flat(22, price=100.0)
        candles[-3] = _c(o=100.0, h=100.5, l=99.0, c=99.5)    # closes BELOW zone
        candles[-2] = _c(o=99.5,  h=101.5, l=99.3, c=101.3)
        candles[-1] = _c(o=101.3, h=103.0, l=101.5, c=102.5)
        assert detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0) is None

    def test_not_enough_candles(self):
        assert detect_ict_signal("BTCUSDT", _flat(10), 110.0, 80.0) is None

    def test_sl_below_three_bar_low_on_buy(self):
        candles = _buy_setup()
        sig = detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0)
        lowest_3 = min(candles[-1]["low"], candles[-2]["low"], candles[-3]["low"])
        assert sig["sl_level"] < lowest_3

    def test_sl_above_three_bar_high_on_sell(self):
        candles = _sell_setup()
        sig = detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0)
        highest_3 = max(candles[-1]["high"], candles[-2]["high"], candles[-3]["high"])
        assert sig["sl_level"] > highest_3

    def test_mode_returned_in_signal(self):
        sig = detect_ict_signal("ETHUSDT", _buy_setup(), pdh=110.0, pdl=80.0, mode="24h")
        assert sig is not None
        assert sig["mode"] == "24h"

    def test_daily_mode_uses_smaller_lookback(self):
        """daily mode: lookback=5; zone from bars[3..7] only."""
        candles = _flat(25, price=100.0)
        # Drop bars[3..7] to low=99.0 so zone_low=99.0 in daily mode
        for i in range(3, 8):
            candles[-(i + 1)] = _c(100.0, 100.0, 99.0, 100.0)
        # bar[2] sweeps 99.0
        candles[-3] = _c(100.0, 100.5, 98.5, 99.5)
        # bar[1]: displacement
        candles[-2] = _c(99.5, 101.5, 99.3, 101.3)
        # bar[0]: FVG: low=101.5 > high[2]=100.5
        candles[-1] = _c(101.3, 103.0, 101.5, 102.5)
        sig = detect_ict_signal("BTCUSDT", candles, pdh=110.0, pdl=80.0, mode="daily")
        assert sig is not None
        assert sig["mode"] == "daily"

    def test_eth_asset_params_applied(self):
        """ETH tick_size=0.01 → SL offset is 0.02 below lowest low."""
        candles = _buy_setup()
        sig = detect_ict_signal("ETHUSDT", candles, pdh=110.0, pdl=80.0)
        lowest_3 = min(candles[-1]["low"], candles[-2]["low"], candles[-3]["low"])
        assert abs(sig["sl_level"] - (lowest_3 - 0.02)) < 1e-9


# ── fetch_ohlcv ───────────────────────────────────────────────────────────────

class TestFetchOHLCV:

    def _mock_klines(self, n):
        return [
            [i * 900_000, "100.0", "101.0", "99.0", "100.5", "1000",
             (i + 1) * 900_000 - 1, "0", "0", "0", "0", "0"]
            for i in range(n)
        ]

    def test_strips_open_bar(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._mock_klines(5)
        with patch("ict_detector.httpx.get", return_value=mock_resp):
            result = fetch_ohlcv("BTCUSDT")
        assert len(result) == 4   # 5 fetched - 1 open = 4

    def test_returns_floats(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._mock_klines(3)
        with patch("ict_detector.httpx.get", return_value=mock_resp):
            result = fetch_ohlcv("BTCUSDT")
        for field in ("open", "high", "low", "close"):
            assert isinstance(result[0][field], float)

    def test_oldest_first_ordering(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._mock_klines(5)
        with patch("ict_detector.httpx.get", return_value=mock_resp):
            result = fetch_ohlcv("BTCUSDT")
        ts = [c["open_time"] for c in result]
        assert ts == sorted(ts)


# ── fetch_pdh_pdl ─────────────────────────────────────────────────────────────

class TestFetchPDHPDL:

    def test_returns_yesterday_not_today(self):
        """klines[-2] is yesterday (completed); klines[-1] is today (open)."""
        klines = [
            [0,         "90", "105", "88", "100", "1000", 86399999, "0", "0", "0", "0", "0"],  # 2d ago
            [86400000,  "95", "115", "94", "110", "1200", 172799999, "0", "0", "0", "0", "0"],  # yesterday
            [172800000, "110", "120", "108", "115", "900", 259199999, "0", "0", "0", "0", "0"],  # today (open)
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = klines
        with patch("ict_detector.httpx.get", return_value=mock_resp):
            pdh, pdl = fetch_pdh_pdl("BTCUSDT")
        assert pdh == 115.0  # yesterday's high
        assert pdl == 94.0   # yesterday's low

    def test_returns_floats(self):
        klines = [[0, "100", "110", "90", "105", "1000", 86399999, "0", "0", "0", "0", "0"]] * 3
        mock_resp = MagicMock()
        mock_resp.json.return_value = klines
        with patch("ict_detector.httpx.get", return_value=mock_resp):
            pdh, pdl = fetch_pdh_pdl("BTCUSDT")
        assert isinstance(pdh, float)
        assert isinstance(pdl, float)
