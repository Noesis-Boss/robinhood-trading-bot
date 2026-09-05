"""Universal strategy base class — every strategy implements just two methods."""
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
from src.risk import RiskManager


class UniversalStrategy(ABC):
    """All strategies inherit from this. Handles sessions, risk, and exit tracking.

    Subclasses override:
        _init()        — strategy-specific config
        _signals()     — emit {direction, entry, stop, target, reason}
        _exits()       — return dict with exit info or None
    """
    name = "universal"

    def __init__(self, config: dict, risk: RiskManager, journal=None):
        self.config = config
        self.risk = risk
        self.journal = journal
        self._active_trades: dict[str, dict] = {}
        self.timezone = config.get("timezone", "America/New_York")
        self.bar_interval = config.get("bar_interval", "5m")
        self.rr_ratio = config.get("rr_ratio", 2.0)
        self.max_holding_bars = config.get("max_holding_bars", 30)
        self._init()

    # ---- Subclass hooks ----
    def _init(self): pass

    @abstractmethod
    def _signals(self, symbol: str, bars: pd.DataFrame, context=None
                 ) -> list[dict]:
        """Return a list of entry signals (0 or 1 per bar)."""

    def _exits(self, symbol: str, bars: pd.DataFrame, trade: dict
               ) -> dict | None:
        """Return exit dict if trade should close, else None."""
        # Default: hit target / stop / max holding bars
        latest = bars.iloc[-1]
        high, low, close = float(latest["high"]), float(latest["low"]), float(latest["close"])
        trade["entry_bar_count"] = trade.get("entry_bar_count", 0) + 1
        direction = trade["direction"]
        stop = trade["stop"]
        target = trade["target"]
        exit_price = None
        reason = None

        if direction == "long":
            if high >= target:
                exit_price, reason = target, "target"
            elif low <= stop:
                exit_price, reason = stop, "stop"
        else:
            if low <= target:
                exit_price, reason = target, "target"
            elif high >= stop:
                exit_price, reason = stop, "stop"

        if trade["entry_bar_count"] >= self.max_holding_bars:
            exit_price, reason = close, "max_holding_bars"

        if exit_price is None:
            return None

        entry = trade["entry"]
        qty = trade["qty"]
        if direction == "long":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty

        return {
            "symbol": symbol,
            "direction": direction,
            "entry": round(entry, 2),
            "exit_price": round(exit_price, 2),
            "qty": qty,
            "pnl": round(pnl, 2),
            "reason": reason,
            "bars_held": trade["entry_bar_count"],
            "timestamp": bars.index[-1].isoformat(),
        }

    def _ny_time(self, ts) -> str:
        t = pd.Timestamp(ts)
        if t.tz is None:
            t = t.tz_localize(self.timezone)
        else:
            t = t.tz_convert(self.timezone)
        return t.strftime("%H:%M")

    def _to_ny(self, ts) -> pd.Timestamp:
        t = pd.Timestamp(ts)
        if t.tz is None:
            return t.tz_localize(self.timezone)
        return t.tz_convert(self.timezone)

    def on_trade_entered(self, symbol: str, trade: dict) -> None:
        trade["entry_bar_count"] = 0
        self._active_trades[symbol] = trade

    def generate_signal(self, symbol: str, bars: pd.DataFrame, context=None):
        """Legacy compatibility — wraps _signals."""
        sigs = self._signals(symbol, bars, context)
        if sigs:
            return sigs[0]
        return None

    def check_exit(self, symbol: str, bars: pd.DataFrame, broker=None):
        """Legacy compatibility — wraps _exits."""
        if symbol not in self._active_trades:
            return None
        return self._exits(symbol, bars, self._active_trades[symbol])
