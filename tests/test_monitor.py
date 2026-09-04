#!/usr/bin/env python3
"""Tests for src/monitor.py — four-layer monitoring architecture."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src.monitor import (
    check_technical,
    check_performance,
    check_behavior,
    check_business,
    run_monitor,
)


def _market_hour_timestamps(now, count, spacing_min=30):
    """Generate `count` timestamps within market hours (09:30-16:00 ET) ending near `now`.

    Returns ISO-format strings in UTC. Wraps to prior market days when the
    current day's session is exhausted.
    """
    et_hour = now.hour - 4  # EDT approximation

    # Start from the most recent market-hour slot
    if et_hour < 9 or (et_hour == 9 and now.minute < 30):
        base = now.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=1)
    elif et_hour >= 16:
        base = now.replace(hour=16, minute=0, second=0, microsecond=0)
    else:
        base = now

    timestamps = []
    current = base
    while len(timestamps) < count:
        ts_et_hour = current.hour - 4
        if ts_et_hour >= 9 and not (ts_et_hour == 9 and current.minute < 30):
            timestamps.append(current.isoformat())
        current = current - timedelta(minutes=spacing_min)
        # When we fall before market open, jump back to previous day's close
        ts_et_hour = current.hour - 4
        if ts_et_hour < 9 or (ts_et_hour == 9 and current.minute < 30):
            current = current.replace(hour=16, minute=0, second=0, microsecond=0)

    return timestamps[:count]


@pytest.fixture
def journal_file(tmp_path):
    jp = tmp_path / "trade_journal.json"
    now = datetime.now(timezone.utc)
    timestamps = _market_hour_timestamps(now, 10, spacing_min=30)
    trades = []
    for i, ts in enumerate(timestamps):
        trades.append(json.dumps({
            "timestamp": ts,
            "symbol": "SPY",
            "direction": "long",
            "qty": 1,
            "entry_price": 100.0,
            "exit_price": 102.0 if i % 2 == 0 else 99.0,
            "pnl": 2.0 if i % 2 == 0 else -1.0,
            "reason": "target" if i % 2 == 0 else "stop",
        }))
    jp.write_text("\n".join(trades) + "\n")
    return str(jp)


@pytest.fixture
def config_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump({
        "capital": 10000,
        "symbols": ["SPY", "QQQ", "AAPL"],
        "max_risk_dollars": 200,
    }))
    return str(cfg)


def test_check_technical_bot_alive(journal_file):
    # Journal modified now -> bot alive
    layer = check_technical({}, journal_path=journal_file)
    assert layer.bot_alive is True
    assert layer.last_heartbeat != ""


def test_check_technical_bot_down(tmp_path):
    # Old journal -> bot not alive
    jp = tmp_path / "old_journal.json"
    jp.write_text(json.dumps({
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "symbol": "SPY", "pnl": 0,
    }) + "\n")
    # Set mtime to 1 hour ago
    old_time = time.time() - 3600
    os.utime(str(jp), (old_time, old_time))
    layer = check_technical({}, journal_path=str(jp))
    assert layer.bot_alive is False


def test_check_technical_no_journal(tmp_path):
    layer = check_technical({}, journal_path=str(tmp_path / "nonexistent.json"))
    assert layer.bot_alive is False


def test_check_performance_basic(journal_file):
    layer = check_performance({}, journal_path=journal_file, lookback_days=2)
    assert layer.total_trades == 10
    assert layer.win_rate == 50.0
    assert layer.net_pnl == 5.0  # 5 wins * 2 + 5 losses * -1


def test_check_performance_no_journal(tmp_path):
    layer = check_performance({}, journal_path=str(tmp_path / "nope.json"))
    assert layer.total_trades == 0
    assert layer.errors


def test_check_behavior_basic(journal_file):
    layer = check_behavior({}, journal_path=journal_file, lookback_days=2)
    assert layer.total_trades == 10
    assert layer.after_hours_trades == 0


def test_check_business_basic(journal_file):
    config = {"capital": 10000, "max_risk_dollars": 200}
    layer = check_business(config, journal_path=journal_file, lookback_days=2)
    assert layer.net_pnl == 5.0
    assert layer.target_monthly_pnl == 1000.0


def test_run_monitor_e2e(config_file, journal_file):
    snap = run_monitor(config_file, journal_file, lookback_days=1)
    assert snap.generated_at != ""
    assert snap.overall_status in {"ok", "warning", "degraded", "down"}
    assert isinstance(snap.technical, dict)
    assert isinstance(snap.performance, dict)
    assert isinstance(snap.behavior, dict)
    assert isinstance(snap.business, dict)
    assert isinstance(snap.alerts, list)


def test_run_monitor_no_journal(config_file, tmp_path):
    snap = run_monitor(config_file, str(tmp_path / "missing.json"))
    assert snap.overall_status in {"down", "degraded", "warning"}


def test_performance_win_rate_warning():
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        trades = []
        now = datetime.now(timezone.utc)
        for i in range(20):
            trades.append(json.dumps({
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "symbol": "SPY",
                "pnl": -1.0 if i < 15 else 5.0,  # 75% loss
            }))
        f.write("\n".join(trades) + "\n")
        jp = f.name
    try:
        layer = check_performance({}, journal_path=jp, lookback_days=1)
        assert layer.win_rate == 25.0
        assert layer.status() == "warning"
    finally:
        os.unlink(jp)


def test_behavior_after_hours():
    import tempfile
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    import pytz
    et = pytz.timezone("US/Eastern")
    now_et = datetime.now(et)
    # 03:00 ET two days ago: guaranteed after-hours and inside a 2-day lookback
    ts = (now_et - timedelta(days=2)).replace(hour=3, minute=0, second=0, microsecond=0)
    ts = ts.astimezone(ZoneInfo("UTC")).isoformat()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        trades = []
        trades.append(json.dumps({
            "timestamp": ts,
            "symbol": "SPY",
            "pnl": 1.0,
        }))
        f.write("\n".join(trades) + "\n")
        jp = f.name
    try:
        layer = check_behavior({}, journal_path=jp, lookback_days=3)
        assert layer.after_hours_trades == 1
        assert layer.status() == "warning"
    finally:
        os.unlink(jp)


def test_business_risk_budget(journal_file):
    config = {"capital": 1000, "max_risk_dollars": 50}
    layer = check_business(config, journal_path=journal_file, lookback_days=2)
    # 5 losses * $50 = $250 risked out of $1000 = 25%
    assert layer.risk_budget_used_pct == 25.0


def test_technical_data_feed_status(journal_file, monkeypatch):
    # Force yfinance provider (no Alpaca keys)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    layer = check_technical({}, journal_path=journal_file)
    assert layer.data_feed == "yfinance"
    # API may or may not be reachable in test env; just check fields exist
    assert isinstance(layer.api_reachable, bool)
    assert isinstance(layer.data_feed_latency_ms, float)
