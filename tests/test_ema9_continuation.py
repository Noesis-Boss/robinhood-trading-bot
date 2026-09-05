import pandas as pd

from src.ema9_continuation import Ema9ContinuationStrategy
from src.risk import RiskManager


def make_bars(closes, volumes=None):
    volumes = volumes or [100] * len(closes)
    index = pd.date_range("2026-08-03 09:30", periods=len(closes), freq="5min", tz="America/New_York")
    return pd.DataFrame({"open": closes, "high": [x + .1 for x in closes], "low": [x - .1 for x in closes], "close": closes, "volume": volumes}, index=index)


def test_research_strategy_has_no_signal_without_volume_confirmation():
    strategy = Ema9ContinuationStrategy({"ema9_continuation": {"volume_multiplier": 2}}, RiskManager({"capital": 10000, "risk_pct": .02}), None)
    bars = make_bars([10] * 25 + [10.5, 10.3, 10.2, 10.4], [100] * 29)
    assert strategy.generate_signal("TEST", bars) is None


def test_signal_contains_defined_risk_levels():
    strategy = Ema9ContinuationStrategy({"ema9_continuation": {"volume_multiplier": 1}}, RiskManager({"capital": 10000, "risk_pct": .02}), None)
    closes = [10 + i * .03 for i in range(25)] + [10.68, 10.62, 10.58, 10.70]
    bars = make_bars(closes, [100] * 28 + [300])
    signal = strategy.generate_signal("TEST", bars)
    assert signal is not None
    assert signal["direction"] == "long"
    assert signal["stop"] < signal["entry"] < signal["target"]
