#!/usr/bin/env python3
import json
import os
import re
import subprocess
import threading
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from src.robinhood_readonly import RobinhoodReadOnly
from src.monitor import run_monitor

JOBS = {}
LOCK = threading.Lock()
ROBINHOOD = RobinhoodReadOnly()
MONITOR_CONFIG_PATH = ROOT / "config.yaml"
STRATEGIES = {"london", "ross", "sneaky", "ha_scalp", "auction_flow_proxy", "vwap_liquidity_proxy", "t3_range_filter", "reversal_zone_confirmation", "ema_cci_macd", "ema9_continuation", "ema20_stoch_pullback", "opening_drive_fade", "orb_fvg", "trailing_stop_ladder", "theta_only", "eps_line_put_selling"}
TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def validate_request(payload):
    if payload.get("strategy") not in STRATEGIES:
        raise ValueError("Choose a supported strategy.")
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 13:
        raise ValueError("Choose between 1 and 13 symbols.")
    symbols = [str(symbol).upper().strip() for symbol in symbols]
    if any(not TICKER.fullmatch(symbol) for symbol in symbols):
        raise ValueError("Symbols must use ticker format.")
    start = payload.get("start")
    end = payload.get("end")
    try:
        start_day = date.fromisoformat(start)
        end_day = date.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValueError("Dates must use YYYY-MM-DD format.")
    if end_day < start_day:
        raise ValueError("End date must be on or after start date.")
    capital = float(payload.get("capital", 300))
    if not 1 <= capital <= 1_000_000:
        raise ValueError("Capital must be between $1 and $1,000,000.")
    return {**payload, "symbols": symbols, "capital": capital, "start": start, "end": end}


def build_backtest_args(payload):
    args = ["python3", "backtest.py", "--json", "--strategy", payload["strategy"], "--provider", payload.get("provider", "auto"), "--symbols", *payload["symbols"], "--start", payload["start"], "--end", payload["end"], "--capital", str(payload["capital"])]
    args += ["--interval", payload.get("interval", "5m"), "--theta", "true" if payload.get("theta", False) else "false"]
    for key, flag in (("breakout_strength", "--breakout-strength"), ("max_bars", "--max-bars"), ("rr_ratio", "--rr-ratio"), ("max_entries_per_day", "--max-entries-per-day"), ("theta_aggressiveness", "--theta-aggressiveness")):
        if payload.get(key) not in (None, ""):
            args += [flag, str(payload[key])]
    params = payload.get("strategy_params", {})
    if params:
        args += ["--strategy-params", json.dumps(params, separators=(",", ":"))]
    return args


def run_job(job_id, payload):
    try:
        process = subprocess.run(build_backtest_args(payload), cwd=ROOT, text=True, capture_output=True, timeout=900)
        if process.returncode:
            raise RuntimeError(process.stderr[-2000:] or "Backtest failed.")
        result = json.loads(process.stdout.strip().splitlines()[-1])
        with LOCK:
            JOBS[job_id] = {"job_id": job_id, "status": "complete", "result": result}
    except Exception as exc:
        with LOCK:
            JOBS[job_id] = {"job_id": job_id, "status": "error", "error": str(exc)}


def _monitor_snapshot():
    import yaml
    cfg = {}
    if MONITOR_CONFIG_PATH.exists():
        with open(MONITOR_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
    journal_path = cfg.get("journal_path", "trade_journal.json")
    snap = run_monitor(str(MONITOR_CONFIG_PATH), journal_path)
    return {
        "generated_at": snap.generated_at,
        "overall_status": snap.overall_status,
        "technical": snap.technical,
        "performance": snap.performance,
        "behavior": snap.behavior,
        "business": snap.business,
        "alerts": snap.alerts,
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, body):
        encoded = json.dumps(body, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json(200, {"status": "ok"})
        if path == "/api/monitor":
            try:
                return self.send_json(200, _monitor_snapshot())
            except Exception as exc:
                return self.send_json(500, {"error": str(exc)})
        if path == "/api/robinhood/status":
            result = ROBINHOOD.snapshot()
            return self.send_json(200 if result["status"] != "error" else 502, result)
        if path.startswith("/api/backtests/"):
            job_id = path.rsplit("/", 1)[-1]
            with LOCK:
                job = JOBS.get(job_id)
            return self.send_json(200 if job else 404, job or {"error": "Job not found."})
        self.send_json(404, {"error": "Not found."})

    def do_POST(self):
        if urlparse(self.path).path != "/api/backtests":
            return self.send_json(404, {"error": "Not found."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = validate_request(json.loads(self.rfile.read(length)))
            with LOCK:
                if any(job["status"] == "running" for job in JOBS.values()):
                    return self.send_json(409, {"error": "Another backtest is already running."})
                job_id = uuid.uuid4().hex
                JOBS[job_id] = {"job_id": job_id, "status": "running"}
            threading.Thread(target=run_job, args=(job_id, payload), daemon=True).start()
            self.send_json(202, {"job_id": job_id, "status": "running"})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
