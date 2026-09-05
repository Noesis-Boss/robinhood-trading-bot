"""ORB + FVG (paper-research only).

Source: "The One Candle Setup" video skeleton, implemented as a constrained
paper-testing module. Marks the high/low (including wicks) of the first 5-minute
candle at 09:30 ET, waits for a 1-minute close outside that range, then requires
a 3-candle fair-value-gap in the breakout direction. Enters at the close of the
third gap candle, stops at the FVG extreme (wick-inclusive), targets 2R.

Config block: orb_fvg in config.yaml. Never enable for live execution until
proven profitable in paper backtests.
"""

import pandas as pd


class OrbfvgStrategy:
    def __init__(self, config, risk, journal):
        cfg = config.get("orb_fvg", {})
        self.config, self.risk, self.journal = config, risk, journal
        self.timezone = config.get("timezone", "America/New_York")
        self.orb_minutes = int(cfg.get("orb_minutes", 5))
        self.orb_end = pd.Timestamp(cfg.get("orb_end", "09:35")).time()
        self.entry_end = pd.Timestamp(cfg.get("entry_end", "11:30")).time()
        self.session_start = pd.Timestamp(cfg.get("session_start", "09:30")).time()
        self.session_end = pd.Timestamp(cfg.get("session_end", "15:45")).time()
        self.rr_ratio = float(cfg.get("rr_ratio", 2.0))
        self.max_holding_bars = int(cfg.get("max_holding_bars", 90))
        self._active_trades, self._entry_counts = {}, {}
        self._orb = {}
        self._breakout = {}

    def _ny(self, ts):
        ts = pd.Timestamp(ts)
        return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert(self.timezone)

    def _orb_range(self, symbol, bars):
        window = bars[bars.index.time < self.orb_end]
        if len(window) < 1:
            return None
        return float(window.high.max()), float(window.low.min())

    def generate_signal(self, symbol, bars, context=None):
        if symbol in self._active_trades:
            return None
        if any(c not in bars for c in ("open", "high", "low", "close", "volume")):
            return None
        ts = self._ny(bars.index[-1])
        key = (symbol, ts.date())
        if self._entry_counts.get(key, 0) >= 1:
            return None
        if ts.time() < self.orb_end or ts.time() >= self.entry_end:
            return None

        if key not in self._orb:
            orb = self._orb_range(symbol, bars)
            if orb is None:
                return None
            self._orb[key] = orb
        orb_high, orb_low = self._orb[key]

        breakout = self._breakout.get(key)
        if breakout is None:
            closes_outside = bars[bars.index.time >= self.orb_end]
            long_break = closes_outside.close > orb_high
            short_break = closes_outside.close < orb_low
            hits = closes_outside[long_break | short_break]
            if hits.empty:
                return None
            breakout_idx = bars.index.get_loc(hits.index[0])
            direction = "long" if float(hits.close.iloc[0]) > orb_high else "short"
            self._breakout[key] = (breakout_idx, direction)
            breakout = self._breakout[key]
        breakout_idx, direction = breakout

        if len(bars) < breakout_idx + 3:
            return None
        for j in range(breakout_idx, len(bars) - 2):
            c1, c3 = bars.iloc[j], bars.iloc[j + 2]
            entry = float(c3.close)
            if entry <= 0:
                continue
            if direction == "long":
                if float(c3.low) <= float(c1.high) or entry <= orb_high:
                    continue
                stop = float(c1.high)
                target = entry + self.rr_ratio * (entry - stop)
            else:
                if float(c3.high) >= float(c1.low) or entry >= orb_low:
                    continue
                stop = float(c1.low)
                target = entry - self.rr_ratio * (stop - entry)
            risk_per_share = abs(entry - stop)
            if risk_per_share <= 0 or target <= 0:
                continue
            qty = self.risk.calculate_qty(entry, stop, allow_fractional=False)
            if qty <= 0:
                continue
            reason = f"{'bull' if direction == 'long' else 'bear'} FVG after ORB break"
            return self._signal(symbol, direction, entry, stop, target, qty, ts, reason)
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
