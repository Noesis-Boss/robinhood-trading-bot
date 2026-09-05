"""Daily supply/demand swing strategy (JeaFx LTV methodology, codified).

Spec source: trading-methodology/PLAN.md (video reyleIzgE3o).
Daily timeframe only. Trade only with structure bias. Limit entries at
supply/demand zones formed by the last candle before a break of structure.
Minimum RR gate. Set-and-forget exits. Fixed fractional risk with weekly
loss and monthly profit circuit breakers.

Pure functions are kept dependency-free so tests run without market data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# --------------------------------------------------------------------------- #
# Swing structure
# --------------------------------------------------------------------------- #
def find_pivots(df: pd.DataFrame, k: int = 2) -> tuple[pd.Series, pd.Series]:
    """Fractal pivots: bar is a pivot high/low if extreme within +-k bars."""
    high, low = df["high"], df["low"]
    ph = pd.Series(False, index=df.index)
    pl = pd.Series(False, index=df.index)
    for i in range(k, len(df) - k):
        win_h = high.iloc[i - k : i + k + 1]
        win_l = low.iloc[i - k : i + k + 1]
        if high.iloc[i] == win_h.max() and (win_h == high.iloc[i]).sum() == 1:
            ph.iloc[i] = True
        if low.iloc[i] == win_l.min() and (win_l == low.iloc[i]).sum() == 1:
            pl.iloc[i] = True
    return ph, pl


@dataclass
class SwingState:
    """Rolling structural state for one symbol."""

    bias: int = 0  # +1 bullish, -1 bearish, 0 unknown
    last_sh: Optional[float] = None  # most recent confirmed swing high price
    last_sl: Optional[float] = None  # most recent confirmed swing low price
    sh_i: int = -1
    sl_i: int = -1


# --------------------------------------------------------------------------- #
# Zones and orders
# --------------------------------------------------------------------------- #
@dataclass
class Zone:
    kind: str  # "demand" | "supply"
    top: float
    bottom: float
    born: int  # bar index where BOS confirmed it
    tapped: bool = False

    def height(self) -> float:
        return self.top - self.bottom


@dataclass
class SwingOrder:
    side: str  # "long" | "short"
    limit: float
    stop: float
    target: float
    rr: float
    placed: int
    zone: Zone

    def check_rr(self) -> float:
        risk = abs(self.limit - self.stop)
        reward = abs(self.target - self.limit)
        return reward / risk if risk > 0 else 0.0


@dataclass
class SwingTrade:
    symbol: str
    side: str
    entry_i: int
    exit_i: int = -1
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    rr: float = 0.0
    outcome: str = ""  # "win" | "loss"
    target_kind: str = ""  # "zone" | "swing"


@dataclass
class RiskGovernor:
    """Fixed-fractional risk with weekly loss / monthly profit breakers."""

    equity: float = 10_000.0
    risk_pct: float = 0.01
    weekly_loss_limit: float = -0.02
    monthly_profit_limit: float = 0.08
    week_pnl: float = 0.0
    month_pnl: float = 0.0
    week_key: str = ""
    month_key: str = ""
    blocked_reason: str = ""
    log: list = field(default_factory=list)

    def roll(self, ts: pd.Timestamp):
        wk = ts.strftime("%G-W%V")
        mk = ts.strftime("%Y-%m")
        if wk != self.week_key:
            self.week_key, self.week_pnl = wk, 0.0
        if mk != self.month_key:
            self.month_key, self.month_pnl = mk, 0.0

    def can_trade(self, ts: pd.Timestamp) -> bool:
        self.roll(ts)
        if self.week_pnl <= self.weekly_loss_limit * 0.999:
            self.blocked_reason = "weekly_loss_limit"
            return False
        if self.month_pnl >= self.monthly_profit_limit * 0.999:
            self.blocked_reason = "monthly_profit_lock"
            return False
        self.blocked_reason = ""
        return True

    def risk_amount(self) -> float:
        return self.equity * self.risk_pct

    def settle(self, r_multiple: float, ts: pd.Timestamp):
        pnl = r_multiple * self.risk_pct
        self.equity *= 1 + pnl
        self.roll(ts)
        self.week_pnl += pnl
        self.month_pnl += pnl


# --------------------------------------------------------------------------- #
# Strategy engine (bar-by-bar)
# --------------------------------------------------------------------------- #
class SupplyDemandSwingStrategy:
    def __init__(self, config: dict | None = None, symbol: str = ""):
        self.symbol = symbol
        cfg = (config or {}).get("supply_demand_swing", {})
        self.pivot_k = int(cfg.get("pivot_k", 2))
        self.impulse_lookback = int(cfg.get("impulse_lookback", 10))
        self.min_rr = float(cfg.get("min_rr", 2.0))
        self.stop_buffer_pct = float(cfg.get("stop_buffer_pct", 0.001))
        self.max_order_bars = int(cfg.get("max_order_bars", 30))
        self.zone_expiry_bars = int(cfg.get("zone_expiry_bars", 120))
        self.governor = RiskGovernor(
            equity=float((config or {}).get("capital", 10_000.0)),
            risk_pct=float(cfg.get("risk_pct", 0.01)),
            weekly_loss_limit=float(cfg.get("weekly_loss_limit", -0.02)),
            monthly_profit_limit=float(cfg.get("monthly_profit_limit", 0.08)),
        )
        self.state = SwingState()
        self.zones: list[Zone] = []
        self.order: Optional[SwingOrder] = None
        self.trade: Optional[SwingTrade] = None
        self.trades: list[SwingTrade] = []
        self.missed: list[str] = []
        self.pending_pivot_high: Optional[tuple[int, float]] = None
        self.pending_pivot_low: Optional[tuple[int, float]] = None

    # -- helpers ---------------------------------------------------------- #
    def _zone_from_bos(self, kind: str, df: pd.DataFrame, bos_i: int) -> Optional[Zone]:
        """Origin candle of the impulse that broke structure."""
        start = max(0, bos_i - self.impulse_lookback)
        if kind == "demand":
            idx = [j for j in range(bos_i - 1, start - 1, -1) if df["close"].iloc[j] < df["open"].iloc[j]]
            j = idx[0] if idx else (start + int(df["low"].iloc[start:bos_i].values.argmin()) if bos_i > start else None)
        else:
            idx = [j for j in range(bos_i - 1, start - 1, -1) if df["close"].iloc[j] > df["open"].iloc[j]]
            j = idx[0] if idx else (start + int(df["high"].iloc[start:bos_i].values.argmax()) if bos_i > start else None)
        if j is None:
            return None
        if kind == "demand":
            z = Zone("demand", float(max(df["open"].iloc[j], df["close"].iloc[j])), float(df["low"].iloc[j]), bos_i)
        else:
            z = Zone("supply", float(df["high"].iloc[j]), float(min(df["open"].iloc[j], df["close"].iloc[j])), bos_i)
        return z if z.height() > 0 else None

    def _target_for_long(self, entry: float) -> tuple[Optional[float], str]:
        cands = [
            (z.bottom, "zone")
            for z in self.zones
            if z.kind == "supply" and not z.tapped and z.bottom > entry * 1.001
        ]
        if cands:
            t = min(cands)[0]
            return t, "zone"
        if self.state.last_sh and self.state.last_sh > entry * 1.001:
            return self.state.last_sh, "swing"
        return None, ""

    def _target_for_short(self, entry: float) -> tuple[Optional[float], str]:
        cands = [
            (z.top, "zone")
            for z in self.zones
            if z.kind == "demand" and not z.tapped and z.top < entry * 0.999
        ]
        if cands:
            t = max(cands)[0]
            return t, "zone"
        if self.state.last_sl and self.state.last_sl < entry * 0.999:
            return self.state.last_sl, "swing"
        return None, ""

    def _prune_zones(self, i: int):
        self.zones = [z for z in self.zones if i - z.born <= self.zone_expiry_bars]

    # -- main step --------------------------------------------------------- #
    def on_bar(self, i: int, df: pd.DataFrame) -> None:
        row = df.iloc[i]
        ts = df.index[i]
        hi, lo, cl = float(row["high"]), float(row["low"]), float(row["close"])

        # confirm pending pivots (k bars later)
        k = self.pivot_k
        if i >= k:
            pj = i - k
            win_h = df["high"].iloc[pj - k : pj + k + 1]
            win_l = df["low"].iloc[pj - k : pj + k + 1]
            if df["high"].iloc[pj] == win_h.max():
                self.state.last_sh, self.state.sh_i = float(df["high"].iloc[pj]), pj
            if df["low"].iloc[pj] == win_l.min():
                self.state.last_sl, self.state.sl_i = float(df["low"].iloc[pj]), pj

        self._prune_zones(i)

        # manage open trade first (set-and-forget)
        if self.trade is not None:
            t = self.trade
            if t.side == "long":
                if lo <= t.stop:
                    t.outcome, t.exit_i = "loss", i
                    self.governor.settle(-1.0, ts)
                elif hi >= t.target:
                    t.outcome, t.exit_i = "win", i
                    self.governor.settle(t.rr, ts)
            else:
                if hi >= t.stop:
                    t.outcome, t.exit_i = "loss", i
                    self.governor.settle(-1.0, ts)
                elif lo <= t.target:
                    t.outcome, t.exit_i = "win", i
                    self.governor.settle(t.rr, ts)
            if t.outcome:
                self.trades.append(t)
                self.trade = None

        # trend-shift confirmation: close beyond opposing swing flips bias
        if self.state.last_sh is not None and cl > self.state.last_sh and self.state.bias <= 0:
            self.state.bias = 1
            z = self._zone_from_bos("demand", df, i)
            if z:
                self.zones.append(z)
                self._maybe_place_long(i, ts, z)
        elif self.state.last_sl is not None and cl < self.state.last_sl and self.state.bias >= 0:
            self.state.bias = -1
            z = self._zone_from_bos("supply", df, i)
            if z:
                self.zones.append(z)
                self._maybe_place_short(i, ts, z)

        # order lifecycle
        if self.order is not None and self.trade is None:
            o = self.order
            expired = i - o.placed >= self.max_order_bars
            ran_away = (o.side == "long" and hi >= o.target) or (o.side == "short" and lo <= o.target)
            flipped = (o.side == "long" and self.state.bias < 0) or (o.side == "short" and self.state.bias > 0)
            filled = lo <= o.limit <= hi if o.side == "long" else lo <= o.limit <= hi
            if filled and not flipped:
                self.trade = SwingTrade(
                    symbol=self.symbol, side=o.side, entry_i=i,
                    entry=o.limit, stop=o.stop, target=o.target,
                    rr=o.rr, target_kind=getattr(o, "target_kind", ""),
                )
                self.order = None
            elif expired or ran_away or flipped:
                if ran_away:
                    self.missed.append(f"{df.index[i].date()}: ran to target unfilled")
                self.order = None
                o.zone.tapped = True

        # mark zones tapped when price passes through their far side
        for z in self.zones:
            if z.kind == "demand" and lo < z.bottom:
                z.tapped = True
            if z.kind == "supply" and hi > z.top:
                z.tapped = True

    def _maybe_place_long(self, i: int, ts: pd.Timestamp, z: Zone):
        if self.trade is not None or self.order is not None or not self.governor.can_trade(ts):
            return
        entry = z.top
        stop = z.bottom * (1 - self.stop_buffer_pct)
        tgt, kind = self._target_for_long(entry)
        if tgt is None:
            return
        o = SwingOrder("long", entry, stop, tgt, 0.0, i, z)
        o.rr = o.check_rr()
        o.target_kind = kind
        if o.rr >= self.min_rr:
            self.order = o
        else:
            self.missed.append(f"rr<{self.min_rr}")

    def _maybe_place_short(self, i: int, ts: pd.Timestamp, z: Zone):
        if self.trade is not None or self.order is not None or not self.governor.can_trade(ts):
            return
        entry = z.bottom
        stop = z.top * (1 + self.stop_buffer_pct)
        tgt, kind = self._target_for_short(entry)
        if tgt is None:
            return
        o = SwingOrder("short", entry, stop, tgt, 0.0, i, z)
        o.rr = o.check_rr()
        o.target_kind = kind
        if o.rr >= self.min_rr:
            self.order = o
        else:
            self.missed.append(f"rr<{self.min_rr}")
