# Robinhood Trading Bot — Project Guidance

London/premarket-breakout day-trading bot. Source strategy: video https://youtu.be/8KblOEu56dM.
Builds a consolidation box over a window, then enters on either the box-high breakout
(long) or box-low breakdown (short) with volume confirmation, a breakout-strength buffer,
directional bias, trend filter, trailing stop to breakeven, and a max holding period.

## Data Provider & Cost (decided 2026-08-08)

**Use Alpaca — IEX feed, free ($0/month).** This is the recommended source for the
current $200–$300 account.

- `provider="auto"` in `backtest.py` uses Alpaca when `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`
  are set in Settings > Advanced; otherwise falls back to yfinance.
- Alpaca IEX gives real-time 1m/5m/15m OHLCV bars + WebSocket streams, free for paper
  trading, and historical 5m bars well beyond Yahoo's ~60-day limit (enables 6-month backtests).
- **Limits:** IEX has no bars before **08:00 ET** (earliest SPY bar 08:05) and the feed
  is gappy on high-volume small-caps (MARA, SOFI) — empty bars expected, not a bot fault.
- Yahoo 5m data is capped at ~60 days and has no premarket bars (earliest 09:30), so
  don't use it for long backtests.

Paid upgrades NOT justified at this capital (each eats a chunk of the ~$40/trade theta
edge before you trade): Polygon Starter $29/mo is delayed 15-min (unusable for day
trading), Polygon Dev $79/mo, Polygon Advanced $199/mo, Alpaca SIP $99/mo. Revisit only
after the strategy is proven.

## Window Retune (2026-08-08) — option 1 accepted

The box must be built from bars the data source actually provides. Free Alpaca IEX has
no London-session data, so the box is now built from the **premarket window 08:00–09:25 ET**
and entries are taken on **regular-session breakouts 09:30–12:00 ET**.

Config keys in `config.yaml` (kept for backward compat, values retuned):
- `london_open: "08:00"` (premarket box start)
- `london_close: "09:25"` (premarket box end, just before regular open)
- `ny_open: "09:30"` (entry window start = regular session open)
- `ny_close: "12:00"`

Default `--symbols` is 5 core; pass the full 13 for the full universe:
`SPY QQQ AAPL TSLA NVDA SOFI F AAL MARA RIVN NIO RBLX DKNG`.

## Backtest (canonical, via Alpaca, 2026-07-01 to 2026-08-06)

Run:
```
python3 backtest.py --provider alpaca \
  --symbols SPY QQQ AAPL TSLA NVDA SOFI F AAL MARA RIVN NIO RBLX DKNG \
  --start 2026-07-01 --end 2026-08-06
```

Results with the retuned premarket-box windows (`capital: 10000`):
- **66 trades** total: 33 directional day-trades + 33 theta spreads
- **+$1,231.62 net**, 59.1% win rate (39W/27L), profit factor 1.44
- Directional equity: 33 trades, +$1,203.30 (16W/17L, avg +$36.46/trade)
- Theta spreads: 33, +$28.32 (23W/10L, avg +$0.86/spread) — realistic band, not a
  guaranteed profit (realism fix: seed 42, `_estimate_credit` clamps $5–15/contract,
  spread width bounds max loss ~$20–30)
- Exit reasons: theta_spread 33, eod_close 24, stop_loss 7, target_hit 2

## EPS-Line Put Selling (added 2026-09-04, paper-only)

