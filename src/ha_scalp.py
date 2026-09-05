import pandas as pd


class HAScalpStrategy:
    def __init__(self, config, risk, journal):
        self.config = config
        cfg = config.get("ha_scalp", {})
        self.risk, self.journal = risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.ema_length = int(cfg.get("ema_length", 100))
        self.doji_ratio = float(cfg.get("doji_body_ratio", 0.35))
        self.min_wick_ratio = float(cfg.get("min_wick_ratio", 0.2))
        self.min_volume_ratio = float(cfg.get("min_volume_ratio", 1.0))
        self.rr_ratio = float(cfg.get("rr_ratio", 1.0))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        raw_entry_limit = config.get("max_entries_per_day", 1)
        self.max_entries_per_day = None if str(raw_entry_limit).lower() in {"unlimited", "0"} else int(raw_entry_limit)
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        if ts.tzinfo is None: ts = ts.tz_localize("UTC")
        return ts.tz_convert(self.timezone)

    def _ha(self, bars):
        f = bars.copy()
        f["ha_close"] = (f.open + f.high + f.low + f.close) / 4
        ha_open = []
        for i, row in f.iterrows():
            ha_open.append((row.open + row.close) / 2 if not ha_open else (ha_open[-1] + f.loc[i, "ha_close"]) / 2)
        f["ha_open"] = ha_open
        f["ha_high"] = f[["high", "ha_open", "ha_close"]].max(axis=1)
        f["ha_low"] = f[["low", "ha_open", "ha_close"]].min(axis=1)
        f["ema"] = f.close.ewm(span=self.ema_length, adjust=False).mean()
        return f

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < 5 or symbol in self._active_trades: return None
        source = bars if self.config_interval_1m() else bars.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        f = self._ha(source.tail(300))
        ts = self._ny(f.index[-1]); day = ts.date()
        if not (self.session_start <= ts.time() < self.session_end) or (self.max_entries_per_day is not None and self._entry_counts.get((symbol, day), 0) >= self.max_entries_per_day): return None
        a, b, c = f.iloc[-3], f.iloc[-2], f.iloc[-1]
        body = abs(float(c.ha_close - c.ha_open)); span = max(float(c.ha_high - c.ha_low), 1e-9)
        avg_vol = float(f.volume.iloc[:-1].tail(20).mean()) if "volume" in f else 0
        high_volume = avg_vol <= 0 or float(c.volume) >= avg_vol * self.min_volume_ratio
        doji = body / span <= self.doji_ratio
        lower_wick = float(min(c.ha_open, c.ha_close) - c.ha_low) / span
        upper_wick = float(c.ha_high - max(c.ha_open, c.ha_close)) / span
        uptrend = float(c.close) > float(c.ema)
        downtrend = float(c.close) < float(c.ema)
        buy_pullback = a.ha_close < a.ha_open and b.ha_close < b.ha_open and a.ha_high <= max(a.ha_open, a.ha_close) and b.ha_high <= max(b.ha_open, b.ha_close)
        sell_pullback = a.ha_close > a.ha_open and b.ha_close > b.ha_open and a.ha_low >= min(a.ha_open, a.ha_close) and b.ha_low >= min(b.ha_open, b.ha_close)
        entry = float(c.close)
        if doji and lower_wick >= self.min_wick_ratio and high_volume and uptrend and buy_pullback:
            stop, target = float(c.low), entry + self.rr_ratio * (entry - float(c.low))
            qty = self.risk.calculate_qty(entry, stop)
            if qty > 0: return {"symbol": symbol, "direction": "long", "entry": entry, "stop": stop, "target": target, "qty": qty, "timestamp": ts.isoformat(), "reason": "Heikin-Ashi 100EMA high-volume doji long"}
        if doji and upper_wick >= self.min_wick_ratio and high_volume and downtrend and sell_pullback:
            stop, target = float(c.high), entry - self.rr_ratio * (float(c.high) - entry)
            qty = self.risk.calculate_qty(entry, stop, allow_fractional=False)
            if qty > 0: return {"symbol": symbol, "direction": "short", "entry": entry, "stop": stop, "target": target, "qty": qty, "timestamp": ts.isoformat(), "reason": "Heikin-Ashi 100EMA high-volume doji short"}
        return None

    def config_interval_1m(self):
        return self.config.get("ha_scalp", {}).get("backtest_interval", "5m") == "1m"

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0)
        day = pd.Timestamp(signal["timestamp"]).date()
        key = (symbol, day)
        self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        t = self._active_trades.get(symbol)
        if not t: return None
        t["entry_bar_count"] += 1; bar = bars.iloc[-1]; ts = self._ny(bars.index[-1])
        high, low, close = map(float, (bar.high, bar.low, bar.close)); entry, stop, target = t["entry"], t["stop"], t["target"]
        if t["direction"] == "long": exit_price, reason = ((stop, "stop_loss") if low <= stop else (target, "target_hit") if high >= target else (None, None))
        else: exit_price, reason = ((stop, "stop_loss") if high >= stop else (target, "target_hit") if low <= target else (None, None))
        if exit_price is None and ts.time() >= self.session_end: exit_price, reason = close, "session_close"
        if exit_price is None: return None
        pnl = (exit_price - entry) * t["qty"] if t["direction"] == "long" else (entry - exit_price) * t["qty"]
        result = {"symbol": symbol, "direction": t["direction"], "entry": entry, "exit_price": round(exit_price, 2), "qty": t["qty"], "pnl": round(pnl, 2), "rr": self.rr_ratio, "reason": reason, "exit_time": ts.isoformat()}
        self.risk.update_cash(pnl)
        if self.journal: self.journal.log_trade(result)
        del self._active_trades[symbol]
        return result
