# Robinhood Trading Bot — Memory

## Project Overview
London Breakout day-trading bot. From video https://youtu.be/8KblOEu56dM (Don McMillan comedy).
Builds a price box during London session (3:00–8:00 AM ET), then trades breakouts
during NY session (8:00 AM–12:00 PM ET). Volume confirmation, breakout-strength
buffer, directional bias, trailing stop to breakeven.

**Backtest results** (2026-07-01 to 2026-08-06, 25 trading days, 5 symbols):
- 24 LD trades + 24 theta spreads = 48 total, 64.6% win rate
- P&L: +$565.87 total; directional-only 24 trades +$666.73 (68.2% win)

## Theta Realism Fix (2026-08-08)
Prior theta model booked every spread as a guaranteed full-credit win (inflated
+$4,643 / 6.26 PF / 79.2%). Fixed in src/theta_farming.py + backtest.py:
- `_estimate_credit` clamps premium to realistic $5-$15/contract, bounds spread
  width so max loss is ~$20-$30/contract.
- `simulate_expiry` resolves each spread by POP (80% win full credit, 20% take
  max loss) with random.seed(42) for reproducibility.
- Result: 17 win @ +$9.29, 7 lose @ -$30.00 -> theta nets **-$52.07** (71% win),
  not a guaranteed profit. Whole-backtest theta numbers now land in range.

## Files
- `config.yaml` — strategy + theta farming config
- `src/data.py` — DataFeed (yfinance 5m bars, London box + premarket data)
- `src/strategy.py` — LondonBreakoutStrategy (box, signal, exit, trailing stop)
- `src/risk.py` — RiskManager (position sizing, capital, cash tracking)
- `src/broker.py` — Broker (Robinhood orders + credit spreads)
- `src/theta_farming.py` — ThetaFarmer (credit spread builder/sizer)
- `src/journal.py` — TradeJournal (JSONL logging)
- `backtest.py` — historical backtest engine (includes theta spreads)
- `project.py` — Monte Carlo projections (both $100 and $1K, with theta)
- `project_theta.py` — Theta farming-only projections

## Theta Farming Parameters (revised 2026-08-06)
After a confirmed London Breakout breakout, sell weekly credit spreads.
- 72% win rate (spreads expire worthless), 28% hit max loss
- Weekly cadence (~5 trading days between spreads)
- **Capital-aware contract scaling**: `contracts = int(risk_amount / max_loss)`, no floor
- Spread width: $0.30/share ($30/contract) | Credit: $10.00/contract | Max loss: $20.00/contract
- Risk: 10% of capital per spread → ~$200 threshold for 1 contract
- Above threshold: $300 → 1 contract (7% risk), $1,000 → 5 contracts (10% risk)
- Below threshold ($100): theta disabled, pure London Breakout day trading
- Config: `config.yaml` → `theta_farming.enabled: true`
- Live trading requires options approval on Robinhood

## Capital-Aware Projections (combined LB + Theta, 20K sims)
Run with updated theta parameters (10% risk, $20 max loss/contract, $200 threshold).

### $100 starting capital (theta disabled — below $200 threshold)
- 1 day:    +$1.45  (+1.5%)
- 1 week:   +$4.43  (+4.4%)
- 1 month:  +$18.78 (+18.8%)
- 3 months: +$71.92 (+71.9%)
- 6 months: +$195.05 (+195.0%)
- 1 year:   +$1,818 (+1,818%)

### $300 starting capital (theta enabled — 1 contract/trade, ~7% risk)
- 1 day:    +$4.97  (+1.7%)
- 1 week:   +$18.96 (+6.3%)
- 1 month:  +$81.22 (+27.1%)
- 3 months: +$367.83 (+122.6%)
- 6 months: +$1,268.32 (+422.8%)
- 1 year:   +$8,230.02 (+2,976.7%)

