"""Forward Tester for Top 3 Strategies.

Takes the top 3 strategies from batch backtest results and runs them
in paper mode with small capital ($100-$300) for forward validation.

Uses the existing bot infrastructure with paper trading enabled.
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import DataFeed
from src.risk import RiskManager
from src.journal import TradeJournal
from src.execution_realism import finalize_trade, valid_bar
from src.strategy import LondonBreakoutStrategy
from src.ross_momentum import RossMomentumStrategy
from src.sneaky_pivot import SneakyPivotStrategy
from src.ha_scalp import HAScalpStrategy
from src.auction_flow_proxy import AuctionFlowProxyStrategy
from src.vwap_liquidity_proxy import VWAPLiquidityProxyStrategy
from src.t3_range_filter import T3RangeFilterStrategy
from src.reversal_zone_confirmation import ReversalZoneConfirmationStrategy
from src.ema_cci_macd import EmaCciMacdStrategy
from src.candle_narrative import CandleNarrativeStrategy

log = logging.getLogger("forward_test")

STRATEGY_MAP = {
    "london": LondonBreakoutStrategy,
    "ross": RossMomentumStrategy,
    "sneaky": SneakyPivotStrategy,
    "ha_scalp": HAScalpStrategy,
    "auction_flow": AuctionFlowProxyStrategy,
    "vwap": VWAPLiquidityProxyStrategy,
    "t3": T3RangeFilterStrategy,
    "reversal": ReversalZoneConfirmationStrategy,
    "ema_cci_macd": EmaCciMacdStrategy,
    "candle_narrative": CandleNarrativeStrategy,
}


class ForwardTestRunner:
    """Runs a single strategy in paper mode with small capital."""

    def __init__(
        self,
        strategy_name: str,
        params: dict,
        base_config: dict,
        symbols: list[str],
        capital: float = 100.0,
        risk_pct: float = 0.02,
    ):
        self.strategy_name = strategy_name
        self.params = params
        self.symbols = symbols
        self.capital = capital
        self.risk_pct = risk_pct

        # Build config with small capital
        import copy
        self.config = copy.deepcopy(base_config)
        self.config["capital"] = capital
        self.config["risk_pct"] = risk_pct
        self.config["max_risk_dollars"] = capital * risk_pct
        self.config["fractional_shares"] = True
        self.config["min_order_value"] = 1.0

        # Merge strategy params
        section_map = {
            "london": None,
            "ross": "ross_momentum",
            "sneaky": "sneaky_pivot",
            "ha_scalp": "ha_scalp",
            "auction_flow": "auction_flow_proxy",
            "vwap": "vwap_liquidity_proxy",
            "t3": "t3_range_filter",
            "reversal": "reversal_zone_confirmation",
            "ema_cci_macd": "ema_cci_macd",
            "candle_narrative": "candle_narrative",
        }
        section = section_map.get(strategy_name)
        if section:
            self.config.setdefault(section, {}).update(params)
        else:
            self.config.update(params)

        self.feed = DataFeed(self.config.get("timezone", "America/New_York"))
        self.risk = RiskManager(self.config)
        self.journal = TradeJournal(f"/tmp/forward_test_{strategy_name}.jsonl")

        strategy_cls = STRATEGY_MAP.get(strategy_name)
        if not strategy_cls:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        self.strategy = strategy_cls(self.config, self.risk, self.journal)

        self.trades = []
        self.equity_curve = []

    def run_bar(
        self,
        symbol: str,
        bars: pd.DataFrame,
        context: tuple[float, float] | None = None,
    ) -> dict | None:
        """Process a single bar. Returns trade result if one was closed."""
        if not valid_bar(bars.iloc[-1]):
            return None

        result = None

        # Check exit first
        if symbol in self.strategy._active_trades:
            exit_result = self.strategy.check_exit(symbol, bars, None)
            if exit_result:
                if self.config.get("execution_realism", {}).get("enabled", True):
                    exit_result = finalize_trade(exit_result, self.config)
                self.trades.append(exit_result)
                self.risk.update_cash(exit_result["pnl"] - exit_result.get("execution_cost", 0))
                result = exit_result

        # Check entry
        if symbol not in self.strategy._active_trades:
            signal = self.strategy.generate_signal(symbol, bars, context)
            if signal:
                self.strategy.on_trade_entered(symbol, signal)

        # Record equity
        self.equity_curve.append({
            "timestamp": bars.index[-1].isoformat(),
            "equity": self.risk.capital,
        })

        return result

    def run_session(self, date: datetime.date) -> list[dict]:
        """Run a full trading session for the given date."""
        day_trades = []

        for symbol in self.symbols:
            try:
                # Get today's bars
                df = self.feed.get_bars(
                    symbol,
                    interval=self.config.get("bar_interval", "5m"),
                    start=date.isoformat(),
                    end=(date + timedelta(days=1)).isoformat(),
                )
            except Exception as exc:
                log.warning(f"  {symbol} download failed: {exc}")
                continue
            if df.empty:
                continue

            if df.index.tz is None:
                df.index = df.index.tz_localize(self.config.get("timezone", "America/New_York"))
            else:
                df.index = df.index.tz_convert(self.config.get("timezone", "America/New_York"))
            df.columns = [str(c).lower() for c in df.columns]

            context = None
            if self.strategy_name == "london":
                context = self.strategy.build_london_box(df)
                if context is None:
                    continue

            # Get session mask
            if self.strategy_name == "london":
                session_start = pd.Timestamp(self.config.get("ny_open", "09:30")).time()
                session_end = pd.Timestamp(self.config.get("ny_close", "12:00")).time()
            elif self.strategy_name == "ross":
                session_start = pd.Timestamp(self.config.get("ross_momentum", {}).get("session_start", "04:00")).time()
                session_end = pd.Timestamp(self.config.get("ross_momentum", {}).get("session_end", "12:00")).time()
            else:
                session_start = pd.Timestamp("09:30").time()
                session_end = pd.Timestamp("16:00").time()

            mask = (df.index.time >= session_start) & (df.index.time < session_end)
            session_data = df[mask]
            if session_data.empty:
                continue

            n = len(session_data)
            for i in range(1, n):
                bars_slice = session_data.iloc[: i + 1]
                result = self.run_bar(symbol, bars_slice, context)
                if result:
                    day_trades.append(result)

            # Force-close at EOD
            if symbol in self.strategy._active_trades:
                last_bar = session_data.iloc[-1]
                trade = self.strategy._active_trades[symbol]
                close = float(last_bar["close"])
                entry = trade["entry"]
                qty = trade["qty"]
                direction = trade["direction"]
                if direction == "long":
                    pnl = (close - entry) * qty
                else:
                    pnl = (entry - close) * qty
                exit_result = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry": round(entry, 2),
                    "exit_price": round(close, 2),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "reason": "eod_close",
                }
                if self.config.get("execution_realism", {}).get("enabled", True):
                    exit_result = finalize_trade(exit_result, self.config)
                self.trades.append(exit_result)
                self.risk.update_cash(exit_result["pnl"] - exit_result.get("execution_cost", 0))
                del self.strategy._active_trades[symbol]
                day_trades.append(exit_result)

        return day_trades

    def get_metrics(self) -> dict:
        """Calculate forward test metrics."""
        if not self.trades:
            return {
                "trade_count": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "total_pnl": 0,
                "final_equity": self.capital,
                "total_return_pct": 0,
            }

        wins = [t for t in self.trades if t.get("pnl", 0) > 0]
        losses = [t for t in self.trades if t.get("pnl", 0) < 0]
        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        gross_wins = sum(t["pnl"] for t in wins) if wins else 0
        gross_losses = sum(abs(t["pnl"]) for t in losses) if losses else 0

        return {
            "trade_count": len(self.trades),
            "win_rate": round(len(wins) / len(self.trades) * 100, 2) if self.trades else 0,
            "profit_factor": round(gross_wins / gross_losses, 2) if gross_losses > 0 else float("inf"),
            "total_pnl": round(total_pnl, 2),
            "final_equity": round(self.risk.capital, 2),
            "total_return_pct": round((self.risk.capital - self.capital) / self.capital * 100, 2),
            "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(abs(t["pnl"]) for t in losses) / len(losses), 2) if losses else 0,
            "max_drawdown_pct": self._calc_max_drawdown(),
        }

    def _calc_max_drawdown(self) -> float:
        """Calculate max drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0
        peak = 0.0
        max_dd = 0.0
        for point in self.equity_curve:
            eq = point["equity"]
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                max_dd = max(max_dd, dd)
        return round(max_dd * 100, 2)


