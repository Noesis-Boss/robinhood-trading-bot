#!/usr/bin/env python3
"""Batch backtest runner — sweep 100 strategy variants, rank, forward-test top N.

Usage:
    python framework/batch_runner.py --start 2026-07-01 --end 2026-08-06
    python framework/batch_runner.py --forward 3  # forward-test top 3
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from framework.base import BacktestRunner, StrategyRegistry, BacktestResult
from framework.variants import build_100_variants

# Import all strategies
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

log = logging.getLogger("batch_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def register_strategies():
    """Register all strategies with their parameter grids."""
    StrategyRegistry.register("london", LondonBreakoutStrategy)
    StrategyRegistry.register("ross", RossMomentumStrategy)
    StrategyRegistry.register("sneaky", SneakyPivotStrategy)
    StrategyRegistry.register("ha_scalp", HAScalpStrategy)
    StrategyRegistry.register("auction_flow_proxy", AuctionFlowProxyStrategy)
    StrategyRegistry.register("vwap_liquidity_proxy", VWAPLiquidityProxyStrategy)
    StrategyRegistry.register("t3_range_filter", T3RangeFilterStrategy)
    StrategyRegistry.register("reversal_zone_confirmation", ReversalZoneConfirmationStrategy)
    StrategyRegistry.register("ema_cci_macd", EmaCciMacdStrategy)
    StrategyRegistry.register("candle_narrative", CandleNarrativeStrategy)


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run_batch(
    config: dict,
    variants: list[tuple[str, dict]],
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: str = "auto",
) -> list[BacktestResult]:
    """Run all variants, return ranked results."""
    runner = BacktestRunner(config, provider=provider)
    results: list[BacktestResult] = []

    for i, (strategy_name, params) in enumerate(variants):
        strategy_cls = StrategyRegistry.get(strategy_name)
        if strategy_cls is None:
            log.warning("Strategy %s not registered, skipping", strategy_name)
            continue

        log.info("[%d/%d] Running %s with params: %s", i + 1, len(variants), strategy_name, params)

        try:
            result = runner.run(
                strategy_cls=strategy_cls,
                params=params,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                strategy_name=strategy_name,
            )
            result.variant_name = f"{strategy_name}_{i:03d}"
            result.base_name = strategy_name
            results.append(result)

            log.info(
                "  -> trades=%d WR=%.1f%% PF=%.2f PnL=$%.2f score=%.3f",
                result.total_trades,
                result.win_rate,
                result.profit_factor,
                result.total_pnl,
                result.score,
            )
        except Exception as exc:
            log.error("  FAILED: %s", exc)
            # Still append a zero-score result so we track failures
            results.append(BacktestResult(
                variant_name=f"{strategy_name}_{i:03d}",
                base_name=strategy_name,
                params=params,
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                total_pnl=0.0,
                net_pnl=0.0,
            ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def save_results(results: list[BacktestResult], path: str):
    """Save results to JSON."""
    data = [
        {
            "rank": i + 1,
            "variant": r.variant_name,
            "base": r.base_name,
            "params": r.params,
            "trades": r.total_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "score": round(r.score, 4),
        }
        for i, r in enumerate(results)
    ]
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    log.info("Results saved to %s", path)


def main():
    parser = argparse.ArgumentParser(description="Batch backtest 100 strategy variants")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--output", default="framework/batch_results.json")
    parser.add_argument("--top", type=int, default=3, help="Number of top strategies to forward-test")
    parser.add_argument("--forward", action="store_true", help="Run forward-test on top N")
    args = parser.parse_args()

    register_strategies()
    config = load_config(args.config)

    # Build 100 variants
    variants = build_100_variants()
    log.info("Built %d variants", len(variants))

    # Run batch
    results = run_batch(
        config=config,
        variants=variants,
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        provider=args.provider,
    )

    # Save
    save_results(results, args.output)

    # Print top 10
    print("\n" + "=" * 80)
    print("TOP 10 STRATEGIES (ranked by score = PF * sqrt(trades) * WR%)")
    print("=" * 80)
    for i, r in enumerate(results[:10]):
        print(
            f"{i+1:3d}. {r.variant_name:30s} | trades={r.total_trades:3d} | "
            f"WR={r.win_rate:5.1f}% | PF={r.profit_factor:5.2f} | "
            f"PnL=${r.total_pnl:8.2f} | score={r.score:.3f}"
        )

    # Forward-test top N
    if args.forward:
        top_n = results[: args.top]
        log.info("Forward-testing top %d strategies with small capital", len(top_n))
        from framework.forward_test import ForwardTester

        tester = ForwardTester(config, provider=args.provider)
        for r in top_n:
            tester.run(r, symbols=args.symbols)


if __name__ == "__main__":
    main()