### $1,000 starting capital (theta enabled — 5 contracts/trade, ~10% risk)
- 1 day:    +$17.54  (+1.8%)
- 1 week:   +$69.75 (+7.0%)
- 1 month:  +$315.65 (+31.6%)
- 3 months: +$1,381.56 (+138.2%)
- 6 months: +$4,735.32 (+473.5%)
- 1 year:   +$33,307.53 (+3,330.8%)

## Win Rate Improvements Applied
1. Volume filter — breakout bar must exceed avg volume
2. Breakout-strength buffer (0.75× box range)
3. Directional bias (NY open must be on same side of box midpoint)
4. Trend filter (5-min EMA trend confirmation)
5. Max holding bars (30 bars)
6. Trailing stop to breakeven

## Window Retune — Alpaca PreMarket Box (2026-08-08, option 1)
Free Alpaca IEX has no London-session bars (earliest 08:00 ET), so the box is now
built from the **premarket window 08:00-09:25 ET** and entries taken on regular-
session breakouts **09:30-12:00 ET** (config.yaml values retuned; keys unchanged).

Canonical backtest via Alpaca, 2026-07-01 -> 08-06, 13 symbols, capital 10000:
- **66 trades** (33 directional + 33 theta), **+$1,231.62**, 59.1% win, PF 1.44
- Directional: +$1,203.30 (16W/17L, avg +$36.46) | Theta: +$28.32 (23W/10L)
- Exits: theta_spread 33, eod_close 24, stop_loss 7, target_hit 2

## Fractional Shares + Expanded Universe (2026-08-07)
- `fractional_shares: true` (config.yaml) — long sizing is now fractional (risk dollars / risk-per-share, rounded to 4dp), so any stock works with a small account. Shorts stay whole-share (RH doesn't allow fractional shorts).
- `min_order_value: 1.0` — skips entries whose notional (qty * entry) is below $1.
- bot.py now passes `entry_price` to broker.place_order so capital validation actually runs.
- Universe expanded 5 → 13: added low-priced, high-liquidity, optionable names SOFI, F, AAL, MARA, RIVN, NIO, RBLX, DKNG (weekly options for theta).
- Smoke backtest (QQQ/NVDA/SPY/SOFI/F, 2026-07-20→31): 28 trades, 85.7% win rate, +$1,432, PF 3.82; fractional qty verified live in trade logs.

## $300 Capital Backtest (2026-08-08, realistic theta)
Added `--capital N` CLI flag to backtest.py (overrides config["capital"], max_risk_dollars,
and theta initial_capital). Run: `python3 backtest.py --capital 300 --symbols <13>`.
- 198 trades (99 theta spreads + 99 equity day-trades), 67.2% win, PF 1.28, **net +$189.63**.
- Theta: +$134.02 (77 wins @ +$9.29, 22 losses @ -$30, avg +$1.35/spread) — realistic band.
- Equity day-trade at $300 (2% risk = $6/trade): +$55.61 (56.6% win, avg +$0.56/trade,
  best +$10.16 MARA long, worst -$6.02 AAL stop). Small notional caps equity gains at $300.

## Alpaca Retune + Canonical Result (2026-08-08)
Free Alpaca IEX has no London data (earliest bar 08:00 ET), so option 1 applied:
box rebuilt from premarket 08:00-09:25 ET, entries regular session 09:30-12:00 ET
(config keys london_open/close, ny_open/close kept, values retuned).

Canonical backtest via Alpaca (2026-07-01->08-06, 13 symbols, capital 10000):
66 trades (33 directional + 33 theta), +$1231.62, 59.1% win, PF 1.44.
Equity +$1203.30 (avg +$36.46/trade); theta +$28.32 (realistic).
Exit: theta 33, eod_close 24, stop_loss 7, target_hit 2. See AGENTS.md.

Recommended source: Alpaca IEX, free ($0/mo). Paids (Polygon $29/$79/$199, Alpaca SIP
$99) each eat too much of a ~$40 theta edge at $200-300 capital. Revisit after proof.

2026-08-09: Theta revenue now compounds through the shared RiskManager cash ledger; directional and theta sizing use updated capital. Regression assertions pass.
