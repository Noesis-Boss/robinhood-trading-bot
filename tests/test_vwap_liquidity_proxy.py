import pandas as pd

from src.vwap_liquidity_proxy import VWAPLiquidityProxyStrategy
from src.risk import RiskManager


def bars(closes, volumes=None):
    volumes = volumes or [100] * len(closes)
    idx = pd.date_range("2026-08-14 09:30", periods=len(closes), freq="5min", tz="America/New_York")
    opens = [closes[0]] + list(closes[:-1])
    return pd.DataFrame({"open": opens, "high": [max(o, c) + .2 for o, c in zip(opens, closes)], "low": [min(o, c) - .2 for o, c in zip(opens, closes)], "close": closes, "volume": volumes}, index=idx)


def strategy(**cfg):
    config = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "vwap_liquidity_proxy": {"volume_multiplier": 1, "max_bar_range_pct": .1}}
    config["vwap_liquidity_proxy"].update(cfg)
    return VWAPLiquidityProxyStrategy(config, RiskManager(config), None)


def test_reclaim_requires_volume_and_returns_long_signal():
    s = strategy()
    values = [10] * 18 + [9.8, 10.3]
    signal = s.generate_signal("TEST", bars(values, [100] * 19 + [300]))
    assert signal and signal["direction"] == "long"
    assert signal["target"] > signal["entry"] > signal["stop"]


def test_low_volume_reclaim_is_rejected():
    s = strategy()
    values = [10] * 18 + [9.8, 10.3]
    assert s.generate_signal("TEST", bars(values, [100] * 19 + [50])) is None


def test_one_entry_per_session():
    s = strategy()
    values = [10] * 18 + [9.8, 10.3]
    frame = bars(values, [100] * 19 + [300])
    signal = s.generate_signal("TEST", frame)
    s.on_trade_entered("TEST", signal)
    s._active_trades.clear()
    assert s.generate_signal("TEST", frame) is None
