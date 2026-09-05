"""Backtest engine — runs one strategy variant over historical data.

Handles config dispatch for each strategy class so that section-keyed
strategies get their params merged into the right sub-dict.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data import DataFeed
from src.risk import RiskManager
from src.journal import TradeJournal
from src.execution_realism import finalize_trade

log = logging.getLogger("engine")


@dataclass
class ClosedTrade:
    symbol: str
    direction: str
    entry: float
    exit_price: float
    qty: float
    pnl: float
    reason: str
    entry_time: str
    exit_time: str
    bars_held: int


def _make_config(base_config: dict, section_key: str | None, params: dict) -> dict:
    """Build a config dict for a specific strategy variant.

    - section_key=None: params merged at top level (London Breakout, Ross)
    - section_key="x": params merged into base_config["x"] sub-dict
    """
    cfg = copy.deepcopy(base_config)
    name = params.pop("name", "unknown")
    if section_key is None:
        cfg.update(params)
    else:
        cfg.setdefault(section_key, {}).update(params)
    params["name"] = name  # restore for tagging
    return cfg


def _summarize(trades: list[ClosedTrade], start_date: str, end_date: str,
               symbols: list, initial_capital: float, strategy_name: str,
               params: dict) -> dict:
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    total_pnl = round(sum(t.pnl for t in trades), 2)
    gross_wins = sum(t.pnl for t in wins)
    gross_losses = sum(abs(t.pnl) for t in losses)
    return {
        "strategy": strategy_name,
        "params": {k: v for k, v in params.items() if k not in {"backtest_interval", "name"}},
        "start_date": start_date,
        "end_date": end_date,
        "symbols": symbols,
        "initial_capital": initial_capital,
        "final_capital": round(initial_capital + total_pnl, 2),
        "total_pnl": total_pnl,
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0,
        "profit_factor": round(gross_wins / gross_losses, 2) if gross_losses else None,
        "avg_win": round(float(np.mean([t.pnl for t in wins])), 2) if wins else 0,
        "avg_loss": round(float(np.mean([abs(t.pnl) for t in losses])), 2) if losses else 0,
        "max_pnl": round(max((t.pnl for t in trades), default=0), 2),
        "min_pnl": round(min((t.pnl for t in trades), default=0), 2),
        "avg_bars_held": round(float(np.mean([t.bars_held for t in trades])), 1) if trades else 0,
    }


def run_single(base_config: dict, strategy_cls, section_key: str | None,
               params: dict, symbols: list, start_date: str, end_date: str,
               provider: str = "auto", data_dir: str | None = None) -> dict:
    """Run one strategy variant. Returns summary dict."""
    cfg = _make_config(base_config, section_key, params)
    name = params.get("name", "unknown")

    feed = DataFeed(cfg.get("timezone", "America/New_York"), provider=provider)
    risk = RiskManager(cfg)
    journal = TradeJournal("/tmp/engine_journal.jsonl")
    strat = strategy_cls(cfg, risk, journal)

    interval = params.get("backtest_interval", cfg.get("bar_interval", "5m"))
    all_trades: list[ClosedTrade] = []

    for symbol in symbols:
        try:
            cached = None
            if data_dir:
                from pathlib import Path
                candidate = Path(data_dir) / f"{symbol}_{start_date}_{end_date}.pkl"
                if candidate.exists():
                    cached = pd.read_pickle(candidate)
            df = cached if cached is not None else feed.get_bars(
                symbol, interval=interval, start=start_date, end=end_date
            )
        except Exception as e:
            log.warning("  %s download failed: %s", symbol, e)
            continue
        if df.empty:
            continue

        if df.index.tz is None:
            df.index = df.index.tz_localize(cfg.get("timezone", "America/New_York"))
        else:
            df.index = df.index.tz_convert(cfg.get("timezone", "America/New_York"))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]

        # London breakout uses box + entry window; others use session_start/end
        if hasattr(strat, 'build_london_box'):
            use_box = True
            session_start = strat.ny_start
            session_end = strat.ny_end
        else:
            use_box = False
            session_start = getattr(strat, 'session_start', None)
            session_end = getattr(strat, 'session_end', None)

        for day in df.index.normalize().unique():
            day_data = df[df.index.normalize() == day].sort_index()
            if len(day_data) < 8:
                continue

            if use_box:
                box = strat.build_london_box(day_data)
                if box is None:
                    continue
                box_high, box_low = box
                ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
                ny_data = day_data[ny_mask]
            else:
                box_high = box_low = None
                if session_start and session_end:
                    s = pd.Timestamp(session_start).time()
                    e = pd.Timestamp(session_end).time()
                    ny_mask = (day_data.index.time >= s) & (day_data.index.time < e)
                    ny_data = day_data[ny_mask]
                else:
                    ny_data = day_data

            if ny_data.empty:
                continue

            for i in range(1, len(ny_data)):
                bars_slice = ny_data.iloc[: i + 1]
                ctx = (box_high, box_low) if use_box else None

                # Check exit first
                if symbol in strat._active_trades:
                    exit_result = strat.check_exit(symbol, bars_slice, None)
                    if exit_result:
                        exit_result = finalize_trade(exit_result, cfg)
                        risk.update_cash(-exit_result.get("execution_cost", 0))
                        all_trades.append(ClosedTrade(
                            symbol=exit_result["symbol"],
                            direction=exit_result["direction"],
                            entry=exit_result["entry"],
                            exit_price=exit_result.get("exit_price", 0),
                            qty=exit_result.get("qty", 0),
                            pnl=exit_result["pnl"],
                            reason=exit_result.get("reason", "exit"),
                            entry_time=str(exit_result.get("entry_time", "")),
                            exit_time=str(exit_result.get("exit_time", "")),
                            bars_held=exit_result.get("bars_held", 0),
                        ))

                # Then entry
                if symbol not in strat._active_trades:
                    signal = strat.generate_signal(symbol, bars_slice, ctx)
                    if signal:
                        strat.on_trade_entered(symbol, signal)

            # Force-close at EOD
            if symbol in strat._active_trades:
                last = ny_data.iloc[-1]
                trade = strat._active_trades[symbol]
                direction = trade["direction"]
                close = float(last["close"])
                entry = trade["entry"]
                qty = trade["qty"]
                pnl = (close - entry) * qty if direction == "long" else (entry - close) * qty
                exit_result = {
                    "symbol": symbol, "direction": direction, "entry": entry,
                    "exit_price": close, "qty": qty, "pnl": round(pnl, 2),
                    "reason": "eod_close", "bars_held": 0,
                }
                exit_result = finalize_trade(exit_result, cfg)
                risk.update_cash(exit_result["pnl"])
                journal.log_trade(exit_result)
                del strat._active_trades[symbol]
                all_trades.append(ClosedTrade(
                    symbol=symbol, direction=direction, entry=entry,
                    exit_price=close, qty=qty, pnl=exit_result["pnl"],
                    reason="eod_close", exit_time=str(last.name), bars_held=0,
                ))

    return _summarize(all_trades, start_date, end_date, symbols,
                      cfg.get("capital", 10000), name, params)
