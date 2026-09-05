import pandas as pd


class AuctionFlowProxyStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("auction_flow_proxy", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.trend_length = int(cfg.get("trend_length", 20)); self.location_lookback = int(cfg.get("location_lookback", 40))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.0)); self.rr_ratio = float(cfg.get("rr_ratio", 2.0)); self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.max_gap_pct = float(cfg.get("max_gap_pct", 0.08))
        self.max_bar_range_pct = float(cfg.get("max_bar_range_pct", 0.08))
        self.confirm_rejection = bool(cfg.get("confirm_rejection", True))
        raw = config.get("max_entries_per_day", 1)
        self.max_entries_per_day = None if str(raw).lower() in {"unlimited", "0"} else int(raw)
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < max(self.trend_length, 10) or symbol in self._active_trades: return None
        ts = self._ny(bars.index[-1])
        if not self.session_start <= ts.time() < self.session_end: return None
        if self.max_entries_per_day is not None and self._entry_counts.get((symbol, ts.date()), 0) >= self.max_entries_per_day: return None
        f = bars.tail(max(self.location_lookback, self.trend_length + 5)); prior = f.iloc[:-1]
        if prior.empty: return None
        bar = f.iloc[-1]; close, high, low = map(float, (bar.close, bar.high, bar.low)); swing_high, swing_low = float(prior.high.max()), float(prior.low.min()); span = swing_high - swing_low
        if span <= 0: return None
        previous_close = float(prior.close.iloc[-1])
        if previous_close <= 0 or abs(float(bar.open) / previous_close - 1) > self.max_gap_pct: return None
        if close <= 0 or (high - low) / close > self.max_bar_range_pct: return None
        fib382, fib618 = swing_low + span * .382, swing_low + span * .618
        sma = float(f.close.tail(self.trend_length).mean()); avg_vol = float(prior.volume.tail(20).mean()) if "volume" in prior else 0
        volume_ok = avg_vol <= 0 or float(bar.get("volume", 0)) >= avg_vol * self.volume_multiplier
        body = abs(close - float(bar.open)); upper = high - max(close, float(bar.open)); lower = min(close, float(bar.open)) - low
        vwap = (f.close * f.volume).sum() / f.volume.sum() if "volume" in f and f.volume.sum() > 0 else close
        long_confirmation = not self.confirm_rejection or close > previous_close
        short_confirmation = not self.confirm_rejection or close < previous_close
        if low < fib382 and close > fib382 and lower >= body * .5 and close > sma and close > vwap and volume_ok and long_confirmation:
            stop, target = low, close + self.rr_ratio * (close - low); qty = self.risk.calculate_qty(close, stop)
            if qty > 0: return self._signal(symbol, "long", close, stop, target, qty, ts, "discount rejection OHLCV proxy")
        if high > fib618 and close < fib618 and upper >= body * .5 and close < sma and close < vwap and volume_ok and short_confirmation:
            stop, target = high, close - self.rr_ratio * (high - close); qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            if qty > 0: return self._signal(symbol, "short", close, stop, target, qty, ts, "premium rejection OHLCV proxy")
        return None

    def _signal(self, symbol, direction, entry, stop, target, qty, ts, reason):
        return {"symbol": symbol, "direction": direction, "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": reason}

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0); key = (symbol, pd.Timestamp(signal["timestamp"]).date()); self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        trade = self._active_trades.get(symbol)
        if not trade: return None
        trade["entry_bar_count"] += 1; bar = bars.iloc[-1]; ts = self._ny(bars.index[-1]); high, low, close = map(float, (bar.high, bar.low, bar.close)); direction = trade["direction"]
        if direction == "long": exit_price, reason = ((trade["stop"], "stop_loss") if low <= trade["stop"] else (trade["target"], "target_hit") if high >= trade["target"] else (None, None))
        else: exit_price, reason = ((trade["stop"], "stop_loss") if high >= trade["stop"] else (trade["target"], "target_hit") if low <= trade["target"] else (None, None))
        if exit_price is None and (trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end): exit_price, reason = close, "session_close" if ts.time() >= self.session_end else "max_holding_bars"
        if exit_price is None: return None
        pnl = (exit_price - trade["entry"]) * trade["qty"] if direction == "long" else (trade["entry"] - exit_price) * trade["qty"]
        result = {"symbol": symbol, "direction": direction, "entry": trade["entry"], "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.rr_ratio, "reason": reason, "exit_time": ts.isoformat()}; self.risk.update_cash(pnl)
        if self.journal: self.journal.log_trade(result)
        del self._active_trades[symbol]; return result
