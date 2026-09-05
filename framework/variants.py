#!/usr/bin/env python3
"""Strategy variant definitions — 100 parameterized combinations.

Each variant is (base_strategy_name, params_dict). The framework sweeps
key parameters across all registered strategies to fill 100 slots.
"""

import itertools
import random

random.seed(42)


def _london_grid():
    """London breakout parameter sweep."""
    grid = []
    for bs in [0.5, 0.75, 1.0]:
        for mb in [0.003, 0.005, 0.01]:
            for ew in [2, 3, 4]:
                for rr in [1.5, 2.0, 2.5]:
                    for mh in [18, 30, 45]:
                        for vm in [0.6, 0.8, 1.0]:
                            grid.append({
                                "breakout_strength": bs,
                                "min_box_pct": mb,
                                "entry_window_hours": ew,
                                "rr_ratio": rr,
                                "max_holding_bars": mh,
                                "volume_multiplier": vm,
                                "directional_bias": True,
                                "trend_filter": True,
                                "trailing_stop_breakeven": True,
                                "early_exit_reversal": False,
                            })
    return grid[:40]  # cap at 40


def _ross_grid():
    """Ross momentum sweep."""
    grid = []
    for mg in [0.01, 0.02, 0.04]:
        for rv in [1.0, 1.5, 2.0]:
            for rr in [1.5, 2.0]:
                for mh in [20, 30, 45]:
                    for pl in [3, 4, 5]:
                        grid.append({
                            "ross_momentum.min_gap_pct": mg,
                            "ross_momentum.min_relative_volume": rv,
                            "ross_momentum.rr_ratio": rr,
                            "ross_momentum.max_holding_bars": mh,
                            "ross_momentum.pullback_lookback": pl,
                        })
    return grid[:15]


def _sneaky_grid():
    """Sneaky pivot sweep."""
    grid = []
    for sl in [2, 3, 4]:
        for pp in [0.002, 0.003, 0.005]:
            for rr in [1.0, 1.5, 2.0]:
                for mh in [20, 26, 35]:
                    grid.append({
                        "sneaky_pivot.swing_lookback": sl,
                        "sneaky_pivot.proximity_pct": pp,
                        "sneaky_pivot.rr_ratio": rr,
                        "sneaky_pivot.max_holding_bars": mh,
                    })
    return grid[:10]


def _vwap_grid():
    """VWAP liquidity proxy sweep."""
    grid = []
    for vm in [1.0, 1.2, 1.5]:
        for rr in [1.5, 2.0, 2.5]:
            for mh in [20, 30, 45]:
                for am in [0.8, 1.0, 1.2]:
                    grid.append({
                        "vwap_liquidity_proxy.volume_multiplier": vm,
                        "vwap_liquidity_proxy.rr_ratio": rr,
                        "vwap_liquidity_proxy.max_holding_bars": mh,
                        "vwap_liquidity_proxy.atr_multiplier": am,
                    })
    return grid[:10]


def _t3_grid():
    """T3 range filter sweep."""
    grid = []
    for tl in [6, 8, 12]:
        for rm in [1.5, 2.0, 2.5]:
            for rr in [1.5, 2.0]:
                for mh in [20, 30]:
                    grid.append({
                        "t3_range_filter.t3_length": tl,
                        "t3_range_filter.range_multiplier": rm,
                        "t3_range_filter.target_r": rr,
                        "t3_range_filter.max_holding_bars": mh,
                    })
    return grid[:10]


def _reversal_grid():
    """Reversal zone confirmation sweep."""
    grid = []
    for ll in [15, 20, 30]:
        for mm in [0.003, 0.004, 0.006]:
            for rr in [1.5, 2.0, 2.5]:
                for vm in [0.8, 1.0, 1.2]:
                    grid.append({
                        "reversal_zone_confirmation.level_lookback": ll,
                        "reversal_zone_confirmation.min_move_pct": mm,
                        "reversal_zone_confirmation.rr_ratio": rr,
                        "reversal_zone_confirmation.volume_multiplier": vm,
                    })
    return grid[:10]


def _ema_cci_macd_grid():
    """EMA/CCI/MACD sweep."""
    grid = []
    for ef in [30, 50, 70]:
        for es in [90, 110, 130]:
            for rr in [1.5, 2.0, 2.5]:
                for mh in [20, 30, 45]:
                    grid.append({
                        "ema_cci_macd.ema_fast": ef,
                        "ema_cci_macd.ema_slow": es,
                        "ema_cci_macd.rr_ratio": rr,
                        "ema_cci_macd.max_holding_bars": mh,
                    })
    return grid[:10]


def _candle_narrative_grid():
    """Candle narrative sweep."""
    grid = []
    for te in [15, 20, 30]:
        for zl in [20, 30, 40]:
            for rr in [1.5, 2.0, 2.5]:
                for vm in [1.0, 1.2, 1.5]:
                    grid.append({
                        "candle_narrative.trend_ema": te,
                        "candle_narrative.zone_lookback": zl,
                        "candle_narrative.rr_ratio": rr,
                        "candle_narrative.volume_multiplier": vm,
                    })
    return grid[:10]


def _ha_scalp_grid():
    """Heikin-Ashi scalp sweep."""
    grid = []
    for el in [50, 100, 150]:
        for rr in [0.8, 1.0, 1.5]:
            for vm in [0.8, 1.0, 1.2]:
                grid.append({
                    "ha_scalp.ema_length": el,
                    "ha_scalp.rr_ratio": rr,
                    "ha_scalp.min_volume_ratio": vm,
                })
    return grid[:5]


def _auction_grid():
    """Auction flow proxy sweep."""
    grid = []
    for mg in [0.05, 0.08, 0.12]:
        for mbr in [0.05, 0.08, 0.12]:
            grid.append({
                "auction_flow_proxy.max_gap_pct": mg,
                "auction_flow_proxy.max_bar_range_pct": mbr,
            })
    return grid[:5]


# ── Master variant list ───────────────────────────────────────────────────
def build_100_variants() -> list[tuple[str, dict]]:
    """Return list of (strategy_name, params) — exactly 100 variants."""
    all_variants = []

    generators = [
        ("london", _london_grid()),
        ("ross", _ross_grid()),
        ("sneaky", _sneaky_grid()),
        ("vwap_liquidity_proxy", _vwap_grid()),
        ("t3_range_filter", _t3_grid()),
        ("reversal_zone_confirmation", _reversal_grid()),
        ("ema_cci_macd", _ema_cci_macd_grid()),
        ("candle_narrative", _candle_narrative_grid()),
        ("ha_scalp", _ha_scalp_grid()),
        ("auction_flow_proxy", _auction_grid()),
    ]

    for name, grid in generators:
        for params in grid:
            all_variants.append((name, params))

    # Trim or pad to exactly 100
    if len(all_variants) > 100:
        random.shuffle(all_variants)
        all_variants = all_variants[:100]
    elif len(all_variants) < 100:
        # Fill remaining with random london variants
        while len(all_variants) < 100:
            params = {
                "breakout_strength": random.choice([0.5, 0.75, 1.0]),
                "min_box_pct": random.choice([0.003, 0.005, 0.01]),
                "entry_window_hours": random.choice([2, 3, 4]),
                "rr_ratio": random.choice([1.5, 2.0, 2.5]),
                "max_holding_bars": random.choice([18, 30, 45]),
                "volume_multiplier": random.choice([0.6, 0.8, 1.0]),
            }
            all_variants.append(("london", params))

    return all_variants


# Convenience: export the list
VARIANTS_100 = build_100_variants()
