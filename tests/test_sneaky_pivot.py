import pandas as pd
from src.sneaky_pivot import SneakyPivotStrategy
from src.risk import RiskManager


def make_strategy(**cfg):
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "sneaky_pivot": {"proximity_pct": .02, **cfg}}
    return SneakyPivotStrategy(config, RiskManager(config), None)


def bars(rows):
    idx = pd.date_range("2026-08-10 09:30", periods=len(rows), freq="15min", tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def test_lower_level_three_candle_long():
    strat = make_strategy(proximity_pct=.03)
    data = bars([(10,10.2,9.8,10,100),(9.9,10.1,9.7,9.8,100),(9.75,9.9,9.6,9.7,100),(9.7,9.8,9.5,9.6,100),(9.6,9.7,9.5,9.65,100),(9.65,9.7,9.6,9.65,100),(9.65,9.9,9.6,9.8,200)])
    signal = strat.generate_signal("TEST", data, {"prior_high": 10.5, "prior_low": 9.8})
    assert signal["direction"] == "long"
    assert signal["stop"] < signal["entry"]


def test_upper_level_three_candle_short():
    strat = make_strategy()
    data = bars([(10,10.2,9.8,10,100),(10.1,10.3,9.9,10.2,100),(10.2,10.4,10.0,10.3,100),(10.3,10.5,10.1,10.4,100),(10.5,10.55,10.3,10.4,100),(10.45,10.5,10.35,10.4,100),(10.4,10.45,10.0,10.3,200)])
    signal = strat.generate_signal("TEST", data, {"prior_high": 10.3, "prior_low": 9.5})
    assert signal["direction"] == "short"
    assert signal["stop"] > signal["entry"]


def test_rejects_price_far_from_levels():
    strat = make_strategy(proximity_pct=.001)
    data = bars([(10,10.2,9.8,10,100)] * 7)
    assert strat.generate_signal("TEST", data, {"prior_high": 20, "prior_low": 1}) is None
