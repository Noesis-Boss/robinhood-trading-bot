"""Paper-only long-dated put selling on EPS-line valuation entries.

Variant of the "portfolio secured put" idea: sell LONG-dated puts (default
730 DTE, the "two-year put") when price is at or below the EPS line
(trailing EPS x target P/E). Strike defaults to the EPS line itself because
assignment at fair value is the thesis, not a failure mode.

PAPER ONLY. This module never places orders; it only records simulated
trades and exposes open positions for the 2008 margin stress case in
`src/margin_stress.py`.
"""
import math
from datetime import timedelta

import pandas as pd

from .risk import RiskManager

DEFAULTS = {
    "target_pe": 15.0,
    "entry_tolerance_pct": 0.05,
    "dte": 730,
    "iv": 0.35,
    "risk_free": 0.04,
    "strike_pct_of_eps_line": 1.0,
    "max_collateral_pct": 0.30,
    "securing": "cash",
    "margin_leverage": 1.5,
    "maintenance_margin_pct": 0.20,
    "min_days_between_entries": 21,
    "max_contracts": 5,
}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_put_price(spot: float, strike: float, years: float, iv: float, risk_free: float) -> float:
    if years <= 0 or iv <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (risk_free + iv * iv / 2) * years) / (iv * math.sqrt(years))
    d2 = d1 - iv * math.sqrt(years)
    return strike * math.exp(-risk_free * years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


class EpsLinePutSellingStrategy:
    """Sell long-dated puts at the EPS line. Cash-secured by default."""

    def __init__(self, config, risk: RiskManager, journal):
        merged = {**DEFAULTS, **(config.get("eps_line_put_selling", {}) or {})}
        self.cfg = merged
        self.risk = risk
        self.journal = journal
        self.eps = self._parse_eps(config.get("eps_line_put_selling", {}) or {})
        self.open_positions = []
        self._last_entry = {}
        self.paper_only = True

    @staticmethod
    def _parse_eps(cfg):
        eps = cfg.get("eps", {})
        if isinstance(eps, dict):
            if "eps" in eps and isinstance(eps["eps"], dict):
                eps = eps["eps"]
            return {str(k).upper(): float(v) for k, v in eps.items() if v}
        if isinstance(eps, (int, float)):
            return float(eps)
        return {}

    def eps_for(self, symbol: str) -> float | None:
        if isinstance(self.eps, dict):
            return self.eps.get(symbol.upper())
        return self.eps or None

    def collateral_available(self) -> float:
        if self.cfg["securing"] == "margin":
            return self.risk.capital * self.cfg["margin_leverage"]
        return self.risk.capital

    def generate_trade(self, symbol: str, day_data):
        if len(day_data) < 2:
            return None
        eps = self.eps_for(symbol)
        if not eps or eps <= 0:
            return None
        close = float(day_data["close"].iloc[-1])
        day = pd.Timestamp(day_data.index[-1]).date()
        last = self._last_entry.get(symbol)
        if last and (day - last).days < self.cfg["min_days_between_entries"]:
            return None
        eps_line = eps * self.cfg["target_pe"]
        if close > eps_line * (1 + self.cfg["entry_tolerance_pct"]):
            return None

        strike = eps_line * self.cfg["strike_pct_of_eps_line"]
        years = self.cfg["dte"] / 365.0
        premium = bs_put_price(close, strike, years, self.cfg["iv"], self.cfg["risk_free"])
        collateral_per_contract = strike * 100.0
        budget = self.collateral_available() * self.cfg["max_collateral_pct"]
        contracts = int(budget / collateral_per_contract)
        contracts = min(contracts, self.cfg["max_contracts"])
        if contracts < 1:
            return None

        trade = {
            "symbol": symbol,
            "trade_type": "long_put_sell",
            "paper_only": True,
            "entry": close,
            "eps_line": round(eps_line, 2),
            "eps": eps,
            "strike": round(strike, 2),
            "dte": self.cfg["dte"],
            "premium_per_contract": round(premium * 100.0, 2),
            "contracts": contracts,
            "premium_collected": round(premium * 100.0 * contracts, 2),
            "max_liability": round((strike - premium) * 100.0 * contracts, 2),
            "securing": self.cfg["securing"],
            "entry_date": str(day),
            "expiry_date": str(day + timedelta(days=self.cfg["dte"])),
            "pnl": 0.0,
            "reason": "eps_line_entry",
            "status": "open_premium_only",
        }
        self.open_positions.append(trade)
        self._last_entry[symbol] = day
        if self.journal:
            self.journal.log_trade(trade)
        return trade

    def mark_positions(self, spot: float, days_elapsed: float = 0.0) -> float:
        """Mark-to-market liability of open puts under a stressed spot."""
        years = max((self.cfg["dte"] - days_elapsed) / 365.0, 0.0)
        iv = self.cfg["iv"]
        liability = 0.0
        for pos in self.open_positions:
            mark = bs_put_price(spot, pos["strike"], years, iv, self.cfg["risk_free"])
            liability += mark * 100.0 * pos["contracts"]
        return liability
