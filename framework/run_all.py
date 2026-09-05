#!/usr/bin/env python3
"""Orchestrator: batch backtest -> forward test -> report.

Usage:
    python3 framework/run_all.py --start 2026-07-01 --end 2026-08-06 \
        --symbols SPY QQQ AAPL TSLA NVDA --capital 100 --days 5
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_batch(config_path: str, symbols: list[str], start: str, end: str, capital: float) -> str:
    out = "framework/batch_results.json"
    cmd = [
        sys.executable, "framework/batch_backtester.py",
        "--config", config_path,
        "--symbols", *symbols,
        "--start", start,
        "--end", end,
        "--capital", str(capital),
        "--out", out,
    ]
    print(f"[ Batch] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[Batch] FAILED with exit code {result.returncode}", file=sys.stderr)
        sys.exit(1)
    return out


def run_forward(results_path: str, config_path: str, symbols: list[str],
                capital: float, days: int, top: int) -> str:
    out = "framework/forward_results.json"
    cmd = [
        sys.executable, "framework/forward_tester.py",
        "--results", results_path,
        "--config", config_path,
        "--symbols", *symbols,
        "--capital", str(capital),
        "--days", str(days),
        "--top", str(top),
        "--out", out,
    ]
    print(f"[Forward] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[Forward] FAILED with exit code {result.returncode}", file=sys.stderr)
        sys.exit(1)
    return out


def generate_report(batch_path: str, forward_path: str) -> str:
    with open(batch_path) as f:
        batch = json.load(f)
    with open(forward_path) as f:
        forward = json.load(f)

    lines = []
    lines.append("# Strategy Evaluation Report\n")
    lines.append(f"## Batch Backtest ({batch['start']} to {batch['end']})\n")
    lines.append(f"Total strategies tested: {batch['total']}")
    lines.append(f"Valid results: {batch['valid']}\n")

    lines.append("### Top 10 by Profit Factor\n")
    lines.append("| Rank | ID | Strategy | PF | WR% | Trades | Capital |")
    lines.append("|------|------|----------|-----|------|--------|---------|")
    for i, s in enumerate(batch["results"][:10], 1):
        pf = s.get("profit_factor", 0)
        pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
        lines.append(
            f"| {i} | {s['id']} | {s['strategy']} | {pf_str} | "
            f"{s.get('win_rate', 0):.1f} | {s.get('trade_count', 0)} | "
            f"${s.get('final_capital', 0):.2f} |"
        )

    lines.append(f"\n## Forward Test ({forward[0].get('days_tested', 0)} days, ${forward[0].get('capital', 0):.0f} capital)\n")
    for r in forward:
        if "error" in r:
            lines.append(f"- **{r['id']}**: ERROR - {r['error']}")
        else:
            lines.append(
                f"- **{r['id']}**: Return={r.get('total_return_pct', 0):.2f}%, "
                f"WR={r.get('win_rate', 0):.1f}%, "
                f"PF={r.get('profit_factor', 0):.2f}, "
                f"MaxDD={r.get('max_drawdown_pct', 0):.1f}%, "
                f"Equity=${r.get('final_equity', 0):.2f}"
            )

    report_path = "framework/REPORT.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Strategy evaluation pipeline")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--capital", type=float, default=100.0)
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    batch_results = run_batch(args.config, args.symbols, args.start, args.end, args.capital)
    forward_results = run_forward(batch_results, args.config, args.symbols, args.capital, args.days, args.top)
    report = generate_report(batch_results, forward_results)

    print(f"\n{'='*60}")
    print(f"DONE. Report: {report}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
