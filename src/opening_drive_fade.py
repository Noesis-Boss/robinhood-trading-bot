"""Opening Drive Fade — fade a one-directional opening drive at drive-end.

Paper-research only. Detects an unhealthy opening drive (large net move from
09:30 with minimal pullback) and fades it at the drive-end bar, targeting a
reversal back toward the open.

Config block: opening_drive_fade in config.yaml.
"""

import pandas as pd


class OpeningDriveFadeStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("opening_drive_fade", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.drive_end = pd.Timestamp(cfg.get("drive_end", "09:45")).time()
        self.drive_min_pct = float(cfg.get("drive_min_pct", 0.5))
        self.max_pullback_frac = float(cfg.get("max_pullback_frac", 0.33))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.2))
        self.stop_buffer_atr = float(cfg.get("stop_buffer_atr", 0.25))
        self.rr_ratio = float(cfg.get("rr_ratio", 3.0))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 66))
        self.require_level = bool(cfg.get("require_level", False))
        self.level_buffer_atr = float(cfg.get("level_buffer_atr", 1.0))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.require_level = bool(cfg.get("require_level", False))
        self.level_buffer_atr = float(cfg.get("level_buffer_atr", 1.0))
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _atr(self, bars):
        previous = bars.close.shift(1)
        tr = pd.concat([bars.high - bars.low, (bars.high - previous).abs(), (bars.low - previous).abs()], axis=1).max(axis=1)
        return float(tr.tail(self.atr_length).mean())

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < 10 or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        key = (symbol, ts.date())
        if ts.time() < self.drive_end or self._entry_counts.get(key, 0) >= 1:
            return None
        if any(c not in bars for c in ("open", "high", "low", "close", "volume")):
            return None

        drive = bars.iloc[:-1]
        if drive.empty:
            return None
        drive_open = float(drive.open.iloc[0])
        entry = float(bars.close.iloc[-1])
        if drive_open <= 0 or entry <= 0:
            return None
        move_pct = (entry - drive_open) / drive_open * 100.0
        if abs(move_pct) < self.drive_min_pct:
            return None

        drive_high = float(drive.high.max())
        drive_low = float(drive.low.min())
        drive_range = drive_high - drive_low
        if drive_range <= 0:
            return None
        if move_pct > 0:
            up_idx = drive.high.values.argmax()
            after = drive.low.iloc[up_idx + 1:]
            pullback = (drive_high - float(after.min())) / drive_range if len(after) else 0.0
        else:
            down_idx = drive.low.values.argmin()
            after = drive.high.iloc[down_idx + 1:]
            pullback = (float(after.max()) - drive_low) / drive_range if len(after) else 0.0
        if pullback > self.max_pullback_frac:
            return None

        avg_volume = float(bars.volume.mean())
        if avg_volume <= 0 or float(bars.volume.iloc[-1]) < avg_volume * self.volume_multiplier:
            return None

        atr = self._atr(bars)
        if atr <= 0:
            return None
        if self.require_level:
            if not context or "prior_high" not in context or "prior_low" not in context:
                return None
            buffer = atr * self.level_buffer_atr
            if move_pct > 0 and drive_high < float(context["prior_high"]) - buffer:
                return None
            if move_pct < 0 and drive_low > float(context["prior_low"]) + buffer:
                return None
        if self.require_level:
            if not context or "prior_high" not in context or "prior_low" not in context:
                return None
            buffer = atr * self.level_buffer_atr
            if move_pct > 0 and drive_high < float(context["prior_high"]) - buffer:
                return None
            if move_pct < 0 and drive_low > float(context["prior_low"]) + buffer:
                return None
        if move_pct > 0:
            direction = "short"
            stop = drive_high + atr * self.stop_buffer_atr
            target = entry - self.rr_ratio * (stop - entry)
            qty = self.risk.calculate_qty(entry, stop, allow_fractional=False)
            reason = f"opening drive up {move_pct:.2f}% / pullback {pullback * 100:.0f}%"
        else:
            direction = "long"
            stop = drive_low - atr * self.stop_buffer_atr
            target = entry + self.rr_ratio * (entry - stop)
            qty = self.risk.calculate_qty(entry, stop)
            reason = f"opening drive down {move_pct:.2f}% / pullback {pullback * 100:.0f}%"
        if qty <= 0 or target <= 0:
            return None
        return self._signal(symbol, direction, entry, stop, target, qty, ts, reason)

    def _signal(self, symbol, direction, entry, stop, target, qty, ts, reason):
        return {"symbol": symbol, "direction": direction, "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": reason}

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0)
        key = (symbol, pd.Timestamp(signal["timestamp"]).date())
        self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        trade = self._active_trades.get(symbol)
        if not trade:
            return None
        trade["entry_bar_count"] += 1
        bar, ts = bars.iloc[-1], self._ny(bars.index[-1])
        high, low, close = map(float, (bar.high, bar.low, bar.close))
        long = trade["direction"] == "long"
        if long:
            exit_price, reason = ((trade["stop"], "stop_loss") if low <= trade["stop"] else (trade["target"], "target_hit") if high >= trade["target"] else (None, None))
        else:
            exit_price, reason = ((trade["stop"], "stop_loss") if high >= trade["stop"] else (trade["target"], "target_hit") if low <= trade["target"] else (None, None))
        if exit_price is None and (trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end):
            exit_price, reason = close, "session_close" if ts.time() >= self.session_end else "max_holding_bars"
        if exit_price is None:
            return None
        pnl = (exit_price - trade["entry"]) * trade["qty"] if long else (trade["entry"] - exit_price) * trade["qty"]
        result = {"symbol": symbol, "direction": trade["direction"], "entry": trade["entry"], "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.rr_ratio, "reason": reason, "exit_time": ts.isoformat()}
        self.risk.update_cash(pnl)
        if self.journal:
            self.journal.log_trade(result)
        del self._active_trades[symbol]
        return result
