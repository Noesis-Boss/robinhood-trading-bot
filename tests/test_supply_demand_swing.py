import pandas as pd
import pytest

from src.supply_demand_swing import (
    RiskGovernor,
    SupplyDemandSwingStrategy,
    find_pivots,
)


def _df(rows, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(rows), freq="D", tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def test_find_pivots_detects_highs_and_lows():
    close = [10, 11, 12, 13, 12, 11, 12, 13, 15, 16, 15, 14, 13, 12, 13, 14, 15, 16, 17, 18]
    rows = [(c - 0.5, c + 0.5, c - 1.0, c, 1000) for c in close]
    df = _df(rows)
    ph, pl = find_pivots(df, k=2)
    assert ph.any() and pl.any()
    for i in list(ph[ph].index) + list(pl[pl].index):
        pos = df.index.get_loc(i)
        assert 2 <= pos < len(df) - 2


def test_governor_blocks_after_weekly_loss_limit():
    g = RiskGovernor(equity=10_000, risk_pct=0.01)
    ts = pd.Timestamp("2026-03-02 09:00", tz="America/New_York")
    g.roll(ts)
    for _ in range(2):
        g.settle(-1.0, ts)
    assert g.week_pnl <= -0.02
    assert not g.can_trade(ts + pd.Timedelta(days=1))
    assert g.blocked_reason == "weekly_loss_limit"


def test_governor_monthly_profit_lock():
    g = RiskGovernor(equity=10_000, risk_pct=0.01, monthly_profit_limit=0.08)
    ts = pd.Timestamp("2026-03-02 09:00", tz="America/New_York")
    g.roll(ts)
    for _ in range(9):
        g.settle(2.0, ts)
    later = ts + pd.Timedelta(days=3)
    assert not g.can_trade(later)
    assert g.blocked_reason == "monthly_profit_lock"
    nxt = later.replace(month=4)
    assert g.can_trade(nxt)


def test_bos_up_creates_demand_zone_and_flips_bias():
    rows = []
    p = 100.0
    for _ in range(8):          # climb -> sets up pivot high at bar 7
        p += 0.5
        rows.append((p - 0.3, p + 0.4, p - 0.6, p + 0.1, 1000))
    for _ in range(3):          # pullback -> bearish candles (demand origin)
        p -= 0.4
        rows.append((p + 0.3, p + 0.5, p - 0.6, p - 0.4, 1000))
    for _ in range(8):          # rally closes above the 105.4 pivot high
        p += 0.8
        rows.append((p - 0.3, p + 0.5, p - 0.6, p + 0.6, 1000))
    df = _df(rows)
    strat = SupplyDemandSwingStrategy({"supply_demand_swing": {"pivot_k": 2}})
    for i in range(len(df)):
        strat.on_bar(i, df)
    assert strat.state.bias == 1
    assert any(z.kind == "demand" for z in strat.zones)


def test_order_skipped_when_rr_below_min():
    import src.supply_demand_swing as m
    from src.supply_demand_swing import Zone

    class Dummy(m.SupplyDemandSwingStrategy):
        def _maybe_place_long(self, i, zone):
            if self.trade is not None or self.order is not None:
                return
            entry = zone.top
            stop = zone.bottom * (1 - self.stop_buffer_pct)
            tgt, kind = self._target_for_long(entry)
            if tgt is None:
                return
            o = m.SwingOrder("long", entry, stop, tgt, 0.0, i, zone)
            o.rr = o.check_rr()
            o.target_kind = kind
            if o.rr >= self.min_rr:
                self.order = o
            else:
                self.missed.append(f"rr<{self.min_rr}")

    d = Dummy()
    d._target_for_long = lambda entry: (101.5, "swing")
    d._maybe_place_long(0, Zone("demand", top=100.0, bottom=99.0, born=0))
    assert d.order is None and d.missed


def test_set_and_forget_stop_first_when_both_hit_same_bar():
    strat = SupplyDemandSwingStrategy({"supply_demand_swing": {}})
    from src.supply_demand_swing import SwingTrade

    strat.trade = SwingTrade("SPY", "long", entry_i=0, entry=100.0, stop=98.0, target=104.0, rr=2.0)
    rows = [
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 101.0, "volume": 1000},
        {"open": 101.0, "high": 105.0, "low": 97.0, "close": 103.0, "volume": 1000},
    ]
    df = _df(rows)
    strat.on_bar(1, df)
    assert strat.trade is None
    assert strat.trades[-1].outcome == "loss"


def test_order_expires_without_fill():
    cfg = {"supply_demand_swing": {"max_order_bars": 3}}
    strat = SupplyDemandSwingStrategy(cfg)
    from src.supply_demand_swing import SwingOrder, Zone

    z = Zone("demand", top=90.0, bottom=89.0, born=0)
    o = SwingOrder("long", limit=90.0, stop=88.9, target=94.0, rr=2.0, placed=0, zone=z)
    o.target_kind = "swing"
    strat.order = o
    strat.state.bias = 1
    rows = [(95, 96, 94.5, 95.5, 1000)] * 5
    df = _df(rows)
    for i in range(len(df)):
        strat.on_bar(i, df)
    assert strat.order is None and strat.trade is None
