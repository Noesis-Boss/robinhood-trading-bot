"""Universal backtester — runs all 100 strategies and ranks them.

Usage:
    python3 framework/universal_backtester.py \
        --start 2026-07-01 --end 2026-08-06 \
        --symbols SPY QQQ AAPL TSLA NVDA \
        --output results_100.json
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from framework.strategy_grid import generate_100_strategies


def run_one(sc, symbols, start, end, data_dir=None):
    """Run a single strategy via the existing backtest.py."""
    cmd = [
        sys.executable, "backtest.py",
        "--strategy", sc.strategy_type,
        "--start", start,
        "--end", end,
        "--symbols", *symbols,
        "--json",
        "--theta", "false",
    ]
    if data_dir:
        cmd += ["--data-dir", data_dir]

    # Merge strategy-specific params into config via --strategy-params
    if sc.params:
        # Map flat params to nested config structure
        config_override = {}
        for k, v in sc.params.items():
            # Put each param in its strategy's config section
            section = sc.strategy_type
            if sc.strategy_type == "vwap_liquidity_proxy":
                section = "vwap_liquidity_proxy"
            elif sc.strategy_type == "t3_range_filter":
                section = "t3_range_filter"
            elif sc.strategy_type == "ema_cci_macd":
                section = "ema_cci_macd"
            elif sc.strategy_type == "candle_narrative":
                section = "candle_narrative"
            elif sc.strategy_type == "ross":
                section = "ross_momentum"
            elif sc.strategy_type == "sneaky":
                section = "sneaky_pivot"
            elif sc.strategy_type == "ha_scalp":
                section = "ha_scalp"
            elif sc.strategy_type == "auction_flow_proxy":
                section = "auction_flow_proxy"
            elif sc.strategy_type == "reversal_zone_confirmation":
                section = "reversal_zone_confirmation"
            config_override.setdefault(section, {})[k] = v

        if config_override:
            cmd += ["--strategy-params", json.dumps(config_override)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"name": sc.name, "strategy_type": sc.strategy_type,
                    "error": result.stderr[:500], "pnl": -99999}
        output = json.loads(result.stdout)
        output["name"] = sc.name
        output["strategy_type"] = sc.strategy_type
        output["params"] = sc.params
        return output
    except subprocess.TimeoutExpired:
        return {"name": sc.name, "strategy_type": sc.strategy_type,
                "error": "timeout", "pnl": -99999}
    except Exception as e:
        return {"name": sc.name, "strategy_type": sc.strategy_type,
                "error": str(e), "pnl": -99999}


def rank_results(results):
    """Rank by profit factor, then P&L, then win rate."""
    valid = [r for r in results if "error" not in r and r.get("trade_count", 0) > 0]
    for r in valid:
        r["_score"] = (
            r.get("profit_factor", 0) * 10 +
            r.get("total_pnl", 0) / 100 +
            r.get("win_rate", 0) / 10
        )
    valid.sort(key=lambda x: x["_score"], reverse=True)
    return valid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-07-01")
    ap.add_argument("--end", default="2026-08-06")
    ap.add_argument("--symbols", nargs="+",
                    default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA",
                             "SOFI", "F", "AAL", "MARA", "RIVN", "NIO",
                             "RBLX", "DKNG"])
    ap.add_argument("--output", default="results_100.json")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--top-n", type=int, default=3)
    args = ap.parse_args()

    strategies = generate_100_strategies()
    print(f"Generated {len(strategies)} strategies")

    results = []
    for i, sc in enumerate(strategies):
        print(f"[{i+1}/{len(strategies)}] Running {sc.name} ({sc.strategy_type})...")
        t0 = time.time()
        r = run_one(sc, args.symbols, args.start, args.end, args.data_dir)
        elapsed = time.time() - t0
        trades = r.get("trade_count", 0)
        pnl = r.get("total_pnl", 0)
        wr = r.get("win_rate", 0)
        pf = r.get("profit_factor", 0)
        print(f"  -> {trades} trades, P&L=${pnl:.2f}, WR={wr:.1f}%, PF={pf:.2f} ({elapsed:.1f}s)")
        results.append(r)

    ranked = rank_results(results)

    output = {
        "run_args": vars(args),
        "total_strategies": len(strategies),
        "valid_results": len(ranked),
        "top_10": [
            {
                "rank": i + 1,
                "name": r["name"],
                "strategy_type": r["strategy_type"],
                "params": r.get("params", {}),
                "trades": r.get("trade_count", 0),
                "pnl": r.get("total_pnl", 0),
                "win_rate": r.get("win_rate", 0),
                "profit_factor": r.get("profit_factor", 0),
                "avg_win": r.get("avg_win", 0),
                "avg_loss": r.get("avg_loss", 0),
            }
            for i, r in enumerate(ranked[:10])
        ],
        "top_3": [
            {
                "rank": i + 1,
                "name": r["name"],
                "strategy_type": r["strategy_type"],
                "params": r.get("params", {}),
                "trades": r.get("trade_count", 0),
                "pnl": r.get("total_pnl", 0),
                "win_rate": r.get("win_rate", 0),
                "profit_factor": r.get("profit_factor", 0),
            }
            for i, r in enumerate(ranked[:args.top_n])
        ],
        "all_results": results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"TOP {args.top_n} STRATEGIES:")
    for r in output["top_3"]:
        print(f"  #{r['rank']} {r['name']} ({r['strategy_type']}) — "
              f"P&L=${r['pnl']:.2f}, WR={r['win_rate']:.1f}%, "
              f"PF={r['profit_factor']:.2f}, {r['trades']} trades")
    print(f"\nFull results saved to {args.output}")
    return output


if __name__ == "__main__":
    main()
