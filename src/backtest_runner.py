"""Reusable backtest runner for the Robinhood trading bot.

Extracted from `backtest.py` so the core engine can be called as a function
without spawning a subprocess. Preserves the existing CLI behavior of
`backtest.py` byte-for-byte on the published benchmark window.
"""
import argparse
import copy
import json
import logging
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import yaml

from src.data import DataFeed
from src.strategy import LondonBreakoutStrategy
from src.ross_momentum import RossMomentumStrategy
from src.sneaky_pivot import SneakyPivotStrategy
from src.ha_scalp import HAScalpStrategy
from src.auction_flow_proxy import AuctionFlowProxyStrategy
from src.theta_only import ThetaOnlyStrategy
from src.eps_line_put_selling import EpsLinePutSellingStrategy, bs_put_price
from src.vwap_liquidity_proxy import VWAPLiquidityProxyStrategy
from src.t3_range_filter import T3RangeFilterStrategy
from src.reversal_zone_confirmation import ReversalZoneConfirmationStrategy
from src.ema_cci_macd import EmaCciMacdStrategy
from src.ema9_continuation import Ema9ContinuationStrategy
from src.candle_narrative import CandleNarrativeStrategy
from src.ema20_stoch_pullback import Ema20StochPullbackStrategy
from src.opening_drive_fade import OpeningDriveFadeStrategy
from src.orb_fvg import OrbfvgStrategy
from src.trailing_stop_ladder import TrailingStopLadderStrategy
from src.risk import RiskManager
from src.journal import TradeJournal
from src.theta_farming import ThetaFarmer
from src.execution_realism import finalize_trade, valid_bar

log = logging.getLogger("backtest_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


STRATEGY_MAP = {

    "london": LondonBreakoutStrategy,
    "ross": RossMomentumStrategy,
    "sneaky": SneakyPivotStrategy,
    "ha_scalp": HAScalpStrategy,
    "auction_flow_proxy": AuctionFlowProxyStrategy,
    "vwap_liquidity_proxy": VWAPLiquidityProxyStrategy,
    "t3_range_filter": T3RangeFilterStrategy,
    "reversal_zone_confirmation": ReversalZoneConfirmationStrategy,
    "ema_cci_macd": EmaCciMacdStrategy,
    "ema9_continuation": Ema9ContinuationStrategy,
    "ema20_stoch_pullback": Ema20StochPullbackStrategy,
    "opening_drive_fade": OpeningDriveFadeStrategy,
    "orb_fvg": OrbfvgStrategy,
    "trailing_stop_ladder": TrailingStopLadderStrategy,
    "candle_narrative": CandleNarrativeStrategy,
    "theta_only": ThetaOnlyStrategy,
    "eps_line_put_selling": EpsLinePutSellingStrategy,
}


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def summarize_trades(trades: list, start_date: str, end_date: str, symbols: list, initial_capital: float) -> dict:
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]
    total_pnl = round(sum(float(t.get("pnl", 0)) for t in trades), 2)
    gross_pnl = round(sum(float(t.get("gross_pnl", t.get("pnl", 0))) for t in trades), 2)
    execution_cost = round(sum(float(t.get("execution_cost", 0)) for t in trades), 2)
    gross_wins = sum(float(t.get("pnl", 0)) for t in wins)
    gross_losses = sum(abs(float(t.get("pnl", 0))) for t in losses)
    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "symbols": symbols,
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(initial_capital + total_pnl, 2),
        "total_pnl": total_pnl,
        "gross_pnl": gross_pnl,
        "execution_cost": execution_cost,
        "net_pnl": total_pnl,
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0,
        "profit_factor": round(gross_wins / gross_losses, 2) if gross_losses else None,
        "avg_win": round(float(np.mean([t["pnl"] for t in wins])), 2) if wins else 0,
        "avg_loss": round(float(np.mean([abs(t["pnl"]) for t in losses])), 2) if losses else 0,
        "reason_counts": dict(Counter(t.get("reason", "unknown") for t in trades)),
        "trades": trades,
    }
    gex_regimes = {}
    for t in trades:
        regime = t.get("gex_regime")
        if regime is None:
            continue
        bucket = gex_regimes.setdefault(regime, {"trades": 0, "wins": 0, "net": 0.0})
        bucket["trades"] += 1
        bucket["wins"] += 1 if t.get("pnl", 0) > 0 else 0
        bucket["net"] = round(bucket["net"] + float(t.get("pnl", 0)), 2)
    if gex_regimes:
        summary["gex_context"] = {
            "matched_trades": sum(b["trades"] for b in gex_regimes.values()),
            "by_regime": gex_regimes,
            "note": "naive GEX proxy from data/gex_daily.csv (started 2026-09-05); history fills in over time",
        }
    return summary


