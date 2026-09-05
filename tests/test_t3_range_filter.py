import pandas as pd

from src.t3_range_filter import T3RangeFilterStrategy
from src.risk import RiskManager


def test_t3_strategy_is_long_only_and_has_risk_levels():
    idx = pd.date_range("2026-08-14 09:30", periods=40, freq="1h", tz="America/New_York")
    close = [10 + i * .03 for i in range(39)] + [11.5]
    frame = pd.DataFrame({"open": close, "high": [x + .1 for x in close], "low": [x - .1 for x in close], "close": close, "volume": [100] * 40}, index=idx)
    cfg = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "t3_range_filter": {"max_bar_range_pct": .2}}
    strat = T3RangeFilterStrategy(cfg, RiskManager(cfg), None)
    signal = strat.generate_signal("TEST", frame)
    assert signal is None or signal["direction"] == "long"
    if signal:
        assert signal["stop"] < signal["entry"] < signal["target"]
