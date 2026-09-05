import json

from src.daily_universe import filter_asset, passes_filters, scan_candidates, symbols_for_today


CFG = {"min_price": 3, "max_price": 100, "min_avg_dollar_volume": 20_000_000,
       "min_premarket_dollar_volume": 500_000, "min_gap_pct": .02, "max_gap_pct": .08,
       "min_relative_volume": 1.5, "max_spread_pct": .005, "max_symbols": 2}


def good_metrics():
    return {"price": 12, "avg_dollar_volume": 30_000_000, "premarket_dollar_volume": 2_000_000,
            "gap_pct": .04, "relative_volume": 2, "atr_pct": .04, "spread_pct": .001}


def test_asset_filter_rejects_otc():
    assert filter_asset({"symbol": "X", "exchange": "OTC", "status": "active"}) == (False, "otc")


def test_metrics_filter_and_scan_ranking():
    assert passes_filters(good_metrics(), CFG)[0]
    result = scan_candidates([{"symbol": "BBB", "exchange": "NASDAQ"}, {"symbol": "AAA", "exchange": "NASDAQ"}],
                             {"AAA": good_metrics(), "BBB": {**good_metrics(), "relative_volume": 4}}, CFG)
    assert result["selected"][0]["symbol"] == "BBB"


def test_stale_or_empty_scan_falls_back(tmp_path):
    path = tmp_path / "daily.json"
    path.write_text(json.dumps({"scan_date": "2000-01-01", "selected_symbols": ["BAD"]}))
    assert symbols_for_today(path, ["SPY"], True, today="2026-08-10") == ["SPY"]


def test_fundamental_filter_can_reject_candidates(tmp_path):
    path = tmp_path / "daily.json"
    path.write_text(json.dumps({"scan_date": "2026-08-10", "selected_symbols": ["GOOD", "BAD"], "actionable": [
        {"symbol": "GOOD", "metrics": {"gross_margin": .7, "operating_margin": .25, "roe": .25, "free_cashflow": 8_000_000, "pe_ratio": 18, "ev_ebitda": 14, "pb_ratio": 3, "revenue_growth": .2, "earnings_growth": .3, "current_ratio": 2, "debt_to_equity": 60, "operating_cashflow": 8_000_000, "avg_dollar_volume_30d": 50_000_000, "volatility_30d": .3}},
        {"symbol": "BAD", "metrics": {"pe_ratio": 80, "debt_to_equity": 400, "volatility_30d": 2}},
    ]}))
    result = symbols_for_today(path, ["SPY"], True, today="2026-08-10", fundamental_config={"enabled": True, "reject_below": 40, "context_path": str(tmp_path / "fundamental.json")})
    assert result == ["GOOD"]


def test_watchlist_returns_near_miss_when_no_qualified_candidate():
    metrics = {**good_metrics(), "gap_pct": 0.01}
    result = scan_candidates([{"symbol": "AAA", "exchange": "NASDAQ"}], {"AAA": metrics}, CFG)
    assert result["selected"] == []
    assert result["actionable"][0]["symbol"] == "AAA"
    assert result["actionable"][0]["selection_type"] == "watchlist"


def test_ross_scoring_prefers_gain_catalyst_and_low_float():
    cfg = {**CFG, "max_gap_pct": .20, "preferred_gap_pct": .10, "preferred_max_float": 20_000_000}
    base = {**good_metrics(), "relative_volume": 5, "float_shares": 50_000_000}
    leader = {**base, "gap_pct": .12, "float_shares": 2_000_000, "catalyst": "earnings"}
    result = scan_candidates(
        [{"symbol": "BASE", "exchange": "NASDAQ"}, {"symbol": "LEAD", "exchange": "NASDAQ"}],
        {"BASE": base, "LEAD": leader}, cfg,
    )
    assert result["selected"][0]["symbol"] == "LEAD"
