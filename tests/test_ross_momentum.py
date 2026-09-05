import pandas as pd

from src.ross_momentum import RossMomentumStrategy
from src.risk import RiskManager


def make_bars(closes, volumes=None, start="2026-08-08 09:30", freq="5min"):
    index = pd.date_range(start, periods=len(closes), freq=freq, tz="America/New_York")
    volumes = volumes or [100] * len(closes)
    return pd.DataFrame({
        "open": closes,
        "high": [value + 0.05 for value in closes],
        "low": [value - 0.05 for value in closes],
        "close": closes,
        "volume": volumes,
    }, index=index)


def strategy(**overrides):
    config = {
        "timezone": "America/New_York",
        "fractional_shares": True,
        "min_order_value": 1,
        "ross_momentum": {
            "min_gap_pct": 0.02,
            "min_price": 1,
            "min_relative_volume": 1.2,
            "pullback_lookback": 4,
            "ema_length": 3,
            "entry_cutoff": "10:00",
            "rr_ratio": 2,
            "max_holding_bars": 6,
        },
    }
    config["ross_momentum"].update(overrides)
    risk = RiskManager({**config, "capital": 1000, "risk_pct": 0.02})
    return RossMomentumStrategy(config, risk, None)


def test_session_vwap_and_ema_use_current_bars_only():
    strat = strategy()
    bars = make_bars([10, 11, 10.5], [100, 200, 100])
    assert strat._session_vwap(bars).iloc[-1] == 10.625
    assert strat._ema(bars["close"]).iloc[-1] == 10.5


def test_long_first_pullback_reclaim_sets_pullback_low_stop():
    strat = strategy(min_gap_pct=0, min_impulse_pct=0, pullback_lookback=3)
    closes = [10, 10.3, 10.8, 11.2, 10.7, 11.4]
    bars = make_bars(closes, [100, 150, 400, 120, 80, 300])
    signal = strat.generate_signal("TEST", bars)
    assert signal["direction"] == "long"
    assert signal["stop"] == 10.25
    assert signal["target"] > signal["entry"]


def test_short_first_pullback_reclaim_sets_pullback_high_stop():
    strat = strategy(min_gap_pct=0, min_impulse_pct=0, pullback_lookback=3)
    closes = [10, 9.7, 9.2, 8.8, 9.3, 8.6]
    bars = make_bars(closes, [100, 150, 400, 120, 80, 300])
    signal = strat.generate_signal("TEST", bars)
    assert signal["direction"] == "short"
    assert signal["stop"] == 9.75
    assert signal["target"] < signal["entry"]


def test_cutoff_and_one_trade_per_symbol():
    strat = strategy(min_gap_pct=0, min_impulse_pct=0, pullback_lookback=3)
    bars = make_bars([10, 10.3, 10.8, 11.2, 10.7, 11.4], [100, 150, 400, 120, 80, 300])
    signal = strat.generate_signal("TEST", bars)
    strat.on_trade_entered("TEST", signal)
    assert strat.generate_signal("TEST", bars) is None
    late = bars.copy()
    late.index = late.index + pd.Timedelta(hours=1)
    assert strat.generate_signal("OTHER", late) is None


def test_exit_moves_stop_to_breakeven_and_honors_cutoff():
    strat = strategy(min_gap_pct=0, min_impulse_pct=0, pullback_lookback=3)
    bars = make_bars([10, 10.3, 10.8, 11.2, 10.7, 11.4], [100, 150, 400, 120, 80, 300])
    signal = strat.generate_signal("TEST", bars)
    strat.on_trade_entered("TEST", signal)
    profitable = make_bars([12.5], [500], start="2026-08-08 09:35")
    strat.check_exit("TEST", profitable, None)
    assert strat._active_trades["TEST"]["stop"] == signal["entry"]
    cutoff = make_bars([11.3], [500], start="2026-08-08 10:00")
    result = strat.check_exit("TEST", cutoff, None)
    assert result["reason"] == "entry_cutoff"


def test_entry_limit_allows_configured_reentries_and_resets_daily():
    strat = strategy(min_gap_pct=0, min_impulse_pct=0, pullback_lookback=3, max_entries_per_day=2)
    bars = make_bars([10, 10.3, 10.8, 11.2, 10.7, 11.4], [100, 150, 400, 120, 80, 300])
    signal = strat.generate_signal("TEST", bars)
    strat.on_trade_entered("TEST", signal)
    assert strat._entry_counts[("TEST", bars.index[-1].date())] == 1
    strat.on_trade_entered("TEST", signal)
    assert strat._entry_counts[("TEST", bars.index[-1].date())] == 2
    next_day = bars.copy()
    next_day.index = next_day.index + pd.Timedelta(days=1)
    next_signal = dict(signal, timestamp=next_day.index[-1].isoformat())
    strat.on_trade_entered("TEST", next_signal)
    assert strat._entry_counts[("TEST", next_day.index[-1].date())] == 1
