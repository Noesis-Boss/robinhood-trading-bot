import pandas as pd


class SneakyPivotStrategy:
    def __init__(self, config, risk, journal):
        self.config = config
        self.risk = risk
        self.journal = journal
        cfg = config.get("sneaky_pivot", {})
        self.timezone = config.get("timezone", "America/New_York")
        self.lookback = int(cfg.get("swing_lookback", 2))
        self.proximity_pct = float(cfg.get("proximity_pct", 0.003))
        self.rr_ratio = float(cfg.get("rr_ratio", 1.0))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.max_holding_bars = int(cfg.get("max_holding_bars", 26))
        raw_entry_limit = config.get("max_entries_per_day", 1)
        self.max_entries_per_day = None if str(raw_entry_limit).lower() in {"unlimited", "0"} else int(raw_entry_limit)
        self._active_trades = {}
        self._entry_counts = {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert(self.timezone)

    def _levels(self, bars, context):
        prior_high = context.get("prior_high") if context else None
        prior_low = context.get("prior_low") if context else None
        highs = bars["high"].rolling(self.lookback * 2 + 1, center=True).max()
        lows = bars["low"].rolling(self.lookback * 2 + 1, center=True).min()
        swing_highs = bars.loc[bars["high"].eq(highs), "high"].dropna().tolist()
        swing_lows = bars.loc[bars["low"].eq(lows), "low"].dropna().tolist()
        upper = [float(prior_high)] if prior_high is not None else []
        lower = [float(prior_low)] if prior_low is not None else []
        upper.extend(float(x) for x in swing_highs)
        lower.extend(float(x) for x in swing_lows)
        return upper, lower

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < max(7, self.lookback * 2 + 3) or symbol in self._active_trades:
            return None
        frame = bars.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        if len(frame) < 4:
            return None
        ts = self._ny(frame.index[-1])
        day = ts.date()
        if not (self.session_start <= ts.time() < self.session_end) or (self.max_entries_per_day is not None and self._entry_counts.get((symbol, day), 0) >= self.max_entries_per_day):
            return None
        upper, lower = self._levels(frame, context)
        if not upper and not lower:
            return None
        a, b, c = frame.iloc[-3], frame.iloc[-2], frame.iloc[-1]
        price = float(c.close)
        upper_level = min((level for level in upper if level >= price), default=None, key=lambda x: x - price)
        lower_level = min((level for level in lower if level <= price), default=None, key=lambda x: price - x)
        proximity = lambda level: level is not None and abs(price - level) / max(abs(level), 0.01) <= self.proximity_pct
        if proximity(lower_level) and a.close >= a.open and b.close >= b.open and c.close > b.high:
            stop = min(float(b.low), float(lower_level))
            if stop >= price:
                return None
            target = upper_level or float(max(frame.high.max(), price))
            if target <= price:
                target = price + self.rr_ratio * (price - stop)
            qty = self.risk.calculate_qty(price, stop)
            if qty > 0:
                return {"symbol": symbol, "direction": "long", "entry": round(price, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "Sneaky Pivot lower-level three-candle long"}
        if proximity(upper_level) and a.close <= a.open and b.close <= b.open and c.close < b.low:
            stop = max(float(b.high), float(upper_level))
            if stop <= price:
                return None
            target = lower_level or float(min(frame.low.min(), price))
            if target >= price:
                target = price - self.rr_ratio * (stop - price)
            qty = self.risk.calculate_qty(price, stop, allow_fractional=False)
            if qty > 0:
                return {"symbol": symbol, "direction": "short", "entry": round(price, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "Sneaky Pivot upper-level three-candle short"}
        return None

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0)
        day = pd.Timestamp(signal["timestamp"]).date()
        key = (symbol, day)
        self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        trade = self._active_trades.get(symbol)
        if not trade:
            return None
        trade["entry_bar_count"] += 1
        bar = bars.iloc[-1]
        ts = self._ny(bars.index[-1])
        high, low, close = map(float, (bar.high, bar.low, bar.close))
        entry, stop, target, direction = trade["entry"], trade["stop"], trade["target"], trade["direction"]
        exit_price, reason = None, None
        if direction == "long":
            if low <= stop: exit_price, reason = stop, "stop_loss"
            elif high >= target: exit_price, reason = target, "target_hit"
        else:
            if high >= stop: exit_price, reason = stop, "stop_loss"
            elif low <= target: exit_price, reason = target, "target_hit"
        if exit_price is None and (trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end):
            exit_price, reason = close, "max_holding_bars" if trade["entry_bar_count"] >= self.max_holding_bars else "session_close"
        if exit_price is None:
            return None
        pnl = (exit_price - entry) * trade["qty"] if direction == "long" else (entry - exit_price) * trade["qty"]
        result = {"symbol": symbol, "direction": direction, "entry": entry, "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.rr_ratio, "reason": reason, "exit_time": ts.isoformat()}
        self.risk.update_cash(pnl)
        if self.journal is not None: self.journal.log_trade(result)
        del self._active_trades[symbol]
        return result
