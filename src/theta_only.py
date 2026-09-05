import json
from pathlib import Path

import pandas as pd

from .theta_farming import ThetaFarmer


PRESETS = {
    "conservative": {"target_pop": 0.85, "min_days_to_expiry": 2, "max_days_to_expiry": 5, "max_risk_per_trade_pct": 0.01},
    "balanced": {"target_pop": 0.80, "min_days_to_expiry": 3, "max_days_to_expiry": 7, "max_risk_per_trade_pct": 0.02},
    "aggressive": {"target_pop": 0.70, "min_days_to_expiry": 7, "max_days_to_expiry": 14, "max_risk_per_trade_pct": 0.05},
}


class ThetaOnlyStrategy:
    def __init__(self, config, risk, journal):
        preset_name = str(config.get("theta_aggressiveness", "balanced")).lower()
        if preset_name not in PRESETS:
            raise ValueError("theta_aggressiveness must be conservative, balanced, or aggressive")
        self.preset_name = preset_name
        self.preset = PRESETS[preset_name]
        self.risk = risk
        self.journal = journal
        theta_config = {**config.get("theta_farming", {}), **self.preset}
        self.farmer = ThetaFarmer(theta_config)
        self._traded_days = set()
        self.selection_mode = "fixed_fallback"

    def symbols_for_run(self, symbols, scan_path="daily_universe.json"):
        try:
            data = json.loads(Path(scan_path).read_text())
            candidates = data.get("actionable_symbols") or data.get("selected_symbols") or []
            candidates = [str(symbol).upper() for symbol in candidates if symbol]
            selected = [symbol for symbol in candidates if symbol in symbols]
            if selected:
                self.selection_mode = "scanner"
                return selected
        except (OSError, json.JSONDecodeError):
            pass
        return symbols

    def generate_trade(self, symbol, day_data):
        if len(day_data) < 2:
            return None
        day = pd.Timestamp(day_data.index[-1]).date()
        key = (symbol, day)
        if key in self._traded_days:
            return None
        first = float(day_data["close"].iloc[0])
        last = float(day_data["close"].iloc[-1])
        move = (last - first) / max(abs(first), 0.01)
        if abs(move) < 0.005:
            return None
        direction = "long" if move > 0 else "short"
        trade = self.farmer.generate_trade(symbol, last, direction)
        if not trade:
            return None
        executed = self.farmer.execute_trade(trade, capital=self.risk.capital)
        if not executed:
            return None
        self._traded_days.add(key)
        pnl = self.farmer.simulate_expiry(trade, executed["contracts"])
        self.risk.update_cash(pnl)
        result = {"symbol": symbol, "trade_type": "theta_spread", "entry": last, "direction": direction, "exit_price": last, "qty": executed["contracts"], "pnl": pnl, "rr": 0, "reason": "theta_only_spread", "dte": trade["dte"], "selection_mode": self.selection_mode, "aggressiveness": self.preset_name}
        if self.journal:
            self.journal.log_trade(result)
        return result
