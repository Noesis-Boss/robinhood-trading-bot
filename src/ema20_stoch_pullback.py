"""Research-only 20 EMA pullback strategy with Stochastic confirmation."""

import pandas as pd


class Ema20StochPullbackStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("ema20_stoch_pullback", {})
        self.risk, self.journal = risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.ema_length = int(cfg.get("ema_length", 20))
        self.k_length, self.d_length, self.slowing = (int(cfg.get(k, v)) for k, v in (("k_length", 8), ("d_length", 5), ("slowing", 3)))
        self.deviation_pct = float(cfg.get("deviation_pct", 0.002))
        self.target_fraction = float(cfg.get("target_fraction", 0.25))
        self.atr_length = int(cfg.get("atr_length", 14))
        self.atr_multiplier = float(cfg.get("atr_multiplier", 1.0))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 0.0))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 30))
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:35")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def generate_signal(self, symbol, bars, context=None):
        minimum = max(self.ema_length + self.slowing + self.d_length + 3, self.atr_length + 3, 30)
        if len(bars) < minimum or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1]); key = (symbol, ts.date())
        if not self.session_start <= ts.time() < self.session_end or self._entry_counts.get(key, 0) >= 1:
            return None
        w = bars.tail(max(60, minimum)).copy()
        if any(c not in w for c in ("open", "high", "low", "close", "volume")):
            return None
        close, prev_close = float(w.close.iloc[-1]), float(w.close.iloc[-2])
        if close <= 0 or prev_close <= 0 or float(w.volume.iloc[-1]) <= 0:
            return None
        ema = w.close.ewm(span=self.ema_length, adjust=False).mean()
        low_high = w.high.rolling(self.k_length).max(); low_low = w.low.rolling(self.k_length).min()
        raw_k = 100 * (w.close - low_low) / (low_high - low_low).replace(0, float("nan"))
        k = raw_k.rolling(self.slowing).mean(); d = k.rolling(self.d_length).mean()
        if pd.isna(k.iloc[-2]) or pd.isna(d.iloc[-2]) or pd.isna(k.iloc[-1]) or pd.isna(d.iloc[-1]):
            return None
        bull_cross = float(k.iloc[-2]) <= float(d.iloc[-2]) and float(k.iloc[-1]) > float(d.iloc[-1])
        bear_cross = float(k.iloc[-2]) >= float(d.iloc[-2]) and float(k.iloc[-1]) < float(d.iloc[-1])
        current_ema, previous_ema = float(ema.iloc[-1]), float(ema.iloc[-2])
        touch = current_ema * self.deviation_pct
        long_setup = prev_close < previous_ema - touch and close > prev_close and close < current_ema and bull_cross and current_ema > previous_ema
        short_setup = prev_close > previous_ema + touch and close < prev_close and close > current_ema and bear_cross and current_ema < previous_ema
        if self.volume_multiplier:
            avg_volume = float(w.volume.iloc[:-1].tail(20).mean())
            if avg_volume <= 0 or float(w.volume.iloc[-1]) < avg_volume * self.volume_multiplier:
                return None
        previous = w.close.shift(1)
        tr = pd.concat([w.high - w.low, (w.high - previous).abs(), (w.low - previous).abs()], axis=1).max(axis=1)
        atr = float(tr.tail(self.atr_length).mean())
        if atr <= 0:
            return None
        if long_setup:
            stop = min(float(w.low.iloc[-4:-1].min()), close - self.atr_multiplier * atr)
            target = close + self.target_fraction * (current_ema - close)
            qty = self.risk.calculate_qty(close, stop)
            if qty > 0 and target > close:
                return self._signal(symbol, "long", close, stop, target, qty, ts)
        if short_setup:
            stop = max(float(w.high.iloc[-4:-1].max()), close + self.atr_multiplier * atr)
            target = close + self.target_fraction * (current_ema - close)
            qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            if qty > 0 and target < close:
                return self._signal(symbol, "short", close, stop, target, qty, ts)
        return None

    def _signal(self, symbol, direction, entry, stop, target, qty, ts):
        return {"symbol": symbol, "direction": direction, "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2), "qty": qty, "timestamp": ts.isoformat(), "reason": "20 EMA deviation pullback with Stochastic 8/5/3"}

    def on_trade_entered(self, symbol, signal):
        self._active_trades[symbol] = dict(signal, entry_bar_count=0)
        key = (symbol, pd.Timestamp(signal["timestamp"]).date()); self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def check_exit(self, symbol, bars, broker):
        trade = self._active_trades.get(symbol)
        if not trade: return None
        trade["entry_bar_count"] += 1; bar, ts = bars.iloc[-1], self._ny(bars.index[-1])
        high, low, close = map(float, (bar.high, bar.low, bar.close)); long = trade["direction"] == "long"
        exit_price, reason = ((trade["stop"], "stop_loss") if (low <= trade["stop"] if long else high >= trade["stop"]) else (trade["target"], "target_hit") if (high >= trade["target"] if long else low <= trade["target"]) else (None, None))
        if exit_price is None and (trade["entry_bar_count"] >= self.max_holding_bars or ts.time() >= self.session_end): exit_price, reason = close, "session_close" if ts.time() >= self.session_end else "max_holding_bars"
        if exit_price is None: return None
        pnl = (exit_price - trade["entry"]) * trade["qty"] if long else (trade["entry"] - exit_price) * trade["qty"]
        result = {"symbol": symbol, "direction": trade["direction"], "entry": trade["entry"], "exit_price": round(exit_price, 2), "qty": trade["qty"], "pnl": round(pnl, 2), "rr": self.target_fraction, "reason": reason, "exit_time": ts.isoformat()}
        self.risk.update_cash(pnl)
        if self.journal: self.journal.log_trade(result)
        del self._active_trades[symbol]; return result
