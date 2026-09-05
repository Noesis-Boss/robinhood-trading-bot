#!/usr/bin/env python3
"""
Monte Carlo projection engine for the London Breakout bot.

Uses historical trade statistics from the backtest (2026-07-01 to 2026-08-06,
24 trades, 58.3% win rate, 2.02 profit factor) to project portfolio growth
under continuous reinvestment. Includes theta farming (options credit spreads)
after confirmed breakouts.

Usage:
    python3 project.py                              # $1,000 (default)
    python3 project.py --capital 100               # $100 only
    python3 project.py --all-capitals               # both $100 and $1,000
    python3 project.py --capital 1000 --simulations 50000
"""

import argparse
import json
import numpy as np

# Historical stats from backtest (2026-07-01 to 2026-08-06)
WIN_RATE = 0.583
PROFIT_FACTOR = 2.02
TOTAL_TRADES = 24
TRADING_DAYS = 25  # Jul 1 to Aug 6, 2026

# Derived R-multiples: solved from win_rate, profit_factor, and total R
AVG_WIN_R = 1.09   # avg winner in R-multiples
AVG_LOSS_R = 0.755  # avg loser in R-multiples (truncated by trailing stop)
EXPECTED_R = WIN_RATE * AVG_WIN_R - (1 - WIN_RATE) * AVG_LOSS_R  # ~0.32
TRADES_PER_DAY = TOTAL_TRADES / TRADING_DAYS  # ~0.96

RISK_PCT = 0.02  # 2% of capital risked per trade (config.yaml risk_pct)

# Theta farming stats (from backtest with theta_farming enabled)
THETA_WIN_RATE = 0.72       # 72% of spreads expire worthless (win)
THETA_TRADES_PER_BREAKOUT = 0.2  # ~1 theta spread per 5 trading days (weekly cadence)
# Capital-aware: contracts = int(risk_amount / max_loss), no floor
THETA_RISK_PCT = 0.10    # 10% of capital at risk per spread
THETA_MAX_LOSS_PER_CONTRACT = 20.0  # $20 max loss/contract → $200 threshold for 1 contract
THETA_CREDIT_PER_CONTRACT = 10.0    # $10 credit/contract


def simulate_day_trading(initial_capital, n_days, n_sims, rng):
    """Simulate London Breakout day trading with continuous reinvestment."""
    results = np.zeros((n_sims, n_days + 1))
    results[:, 0] = initial_capital

    trades_per_day = TRADES_PER_DAY

    for sim in range(n_sims):
        equity = initial_capital
        for day in range(n_days):
            n_trades = max(1, int(round(rng.poisson(trades_per_day))))
            for _ in range(n_trades):
                if rng.random() < WIN_RATE:
                    r_mult = max(0.1, rng.normal(AVG_WIN_R, 0.3))
                    equity *= (1 + RISK_PCT * r_mult)
                else:
                    r_mult = max(0.05, min(1.0, rng.normal(AVG_LOSS_R, 0.25)))
                    equity *= (1 - RISK_PCT * r_mult)
            results[sim, day + 1] = equity
    return results


def simulate_combined(initial_capital, n_days, n_sims, rng):
    """Simulate London Breakout + Theta Farming with continuous reinvestment.

    Each day: ~1 London Breakout trade occurs. After each breakout, a weekly
    credit spread is sold (theta farming). Position sizes scale with equity.
    """
    results = np.zeros((n_sims, n_days + 1))
    results[:, 0] = initial_capital

    trades_per_day = TRADES_PER_DAY

    for sim in range(n_sims):
        equity = initial_capital
        for day in range(n_days):
            n_trades = max(1, int(round(rng.poisson(trades_per_day))))

            for _ in range(n_trades):
                if rng.random() < WIN_RATE:
                    r_mult = max(0.1, rng.normal(AVG_WIN_R, 0.3))
                    equity *= (1 + RISK_PCT * r_mult)
                else:
                    r_mult = max(0.05, min(1.0, rng.normal(AVG_LOSS_R, 0.25)))
                    equity *= (1 - RISK_PCT * r_mult)

                # --- Theta farming spread (after breakout) ---
                if rng.random() > THETA_TRADES_PER_BREAKOUT:
                    continue
                theta_risk_amount = equity * THETA_RISK_PCT
                n_contracts = int(theta_risk_amount / THETA_MAX_LOSS_PER_CONTRACT)
                if n_contracts < 1:
                    continue
                credit_per_contract = THETA_CREDIT_PER_CONTRACT
                max_loss_per_contract = THETA_MAX_LOSS_PER_CONTRACT

                if rng.random() < THETA_WIN_RATE:
                    equity += credit_per_contract * n_contracts
                else:
                    net_loss = (max_loss_per_contract - credit_per_contract) * n_contracts
                    equity -= net_loss

            results[sim, day + 1] = equity
    return results