Strategy: `src/eps_line_put_selling.py` — sell LONG-dated puts (default 730 DTE, the
"two-year put") when price is at/below the EPS line (trailing EPS x target P/E, default 15).
Cash-secured by default; optional margin securing for stress testing. Strike defaults to the
EPS line itself (assignment at fair value is the thesis). Premium via Black-Scholes (bs_put_price).
Non-earners are skipped: generate_trade returns None for zero/negative EPS, so loss-making
trailing-EPS symbols (e.g. F) can never anchor a nonsensical strike.
Config: `eps_line_put_selling` block in config.yaml (`eps` per-symbol map, `target_pe`, `dte`, `iv`,
`max_collateral_pct` 0.30, `min_days_between_entries` 21, `securing` cash|margin, `margin_leverage`).
Requires per-symbol EPS in config or no trades fire. Wired into STRATEGY_MAP and web API
(`--strategy eps_line_put_selling`); summary reports premium_collected / open_max_liability /
unrealized_mtm (Black-Scholes mark-to-market of open puts at the window-end close).
Entry gate: `min_yield_annual_pct` (default 5.0) blocks entries whose annualized yield
(premium/strike, DTE-adjusted) is below the floor — dead-money low-IV entries never fire;
each trade reports `yield_annual_pct`. Entry-quality gate (2026-09-05):
`max_distance_to_line_pct` (default 2.0) requires price within 2% of the EPS line, and
`rsi_period`/`rsi_max` (14/40.0) require RSI below 40 on the entry day — deep-ITM or
recently-rallied entries never fire. Both are Strategy Lab UI params.
Zero-param runs work: config.yaml `eps_line_put_selling` seed (SPY/QQQ/T/VZ) + auto-resolve
of missing trailing EPS via yfinance in the runner.

Margin stress: `src/margin_stress.py` — replays the real 2008 SPX monthly path (-38.5%) with
stressed IV on down months, maintenance-margin check, forced-liquidation spiral detection.
Run: `python3 -m src.margin_stress --portfolio-value 100000 --eps 28 --securing margin --margin-leverage 2.0`
Result at 2x margin: MARGIN_CALL in month 11 (Oct 2008 -16.8%), final equity $28.4k (-72% on a
-38.5% year). 1 cash-secured contract: SURVIVED, $64.8k (-35%) — drawdown without spiral.
PAPER ONLY — no order placement anywhere in the module.

Book replay (added 2026-09-04): `replay_book(portfolio_value, eps, ...)` in margin_stress.py rolls a
staggered entry schedule (num_entries, entry_spacing_days) through the 2008 monthly path. Entries
are gate-filtered (min_yield_annual_pct) and strike-sized at the EPS line; puts price at their own
entry-month spot with independent remaining DTE. VZ book ($100k, EPS 3.84, 4 entries / 21-day
spacing): cash-secured SURVIVED at $78.8k (-21% on a -38.5% year); 2x margin MARGIN_CALL month 10
(Oct 2008), final $38.0k (-62%). CLI: `--num-entries 4 --entry-spacing-days 21`.

## ORB + FVG (added 2026-09-05, paper-only)

Strategy: `src/orb_fvg.py` — from "The One Candle Setup" video (Cryptic Hustle).
Marks the first 5-min candle (09:30-09:35 ET, wick-inclusive) high/low on 1-min bars,
waits for a 1-min close outside the range, then requires a 3-candle FVG in the
breakout direction (c1 to c3 window scanned from the breakout bar; c1 may be the
breakout candle). Entry at c3 close, stop at the FVG extreme (wick-inclusive:
c1.high for longs, c1.low for shorts), fixed 2R target, 1 trade/day, entries stop
at 11:30, max hold 90 bars. Registered as `orb_fvg` in STRATEGY_MAP; config block
`orb_fvg` (backtest_interval "1m"). NQ futures are not available on Alpaca — QQQ
is the proxy.

Baseline backtest (QQQ, Alpaca IEX 1m, 2026-08-01 to 2026-08-28, theta disabled,
execution realism on: 5bps slippage + 5bps spread):
- 18 trades, 3W/15L (16.7% win), PF 0.07, net -$368.04, gross -$30.88
- Negative BEFORE costs: the setup itself has no edge at these parameters.
- Root cause: wick-inclusive 1-min FVG stops are pennies wide, so 2R targets are
  tiny in absolute terms (~$0.10-0.25/share); the ~$0.15/share round-trip cost
  (spread+slippage) exceeds the target distance. Stops also get tagged by normal
  1-min noise (13/18 stopped).
- Verdict: fails as specified. Do NOT enable for live (source video evidence
  quality 2/10: no verified track record, cherry-picked examples).

