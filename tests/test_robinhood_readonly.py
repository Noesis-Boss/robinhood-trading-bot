from src.robinhood_readonly import RobinhoodReadOnly


class FakeRobinhood:
    def login(self, **kwargs):
        self.logged_in = True

    def account(self):
        return {"cash": "100.00", "buying_power": "250.00", "portfolio_value": "500.00"}

    def positions(self):
        return [{"symbol": "SPY", "quantity": "1"}]

    def orders(self):
        return [{"id": "order-1", "state": "filled"}]


def test_missing_credentials_is_safe(monkeypatch):
    monkeypatch.delenv("ROBINHOOD_USERNAME", raising=False)
    monkeypatch.delenv("ROBINHOOD_PASSWORD", raising=False)
    assert RobinhoodReadOnly().snapshot()["status"] == "not_configured"


def test_read_only_snapshot(monkeypatch):
    monkeypatch.setenv("ROBINHOOD_USERNAME", "user")
    monkeypatch.setenv("ROBINHOOD_PASSWORD", "pass")
    result = RobinhoodReadOnly(client_factory=FakeRobinhood).snapshot()
    assert result["status"] == "ok"
    assert result["account"]["cash"] == 100.0
    assert result["positions"][0]["symbol"] == "SPY"
