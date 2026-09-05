#!/usr/bin/env python3
"""Generate 100 strategy parameter combinations for grid search."""
import json
import itertools

strategies = []

# London Breakout variations (30 strategies)
for i, (bs, rr, mh, vmult) in enumerate(itertools.product(
    [0.3, 0.5, 0.75, 1.0],  # breakout_strength
    [1.5, 2.0, 2.5, 3.0],  # rr_ratio
    [15, 30, 45, 60],      # max_holding_bars
    [0.5, 0.8, 1.0, 1.2],  # volume_multiplier
)):
    if i >= 30:
        break
    strategies.append({
        "id": f"london_{i:03d}",
        "strategy": "london",
        "params": {
            "breakout_strength": bs,
            "rr_ratio": rr,
            "max_holding_bars": mh,
            "volume_multiplier": vmult,
        }
    })

# Ross Momentum variations (15 strategies)
for i, (gap, vol, rr, pb) in enumerate(itertools.product(
    [0.01, 0.02, 0.03, 0.05],   # min_gap_pct
    [1.0, 1.5, 2.0],            # min_relative_volume
    [1.5, 2.0, 2.5],            # rr_ratio
    [3, 4, 5],                   # pullback_lookback
)):
    if i >= 15:
        break
    strategies.append({
        "id": f"ross_{i:03d}",
        "strategy": "ross",
        "params": {
            "ross_momentum": {
                "min_gap_pct": gap,
                "min_relative_volume": vol,
                "rr_ratio": rr,
                "pullback_lookback": pb,
            }
        }
    })

# EMA/CCI/MACD variations (20 strategies)
for i, (efast, eslow, cci, rr, mh) in enumerate(itertools.product(
    [20, 30, 50],              # ema_fast
    [80, 110, 150],            # ema_slow
    [14, 20, 30],              # cci_length
    [1.5, 2.0, 2.5],           # rr_ratio
    [20, 30, 40],              # max_holding_bars
)):
    if i >= 20:
        break
    strategies.append({
        "id": f"ema_cci_{i:03d}",
        "strategy": "ema_cci_macd",
        "params": {
            "ema_cci_macd": {
                "ema_fast": efast,
                "ema_slow": eslow,
                "cci_length": cci,
                "rr_ratio": rr,
                "max_holding_bars": mh,
            }
        }
    })

# VWAP Liquidity Proxy variations (15 strategies)
for i, (vmult, rr, mh, atr) in enumerate(itertools.product(
    [0.8, 1.0, 1.2, 1.5],     # volume_multiplier
    [1.5, 2.0, 2.5],           # rr_ratio
    [15, 30, 45],              # max_holding_bars
    [1.0, 1.5, 2.0],           # atr_multiplier
)):
    if i >= 15:
        break
    strategies.append({
        "id": f"vwap_{i:03d}",
        "strategy": "vwap",
        "params": {
            "vwap_liquidity_proxy": {
                "volume_multiplier": vmult,
                "rr_ratio": rr,
                "max_holding_bars": mh,
                "atr_multiplier": atr,
            }
        }
    })

# T3 Range Filter variations (10 strategies)
for i, (t3l, t3f, rr, mh) in enumerate(itertools.product(
    [4, 6, 8, 10],             # t3_length
    [0.5, 0.7, 0.9],           # t3_factor
    [1.5, 2.0, 2.5],           # rr_ratio
    [20, 30, 40],              # max_holding_bars
)):
    if i >= 10:
        break
    strategies.append({
        "id": f"t3_{i:03d}",
        "strategy": "t3",
        "params": {
            "t3_range_filter": {
                "t3_length": t3l,
                "t3_factor": t3f,
                "rr_ratio": rr,
                "max_holding_bars": mh,
            }
        }
    })

# Reversal Zone Confirmation variations (10 strategies)
for i, (ll, rr, mh, vol) in enumerate(itertools.product(
    [10, 20, 30],              # level_lookback
    [1.5, 2.0, 2.5],           # rr_ratio
    [20, 30, 40],              # max_holding_bars
    [0.8, 1.0, 1.2],           # volume_multiplier
)):
    if i >= 10:
        break
    strategies.append({
        "id": f"reversal_{i:03d}",
        "strategy": "reversal",
        "params": {
            "reversal_zone_confirmation": {
                "level_lookback": ll,
                "rr_ratio": rr,
                "max_holding_bars": mh,
                "volume_multiplier": vol,
            }
        }
    })

# Save
with open("framework/strategy_grid.json", "w") as f:
    json.dump(strategies, f, indent=2)

print(f"Generated {len(strategies)} strategy combinations")