5-min FVG variant (2026-09-05, same window, backtest_interval 5m, max_holding 18
bars = 90 min): 14 trades, 3W/11L (21.4% win), PF 0.07, net -$286.11, gross
-$21.99 — still negative before costs. Wider stops did not help: 8/11 losses
were shorts into a rallying month (QQQ 690→733); longs were gross +$62 on 4
trades but the sample is far too small to call an edge. BOTH timeframes fail;
strategy closed. Parked, not in rotation, no further variants planned.

Run: `python3 -m src.backtest_runner --strategy orb_fvg --symbols QQQ --start 2026-08-01 --end 2026-08-28 --provider alpaca --json`
(theta_farming.enabled was true in config.yaml and leaked theta_spread trades
into the first run — disable it or pass a stripped config for orb_fvg runs.)

## Key Source Files

- `config.yaml` — strategy + theta farming params (tuning knobs: `breakout_strength`
  `max_holding_bars`, `rr_ratio`, `entry_window_hours`, `min_box_pct`/`max_box_pct`)
- `src/data.py` — `DataFeed` (alpaca IEX + yfinance fallback)
- `src/strategy.py` — `LondonBreakoutStrategy` (box, signal, exits, trailing stop)
- `src/risk.py` — `RiskManager` (position sizing, cash tracking; fractional longs,
  whole-share shorts)
- `src/broker.py` — order placement + credit spreads
- `src/theta_farming.py` — `ThetaFarmer` (weekly credit spreads after confirmations)
- `src/journal.py` — JSONL trade journal
- `backtest.py` — historical backtest engine (directional + theta)
- `project.py` / `project_theta.py` — capital projections → `projections*.json`

## Workflow Notes

- Live trading = paper-sim by default; real Robinhood only via env secrets, never paste
  keys in chat.
- Theta farming needs options approval on Robinhood.
- Before a 6-month run, confirm data source can reach that far (Alpaca yes, Yahoo no).

## Issue Log

- 2026-09-03 — Restored Graphify `post-commit` and `post-checkout` hooks; `graphify hook status` reports both installed and the merge driver registered.

- 2026-08-24 — Completed the interrupted four-layer monitor UI/API integration. Removed duplicate monitor CSS, fixed JSON serialization of infinite profit factor values, and populated behavior trade counts. API JSON, production build, and browser screenshot verified. Three monitor test failures remain isolated to the test fixture's market-hour timestamp generator producing only 7 of its expected 10 rows; the live monitor renders correctly.

- 2026-08-22 — Fixed `tests/test_robinhood_readonly.py` cash assertion (expected string "100.00"; adapter returns floats). Full suite green: 46 passed.

- 2026-08-16 — Fixed the public `/api/zz-dbtest` import error by replacing unsupported `node:sqlite` with the installed `sqlite3` CLI via `Bun.spawn`. Live endpoint now reports both databases successfully: 11,340 and 11,969 scholarships; Space error count is 0.

- 2026-08-16 — Added shared research execution realism: invalid/zero-volume bars are rejected; directional results now report gross P&L, execution cost, and net P&L using configurable 5 bps slippage plus 5 bps spread defaults. HA scalp now has explicit minimum wick-ratio validation. Research strategies remain blocked from paper/live execution.

- 2026-08-16 — Live Strategy Lab rejected the two new research strategies with `Choose a supported strategy` because the public `/api/backtests/*` route retained an older four-strategy allowlist. Expanded the live allowlist to all 8 strategies and forwarded `strategy_params`; live VWAP and T3 API runs now complete successfully.

- 2026-08-16 — Added selectable research-only `vwap_liquidity_proxy` and `t3_range_filter` strategies. VWAP is an OHLCV reclaim proxy and cannot reproduce Bookmap/iceberg/order-flow data. T3 is long-only with T3, green Range Filter, ATR, and safety filters. Both preserve London as default and are blocked from paper/live execution. Focused tests and full suite pass. Six-month 13-symbol VWAP run (2026-07-01 through 2026-08-06, theta disabled) produced 219 trades, 38.81% win rate, 1.07 profit factor, and +$273.69 P&L. T3 produced zero qualifying trades in that sample and needs rule/data review before further conclusions.

