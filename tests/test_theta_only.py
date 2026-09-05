import json

import pandas as pd

from src.risk import RiskManager
from src.theta_only import PRESETS, ThetaOnlyStrategy


class Journal:
    def log_trade(self, trade):
        pass


def config(preset="balanced"):
    return {"capital": 3000, "theta_aggressiveness": preset, "theta_farming": {"enabled": True}}


def day(move=0.02, date="2026-08-01"):
    index = pd.date_range(f"{date} 09:30", periods=2, freq="5min", tz="America/New_York")
    return pd.DataFrame({"close": [100, 100 * (1 + move)]}, index=index)


def test_presets_have_distinct_risk_and_dte_ranges():
    assert PRESETS["conservative"]["max_risk_per_trade_pct"] < PRESETS["balanced"]["max_risk_per_trade_pct"] < PRESETS["aggressive"]["max_risk_per_trade_pct"]
    assert PRESETS["conservative"]["min_days_to_expiry"] < PRESETS["balanced"]["min_days_to_expiry"] < PRESETS["aggressive"]["min_days_to_expiry"]
    assert PRESETS["conservative"]["max_days_to_expiry"] < PRESETS["aggressive"]["max_days_to_expiry"]


def test_scanner_selection_and_fixed_fallback(tmp_path):
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"actionable_symbols": ["QQQ", "SPY"]}))
    strategy = ThetaOnlyStrategy(config(), RiskManager(config()), Journal())
    assert strategy.symbols_for_run(["SPY", "AAPL"], scan) == ["SPY"]
    assert strategy.selection_mode == "scanner"
    missing = ThetaOnlyStrategy(config(), RiskManager(config()), Journal())
    assert missing.symbols_for_run(["SPY"], tmp_path / "missing.json") == ["SPY"]
    assert missing.selection_mode == "fixed_fallback"


def test_ambiguous_direction_is_skipped():
    strategy = ThetaOnlyStrategy(config(), RiskManager(config()), Journal())
    assert strategy.generate_trade("SPY", day(move=0.001)) is None


def test_one_spread_per_ticker_per_day_and_realistic_loss_bound():
    strategy = ThetaOnlyStrategy(config(), RiskManager(config()), Journal())
    first = strategy.generate_trade("SPY", day())
    assert first is not None
    assert first["trade_type"] == "theta_spread"
    assert first["pnl"] >= -30
    assert strategy.generate_trade("SPY", day(date="2026-08-01")) is None
    assert strategy.generate_trade("SPY", day(date="2026-08-02")) is not None
