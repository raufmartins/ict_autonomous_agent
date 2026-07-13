"""
ICT Signal Detector — Python port of ict_signals_universal.pine v5.

Fetches M15 OHLCV from Binance public API and replicates the
Sweep → Displacement → FVG signal logic.

Bar indexing convention (matches Pine's [N] notation):
    bar(0) = most recently CLOSED candle  (signal bar)
    bar(1) = one bar prior                (displacement bar)
    bar(2) = two bars prior               (sweep bar)
    bar(3+)= historical structure used to define zones
"""

from typing import Optional

import httpx

from asset_params import get_asset_params

BINANCE_BASE = "https://api.binance.com/api/v3"
_HTTP_TIMEOUT = 10.0


def fetch_ohlcv(symbol: str, interval: str = "15m", limit: int = 60) -> list[dict]:
    """
    Fetch closed OHLCV candles from Binance.
    Returns list ordered oldest → newest; the still-open bar is stripped.
    """
    resp = httpx.get(
        f"{BINANCE_BASE}/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    candles = [
        {
            "open_time": int(k[0]),
            "open":  float(k[1]),
            "high":  float(k[2]),
            "low":   float(k[3]),
            "close": float(k[4]),
        }
        for k in resp.json()
    ]
    return candles[:-1]  # strip the still-open bar


def fetch_pdh_pdl(symbol: str) -> tuple[float, float]:
    """
    Return (pdh, pdl) — the previous completed daily candle's high and low.
    klines[-2] is yesterday; klines[-1] is today's open (incomplete) candle.
    """
    resp = httpx.get(
        f"{BINANCE_BASE}/klines",
        params={"symbol": symbol, "interval": "1d", "limit": 3},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    klines = resp.json()
    prev = klines[-2]
    return float(prev[2]), float(prev[3])   # (high, low)


def detect_ict_signal(
    symbol: str,
    candles: list[dict],
    pdh: float,
    pdl: float,
    mode: str = "24h",
) -> Optional[dict]:
    """
    Detect an ICT BUY or SELL signal on the most recently closed bar.

    Three-bar pattern:
        bar[2]  Sweep bar — wicks through a liquidity level, closes back.
        bar[1]  Displacement — large-body candle (body/range ≥ 70 %).
        bar[0]  Signal bar — a Fair Value Gap is left between bar[0] and bar[2].

    Zone logic: liquidity zones are computed from bars[3 .. 3+lookback-1]
    (the established structure), so bar[2] can legitimately break below/above them.

    Returns a dict matching the SignalPayload schema, or None.
    """
    if len(candles) < 22:
        return None

    def h(i: int) -> float: return candles[-(i + 1)]["high"]
    def l(i: int) -> float: return candles[-(i + 1)]["low"]
    def o(i: int) -> float: return candles[-(i + 1)]["open"]
    def c(i: int) -> float: return candles[-(i + 1)]["close"]

    lb_h = 5 if mode == "daily" else 16
    lb_l = 5 if mode == "daily" else 12
    start = 3   # first bar of historical zone (excludes pattern bars 0, 1, 2)

    # ── Liquidity Zones ───────────────────────────────────────────────────
    zone_high1 = max(h(i) for i in range(start, start + lb_h))
    zone_low1  = min(l(i) for i in range(start, start + lb_h))
    zone_high2 = max(h(i) for i in range(start, start + lb_l))
    zone_low2  = min(l(i) for i in range(start, start + lb_l))

    # ── Sweep Detection at bar[2] ─────────────────────────────────────────
    sweep_bull_z1  = l(2) < zone_low1  and c(2) > zone_low1
    sweep_bull_z2  = l(2) < zone_low2  and c(2) > zone_low2
    sweep_bull_pdl = l(2) < pdl        and c(2) > pdl

    sweep_bear_z1  = h(2) > zone_high1 and c(2) < zone_high1
    sweep_bear_z2  = h(2) > zone_high2 and c(2) < zone_high2
    sweep_bear_pdh = h(2) > pdh        and c(2) < pdh

    any_sweep_bull = sweep_bull_z1 or sweep_bull_z2 or sweep_bull_pdl
    any_sweep_bear = sweep_bear_z1 or sweep_bear_z2 or sweep_bear_pdh

    if not any_sweep_bull and not any_sweep_bear:
        return None

    # ── Displacement at bar[1] ────────────────────────────────────────────
    body = abs(c(1) - o(1))
    rng  = h(1) - l(1)
    is_disp_bull = c(1) > o(1) and rng > 0 and body / rng >= 0.70
    is_disp_bear = c(1) < o(1) and rng > 0 and body / rng >= 0.70

    # ── Fair Value Gap at bar[0] ──────────────────────────────────────────
    fvg_bull_top    = l(0)
    fvg_bull_bottom = h(2)
    has_fvg_bull    = fvg_bull_top > fvg_bull_bottom

    fvg_bear_top    = l(2)
    fvg_bear_bottom = h(0)
    has_fvg_bear    = fvg_bear_top > fvg_bear_bottom

    # ── Signal ────────────────────────────────────────────────────────────
    buy_signal  = any_sweep_bull and is_disp_bull and has_fvg_bull
    sell_signal = any_sweep_bear and is_disp_bear and has_fvg_bear

    if not buy_signal and not sell_signal:
        return None

    params = get_asset_params(symbol.upper().replace("USDT", ""))
    mint   = params["tick_size"]

    if buy_signal:
        if sweep_bull_z1:       zone_hit, sweep_level = "zone1_low",  zone_low1
        elif sweep_bull_z2:     zone_hit, sweep_level = "zone2_low",  zone_low2
        else:                   zone_hit, sweep_level = "pdl",        pdl
        sl = min(l(i) for i in range(3)) - mint * 2
        return dict(
            action="BUY", zone_hit=zone_hit, sweep_level=sweep_level,
            fvg_top=fvg_bull_top, fvg_bottom=fvg_bull_bottom,
            sl_level=sl, mode=mode,
        )

    # sell_signal
    if sweep_bear_z1:       zone_hit, sweep_level = "zone1_high", zone_high1
    elif sweep_bear_z2:     zone_hit, sweep_level = "zone2_high", zone_high2
    else:                   zone_hit, sweep_level = "pdh",        pdh
    sl = max(h(i) for i in range(3)) + mint * 2
    return dict(
        action="SELL", zone_hit=zone_hit, sweep_level=sweep_level,
        fvg_top=fvg_bear_top, fvg_bottom=fvg_bear_bottom,
        sl_level=sl, mode=mode,
    )
