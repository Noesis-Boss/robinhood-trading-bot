import logging


class RiskManager:
    """Position sizing and risk validation for the London Breakout strategy.

    From the video: with a $10k account, the trader risks $200 per trade
    (2% of capital). Risk per share = entry - stop.

    When fractional_shares is enabled (default), quantity is a float so the
    full risk dollar amount deploys on any stock price. Otherwise quantity
    is floored to whole shares.
    """

    def __init__(self, config: dict):
        self.config = config
        self.capital = config.get("capital", 10000)
        self.risk_pct = config.get("risk_pct", 0.02)
        self.risk_dollars = self.capital * self.risk_pct
        self.max_risk_dollars = config.get("max_risk_dollars", self.risk_dollars)
        self.fractional = config.get("fractional_shares", True)
        self.min_order_value = config.get("min_order_value", 1.0)
        # Shorts must be whole shares (fractional shorting not supported by RH)
        self._cash = self.capital

    def validate_order(self, qty: float, entry_price: float, risk_per_share: float) -> tuple[bool, str]:
        """Check if an order passes risk validation.

        Returns (True, "ok") or (False, reason).
        """
        total_risk = qty * risk_per_share
        if total_risk > self.max_risk_dollars:
            return False, f"order risk ${total_risk:.2f} exceeds max ${self.max_risk_dollars:.2f}"
        if qty * entry_price > self._cash:
            return False, "insufficient capital"
        return True, "ok"

    def calculate_qty(self, entry: float, stop: float, allow_fractional: bool | None = None) -> float:
        """Calculate position size based on fixed-dollar risk.

        Args:
            entry: Entry price.
            stop: Stop loss price.

        Returns:
            Number of shares to trade (fractional if enabled, else whole).
            Returns 0 if the notional order value is below the minimum.
        """
        risk_per_share = abs(entry - stop)
        if risk_per_share == 0:
            logging.warning("Zero risk per share — entry equals stop")
            return 1.0 if self.fractional else 1

        # Risk-based size: how much notional fits the risk budget?
        max_qty_by_risk = self.max_risk_dollars / risk_per_share
        # Cash cap: don't let the full position value exceed available cash
        max_affordable = self._cash / entry
        qty = min(max_qty_by_risk, max_affordable)

        use_fractional = self.fractional if allow_fractional is None else allow_fractional
        if use_fractional:
            qty = round(qty, 4)
        else:
            qty = max(1, int(qty))

        # Enforce minimum notional (RH fractional min is ~$1)
        if qty * entry < self.min_order_value:
            logging.warning(
                f"Order value ${qty * entry:.2f} below min ${self.min_order_value:.2f} "
                f"(entry ${entry:.2f}) — skipping"
            )
            return 0.0

        if qty < 1e-12:
            logging.warning(f"Cannot afford position at ${entry:.2f} with ${self._cash:.2f} cash")
            return 0.0
        return qty

    def update_cash(self, pnl: float) -> None:
        """Update cash balance after a trade."""
        self._cash += pnl
        self.capital = max(0, self._cash)
        self.risk_dollars = self.capital * self.risk_pct
        self.max_risk_dollars = self.config.get("max_risk_dollars", self.risk_dollars)
        logging.info(f"Cash balance: ${self._cash:.2f} | Capital: ${self.capital:.2f}")
