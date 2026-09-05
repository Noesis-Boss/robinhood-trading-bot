#!/usr/bin/env python3
"""London Breakout day trading bot — live trading via Robinhood (or simulation)."""

import logging
import os
import time
from datetime import datetime, timezone

import pandas as pd
import yaml

from .data import DataFeed
from .strategy import LondonBreakoutStrategy
from .risk import RiskManager
from .journal import TradeJournal
from .theta_farming import ThetaFarmer
from .broker import Broker
from .daily_universe import symbols_for_today

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")


def load_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> int:
    config = load_config()

    tz = pd.Timestamp("now", tz=config.get("timezone", "America/New_York")).tz
    data_feed = DataFeed(config.get("timezone", "America/New_York"))
    journal = TradeJournal("trade_journal.json")
    risk = RiskManager(config)
    broker = Broker(config, risk)
    strat = LondonBreakoutStrategy(config, risk, journal)
    theta_farmer = ThetaFarmer(config.get("theta_farming", {})) if config.get("theta_farming", {}).get("enabled", False) else None

    universe_cfg = config.get("daily_universe", {})
    symbols = symbols_for_today(
        universe_cfg.get("output_path", "daily_universe.json"),
        config["symbols"],
        universe_cfg.get("enabled", False),
        fundamental_config=config.get("fundamental_filter"),
    )
    mode = "LIVE" if broker.enabled else "SIM"
    log.info("London Breakout bot started | symbols=%s | capital=$%s | mode=%s",
             symbols, risk.capital, mode)

    box_cache: dict[str, tuple[float, float]] = {}

    while True:
        try:
            now = datetime.now(timezone.utc)
            et = now.astimezone(tz)
            current_time = et.time()

            if pd.Timestamp("03:00").time() <= current_time < pd.Timestamp("08:00").time():
                # London session: build boxes
                for s in symbols:
                    try:
                        df = data_feed.get_bars(s, "5m", "1d")
                        if df is None or len(df) < 30:
                            continue
                        box = strat.build_london_box(df)
                        if box is not None:
                            box_cache[s] = box
                            log.info("[%s] London box set: low=%.2f high=%.2f", s, box[1], box[0])
                    except Exception as e:
                        log.warning("[%s] London box error: %s", s, e)

            elif pd.Timestamp("08:00").time() <= current_time < pd.Timestamp("12:00").time():
                # NY session: check exits, generate signals
                for s in symbols:
                    if s not in box_cache:
                        continue
                    try:
                        df = data_feed.get_bars(s, "5m", "1d")
                        if df is None or len(df) < 30:
                            continue

                        exit_info = strat.check_exit(s, df, broker)
                        if exit_info:
                            log.info("[%s] EXIT %s @ %.2f | P&L=$%.2f (%s)",
                                     s, exit_info["direction"],
                                     exit_info["exit_price"],
                                     exit_info["pnl"], exit_info["reason"])

                        signal = strat.generate_signal(s, df, box_cache[s])
                        if signal:
                            order = broker.place_order(
                                signal["symbol"], signal["direction"], signal["qty"],
                                entry_price=signal["entry"]
                            )
                            signal["order_id"] = order.get("id") if order else "sim"
                            log.info("[%s] SIGNAL %s @ %.2f | qty=%.3f | target=%.2f stop=%.2f | order=%s",
                                     s, signal["direction"], signal["entry"],
                                     signal["qty"], signal["target"], signal["stop"],
                                     signal["order_id"])

                            if order:
                                strat.on_trade_entered(s, {
                                    "entry": signal["entry"],
                                    "stop": signal["stop"],
                                    "target": signal["target"],
                                    "qty": signal["qty"],
                                    "direction": signal["direction"],
                                })
                            journal.log_trade(signal)
                            if theta_farmer and order:
                                tf_trade = theta_farmer.generate_trade(signal["symbol"], signal["entry"], signal["direction"])
                                if tf_trade:
                                    tf_order = broker.place_spread(
                                        signal["symbol"], tf_trade["short_leg"]["type"],
                                        tf_trade["short_leg"]["strike"], tf_trade["width"],
                                        theta_farmer.size_position(tf_trade["max_loss"] * 100, capital=risk.capital), tf_trade["dte"]
                                    )
                                    if tf_order:
                                        log.info("[%s] THETA %s %.0f strike, width=%s, $%.2f credit | order=%s",
                                                 signal["symbol"], tf_trade["short_leg"]["type"],
                                                 tf_trade["short_leg"]["strike"], tf_trade["width"],
                                                 tf_trade["credit"], tf_order.get("id", "sim"))
                                        journal.log_trade({**signal, "trade_type": "theta_spread", **tf_trade})
                    except Exception as e:
                        log.warning("[%s] NY session error: %s", s, e)

            # After NY session ends, clear boxes for next day
            if current_time >= pd.Timestamp("12:00").time():
                if box_cache:
                    box_cache.clear()
                    log.info("NY session ended — boxes cleared")

        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except Exception as e:
            log.error("Loop error: %s", e)

        time.sleep(300)  # 5-min polling

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
