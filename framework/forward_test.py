#!/usr/bin/env python3
"""Forward-test runner — paper-trade top strategies with small capital.

Uses the same strategy classes but runs on live/latest data instead of
historical backtest windows. Tracks P&L, trades, and basic stats.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yaml

from src.data import DataFeed
from src.risk import RiskManager
from src.journal import TradeJournal
from src.execution_realism import finalize_trade, valid_bar

log = logging.getLogger("forward_test")


@dataclass
class ForwardResult:
    variant_name: str
    base_name: str
    params: dict
    start_time: str
    end_time: str
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    trades: list[dict] = field(default_factory=list)


class ForwardTester:
    """Paper-trade a strategy on live/latest available data."""

    def __init__(self, config: dict, provider: str = "auto"):
        self.config = config
        self.provider = provider

    def run(
        self,
        result: Any,  # BacktestResult
        symbols: list[str],
        days: int = 5,
        capital: float = 1000.0,
    ) -> ForwardResult:
        """Run forward-test for a given strategy variant."""
        from framework.base import StrategyRegistry

        strategy_cls = StrategyRegistry.get(result.base_name)
        if strategy_cls is None:
            raise ValueError(f"Strategy {result.base_name} not registered")

        # Merge params into config
        merged = {**self.config, **result.params}
        merged["capital"] = capital
        merged["max_risk_dollars"] = capital * merged.get("risk_pct", 0.02)

        feed = DataFeed(merged.get("timezone", "America/New_York"), provider=self.provider)
        risk = RiskManager(merged)
        journal = TradeJournal("/tmp/forward_test_journal.json")
        strat = strategy_cls(merged, risk, journal)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        fwd = ForwardResult(
            variant_name=result.variant_name,
            base_name=result.base_name,
            params=result.params,
            start_time=start_date,
            end_time=end_date,
        )

        log.info("Forward-testing %s from %s to %s with $%.2f", result.variant_name, start_date, end_date, capital)

        for symbol in symbols:
            try:
                df = feed.get_bars(symbol, interval=merged.get("bar_interval", "5m"), start=start_date, end=end_date)
            except Exception as exc:
                log.warning("  %s download failed: %s", symbol, exc)
                continue
            if df.empty:
                continue

            if df.index.tz is None:
                df.index = df.index.tz_localize(merged.get("timezone", "America/New_York"))
            else:
                df.index = df.index.tz_convert(merged.get("timezone", "America/New_York"))
            df.columns = [str(c).lower() for c in df.columns]

            for day in df.index.normalize().unique():
                day_data = df[df.index.normalize() == day].sort_index()
                if len(day_data) < 8:
                    continue

                session_start = getattr(strat, "session_start", None)
                session_end = getattr(strat, "session_end", None)
                if session_start is None:
                    session_start = pd.Timestamp("09:30").time()
                if session_end is None:
                    session_end = pd.Timestamp("12:00").time()
                ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
                ny_data = day_data[ny_mask]
                if ny_data.empty:
                    continue

                n = len(ny_data)
                for i in range(1, n):
                    bars_slice = ny_data.iloc[: i + 1]
                    if not valid_bar(bars_slice.iloc[-1]):
                        continue

                    if symbol in strat._active_trades:
                        exit_result = strat.check_exit(symbol, bars_slice, None)
                        if exit_result:
                            if merged.get("execution_realism", {}).get("enabled", True):
                                exit_result = finalize_trade(exit_result, merged)
                                risk.update_cash(-exit_result["execution_cost"])
                            fwd.trades.append(exit_result)

                    if symbol not in strat._active_trades:
                        signal = strat.generate_signal(symbol, bars_slice, context=None)
                        if signal:
                            strat.on_trade_entered(symbol, signal)

                if symbol in strat._active_trades:
                    last_bar = ny_data.iloc[-1]
                    trade = strat._active_trades[symbol]
                    direction = trade["direction"]
                    close = float(last_bar["close"])
                    entry = trade["entry"]
                    qty = trade["qty"]
                    if direction == "long":
                        pnl = (close - entry) * qty
                    else:
                        pnl = (entry - close) * qty
                    exit_result = {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": round(entry, 2),
                        "exit_price": round(close, 2),
                        "exit_time": None,
                        "qty": qty,
                        "pnl": round(pnl, 2),
                        "reason": "eod_close",
                    }
                    if merged.get("execution_realism", {}).get("enabled", True):
                        exit_result = finalize_trade(exit_result, merged)
                    risk.update_cash(exit_result["pnl"])
                    journal.log_trade(exit_result)
                    del strat._active_trades[symbol]
                    fwd.trades.append(exit_result)

        # Summarize
        wins = [t for t in fwd.trades if t.get("pnl", 0) > 0]
        losses = [t for t in fwd.trades if t.get("pnl", 0) < 0]
        fwd.total_trades = len(fwd.trades)
        fwd.win_rate = round(len(wins) / len(fwd.trades) * 100, 2) if fwd.trades else 0.0
        gross_wins = sum(float(t.get("pnl", 0)) for t in wins)
        gross_losses = sum(abs(float(t.get("pnl", 0))) for t in losses)
        fwd.profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else 0.0
        fwd.total_pnl = round(sum(float(t.get("pnl", 0)) for t in fwd.trades), 2)

        log.info(
            "Forward-test %s: trades=%d WR=%.1f%% PF=%.2f PnL=$%.2f",
            fwd.variant_name, fwd.total_trades, fwd.win_rate, fwd.profit_factor, fwd.total_pnl,
        )
        return fwd
