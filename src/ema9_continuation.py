"""Research-only 9 EMA continuation strategy from the SMB Capital tutorial."""

import pandas as pd


class Ema9ContinuationStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("ema9_continuation", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.ema_length = int(cfg.get("ema_length", 9))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.2))
        self.pullback_bars = int(cfg.get("pullback_bars", 3))
        self.touch_tolerance_pct = float(cfg.get("touch_tolerance_pct", 0.002))
        self.rr_ratio = float(cfg.get("rr_ratio", 2.0))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.atr_multiplier = float(cfg.get("atr_multiplier", 0.5))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:35")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.max_gap_pct = float(cfg.get("max_gap_pct", 0.08))
        self.max_bar_range_pct = float(cfg.get("max_bar_range_pct", 0.08))
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _atr(self, bars):
        previous = bars.close.shift(1)
        true_range = pd.concat([bars.high - bars.low, (bars.high - previous).abs(), (bars.low - previous).abs()], axis=1).max(axis=1)
        return float(true_range.tail(self.atr_length).mean())

    def generate_signal(self, symbol, bars, context=None):
        minimum = max(self.ema_length + 2, self.atr_length + 2, 20)
        if len(bars) < minimum or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        key = (symbol, ts.date())
        if not self.session_start <= ts.time() < self.session_end or self._entry_counts.get(key, 0) >= 1:
            return None
        window = bars.tail(max(30, self.ema_length + self.pullback_bars + 5)).copy()
        if any(column not in window for column in ("open", "high", "low", "close", "volume")):
            return None
        bar, previous = window.iloc[-1], window.iloc[-2]
        close, high, low, open_price, volume = map(float, (bar.close, bar.high, bar.low, bar.open, bar.volume))
        previous_close = float(previous.close)
        if close <= 0 or previous_close <= 0 or volume <= 0:
            return None
        if abs(open_price / previous_close - 1) > self.max_gap_pct or (high - low) / close > self.max_bar_range_pct:
            return None
        average_volume = float(window.volume.iloc[:-1].tail(20).mean())
        if average_volume <= 0 or volume < average_volume * self.volume_multiplier:
            return None
        ema = window.close.ewm(span=self.ema_length, adjust=False).mean()
        if pd.isna(ema.iloc[-1]) or len(window) < self.pullback_bars + 2:
            return None
        current_ema, previous_ema = float(ema.iloc[-1]), float(ema.iloc[-2])
        recent = window.iloc[-(self.pullback_bars + 1):-1]
        recent_ema = ema.iloc[-(self.pullback_bars + 1):-1]
        tolerance = current_ema * self.touch_tolerance_pct
        long_touch = float(recent.low.min()) <= float(recent_ema.max()) + tolerance
        short_touch = float(recent.high.max()) >= float(recent_ema.min()) - tolerance
        atr = self._atr(window)
        if atr <= 0:
            return None
        long_reclaim = close > current_ema and previous_close <= previous_ema
        short_reclaim = close < current_ema and previous_close >= previous_ema
        if long_reclaim and long_touch and current_ema >= previous_ema:
            stop = min(float(recent.low.min()), close - self.atr_multiplier * atr)
            target = close + self.rr_ratio * (close - stop)
            qty = self.risk.calculate_qty(close, stop)
            if qty > 0:
                return self._signal(symbol, "long", close, stop, target, qty, ts, "9 EMA pullback reclaim with volume")
        if short_reclaim and short_touch and current_ema <= previous_ema:
            stop = max(float(recent.high.max()), close + self.atr_multiplier * atr)
            target = close - self.rr_ratio * (stop - close)
            qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            if qty > 0:
                return self._signal(symbol, "short", close, stop, target, qty, ts, "9 EMA pullback rejection with volume")
        return None

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