- 2026-08-15 — Evaluated the Fabio Valentini auction/order-flow model from the referenced video. Added deterministic OHLCV-only safeguards to `auction_flow_proxy`: directional rejection confirmation, maximum gap filtering, and abnormal-bar-range filtering. Focused and full regression suite: 35 passed. A six-month 13-symbol directional research run (2026-02-10 through 2026-08-10, theta disabled in the directional aggregation) produced 263 trades, 31.94% win rate, 0.18 profit factor, and -$1,443.05 P&L. The strategy remains research-only and must not be enabled for paper/live execution. True footprint/order-flow data and bid/ask spread data are unavailable from the current OHLCV feed.

- 2026-08-09 — Theta P&L previously accumulated in `ThetaFarmer`/`strat._theta_capital`, so it did not compound with directional trades. Fixed by passing shared `RiskManager.capital` into theta sizing and applying theta expiry P&L through `risk.update_cash()`. Regression assertions pass; the Alpaca smoke backtest was blocked because the optional `alpaca` Python package is not installed in this environment.

## Feature Log

- 2026-08-28 — Added the disabled-by-default `ema20_stoch_pullback` research strategy from the Trader DNA video: 20 EMA deviation pullback, Stochastic 8/5/3 crossover, and target at 25% of the distance from entry back to the EMA. Restored missing engine modules from `https://github.com/Noesis-Boss/robinhood-trading-bot` and corrected the local `origin`, which had incorrectly pointed to `domain-finder.git`. The 13-symbol Alpaca run for 2026-07-01 through 2026-08-06 executes successfully but produces 0 trades and $0 net P&L; no profitability claim.

- 2026-08-25 — Added disabled-by-default `ema9_continuation` research strategy based on the SMB Capital 9 EMA continuation tutorial. It uses objective OHLCV proxies for EMA pullback touch, reclaim/rejection, volume confirmation, ATR-defined risk, and paper-only exits; registered in the CLI, API allowlist, Strategy Lab parameters, config, and focused tests. No live or paper-order execution wiring was added.

- 2026-08-25 — Completed the 100-variant strategy boilerplate evaluation: 100 variants ran without execution errors and 75 produced trades. The three top-ranked London variants each had only nine trades, so they remain paper-only. Fixed the forward tester to construct and pass the required premarket box; a $100/latest-10-day incubation run produced zero trades because Alpaca IEX supplied insufficient continuous premarket bars (only 08:25 and 08:30 ET on the inspected August 24 session). Results documented in `framework/REPORT.md`; no live trading enabled.

- 2026-08-22 — Added disabled-by-default `ema_cci_macd` research strategy (`src/ema_cci_macd.py`): EMA 50/110 trend filter, CCI(20) pullback into the trend zone, MACD momentum turn, volume multiplier, ATR stops/targets, session/gap/range guards. Registered in CLI, backtester, live API allowlist, and Strategy Lab dropdown with strategy-specific parameters. Focused tests 5 passed; full suite 46 passed. Six-month 13-symbol run (2026-07-01→2026-08-06, theta disabled): 142 trades, 29.58% win rate, 0.44 profit factor, gross +$131.87, execution cost -$2,496.32, net -$2,364.45. Rejected for enablement; remains research-only.

- 2026-08-22 — Added disabled-by-default `ema_cci_macd` research strategy in `src/ema_cci_macd.py`: EMA 50/110 trend, CCI(20) pullback into the trend zone, MACD momentum turn, volume multiplier, ATR stop/target, session and gap/range guards. Registered in CLI, backtester, live API allowlist, and Strategy Lab dropdown with strategy-specific parameters. Focused tests (5) and full suite (46) pass. Six-month 13-symbol run (2026-07-01 to 2026-08-06, theta disabled): 142 trades, 29.58% win rate, 0.44 profit factor, gross +$131.87, execution cost -$2,496.32, net -$2,364.45. Rejected for enablement; remains research-only.


- 2026-08-18 — Added disabled-by-default `reversal_zone_confirmation` research strategy. It converts the video’s futures reversal setup into an OHLCV proxy with rolling support/resistance zones, fast-move, 1-minute structure, confirmation-body, volume, ATR, session, and reward/risk controls. Added CLI/API/Strategy Lab registration and focused tests. It remains research-only; discretionary zone judgment and futures execution are not reproduced.

