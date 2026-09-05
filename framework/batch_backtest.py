"""Batch Backtest Engine — 100 Strategy Grid.

Generates 100 parameter combinations across all strategies,
runs them all, ranks by composite score, outputs top 3 for
forward testing.

Usage:
  python3 framework/batch_backtest.py [--out framework/batch_results.json]
"""
import argparse
import copy
import itertools
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import DataFeed
from src.risk import RiskManager
from src.journal import TradeJournal
from src.execution_realism import finalize_trade, valid_bar
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

log = logging.getLogger("batch_backtest")

STRATEGY_FACTORIES = {
    "london": lambda cfg, risk, journal: LondonBreakoutStrategy(cfg, risk, journal),
    "ross": lambda cfg, risk, journal: RossMomentumStrategy(cfg, risk, journal),
    "sneaky": lambda cfg, risk, journal: SneakyPivotStrategy(cfg, risk, journal),
    "ha_scalp": lambda cfg, risk, journal: HAScalpStrategy(cfg, risk, journal),
    "auction_flow": lambda cfg, risk, journal: AuctionFlowProxyStrategy(cfg, risk, journal),
    "vwap": lambda cfg, risk, journal: VWAPLiquidityProxyStrategy(cfg, risk, journal),
    "t3": lambda cfg, risk, journal: T3RangeFilterStrategy(cfg, risk, journal),
    "reversal": lambda cfg, risk, journal: ReversalZoneConfirmationStrategy(cfg, risk, journal),
    "ema_cci_macd": lambda cfg, risk, journal: EmaCciMacdStrategy(cfg, risk, journal),
    "candle_narrative": lambda cfg, risk, journal: CandleNarrativeStrategy(cfg, risk, journal),
}

SESSION_WINDOWS = {
    "london": ("ny_open", "ny_close", "bar_interval", "09:30", "12:00", "5m"),
    "ross": ("session_start", "session_end", "bar_interval", "04:00", "12:00", "5m"),
    "sneaky": ("session_start", "session_end", "bar_interval", "09:30", "15:45", "5m"),
    "ha_scalp": ("session_start", "session_end", "backtest_interval", "09:30", "15:45", "15m"),
    "auction_flow": ("session_start", "session_end", "bar_interval", "09:30", "15:45", "5m"),
    "vwap": ("session_start", "session_end", "bar_interval", "09:30", "15:45", "5m"),
    "t3": ("session_start", "session_end", "backtest_interval", "09:30", "15:45", "1h"),
    "reversal": ("session_start", "session_end", "backtest_interval", "09:35", "11:00", "1m"),
    "ema_cci_macd": ("session_start", "session_end", "bar_interval", "09:35", "15:45", "5m"),
    "candle_narrative": ("session_start", "session_end", "bar_interval", "09:35", "12:30", "5m"),
}

