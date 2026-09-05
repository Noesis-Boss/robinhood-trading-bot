import pandas as pd


class VWAPLiquidityProxyStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("vwap_liquidity_proxy", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.2))
        self.rr_ratio = float(cfg.get("rr_ratio", 2.0))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.atr_multiplier = float(cfg.get("atr_multiplier", 1.0))
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
        if len(bars) < max(self.atr_length + 2, 20) or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        if not self.session_start <= ts.time() < self.session_end:
            return None
        if self._entry_counts.get((symbol, ts.date()), 0) >= 1:
            return None
        f = bars.copy().tail(max(40, self.atr_length + 5))
        if any(c not in f for c in ("open", "high", "low", "close", "volume")) or f.volume.iloc[-1] <= 0:
            return None
        prior = f.iloc[:-1]
        previous_close = float(prior.close.iloc[-1])
        bar = f.iloc[-1]
        close, high, low = map(float, (bar.close, bar.high, bar.low))
        if previous_close <= 0 or abs(float(bar.open) / previous_close - 1) > self.max_gap_pct or close <= 0:
            return None
        if (high - low) / close > self.max_bar_range_pct:
            return None
        volume_avg = float(prior.volume.tail(20).mean())
        if volume_avg <= 0 or float(bar.volume) < volume_avg * self.volume_multiplier:
            return None
        typical = (f.high + f.low + f.close) / 3
        vwap = (typical * f.volume).cumsum() / f.volume.cumsum()
        if float(vwap.iloc[-1]) <= 0:
            return None
        previous_vwap, current_vwap = float(vwap.iloc[-2]), float(vwap.iloc[-1])
        atr = self._atr(f)
        if atr <= 0:
            return None
        if previous_close <= previous_vwap and close > current_vwap:
            stop = min(low, close - self.atr_multiplier * atr)
            target = close + self.rr_ratio * (close - stop)
            qty = self.risk.calculate_qty(close, stop)
            if qty > 0:
                return self._signal(symbol, "long", close, stop, target, qty, ts, "VWAP reclaim OHLCV proxy")
        if previous_close >= previous_vwap and close < current_vwap:
            stop = max(high, close + self.atr_multiplier * atr)
            target = close - self.rr_ratio * (stop - close)
            qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            if qty > 0:
                return self._signal(symbol, "short", close, stop, target, qty, ts, "VWAP reclaim OHLCV proxy")
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
