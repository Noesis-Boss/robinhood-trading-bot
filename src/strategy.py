import logging
import pandas as pd
from datetime import time
from .risk import RiskManager
from .journal import TradeJournal


class LondonBreakoutStrategy:
    """London Breakout day trading strategy.

    Based on the video's approach:
      1. Build a price box during the London session (3:00 AM – 8:00 AM ET).
      2. Watch for breakouts at the open of the NY session (8:00 AM ET).
      3. Long if price breaks above the box high; short if it breaks below the box low.
      4. Target = 2x risk (2:1 reward:risk).
      5. Stop = other side of the box.
      6. Trades 5-min candles; max one trade per symbol per session.

    Improvements for higher win rate:
      - Volume confirmation: only enter on above-average breakout volume.
      - Box-size filter: skip when London range is too narrow or too wide.
      - Entry window: only enter in first N hours of NY session.
      - Directional bias: align entry with NY open momentum.
      - Trend filter: only long in uptrends, short in downtrends.
      - Maximum holding period: force exit after N bars to avoid random EOD closes.
      - Trailing stop: once 1x risk in profit, trail to breakeven.
      - Early exit: close losing positions if price reverses back into the box.
    """

    def __init__(self, config: dict, risk: RiskManager, journal: TradeJournal):
        self.config = config
        self.risk = risk
        self.journal = journal
        self.timezone = config.get("timezone", "America/New_York")
        self.bar_interval = config.get("bar_interval", "5m")

        london_open = config.get("london_open", "03:00")
        london_close = config.get("london_close", "08:00")
        ny_open = config.get("ny_open", "08:00")
        ny_close = config.get("ny_close", "12:00")

        self.london_start = pd.Timestamp(london_open).time()
        self.london_end = pd.Timestamp(london_close).time()
        self.ny_start = pd.Timestamp(ny_open).time()
        self.ny_end = pd.Timestamp(ny_close).time()

        # --- Strategy parameters (defaults from video + best practices) ---
        self.min_box_pct = config.get("min_box_pct", 0.005)
        self.max_box_pct = config.get("max_box_pct", 0.04)
        self.entry_window_hours = config.get("entry_window_hours", 3)
        self.volume_lookback = config.get("volume_lookback", 20)
        self.volume_multiplier = config.get("volume_multiplier", 0.8)
        self.directional_bias = config.get("directional_bias", True)
        self.trend_filter = config.get("trend_filter", True)
        self.trend_lookback = config.get("trend_lookback", 20)
        self.breakout_strength = config.get("breakout_strength", 0.3)
        self.rr_ratio = config.get("rr_ratio", 2.0)
        self.max_holding_bars = config.get("max_holding_bars", 45)
        self.trailing_stop_breakeven = config.get("trailing_stop_breakeven", True)
        self.early_exit_reversal = config.get("early_exit_reversal", False)
        raw_entry_limit = config.get("max_entries_per_day", 1)
        self.max_entries_per_day = None if str(raw_entry_limit).lower() in {"unlimited", "0"} else int(raw_entry_limit)

        self._active_trades: dict[str, dict] = {}
        self._entry_counts: dict[tuple[str, object], int] = {}

    def _to_ny_timezone(self, ts: pd.Timestamp) -> pd.Timestamp:
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert(self.timezone)

    def build_london_box(self, bars: pd.DataFrame) -> tuple[float, float] | None:
        """Build the London session price box from historical bars.

        Returns (box_high, box_low) or None if no London data or invalid box.
        """
        ny_bars = bars.copy()
        ny_bars.index = ny_bars.index.map(self._to_ny_timezone)

        london_mask = (ny_bars.index.time >= self.london_start) & (ny_bars.index.time < self.london_end)
        london_data = ny_bars[london_mask]

        if london_data.empty:
            return None

        box_high = float(london_data["high"].max())
        box_low = float(london_data["low"].min())

        # Filter: box range must be within acceptable volatility bounds
        box_range = box_high - box_low
        box_mid = (box_high + box_low) / 2
        if box_mid == 0:
            return None
        box_pct = box_range / box_mid

        if box_pct < self.min_box_pct:
            return None
        if box_pct > self.max_box_pct:
            return None

        return box_high, box_low

    def _avg_volume(self, bars: pd.DataFrame) -> float:
        """Average volume over the lookback window."""
        if "volume" not in bars.columns:
            return 0.0
        vol = bars["volume"].tail(self.volume_lookback)
        if vol.empty:
            return 0.0
        return float(vol.mean())

    def _in_uptrend(self, bars: pd.DataFrame) -> bool:
        """Check if the latest close is above the N-bar simple moving average."""
        closes = bars["close"].tail(self.trend_lookback)
        if len(closes) < self.trend_lookback:
            return True
        sma = closes.mean()
        return float(bars["close"].iloc[-1]) > float(sma)

    def _in_downtrend(self, bars: pd.DataFrame) -> bool:
        """Check if the latest close is below the N-bar simple moving average."""
        closes = bars["close"].tail(self.trend_lookback)
        if len(closes) < self.trend_lookback:
            return True
        sma = closes.mean()
        return float(bars["close"].iloc[-1]) < float(sma)

    def generate_signal(
        self,
        symbol: str,
        bars: pd.DataFrame,
        london_box: tuple[float, float] | None,
    ) -> dict | None:
        """Generate a trading signal from the latest bar."""
        if london_box is None:
            return None

        box_high, box_low = london_box
        latest = bars.iloc[-1]
        close = float(latest["close"])
        high = float(latest["high"])
        low = float(latest["low"])
        ts = self._to_ny_timezone(bars.index[-1])

        # Only generate signals during NY session
        if not (ts.time() >= self.ny_start and ts.time() < self.ny_end):
            return None

        # Skip if already have an active trade for this symbol
        if symbol in self._active_trades:
            return None
        if self.max_entries_per_day is not None and self._entry_counts.get((symbol, ts.date()), 0) >= self.max_entries_per_day:
            return None

        # Entry window filter: only enter in first N hours of NY session
        ny_open_ts = pd.Timestamp.combine(ts.date(), self.ny_start)
        if ts.tzinfo is not None:
            ny_open_ts = ny_open_ts.tz_localize(self.timezone)
        hours_since_open = (ts - ny_open_ts).total_seconds() / 3600
        if hours_since_open >= self.entry_window_hours:
            return None

        # Volume confirmation: breakout bar must exceed average volume
        avg_vol = self._avg_volume(bars)
        current_vol = float(latest.get("volume", 0))
        if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
            return None

        # Box range and midpoint for bias / breakout strength filters
        box_range = box_high - box_low
        box_mid = (box_high + box_low) / 2

        # Directional bias: for longs, NY open should be above box midpoint
        #                     for shorts, NY open should be below box midpoint
        ny_open_price = close
        if self.directional_bias:
            try:
                ny_open_bar_idx = bars.index.get_indexer([ny_open_ts], method="nearest")[0]
                ny_open_price = float(bars.iloc[ny_open_bar_idx]["close"])
            except Exception:
                ny_open_price = close

        # Long breakout: close breaks above box high + strength buffer
        if close > box_high + box_range * self.breakout_strength:
            if self.directional_bias and ny_open_price < box_mid:
                return None
            if self.trend_filter and not self._in_uptrend(bars):
                return None
            entry = close
            stop = box_low
            target = entry + self.rr_ratio * (entry - stop)
            qty = self.risk.calculate_qty(entry, stop)
            if qty <= 0:
                return None
            return {
                "symbol": symbol,
                "direction": "long",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "qty": qty,
                "box_high": round(box_high, 2),
                "box_low": round(box_low, 2),
                "timestamp": ts.isoformat(),
                "reason": f"London breakout long: close ${close:.2f} > box high ${box_high:.2f} + strength (vol={current_vol:.0f} vs avg={avg_vol:.0f})",
            }

        # Short breakout: close breaks below box low - strength buffer
        if close < box_low - box_range * self.breakout_strength:
            if self.directional_bias and ny_open_price > box_mid:
                return None
            if self.trend_filter and not self._in_downtrend(bars):
                return None
            entry = close
            stop = box_high
            target = entry - self.rr_ratio * (stop - entry)
            qty = self.risk.calculate_qty(entry, stop, allow_fractional=False)
            if qty <= 0:
                return None
            return {
                "symbol": symbol,
                "direction": "short",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "qty": qty,
                "box_high": round(box_high, 2),
                "box_low": round(box_low, 2),
                "timestamp": ts.isoformat(),
                "reason": f"London breakout short: close ${close:.2f} < box low ${box_low:.2f} - strength (vol={current_vol:.0f} vs avg={avg_vol:.0f})",
            }

        return None

    def check_exit(self, symbol: str, bars: pd.DataFrame, broker) -> dict | None:
        """Check if an active trade should be exited."""
        if symbol not in self._active_trades:
            return None

        trade = self._active_trades[symbol]
        trade["entry_bar_count"] = trade.get("entry_bar_count", 0) + 1
        bar_count = trade["entry_bar_count"]
        latest = bars.iloc[-1]
        ts = self._to_ny_timezone(bars.index[-1])

        high = float(latest["high"])
        low = float(latest["low"])
        close = float(latest["close"])

        box_high = trade.get("box_high", 0)
        box_low = trade.get("box_low", 0)
        target = trade["target"]
        stop = trade["stop"]
        entry = trade["entry"]
        direction = trade["direction"]

        exited = False
        exit_price = None
        reason = ""

        if direction == "long":
            # Trailing stop: if in profit by 1x risk, move stop to breakeven
            risk_amount = entry - stop
            if self.trailing_stop_breakeven and low >= entry + risk_amount:
                stop = entry
                trade["stop"] = stop
                self.journal.log(f"[TRAIL] {symbol} long stop->breakeven ${stop:.2f}")

            # Early exit: if price reverses back into the box, exit at market
            if self.early_exit_reversal and low <= box_high:
                exit_price = box_high
                exited = True
                reason = "early_exit_reversal"

            if not exited:
                if low <= stop:
                    exit_price = stop
                    exited = True
                    reason = "stop_loss"
                elif high >= target:
                    exit_price = target
                    exited = True
                    reason = "target_hit"

        else:  # short
            risk_amount = stop - entry
            if self.trailing_stop_breakeven and high <= entry - risk_amount:
                stop = entry
                trade["stop"] = stop
                self.journal.log(f"[TRAIL] {symbol} short stop->breakeven ${stop:.2f}")

            if self.early_exit_reversal and high >= box_low:
                exit_price = box_low
                exited = True
                reason = "early_exit_reversal"

            if not exited:
                if high >= stop:
                    exit_price = stop
                    exited = True
                    reason = "stop_loss"
                elif low <= target:
                    exit_price = target
                    exited = True
                    reason = "target_hit"

        # Maximum holding period: force exit after N bars
        if not exited and bar_count >= self.max_holding_bars:
            exit_price = close
            exited = True
            reason = f"time_exit_{self.max_holding_bars}bars"

        # EOD close: if still open at session end
        if not exited and ts.time() >= self.ny_end:
            exit_price = close
            exited = True
            reason = "eod_close"

        if exited and exit_price is not None:
            qty = trade["qty"]
            if direction == "long":
                pnl = (exit_price - entry) * qty
            else:
                pnl = (entry - exit_price) * qty
            self.risk.update_cash(pnl)

            result = {
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "exit_price": round(exit_price, 2),
                "exit_time": ts.isoformat(),
                "timestamp": trade.get("timestamp"),
                "qty": qty,
                "pnl": round(pnl, 2),
                "rr": round(abs(target - entry) / abs(stop - entry), 2) if abs(stop - entry) != 0 else 0,
                "reason": reason,
            }
            self.journal.log_trade(result)
            del self._active_trades[symbol]
            logging.info(f"Exit: {symbol} {direction} @${exit_price:.2f} {reason} P&L=${pnl:.2f}")
            return result

        return None

    def on_trade_entered(self, symbol: str, trade: dict) -> None:
        """Record a trade as active."""
        trade["entry_bar_count"] = 0
        self._active_trades[symbol] = trade
        day = self._to_ny_timezone(pd.Timestamp(trade.get("timestamp"))).date()
        key = (symbol, day)
        self._entry_counts[key] = self._entry_counts.get(key, 0) + 1
        logging.info(
            f"Active trade opened: {trade['direction'].upper()} {trade['qty']} {symbol} "
            f"entry=${trade['entry']} stop=${trade['stop']} target=${trade['target']}"
        )
