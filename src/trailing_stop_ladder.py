"""Research-only trailing-stop ladder strategy (from the Claude/Alpaca video eval).

Momentum continuation entry in the direction of a fast/slow EMA trend, with an
ATR-buffered swing stop and an R-ladder: each rung of favorable move raises the
stop by one rung minus the lock offset. No fixed target — profits are captured
by the ladder trail, session close, or max holding bars. Paper-research only.
"""

import pandas as pd


class TrailingStopLadderStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("trailing_stop_ladder", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.ema_fast = int(cfg.get("ema_fast", 9))
        self.ema_slow = int(cfg.get("ema_slow", 50))
        self.lookback = int(cfg.get("lookback", 20))
        self.swing_lookback = int(cfg.get("swing_lookback", 10))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.2))
        self.stop_buffer_atr = float(cfg.get("stop_buffer_atr", 0.5))
        self.rung_r = float(cfg.get("rung_r", 1.0))
        self.lock_r = float(cfg.get("lock_offset_r", 1.0))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.entry_cutoff = pd.Timestamp(cfg.get("entry_cutoff", "15:00")).time()
        self.max_holding_bars = int(cfg.get("max_holding_bars", 60))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:35")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _atr(self, bars):
        previous = bars.close.shift(1)
        tr = pd.concat([bars.high - bars.low, (bars.high - previous).abs(), (bars.low - previous).abs()], axis=1).max(axis=1)
        return float(tr.tail(self.atr_length).mean())

    def generate_signal(self, symbol, bars, context=None):
        minimum = max(self.ema_slow + 2, self.atr_length + 2, self.lookback + 2)
        if len(bars) < minimum or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        key = (symbol, ts.date())
        if not self.session_start <= ts.time() < self.entry_cutoff or self._entry_counts.get(key, 0) >= 1:
            return None
        if any(c not in bars for c in ("open", "high", "low", "close", "volume")):
            return None
        bar, previous = bars.iloc[-1], bars.iloc[-2]
        close, volume = float(bar.close), float(bar.volume)
        previous_close = float(previous.close)
        if close <= 0 or previous_close <= 0 or volume <= 0:
            return None
        window = bars.tail(self.lookback)
        average_volume = float(window.volume.iloc[:-1].mean())
        if average_volume <= 0 or volume < average_volume * self.volume_multiplier:
            return None
        ema_fast = bars.close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = bars.close.ewm(span=self.ema_slow, adjust=False).mean()
        fast, slow = float(ema_fast.iloc[-1]), float(ema_slow.iloc[-1])
        atr = self._atr(bars)
        if atr <= 0:
            return None
        momentum = close > previous_close
        if fast > slow and momentum and close > fast:
            direction = "long"
            swing = float(bars.tail(self.swing_lookback).low.min())
            stop = swing - atr * self.stop_buffer_atr
        elif fast < slow and not momentum and close < fast:
            direction = "short"
            swing = float(bars.tail(self.swing_lookback).high.max())
            stop = swing + atr * self.stop_buffer_atr
        else:
            return None
        entry = close
        if direction == "long" and not 0 < stop < entry:
            return None
        if direction == "short" and not entry < stop:
            return None
        qty = self.risk.calculate_qty(entry, stop, allow_fractional=direction == "long")
        if qty <= 0:
            return None
        reason = f"EMA{self.ema_fast}/{self.ema_slow} trend continuation ladder"
        signal = {"symbol": symbol, "direction": direction, "entry": round(entry, 2), "stop": round(stop, 2), "target": 0.0, "qty": qty, "timestamp": ts.isoformat(), "reason": reason}
        return signal

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0, rung=0)
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
        entry, initial_stop, rung_reached = trade["entry"], trade["stop"], trade["rung"]
        risk_per_share = abs(entry - initial_stop)
        if risk_per_share <= 0:
            return None
        if long:
            post = bars[bars.index >= pd.Timestamp(trade["timestamp"])]
            peak = max(float(trade.get("peak", entry)), float(post.high.max()) if not post.empty else high)
            trade["peak"] = peak
            rung = int((peak - entry) / (risk_per_share * self.rung_r)) if peak >= entry else 0
            if rung > rung_reached:
                trade["rung"] = rung
                trade["stop"] = round(max(initial_stop, entry + (rung - self.lock_r) * risk_per_share), 2)
        else:
            post = bars[bars.index >= pd.Timestamp(trade["timestamp"])]
            trough = min(float(trade.get("trough", entry)), float(post.low.min()) if not post.empty else low)
            trade["trough"] = trough
            rung = int((entry - trough) / (risk_per_share * self.rung_r)) if trough <= entry else 0
            if rung > rung_reached:
                trade["rung"] = rung
                trade["stop"] = round(min(initial_stop, entry - (rung - self.lock_r) * risk_per_share), 2)
        stop, reason = trade["stop"], None
        if long:
            exit_price = stop if low <= stop else None
        else:
            exit_price = stop if high >= stop else None
        if exit_price is not None:
            reason = "trailing_stop" if trade["rung"] > 0 else "stop_loss"
        elif trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end:
            exit_price, reason = close, "session_close" if ts.time() >= self.session_end else "max_holding_bars"
        if exit_price is None:
            return None
        pnl = (exit_price - entry) * trade["qty"] if long else (entry - exit_price) * trade["qty"]
        realized_r = (exit_price - entry) / risk_per_share if long else (entry - exit_price) / risk_per_share
        result = {"symbol": symbol, "direction": trade["direction"], "entry": entry, "exit_price": round(exit_price, 2), "exit_time": ts.isoformat(), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": round(realized_r, 2), "reason": reason}
        self.risk.update_cash(pnl)
        if self.journal:
            self.journal.log_trade(result)
        del self._active_trades[symbol]
        return result
