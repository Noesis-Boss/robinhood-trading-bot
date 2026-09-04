import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.backtest_runner import summarize_trades


def test_empty_summary_is_json_safe():
    result = summarize_trades([], "2026-01-01", "2026-01-31", ["SPY"], 300)
    assert result["trade_count"] == 0
    assert result["final_capital"] == 300
    assert result["profit_factor"] is None


def test_summary_calculates_metrics_and_preserves_trades():
    trades = [
        {"symbol": "SPY", "pnl": 20, "reason": "target_hit"},
        {"symbol": "QQQ", "pnl": -10, "reason": "stop_loss"},
    ]
    result = summarize_trades(trades, "2026-01-01", "2026-01-31", ["SPY", "QQQ"], 300)
    assert result["total_pnl"] == 10
    assert result["final_capital"] == 310
    assert result["win_rate"] == 50
    assert result["profit_factor"] == 2
    assert result["reason_counts"] == {"target_hit": 1, "stop_loss": 1}
    assert result["trades"] == trades


def test_summary_reports_gross_and_execution_costs():
    result = summarize_trades([
        {"pnl": 9, "gross_pnl": 10, "execution_cost": 1, "reason": "target_hit"},
    ], "2026-01-01", "2026-01-31", ["SPY"], 300)
    assert result["gross_pnl"] == 10
    assert result["execution_cost"] == 1
    assert result["net_pnl"] == 9
