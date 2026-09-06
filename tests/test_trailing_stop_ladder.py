import pandas as pd

from src.trailing_stop_ladder import TrailingStopLadderStrategy
from src.risk import RiskManager


def make_bars(closes, volumes=None):
    volumes = volumes or [100] * len(closes)
    index = pd.date_range("2026-08-03 09:35", periods=len(closes), freq="5min", tz="America/New_York")
    return pd.DataFrame({"open": closes, "high": [x + .1 for x in closes], "low": [x - .1 for x in closes], "close": closes, "volume": volumes}, index=index)


def make_strategy(**overrides):
    cfg = {"trailing_stop_ladder": dict({"volume_multiplier": 1, "ema_fast": 4, "ema_slow": 10, "atr_length": 5, "swing_lookback": 5, "momentum_lookback": 3}, **overrides)}
    return TrailingStopLadderStrategy(cfg, RiskManager({"capital": 10000, "risk_pct": .02}), None)


def test_no_signal_without_trend_alignment():
    strategy = make_strategy()
    closes = [10 - i * .05 for i in range(28)] + [8.9]
    bars = make_bars(closes, [100] * 28 + [300])
    assert strategy.generate_signal("TEST", bars) is None


def test_signal_long_with_defined_risk():
    strategy = make_strategy()
    closes = [10 + i * .04 for i in range(25)] + [10.9, 10.95, 11.0, 11.05]
    bars = make_bars(closes, [100] * 28 + [300])
    signal = strategy.generate_signal("TEST", bars)
    assert signal is not None
    assert signal["direction"] == "long"
    assert 0 < signal["stop"] < signal["entry"]


def test_ladder_locks_stop_at_breakeven_then_locks_profit():
    strategy = make_strategy(rung_r=1.0, lock_offset_r=1.0)
    entry, stop = 10.0, 9.5
    strategy._active_trades["TEST"] = {"symbol": "TEST", "direction": "long", "entry": entry, "stop": stop, "target": 0.0, "qty": 100, "timestamp": "2026-08-03T09:40:00-04:00", "entry_bar_count": 1, "rung": 0}
    closes = [10.0] * 7 + [11.1, 10.2]
    bars = make_bars(closes)
    result = strategy.check_exit("TEST", bars, None)
    assert result is not None
    assert result["reason"] == "trailing_stop"
    assert result["exit_price"] >= entry
    assert result["rr"] == 1.0