def load_gex_log(path: str = "data/gex_daily.csv") -> dict:
    """Load daily GEX snapshots logged by src/gamma_monitor.py --log."""
    import csv

    try:
        with open(path) as fh:
            return {r["date"]: (float(r["net_gex"]), r["regime"]) for r in csv.DictReader(fh) if r.get("date")}
    except FileNotFoundError:
        return {}


def annotate_gex(trades: list, gex_map: dict) -> None:
    """Stamp net_gex + gex_regime onto trades by entry date (n/a when unlogged)."""
    if not gex_map:
        return
    for t in trades:
        ts = t.get("timestamp") or t.get("entry_time") or t.get("entry_date") or ""
        net_gex, regime = gex_map.get(str(ts)[:10], (None, None))
        t["net_gex"] = net_gex
        t["gex_regime"] = regime


def run_backtest(config: dict, symbols: list, start_date: str, end_date: str, provider: str = "auto", strategy_name: str = "london", data_dir: str | None = None, json_output: bool = False, breakout_strength_override: float | None = None) -> list:
    """Run a single backtest. Returns the trade list (full dicts).

    If `breakout_strength_override` is set, it patches a deepcopy of `config`
    before the strategy is constructed. This matches the existing CLI arg
    behavior in `backtest.py`.
    """
    if breakout_strength_override is not None:
        config = copy.deepcopy(config)
        config["breakout_strength"] = breakout_strength_override

    feed = DataFeed(config.get("timezone", "America/New_York"), provider=provider)
    risk = RiskManager(config)
    journal = TradeJournal("/tmp/backtest_journal.json")
    strat = STRATEGY_MAP[strategy_name](config, risk, journal)
    all_trades = []
    gex_map = load_gex_log()

    if strategy_name in ("theta_only", "eps_line_put_selling"):
        selected_symbols = strat.symbols_for_run(symbols) if strategy_name == "theta_only" else symbols
        daily_frames = {}
        for symbol in selected_symbols:
            try:
                cached = None
                if data_dir:
                    candidate = Path(data_dir) / f"{symbol}_{start_date}_{end_date}.pkl"
                    if candidate.exists():
                        cached = pd.read_pickle(candidate)
                interval = (config.get("eps_line_put_selling", {}).get("backtest_interval", "1d") if strategy_name == "eps_line_put_selling" else config.get("bar_interval", "5m"))
                df = cached if cached is not None else feed.get_bars(symbol, interval=interval, start=start_date, end=end_date)
            except Exception as exc:
                log.warning("  %s download failed: %s", symbol, exc)
                continue
            if df.empty:
                continue
            if df.index.tz is None:
                df.index = df.index.tz_localize(config.get("timezone", "America/New_York"))
            else:
                df.index = df.index.tz_convert(config.get("timezone", "America/New_York"))
            df.columns = [str(column).lower() for column in df.columns]
            daily_frames[symbol] = df
            for day in df.index.normalize().unique():
                result = strat.generate_trade(symbol, df[df.index <= day].sort_index())
                if result:
                    all_trades.append(result)
        if json_output:
            annotate_gex(all_trades, gex_map)
            summary = summarize_trades(all_trades, start_date, end_date, selected_symbols, config.get("capital", 0))
            if strategy_name == "theta_only":
                summary.update({"strategy": "theta_only", "selection_mode": strat.selection_mode, "aggressiveness": strat.preset_name, "directional_trades": 0})
            else:
                frames_by_symbol = daily_frames
                unrealized = 0.0
                for pos in strat.open_positions:
                    frame = frames_by_symbol.get(pos["symbol"])
                    spot = float(frame["close"].iloc[-1]) if frame is not None and not frame.empty else pos["entry"]
                    days_elapsed = (pd.Timestamp(end_date).tz_localize("America/New_York") - pd.Timestamp(pos["entry_date"]).tz_localize("America/New_York")).days
                    years = max((strat.cfg["dte"] - days_elapsed) / 365.0, 0.0)
                    unrealized += bs_put_price(spot, pos["strike"], years, strat.cfg["iv"], strat.cfg["risk_free"]) * 100.0 * pos["contracts"]
                summary.update({"strategy": "eps_line_put_selling", "paper_only": True, "open_positions": len(all_trades), "premium_collected": round(sum(t["premium_collected"] for t in all_trades), 2), "open_max_liability": round(sum(t["max_liability"] for t in all_trades), 2), "unrealized_mtm": round(unrealized, 2), "securing": strat.cfg["securing"], "dte": strat.cfg["dte"], "directional_trades": 0, "blocked_entries": dict(strat.blocked_entries)})
            print(json.dumps(summary, default=str))
        return all_trades

    regime_cfg = config.get("regime_filter", {})
    regime_enabled = bool(regime_cfg.get("enabled", False)) and strategy_name == "london"
    regime_map = {}
    if regime_enabled:
        r_sym = regime_cfg.get("symbol", "SPY")
        ma_len = int(regime_cfg.get("ma_length", 50))
        r_start = (pd.Timestamp(start_date) - pd.Timedelta(days=ma_len * 2 + 15)).strftime("%Y-%m-%d")
        spy = feed.get_bars(r_sym, interval="1d", start=r_start, end=end_date)
        if spy.empty:
            log.warning("regime_filter: no daily bars for %s — filter inactive", r_sym)
            regime_enabled = False
        else:
            sma = spy["close"].rolling(ma_len).mean()
            invert = bool(regime_cfg.get("invert", False))
            regime_map = {ts.date(): bool(c > m) != invert for ts, c, m in zip(spy.index, spy["close"], sma) if pd.notna(m)}
            log.info("regime_filter: %d regime days for %s (SMA%d)", len(regime_map), r_sym, ma_len)

    theta_cfg = config.get("theta_farming", {})
    theta_farmer = ThetaFarmer(theta_cfg) if theta_cfg.get("enabled", False) else None

    for symbol in symbols:
        log.info("Downloading %s ...", symbol)
        try:
            cached = None
            if data_dir:
                candidate = Path(data_dir) / f"{symbol}_{start_date}_{end_date}.pkl"
                if candidate.exists():
                    cached = pd.read_pickle(candidate)
            df = cached if cached is not None else feed.get_bars(
                symbol,
                interval=(config.get("eps_line_put_selling", {}).get("backtest_interval", "1d") if strategy_name == "eps_line_put_selling" else config.get("ha_scalp", {}).get("backtest_interval", "5m") if strategy_name == "ha_scalp" else config.get("t3_range_filter", {}).get("backtest_interval", config.get("bar_interval", "5m")) if strategy_name == "t3_range_filter" else config.get("reversal_zone_confirmation", {}).get("backtest_interval", config.get("bar_interval", "5m")) if strategy_name == "reversal_zone_confirmation" else config.get("ema20_stoch_pullback", {}).get("backtest_interval", config.get("bar_interval", "5m")) if strategy_name == "ema20_stoch_pullback" else config.get("orb_fvg", {}).get("backtest_interval", config.get("bar_interval", "5m")) if strategy_name == "orb_fvg" else config.get("bar_interval", "5m")),
                start=start_date,
                end=end_date,
            )
        except Exception as e:
            log.warning("  %s download failed: %s", symbol, e)
            continue
        if df.empty:
            log.warning("  no data for %s", symbol)
            continue

        if df.index.tz is None:
            df.index = df.index.tz_localize(config.get("timezone", "America/New_York"))
        else:
            df.index = df.index.tz_convert(config.get("timezone", "America/New_York"))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]
        trade_dates = df.index.normalize().unique()

        for day in trade_dates:
            day_data = df[df.index.normalize() == day].sort_index()
            min_day_bars = 8 if strategy_name == "t3_range_filter" else (35 if strategy_name == "orb_fvg" else (40 if config.get("bar_interval", "5m") == "5m" else 8))
            if len(day_data) < min_day_bars:
                continue

            if strategy_name == "london":
                box = strat.build_london_box(day_data)
                if box is None:
                    continue
                box_high, box_low = box
                ny_mask = (day_data.index.time >= strat.ny_start) & (day_data.index.time < strat.ny_end)
            elif strategy_name == "ross":
                box_high = box_low = None
                session_start = pd.Timestamp(config.get("ross_momentum", {}).get("session_start", "04:00")).time()
                session_end = pd.Timestamp(config.get("ross_momentum", {}).get("session_end", "12:00")).time()
                ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
            elif strategy_name in {"ha_scalp", "auction_flow_proxy", "vwap_liquidity_proxy", "t3_range_filter", "reversal_zone_confirmation", "ema_cci_macd", "ema9_continuation", "ema20_stoch_pullback", "candle_narrative", "opening_drive_fade", "orb_fvg", "trailing_stop_ladder"}:
                box_high = box_low = None
                session_start, session_end = strat.session_start, strat.session_end
                ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
            else:
                box_high = box_low = None
                session_start = pd.Timestamp(config.get("sneaky_pivot", {}).get("session_start", "09:30")).time()
                session_end = pd.Timestamp(config.get("sneaky_pivot", {}).get("session_end", "15:45")).time()
                ny_mask = (day_data.index.time >= session_start) & (day_data.index.time < session_end)
            ny_data = day_data[ny_mask]
            if ny_data.empty:
                continue

            n = len(ny_data)
            for i in range(n):
                if i == 0:
                    continue
                bars_slice = ny_data.iloc[: i + 1]
                if not valid_bar(bars_slice.iloc[-1]):
                    continue

                if symbol in strat._active_trades:
                    exit_result = strat.check_exit(symbol, bars_slice, None)
                    if exit_result:
                        if config.get("execution_realism", {}).get("enabled", True):
                            exit_result = finalize_trade(exit_result, config)
                            risk.update_cash(-exit_result["execution_cost"])
                        all_trades.append(exit_result)

                if symbol not in strat._active_trades:
                    context = (box_high, box_low) if strategy_name == "london" else None
                    if strategy_name in ("sneaky", "opening_drive_fade"):
                        prior = df[df.index.normalize() < day]
                        context = {"prior_high": float(prior["high"].max()), "prior_low": float(prior["low"].min())} if not prior.empty else None
                    signal = strat.generate_signal(symbol, bars_slice, context)
                    if signal and regime_enabled:
                        want_long = regime_map.get(day.date())
                        if want_long is not None and ((signal["direction"] == "long") != want_long):
                            signal = None
                    if signal:
                        strat.on_trade_entered(symbol, signal)

                        if theta_farmer:
                            tf_trade = theta_farmer.generate_trade(
                                signal["symbol"], signal["entry"], signal["direction"]
                            )
                            if tf_trade:
                                tf_result = theta_farmer.execute_trade(tf_trade, capital=risk.capital)
                                if tf_result:
                                    realized = theta_farmer.simulate_expiry(tf_trade, tf_result["contracts"])
                                    risk.update_cash(realized)
                                    all_trades.append({
                                        "symbol": signal["symbol"],
                                        "trade_type": "theta_spread",
                                        "entry": signal["entry"],
                                        "timestamp": signal.get("timestamp"),
                                        "direction": signal["direction"],
                                        "exit_price": signal["entry"],
                                        "qty": tf_result["contracts"],
                                        "pnl": realized,
                                        "rr": 0,
                                        "reason": "theta_spread",
                                    })

            if symbol in strat._active_trades:
                last_bar = ny_data.iloc[-1]
                trade = strat._active_trades[symbol]
                direction = trade["direction"]
                close = float(last_bar["close"])
                entry = trade["entry"]
                qty = trade["qty"]
                if direction == "long":
                    pnl = (close - entry) * qty
                else:
                    pnl = (entry - close) * qty
                exit_result = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry": round(entry, 2),
                    "exit_price": round(close, 2),
                    "exit_time": None,
                    "timestamp": trade.get("timestamp"),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "rr": round(abs(trade["target"] - entry) / abs(trade["stop"] - entry), 2)
                        if abs(trade["stop"] - entry) != 0 else 0,
                    "reason": "eod_close",
                }
                if config.get("execution_realism", {}).get("enabled", True):
                    exit_result = finalize_trade(exit_result, config)
                    pnl = exit_result["pnl"]
                risk.update_cash(pnl)
                journal.log_trade(exit_result)
                del strat._active_trades[symbol]
                all_trades.append(exit_result)

    if json_output:
        annotate_gex(all_trades, gex_map)
        print(json.dumps(summarize_trades(all_trades, start_date, end_date, symbols, config.get("capital", 0)), default=str))
        return all_trades

    print(f"\n{'=' * 60}")
    print(f"Backtest Results: {start_date} to {end_date}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Total trades: {len(all_trades)}")
    print(f"{'=' * 60}")

    if all_trades:
        wins = [t for t in all_trades if t["pnl"] > 0]
        losses = [t for t in all_trades if t["pnl"] < 0]
        total_pnl = sum(t["pnl"] for t in all_trades)
        winrate = len(wins) / len(all_trades) * 100 if all_trades else 0
        gross_wins = sum(t["pnl"] for t in wins) if wins else 0
        gross_losses = sum(abs(t["pnl"]) for t in losses) if losses else 0
        avg_r = abs(gross_wins - gross_losses) / len(all_trades) if all_trades else 0

        print(f"Closed trades: {len(all_trades)}")
        print(f"Total P&L: ${total_pnl:.2f}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win rate: {winrate:.1f}%")
        if wins:
            print(f"Avg win: ${np.mean([t['pnl'] for t in wins]):.2f}")
        if losses:
            print(f"Avg loss: ${np.mean([abs(t['pnl']) for t in losses]):.2f}")
        if gross_losses > 0:
            print(f"Profit factor: {gross_wins / gross_losses:.2f}")

        reason_counts = Counter(t["reason"] for t in all_trades)
        for reason, count in reason_counts.most_common():
            print(f"  {reason}: {count}")

        print()
        for t in all_trades:
            ex = t.get("exit_price", t.get("exit", "?"))
            print(f"  {t.get('exit_time', '').split('T')[0] if t.get('exit_time') else 'N/A'} "
                  f"{t['symbol']} {t['direction']} {t['qty']}sh "
                  f"entry=${t['entry']} exit=${ex} P&L=${t['pnl']:.2f} ({t['reason']})")
    else:
        print("No signals generated.")

    print(f"{'=' * 60}")
    return all_trades


