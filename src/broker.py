import os
import logging

try:
    from robinhood import Robinhood
except ImportError:
    Robinhood = None

from .risk import RiskManager


class Broker:
    """Order execution via Robinhood (or paper-trading stub).

    Set ROBINHOOD_USERNAME / ROBINHOOD_PASSWORD / ROBINHOOD_MFA_TOKEN in env
    to enable real trading. Without credentials, all order methods return
    simulated fills and log to stdout — safe for testing.

    Fractional-share orders are supported in simulation. For live trading,
    set ROBINHOOD_FRACTIONAL=true and use a python-robinhood build that
    submits a fractional quantity; otherwise live orders round to whole shares.
    """

    def __init__(self, config: dict, risk_mgr: RiskManager):
        self.config = config
        self.risk_mgr = risk_mgr
        self.enabled = config.get("robinhood", {}).get("enabled", False)
        self.simulation = not self.enabled
        self.RH_FRACTIONAL = os.environ.get("ROBINHOOD_FRACTIONAL", "false").lower() == "true"
        self._client = None

        if self.enabled:
            if Robinhood is None:
                raise ImportError("Install python-robinhood for live trading: pip install python-robinhood")
            username = os.environ["ROBINHOOD_USERNAME"]
            password = os.environ["ROBINHOOD_PASSWORD"]
            mfa_token = os.environ.get("ROBINHOOD_MFA_TOKEN", "")
            self._client = self._login(username, password, mfa_token)

    def _login(self, username: str, password: str, mfa_code: str) -> "Robinhood":
        client = Robinhood()
        client.login(
            username=username,
            password=password,
            mfa_code=mfa_code,
        )
        return client

    def place_order(self, symbol: str, direction: str, qty: float, order_type: str = "market", entry_price: float = 0.0) -> dict | None:
        """Place a buy (long) or sell short order.

        qty is a float, so fractional-share orders are supported. In
        simulation the fill is reported as-is. For live Robinhood trading,
        fractional orders additionally require the ROBINHOOD_FRACTIONAL env
        flag; without it, live orders round up to whole shares.

        Returns order dict on success, None on failure or simulation.
        """
        side = "buy" if direction == "long" else "sell"

        if entry_price is None:
            entry_price = 0.0
        valid, reason = self.risk_mgr.validate_order(qty, entry_price, 0)
        if not valid:
            logging.warning(f"Order rejected: {reason}")
            return None

        # Live risk guard: fractional longs require explicit opt-in
        if not self.simulation and qty != int(qty) and \
                os.environ.get("ROBINHOOD_FRACTIONAL", "false").lower() != "true":
            logging.warning("Fractional long order requires ROBINHOOD_FRACTIONAL=true; rounding up to whole share")
            qty = max(1, int(qty) + 1)

        if self.simulation:
            order = {
                "id": f"sim-{symbol}-{direction}-{qty:.3f}".rstrip("0").rstrip("."),
                "symbol": symbol,
                "side": side,
                "quantity": qty,
                "type": "market",
                "state": "filled",
                "price": 0.0,
            }
            logging.info(f"[SIMULATION] {side} {qty:.3f} {symbol}")
            return order

        if self._client is None:
            logging.error("Broker not initialized")
            return None

        sent_qty = str(qty) if self.RH_FRACTIONAL else str(max(1, int(qty)))
        order_data = {
            "instrument": self._client.instruments(symbol)[0],
            "quantity": sent_qty,
            "side": side,
            "type": order_type,
            "time_in_force": "day",
        }

        result = self._client.place_order(**order_data)
        logging.info(f"[LIVE] {side} {sent_qty} {symbol} -> order {result.get('id', '?')}")
        return result

    def close_position(self, symbol: str, qty: int, direction: str) -> dict | None:
        """Close an open position."""
        side = "sell" if direction == "long" else "buy"
        return self.place_order(symbol=symbol, direction="short" if direction == "long" else "long", qty=qty)

    def get_position(self, symbol: str) -> dict | None:
        """Return current position for a symbol if any."""
        if self.simulation:
            return None
        positions = self._client.positions()
        for pos in positions:
            if pos.get("symbol") == symbol:
                return pos
        return None

    def place_spread(self, symbol: str, spread_type: str, strike: float,
                     width: float, contracts: int, days_to_expiry: int) -> dict | None:
        """Place an options credit spread (theta farming).

        Args:
            symbol: Underlying stock symbol (e.g. 'AAPL')
            spread_type: 'put' (bullish credit spread) or 'call' (bearish)
            strike: Short strike price
            width: Spread width in dollars (e.g. 2.0 for $2 spread)
            contracts: Number of contracts
            days_to_expiry: Target days to expiry for the spread

        Returns:
            Order confirmation dict or None if simulation/disabled
        """
        if self.simulation:
            logging.info(f"[SIM] Would sell {contracts}x {strike} {spread_type.upper()} spread "
                         f"width=${width}, {days_to_expiry}DTE on {symbol}")
            return {"simulation": True, "symbol": symbol, "spread_type": spread_type,
                    "strike": strike, "width": width, "qty": contracts}
        if not os.environ.get("ROBINHOOD_USE_OPTIONS", "false").lower() == "true":
            logging.warning("Options trading not enabled (set ROBINHOOD_USE_OPTIONS=true)")
            return None
        try:
            leg1 = self._client.place_options_order(
                symbol=symbol, type=f"{spread_type}_spread", side="sell",
                strike=str(strike), quantity=str(contracts))
            leg2 = self._client.place_options_order(
                symbol=symbol, type=f"{spread_type}_spread", side="buy",
                strike=str(strike + width), quantity=str(contracts))
            logging.info(f"Placed {spread_type} credit spread on {symbol}: "
                         f"short {strike}, long {strike + width}, {contracts} contracts")
            return {"leg1": leg1, "leg2": leg2}
        except Exception as e:
            logging.error(f"Options spread order failed: {e}")
            return None
