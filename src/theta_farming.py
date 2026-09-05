"""
Options Theta Farming Module
Strategy: After a successful London Breakout (price holds above/below box for 3+ candles),
sell weekly credit spreads to collect time decay income.
Convert momentum into theta decay profit.
"""
import random
from datetime import datetime

# Realistic per-contract constants for credit spreads so backtest numbers stay
# honest. A ~$20-30 max-loss weekly spread typically collects ~$5-15 of credit
# (25-75% of width) at an ~80% probability of profit.
CREDIT_MIN_PER_CONTRACT = 5.0
CREDIT_MAX_PER_CONTRACT = 15.0
MAX_LOSS_BUDGET_PER_CONTRACT = 30.0

_rng = random.Random(20260808)  # fixed seed -> reproducible backtests


class ThetaFarmer:
    def __init__(self, config):
        self.initial_capital = config.get("initial_capital", 1000)
        self.max_risk_per_trade = config.get("max_risk_per_trade_pct", 0.02)  # 2% of capital
        self.min_days_to_expiry = config.get("min_days_to_expiry", 2)
        self.max_days_to_expiry = config.get("max_days_to_expiry", self.min_days_to_expiry + 3)
        self.target_pop = config.get("target_pop", 0.80)  # target probability OTM
        self.max_spread_width = config.get("max_spread_width_pct", 0.02)  # % of underlying price
        self.contracts_per_trade = config.get("contracts_per_trade", 1)

    def generate_trade(self, symbol, price, direction):
        """Generate a single credit spread trade for a confirmed breakout.

        Args:
            symbol: e.g. 'SPY'
            price: current underlying price (float)
            direction: 'long' (bullish) or 'short' (bearish)

        Returns:
            Trade dict compatible with Broker.place_spread, or None.
        """
        breakout_signal = {"symbol": symbol, "direction": direction, "action": direction}
        dte_list = list(range(self.min_days_to_expiry, self.max_days_to_expiry + 1))
        trades = self.find_eligible_trades(breakout_signal, price, dte_list)
        if not trades:
            return None
        return max(trades, key=lambda t: t.get("credit", 0))

    def find_eligible_trades(self, breakout_signal, current_price, days_to_expiry_list):
        """
        After a confirmed London Breakout, find credit spread opportunities.

        Args:
            breakout_signal: dict from LondonBreakoutStrategy.generate_signal
            current_price: float, current underlying price
            days_to_expiry_list: list of ints (days to expiry for available weekly options)

        Returns:
            list of dicts representing eligible credit spread trades
        """
        if breakout_signal is None or breakout_signal.get("action") == "HOLD":
            return []

        # Only farm theta after breakout is confirmed (box broken + held)
        direction = breakout_signal.get("direction")
        if direction not in ("long", "short"):
            return []

        trades = []
        for dte in days_to_expiry_list:
            if dte < self.min_days_to_expiry:
                continue

            # For LONG breakout → sell PUT spread (bullish, collect premium)
            # For SHORT breakout → sell CALL spread (bearish, collect premium)
            if direction == "long":
                trade = self._build_put_spread(current_price, dte)
            else:
                trade = self._build_call_spread(current_price, dte)

            if trade:
                trades.append(trade)

        return trades

    def _build_put_spread(self, current_price, dte):
        """Build a put credit spread for a bullish breakout."""
        short_strike = round(current_price * (1 - self.target_pop * 0.05), 0)  # ~5% OTM
        if short_strike <= 0:
            return None

        estimated_credit = self._estimate_credit(current_price, "put", short_strike, dte)
        credit_width = self._bounded_width(current_price, estimated_credit)
        long_strike = round(short_strike - credit_width, 0)

        return {
            "type": "put_credit_spread",
            "short_leg": {"strike": short_strike, "type": "put", "action": "sell"},
            "long_leg": {"strike": long_strike, "type": "put", "action": "buy"},
            "width": credit_width,
            "credit": estimated_credit,
            "dte": dte,
            "max_loss": credit_width - estimated_credit,
            "max_gain": estimated_credit,
            "pop": self.target_pop,
            "underlying": current_price,
        }

    def _build_call_spread(self, current_price, dte):
        """Build a call credit spread for a bearish breakout."""
        short_strike = round(current_price * (1 + self.target_pop * 0.05), 0)

        estimated_credit = self._estimate_credit(current_price, "call", short_strike, dte)
        credit_width = self._bounded_width(current_price, estimated_credit)
        long_strike = round(short_strike + credit_width, 0)

        return {
            "type": "call_credit_spread",
            "short_leg": {"strike": short_strike, "type": "call", "action": "sell"},
            "long_leg": {"strike": long_strike, "type": "call", "action": "buy"},
            "width": credit_width,
            "credit": estimated_credit,
            "dte": dte,
            "max_loss": credit_width - estimated_credit,
            "max_gain": estimated_credit,
            "pop": self.target_pop,
            "underlying": current_price,
        }

    def _bounded_width(self, current_price, credit):
        """Strike width (per share) bounded so per-contract max loss stays realistic.

        max_loss = width - credit; keep (width - credit) * 100 <= MAX_LOSS_BUDGET.
        Also never wider than the configured % of price (low-priced names).
        """
        wide = current_price * self.max_spread_width
        budget = (MAX_LOSS_BUDGET_PER_CONTRACT + credit * 100) / 100.0
        return round(max(min(wide, budget), 0.0), 4)

    def _estimate_credit(self, current_price, option_type, strike, dte):
        """Realistic per-share credit so per-contract premium lands in the $5-15 range."""
        width = current_price * self.max_spread_width
        if width <= 0:
            return 0.0
        # More DTE -> more premium, but stay inside the realistic per-contract band.
        time_factor = min(dte / 7.0, 1.0)
        per_contract = 10.0 * (0.5 + time_factor * 0.6)
        per_contract = max(CREDIT_MIN_PER_CONTRACT, min(CREDIT_MAX_PER_CONTRACT, per_contract))
        per_share = min(per_contract / 100.0, width * 0.9)
        return round(per_share, 4)

    def size_position(self, max_loss, capital=None):
        """Calculate position size based on capital and risk."""
        capital = self.initial_capital if capital is None else capital
        risk_amount = capital * self.max_risk_per_trade
        max_contracts = int(risk_amount / max_loss) if max_loss > 0 else 1
        return min(max_contracts, self.contracts_per_trade)

    def execute_trade(self, trade, capital=None):
        """Execute a theta farming trade (paper mode by default)."""
        contracts = self.size_position(trade["max_loss"] * 100, capital=capital)
        if contracts < 1:
            return None

        total_credit = trade["credit"] * 100 * contracts  # 100 shares per contract

        return {
            "trade_id": f"theta_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "executed_at": datetime.now().isoformat(),
            "credit_collected": total_credit,
            "contracts": contracts,
            "new_capital": (capital if capital is not None else self.initial_capital) + total_credit,
            "type": trade["type"],
            "dte": trade["dte"],
        }

    def simulate_expiry(self, trade, contracts):
        """Resolve a credit spread to its realistic expiry P&L.

        The short spread expires worthless (keep credit) with probability POP;
        otherwise it is in the money and realizes the full max loss. This is what
        makes backtests honest: not every theta trade is a guaranteed win.
        """
        credit = trade["credit"]
        width = trade["width"]
        pop = trade.get("pop", self.target_pop)
        if _rng.random() < pop:
            return round(credit * 100 * contracts, 2)
        return round(-(width - credit) * 100 * contracts, 2)

    def get_weekly_summary(self):
        """Return summary of theta farming performance."""
        return {
            "starting_capital": self.initial_capital,
            "current_capital": self.initial_capital,
            "total_return": 0,
            "return_pct": 0,
        }