def _resolve_missing_eps(symbols, params):
    """Fill in per-symbol trailing EPS via yfinance when not configured."""
    eps_cfg = params.get("eps", {})
    if isinstance(eps_cfg, dict) and "eps" in eps_cfg and isinstance(eps_cfg["eps"], dict):
        eps_cfg = eps_cfg["eps"]
    if isinstance(eps_cfg, (int, float)):
        eps_map = {s: eps_cfg for s in symbols}
    elif isinstance(eps_cfg, dict):
        upper = {str(k).upper(): v for k, v in eps_cfg.items() if v}
        eps_map = {s: upper.get(s.upper()) for s in symbols}
    else:
        eps_map = {s: None for s in symbols}
    resolved = {}
    missing = [s for s, v in eps_map.items() if not v]
    if missing:
        import yfinance as yf
        for sym in missing:
            try:
                value = yf.Ticker(sym).info.get("trailingEps")
                if value and float(value) > 0:
                    eps_map[sym] = float(value)
                    resolved[sym] = float(value)
                elif value:
                    logging.warning(
                        "Skipping %s: trailing EPS %.2f is not positive (loss-making or distorted)",
                        sym,
                        float(value),
                    )
            except Exception as exc:
                logging.warning("Could not fetch trailing EPS for %s: %s", sym, exc)
    return eps_map, resolved


