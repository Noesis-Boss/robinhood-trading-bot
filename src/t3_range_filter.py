import pandas as pd


class T3RangeFilterStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("t3_range_filter", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.t3_length = int(cfg.get("t3_length", 8)); self.t3_factor = float(cfg.get("t3_factor", .7))
        self.range_length = int(cfg.get("range_length", 14)); self.range_multiplier = float(cfg.get("range_multiplier", 2.0))
        self.atr_length = int(cfg.get("atr_length", 14)); self.atr_multiplier = float(cfg.get("atr_multiplier", 1.5))
        self.target_r = float(cfg.get("target_r", 2.0)); self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.max_gap_pct = float(cfg.get("max_gap_pct", .08)); self.max_bar_range_pct = float(cfg.get("max_bar_range_pct", .08))
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _t3(self, close):
        v = self.t3_factor; e1 = close.ewm(span=self.t3_length, adjust=False).mean(); e2 = e1.ewm(span=self.t3_length, adjust=False).mean(); e3 = e2.ewm(span=self.t3_length, adjust=False).mean(); e4 = e3.ewm(span=self.t3_length, adjust=False).mean(); e5 = e4.ewm(span=self.t3_length, adjust=False).mean(); e6 = e5.ewm(span=self.t3_length, adjust=False).mean()
        c1 = -v ** 3; c2 = 3 * v ** 2 + 3 * v ** 3; c3 = -6 * v ** 2 - 3 * v - 3 * v ** 3; c4 = 1 + 3 * v + 3 * v ** 2 + v ** 3
        return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < max(self.t3_length * 3, self.atr_length + 3, 30) or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        if not self.session_start <= ts.time() < self.session_end or self._entry_counts.get((symbol, ts.date()), 0) >= 1:
            return None
        f = bars.copy().tail(100)
        if any(c not in f for c in ("open", "high", "low", "close", "volume")) or f.volume.iloc[-1] <= 0:
            return None
        prior = f.iloc[:-1]; bar = f.iloc[-1]; close = float(bar.close); previous_close = float(prior.close.iloc[-1])
        if previous_close <= 0 or abs(float(bar.open) / previous_close - 1) > self.max_gap_pct or close <= 0 or (float(bar.high) - float(bar.low)) / close > self.max_bar_range_pct:
            return None
        t3 = self._t3(f.close); smooth_range = (f.high - f.low).ewm(span=self.range_length, adjust=False).mean() * self.range_multiplier
        filt = f.close.copy();
        for i in range(1, len(f)):
            step = float(smooth_range.iloc[i]); prev = float(filt.iloc[i - 1]); price = float(f.close.iloc[i]); filt.iloc[i] = max(prev - step, min(prev + step, price))
        atr = float(pd.concat([f.high - f.low, (f.high - f.close.shift(1)).abs(), (f.low - f.close.shift(1)).abs()], axis=1).max(axis=1).tail(self.atr_length).mean())
        green = close > float(filt.iloc[-1]) and float(filt.iloc[-1]) >= float(filt.iloc[-2])
        t3_up = close > float(t3.iloc[-1]) and float(t3.iloc[-1]) >= float(t3.iloc[-2])
        if not (green and t3_up and previous_close <= float(t3.iloc[-2]) and atr > 0):
            return None
        stop = close - self.atr_multiplier * atr; target = close + self.target_r * (close - stop); qty = self.risk.calculate_qty(close, stop)
        return self._signal(symbol, close, stop, target, qty, ts) if qty > 0 else None

    def _signal(self, symbol, entry, stop, target, qty, ts):
        return {"symbol": symbol, "direction": "long", "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "T3 and green range-filter research signal"}

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0); key = (symbol, pd.Timestamp(signal["timestamp"]).date()); self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        trade = self._active_trades.get(symbol)
        if not trade: return None
        trade["entry_bar_count"] += 1; bar = bars.iloc[-1]; ts = self._ny(bars.index[-1]); high, low, close = map(float, (bar.high, bar.low, bar.close))
        exit_price, reason = ((trade["stop"], "stop_loss") if low <= trade["stop"] else (trade["target"], "target_hit") if high >= trade["target"] else (None, None))
        if exit_price is None and (trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end): exit_price, reason = close, "session_close" if ts.time() >= self.session_end else "max_holding_bars"
        if exit_price is None: return None
        pnl = (exit_price - trade["entry"]) * trade["qty"]; result = {"symbol": symbol, "direction": "long", "entry": trade["entry"], "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.target_r, "reason": reason, "exit_time": ts.isoformat()}; self.risk.update_cash(pnl)
        if self.journal: self.journal.log_trade(result)
        del self._active_trades[symbol]; return result
