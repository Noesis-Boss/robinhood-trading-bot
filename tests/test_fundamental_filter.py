import json

from src.fundamental_filter import load_fundamental_context, score_candidate, score_candidates, write_fundamental_context


def strong(symbol="AAA"):
    return {"symbol": symbol, "gross_margin": .7, "operating_margin": .25, "roe": .25, "free_cashflow": 8_000_000,
            "pe_ratio": 18, "ev_ebitda": 14, "pb_ratio": 3, "revenue_growth": .2, "earnings_growth": .3,
            "current_ratio": 2, "debt_to_equity": 60, "operating_cashflow": 8_000_000,
            "avg_dollar_volume_30d": 50_000_000, "volatility_30d": .3}


def test_score_is_deterministic_and_bounded():
    first = score_candidate(strong())
    assert first == score_candidate(strong())
    assert 0 <= first["score"] <= 100
    assert first["eligible"]


def test_weak_candidate_gets_flags_and_missing_fields():
    result = score_candidate({"symbol": "BAD", "pe_ratio": 80, "debt_to_equity": 400, "volatility_30d": 2})
    assert result["score"] < 60
    assert "high_debt" in result["risk_flags"]
    assert "high_valuation" in result["risk_flags"]
    assert "gross_margin" in result["missing_fields"]


def test_candidates_sort_by_score():
    result = score_candidates([strong("LOW"), {**strong("HIGH"), "gross_margin": .8, "revenue_growth": .5}])
    assert [row["symbol"] for row in result] == ["HIGH", "LOW"]


def test_context_is_atomic_and_rejects_stale_or_mismatched_universe(tmp_path):
    path = tmp_path / "fundamental.json"
    payload = write_fundamental_context(path, score_candidates([strong()]))
    assert json.loads(path.read_text())["results"][0]["symbol"] == "AAA"
    assert load_fundamental_context(path, ["AAA"]) == payload
    assert load_fundamental_context(path, ["BBB"]) is None
    assert load_fundamental_context(path, today="2000-01-01") is None