PARAM_GRIDS = {
    "london": [
        {"min_box_pct": 0.003, "max_box_pct": 0.03, "breakout_strength": 0.5, "volume_multiplier": 0.8, "rr_ratio": 2.0, "max_holding_bars": 30, "directional_bias": True, "trend_filter": True},
        {"min_box_pct": 0.005, "max_box_pct": 0.04, "breakout_strength": 0.75, "volume_multiplier": 0.8, "rr_ratio": 2.0, "max_holding_bars": 30, "directional_bias": True, "trend_filter": True},
        {"min_box_pct": 0.008, "max_box_pct": 0.05, "breakout_strength": 0.6, "volume_multiplier": 1.0, "rr_ratio": 2.5, "max_holding_bars": 25, "directional_bias": False, "trend_filter": True},
        {"min_box_pct": 0.004, "max_box_pct": 0.035, "breakout_strength": 0.4, "volume_multiplier": 0.6, "rr_ratio": 1.8, "max_holding_bars": 40, "directional_bias": True, "trend_filter": False},
        {"min_box_pct": 0.006, "max_box_pct": 0.045, "breakout_strength": 0.8, "volume_multiplier": 1.2, "rr_ratio": 3.0, "max_holding_bars": 20, "directional_bias": True, "trend_filter": True},
    ],
    "ross": [
        {"min_gap_pct": 0.02, "min_relative_volume": 1.5, "rr_ratio": 1.5, "pullback_lookback": 4, "ema_length": 9},
        {"min_gap_pct": 0.03, "min_relative_volume": 2.0, "rr_ratio": 2.0, "pullback_lookback": 3, "ema_length": 12},
        {"min_gap_pct": 0.015, "min_relative_volume": 1.2, "rr_ratio": 1.2, "pullback_lookback": 5, "ema_length": 7},
        {"min_gap_pct": 0.025, "min_relative_volume": 1.8, "rr_ratio": 1.8, "pullback_lookback": 4, "ema_length": 10},
        {"min_gap_pct": 0.035, "min_relative_volume": 2.5, "rr_ratio": 2.5, "pullback_lookback": 2, "ema_length": 14},
    ],
    "sneaky": [
        {"swing_lookback": 2, "proximity_pct": 0.003, "rr_ratio": 1.0, "max_holding_bars": 26},
        {"swing_lookback": 3, "proximity_pct": 0.005, "rr_ratio": 1.5, "max_holding_bars": 20},
        {"swing_lookback": 2, "proximity_pct": 0.002, "rr_ratio": 0.8, "max_holding_bars": 30},
        {"swing_lookback": 4, "proximity_pct": 0.004, "rr_ratio": 2.0, "max_holding_bars": 18},
        {"swing_lookback": 3, "proximity_pct": 0.003, "rr_ratio": 1.2, "max_holding_bars": 24},
    ],
    "ha_scalp": [
        {"ema_length": 100, "doji_body_ratio": 0.35, "rr_ratio": 1.0, "min_volume_ratio": 1.0},
        {"ema_length": 80, "doji_body_ratio": 0.3, "rr_ratio": 1.2, "min_volume_ratio": 1.2},
        {"ema_length": 120, "doji_body_ratio": 0.4, "rr_ratio": 0.8, "min_volume_ratio": 0.8},
        {"ema_length": 90, "doji_body_ratio": 0.25, "rr_ratio": 1.5, "min_volume_ratio": 1.5},
        {"ema_length": 110, "doji_body_ratio": 0.38, "rr_ratio": 1.0, "min_volume_ratio": 1.0},
    ],
    "auction_flow": [
        {"confirm_rejection": True, "max_gap_pct": 0.08, "max_bar_range_pct": 0.08, "rr_ratio": 2.0, "max_holding_bars": 30},
        {"confirm_rejection": True, "max_gap_pct": 0.05, "max_bar_range_pct": 0.05, "rr_ratio": 1.5, "max_holding_bars": 25},
        {"confirm_rejection": False, "max_gap_pct": 0.10, "max_bar_range_pct": 0.10, "rr_ratio": 2.5, "max_holding_bars": 35},
        {"confirm_rejection": True, "max_gap_pct": 0.06, "max_bar_range_pct": 0.06, "rr_ratio": 1.8, "max_holding_bars": 28},
        {"confirm_rejection": False, "max_gap_pct": 0.12, "max_bar_range_pct": 0.12, "rr_ratio": 3.0, "max_holding_bars": 20},
    ],
    "vwap": [
        {"volume_multiplier": 1.2, "rr_ratio": 2.0, "atr_multiplier": 1.0, "max_holding_bars": 30},
        {"volume_multiplier": 1.0, "rr_ratio": 1.5, "atr_multiplier": 0.8, "max_holding_bars": 35},
        {"volume_multiplier": 1.5, "rr_ratio": 2.5, "atr_multiplier": 1.2, "max_holding_bars": 25},
        {"volume_multiplier": 0.8, "rr_ratio": 1.8, "atr_multiplier": 1.5, "max_holding_bars": 40},
        {"volume_multiplier": 1.3, "rr_ratio": 3.0, "atr_multiplier": 0.9, "max_holding_bars": 20},
    ],
    "t3": [
        {"t3_length": 8, "t3_factor": 0.7, "range_multiplier": 2.0, "atr_multiplier": 1.5, "target_r": 2.0, "max_holding_bars": 30},
        {"t3_length": 6, "t3_factor": 0.6, "range_multiplier": 1.8, "atr_multiplier": 1.2, "target_r": 2.5, "max_holding_bars": 35},
        {"t3_length": 10, "t3_factor": 0.8, "range_multiplier": 2.5, "atr_multiplier": 2.0, "target_r": 1.8, "max_holding_bars": 25},
        {"t3_length": 7, "t3_factor": 0.65, "range_multiplier": 2.2, "atr_multiplier": 1.8, "target_r": 2.2, "max_holding_bars": 28},
        {"t3_length": 9, "t3_factor": 0.75, "range_multiplier": 1.5, "atr_multiplier": 1.3, "target_r": 3.0, "max_holding_bars": 40},
    ],
    "reversal": [
        {"level_lookback": 20, "min_move_pct": 0.004, "confirmation_body_ratio": 0.5, "rr_ratio": 2.0, "max_holding_bars": 30},
        {"level_lookback": 15, "min_move_pct": 0.003, "confirmation_body_ratio": 0.4, "rr_ratio": 1.8, "max_holding_bars": 35},
        {"level_lookback": 25, "min_move_pct": 0.005, "confirmation_body_ratio": 0.6, "rr_ratio": 2.5, "max_holding_bars": 25},
        {"level_lookback": 18, "min_move_pct": 0.0035, "confirmation_body_ratio": 0.45, "rr_ratio": 2.2, "max_holding_bars": 28},
        {"level_lookback": 22, "min_move_pct": 0.0045, "confirmation_body_ratio": 0.55, "rr_ratio": 1.5, "max_holding_bars": 40},
    ],
    "ema_cci_macd": [
        {"ema_fast": 50, "ema_slow": 110, "cci_length": 20, "rr_ratio": 2.0, "max_holding_bars": 30},
        {"ema_fast": 40, "ema_slow": 100, "cci_length": 15, "rr_ratio": 1.8, "max_holding_bars": 35},
        {"ema_fast": 60, "ema_slow": 120, "cci_length": 25, "rr_ratio": 2.5, "max_holding_bars": 25},
        {"ema_fast": 45, "ema_slow": 105, "cci_length": 18, "rr_ratio": 2.2, "max_holding_bars": 28},
        {"ema_fast": 55, "ema_slow": 115, "cci_length": 22, "rr_ratio": 1.5, "max_holding_bars": 40},
    ],
    "candle_narrative": [
        {"trend_ema": 20, "zone_lookback": 30, "asymmetry_ratio": 1.5, "rr_ratio": 2.0, "max_holding_bars": 24},
        {"trend_ema": 15, "zone_lookback": 25, "asymmetry_ratio": 1.2, "rr_ratio": 1.8, "max_holding_bars": 30},
        {"trend_ema": 25, "zone_lookback": 35, "asymmetry_ratio": 2.0, "rr_ratio": 2.5, "max_holding_bars": 20},
        {"trend_ema": 18, "zone_lookback": 28, "asymmetry_ratio": 1.3, "rr_ratio": 2.2, "max_holding_bars": 26},
        {"trend_ema": 22, "zone_lookback": 32, "asymmetry_ratio": 1.8, "rr_ratio": 1.5, "max_holding_bars": 28},
    ],
}


