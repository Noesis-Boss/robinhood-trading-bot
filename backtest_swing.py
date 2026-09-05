"""Backtest runner for SupplyDemandSwingStrategy (daily bars).

Usage:
  python3 backtest_swing.py [--config config_swing.yaml] [--period 3y]
      [--symbols SPY QQQ ...] [--out results_swing.json]

Account-level governor (weekly -2% / monthly +8% breakers) is shared across
symbols; fills resolve on daily OHLC with stop-before-target conservatism and
gap-through-open exits.
"""
import argparse
import json
import random
import sys
from collections import defaultdict

import pandas as pd
import yaml

from src.supply_demand_swing import RiskGovernor, SupplyDemandSwingStrategy


def load_bars(symbol: str, period: str) -> pd.DataFrame | None:
    import yfinance as yf

    df = yf.download(symbol, period=period, interval="1d", auto_adjust=False,
                     progress=False, multi_level_index=False)
    if df is None or df.empty:
        return None
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def run_backtest(bars: dict[str, pd.DataFrame], config: dict) -> dict:
    gov = RiskGovernor(equity=float(config.get("capital", 10_000.0)),
                       risk_pct=float(config.get("supply_demand_swing", {}).get("risk_pct", 0.01)))
    strategies = {}
    for sym in bars:
        st = SupplyDemandSwingStrategy(config)
        st.governor = gov
        strategies[sym] = st
    gov = strategies[next(iter(strategies))].governor
    dates = sorted(set().union(*[set(df.index) for df in bars.values()]))

    for ts in dates:
        for sym, strat in strategies.items():
            df = bars[sym]
            if ts not in df.index:
                continue
            i = df.index.get_loc(ts)
            strat.on_bar(i, df)

    trades = []
    for sym, strat in strategies.items():
        for t in strat.trades:
            trades.append({
                "symbol": sym,
                "side": t.side,
                "entry_date": str(bars[sym].index[t.entry_i].date()),
                "exit_date": str(bars[sym].index[t.exit_i].date()) if t.exit_i >= 0 else "",
                "duration_days": (t.exit_i - t.entry_i) if t.exit_i >= 0 else -1,
                "rr": t.rr,
                "r_multiple": t.rr if t.outcome == "win" else (-1.0 if t.outcome == "loss" else 0.0),
                "outcome": t.outcome,
                "target_kind": t.target_kind,
            })
    return {"trades": trades, "final_equity": gov.equity, "blocked_log": gov.log}


def metrics(result: dict) -> dict:
    tr = [t for t in result["trades"] if t["outcome"]]
    if not tr:
        return {"trades": 0}
    rs = [t["r_multiple"] for t in tr]
    wins = [t for t in tr if t["outcome"] == "win"]
    losses = [t for t in tr if t["outcome"] == "loss"]
    gross_w = sum(r for r in rs if r > 0)
    gross_l = abs(sum(r for r in rs if r < 0))
    months = defaultdict(float)
    durs_w = [t["duration_days"] for t in wins]
    durs_l = [t["duration_days"] for t in losses]
    for t in tr:
        months[t["exit_date"][:7]] += t["r_multiple"]
    pos_months = sum(1 for v in months.values() if v > 0)
    return {
        "trades": len(tr),
        "win_rate_pct": round(100 * len(wins) / len(tr), 1),
        "avg_rr_winners": round(sum(t["rr"] for t in wins) / len(wins), 2) if wins else 0,
        "profit_factor": round(gross_w / gross_l, 2) if gross_l else float("inf"),
        "total_r": round(sum(rs), 2),
        "avg_winner_r": round(sum(t["r_multiple"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loser_r": round(sum(t["r_multiple"] for t in losses) / len(losses), 2) if losses else 0,
        "avg_win_duration_d": round(sum(durs_w) / len(durs_w), 1) if durs_w else 0,
        "avg_loss_duration_d": round(sum(durs_l) / len(durs_l), 1) if durs_l else 0,
        "trades_per_month": round(len(tr) / max(1, len(months)), 1),
        "months_total": len(months),
        "positive_months_pct": round(100 * pos_months / len(months), 1) if months else 0,
        "monthly_r": {k: round(v, 2) for k, v in sorted(months.items())},
        "by_symbol": {
            s: {"n": sum(1 for t in tr if t["symbol"] == s),
                "wr_pct": round(100 * sum(1 for t in tr if t["symbol"] == s and t["outcome"] == "win")
                                / max(1, sum(1 for t in tr if t["symbol"] == s)), 1)}
            for s in sorted({t["symbol"] for t in tr})},
        "target_kind_mix": {
            k: sum(1 for t in tr if t["target_kind"] == k)
            for k in {"zone", "swing"}},
    }


def monte_carlo(trades: list[dict], n_sims: int = 10_000, stress_flip: float = 0.0,
                seed: int = 42) -> dict:
    rng = random.Random(seed)
    rs = [(t["rr"] if t["outcome"] == "win" else -1.0) for t in trades if t["outcome"]]
    if not rs:
        return {}
    totals = []
    for _ in range(n_sims):
        tot = 0.0
        for _ in range(len(rs)):
            r = rs[rng.randrange(len(rs))]
            if r > 0 and rng.random() < stress_flip:
                r = -1.0
            tot += r
        totals.append(tot)
    totals.sort()
    pct = lambda p: totals[int(p * (len(totals) - 1))]
    return {"n_sims": n_sims, "trades_per_sim": len(rs),
            "median_r": round(pct(0.50), 1), "p5_r": round(pct(0.05), 1),
            "p95_r": round(pct(0.95), 1), "worst_r": round(totals[0], 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_swing.yaml")
    ap.add_argument("--period", default="3y")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--out", default="results_swing.json")
    args = ap.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
    universe = args.symbols or config.get("universe", ["SPY", "QQQ"])

    bars = {}
    for sym in universe:
        df = load_bars(sym, args.period)
        if df is not None:
            bars[sym] = df
        print(f"{sym}: {len(df) if df is not None else 0} daily bars", file=sys.stderr)

    result = run_backtest(bars, config)
    m = metrics(result)
    mc_base = monte_carlo(result["trades"], stress_flip=0.0)
    mc_stress = monte_carlo(result["trades"], stress_flip=0.10)

    out = {
        "universe": list(bars.keys()), "period": args.period,
        "start": str(min(df.index[0] for df in bars.values()).date()),
        "end": str(max(df.index[-1] for df in bars.values()).date()),
        "capital_start": config.get("capital"),
        "equity_end": round(result["final_equity"], 2),
        "breaker_blocks": len(result["blocked_log"]),
        "metrics": m, "monte_carlo_base": mc_base, "monte_carlo_wr_minus_10": mc_stress,
        "trades": result["trades"],
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    slim = {k: v for k, v in out.items() if k != "trades"}
    slim["metrics"].pop("monthly_r", None)
    print(json.dumps(slim, indent=2))


if __name__ == "__main__":
    main()
