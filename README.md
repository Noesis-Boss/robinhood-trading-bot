# Robinhood Trading Bot — London Breakout

Day-trading bot built from the 8 principles in [this YouTube video](https://youtu.be/8KblOEu56dM), which describes the "London breakout" strategy used by prop-firm traders.

## Strategy

1. **London box**: 03:00–08:00 ET — record the session's high and low.
2. **NY open breakout**: 08:00–12:00 ET — go long on a break above the box high, short on a break below the box low. One trade per symbol per session.
3. **2:1 reward:risk** — target = 2 × risk; stop = opposite side of box.
4. **Fixed fractional risk** — 2 % of capital per trade ($200 on a $10k account).

### Backtested improvements (win-rate boosters)

| Filter | Effect | Default |
|---|---|---|
| **Box-size volatility filter** | Skip sessions where London range < 0.5 % or > 4 % of price — reduces false breakouts in low/high vol. | `min_box_pct=0.005`, `max_box_pct=0.04` |
| **Breakout strength** | Require breakout to exceed box edge by *N* × box range. Higher = fewer but higher-quality signals. | `breakout_strength=0.75` |
| **Volume confirmation** | Only enter on bars with volume ≥ 0.8 × recent average. | `volume_multiplier=0.8` |
| **Directional bias** | Long only if NY open > box midpoint; short only if NY open < box midpoint. | `true` |
| **Trend filter** | Longs must pass 20-bar SMA uptrend test; shorts must fail it. | `true` |
| **Entry time window** | Only enter in first 3 hours of NY session. | `entry_window_hours=3` |
| **Trailing stop → breakeven** | Once in profit by 1 × risk, move stop to entry. | `true` |
| **Max holding bars** | Force-exit after N bars to avoid EOD randomness. | `max_holding_bars=30` |

### Backtest results (default config, 5 symbols, July 2026)

```
Closed trades: 24
Total P&L: $1,540.05
Wins: 14 | Losses: 10
Win rate: 58.3%
Avg win: $217.75 | Avg loss: $150.84
Profit factor: 2.02
```

### Tuning parameters via CLI

```bash
python backtest.py --symbols SPY --breakout-strength 0.75 --max-bars 30 --rr-ratio 2.0
```

## Files

| File | Purpose |
|---|---|
| `config.yaml` | capital, risk %, session times, symbols, strategy params, Robinhood toggle |
| `src/data.py` | yfinance 5-min bar fetch (pre/post market included) |
| `src/strategy.py` | London box builder, signal generator, trade tracker |
| `src/risk.py` | position sizing + risk validation |
| `src/journal.py` | JSONL trade journal with P&L summary |
| `src/broker.py` | order execution (paper simulation by default) |
| `src/bot.py` | live trading loop — polls every 5 min, builds boxes at 3 AM ET, trades NY session |
| `src/__main__.py` | entry point: `python -m src` |
| `backtest.py` | historical backtest across multiple symbols |

## Setup

```bash
cd /home/workspace/robinhood-trading-bot
pip install -r requirements.txt
```

## Backtest

### Research dashboard

The browser dashboard runs the real backtest engine and is research-only:

```bash
cd /home/workspace/robinhood-trading-bot
python3 web/api.py
cd web && bun run dev
```

Open `http://localhost:5173`. Configure strategy, dates, capital, symbols,
interval, theta, and tuning parameters, then run the historical test. No live
orders are exposed.

```bash
python backtest.py --symbols SPY QQQ --start 2026-07-01 --end 2026-08-06
```

Select the Ross momentum pullback strategy with `--strategy ross`; London remains
the default. Ross uses cumulative session VWAP, EMA reclaim, first-pullback volume
confirmation, pullback-extreme stops, breakeven trailing, and a 10:00 ET cutoff.

Select the Sneaky Pivot reversal strategy with `--strategy sneaky`; London remains
the default. Sneaky Pivot uses 15-minute local swing levels plus prior-day high/low,
three-candle confirmation, level-proximity entries, level-based stops, and opposite-
range targets. It is research-only until broader validation is complete.

The Heikin-Ashi scalping strategy is selectable with `--strategy ha_scalp`. It uses
Heikin-Ashi candles, a 100 EMA trend filter, two-candle clean pullbacks, high-volume
doji entries, and 1:1 targets. The six-month Alpaca test at $300 used 15-minute bars
because a literal six-month 1-minute query exceeded the practical data/runtime limit;
the 15-minute run across the full 13-symbol universe produced zero qualifying signals.

Run independent one-minute symbol tests and aggregate them:

```bash
python3 batch_ha_backtest.py --symbols SPY QQQ AAPL TSLA NVDA SOFI F AAL MARA RIVN NIO RBLX DKNG \
  --start 2026-07-10 --end 2026-08-10 --capital 300
```

Each symbol starts with its own $300 allocation; the aggregate is a research summary,
not a single account-level compounding simulation.

Canonical Alpaca IEX comparison, 2026-07-01 through 2026-08-06, full 13-symbol
universe: Ross produced 676 trades (338 directional and 338 theta), -$2,321.58
total P&L, 46.3% overall win rate, and 0.68 profit factor. Directional P&L was
- $3,408.64 and theta P&L was +$1,087.06. London produced 66 trades, +$1,232.18,
59.1% win rate, and 1.44 profit factor under the same run. These are historical
research results, not a live-performance claim; Ross needs further filtering before
paper-trading consideration.

Select `vwap_liquidity_proxy` for the disabled research-only VWAP reclaim proxy. It uses session VWAP, relative volume, ATR risk, and OHLCV safety filters; it does not reproduce Bookmap, iceberg, bid/ask, or futures order-flow data.

Select `t3_range_filter` for the disabled research-only long strategy using T3 trend, green Range Filter direction, ATR risk, and a configurable 1R/2R/3R target. It prefers 1-hour bars and falls back to the configured interval. Neither strategy is available to paper or live execution.

Select `reversal_zone_confirmation` for the disabled research-only OHLCV proxy based on 15-minute rolling zones, fast moves into support/resistance, 1-minute structure confirmation, volume, ATR stops, and fixed reward/risk. It defaults to the 09:35–11:00 ET window and 1-minute bars. It does not reproduce discretionary zone drawing or futures execution and is unavailable to paper/live execution.

## Live (simulation mode)

```bash
python -m src
```

No Robinhood credentials needed — runs in simulation by default. All signals log to stdout; completed trades append to `trade_journal.json`.

## Live (Robinhood)

1. Add to [Settings → Advanced](https://jaknyfe.zo.computer/?t=settings&s=advanced):
   - `ROBINHOOD_USERNAME`
   - `ROBINHOOD_PASSWORD`
   - `ROBINHOOD_MFA_TOKEN`
2. Set `robinhood.enabled: true` in `config.yaml`.

> **Risk warning**: this is a learning scaffold. Past performance is not indicative of future results. Paper-trade first.

## Ross-style daily universe scanner

The optional daily scanner ranks premarket candidates using the stock-selection framework from the Ross Cameron transcript: upward gainers, $1–$20 price, relative volume, low float, catalyst presence, spread, and liquidity. The configured profile prefers at least 4% gains, 5x relative volume, and float below 20 million shares; it returns ranked near-misses instead of an empty result when optional data is missing. It remains disabled by default and does not place orders.

## Improving the win rate

Current baseline: 58.3% win rate, 2.02 profit factor (24 trades, Jul–Aug 2026).

The biggest win-rate lever is **filtering bad setups**, not adding more entries. Each filter removes losing trades but also removes some winners — the key is finding the filter that adds the most net value per trade.

### Recommended tuning order (test one at a time)

1. **Widen breakout strength** from 0.5 → 0.75 → 1.0. Each +0.25 reduces entries ~15% but lifts win rate 3–5% by requiring a stronger push through the box edge. Use `python backtest.py --breakout-strength 0.75`.
2. **Enable directional bias + trend filter** (both already `true`). Confirms the breakout is *with* the broader trend — the single most effective filter.
3. **Tighten the max holding bars** from 45 → 30 → 18. London breakouts are fast; holding past 2–3 hours mostly captures reversals. Use `--max-bars 30`.
4. **Add a box-size volatility filter** if not yet active: `min_box_pct=0.005` skips low-volatility sessions that grind sideways; `max_box_pct=0.04` skips news-driven sessions that whip.
5. **Narrow the entry window** to the first 2 hours of the NY session (`--entry-window 2`). Breakouts lose edge after 10 AM ET.
6. **Switch to 30-min box bars** to smooth noise, or add a 2-bar confirmation close (require price to close above box high on the next bar).

Run a sweep:
```bash
python backtest.py --breakout-strength 0.5  &&  echo "---" && \
python backtest.py --breakout-strength 1.0  &&  echo "---" && \
python backtest.py --breakout-strength 1.0 --max-bars 18 --rr-ratio 3.0
```

## Other day-trading strategies (higher win rate, more complex)

### Options theta farming (credit spreads)

After a confirmed London breakout, sell a **put credit spread** (bullish) or **call credit spread** (bearish) 2-5 DTE. This harvests time decay on the *opposite* side from the breakout — if the move stalls, theta burns the option premium while you keep the credit. If the breakout holds, you simply don't enter the spread.

Config in `config.yaml` under `theta_farming:`:
- `enabled` — off by default (requires options approval on Robinhood)
- `min_days_to_expiry` — 2-5; longer = more theta but more risk window
- `target_pop` — probability of profit threshold (0.80+); only sell when POP is high
- `max_spread_width_pct` — max spread width as % of stock price (0.03–0.05)
- `contracts_per_trade` — 1 contract for <$50k account; scales with capital
- `max_risk_per_trade_pct` — 1-2% of capital per spread

> **Note**: Robinhood options support requires the broker to approve options trading. Start with paper trades via the simulation mode first. The `broker.py` supports a `place_spread` method when `ROBINHOOD_USE_OPTIONS=true` is set in env.

## Ross Momentum Pullback

Select the Ross Cameron-style first-pullback strategy with `--strategy ross`; London remains the default.

The canonical Alpaca IEX comparison (2026-07-01 through 2026-08-06, full 13-symbol universe) produced 676 Ross trades, -$2,321.58 P&L, 46.3% win rate, and 0.68 profit factor. London produced 66 trades, +$1,232.18 P&L, 59.1% win rate, and 1.44 profit factor. These are historical research results, not live-performance claims.
