import pandas as pd

from src.reversal_zone_confirmation import ReversalZoneConfirmationStrategy


def test_reversal_zone_strategy_is_research_only_shape():
    cfg = {"timezone": "America/New_York", "capital": 1000, "risk_pct": .02, "fractional_shares": True, "reversal_zone_confirmation": {}}
    strategy = ReversalZoneConfirmationStrategy(cfg, type("Risk", (), {"calculate_qty": lambda *_args, **_kwargs: 1})(), None)
    bars = pd.DataFrame({"open": [100] * 25, "high": [101] * 25, "low": [99] * 25, "close": [100] * 25, "volume": [1000] * 25}, index=pd.date_range("2026-08-17 13:35", periods=25, freq="min", tz="UTC"))
    assert strategy.generate_signal("SPY", bars) is None
    assert strategy.session_start == pd.Timestamp("09:35").time()
