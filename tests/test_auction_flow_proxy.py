import pandas as pd
from src.auction_flow_proxy import AuctionFlowProxyStrategy
from src.risk import RiskManager


def test_proxy_rejects_without_session_or_history():
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "auction_flow_proxy": {"trend_length": 5}}
    strategy = AuctionFlowProxyStrategy(config, RiskManager(config), None)
    idx = pd.date_range("2026-08-12 08:00", periods=6, freq="5min", tz="America/New_York")
    bars = pd.DataFrame({"open": [10]*6, "high": [10.1]*6, "low": [9.9]*6, "close": [10]*6, "volume": [100]*6}, index=idx)
    assert strategy.generate_signal("TEST", bars) is None


def test_proxy_long_discount_rejection():
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "auction_flow_proxy": {"trend_length": 5, "location_lookback": 10, "volume_multiplier": .5}}
    strategy = AuctionFlowProxyStrategy(config, RiskManager(config), None)
    idx = pd.date_range("2026-08-12 09:30", periods=10, freq="5min", tz="America/New_York")
    close = [10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.45, 10.35, 10.0, 10.5]
    bars = pd.DataFrame({"open": close, "high": [x+.04 for x in close], "low": [x-.04 for x in close], "close": close, "volume": [100]*9+[200]}, index=idx)
    bars.iloc[-1, bars.columns.get_loc("low")] = 9.7
    signal = strategy.generate_signal("TEST", bars)
    assert signal and signal["direction"] == "long"


def test_proxy_requires_directional_confirmation():
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True,
              "auction_flow_proxy": {"trend_length": 5, "location_lookback": 10, "volume_multiplier": .5}}
    strategy = AuctionFlowProxyStrategy(config, RiskManager(config), None)
    idx = pd.date_range("2026-08-12 09:30", periods=10, freq="5min", tz="America/New_York")
    close = [10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.45, 10.35, 10.0, 9.95]
    bars = pd.DataFrame({"open": close, "high": [x+.04 for x in close], "low": [x-.04 for x in close], "close": close, "volume": [100]*9+[200]}, index=idx)
    bars.iloc[-1, bars.columns.get_loc("low")] = 9.7
    assert strategy.generate_signal("TEST", bars) is None


def test_proxy_rejects_abnormal_gap_and_range():
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True,
              "auction_flow_proxy": {"trend_length": 5, "location_lookback": 10, "volume_multiplier": .5,
                                      "max_gap_pct": .05, "max_bar_range_pct": .05}}
    strategy = AuctionFlowProxyStrategy(config, RiskManager(config), None)
    idx = pd.date_range("2026-08-12 09:30", periods=10, freq="5min", tz="America/New_York")
    close = [10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.45, 10.35, 10.0, 10.5]
    bars = pd.DataFrame({"open": close, "high": [x+.04 for x in close], "low": [x-.04 for x in close], "close": close, "volume": [100]*9+[200]}, index=idx)
    bars.iloc[-1, bars.columns.get_loc("low")] = 9.7
    bars.iloc[-1, bars.columns.get_loc("open")] = 11.0
    assert strategy.generate_signal("TEST", bars) is None
