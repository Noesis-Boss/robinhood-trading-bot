"""2008-style margin stress case for long-dated put selling. PAPER ONLY.

Replays the actual 2008 S&P 500 monthly return path (-38.5% year) against a
portfolio carrying sold long-dated puts (cash- or margin-secured), applies
maintenance-margin requirements, and detects the margin-call spiral: equity
falls -> maintenance requirement bites -> forced share liquidation -> equity
falls further.

CLI (paper-only, no orders):
    python3 margin_stress.py --portfolio-value 100000 --eps 28 --symbol SPY
"""
import argparse
import json
import math

from src.eps_line_put_selling import bs_put_price

# Real 2008 S&P 500 total-return monthly path, Jan-Dec 2008.
PATH_2008 = [-0.061, -0.035, -0.006, 0.048, 0.015, -0.084,
             -0.008, 0.015, -0.092, -0.168, -0.075, 0.010]


def run_stress(
    portfolio_value: float,
    eps: float,
    price: float,
    target_pe: float = 15.0,
    contracts: int | None = None,
    strike: float | None = None,
    dte: float = 730.0,
    iv: float = 0.35,
    risk_free: float = 0.04,
    securing: str = "margin",
    margin_leverage: float = 1.5,
    maintenance_pct: float = 0.20,
    max_collateral_pct: float = 0.30,
    max_contracts: int = 5,
    path: list[float] | None = None,
) -> dict:
    path = path or PATH_2008
    eps_line = eps * target_pe
    if strike is None:
        strike = eps_line
    premium = bs_put_price(price, strike, dte / 365.0, iv, risk_free)

    if contracts is None:
        collateral = portfolio_value * (margin_leverage if securing == "margin" else 1.0)
        contracts = min(int(collateral * max_collateral_pct / (strike * 100)), max_contracts)
    contracts = max(contracts, 0)

    premium_cash = premium * 100.0 * contracts
    if securing == "margin":
        # Leverage buys MORE shares; equity starts at portfolio_value.
        shares_value = portfolio_value * margin_leverage
        loan = shares_value - portfolio_value
    else:
        # Cash-secured: premium collected is idle cash, not investable collateral.
        shares_value = portfolio_value - premium_cash
        loan = 0.0

    months_elapsed = 0.0
    events, monthly = [], []
    margin_called_at = None
    liquidation_loss = 0.0

    for i, ret in enumerate(path):
        spot = price * (1 + ret)
        shares_value *= (1 + ret)
        months_elapsed += 1
        remaining_years = max((dte - months_elapsed * 30.4) / 365.0, 0.02)
        stressed_iv = min(iv * (1 + 0.5 * max(0, -ret) * 10), 1.20)
        liability = bs_put_price(spot, strike, remaining_years, stressed_iv, risk_free) * 100.0 * contracts

        equity = shares_value - loan + premium_cash
        maintenance = (shares_value * maintenance_pct if securing == "margin" else 0.0) \
            + strike * 100.0 * contracts * 0.10 + max(strike - spot, 0) * 100.0 * contracts

        if equity < maintenance and margin_called_at is None:
            margin_called_at = i + 1
            deficit = maintenance - equity
            forced_sale = min(deficit / max(1 - maintenance_pct, 0.01), shares_value)
            liquidation_loss = forced_sale * 0.03  # 3% liquidation slippage
            shares_value -= forced_sale
            equity = shares_value - loan + premium_cash
            events.append({
                "month": i + 1, "spot": round(spot, 2), "equity": round(equity, 2),
                "maintenance": round(maintenance, 2), "forced_sale": round(forced_sale, 2),
            })

        monthly.append({
            "month": i + 1, "spot": round(spot, 2), "shares_value": round(shares_value, 2),
            "put_liability": round(liability, 2), "equity": round(equity, 2),
            "maintenance": round(maintenance, 2),
        })

    verdict = "SURVIVED" if margin_called_at is None else "MARGIN_CALL"
    return {
        "paper_only": True,
        "scenario": "2008 SPX monthly path (-38.5% year)",
        "securing": securing,
        "margin_leverage": margin_leverage if securing == "margin" else None,
        "start_price": price, "eps_line": round(eps_line, 2), "strike": round(strike, 2),
        "dte": dte, "contracts": contracts,
        "premium_collected": round(premium_cash, 2),
        "start_equity": round(portfolio_value, 2),
        "final_spot": monthly[-1]["spot"],
        "final_equity": monthly[-1]["equity"],
        "verdict": verdict,
        "margin_called_month": margin_called_at,
        "forced_liquidation_events": events,
        "liquidation_slippage_loss": round(liquidation_loss, 2),
        "monthly": monthly,
    }


def main():
    parser = argparse.ArgumentParser(description="2008 margin stress case for EPS-line put selling (paper only)")
    parser.add_argument("--portfolio-value", type=float, default=100000)
    parser.add_argument("--eps", type=float, required=True, help="trailing EPS of the underlying")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--price", type=float, default=None, help="current spot; defaults to eps x 15")
    parser.add_argument("--securing", choices=["cash", "margin"], default="margin")
    parser.add_argument("--margin-leverage", type=float, default=1.5)
    parser.add_argument("--maintenance-pct", type=float, default=0.20)
    parser.add_argument("--contracts", type=int, default=None)
    args = parser.parse_args()
    price = args.price or args.eps * 15.0
    result = run_stress(
        portfolio_value=args.portfolio_value, eps=args.eps, price=price,
        securing=args.securing, margin_leverage=args.margin_leverage,
        maintenance_pct=args.maintenance_pct, contracts=args.contracts,
    )
    print(f"=== PAPER ONLY — {args.symbol} 2008 stress ===")
    print(json.dumps({k: v for k, v in result.items() if k != "monthly"}, indent=2))


if __name__ == "__main__":
    main()
