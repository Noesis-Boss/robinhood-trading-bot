"""Sensitivity sweep for the London breakout `breakout_strength` knob.

Runs the full backtest N times, once per value in --values, on the
published benchmark window. Prints a markdown table to stdout and writes
the same table to `.specify/memory/sensitivity-result.md` for the
`memory` stage of the spec-driven-dev pipeline.

Recommendation policy (per spec.md AC4):
  - If any non-default row has PF > baseline PF AND |delta_pnl| < 5% of |baseline_pnl|,
    recommend a window of 2-3 neighbouring values and STOP.
  - Otherwise, keep the current default.

Usage:
  python3 backtest_sensitivity.py
  python3 backtest_sensitivity.py --values 0.5,0.75,1.0
  python3 backtest_sensitivity.py --symbols SPY QQQ --start 2026-08-01 --end 2026-08-06
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.backtest_runner import load_config, run_backtest, summarize_trades

log = logging.getLogger("backtest_sensitivity")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_VALUES = [0.50, 0.60, 0.70, 0.75, 0.80, 0.90, 1.00]
DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "SOFI", "F", "AAL",
                   "MARA", "RIVN", "NIO", "RBLX", "DKNG"]


def _row_md(value: float, summary: dict) -> str:
    return (
        f"| {value:.2f} | {summary['trade_count']} | {summary['win_rate']:.1f}% "
        f"| {summary['profit_factor'] if summary['profit_factor'] is not None else 'N/A'} "
        f"| ${summary['total_pnl']:,.2f} |"
    )


def recommend(rows: list[tuple[float, dict]], default: float) -> str:
    """Per spec.md AC4.

    Default row is the one matching the `default` arg. Recommend if any
    non-default row has higher PF AND comparable pnl magnitude.
    """
    default_row = next((r for r in rows if abs(r[0] - default) < 1e-9), None)
    if default_row is None:
        return (f"No default row at {default} in sweep; "
                f"cannot recommend. Keep current default.")

    base_pnl = abs(default_row[1]["total_pnl"]) or 1.0
    candidates = []
    for v, s in rows:
        if abs(v - default) < 1e-9:
            continue
        if s["profit_factor"] is None or default_row[1]["profit_factor"] is None:
            continue
        if (s["profit_factor"] > default_row[1]["profit_factor"]
                and abs(abs(s["total_pnl"]) - abs(default_row[1]["total_pnl"])) < 0.05 * base_pnl):
            candidates.append((v, s))

    if not candidates:
        return f"Keep default {default}. No neighbour beats baseline PF with comparable P&L."

    best = max(candidates, key=lambda r: r[1]["profit_factor"])
    return (f"Try {best[0]:.2f} (PF={best[1]['profit_factor']} vs baseline "
            f"PF={default_row[1]['profit_factor']}). Within 5% of baseline P&L.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep breakout_strength values")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--values", default=",".join(f"{v:.2f}" for v in DEFAULT_VALUES),
                        help="Comma-separated breakout_strength values")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--provider", default="yfinance")
    parser.add_argument("--strategy", default="london")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output",
                        default=str(Path(__file__).resolve().parent / ".specify/memory/sensitivity-result.md"),
                        help="Where to write the markdown report")
    parser.add_argument("--default", type=float, default=0.75,
                        help="The current production default to compare against")
    args = parser.parse_args()

    values = [float(v) for v in args.values.split(",") if v.strip()]
    cfg = load_config(args.config)
    rows: list[tuple[float, dict]] = []

    for v in values:
        log.info("Sweeping breakout_strength=%.2f ...", v)
        trades = run_backtest(
            cfg, args.symbols, args.start, args.end,
            provider=args.provider, strategy_name=args.strategy,
            data_dir=args.data_dir, json_output=False,
            breakout_strength_override=v,
        )
        summary = summarize_trades(trades, args.start, args.end, args.symbols,
                                   cfg.get("capital", 0))
        rows.append((v, summary))

    # Markdown table
    header = "| breakout_strength | trades | win_rate | profit_factor | total_pnl |\n|---:|---:|---:|---:|---:|"
    body = "\n".join(_row_md(v, s) for v, s in rows)
    rec = recommend(rows, args.default)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md = (
        f"# Breakout-Strength Sensitivity\n\n"
        f"Window: {args.start} → {args.end}\n"
        f"Symbols: {', '.join(args.symbols)}\n"
        f"Strategy: {args.strategy}\n"
        f"Provider: {args.provider}\n"
        f"Default for comparison: {args.default}\n"
        f"Generated: {ts}\n\n"
        f"{header}\n{body}\n\n"
        f"**Recommendation:** {rec}\n"
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
