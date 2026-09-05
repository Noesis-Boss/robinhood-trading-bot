"""100-strategy grid for backtesting.

Each entry is (strategy_class, section_key, params_dict) — 100 unique
combinations across 10 strategy families × 10 parameter variations each.
section_key is the config sub-dict the strategy reads from (None for
strategies that read top-level config keys like London Breakout).
"""

from __future__ import annotations

from src.strategy import LondonBreakoutStrategy
from src.ross_momentum import RossMomentumStrategy
from src.sneaky_pivot import SneakyPivotStrategy
from src.ha_scalp import HAScalpStrategy
from src.auction_flow_proxy import AuctionFlowProxyStrategy
from src.vwap_liquidity_proxy import VWAPLiquidityProxyStrategy
from src.t3_range_filter import T3RangeFilterStrategy
from src.reversal_zone_confirmation import ReversalZoneConfirmationStrategy
from src.ema_cci_macd import EmaCciMacdStrategy
from src.candle_narrative import CandleNarrativeStrategy


def _cfg(base: dict, **overrides) -> dict:
    merged = {**base, **overrides}
    return merged


def build_grid() -> list[tuple]:
    """Return list of (strategy_class, section_key, params) — 100 entries."""
    grid = []

    # ── 1. London Breakout (10 variants) ──
    # LondonBreakoutStrategy reads from top-level config keys directly
    lb_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": True}
    for i, (bs, rr, mhb, vb, vm) in enumerate([
        (0.5, 2.0, 30, 20, 0.8), (0.75, 2.0, 30, 20, 0.8),
        (1.0, 2.0, 30, 20, 0.8), (0.75, 1.5, 30, 20, 0.8),
        (0.75, 2.5, 30, 20, 0.8), (0.75, 2.0, 45, 20, 0.8),
        (0.75, 2.0, 20, 20, 0.8), (0.75, 2.0, 30, 10, 0.8),
        (0.75, 2.0, 30, 30, 0.8), (0.75, 2.0, 30, 20, 1.2),
    ]):
        grid.append((LondonBreakoutStrategy, None, _cfg(lb_base,
            breakout_strength=bs, rr_ratio=rr, max_holding_bars=mhb,
            volume_lookback=vb, volume_multiplier=vm,
            backtest_interval="5m", name=f"lb_{i}")))

    # ── 2. Ross Momentum (10 variants) ──
    rm_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (min_gap, rr, ema, mhb) in enumerate([
        (0.02, 1.5, 9, 30), (0.03, 1.5, 9, 30),
        (0.02, 2.0, 9, 30), (0.02, 1.5, 14, 30),
        (0.02, 1.5, 9, 45), (0.02, 1.5, 9, 20),
        (0.04, 2.0, 9, 30), (0.03, 2.0, 14, 30),
        (0.02, 2.5, 9, 45), (0.03, 1.5, 14, 30),
    ]):
        grid.append((RossMomentumStrategy, "ross_momentum", _cfg(rm_base,
            min_gap_pct=min_gap, rr_ratio=rr, ema_length=ema,
            max_holding_bars=mhb, backtest_interval="5m", name=f"rm_{i}")))

    # ── 3. VWAP Liquidity Proxy (10 variants) ──
    vwap_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (vm, rr, atr_m, mhb) in enumerate([
        (1.2, 2.0, 1.0, 30), (1.5, 2.0, 1.0, 30),
        (1.2, 2.5, 1.0, 30), (1.2, 2.0, 1.5, 30),
        (1.2, 2.0, 1.0, 45), (1.2, 2.0, 1.0, 20),
        (0.8, 2.0, 1.0, 30), (1.5, 2.5, 1.5, 30),
        (1.0, 1.5, 1.0, 45), (1.2, 2.5, 1.2, 25),
    ]):
        grid.append((VWAPLiquidityProxyStrategy, "vwap_liquidity_proxy", _cfg(vwap_base,
            volume_multiplier=vm, rr_ratio=rr, atr_multiplier=atr_m,
            max_holding_bars=mhb, backtest_interval="5m", name=f"vwap_{i}")))

    # ── 4. EMA/CCI/MACD (10 variants) ──
    ecm_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (ema_f, ema_s, rr, mhb) in enumerate([
        (50, 110, 2.0, 30), (50, 110, 2.0, 45),
        (50, 110, 2.5, 30), (50, 110, 1.5, 30),
        (30, 80, 2.0, 30), (80, 150, 2.0, 30),
        (50, 110, 2.0, 20), (50, 110, 3.0, 30),
        (30, 80, 2.5, 45), (80, 150, 1.5, 20),
    ]):
        grid.append((EmaCciMacdStrategy, "ema_cci_macd", _cfg(ecm_base,
            ema_fast=ema_f, ema_slow=ema_s, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="5m", name=f"ecm_{i}")))

    # ── 5. T3 Range Filter (10 variants) ──
    t3_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (t3_l, t3_f, rr, mhb) in enumerate([
        (8, 0.7, 2.0, 30), (8, 0.7, 2.0, 45),
        (8, 0.7, 2.5, 30), (8, 0.7, 1.5, 30),
        (5, 0.7, 2.0, 30), (10, 0.7, 2.0, 30),
        (8, 0.5, 2.0, 30), (8, 0.9, 2.0, 30),
        (5, 0.5, 2.5, 45), (10, 0.9, 1.5, 20),
    ]):
        grid.append((T3RangeFilterStrategy, "t3_range_filter", _cfg(t3_base,
            t3_length=t3_l, t3_factor=t3_f, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="1h", name=f"t3_{i}")))

    # ── 6. Reversal Zone Confirmation (10 variants) ──
    rzc_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (lb, rr, mhb) in enumerate([
        (20, 2.0, 30), (20, 2.0, 45),
        (20, 2.5, 30), (20, 1.5, 30),
        (30, 2.0, 30), (10, 2.0, 30),
        (20, 2.0, 20), (20, 3.0, 30),
        (30, 2.5, 45), (10, 1.5, 20),
    ]):
        grid.append((ReversalZoneConfirmationStrategy, "reversal_zone_confirmation", _cfg(rzc_base,
            level_lookback=lb, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="1m", name=f"rzc_{i}")))

    # ── 7. Candle Narrative (10 variants) ──
    cn_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (zl, rr, mhb) in enumerate([
        (30, 2.0, 24), (30, 2.0, 36),
        (30, 2.5, 24), (30, 1.5, 24),
        (20, 2.0, 24), (40, 2.0, 24),
        (30, 2.0, 18), (30, 3.0, 24),
        (20, 2.5, 36), (40, 1.5, 18),
    ]):
        grid.append((CandleNarrativeStrategy, "candle_narrative", _cfg(cn_base,
            zone_lookback=zl, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="5m", name=f"cn_{i}")))

    # ── 8. Auction Flow Proxy (10 variants) ──
    afp_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (mg, rr, mhb) in enumerate([
        (0.08, 2.0, 30), (0.08, 2.0, 45),
        (0.08, 2.5, 30), (0.08, 1.5, 30),
        (0.05, 2.0, 30), (0.10, 2.0, 30),
        (0.08, 2.0, 20), (0.08, 3.0, 30),
        (0.05, 2.5, 45), (0.10, 1.5, 20),
    ]):
        grid.append((AuctionFlowProxyStrategy, "auction_flow_proxy", _cfg(afp_base,
            max_gap_pct=mg, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="5m", name=f"afp_{i}")))

    # ── 9. HA Scalp (10 variants) ──
    ha_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (dr, wr, rr, mhb) in enumerate([
        (0.35, 0.2, 1.0, 30), (0.35, 0.2, 1.0, 45),
        (0.35, 0.2, 1.5, 30), (0.35, 0.2, 0.8, 30),
        (0.25, 0.2, 1.0, 30), (0.45, 0.2, 1.0, 30),
        (0.35, 0.15, 1.0, 30), (0.35, 0.3, 1.0, 30),
        (0.25, 0.3, 1.5, 45), (0.45, 0.15, 0.8, 20),
    ]):
        grid.append((HAScalpStrategy, "ha_scalp", _cfg(ha_base,
            doji_body_ratio=dr, min_wick_ratio=wr, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="15m", name=f"ha_{i}")))

    # ── 10. Sneaky Pivot (10 variants) ──
    sp_base = {"max_entries_per_day": 1, "trailing_stop_breakeven": False}
    for i, (sl, prox, rr, mhb) in enumerate([
        (2, 0.003, 1.0, 26), (2, 0.003, 1.0, 36),
        (2, 0.003, 1.5, 26), (2, 0.003, 0.8, 26),
        (3, 0.003, 1.0, 26), (1, 0.003, 1.0, 26),
        (2, 0.005, 1.0, 26), (2, 0.002, 1.0, 26),
        (3, 0.005, 1.5, 36), (1, 0.002, 0.8, 18),
    ]):
        grid.append((SneakyPivotStrategy, "sneaky_pivot", _cfg(sp_base,
            swing_lookback=sl, proximity_pct=prox, rr_ratio=rr,
            max_holding_bars=mhb, backtest_interval="5m", name=f"sp_{i}")))

    return grid
