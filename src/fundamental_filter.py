"""Deterministic fundamental-quality scoring for daily candidate selection."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path


def _number(record: dict, *names: str) -> float | None:
    for name in names:
        value = record.get(name)
        if value is None:
            continue
        try:
            value = float(value)
            if value == value:
                return value
        except (TypeError, ValueError):
            pass
    return None


def _points(value: float | None, low: float, high: float, weight: float, missing: list[str], field: str) -> float:
    if value is None:
        missing.append(field)
        return weight / 2
    return max(0.0, min(weight, (value - low) / (high - low) * weight))


def score_candidate(record: dict, config: dict | None = None) -> dict:
    config = config or {}
    missing: list[str] = []
    flags: list[str] = []
    quality = (
        _points(_number(record, "gross_margin"), 0.0, 0.8, 5, missing, "gross_margin")
        + _points(_number(record, "operating_margin"), -0.1, 0.4, 5, missing, "operating_margin")
        + _points(_number(record, "roe"), -0.1, 0.35, 5, missing, "roe")
        + _points(_number(record, "free_cashflow"), -1_000_000, 10_000_000, 5, missing, "free_cashflow")
    )
    valuation = (
        _points(_number(record, "pe_ratio", "forward_pe"), 5, 35, 7, missing, "pe_ratio")
        + _points(_number(record, "ev_ebitda"), 4, 30, 5, missing, "ev_ebitda")
        + _points(_number(record, "pb_ratio"), 0.5, 8, 3, missing, "pb_ratio")
    )
    growth = (
        _points(_number(record, "revenue_growth"), -0.2, 0.5, 8, missing, "revenue_growth")
        + _points(_number(record, "earnings_growth", "earnings_quarterly_growth"), -0.5, 1.0, 7, missing, "earnings_growth")
    )
    debt = _number(record, "debt_to_equity")
    if debt is not None and debt > config.get("high_debt_ratio", 250):
        flags.append("high_debt")
    financial_health = (
        _points(_number(record, "current_ratio"), 0.5, 3.0, 5, missing, "current_ratio")
        + _points(None if debt is None else -debt, -300, 0, 5, missing, "debt_to_equity")
        + _points(_number(record, "operating_cashflow"), -1_000_000, 10_000_000, 5, missing, "operating_cashflow")
    )
    dollar_volume = _number(record, "avg_dollar_volume", "avg_dollar_volume_30d")
    liquidity = _points(dollar_volume, 1_000_000, 100_000_000, 5, missing, "avg_dollar_volume")
    volatility = _number(record, "volatility_30d", "atr_pct")
    if volatility is not None and volatility > config.get("high_volatility", 1.0):
        flags.append("high_volatility")
    risk = liquidity + _points(None if volatility is None else -volatility, -2.0, 0.0, 5, missing, "volatility_30d")
    pe = _number(record, "pe_ratio", "forward_pe")
    if pe is not None and pe > config.get("high_pe", 50):
        flags.append("high_valuation")
    score = round(max(0.0, min(100.0, quality + valuation + growth + financial_health + risk)), 4)
    return {
        "symbol": str(record.get("symbol", record.get("ticker", ""))).upper(),
        "score": score,
        "components": {"quality": round(quality, 4), "valuation": round(valuation, 4), "growth": round(growth, 4), "financial_health": round(financial_health, 4), "liquidity_and_risk": round(risk, 4)},
        "risk_flags": sorted(set(flags)),
        "missing_fields": sorted(set(missing)),
        "eligible": score >= config.get("reject_below", 40),
    }


def score_candidates(records: list[dict], config: dict | None = None) -> list[dict]:
    return sorted((score_candidate(record, config) for record in records), key=lambda row: (-row["score"], row["symbol"]))


def _universe_hash(symbols: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(symbols)).encode()).hexdigest()[:16]


def write_fundamental_context(path: str | Path, results: list[dict], run_metadata: dict | None = None) -> dict:
    symbols = [row["symbol"] for row in results]
    payload = {"run_date": date.today().isoformat(), "scored_at": datetime.now().astimezone().isoformat(), "universe_hash": _universe_hash(symbols), "results": results, **(run_metadata or {})}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, target)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return payload


def load_fundamental_context(path: str | Path, symbols: list[str] | None = None, today: str | None = None) -> dict | None:
    try:
        payload = json.loads(Path(path).read_text())
        if payload.get("run_date") != (today or date.today().isoformat()):
            return None
        if symbols is not None and payload.get("universe_hash") != _universe_hash(symbols):
            return None
        return payload
    except (OSError, ValueError, TypeError):
        return None
