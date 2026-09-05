import pandas as pd

from src.candle_narrative import CandleNarrativeStrategy


def _bars(closes, opens=None, highs=None, lows=None, volumes=None):
    n = len(closes)
    opens = opens or closes
    highs = highs or [max(o, c) * 1.001 for o, c in zip(opens, closes)]
    lows = lows or [min(o, c) * 0.999 for o, c in zip(opens, closes)]
    volumes = volumes or [1000] * n
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
                        index=pd.date_range("2026-08-17 13:35", periods=n, freq="min", tz="UTC"))


def _strategy():
    cfg = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True,
           "candle_narrative": {}}
    risk = type("Risk", (), {"calculate_qty": lambda *_a, **_k: 1})()
    return CandleNarrativeStrategy(cfg, risk, None)


def test_candle_narrative_rejects_short_history_and_defaults():
    strategy = _strategy()
    assert strategy.generate_signal("SPY", _bars([100] * 10)) is None
    assert strategy.session_start == pd.Timestamp("09:35").time()
    assert strategy.session_end == pd.Timestamp("12:30").time()


def test_candle_narrative_flat_market_no_signal():
    strategy = _strategy()
    bars = _bars([100.0] * 60)
    assert strategy.generate_signal("SPY", bars) is None
