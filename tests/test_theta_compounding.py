from src.risk import RiskManager
from src.theta_farming import ThetaFarmer


def test_theta_pnl_updates_shared_cash_and_directional_size():
    risk = RiskManager({"capital": 1000, "risk_pct": 0.02, "fractional_shares": True})
    before = risk.calculate_qty(10, 9)
    risk.update_cash(100)
    after = risk.calculate_qty(10, 9)
    assert risk.capital == 1100
    assert after > before


def test_theta_contract_size_uses_shared_updated_capital():
    risk = RiskManager({"capital": 1000, "risk_pct": 0.02, "fractional_shares": True})
    farmer = ThetaFarmer({"max_risk_per_trade_pct": 0.10, "contracts_per_trade": 10})
    max_loss = 20
    assert farmer.size_position(max_loss, capital=risk.capital) == 5
    risk.update_cash(1000)
    assert farmer.size_position(max_loss, capital=risk.capital) == 10
