import pandas as pd


class CandleNarrativeStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("candle_narrative", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:35")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "12:30")).time()
        self.trend_ema = int(cfg.get("trend_ema", 20))
        self.zone_lookback = int(cfg.get("zone_lookback", 30))
        self.pivot_left_right = int(cfg.get("pivot_left_right", 3))
        self.impulse_lookback = int(cfg.get("impulse_lookback", 4))
        self.pullback_lookback = int(cfg.get("pullback_lookback", 3))
        self.asymmetry_ratio = float(cfg.get("asymmetry_ratio", 1.5))
        self.min_engulf_ratio = float(cfg.get("min_engulf_ratio", 1.1))
        self.pin_wick_ratio = float(cfg.get("pin_wick_ratio", 2.0))
        self.min_body_ratio = float(cfg.get("min_body_ratio", .6))
        self.close_location = float(cfg.get("close_location", .75))
        self.volume_multiplier = float(cfg.get("volume_multiplier", 1.2))
        self.atr_stop_buffer = float(cfg.get("atr_stop_buffer", .25))
        self.zone_tolerance_atr = float(cfg.get("zone_tolerance_atr", .5))
        self.rr_ratio = float(cfg.get("rr_ratio", 2))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 24))
        self.max_gap_pct = float(cfg.get("max_gap_pct", .08))
        self.max_bar_range_pct = float(cfg.get("max_bar_range_pct", .08))
        self._active_trades, self._entry_counts = {}, {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _atr(self, bars):
        previous = bars.close.shift(1)
        tr = pd.concat([bars.high - bars.low, (bars.high - previous).abs(), (bars.low - previous).abs()], axis=1).max(axis=1)
        return float(tr.tail(14).mean())

    def _pivots(self, highs, lows):
        k = self.pivot_left_right
        supports, resistances = [], []
        for i in range(k, len(highs) - k):
            if lows.iloc[i] == lows.iloc[i - k:i + k + 1].min():
                supports.append(float(lows.iloc[i]))
            if highs.iloc[i] == highs.iloc[i - k:i + k + 1].max():
                resistances.append(float(highs.iloc[i]))
        return supports, resistances

    def _nearest_below(self, levels, price):
        below = [x for x in levels if x < price]
        return max(below) if below else None

    def _nearest_above(self, levels, price):
        above = [x for x in levels if x > price]
        return min(above) if above else None

    def generate_signal(self, symbol, bars, context=None):
        minimum = max(self.zone_lookback + self.pivot_left_right * 2 + 2, self.trend_ema + 5, 40)
        if len(bars) < minimum or symbol in self._active_trades:
            return None
        ts = self._ny(bars.index[-1])
        if not self.session_start <= ts.time() < self.session_end or self._entry_counts.get((symbol, ts.date()), 0) >= 1:
            return None
        f = bars.copy().tail(minimum + 20)
        if any(c not in f for c in ("open", "high", "low", "close", "volume")):
            return None
        bar, prior = f.iloc[-1], f.iloc[:-1]
        open_price, high, low, close = map(float, (bar.open, bar.high, bar.low, bar.close))
        previous_close = float(prior.close.iloc[-1])
        range_ = high - low
        if close <= 0 or previous_close <= 0 or float(bar.volume) <= 0 or range_ <= 0:
            return None
        if abs(open_price / previous_close - 1) > self.max_gap_pct or range_ / close > self.max_bar_range_pct:
            return None
        avg_volume = float(prior.volume.tail(20).mean())
        if avg_volume <= 0 or float(bar.volume) < avg_volume * self.volume_multiplier:
            return None
        ema = float(f.close.ewm(span=self.trend_ema, adjust=False).mean().iloc[-1])
        atr = self._atr(f)
        if atr <= 0:
            return None
        body = abs(close - open_price)
        upper_wick, lower_wick = high - max(open_price, close), min(open_price, close) - low
        close_pos = (close - low) / range_
        prior_body = abs(float(prior.close.iloc[-1]) - float(prior.open.iloc[-1]))
        engulf_bull = close > open_price and body >= prior_body * self.min_engulf_ratio and close > float(prior.high.iloc[-1]) * .999 and open_price <= float(prior.close.iloc[-1])
        engulf_bear = close < open_price and body >= prior_body * self.min_engulf_ratio and close < float(prior.low.iloc[-1]) * 1.001 and open_price >= float(prior.close.iloc[-1])
        pin_bull = lower_wick >= body * self.pin_wick_ratio and close_pos <= 1 - self.close_location
        pin_bear = upper_wick >= body * self.pin_wick_ratio and close_pos >= self.close_location
        momentum_bull = body / range_ >= self.min_body_ratio and close_pos >= self.close_location
        momentum_bear = body / range_ >= self.min_body_ratio and close_pos <= 1 - self.close_location
        impulse = float(prior.tail(self.impulse_lookback).apply(lambda r: abs(r.close - r.open), axis=1).sum())
        pullback = float(prior.tail(self.pullback_lookback).apply(lambda r: abs(r.close - r.open), axis=1).sum())
        supports, resistances = self._pivots(f.high, f.low)
        price_ref = float(prior.close.iloc[-1])
        support, resistance = self._nearest_below(supports, price_ref), self._nearest_above(resistances, price_ref)
        bullish_story = (engulf_bull or momentum_bull) and close > ema
        bearish_story = (engulf_bear or momentum_bear) and close < ema
        bull_pin = pin_bull and support is not None and low <= support + atr * self.zone_tolerance_atr
        bear_pin = pin_bear and resistance is not None and high >= resistance - atr * self.zone_tolerance_atr
        asym_ok = pullback <= 0 or impulse / pullback >= self.asymmetry_ratio
        if (bullish_story or bull_pin) and close > ema and asym_ok and support is not None:
            stop = min(low, support) - atr * self.atr_stop_buffer
            qty = self.risk.calculate_qty(close, stop)
            reason = "bull_pin_rejection" if bull_pin else "bull_continuation_candle"
            if qty > 0:
                return self._signal(symbol, "long", close, stop, close + self.rr_ratio * (close - stop), qty, ts, reason)
        if (bearish_story or bear_pin) and close < ema and asym_ok and resistance is not None:
            stop = max(high, resistance) + atr * self.atr_stop_buffer
            qty = self.risk.calculate_qty(close, stop, allow_fractional=False)
            reason = "bear_pin_rejection" if bear_pin else "bear_continuation_candle"
            if qty > 0:
                return self._signal(symbol, "short", close, stop, close - self.rr_ratio * (stop - close), qty, ts, reason)
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
