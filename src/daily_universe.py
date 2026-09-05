"""Daily premarket universe discovery for live paper trading."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def filter_asset(asset: dict) -> tuple[bool, str]:
    if asset.get("class") not in (None, "us_equity"):
        return False, "not_us_equity"
    if asset.get("status") not in (None, "active"):
        return False, "inactive"
    if asset.get("tradable") is False:
        return False, "not_tradable"
    exchange = str(asset.get("exchange", "")).upper()
    if exchange in {"OTC", "OTCBB", "PINK"}:
        return False, "otc"
    return True, ""


def passes_filters(m: dict, cfg: dict) -> tuple[bool, list[str]]:
    reasons = []
    checks = (
        (m.get("price", 0) >= cfg.get("min_price", 3), "price_low"),
        (m.get("price", 0) <= cfg.get("max_price", 100), "price_high"),
        (m.get("avg_dollar_volume", 0) >= cfg.get("min_avg_dollar_volume", 20_000_000), "avg_dollar_volume"),
        (m.get("premarket_dollar_volume", 0) >= cfg.get("min_premarket_dollar_volume", 500_000), "premarket_dollar_volume"),
        (cfg.get("min_gap_pct", 0.02) <= m.get("gap_pct", -1) <= cfg.get("max_gap_pct", 0.08), "gap"),
        (m.get("relative_volume", 0) >= cfg.get("min_relative_volume", 1.5), "relative_volume"),
        (m.get("atr_pct", 0) > 0, "atr"),
    )
    for passed, reason in checks:
        if not passed:
            reasons.append(reason)
    spread = m.get("spread_pct")
    if spread is not None and spread > cfg.get("max_spread_pct", 0.005):
        reasons.append("spread")
    return not reasons, reasons


def hard_rejections(m: dict, cfg: dict) -> list[str]:
    reasons = []
    if m.get("price", 0) < cfg.get("min_price", 3) or m.get("price", 0) > cfg.get("max_price", 100):
        reasons.append("price")
    if m.get("avg_dollar_volume", 0) < cfg.get("min_avg_dollar_volume", 20_000_000):
        reasons.append("avg_dollar_volume")
    if m.get("atr_pct", 0) <= 0:
        reasons.append("atr")
    if m.get("spread_pct") is not None and m["spread_pct"] > cfg.get("max_spread_pct", 0.005):
        reasons.append("spread")
    return reasons


def score_metrics(m: dict, cfg: dict | None = None) -> float:
    cfg = cfg or {}
    def norm(value, low, high):
        return max(0.0, min(1.0, (value - low) / (high - low)))
    relvol = norm(m.get("relative_volume", 0), cfg.get("min_relative_volume", 1.5), 5)
    premarket = norm(m.get("premarket_dollar_volume", 0), 500_000, 20_000_000)
    gain = norm(m.get("gap_pct", 0), cfg.get("min_gap_pct", 0.02), cfg.get("preferred_gap_pct", 0.10))
    atr = norm(m.get("atr_pct", 0), 0.01, 0.12)
    spread = 1 - min(1, m.get("spread_pct", 0.005) / 0.005)
    float_shares = m.get("float_shares")
    float_score = 0.5 if float_shares is None else 1 - min(1, float_shares / cfg.get("preferred_max_float", 20_000_000))
    catalyst = 1.0 if m.get("catalyst") else 0.0
    return round(100 * (0.25 * gain + 0.20 * relvol + 0.15 * premarket + 0.15 * float_score + 0.15 * catalyst + 0.10 * spread), 4)


def scan_candidates(assets: list[dict], metrics: dict[str, dict], cfg: dict) -> dict:
    rows, watchlist, rejected = [], [], {}
    for asset in assets:
        symbol = asset.get("symbol", "").upper()
        ok, reason = filter_asset(asset)
        if not ok:
            rejected[symbol] = [reason]
            continue
        m = metrics.get(symbol)
        if not m:
            rejected[symbol] = ["missing_metrics"]
            continue
        ok, reasons = passes_filters(m, cfg)
        hard = hard_rejections(m, cfg)
        row = {"symbol": symbol, "score": score_metrics(m, cfg), "metrics": m, "failed_filters": reasons}
        if ok:
            rows.append(row)
        elif not hard and len(reasons) <= cfg.get("fallback_max_failures", 2):
            row["selection_type"] = "watchlist"
            watchlist.append(row)
        else:
            rejected[symbol] = reasons
    rows.sort(key=lambda row: (-row["score"], row["symbol"]))
    watchlist.sort(key=lambda row: (-row["score"], row["symbol"]))
    selected = rows[: cfg.get("max_symbols", 10)]
    actionable = selected or watchlist[: cfg.get("max_symbols", 10)]
    for row in selected:
        row["selection_type"] = "qualified"
    return {"selected": selected, "watchlist": watchlist, "actionable": actionable, "rejected": rejected}


def write_scan(result: dict, output_path: str | Path, static_symbols: list[str], scan_date: str | None = None) -> dict:
    payload = {"scan_date": scan_date or date.today().isoformat(), "scanned_at": datetime.now().astimezone().isoformat(), **result}
    selected = [row["symbol"] for row in payload.get("actionable", payload["selected"])]
    payload["qualified_symbols"] = [row["symbol"] for row in payload["selected"]]
    payload["actionable_symbols"] = selected
    payload["fallback_candidates"] = [{"symbol": symbol, "selection_type": "static_fallback", "reason": "insufficient_scan_data"} for symbol in static_symbols]
    payload["selection_mode"] = "ranked" if selected else "static_fallback"
    payload["fallback_symbols"] = static_symbols
    payload["selected_symbols"] = selected
    Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def symbols_for_today(path: str | Path, static_symbols: list[str], enabled: bool, today: str | None = None, fundamental_config: dict | None = None) -> list[str]:
    if not enabled:
        return static_symbols
    try:
        payload = json.loads(Path(path).read_text())
        if payload.get("scan_date") != (today or date.today().isoformat()):
            return static_symbols
        symbols = payload.get("selected_symbols", [])
        if fundamental_config and fundamental_config.get("enabled"):
            from .fundamental_filter import score_candidates, write_fundamental_context
            rows = [row.get("metrics", {}) | {"symbol": row.get("symbol")} for row in payload.get("actionable", [])]
            scored = score_candidates(rows, fundamental_config)
            write_fundamental_context(fundamental_config.get("context_path", "fundamental_context.json"), scored, {"input_universe_hash": payload.get("scan_date")})
            by_symbol = {row["symbol"]: row for row in scored}
            allowed = {row["symbol"] for row in scored if row["eligible"]}
            symbols = [symbol for symbol in symbols if symbol in allowed]
            bonus_at = fundamental_config.get("bonus_at", 60)
            symbols.sort(key=lambda symbol: (-(fundamental_config.get("max_bonus", 10) if by_symbol[symbol]["score"] >= bonus_at else 0), -by_symbol[symbol]["score"], symbol))
        return symbols or static_symbols
    except (OSError, ValueError, TypeError):
        return static_symbols


def alpaca_assets() -> list[dict]:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetAssetsRequest
    from alpaca.trading.enums import AssetClass, AssetStatus
    client = TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True)
    assets = client.get_all_assets(GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY))
    return [a.__dict__ for a in assets]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Write a daily trading universe from prepared asset/metric JSON")
    parser.add_argument("--assets", required=True, help="JSON array of Alpaca-style assets")
    parser.add_argument("--metrics", required=True, help="JSON object keyed by symbol")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default="daily_universe.json")
    args = parser.parse_args()
    import yaml
    config = yaml.safe_load(Path(args.config).read_text()).get("daily_universe", {})
    result = scan_candidates(json.loads(Path(args.assets).read_text()), json.loads(Path(args.metrics).read_text()), config)
    payload = write_scan(result, args.output, yaml.safe_load(Path(args.config).read_text()).get("symbols", []))
    print(json.dumps({"output": str(args.output), "selected_symbols": payload["selected_symbols"], "rejected": len(payload["rejected"])}))
