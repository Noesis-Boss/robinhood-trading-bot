import os
from datetime import datetime, timezone


class RobinhoodReadOnly:
    def __init__(self, client_factory=None):
        self._client_factory = client_factory
        self._client = None

    def snapshot(self):
        if not os.environ.get("ROBINHOOD_USERNAME") or not os.environ.get("ROBINHOOD_PASSWORD"):
            return {"status": "not_configured", "message": "Robinhood credentials are not configured."}
        try:
            if self._client is None:
                factory = self._client_factory
                if factory is None:
                    from robin_stocks import robinhood as client
                    client.login(
                        username=os.environ["ROBINHOOD_USERNAME"],
                        password=os.environ["ROBINHOOD_PASSWORD"],
                        mfa_code=os.environ.get("ROBINHOOD_MFA_TOKEN", ""),
                    )
                else:
                    client = factory()
                    client.login(
                        username=os.environ["ROBINHOOD_USERNAME"],
                        password=os.environ["ROBINHOOD_PASSWORD"],
                        mfa_code=os.environ.get("ROBINHOOD_MFA_TOKEN", ""),
                    )
                self._client = client
            account_loader = self._client.load_account_profile if hasattr(self._client, "load_account_profile") else self._client.account
            positions_loader = self._client.build_holdings if hasattr(self._client, "build_holdings") else self._client.positions
            orders_loader = self._client.get_all_stock_orders if hasattr(self._client, "get_all_stock_orders") else self._client.orders
            account = account_loader() or {}
            raw_positions = positions_loader() or {}
            if isinstance(raw_positions, dict):
                positions = [{"symbol": symbol, **position} for symbol, position in raw_positions.items()]
            else:
                positions = raw_positions
            if hasattr(self._client, "get_crypto_positions"):
                crypto_positions = self._client.get_crypto_positions() or []
                for position in crypto_positions:
                    quantity = float(position.get("quantity") or 0)
                    symbol = (position.get("currency") or {}).get("code")
                    if quantity > 0 and symbol:
                        quote = self._client.get_crypto_quote(symbol) or {}
                        price = float(quote.get("mark_price") or quote.get("ask_price") or 0)
                        positions.append({"asset_type": "crypto", "symbol": symbol, "quantity": position.get("quantity"), "market_value": quantity * price, "unrealized_pnl": 0})
            if hasattr(self._client, "get_open_option_positions"):
                option_positions = self._client.get_open_option_positions() or []
                positions.extend({"asset_type": "option", **position} for position in option_positions if float(position.get("quantity") or 0) > 0)
            for position in positions:
                position.setdefault("asset_type", "stock")
            orders = orders_loader() or []
            cash = account.get("cash")
            holdings_value = sum(float(position.get("equity") or 0) for position in positions)
            portfolio_value = account.get("portfolio_value") or f"{holdings_value + float(cash or 0):.2f}"
            for position in positions:
                position["market_value"] = float(position.get("market_value") or position.get("equity") or 0)
                position["unrealized_pnl"] = float(position.get("unrealized_pnl") or position.get("equity_change") or 0)
            return {
                "status": "ok",
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "account": {
                    "cash": float(cash or 0),
                    "buying_power": float(account.get("buying_power") or 0),
                    "portfolio_value": float(portfolio_value or 0),
                },
                "positions": positions,
                "orders": orders,
            }
        except Exception as exc:
            self._client = None
            return {"status": "error", "message": str(exc)[:240]}
