#!/usr/bin/env python3
"""Four-layer trading bot monitoring architecture.

Layer 1 — Technical: bot process alive, API reachable, last heartbeat, data feed latency
Layer 2 — Performance: win rate, profit factor, drawdown, trade count vs expectations
Layer 3 — Behavior: position overlap, order timing, signal frequency, slippage
Layer 4 — Business: P&L vs targets, theta decay, catalyst timing, risk budget
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

log = logging.getLogger("monitor")

# ---------------------------------------------------------------------------
# Layer 1 — Technical health
# ---------------------------------------------------------------------------

@dataclass
class TechnicalLayer:
    bot_alive: bool = False
    api_reachable: bool = False
    last_heartbeat: str = ""
    data_feed_latency_ms: float = -1.0
    data_feed: str = "unknown"
    errors: list[str] = field(default_factory=list)

    def status(self) -> str:
        if not self.bot_alive:
            return "down"
        if self.errors:
            return "degraded"
        return "ok"


def check_technical(config: dict, journal_path: str = "trade_journal.json") -> TechnicalLayer:
    layer = TechnicalLayer()
    now = datetime.now(timezone.utc)

    # Bot alive: journal file modified within last 15 minutes
    jp = Path(journal_path)
    if jp.exists():
        mtime = jp.stat().st_mtime
        layer.bot_alive = (time.time() - mtime) < 900
        layer.last_heartbeat = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    else:
        layer.bot_alive = False
        layer.last_heartbeat = ""

    # Data feed latency
    provider = _detect_provider(config)
    layer.data_feed = provider
    start = time.monotonic()
    try:
        if provider == "alpaca":
            _ping_alpaca()
        else:
            _ping_yfinance(config.get("symbols", ["SPY"])[0])
        layer.data_feed_latency_ms = round((time.monotonic() - start) * 1000, 1)
        layer.api_reachable = True
    except Exception as exc:
        layer.api_reachable = False
        layer.data_feed_latency_ms = -1.0
        layer.errors.append(f"data_feed: {exc}")

    # API reachable: check if the web API port is responding
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex(("127.0.0.1", 8787))
        if result != 0:
            layer.errors.append("web_api: port 8787 not responding")
    except Exception as exc:
        layer.errors.append(f"web_api: {exc}")
    finally:
        sock.close()

    return layer


def _detect_provider(config: dict) -> str:
    if os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"):
        return "alpaca"
    return "yfinance"


def _ping_alpaca() -> None:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    client = StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    )
    end = pd.Timestamp.now(tz="US/Eastern")
    start = end - pd.Timedelta(hours=1)
    req = StockBarsRequest(
        symbol_or_symbols="SPY",
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=start, end=end, feed="iex",
    )
    bars = client.get_stock_bars(req)
    if bars.df is None or bars.df.empty:
        raise RuntimeError("Alpaca returned empty bars")


def _ping_yfinance(symbol: str) -> None:
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="1d", interval="5m")
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned empty bars for {symbol}")


# ---------------------------------------------------------------------------
# Layer 2 — Performance
# ---------------------------------------------------------------------------

@dataclass
class PerformanceLayer:
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    net_pnl: float = 0.0
    gross_pnl: float = 0.0
    gross_loss: float = 0.0
    avg_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    trade_count_expected: int = 0
    trade_count_status: str = "unknown"
    errors: list[str] = field(default_factory=list)

    def status(self) -> str:
        if self.errors:
            return "degraded"
        if self.win_rate < 40 and self.total_trades > 10:
            return "warning"
        if self.max_drawdown_pct > 15.0:
            return "warning"
        return "ok"


def check_performance(
    config: dict,
    journal_path: str = "trade_journal.json",
    lookback_days: int = 30,
) -> PerformanceLayer:
    layer = PerformanceLayer()
    jp = Path(journal_path)
    if not jp.exists():
        layer.errors.append("journal: file not found")
        return layer

    trades = _load_trades(jp, lookback_days)
    if not trades:
        layer.errors.append("journal: no trades in lookback window")
        return layer

    layer.total_trades = len(trades)

    layer.total_trades = len(trades)
    pnls = [t.get("pnl", 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    layer.net_pnl = sum(pnls)
    layer.gross_pnl = sum(wins) if wins else 0
    layer.gross_loss = abs(sum(losses)) if losses else 0
    layer.win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    layer.profit_factor = layer.gross_pnl / layer.gross_loss if layer.gross_loss > 0 else 0.0
    layer.avg_trade = layer.net_pnl / len(pnls) if pnls else 0
    layer.avg_win = sum(wins) / len(wins) if wins else 0
    layer.avg_loss = sum(losses) / len(losses) if losses else 0

    # Max drawdown from cumulative P&L
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    capital = config.get("capital", 10000)
    layer.max_drawdown_pct = (max_dd / capital) * 100 if capital > 0 else 0

    # Trade count expectation: ~1 trade per symbol per day
    symbols = config.get("symbols", [])
    layer.trade_count_expected = len(symbols) * lookback_days
    if layer.total_trades < layer.trade_count_expected * 0.5:
        layer.trade_count_status = "below_expected"
    elif layer.total_trades > layer.trade_count_expected * 1.5:
        layer.trade_count_status = "above_expected"
    else:
        layer.trade_count_status = "on_track"

    return layer


def _load_trades(jp: Path, lookback_days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    trades = []
    with open(jp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                ts = t.get("timestamp", "")
                if ts:
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        trades.append(t)
            except (json.JSONDecodeError, ValueError):
                continue
    return trades


# ---------------------------------------------------------------------------
# Layer 3 — Behavior
# ---------------------------------------------------------------------------

@dataclass
class BehaviorLayer:
    position_overlap_count: int = 0
    avg_signal_interval_min: float = 0.0
    signal_frequency_status: str = "unknown"
    avg_slippage_bps: float = 0.0
    slippage_status: str = "unknown"
    after_hours_trades: int = 0
    total_trades: int = 0
    duplicate_signals: int = 0
    errors: list[str] = field(default_factory=list)

    def status(self) -> str:
        if self.after_hours_trades > 0:
            return "warning"
        if self.duplicate_signals > 5:
            return "warning"
        if self.avg_slippage_bps > 10:
            return "warning"
        return "ok"


def check_behavior(
    config: dict,
    journal_path: str = "trade_journal.json",
    lookback_days: int = 30,
) -> BehaviorLayer:
    layer = BehaviorLayer()
    jp = Path(journal_path)
    if not jp.exists():
        layer.errors.append("journal: file not found")
        return layer

    trades = _load_trades(jp, lookback_days)
    if not trades:
        layer.errors.append("journal: no trades in lookback window")
        return layer

    layer.total_trades = len(trades)


    # Position overlap: count trades within 5-minute windows
    timestamps = []
    for t in trades:
        ts = t.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamps.append(dt)
            except ValueError:
                continue

    timestamps.sort()
    overlap_count = 0
    for i in range(1, len(timestamps)):
        if (timestamps[i] - timestamps[i - 1]).total_seconds() < 300:
            overlap_count += 1
    layer.position_overlap_count = overlap_count

    # Signal frequency
    if len(timestamps) >= 2:
        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
            intervals.append(delta)
        layer.avg_signal_interval_min = round(statistics.mean(intervals), 1)

    # After-hours trades (before 09:30 or after 16:00 ET)
    import pytz
    et = pytz.timezone("US/Eastern")
    for dt in timestamps:
        dt_et = dt.astimezone(et)
        if dt_et.hour < 9 or (dt_et.hour == 9 and dt_et.minute < 30) or dt_et.hour >= 16:
            layer.after_hours_trades += 1

    # Duplicate signals: same symbol within 10 minutes
    symbol_times: dict[str, list[datetime]] = {}
    for t in trades:
        sym = t.get("symbol", "unknown")
        ts = t.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                symbol_times.setdefault(sym, []).append(dt)
            except ValueError:
                continue

    dupes = 0
    for sym, times in symbol_times.items():
        times.sort()
        for i in range(1, len(times)):
            if (times[i] - times[i - 1]).total_seconds() < 600:
                dupes += 1
    layer.duplicate_signals = dupes

    # Slippage estimate: compare entry_price vs expected (if available)
    slippages = []
    for t in trades:
        entry = t.get("entry_price")
        expected = t.get("expected_entry")
        if entry and expected and expected > 0:
            slip = abs(entry - expected) / expected * 10000  # bps
            slippages.append(slip)
    if slippages:
        layer.avg_slippage_bps = round(statistics.mean(slippages), 1)

    # Status heuristics
    if layer.avg_signal_interval_min < 5:
        layer.signal_frequency_status = "high"
    elif layer.avg_signal_interval_min > 120:
        layer.signal_frequency_status = "low"
    else:
        layer.signal_frequency_status = "normal"

    if layer.avg_slippage_bps > 10:
        layer.slippage_status = "high"
    elif layer.avg_slippage_bps > 5:
        layer.slippage_status = "elevated"
    else:
        layer.slippage_status = "normal"

    return layer


# ---------------------------------------------------------------------------
# Layer 4 — Business
# ---------------------------------------------------------------------------

@dataclass
class BusinessLayer:
    net_pnl: float = 0.0
    target_monthly_pnl: float = 0.0
    pnl_vs_target_pct: float = 0.0
    theta_pnl: float = 0.0
    directional_pnl: float = 0.0
    theta_pct_of_total: float = 0.0
    risk_budget_used_pct: float = 0.0
    risk_budget_status: str = "unknown"
    catalyst_trades: int = 0
    catalyst_win_rate: float = 0.0
    errors: list[str] = field(default_factory=list)

    def status(self) -> str:
        if self.pnl_vs_target_pct < -50:
            return "warning"
        if self.risk_budget_used_pct > 80:
            return "warning"
        return "ok"


def check_business(
    config: dict,
    journal_path: str = "trade_journal.json",
    lookback_days: int = 30,
) -> BusinessLayer:
    layer = BusinessLayer()
    jp = Path(journal_path)
    if not jp.exists():
        layer.errors.append("journal: file not found")
        return layer

    trades = _load_trades(jp, lookback_days)
    if not trades:
        layer.errors.append("journal: no trades in lookback window")
        return layer

    layer.total_trades = len(trades)
    pnls = [t.get("pnl", 0) for t in trades]
    layer.net_pnl = sum(pnls)

    # Theta vs directional split
    theta_pnls = [t.get("pnl", 0) for t in trades if t.get("trade_type") == "theta_spread"]
    directional_pnls = [t.get("pnl", 0) for t in trades if t.get("trade_type") != "theta_spread"]
    layer.theta_pnl = sum(theta_pnls) if theta_pnls else 0
    layer.directional_pnl = sum(directional_pnls) if directional_pnls else 0
    if layer.net_pnl != 0:
        layer.theta_pct_of_total = (layer.theta_pnl / abs(layer.net_pnl)) * 100

    # Target: 10% monthly return on capital
    capital = config.get("capital", 10000)
    layer.target_monthly_pnl = capital * 0.10
    if layer.target_monthly_pnl > 0:
        layer.pnl_vs_target_pct = (layer.net_pnl / layer.target_monthly_pnl) * 100

    # Risk budget: max 2% per trade, 6% per day
    max_risk = config.get("max_risk_dollars", capital * 0.02)
    total_risked = sum(max_risk for t in trades if t.get("pnl", 0) < 0)
    if capital > 0:
        layer.risk_budget_used_pct = (total_risked / capital) * 100
    if layer.risk_budget_used_pct > 80:
        layer.risk_budget_status = "critical"
    elif layer.risk_budget_used_pct > 50:
        layer.risk_budget_status = "elevated"
    else:
        layer.risk_budget_status = "normal"

    # Catalyst trades: trades with catalyst tag (from daily universe scoring)
    catalyst_trades = [t for t in trades if t.get("catalyst_score", 0) > 0]
    layer.catalyst_trades = len(catalyst_trades)
    if catalyst_trades:
        wins = [t for t in catalyst_trades if t.get("pnl", 0) > 0]
        layer.catalyst_win_rate = len(wins) / len(catalyst_trades) * 100

    return layer


# ---------------------------------------------------------------------------
# Aggregate monitor
# ---------------------------------------------------------------------------

@dataclass
class MonitorSnapshot:
    generated_at: str = ""
    technical: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    behavior: dict = field(default_factory=dict)
    business: dict = field(default_factory=dict)
    overall_status: str = "unknown"
    alerts: list[str] = field(default_factory=list)


def run_monitor(
    config_path: str = "config.yaml",
    journal_path: str = "trade_journal.json",
    lookback_days: int = 30,
) -> MonitorSnapshot:
    snapshot = MonitorSnapshot()
    snapshot.generated_at = datetime.now(timezone.utc).isoformat()

    config = _load_config(config_path)

    tech = check_technical(config, journal_path)
    perf = check_performance(config, journal_path, lookback_days)
    beh = check_behavior(config, journal_path, lookback_days)
    biz = check_business(config, journal_path, lookback_days)

    snapshot.technical = {k: v for k, v in asdict(tech).items()}
    snapshot.performance = {k: v for k, v in asdict(perf).items()}
    snapshot.behavior = {k: v for k, v in asdict(beh).items()}
    snapshot.business = {k: v for k, v in asdict(biz).items()}

    # Overall status: worst of all layers
    statuses = [tech.status(), perf.status(), beh.status(), biz.status()]
    if "down" in statuses:
        snapshot.overall_status = "down"
    elif "warning" in statuses:
        snapshot.overall_status = "warning"
    elif "degraded" in statuses:
        snapshot.overall_status = "degraded"
    else:
        snapshot.overall_status = "ok"

    # Alerts
    if not tech.bot_alive:
        snapshot.alerts.append("BOT_DOWN: No journal activity in 15+ minutes")
    if not tech.api_reachable:
        snapshot.alerts.append("DATA_FEED_DOWN: Cannot reach market data API")
    if perf.win_rate < 40 and perf.total_trades > 10:
        snapshot.alerts.append(f"LOW_WIN_RATE: {perf.win_rate:.1f}% (below 40%)")
    if perf.max_drawdown_pct > 15:
        snapshot.alerts.append(f"HIGH_DRAWDOWN: {perf.max_drawdown_pct:.1f}% (above 15%)")
    if beh.after_hours_trades > 0:
        snapshot.alerts.append(f"AFTER_HOURS: {beh.after_hours_trades} trades outside market hours")
    if beh.duplicate_signals > 5:
        snapshot.alerts.append(f"DUPLICATE_SIGNALS: {beh.duplicate_signals} duplicate signals detected")
    if biz.pnl_vs_target_pct < -50:
        snapshot.alerts.append(f"BEHIND_TARGET: P&L {biz.pnl_vs_target_pct:.0f}% of monthly target")
    if biz.risk_budget_used_pct > 80:
        snapshot.alerts.append(f"RISK_BUDGET_CRITICAL: {biz.risk_budget_used_pct:.0f}% of risk budget used")

    return snapshot


def _load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    journal_path = sys.argv[2] if len(sys.argv) > 2 else "trade_journal.json"
    snapshot = run_monitor(config_path, journal_path)
    print(json.dumps(asdict(snapshot), indent=2, default=str))
