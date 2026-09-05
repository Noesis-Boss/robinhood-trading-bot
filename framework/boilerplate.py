"""Universal Strategy Boilerplate for the Robinhood Trading Bot.

Wraps any strategy with:
- Realistic risk management (fixed fractional sizing, max daily loss, max drawdown)
- Position sizing from config
- Execution realism (slippage + spread)
- Session filtering (NY/London hours)
- Per-symbol, per-day entry limits
- Active trade tracking

All strategies follow the same interface:
  generate_signal(symbol, bars, context) -> dict | None
  check_exit(symbol, bars, broker) -> dict | None
  on_trade_entered(symbol, signal) -> None
"""
import logging
from dataclasses import dataclass, field

import pandas as pd

from src.risk import RiskManager
from src.journal import TradeJournal
from src.execution_realism import finalize_trade, valid_bar


@dataclass
class BoilerplateConfig:
    """Configuration for the strategy boilerplate."""
    timezone: str = "America/New_York"
    capital: float = 10_000.0
    risk_pct: float = 0.02
    max_risk_dollars: float = 500.0
    fractional_shares: bool = True
    min_order_value: float = 1.0
    max_entries_per_day: int = 1
    max_daily_loss_pct: float = 0.03  # 3% daily stop
    max_drawdown_pct: float = 0.10    # 10% equity stop
    rr_ratio: float = 2.0
    max_holding_bars: int = 30
    trailing_stop_breakeven: bool = True
    early_exit_reversal: bool = False
    bar_interval: str = "5m"
    session_start: str = "09:30"
    session_end: str = "16:00"
    slippage_bps: float = 5.0
    spread_bps: float = 5.0
    min_day_bars: int = 40


class UniversalBoilerplate:
    """Wraps any strategy with consistent risk management and session logic."""

    def __init__(self, config: dict, risk: RiskManager = None, journal: TradeJournal = None):
        self.config = config
        self.risk = risk or RiskManager(config)
        self.journal = journal or TradeJournal("/tmp/backtest_journal.json")
        self.bp = self._load_boilerplate_config(config)
        self._active_trades: dict[str, dict] = {}
        self._entry_counts: dict[tuple[str, object], int] = {}
        self._daily_pnl: dict[object, float] = {}
        self._peak_equity = self.risk.capital
        self._current_equity = self.risk.capital
        self.log = logging.getLogger("boilerplate")

    def _load_boilerplate_config(self, config: dict) -> BoilerplateConfig:
        bp = BoilerplateConfig()
        bp.timezone = config.get("timezone", bp.timezone)
        bp.capital = config.get("capital", bp.capital)
        bp.risk_pct = config.get("risk_pct", bp.risk_pct)
        bp.max_risk_dollars = config.get("max_risk_dollars", bp.max_risk_dollars)
        bp.fractional_shares = config.get("fractional_shares", bp.fractional_shares)
        bp.min_order_value = config.get("min_order_value", bp.min_order_value)
        bp.max_entries_per_day = config.get("max_entries_per_day", bp.max_entries_per_day)
        bp.rr_ratio = config.get("rr_ratio", bp.rr_ratio)
        bp.max_holding_bars = config.get("max_holding_bars", bp.max_holding_bars)
        bp.trailing_stop_breakeven = config.get("trailing_stop_breakeven", bp.trailing_stop_breakeven)
        bp.early_exit_reversal = config.get("early_exit_reversal", bp.early_exit_reversal)
        bp.bar_interval = config.get("bar_interval", bp.bar_interval)
        bp.slippage_bps = config.get("execution_realism", {}).get("slippage_bps", bp.slippage_bps)
        bp.spread_bps = config.get("execution_realism", {}).get("spread_bps", bp.spread_bps)
        return bp

    def can_trade(self, symbol: str, bars: pd.DataFrame) -> tuple[bool, str]:
        """Global risk gates: daily loss limit, drawdown limit, entry limits."""
        if not bars.empty:
            day = bars.index[-1].date() if hasattr(bars.index[-1], 'date') else bars.index[-1]
        else:
            day = None

        # Drawdown limit
        if self._peak_equity > 0:
            dd = (self._peak_equity - self._current_equity) / self._peak_equity
            if dd >= self.bp.max_drawdown_pct:
                return False, f"max drawdown {dd:.1%} >= {self.bp.max_drawdown_pct:.1%}"

        # Daily loss limit
        daily_loss = self._daily_pnl.get(day, 0.0)
        if self._current_equity > 0:
            daily_loss_pct = abs(daily_loss) / self._current_equity
            if daily_loss_pct >= self.bp.max_daily_loss_pct and daily_loss < 0:
                return False, f"daily loss {daily_loss_pct:.1%} >= {self.bp.max_daily_loss_pct:.1%}"

        # Per-day entry limit
        key = (symbol, day)
        entries_today = self._entry_counts.get(key, 0)
        if entries_today >= self.bp.max_entries_per_day:
            return False, f"max entries ({entries_today}) reached for {symbol} on {day}"

        # Already in a trade for this symbol
        if symbol in self._active_trades:
            return False, f"active trade already exists for {symbol}"

        return True, "ok"

    def record_entry(self, symbol: str, signal: dict, bars: pd.DataFrame = None):
        """Record a trade entry and update counters."""
        if bars is not None and not bars.empty:
            day = bars.index[-1].date() if hasattr(bars.index[-1], 'date') else bars.index[-1]
        else:
            day = signal.get("timestamp", "unknown")
        signal["entry_bar_count"] = 0
        self._active_trades[symbol] = signal
        key = (symbol, day)
        self._entry_counts[key] = self._entry_counts.get(key, 0) + 1

    def record_exit(self, symbol: str, result: dict, bars: pd.DataFrame = None):
        """Record a trade exit and update equity."""
        pnl = result.get("pnl", 0.0)
        exec_cost = result.get("execution_cost", 0.0)
        total = pnl - exec_cost
        self.risk.update_cash(total)
        self._current_equity = self.risk.capital
        if self._current_equity > self._peak_equity:
            self._peak_equity = self._current_equity
        if bars is not None and not bars.empty:
            day = bars.index[-1].date() if hasattr(bars.index[-1], 'date') else bars.index[-1]
            self._daily_pnl[day] = self._daily_pnl.get(day, 0.0) + total
        self._active_trades.pop(symbol, None)
        self.journal.log_trade(result)

    def session_mask(self, index: pd.Index) -> pd.Series:
        """Return boolean mask for session hours."""
        start = pd.Timestamp(self.bp.session_start).time()
        end = pd.Timestamp(self.bp.session_end).time()
        times = index.time if hasattr(index, 'time') else pd.to_datetime(index).time
        return (times >= start) & (times < end)

    @property
    def equity(self) -> float:
        return self._current_equity

    @property
    def total_return_pct(self) -> float:
        if self.bp.capital > 0:
            return (self._current_equity - self.bp.capital) / self.bp.capital * 100
        return 0.0