- 2026-08-18 — Expanded the live investment dashboard holdings feed to include stocks, crypto, and open options when present. Added asset-type labels, crypto quotes/market values, and holdings-table columns; live screenshot verified ELMT/SPCX stocks plus BTC/DOGE crypto.

- 2026-08-18 — Fixed live Robinhood dashboard authentication and data rendering. The managed adapter now receives the existing Zo secrets, runs from the project virtualenv with `robin-stocks`, normalizes account/holding values for the UI, and returns the live account snapshot. Screenshot verified portfolio value ($41.85), cash, buying power, two holdings, and recent activity.

- 2026-08-18 — Added separate public read-only investment dashboard at `https://jaknyfe.zo.space/robinhood-investments`, distinct from the research-only Strategy Lab. It displays account KPIs, holdings, recent activity, refresh state, and explicit credential/unavailable states. The adapter runs as a private process service on localhost:8787; screenshot verification passed.

- 2026-08-18 — Added read-only Robinhood account adapter at `src/robinhood_readonly.py` and `/api/robinhood/status`. It exposes cash, buying power, portfolio value, positions, and orders only; missing credentials return `not_configured`, and authentication failures return a bounded error. No order-placement or live-trading controls were added. Focused tests and API tests: 8 passed.

- 2026-08-16 — Deployed shared execution-realism UI updates to the public Strategy Lab. Live health and page checks returned 200/ok; browser screenshot verified readable rendering, all 8 strategies, and HA-specific wick controls.

- 2026-08-16 — Strategy Lab now lists all 8 registered strategies and dynamically displays each strategy’s complete parameter set. Selected values are forwarded as `strategy_params` into the backtest configuration; VWAP and T3 research strategies default to their required intervals. Browser verification confirmed VWAP and T3 controls render correctly.

- 2026-08-15 — Added disabled-by-default `fundamental_filter` research integration inspired by Investment Council. It scores daily-universe candidates deterministically from available metrics, writes `fundamental_context.json`, rejects only below the configured floor when enabled, and applies a bounded ranking bonus. It never creates orders or changes strategy risk controls. Focused and full test suite: 32 passed. Broader out-of-sample validation is still required before enabling it.

- 2026-08-12 — Added selectable `auction_flow_proxy` research strategy. It approximates the Chris Kmer auction-market process with OHLCV-only trend, Fibonacci location, VWAP, volume, wick-failure, swing-risk, and session filters. It is explicitly labeled a proxy; no GEX, footprint, delta, or live-order behavior is included. Focused tests, full suite (28 passed), frontend build, and dashboard screenshot passed.

- 2026-08-12 — Added selectable `theta_only` options research with scanner-first/fixed-universe fallback and Conservative, Balanced, and Aggressive presets. It sells only defined-risk credit spreads, reports selection mode and theta-specific results, and never opens directional positions. Tests: 25 passed; frontend production build passed.

- 2026-08-12 — Added the `max_entries_per_day` Strategy Lab picker with 1, 2, 3, 5, and Unlimited options. The limit is enforced per ticker/day across London, Ross, Sneaky Pivot, and Heikin-Ashi backtests; default is 1. Tests: 21 passed; frontend build and live screenshot verified.

- 2026-08-11 — Added visible `RUN STOCK PICKER` and `APPLY PICKS` controls to the public Strategy Lab. The picker endpoint returns ranked/fallback symbols, shows the result before replacement, and browser verification confirmed 13 candidates render correctly.

- 2026-08-11 — Hosted the research dashboard at https://jaknyfe.zo.space/robinhood-trading-bot as a public Zo Space subdirectory. The page is screenshot-verified; `/api/backtests/*` bridges the UI to the existing Python backtest engine, and `/api/health` returns `{"status":"ok"}`. No live-order controls were added.
- 2026-08-11 — Updated all three public dashboards with scanner context: Strategy Lab displays the Ross-ranked universe profile, Strategy Comparison documents fixed-symbol fair comparisons, and Paper Trading Monitor shows scanner configuration plus disabled-by-default safety status. All three pages were screenshot-verified.