def run_forward_tests(
    results_path: str,
    base_config_path: str,
    symbols: list[str],
    days: int = 5,
    capital: float = 100.0,
    top_n: int = 3,
) -> list[dict]:
    """Run forward tests on top N strategies."""
    with open(results_path) as f:
        results = json.load(f)

    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)

    # Filter out errors and get top N
    valid = [r for r in results if "error" not in r and r.get("trade_count", 0) > 0]
    top_strategies = valid[:top_n]

    print(f"\n{'='*60}")
    print(f"Forward Testing Top {top_n} Strategies with ${capital} capital")
    print(f"{'='*60}")

    forward_results = []
    for i, strat in enumerate(top_strategies, 1):
        strategy_id = strat["id"]
        strategy_name = strat["strategy"]
        params = strat["params"]

        print(f"\n[{i}/{top_n}] Forward testing {strategy_id}...")
        print(f"    Strategy: {strategy_name}")
        print(f"    Params: {json.dumps(params, indent=2)[:200]}...")

        try:
            runner = ForwardTestRunner(
                strategy_name=strategy_name,
                params=params,
                base_config=base_config,
                symbols=symbols,
                capital=capital,
            )

            # Run for specified number of days
            today = datetime.now().date()
            for day_offset in range(days):
                date = today - timedelta(days=day_offset)
                if date.weekday() >= 5:  # Skip weekends
                    continue
                print(f"    Running {date}...")
                day_trades = runner.run_session(date)
                print(f"      {len(day_trades)} trades, equity=${runner.risk.capital:.2f}")

            metrics = runner.get_metrics()
            metrics["id"] = strategy_id
            metrics["strategy"] = strategy_name
            metrics["params"] = params
            metrics["capital"] = capital
            metrics["days_tested"] = days
            forward_results.append(metrics)

            print(f"    Final: Equity=${metrics['final_equity']}, Return={metrics['total_return_pct']}%, "
                  f"WR={metrics['win_rate']}%, PF={metrics['profit_factor']}")

        except Exception as exc:
            log.error(f"    FAILED: {exc}")
            import traceback
            traceback.print_exc()
            forward_results.append({
                "id": strategy_id,
                "strategy": strategy_name,
                "error": str(exc),
                "capital": capital,
            })

    return forward_results


def main():
    parser = argparse.ArgumentParser(description="Forward test top 3 strategies")
    parser.add_argument("--results", default="framework/batch_results.json")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--capital", type=float, default=100.0)
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--out", default="framework/forward_results.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    results = run_forward_tests(
        args.results, args.config, args.symbols, args.days, args.capital, args.top
    )

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Forward Test Summary")
    print(f"{'='*60}")
    for r in results:
        if "error" in r:
            print(f"  {r['id']}: ERROR - {r['error']}")
        else:
            print(f"  {r['id']}: Return={r.get('total_return_pct', 0)}%, "
                  f"WR={r.get('win_rate', 0)}%, PF={r.get('profit_factor', 0)}, "
                  f"Equity=${r.get('final_equity', 0)}")

    print(f"\nFull results saved to {args.out}")
    return results


if __name__ == "__main__":
    main()
