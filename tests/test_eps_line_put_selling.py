import pandas as pd
import pytest

from src.margin_stress import PATH_2008, run_stress
from src.eps_line_put_selling import EpsLinePutSellingStrategy, bs_put_price
from src.risk import RiskManager


class Journal:
    def log_trade(self, trade):
        pass


def make_strategy(eps=6.67, capital=100_000, **cfg_overrides):
    cfg = {"capital": capital, "eps_line_put_selling": {"eps": {"SPY": eps}, **cfg_overrides}}
    return EpsLinePutSellingStrategy(cfg, RiskManager(cfg), Journal())


def day(close=100.0, date="2026-08-03"):
    index = pd.date_range(f"{date} 09:30", periods=2, freq="5min", tz="America/New_York")
    return pd.DataFrame({"close": [close, close]}, index=index)


def test_put_price_is_positive_and_increases_with_vol():
    low = bs_put_price(100, 100, 2.0, 0.20, 0.04)
    high = bs_put_price(100, 100, 2.0, 0.50, 0.04)
    assert 0 < low < high
    assert bs_put_price(100, 100, 0, 0.5, 0.04) == 0.0


def test_sells_long_dated_put_at_eps_line_entry():
    strat = make_strategy()
    trade = strat.generate_trade("SPY", day(close=100.0))
    assert trade is not None
    assert trade["paper_only"] is True
    assert trade["dte"] == 730
    assert trade["strike"] == pytest.approx(100.05, abs=0.5)
    assert trade["contracts"] >= 1
    assert trade["premium_collected"] > 0
    assert trade["max_liability"] > trade["premium_collected"]


def test_skips_entries_above_eps_line_tolerance():
    strat = make_strategy(entry_tolerance_pct=0.0)
    assert strat.generate_trade("SPY", day(close=110.0)) is None


def test_cooldown_blocks_same_month_reentry():
    strat = make_strategy()
    assert strat.generate_trade("SPY", day()) is not None
    assert strat.generate_trade("SPY", day(date="2026-08-10")) is None
    assert strat.generate_trade("SPY", day(date="2026-09-25")) is not None


def test_cash_securing_contracts_fit_capital():
    # $10k cannot cash-secure even one 100-strike contract -> no trade.
    small = make_strategy(capital=10_000, max_contracts=100)
    assert small.generate_trade("SPY", day()) is None
    # Larger capital: contracts sized so strike collateral fits the 30% budget.
    strat = make_strategy(capital=100_000, max_contracts=100)
    trade = strat.generate_trade("SPY", day())
    assert trade is not None
    assert trade["contracts"] * trade["strike"] * 100 <= 100_000 * 0.30 * 1.01


def test_margin_stress_cash_secured_survives_2008():
    result = run_stress(portfolio_value=100_000, eps=6.67, price=100.0, securing="cash", contracts=1)
    assert result["verdict"] == "SURVIVED"
    assert result["margin_called_month"] is None
    assert result["final_equity"] < 100_000


def test_margin_stress_margin_secured_flags_call():
    result = run_stress(portfolio_value=100_000, eps=6.67, price=100.0, securing="margin", contracts=5, margin_leverage=2.0)
    assert result["verdict"] == "MARGIN_CALL"
    assert result["margin_called_month"] is not None
    assert result["forced_liquidation_events"]
    assert result["liquidation_slippage_loss"] > 0


def test_stress_path_is_real_2008_shape():
    assert len(PATH_2008) == 12
    assert sum(PATH_2008) < -0.30
