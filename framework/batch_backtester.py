#!/usr/bin/env python3
"""Batch Backtester for 100 Strategies.

Runs all strategies from the grid, collects metrics, ranks by profit factor.
Outputs ranked results to JSON.
"""
import argparse
import json
import logging
import sys
import tempfile
import copy
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

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("batch_backtest")

STRATEGY_MAP = {
    "london": LondonBreakoutStrategy,
    "ross": RossMomentumStrategy,
    "sneaky": SneakyPivotStrategy,
    "ha_scalp": HAScalpStrategy,
    "auction_flow": AuctionFlowProxyStrategy,
    "vwap": VWAPLiquidityProxyStrategy,
    "t3": T3RangeFilterStrategy,
    "reversal": ReversalZoneConfirmationStrategy,
    "ema_cci_macd": EmaCciMacdStrategy,
    "candle_narrative": CandleNarrativeStrategy,
}

SECTION_MAP = {
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


def load_config(base_config: dict, strategy_name: str, params: dict) -> dict:
    config = copy.deepcopy(base_config)
    section = SECTION_MAP.get(strategy_name)
    if section:
        config.setdefault(section, {}).update(params)
    else:
        config.update(params)
    return config


def run_single_backtest(
    strategy_name: str,
    params: dict,
    base_config: dict,
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: str = "auto",
) -> dict:
    config = load_config(base_config, strategy_name, params)
    feed = DataFeed(config.get("timezone", "America/New_York"), provider=provider)
    risk = RiskManager(config)
    journal = TradeJournal(tempfile.mktemp(suffix=".jsonl"))

    strategy_cls = STRATEGY_MAP.get(strategy_name)
    if not strategy_cls:
        return {"error": f"Unknown strategy: {strategy_name}"}

    strat = strategy_cls(config, risk, journal)
    all_trades = []

    for symbol in symbols:
        try:
            df = feed.get_bars(
                symbol,
                interval=config.get("bar_interval", "5m"),
                start=start_date,
                end=end_date,
            )
        except Exception as exc:
            log.warning(f"  {symbol} download failed: {exc}")
            continue
        if df.empty:
            continue

        if df.index.tz is None:
            df.index = df.index.tz_localize(config.get("timezone", "America/New_York"))
        else:
            df.index = df.index.tz_convert(config.get("timezone", "America/New_York"))
        df.columns = [str(c).lower() for c in df.columns]

        for day in df.index.normalize().unique():
            day_data = df[df.index.normalize() == day].sort_index()
            if len(day_data) < 40:
                continue

            if strategy_name == "london":
                session_start = pd.Timestamp(config.get("ny_open", "09:30")).time()
                session_end = pd.Timestamp(config.get("ny_close", "12:00")).time()
            elif strategy_name == "ross":
                session_start = pd.Timestamp(config.get("ross_momentum", {}).get("session_start", "04:00")).time()
                session_end = pd.Timestamp(config.get("ross_momentum", {}).get("session_end", "12:00")).time()
            elif strategy_name == "sneaky":
                session_start = pd.Timestamp(config.get("sneaky_pivot", {}).get("session_start", "09:30")).time()
                session_end = pd.Timestamp(config.get("sneaky_pivot", {}).get("session_end", "15:45")).time()
            else:
                session_start = pd.Timestamp("09:30").time()
                session_end = pd.Timestamp("16:00").time()

            ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
            ny_data = day_data[ny_mask]
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
                        if config.get("execution_realism", {}).get("enabled", True):
                            exit_result = finalize_trade(exit_result, config)
                        all_trades.append(exit_result)

                if symbol not in strat._active_trades:
                    context = None
                    if strategy_name == "london":
                        box = strat.build_london_box(day_data)
                        if box is None:
                            continue
                        context = box
                    signal = strat.generate_signal(symbol, bars_slice, context)
                    if signal:
                        strat.on_trade_entered(symbol, signal)

            if symbol in strat._active_trades:
                last_bar = ny_data.iloc[-1]
                trade = strat._active_trades[symbol]
                close = float(last_bar["close"])
                entry = trade["entry"]
                qty = trade["qty"]
                direction = trade["direction"]
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
                if config.get("execution_realism", {}).get("enabled", True):
                    exit_result = finalize_trade(exit_result, config)
                all_trades.append(exit_result)
                del strat._active_trades[symbol]

    if not all_trades:
        return {
            "trade_count": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
        }

    wins = [t for t in all_trades if t.get("pnl", 0) > 0]
    losses = [t for t in all_trades if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in all_trades)
    gross_wins = sum(t["pnl"] for t in wins) if wins else 0
    gross_losses = sum(abs(t["pnl"]) for t in losses) if losses else 0

    return {
        "trade_count": len(all_trades),
        "win_rate": round(len(wins) / len(all_trades) * 100, 2) if all_trades else 0,
        "profit_factor": round(gross_wins / gross_losses, 2) if gross_losses > 0 else float("inf"),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(abs(t["pnl"]) for t in losses) / len(losses), 2) if losses else 0,
        "wins": len(wins),
        "losses": len(losses),
    }


def run_batch(
    grid_path: str,
    base_config_path: str,
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: str = "auto",
    max_strategies: int = 100,
) -> list[dict]:
    with open(grid_path) as f:
        grid = json.load(f)

    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)

    results = []
    for i, strategy_def in enumerate(grid[:max_strategies]):
        strategy_name = strategy_def["strategy"]
        params = strategy_def["params"]
        strategy_id = strategy_def["id"]

        print(f"[{i+1}/{min(len(grid), max_strategies)}] Running {strategy_id}...", flush=True)

        try:
            metrics = run_single_backtest(
                strategy_name, params, base_config, symbols, start_date, end_date, provider
            )
            metrics["id"] = strategy_id
            metrics["strategy"] = strategy_name
            metrics["params"] = params
            results.append(metrics)
            pf = metrics["profit_factor"]
            pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
            print(f"  -> PF={pf_str}, WR={metrics['win_rate']}%, PnL=${metrics['total_pnl']}", flush=True)
        except Exception as exc:
            print(f"  FAILED: {exc}", flush=True)
            results.append({
                "id": strategy_id,
                "strategy": strategy_name,
                "params": params,
                "error": str(exc),
                "profit_factor": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "trade_count": 0,
            })

    results.sort(key=lambda x: (x.get("profit_factor", 0), x.get("total_pnl", 0)), reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Batch backtest 100 strategies")
    parser.add_argument("--grid", default="framework/strategy_grid.json")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--max", type=int, default=100)
    parser.add_argument("--out", default="framework/batch_results.json")
    args = parser.parse_args()

    results = run_batch(
        args.grid, args.config, args.symbols, args.start, args.end, args.provider, args.max
    )

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Batch Backtest Results ({len(results)} strategies)")
    print(f"{'='*60}")
    print(f"{'Rank':<5} {'ID':<25} {'PF':<6} {'WR%':<6} {'PnL':<10} {'Trades':<7}")
    print(f"{'-'*60}")
    for i, r in enumerate(results[:20], 1):
        pf = r.get("profit_factor", 0)
        pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
        print(f"{i:<5} {r['id']:<25} {pf_str:<6} {r.get('win_rate', 0):<6} ${r.get('total_pnl', 0):<9} {r.get('trade_count', 0):<7}")

    print(f"\nFull results saved to {args.out}")
    return results


if __name__ == "__main__":
    main()