def project(capital, simulations=20000, seed=42):
    rng = np.random.default_rng(seed)

    horizons = {
        "1_day": 1,
        "1_week": 5,    # 5 trading days
        "1_month": 20,  # ~20 trading days
        "3_months": 63, # ~3 months
        "6_months": 126,# ~6 months
        "1_year": 252,  # ~252 trading days
    }

    projections = {}
    for label, days in horizons.items():
        results = simulate_combined(capital, days, simulations, rng)
        final = results[:, -1]

        projections[label] = {
            "days": days,
            "starting_capital": capital,
            "median": float(np.median(final)),
            "p25": float(np.percentile(final, 25)),
            "p75": float(np.percentile(final, 75)),
            "p10": float(np.percentile(final, 10)),
            "p90": float(np.percentile(final, 90)),
            "mean": float(np.mean(final)),
            "std": float(np.std(final)),
            "median_return_pct": float((np.median(final) - capital) / capital * 100),
            "p10_return_pct": float((np.percentile(final, 10) - capital) / capital * 100),
            "p90_return_pct": float((np.percentile(final, 90) - capital) / capital * 100),
        }

    return projections


def main():
    parser = argparse.ArgumentParser(description="London Breakout bot — Monte Carlo projections")
    parser.add_argument("--capital", type=float, default=1000, help="Starting capital (default: 1000)")
    parser.add_argument("--all-capitals", action="store_true", help="Project both $100 and $1,000")
    parser.add_argument("--simulations", type=int, default=20000, help="Number of Monte Carlo simulations")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"London Breakout Bot — Monte Carlo Projections")
    print(f"  Risk per trade: {RISK_PCT*100}% of equity (continuous reinvestment)")
    print(f"  Historical stats: {WIN_RATE*100:.1f}% win rate, {PROFIT_FACTOR} profit factor, {TRADES_PER_DAY:.2f} trades/day")
    print(f"  Expected R/trade: {EXPECTED_R:.2f}")
    print(f"  Theta: {THETA_WIN_RATE*100:.0f}% win, weekly cadence, {THETA_RISK_PCT*100:.0f}% equity risk/spread")
    print()

    capitals = [100, 300, 1000] if args.all_capitals else [args.capital]
    all_projections = {}

    for cap in capitals:
        print(f"\n{'='*60}")
        print(f"  Capital: ${cap:,.2f} | {args.simulations:,} sims")
        print(f"{'='*60}\n")

        projections = project(cap, args.simulations, args.seed)
        all_projections[str(int(cap))] = projections

        for label, data in projections.items():
            print(f"{'='*60}")
            print(f"  {label.upper()}  ({data['days']} trading days)")
            print(f"{'='*60}")
            print(f"  Median final:        ${data['median']:,.2f}  ({data['median_return_pct']:+.1f}%)")
            print(f"  P25-P75 range:       ${data['p25']:,.2f} - ${data['p75']:,.2f}")
            print(f"  P10-P90 range:       ${data['p10']:,.2f} - ${data['p90']:,.2f}")
            print(f"  Mean:                ${data['mean']:,.2f}")
            print(f"  Std dev:             ${data['std']:,.2f}")
            print()

    trades_per_year = TRADES_PER_DAY * 252
    annual_expected_return = EXPECTED_R * RISK_PCT * trades_per_year
    print(f"\n  Annualized expected return (simple): {annual_expected_return*100:.1f}%")
    print(f"  With compounding (continuous reinvestment): ~{((1 + RISK_PCT * EXPECTED_R) ** trades_per_year - 1)*100:.1f}%")
    print()

    output = {
        "simulations": args.simulations,
        "historical_stats": {
            "win_rate": WIN_RATE,
            "profit_factor": PROFIT_FACTOR,
            "total_trades": TOTAL_TRADES,
            "trading_days": TRADING_DAYS,
            "trades_per_day": round(TRADES_PER_DAY, 2),
            "expected_r_per_trade": round(EXPECTED_R, 3),
            "avg_win_r": AVG_WIN_R,
            "avg_loss_r": AVG_LOSS_R,
        },
        "risk_params": {
            "risk_pct": RISK_PCT,
            "rr_ratio": 2.0,
            "theta": {
                "win_rate": THETA_WIN_RATE,
                "trades_per_breakout": THETA_TRADES_PER_BREAKOUT,
                "risk_pct": THETA_RISK_PCT,
                "risk_per_contract": THETA_MAX_LOSS_PER_CONTRACT,
                "credit_per_contract": THETA_CREDIT_PER_CONTRACT,
                "contract_scaling": "int(risk_amount / max_loss) per contract",
                "threshold_for_1_contract": "$" + str(THETA_MAX_LOSS_PER_CONTRACT / THETA_RISK_PCT),
            },
        },
        "projections": all_projections,
    }

    outpath = "/home/workspace/robinhood-trading-bot/projections.json"
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Full results saved to: {outpath}")


if __name__ == "__main__":
    main()
