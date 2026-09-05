"""SPY gamma-exposure monitor — read-only research proxy (no orders, ever).

Estimates dealer gamma exposure (GEX) from the yfinance SPY options chain.
Naive positioning assumption (standard public proxy): dealers are long calls
(positive gamma) and short puts (negative gamma). Real dealer positioning is
unknown; treat all numbers as a regime proxy, not ground truth.

Outputs: per-strike GEX, net GEX, largest gamma strikes ("walls"), and the
zero-gamma flip point. CLI prints JSON; exit code 0 on success.

Usage:
  python3 -m src.gamma_monitor [--expiries 2] [--dte-min 0] [--dte-max 7]
"""
import argparse
import datetime as dt
import json
import math

import numpy as np
import yfinance as yf

RISK_FREE = 0.04


def _bs_gamma(S, K, T, sigma, r=RISK_FREE):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi) / (S * sigma * math.sqrt(T))


def _nearest_iv(iv_series, strike):
    if iv_series is None or iv_series.empty:
        return 0.20
    import pandas as pd
    diffs = pd.Series(iv_series.index.astype(float)).sub(strike).abs()
    idx = diffs.idxmin()
    val = float(iv_series.iloc[idx])
    return val if np.isfinite(val) and val > 0 else 0.20


def compute_gex(expiries=2, dte_min=0, dte_max=7):
    tk = yf.Ticker("SPY")
    spot = float(tk.fast_info["last_price"])
    today = dt.date.today()
    exp_dates = tk.options[:expiries]
    rows = {}
    for exp in exp_dates:
        dte = (dt.date.fromisoformat(exp) - today).days
        if not (dte_min <= dte <= dte_max):
            continue
        T = max(dte, 0) / 365.0
        chain = tk.option_chain(exp)
        calls, puts = chain.calls, chain.puts
        call_iv = calls.set_index("strike")["impliedVolatility"]
        put_iv = puts.set_index("strike")["impliedVolatility"]
        for _, row in calls.iterrows():
            K = float(row["strike"])
            oi = float(row.get("openInterest") or 0)
            if oi <= 0:
                continue
            g = _bs_gamma(spot, K, T, _nearest_iv(call_iv, K))
            rows.setdefault(K, {"call": 0.0, "put": 0.0})
            rows[K]["call"] += g * oi * 100 * spot * spot * 0.01
        for _, row in puts.iterrows():
            K = float(row["strike"])
            oi = float(row.get("openInterest") or 0)
            if oi <= 0:
                continue
            g = _bs_gamma(spot, K, T, _nearest_iv(put_iv, K))
            rows.setdefault(K, {"call": 0.0, "put": 0.0})
            rows[K]["put"] -= g * oi * 100 * spot * spot * 0.01
    strikes = sorted(rows)
    per_strike = [
        {
            "strike": K,
            "call_gex": round(rows[K]["call"], 0),
            "put_gex": round(rows[K]["put"], 0),
            "net_gex": round(rows[K]["call"] + rows[K]["put"], 0),
        }
        for K in strikes
    ]
    net_gex = sum(r["net_gex"] for r in per_strike)
    walls = sorted(per_strike, key=lambda r: abs(r["net_gex"]), reverse=True)[:3]
    flip = None
    cum = 0.0
    prev = None
    for r in per_strike:
        prev_sign = 1 if cum >= 0 else -1
        cum += r["net_gex"]
        cur_sign = 1 if cum >= 0 else -1
        if prev is not None and prev_sign != cur_sign:
            flip = r["strike"]
            break
        prev = r
    return {
        "symbol": "SPY",
        "spot": round(spot, 2),
        "expiries_used": exp_dates[:expiries],
        "net_gex": round(net_gex, 0),
        "regime": "positive (mean-revert pin)" if net_gex >= 0 else "negative (trend/volatility)",
        "gamma_walls": [{"strike": w["strike"], "net_gex": w["net_gex"]} for w in walls],
        "flip_point": flip,
        "naive_assumption": "dealers long calls / short puts — proxy only, not ground truth",
        "per_strike": per_strike,
    }


def log_daily(result: dict, path: str = "data/gex_daily.csv") -> str:
    """Append (or overwrite) today's GEX snapshot row. One row per calendar day."""
    import csv
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("date")]
    today = dt.date.today().isoformat()
    rows = [r for r in rows if r["date"] != today]
    rows.append({
        "date": today,
        "spot": result["spot"],
        "net_gex": result["net_gex"],
        "regime": result["regime"],
        "dte_max": result.get("dte_max", 7),
    })
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "spot", "net_gex", "regime", "dte_max"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expiries", type=int, default=2)
    ap.add_argument("--dte-min", type=int, default=0)
    ap.add_argument("--dte-max", type=int, default=7)
    ap.add_argument("--log", action="store_true", help="append today's snapshot to data/gex_daily.csv")
    a = ap.parse_args()
    result = compute_gex(a.expiries, a.dte_min, a.dte_max)
    if a.log:
        result["logged_to"] = log_daily(result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


def get_gamma_regime(symbol: str = "SPY", dte_max: int = 7) -> dict:
    """Read-only regime snapshot for the London bot dashboard/logs.

    Returns spot, net_gex, and regime label. NOT wired into entry logic —
    the regime-filter experiment (2026-09-05) showed SPY-SMA gating hurts
    London expectancy; treat gamma regime as context, not a filter.
    """
    import yfinance as _yf
    tk = _yf.Ticker(symbol)
    spot = float(tk.fast_info["last_price"])
    today = dt.date.today()
    exps = [e for e in tk.options if 0 <= (dt.date.fromisoformat(e) - today).days <= dte_max]
    rows = {"symbol": symbol, "spot": spot, "expiries_used": exps, "per_strike": []}
    net = 0.0
    for exp in exps:
        dte = (dt.date.fromisoformat(exp) - today).days
        T = max(dte, 0) / 365.0
        chain = tk.option_chain(exp)
        for _, row in chain.calls.iterrows():
            g = _bs_gamma(spot, float(row["strike"]), T, _nearest_iv(chain.calls.impliedVolatility, float(row["strike"])))
            v = g * float(row["openInterest"]) * 100 * spot
            net += v
        for _, row in chain.puts.iterrows():
            g = _bs_gamma(spot, float(row["strike"]), T, _nearest_iv(chain.puts.impliedVolatility, float(row["strike"])))
            v = -g * float(row["openInterest"]) * 100 * spot
            net += v
    rows["net_gex"] = round(net, 0)
    rows["regime"] = "positive (mean-reversion)" if net > 0 else "negative (trend/volatility)"
    rows["naive_assumption"] = "dealers long calls / short puts — proxy only, not ground truth"
    return rows
