import pandas as pd

from src.ema_cci_macd import EmaCciMacdStrategy
from src.risk import RiskManager


def _frame(closes, lows=None, highs=None, volumes=None, start="2026-08-17 09:35", freq="5min"):
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz="America/New_York")
    lows = lows if lows is not None else [c * .999 for c in closes]
    highs = highs if highs is not None else [c * 1.001 for c in closes]
    volumes = volumes if volumes is not None else [1000] * len(closes)
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes}, index=idx)


def _strategy(**overrides):
    cfg = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "ema_cci_macd": overrides}
    return EmaCciMacdStrategy(cfg, RiskManager(cfg), None)


def test_defaults_are_fixed_and_research_only():
    strat = _strategy()
    assert (strat.ema_fast, strat.ema_slow) == (50, 110)
    assert strat.cci_length == 20 and (strat.macd_fast, strat.macd_slow, strat.macd_signal) == (12, 26, 9)
    assert strat.volume_multiplier == 1 and strat.rr_ratio == 2
    assert strat.session_start == pd.Timestamp("09:35").time() and strat.session_end == pd.Timestamp("15:45").time()


def test_flat_and_insufficient_data_produce_no_signal():
    strat = _strategy()
    flat = [100] * 300
    assert strat.generate_signal("SPY", _frame(flat)) is None
    assert strat.generate_signal("SPY", _frame(flat[:100])) is None


def test_uptrend_pullback_bounce_can_only_signal_long_with_valid_levels():
    strat = _strategy(max_bar_range_pct=.2)
    warmup = [100 + i * .04 for i in range(280)]
    pullback = [warmup[-1] - i * .06 for i in range(1, 7)]
    bounce = [pullback[-1] + .5]
    closes = warmup + pullback + bounce
    bars = len(closes)
    lows = [c * .998 for c in closes]
    lows[-4] = min(lows[-4], closes[-4] * .985)
    highs = [c * 1.002 for c in closes]
    highs[-1] = bounce[0] * 1.006
    frame = _frame(closes, lows=lows, highs=highs)
    signal = strat.generate_signal("TEST", frame)
    if signal:
        assert signal["direction"] == "long"
        assert signal["stop"] < signal["entry"] < signal["target"]
        assert signal["qty"] > 0


def test_downtrend_bounce_cannot_signal_long_against_trend():
    strat = _strategy(max_bar_range_pct=.2)
    downtrend = [200 - i * .05 for i in range(287)]
    frame = _frame(downtrend)
    signal = strat.generate_signal("TEST", frame)
    assert signal is None or signal["direction"] == "short"


def test_check_exit_respects_stop_target_and_time_limits():
    strat = _strategy()
    entry = 100.0
    trade = {"symbol": "TEST", "direction": "long", "entry": entry, "stop": 98.0, "target": 104.0, "qty": 10, "entry_bar_count": 0, "timestamp": "2026-08-17 09:35:00-04:00"}
    cash = {"cash": 1000.0}

    class Risk:
        def update_cash(self, pnl):
            cash["cash"] += pnl

    strat.risk = Risk()
    strat._active_trades["TEST"] = dict(trade)
    hit = _frame([101.5, 104.2], start="2026-08-17 09:40")
    result = strat.check_exit("TEST", hit, None)
    assert result["reason"] == "target_hit" and abs(result["pnl"] - 40.0) < 1e-6
    strat._active_trades["TEST"] = dict(trade)
    stopped = _frame([97.5], start="2026-08-17 09:40")
    assert strat.check_exit("TEST", stopped, None)["reason"] == "stop_loss"
