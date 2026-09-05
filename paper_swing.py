"""Paper validation runner for SupplyDemandSwingStrategy (Phase 3).

Full deterministic replay of daily bars on every invocation; only trades
entered on/after the anchor date count toward paper P&L. Idempotent — safe
to run daily (automation or manual).

Usage:
  python3 paper_swing.py                      # run/update validation
  python3 paper_swing.py --status             # show current paper state

State:   paper_state.json   (anchor date, run log)
Journal: paper_journal.jsonl (one line per counted trade, rewritten each run)
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from backtest_swing import load_bars, metrics

HERE = Path(__file__).resolve().parent
STATE = HERE / "paper_state.json"
JOURNAL = HERE / "paper_journal.jsonl"


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "config_swing.yaml"))
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--period", default="3y")
    ap.add_argument("--anchor", default=None, help="YYYY-MM-DD first-counted entry date")
    ap.add_argument("--risk", type=float, default=0.005, help="paper risk fraction (gate: 0.005)")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    state = load_state()
    if args.status:
        if not state:
            print("no paper state yet — run python3 paper_swing.py to bootstrap")
            return 0
        j = [json.loads(l) for l in JOURNAL.read_text().splitlines() if l.strip()] if JOURNAL.exists() else []
        closed = [t for t in j if t["outcome"]]
        wins = sum(1 for t in closed if t["outcome"] == "win")
        r = sum(t["r_multiple"] for t in closed)
        print(f"anchor={state.get('anchor')} runs={len(state.get('runs', []))}")
        print(f"counted_trades={len(j)} closed={len(closed)} open={len(j)-len(closed)} "
              f"wins={wins} total_R={round(r,2)}")
        for t in j:
            print(f"  {t['symbol']:5s} {t['side']:5s} in={t['entry_date']} out={t['exit_date'] or 'OPEN':10s} "
                  f"rr={t['rr']:.2f} R={t['r_multiple']:+.2f} {t['outcome'] or 'PENDING'}")
        return 0

    config = yaml.safe_load(open(args.config))
    config.setdefault("supply_demand_swing", {})["risk_pct"] = args.risk
    syms = args.symbols or config.get("universe", ["SPY", "QQQ"])
    anchor = state.get("anchor") or args.anchor or date.today().isoformat()

    bars = {}
    for s in syms:
        df = load_bars(s, args.period)
        if df is None or df.empty:
            print(f"WARN no bars for {s}, skipping", file=sys.stderr)
            continue
        bars[s] = df
    if not bars:
        print("ERROR: no data downloaded (yfinance failure?)")
        return 1

    counted, skipped_pre = [], 0
    from src.supply_demand_swing import RiskGovernor, SupplyDemandSwingStrategy
    gov = RiskGovernor(equity=float(config.get("capital", 10_000.0)), risk_pct=args.risk)
    strategies = {}
    for sym in bars:
        st = SupplyDemandSwingStrategy(config)
        st.governor = gov
        strategies[sym] = st
    dates = sorted(set().union(*[set(df.index) for df in bars.values()]))
    for ts in dates:
        for sym, strat in strategies.items():
            df = bars[sym]
            if ts not in df.index:
                continue
            strat.on_bar(df.index.get_loc(ts), df)

    for sym, strat in strategies.items():
        df = bars[sym]
        for t in strat.trades:
            rec = {
                "symbol": sym,
                "side": t.side,
                "entry_date": str(df.index[t.entry_i].date()),
                "exit_date": str(df.index[t.exit_i].date()) if t.exit_i >= 0 else "",
                "entry": round(float(t.entry), 2),
                "stop": round(float(t.stop), 2),
                "target": round(float(t.target), 2),
                "rr": round(t.rr, 2),
                "target_kind": t.target_kind,
                "outcome": t.outcome,
                "r_multiple": round(t.rr if t.outcome == "win" else (-1.0 if t.outcome == "loss" else 0.0), 2),
            }
            if rec["entry_date"] < anchor:
                skipped_pre += 1
                continue
            counted.append(rec)

    counted.sort(key=lambda t: (t["entry_date"], t["symbol"]))
    JOURNAL.write_text("".join(json.dumps(t) + "\n" for t in counted))

    open_pos = [t for t in counted if not t["outcome"]]
    pending = {s: bool(st.order) for s, st in strategies.items() if st.order}
    m = metrics({"trades": counted}) if counted else {"trades": 0}

    state.setdefault("runs", []).append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_bar": str(max(df.index.max() for df in bars.values()).date()),
        "counted": len(counted),
    })
    state["runs"] = state["runs"][-100:]
    state["anchor"] = anchor
    state["risk_pct"] = args.risk
    STATE.write_text(json.dumps(state, indent=2))

    print(f"PAPER VALIDATION — anchor {anchor}, risk {args.risk:.1%}, "
          f"data through {state['runs'][-1]['last_bar']}")
    print(f"pre-anchor trades replayed but not counted: {skipped_pre}")
    print(f"counted: {m['trades']} | closed: {m['trades'] - len(open_pos)} | open: {len(open_pos)} "
          f"| pending orders: {[s for s, v in pending.items() if v] or 'none'}")
    if m.get("trades"):
        print(f"WR {m['win_rate_pct']}% | PF {m['profit_factor']} | total R {m['total_r']} "
              f"| equity ${gov.equity:,.2f}")
    for t in open_pos:
        print(f"  OPEN {t['symbol']} {t['side']} @ {t['entry']} stop {t['stop']} target {t['target']} "
              f"(rr {t['rr']}) since {t['entry_date']}")
    for b in gov.log[-5:]:
        print(f"  breaker: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