def generate_strategies():
    """Generate 100 strategy variants (10 per strategy type)."""
    strategies = []
    for name, grid in PARAM_GRIDS.items():
        for i, params in enumerate(grid):
            strategies.append({
                "strategy": name,
                "params": params,
                "id": f"{name}_v{i+1}",
            })
    return strategies


def run_strategy(config, symbols, start_date, end_date, strategy_name, params, data_dir=None):
    """Run a single strategy backtest."""
    cfg = copy.deepcopy(config)

    # Map strategy name to config section
    section_map = {
        "london": None,
        "ross": "ross_momentum",
        "sneaky": "sneaky_pivot",
        "ha_scalp": "ha_scalp",
        "auction_flow": "auction_flow_proxy",
        "vwap": "vwap_liquidity_proxy",
        "t3": "t3_range_filter",
        "reversal": "reversal_zone_confirmation",
        "ema_cci_macd": "ema_cci_macd",
        "candle_narrative": "candle_narrative",
    }
    section = section_map.get(strategy_name)
    if section:
        cfg.setdefault(section, {}).update(params)
    else:
        cfg.update(params)

    # Disable theta farming for cleaner comparison
    cfg["theta_farming"] = {"enabled": False}

    feed = DataFeed(cfg.get("timezone", "America/New_York"))
    risk = RiskManager(cfg)
    journal = TradeJournal(f"/tmp/batch_journal_{strategy_name}.jsonl")

    strategy_cls = STRATEGY_FACTORIES.get(strategy_name)
    if not strategy_cls:
        return {"error": f"Unknown strategy: {strategy_name}"}

    strat = strategy_cls(cfg, risk, journal)
    all_trades = []

    for symbol in symbols:
        try:
            cached = None
            if data_dir:
                candidate = Path(data_dir) / f"{symbol}_{start_date}_{end_date}.pkl"
                if candidate.exists():
                    cached = pd.read_pickle(candidate)

            interval_key = SESSION_WINDOWS.get(strategy_name, (None, None, "bar_interval", "09:30", "16:00", "5m"))[2]
            default_interval = SESSION_WINDOWS.get(strategy_name, (None, None, "bar_interval", "09:30", "16:00", "5m"))[5]
            interval = cfg.get(interval_key, cfg.get("bar_interval", default_interval))

            df = cached if cached is not None else feed.get_bars(
                symbol,
                interval=interval,
                start=start_date,
                end=end_date,
            )
        except Exception as exc:
            log.warning(f"  {symbol} download failed: {exc}")
            continue
        if df.empty:
            continue

        if df.index.tz is None:
            df.index = df.index.tz_localize(cfg.get("timezone", "America/New_York"))
        else:
            df.index = df.index.tz_convert(cfg.get("timezone", "America/New_York"))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]

        trade_dates = df.index.normalize().unique()

        for day in trade_dates:
            day_data = df[df.index.normalize() == day].sort_index()
            min_bars = 8 if interval in ("1h", "15m") else 40
            if len(day_data) < min_bars:
                continue

            # Get session mask
            win = SESSION_WINDOWS.get(strategy_name, (None, None, "bar_interval", "09:30", "16:00", "5m"))
            session_start = pd.Timestamp(cfg.get(strategy_name.replace("_", "_") if strategy_name != "london" else "london", {}).get(win[3].replace(":", "_").split("_")[0] if False else "09:30", win[3])).time()
            session_end = pd.Timestamp(cfg.get(strategy_name.replace("_", "_") if strategy_name != "london" else "london", {}).get(win[4].replace(":", "_").split("_")[0] if False else "16:00", win[4])).time()

            # Simpler session mask
            if strategy_name == "london":
                s_start = pd.Timestamp(cfg.get("ny_open", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("ny_close", "12:00")).time()
            elif strategy_name == "ross":
                s_start = pd.Timestamp(cfg.get("ross_momentum", {}).get("session_start", "04:00")).time()
                s_end = pd.Timestamp(cfg.get("ross_momentum", {}).get("session_end", "12:00")).time()
            elif strategy_name == "sneaky":
                s_start = pd.Timestamp(cfg.get("sneaky_pivot", {}).get("session_start", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("sneaky_pivot", {}).get("session_end", "15:45")).time()
            elif strategy_name == "ha_scalp":
                s_start = pd.Timestamp(cfg.get("ha_scalp", {}).get("session_start", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("ha_scalp", {}).get("session_end", "15:45")).time()
            elif strategy_name == "auction_flow":
                s_start = pd.Timestamp(cfg.get("auction_flow_proxy", {}).get("session_start", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("auction_flow_proxy", {}).get("session_end", "15:45")).time()
            elif strategy_name == "vwap":
                s_start = pd.Timestamp(cfg.get("vwap_liquidity_proxy", {}).get("session_start", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("vwap_liquidity_proxy", {}).get("session_end", "15:45")).time()
            elif strategy_name == "t3":
                s_start = pd.Timestamp(cfg.get("t3_range_filter", {}).get("session_start", "09:30")).time()
                s_end = pd.Timestamp(cfg.get("t3_range_filter", {}).get("session_end", "15:45")).time()
            elif strategy_name == "reversal":
                s_start = pd.Timestamp(cfg.get("reversal_zone_confirmation", {}).get("session_start", "09:35")).time()
                s_end = pd.Timestamp(cfg.get("reversal_zone_confirmation", {}).get("session_end", "11:00")).time()
            elif strategy_name == "ema_cci_macd":
                s_start = pd.Timestamp(cfg.get("ema_cci_macd", {}).get("session_start", "09:35")).time()
                s_end = pd.Timestamp(cfg.get("ema_cci_macd", {}).get("session_end", "15:45")).time()
            elif strategy_name == "candle_narrative":
                s_start = pd.Timestamp(cfg.get("candle_narrative", {}).get("session_start", "09:35")).time()
                s_end = pd.Timestamp(cfg.get("candle_narrative", {}).get("session_end", "12:30")).time()
            else:
                s_start = pd.Timestamp("09:30").time()
                s_end = pd.Timestamp("16:00").time()

            mask = (day_data.index.time >= s_start) & (day_data.index.time < s_end)
            ny_data = day_data[mask]
            if ny_data.empty:
                continue

            n = len(ny_data)
            for i in range(1, n):
                bars_slice = ny_data.iloc[: i + 1]
                if not valid_bar(bars_slice.iloc[-1]):
                    continue

                if symbol in strat._active_trades:
                    exit_result = strat.check_exit(symbol, bars_slice, None)
                    if exit_result:
                        if cfg.get("execution_realism", {}).get("enabled", True):
                            exit_result = finalize_trade(exit_result, cfg)
                        all_trades.append(exit_result)

                if symbol not in strat._active_trades:
                    context = None
                    if strategy_name == "london":
                        box = strat.build_london_box(day_data)
                        if box is None:
                            continue
                        box_high, box_low = box
                        context = (box_high, box_low)
                    elif strategy_name == "sneaky":
                        prior = df[df.index.normalize() < day]
                        context = {"prior_high": float(prior["high"].max()), "prior_low": float(prior["low"].min())} if not prior.empty else None
                    signal = strat.generate_signal(symbol, bars_slice, context)
                    if signal:
                        strat.on_trade_entered(symbol, signal)

            if symbol in strat._active_trades:
                last_bar = ny_data.iloc[-1]
                trade = strat._active_trades[symbol]
                direction = trade["direction"]
                close = float(last_bar["close"])
                entry = trade["entry"]
                qty = trade["qty"]
                if direction == "long":
                    pnl = (close - entry) * qty
                else:
                    pnl = (entry - close) * qty
                exit_result = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry": round(entry, 2),
                    "exit_price": round(close, 2),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "reason": "eod_close",
                }
                if cfg.get("execution_realism", {}).get("enabled", True):
                    exit_result = finalize_trade(exit_result, cfg)
                all_trades.append(exit_result)
                del strat._active_trades[symbol]

    # Summarize
    wins = [t for t in all_trades if t.get("pnl", 0) > 0]
    losses = [t for t in all_trades if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in all_trades)
    gross_wins = sum(t["pnl"] for t in wins) if wins else 0
    gross_losses = sum(abs(t["pnl"]) for t in losses) if losses else 0

    return {
        "trade_count": len(all_trades),
        "win_rate": round(len(wins) / len(all_trades) * 100, 2) if all_trades else 0,
        "profit_factor": round(gross_wins / gross_losses, 2) if gross_losses > 0 else 0,
        "total_pnl": round(total_pnl, 2),
        "final_capital": round(cfg.get("capital", 10000) + total_pnl, 2),
        "return_pct": round(total_pnl / cfg.get("capital", 10000) * 100, 2),
    }


def score_strategy(result):
    """Score a strategy result. Higher is better."""
    if "error" in result:
        return -999

    trade_count = result.get("trade_count", 0)
    win_rate = result.get("win_rate", 0)
    profit_factor = result.get("profit_factor", 0)
    return_pct = result.get("return_pct", 0)

    # Penalize too few trades
    if trade_count < 5:
        return -999

    # Composite: balance return, win rate, profit factor, and trade count
    score = (
        return_pct * 0.35 +
        win_rate * 0.25 +
        profit_factor * 10 * 0.25 +
        min(trade_count, 50) * 0.15
    )
    return score


def main():
    parser = argparse.ArgumentParser(description="Batch backtest 100 strategies")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out", default="framework/batch_results.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    with open(args.config) as f:
        config = yaml.safe_load(f)

    strategies = generate_strategies()
    print(f"Generated {len(strategies)} strategy variants")
    print(f"Backtesting {args.start} to {args.end} on {args.symbols}")

    results = []
    for i, strat in enumerate(strategies, 1):
        print(f"[{i}/{len(strategies)}] {strat['id']}...", end=" ", flush=True)
        try:
            result = run_strategy(
                config, args.symbols, args.start, args.end,
                strat["strategy"], strat["params"], args.data_dir
            )
            result["id"] = strat["id"]
            result["strategy"] = strat["strategy"]
            result["params"] = strat["params"]
            result["score"] = score_strategy(result)
            print(f"trades={result.get('trade_count', 0)}, WR={result.get('win_rate', 0)}%, PF={result.get('profit_factor', 0)}, score={result['score']:.2f}")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            result = {
                "id": strat["id"],
                "strategy": strat["strategy"],
                "params": strat["params"],
                "error": str(exc),
                "score": -999,
            }
            print(f"ERROR: {exc}")
        results.append(result)

    # Sort by score descending
    results.sort(key=lambda x: x.get("score", -999), reverse=True)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Top 10 Strategies:")
    print(f"{'='*60}")
    for r in results[:10]:
        if "error" in r:
            print(f"  {r['id']}: ERROR")
        else:
            print(f"  {r['id']}: score={r['score']:.2f}, trades={r['trade_count']}, WR={r['win_rate']}%, PF={r['profit_factor']}, return={r['return_pct']}%")

    print(f"\nFull results saved to {args.out}")
    return results


if __name__ == "__main__":
    main()
