import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from web.api import build_backtest_args, validate_request


def base():
    return {"strategy": "london", "symbols": ["SPY"], "start": "2026-01-01", "end": "2026-01-31", "capital": 300}


def test_validation_normalizes_symbols():
    result = validate_request({**base(), "symbols": ["spy"]})
    assert result["symbols"] == ["SPY"]


def test_args_are_an_array_with_expected_flags():
    args = build_backtest_args(validate_request({**base(), "breakout_strength": 0.75}))
    assert args[:4] == ["python3", "backtest.py", "--json", "--strategy"]
    assert "--breakout-strength" in args


def test_invalid_range_is_rejected():
    try:
        validate_request({**base(), "start": "2026-02-01"})
    except ValueError as exc:
        assert "End date" in str(exc)
    else:
        raise AssertionError("expected invalid date range")


def test_theta_only_and_aggressiveness_are_forwarded():
    payload = validate_request({**base(), "strategy": "theta_only", "theta_aggressiveness": "aggressive"})
    args = build_backtest_args(payload)
    assert "theta_only" in args
    assert args[args.index("--theta-aggressiveness") + 1] == "aggressive"


def test_all_registered_strategies_are_supported():
    for strategy in ("london", "ross", "sneaky", "ha_scalp", "auction_flow_proxy", "vwap_liquidity_proxy", "t3_range_filter", "theta_only"):
        assert validate_request({**base(), "strategy": strategy})["strategy"] == strategy


def test_strategy_params_are_forwarded():
    args = build_backtest_args(validate_request({**base(), "strategy": "t3_range_filter", "strategy_params": {"t3_length": 12, "target_r": 3}}))
    assert "--strategy-params" in args
    assert '"t3_length":12' in args[args.index("--strategy-params") + 1]
