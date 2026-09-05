"""Research strategy: EMA(50/110) zone pullback confirmed by CCI zero-line cross
and a turning MACD histogram (video: https://m.youtube.com/watch?v=_Wr57vS9ADM).

Research-only: disabled by default, never wired to live order placement.
"""

import pandas as pd


class EmaCciMacdStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("ema_cci_macd", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.ema_fast = int(cfg.get("ema_fast", 50))
        self.ema_slow = int(cfg.get("ema_slow", 110))
        self.cci_length = int(cfg.get("cci_length", 20))
        self.macd_fast = int(cfg.get("macd_fast", 12))
        self.macd_slow = int(cfg.get("macd_slow", 26))
        self.macd_signal = int(cfg.get("macd_signal", 9))
        self.zone_touch_bars = int(cfg.get("zone_touch_bars", 3))
        self.zone_proximity_pct = float(cfg.get("zone_proximity_pct", .002))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.rr_ratio = float(cfg.get("rr_ratio", 2))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.max_gap_pct = float(cfg.get("max_gap_pct", .08))
        self.max_bar_range_pct = float(cfg.get("max_bar_range_pct", .08))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:35")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.warmup = max(self.ema_slow * 3, self.macd_slow * 4, 260)
        self._cache, self._active_trades, self._entry_counts = {}, {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _window(self, symbol, bars):
        cached = self._cache.get(symbol)
        if cached is None:
            window = bars.tail(self.warmup)
        else:
            if len(bars) and bars.index[-1] <= cached.index[-1]:
                return cached
            window = pd.concat([cached, bars[bars.index > cached.index[-1]]])
        self._cache[symbol] = window
        return window

    def _atr(self, window):
        previous = window.close.shift(1)
        tr = pd.concat([window.high - window.low, (window.high - previous).abs(), (window.low - previous).abs()], axis=1).max(axis=1)
        return float(tr.tail(self.atr_length).mean())

    def _indicators(self, window):
        typical = (window.high + window.low + window.close) / 3
        sma = typical.rolling(self.cci_length).mean()
        deviation = typical.rolling(self.cci_length).apply(lambda x: (x - x.mean()).abs().mean())
        cci = (typical - sma) / (0.015 * deviation)
        macd_line = window.close.ewm(span=self.macd_fast, adjust=False).mean() - window.close.ewm(span=self.macd_slow, adjust=False).mean()
        histogram = macd_line - macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        return cci, histogram, window.close.ewm(span=self.ema_fast, adjust=False).mean(), window.close.ewm(span=self.ema_slow, adjust=False).mean()

    def generate_signal(self, symbol, bars, context=None):
        window = self._window(symbol, bars)
        if len(window) < self.warmup or symbol in self._active_trades:
            return None
        bar, ts = window.iloc[-1], self._ny(window.index[-1])
        if not self.session_start <= ts.time() < self.session_end or self._entry_counts.get((symbol, ts.date()), 0) >= 1:
            return None
        if any(c not in window for c in ("open", "high", "low", "close", "volume")) or len(window) < 2:
            return None
        previous_close = float(window.close.iloc[-2])
        close, high, low, open_price, volume = map(float, (bar.close, bar.high, bar.low, bar.open, bar.volume))
        if close <= 0 or previous_close <= 0 or volume <= 0 or abs(open_price / previous_close - 1) > self.max_gap_pct or (high - low) / close > self.max_bar_range_pct:
            return None
        cci, histogram, ema_fast, ema_slow = self._indicators(window)
        if pd.isna(cci.iloc[-1]) or pd.isna(cci.iloc[-2]) or pd.isna(histogram.iloc[-2]) or ema_slow.iloc[-1] <= 0:
            return None
        avg_volume = float(window.volume.tail(20).mean())
        if avg_volume <= 0 or volume < avg_volume * self.volume_multiplier:
            return None
        cci_now, cci_prev = float(cci.iloc[-1]), float(cci.iloc[-2])
        hist_now, hist_prev = float(histogram.iloc[-1]), float(histogram.iloc[-2])
        ema_fast_now, ema_slow_now = float(ema_fast.iloc[-1]), float(ema_slow.iloc[-1])
        zone_high = ema_fast_now * (1 + self.zone_proximity_pct)
        zone_low = ema_fast_now * (1 - self.zone_proximity_pct)
        atr = self._atr(window)
        if atr <= 0:
            return None
        touched_zone = float(window.low.tail(self.zone_touch_bars + 1).head(self.zone_touch_bars).min()) <= zone_high
        touched_zone_high = float(window.high.tail(self.zone_touch_bars + 1).head(self.zone_touch_bars).max()) >= zone_low
        if ema_fast_now > ema_slow_now and close > ema_slow_now and touched_zone and cci_prev <= 0 < cci_now and hist_now > hist_prev:
            stop = min(low, close - atr)
            target = close + self.rr_ratio * (close - stop)
            qty = self.risk.calculate_qty(close, stop)
            if qty > 0:
                return self._signal(symbol, "long", close, stop, target, qty, ts, f"EMA {self.ema_fast}/{self.ema_slow} zone pullback, CCI zero-cross, MACD histogram turn")
        if ema_fast_now < ema_slow_now and close < ema_slow_now and touched_zone_high and cci_prev >= 0 > cci_now and hist_now < hist_prev:
            stop = max(high, close + atr)
            target = close - self.rr_ratio * (stop - close)
            qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            if qty > 0:
                return self._signal(symbol, "short", close, stop, target, qty, ts, f"EMA {self.ema_fast}/{self.ema_slow} zone rally, CCI zero-cross down, MACD histogram turn")
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
