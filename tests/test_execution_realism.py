import pandas as pd

from src.execution_realism import finalize_trade, valid_bar


def test_invalid_zero_volume_bar_cannot_fill():
    bar = pd.Series({"open": 10, "high": 11, "low": 9, "close": 10, "volume": 0})
    assert not valid_bar(bar)


def test_execution_cost_is_reported_and_subtracted():
    result = finalize_trade(
        {"entry": 10, "exit_price": 11, "qty": 10, "pnl": 10},
        {"execution_realism": {"slippage_bps": 10, "spread_bps": 10}},
    )
    assert result["gross_pnl"] == 10
    assert result["execution_cost"] == 0.42
    assert result["pnl"] == 9.58
    assert result["net_pnl"] == 9.58