- 2026-08-11 — Added `web/` research dashboard with validated local API, real CLI-backed JSON results, controls for current strategies and parameters, metric/equity/trade views, and no live-order controls. Python/API tests: 5 passed; Vite production build passed; browser screenshot verified the rendered idle state.

- 2026-08-10 — Added `src/daily_universe.py` with asset/metric filters, weighted candidate scoring, deterministic JSON output, stale-date/static fallback, and a manual JSON-input CLI. Added `daily_universe` config with live use disabled by default and wired `src/bot.py` to consume only a current-day scan when explicitly enabled. Historical backtests retain their static symbol list. Offline tests: 13 passed; live Alpaca scan not run.
- 2026-08-10 — Hardened daily scanner selection: missing quotes no longer veto a candidate, hard safety filters are separated from soft ranking filters, near-misses are returned in `watchlist`/`actionable`, and empty scans now expose explicit `fallback_candidates` with `selection_mode: static_fallback`. Scanner tests: 4 passed.
- 2026-08-11 — Upgraded the daily scanner with Ross-style ranking: configured $1–$20 price, 4% minimum gain, 5x preferred relative volume, up to 200% gain ceiling, low-float preference under 20M shares, catalyst scoring, and a lower $5M average-dollar-volume floor. Missing float/catalyst data remains score-neutral rather than a hard rejection. Scanner tests: 5 passed.

- 2026-08-09 — Added selectable `RossMomentumStrategy` from the Ross Cameron transcript: momentum impulse, first pullback, VWAP/9-EMA reclaim, volume confirmation, pullback stop, breakeven, and 10:00 ET cutoff. Use `python3 backtest.py --strategy ross`; London remains the default. Unit tests pass. The canonical Alpaca period produced zero Ross signals, so no profitability claim is made until the scanner thresholds and a broader sample are evaluated.

## Feature Log

- 2026-08-09 — Added selectable `RossMomentumStrategy` in `src/ross_momentum.py`, deterministic tests in `tests/test_ross_momentum.py`, `--strategy {london,ross}` with London default, and `ross_momentum` config thresholds. Canonical Alpaca run completed: Ross 676 trades, -$2,321.58, 46.3% win rate, 0.68 profit factor; London comparison 66 trades, +$1,232.18, 59.1%, 1.44. Ross is research-only until its high zero/stop-loss rate is addressed.
- 2026-08-10 — Added selectable `SneakyPivotStrategy` in `src/sneaky_pivot.py`, deterministic tests in `tests/test_sneaky_pivot.py`, and `--strategy sneaky`. A two-symbol Alpaca smoke run (SPY/QQQ, 2026-07-01 to 2026-08-06) produced 68 trades, -$35.31, 60.3% win rate, and 0.93 profit factor. This is not a profitability claim; the strategy remains research-only.
- 2026-09-04 — `eps_line_put_selling`: EPS auto-fetch wired in the runner (`src/backtest_runner.py` `_resolve_missing_eps` — CLI and `/api/backtest` both go through backtest.py, so the web API inherits it; logs `Auto-resolved trailing EPS for <SYM>: <value>`) (`src/eps_line_put_selling._parse_eps` now accepts `eps: {"eps": {SYM: val}}` from `/zo/ask`-style wrappers). Live yfinance validation 2026-07-01→2026-09-03, $100k, VZ (EPS 3.87, PE line 58.05): 4 cash-secured positions (21-day spacing), $28,495 premium collected, $77,691 open max liability, paper-only. Caveat fixed: local-only `main` branch was shadowing `master`; unified to `master`, set upstream, force-pushed `6218d0b`; remote and local are in sync.
- 2026-09-05 — Strategy Lab UI: added `eps_line_put_selling` to both the repo dashboard (`web/src/App.tsx`, commit 55c04bd) and the live zo.space Strategy Lab route. Screenshot-verified at /robinhood-trading-bot: dropdown shows "EPS-line put selling (paper)" and selecting it renders all 7 params (target_pe 15, dte 730, iv 0.30, max_collateral_pct 0.30, min_days_between_entries 21, min_yield_annual_pct 5, securing cash).
- 2026-08-10 — Added selectable `HAScalpStrategy` in `src/ha_scalp.py` and `--strategy ha_scalp`. Six-month Alpaca run at $300 across all 13 symbols (2026-02-10 to 2026-08-10) used 15-minute bars as a runtime approximation to the source's 1-minute chart and produced zero qualifying signals. No profitability claim is made.

