"""Book-replay tests: staggered gate-filtered entries through the 2008 path."""
from src.margin_stress import replay_book


def test_cash_secured_book_survives_2008():
    r = replay_book(100000, 3.84, securing="cash", num_entries=4, entry_spacing_days=21)
    assert r["verdict"] == "SURVIVED"
    assert r["entries_open_at_end"] == 4
    assert r["premium_collected"] > 0
    assert r["open_max_liability"] == 115200.0
    assert r["final_equity"] < r["start_equity"]


def test_margin_book_flags_call():
    r = replay_book(100000, 3.84, securing="margin", margin_leverage=2.0,
                    num_entries=4, entry_spacing_days=21)
    assert r["verdict"] == "MARGIN_CALL"
    assert r["margin_called_month"] == 10
    assert r["final_equity"] < r["start_equity"]


def test_gate_blocks_all_entries_when_floor_impossible():
    r = replay_book(100000, 3.84, num_entries=4, min_yield_annual_pct=99.0)
    assert r["entries_open_at_end"] == 0
    assert r["premium_collected"] == 0.0
    assert r["open_max_liability"] == 0.0
    assert r["verdict"] == "SURVIVED"


def test_staggered_entries_price_at_later_spots():
    r = replay_book(100000, 28.0, num_entries=3, entry_spacing_days=31)
    months = [e["entry_month"] for e in r["entries"]]
    assert months == [1, 2, 3]
    assert r["entries"][1]["spot_at_entry"] < r["entries"][0]["spot_at_entry"]
