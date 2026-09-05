import pandas as pd


class RossMomentumStrategy:
    def __init__(self, config: dict, risk, journal):
        self.config = config
        self.risk = risk
        self.journal = journal
        cfg = config.get("ross_momentum", {})
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "08:00")).time()
        self.entry_cutoff = pd.Timestamp(cfg.get("entry_cutoff", "10:00")).time()
        self.min_price = float(cfg.get("min_price", 1.0))
        self.min_gap_pct = float(cfg.get("min_gap_pct", 0.03))
        self.relative_volume = float(cfg.get("min_relative_volume", cfg.get("relative_volume", 2.0)))
        self.ema_length = int(cfg.get("ema_length", 9))
        self.pullback_lookback = int(cfg.get("pullback_lookback", 6))
        self.min_impulse_pct = float(cfg.get("min_impulse_pct", 0.04))
        self.volume_ratio = float(cfg.get("volume_ratio", 1.2))
        self.rr_ratio = float(cfg.get("rr_ratio", 1.5))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 18))
        self.breakeven = bool(cfg.get("trailing_stop_breakeven", True))
        raw_entry_limit = config.get("max_entries_per_day", 1)
        self.max_entries_per_day = None if str(raw_entry_limit).lower() in {"unlimited", "0"} else int(raw_entry_limit)
        self._active_trades = {}
        self._entry_counts = {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert(self.timezone)

    def _indicators(self, bars):
        frame = bars.copy()
        frame["ema"] = frame["close"].ewm(span=self.ema_length, adjust=False).mean()
        typical = (frame["high"] + frame["low"] + frame["close"]) / 3
        volume = frame.get("volume", pd.Series(0.0, index=frame.index)).fillna(0)
        frame["vwap"] = (typical * volume).cumsum() / volume.cumsum().replace(0, pd.NA)
        frame["vwap"] = frame["vwap"].ffill().fillna(frame["close"])
        return frame

    def _session_vwap(self, bars):
        return self._indicators(bars)["vwap"]

    def _ema(self, closes):
        return closes.ewm(span=self.ema_length, adjust=False).mean()

    def _session_vwap(self, bars):
        return self._indicators(bars)["vwap"]

    def _avg_volume(self, bars):
        volume = bars.get("volume")
        if volume is None or volume.empty:
            return 0.0
        return float(volume.iloc[:-1].tail(20).mean())

    def generate_signal(self, symbol, bars, context=None):
        if len(bars) < max(self.ema_length + 2, self.pullback_lookback + 3):
            return None
        frame = self._indicators(bars)
        ts = self._ny(frame.index[-1])
        day = ts.date()
        if ts.time() < self.session_start or ts.time() >= self.entry_cutoff:
            return None
        if symbol in self._active_trades or (self.max_entries_per_day is not None and self._entry_counts.get((symbol, day), 0) >= self.max_entries_per_day):
            return None
        latest = frame.iloc[-1]
        prior = frame.iloc[:-1]
        price = float(latest.close)
        if price < self.min_price:
            return None
        avg_vol = self._avg_volume(frame)
        current_vol = float(latest.get("volume", 0))
        if avg_vol and current_vol < avg_vol * self.relative_volume:
            return None
        recent = prior.tail(self.pullback_lookback + 1)
        if len(recent) < self.pullback_lookback + 1:
            return None
        impulse = prior.iloc[: max(2, len(prior) - self.pullback_lookback + 1)]
        if impulse.empty:
            return None
        impulse_high = float(impulse.high.max())
        impulse_low = float(impulse.low.min())
        pullback = recent.iloc[:-1]
        pull_high = float(pullback.high.max())
        pull_low = float(pullback.low.min())
        pull_vol = float(pullback.get("volume", pd.Series(0, index=pullback.index)).mean())
        if pull_vol and current_vol < pull_vol * self.volume_ratio:
            return None
        bullish = (impulse_high / max(float(impulse.close.iloc[0]), 0.01) - 1) >= self.min_impulse_pct
        bearish = (1 - impulse_low / max(float(impulse.close.iloc[0]), 0.01)) >= self.min_impulse_pct
        if bullish and price > float(latest.ema) and price > float(latest.vwap) and price > pull_high:
            stop = pull_low
            if stop >= price:
                return None
            target = price + self.rr_ratio * (price - stop)
            qty = self.risk.calculate_qty(price, stop)
            if qty > 0:
                return {"symbol": symbol, "direction": "long", "entry": round(price, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "Ross momentum first pullback long: VWAP/9EMA reclaim with volume"}
        if bearish and price < float(latest.ema) and price < float(latest.vwap) and price < pull_low:
            stop = pull_high
            if stop <= price:
                return None
            target = price - self.rr_ratio * (stop - price)
            qty = self.risk.calculate_qty(price, stop, allow_fractional=False)
            if qty > 0:
                return {"symbol": symbol, "direction": "short", "entry": round(price, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "Ross momentum first pullback short: VWAP/9EMA rejection with volume"}
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
        latest = bars.iloc[-1]
        ts = self._ny(bars.index[-1])
        high, low, close = map(float, (latest.high, latest.low, latest.close))
        entry, stop, target = trade["entry"], trade["stop"], trade["target"]
        direction = trade["direction"]
        risk = abs(entry - stop)
        if self.breakeven and ((direction == "long" and high >= entry + risk) or (direction == "short" and low <= entry - risk)):
            trade["stop"] = entry
            stop = entry
        exit_price = None
        reason = None
        if ts.time() >= self.entry_cutoff:
            exit_price, reason = close, "entry_cutoff"
        elif trade["entry_bar_count"] >= self.max_holding_bars:
            exit_price, reason = close, "max_holding_bars"
        elif direction == "long":
            if low <= stop: exit_price, reason = stop, "stop_loss"
            elif high >= target: exit_price, reason = target, "target_hit"
        else:
            if high >= stop: exit_price, reason = stop, "stop_loss"
            elif low <= target: exit_price, reason = target, "target_hit"
        if exit_price is None:
            return None
        pnl = (exit_price - entry) * trade["qty"] if direction == "long" else (entry - exit_price) * trade["qty"]
        result = {"symbol": symbol, "direction": direction, "entry": entry, "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.rr_ratio, "reason": reason, "exit_time": ts.isoformat()}
        self.risk.update_cash(pnl)
        if self.journal is not None:
            self.journal.log_trade(result)
        del self._active_trades[symbol]
        return result