def main():
    parser = argparse.ArgumentParser(description="Trading strategy backtest")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"])
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-08-06")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--rr-ratio", type=float, default=None)
    parser.add_argument("--max-bars", type=int, default=None)
    parser.add_argument("--capital", type=float, default=None)
    parser.add_argument("--breakout-strength", type=float, default=None)
    parser.add_argument("--min-box-pct", type=float, default=None)
    parser.add_argument("--entry-window", type=float, default=None)
    parser.add_argument("--max-entries-per-day", default=None)
    parser.add_argument("--trend-filter", type=lambda x: x.lower()=="true", default=None)
    parser.add_argument("--directional-bias", type=lambda x: x.lower()=="true", default=None)
    parser.add_argument("--provider", default="auto",
                        help="data provider: auto (alpaca if keys set, else yfinance), alpaca, yfinance")
    parser.add_argument("--strategy", choices=list(STRATEGY_MAP.keys()), default="london")
    parser.add_argument("--theta-aggressiveness", choices=["conservative", "balanced", "aggressive"], default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--interval", choices=["1m", "5m", "15m", "1h"], default=None)
    parser.add_argument("--theta", choices=["true", "false"], default=None)
    parser.add_argument("--strategy-params", default=None, help="JSON object merged into the selected strategy configuration")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.strategy_params:
        params = json.loads(args.strategy_params)
        if not isinstance(params, dict):
            raise ValueError("--strategy-params must be a JSON object")
        config.setdefault(args.strategy, {}).update(params)
    if args.strategy == "eps_line_put_selling":
        block = config.setdefault("eps_line_put_selling", {})
        eps_map, resolved = _resolve_missing_eps(args.symbols, block)
        if eps_map:
            block["eps"] = eps_map
        for sym, value in resolved.items():
            logging.info("Auto-resolved trailing EPS for %s: %.2f", sym, value)
        no_eps = [s for s, v in eps_map.items() if not v]
        if no_eps:
            logging.warning("Skipping %s: no trailing EPS available (ETFs/funds cannot anchor an EPS line)", ", ".join(no_eps))
            args.symbols = [s for s in args.symbols if s not in no_eps]
    if args.capital:
        config["capital"] = args.capital
        config["max_risk_dollars"] = args.capital * config.get("risk_pct", 0.02)
        tf = config.setdefault("theta_farming", {})
        tf["initial_capital"] = args.capital
    if args.rr_ratio: config["rr_ratio"] = args.rr_ratio
    if args.max_bars: config["max_holding_bars"] = args.max_bars
    if args.breakout_strength is not None: config["breakout_strength"] = args.breakout_strength
    if args.min_box_pct is not None: config["min_box_pct"] = args.min_box_pct
    if args.entry_window is not None: config["entry_window_hours"] = args.entry_window
    if args.max_entries_per_day is not None: config["max_entries_per_day"] = args.max_entries_per_day
    if args.strategy == "ha_scalp": config["theta_farming"] = {"enabled": False}
    if args.interval:
        config["bar_interval"] = args.interval
        config.setdefault("ha_scalp", {})["backtest_interval"] = args.interval
    if args.theta is not None:
        config.setdefault("theta_farming", {})["enabled"] = args.theta == "true"
    if args.theta_aggressiveness:
        config["theta_aggressiveness"] = args.theta_aggressiveness
    if args.trend_filter is not None: config["trend_filter"] = args.trend_filter
    run_backtest(config, args.symbols, args.start, args.end, provider=args.provider, strategy_name=args.strategy, data_dir=args.data_dir, json_output=args.json)


if __name__ == "__main__":
    main()
