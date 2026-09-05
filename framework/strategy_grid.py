"""Strategy Grid Generator.

Generates 100 strategy permutations by varying key parameters:
- 10 base strategies (london, ross, sneaky, ha_scalp, auction_flow, vwap, t3, reversal, ema_cci, candle_narrative)
- Each with 10 parameter variations (breakout_strength, rr_ratio, max_holding_bars, volume_multiplier, trend_filter)

Total: 10 * 10 = 100 unique strategy configurations.

Output: JSON file with all 100 configs, ready for batch backtesting.
"""
import json
import itertools
from pathlib import Path
from typing import Any

# Strategy configuration templates
STRATEGY_TEMPLATES = {
    "london": {
        "class": "LondonBreakoutStrategy",
        "module": "src.strategy",
        "params": {
            "breakout_strength": [0.3, 0.5, 0.75, 1.0],
            "rr_ratio": [1.5, 2.0, 2.5, 3.0],
            "max_holding_bars": [18, 30, 45],
            "volume_multiplier": [0.6, 0.8, 1.0],
            "trend_filter": [True, False],
            "directional_bias": [True, False],
            "min_box_pct": [0.003, 0.005, 0.01],
            "entry_window_hours": [2, 3, 4],
        },
    },
    "ross": {
        "class": "RossMomentumStrategy",
        "module": "src.ross_momentum",
        "params": {
            "min_gap_pct": [0.01, 0.02, 0.04],
            "min_relative_volume": [1.0, 1.5, 2.0],
            "pullback_lookback": [3, 4, 5],
            "ema_length": [5, 9, 12],
            "rr_ratio": [1.5, 2.0],
            "max_holding_bars": [18, 30, 45],
            "session_start": ["04:00", "06:00"],
            "session_end": ["10:00", "12:00"],
        },
    },
    "sneaky": {
        "class": "SneakyPivotStrategy",
        "module": "src.sneaky_pivot",
        "params": {
            "swing_lookback": [1, 2, 3],
            "proximity_pct": [0.001, 0.003, 0.005],
            "rr_ratio": [1.0, 1.5, 2.0],
            "max_holding_bars": [18, 26, 40],
            "session_start": ["09:30", "10:00"],
            "session_end": ["15:00", "15:45"],
        },
    },
    "ha_scalp": {
        "class": "HAScalpStrategy",
        "module": "src.ha_scalp",
        "params": {
            "ema_length": [50, 100, 200],
            "doji_body_ratio": [0.25, 0.35, 0.5],
            "min_wick_ratio": [0.15, 0.2, 0.3],
            "min_volume_ratio": [0.8, 1.0, 1.5],
            "rr_ratio": [1.0, 1.5, 2.0],
        },
    },
    "auction_flow": {
        "class": "AuctionFlowProxyStrategy",
        "module": "src.auction_flow_proxy",
        "params": {
            "confirm_rejection": [True, False],
            "max_gap_pct": [0.04, 0.08, 0.12],
            "max_bar_range_pct": [0.04, 0.08, 0.12],
            "rr_ratio": [1.5, 2.0, 2.5],
            "max_holding_bars": [18, 30],
        },
    },
    "vwap": {
        "class": "VWAPLiquidityProxyStrategy",
        "module": "src.vwap_liquidity_proxy",
        "params": {
            "volume_multiplier": [1.0, 1.2, 1.5, 2.0],
            "rr_ratio": [1.5, 2.0, 2.5],
            "max_holding_bars": [18, 30, 45],
            "atr_length": [10, 14, 20],
            "atr_multiplier": [0.8, 1.0, 1.5],
            "max_gap_pct": [0.04, 0.08],
            "max_bar_range_pct": [0.04, 0.08],
        },
    },
    "t3": {
        "class": "T3RangeFilterStrategy",
        "module": "src.t3_range_filter",
        "params": {
            "t3_length": [5, 8, 12],
            "t3_factor": [0.5, 0.7, 0.9],
            "range_length": [10, 14, 20],
            "range_multiplier": [1.5, 2.0, 2.5],
            "atr_length": [10, 14],
            "atr_multiplier": [1.0, 1.5],
            "target_r": [1.5, 2.0, 2.5],
            "max_holding_bars": [18, 30],
        },
    },
    "reversal": {
        "class": "ReversalZoneConfirmationStrategy",
        "module": "src.reversal_zone_confirmation",
        "params": {
            "level_lookback": [10, 20, 30],
            "move_lookback": [2, 3, 5],
            "min_move_pct": [0.002, 0.004, 0.008],
            "structure_lookback": [2, 3, 5],
            "confirmation_body_ratio": [0.4, 0.5, 0.6],
            "volume_multiplier": [0.8, 1.0, 1.5],
            "rr_ratio": [1.5, 2.0],
            "max_holding_bars": [18, 30],
            "session_start": ["09:35", "10:00"],
            "session_end": ["11:00", "12:00"],
        },
    },
    "ema_cci_macd": {
        "class": "EmaCciMacdStrategy",
        "module": "src.ema_cci_macd",
        "params": {
            "ema_fast": [20, 50, 80],
            "ema_slow": [80, 110, 150],
            "cci_length": [14, 20, 30],
            "macd_fast": [8, 12],
            "macd_slow": [20, 26],
            "macd_signal": [7, 9, 12],
            "zone_touch_bars": [2, 3, 5],
            "zone_proximity_pct": [0.001, 0.002, 0.004],
            "volume_multiplier": [0.8, 1.0, 1.5],
            "atr_length": [10, 14],
            "rr_ratio": [1.5, 2.0],
            "max_holding_bars": [18, 30],
            "session_start": ["09:35", "10:00"],
            "session_end": ["15:00", "15:45"],
        },
    },
    "candle_narrative": {
        "class": "CandleNarrativeStrategy",
        "module": "src.candle_narrative",
        "params": {
            "trend_ema": [10, 20, 50],
            "zone_lookback": [20, 30, 50],
            "pivot_left_right": [2, 3, 5],
            "impulse_lookback": [3, 4, 5],
            "pullback_lookback": [2, 3, 4],
            "asymmetry_ratio": [1.2, 1.5, 2.0],
            "min_engulf_ratio": [1.05, 1.1, 1.2],
            "pin_wick_ratio": [1.5, 2.0, 3.0],
            "min_body_ratio": [0.5, 0.6, 0.7],
            "close_location": [0.6, 0.75, 0.85],
            "volume_multiplier": [1.0, 1.2, 1.5],
            "atr_stop_buffer": [0.15, 0.25, 0.4],
            "zone_tolerance_atr": [0.3, 0.5, 0.8],
            "rr_ratio": [1.5, 2.0],
            "max_holding_bars": [18, 24, 36],
            "session_start": ["09:35", "10:00"],
            "session_end": ["12:00", "12:30"],
        },
    },
}


def generate_grid(max_per_strategy: int = 10) -> list[dict[str, Any]]:
    """Generate strategy grid with up to max_per_strategy variations per base strategy."""
    grid = []
    for strategy_name, template in STRATEGY_TEMPLATES.items():
        params = template["params"]
        param_names = list(params.keys())
        param_values = list(params.values())

        combos = list(itertools.product(*param_values))
        if len(combos) > max_per_strategy:
            step = len(combos) // max_per_strategy
            combos = combos[::step][:max_per_strategy]

        for i, combo in enumerate(combos):
            config = dict(zip(param_names, combo))
            grid.append({
                "id": f"{strategy_name}_{i:02d}",
                "strategy": strategy_name,
                "class": template["class"],
                "module": template["module"],
                "params": config,
            })
    return grid


def save_grid(grid: list[dict[str, Any]], path: str = "framework/strategy_grid.json"):
    """Save strategy grid to JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(grid, f, indent=2)
    return path


if __name__ == "__main__":
    grid = generate_grid(max_per_strategy=10)
    path = save_grid(grid)
    print(f"Generated {len(grid)} strategies -> {path}")
    for s in grid:
        print(f"  {s['id']}: {s['class']} with {len(s['params'])} params")
