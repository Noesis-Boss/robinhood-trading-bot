"""Options Theta Farming Projector — capital-aware compounding model.

After a confirmed London Breakout, sell weekly credit spreads to collect
time-decay income. Trades are modeled at the contract level (100 shares/contract).

Position sizing scales by capital: contracts = int(risk_amount / max_loss).
No floor — accounts below the ~$200 threshold cannot afford options spreads
and skip theta farming (London Breakout day trades still compound).
"""
import json

# --- Assumptions ---
WIDTH = 0.30              # $0.30 spread width per share → $30/contract
CREDIT_PER_CONTRACT = 10.0   # $0.10 credit × 100 shares
MAX_LOSS_PER_CONTRACT = 20.0 # width - credit = $0.20 × 100
WIN_RATE = 0.72            # 72% of spreads expire OTM (keep full credit)
TRADES_PER_YEAR = 52

# Target risk as % of capital per trade (theta farming)
RISK_TARGET_PCT = 0.10  # 10% of capital at risk per spread
THETA_THRESHOLD = MAX_LOSS_PER_CONTRACT / RISK_TARGET_PCT  # ~$200 minimum for 1 contract


def contracts_for_capital(capital):
    """How many contracts we can sell so that max loss ~ RISK_TARGET_PCT of cap.
    Uses the new model: int(risk_amount / max_loss) — NO floor.
    Below threshold (~$200), cannot afford any contracts."""
    n = int(capital * RISK_TARGET_PCT / MAX_LOSS_PER_CONTRACT)
    return n  # 0 if capital < ~$200


def simulate(capital, n_trades):
    """Compounding simulation. Returns list of capitals per week."""
    path = [capital]
    cap = capital
    for w in range(n_trades):
        n_contracts = contracts_for_capital(cap)
        if n_contracts < 1:
            # Not enough capital for theta spreads — skip (London trades still occur)
            path.append(round(cap, 2))
            continue
        credit = CREDIT_PER_CONTRACT * n_contracts
        max_loss = MAX_LOSS_PER_CONTRACT * n_contracts
        # Deterministic pseudo-random win/loss based on win rate
        win = ((w * 37 + 13) % 100) < int(WIN_RATE * 100)
        if win:
            cap += credit
        else:
            cap -= (max_loss - credit)  # net loss per contract × n
        path.append(round(cap, 2))
    return path


WEEK_UNITS = {
    "1-day":   1,
    "1-week":  1,
    "1-month": 4,
    "3-months": 12,
    "6-months": 25,
    "1-year":  52,
}

if __name__ == "__main__":
    print("=== Options Theta Farming Projections (capital-aware) ===\n")
    print("Model: post-breakout weekly credit spreads")
    print(f"Spread width: ${WIDTH:.2f}/share | Credit/contract: ${CREDIT_PER_CONTRACT:.2f} | Max loss/contract: ${MAX_LOSS_PER_CONTRACT:.2f}")
    print(f"Win rate: {WIN_RATE*100:.0f}% | 52 trades/year")
    print(f"Risk target: {RISK_TARGET_PCT*100:.0f}% of capital per trade (scales contracts)")
    print(f"Theta threshold: ~${THETA_THRESHOLD:.0f} (minimum to afford 1 contract)\n")

    capitals = [100, 300, 1000]
    all_projections = {}
    for capital in capitals:
        path = simulate(capital, TRADES_PER_YEAR)
        results = {}
        n_c = contracts_for_capital(capital)
        can_theta = n_c >= 1
        for label, n_weeks in WEEK_UNITS.items():
            val = path[n_weeks] if n_weeks < len(path) else path[-1]
            gain = val - capital
            pct = (gain / capital) * 100 if capital > 0 else 0
            rm = MAX_LOSS_PER_CONTRACT * n_c
            risk_pct = (rm / capital) * 100 if capital > 0 else 0
            results[label] = {
                "ending_capital": round(val, 2),
                "gain": round(gain, 2),
                "pct": round(pct, 1),
                "risk_pct_per_trade": round(risk_pct, 1),
                "contracts_per_trade": n_c,
            }
        all_projections[capital] = {
            "results": results,
            "contracts_per_trade": n_c,
            "theta_enabled": can_theta,
        }

        print(f"--- Starting capital: ${capital} ---")
        rm = MAX_LOSS_PER_CONTRACT * n_c
        if can_theta:
            print(f"    {n_c} contract(s)/trade | Risk/trade: ~${rm:.0f} ({rm/capital*100:.0f}% of capital)")
        else:
            print(f"    0 contracts — below ${THETA_THRESHOLD:.0f} threshold (theta disabled)")
            print(f"    Day trading only (London Breakout, 2% risk/trade)")
        for lbl in ["1-day", "1-week", "1-month", "3-months", "6-months", "1-year"]:
            r = results[lbl]
            print(f"    {lbl:12s}: ${r['ending_capital']:>10.2f}  ({r['pct']:+.1f}%  net +${r['gain']:.2f})")
        print()

    output = {
        "strategy": "options_theta_farming",
        "assumptions": {
            "spread_width": WIDTH,
            "credit_per_contract": CREDIT_PER_CONTRACT,
            "max_loss_per_contract": MAX_LOSS_PER_CONTRACT,
            "win_rate": WIN_RATE,
            "risk_target_pct": RISK_TARGET_PCT,
            "trades_per_year": TRADES_PER_YEAR,
            "trading_style": "post-breakout weekly credit spreads",
            "position_sizing": "contracts = int(risk_amount / max_loss), no floor",
        },
        "projections": {
            "$100": all_projections[100],
            "$300": all_projections[300],
            "$1000": all_projections[1000],
        },
    }
    out_path = "/home/workspace/robinhood-trading-bot/projections_theta.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to `file '{out_path}'`")