## Verified Edge — 6-month regime check (2026-09-05)

Monthly standalone London runs (13 symbols, Alpaca 5m, theta on, execution realism on):

| Month | Trades | Win % | PF | Net |
|---|---|---|---|---|
| 2026-03 | 70 | 55.7 | 1.13 | +$342 |
| 2026-04 | 58 | 58.6 | 0.98 | -$44 |
| 2026-05 | 84 | 54.8 | 0.99 | -$31 |
| 2026-06 | 80 | 60.0 | 1.32 | +$754 |
| 2026-07 (canonical) | 66 | 59.1 | 1.44 | +$1,232 |
| 2026-08 | 26 | 61.5 | 1.10 | +$113 |
| 2026-09-01/03 | 2 | 50.0 | 0.04 | -$162 |
| **Total (~6.5 mo)** | **386** | **~57.8%** | **~1.15** | **+$2,204** |

- Win rate is stable in EVERY window (54.8–61.5%) — that part of the edge is real.
- Profit is not: expectancy concentrates in Jun+Jul (+$1,986 of +$2,204). Apr/May flat,
  Mar modest. Overall ~+$315/month on $10k (~3%/mo) with heavy month-to-month variance.
- Theta contributes ~nothing (avg +$1/spread); the directional book drives results.
- **Verdict: thin, variance-heavy positive expectancy — keep London as the primary
  paper candidate, stay paper-only.** Not strong enough to enable live at $200–300
  capital; one bad regime (Apr/May-type) erases two good months. Prior "edge did not
  hold" note referred to the Aug 7–Sep 3 slice (PF 0.87) — within normal variance of
  the full 6-month picture, but confirms no fat edge.

## Opening Drive Fade (added 2026-09-05, paper-only research)

Strategy: `src/opening_drive_fade.py` — fades one-directional opening drives (09:30→drive_end,
default 09:45): |net move| ≥ drive_min_pct, path pullback ≤ max_pullback_frac of drive range,
volume confirmation; stop beyond drive extreme + stop_buffer_atr×ATR, fixed-R target, 1 entry/symbol/day.
Registered in STRATEGY_MAP + `opening_drive_fade` config block; CLI `--strategy opening_drive_fade`.

**Verdict (2026-08-01→08-08, 1m cache, 13 symbols, $10k, execution realism on): NOT VIABLE — do not add to rotation.**
Baseline: 62 directional trades, -$1,197, 21% win, PF 0.24. Best tuned variant (stop 4×ATR,
drive ≥0.8%, pullback ≤20%, vol 1.5×, 2R): -$94, 40% win, PF 0.96 — breakeven, not edge.
3 filter iterations (strict drive quality, shorter 1.5R targets, wider stops to 6×ATR) all lost.
Dominant lever was stop width (razor-thin 1m-ATR stops → 48/62 stop-outs). Raw drive fading without
a higher-timeframe level target or news filter has no edge on this universe/window.
Level-fade variant (2026-09-05): drives must reach prior-day H/L ±level_buffer_atr×ATR (runner passes
prior_high/prior_low to the strategy; require_level/level_buffer_atr config). Buffers 1/2/3 ATR →
21/-\$256, 20/-\$312, 20/-\$336 — worse than the -$94 ungated tuned baseline. Level gate improves selectivity
but kills the better-location entries. Verdict stands: park, do not add to rotation.
**Level-gate variant (2026-09-05): also NOT VIABLE.** Added `require_level` + `level_buffer_atr`
(strategy + runner passes prior-day high/low context): drive must terminate at prior-day H/L ±buffer.
E-best params + gate: buffer 1.0 → 21 trades -$256; 2.0 → 20 trades -$311.70 (30% win, PF 0.64);
3.0 → 20 trades -$335.64 (30% win, PF 0.63). Level gating raised win rate (21→30%) but cut profit
trades harder than losers — net worse than the -$94 ungated baseline. Both variants closed: strategy
parked, kept out of rotation.
