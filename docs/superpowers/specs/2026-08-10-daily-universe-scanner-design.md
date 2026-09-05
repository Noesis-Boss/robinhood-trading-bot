# Daily Universe Scanner Design

Date: 2026-08-10

## Goal

Create an opt-in daily premarket scanner that discovers tradable U.S. equities through Alpaca, filters unsuitable symbols, ranks candidates for the bot's supported strategies, and writes a timestamped universe file. Existing static-symbol backtests must remain unchanged.

## Scope

The scanner will:

- Load Alpaca assets and keep active, tradable U.S. equities while excluding OTC assets.
- Apply configurable price, average dollar-volume, premarket-volume, gap, relative-volume, volatility, and spread-quality filters.
- Produce strategy-specific rankings for London breakout, Ross momentum, Sneaky Pivot, and theta spreads.
- Write `daily_universe.json` containing the scan timestamp, selected symbols, scores, metrics, and rejection reasons.
- Support a CLI command for manual execution before the market open.
- Add an explicit configuration switch for live-mode use; it defaults to disabled.
- Fall back to the configured static symbols when Alpaca asset or market-data requests fail.

The scanner will not alter historical backtest symbol selection, place orders, or claim that a ranking predicts profitability.

## Architecture

`daily_universe.py` will contain a small scanner boundary with separate responsibilities:

1. Asset discovery: retrieve and filter the Alpaca asset universe.
2. Market metrics: obtain the recent daily and premarket metrics needed by filters.
3. Candidate scoring: calculate normalized component scores and strategy-specific totals.
4. Output: persist deterministic JSON with the selected symbols and audit details.

The live bot will read the output only when `daily_universe.enabled` is true and the file is from the current trading date. Otherwise it will use the existing configured symbols.

## Default filters

- Price: `$3` to `$100`
- Average daily dollar volume: at least `$20 million`
- Premarket dollar volume: at least `$500,000`
- Gap: `2%` to `8%`
- Relative volume: at least `1.5`
- Maximum quoted spread: `0.5%` when quote data is available
- Maximum selected symbols: `10`

Missing premarket or quote data rejects a symbol rather than inventing a value. The scanner will retain rejection reasons for inspection.

## Scoring

The base score weights relative volume at 30%, premarket dollar volume at 25%, gap quality at 20%, expected movement/ATR at 15%, and liquidity/spread quality at 10%. Strategy-specific adjustments will favor:

- London: tight premarket range with sufficient range expansion potential.
- Ross: stronger gap, relative volume, and catalyst-compatible momentum.
- Sneaky Pivot: clean range and proximity to usable prior-day levels.
- Theta: liquid options eligibility, tight quotes, and no imminent earnings when data is available.

Scores are ranking aids only. They do not bypass each strategy's entry rules.

## Failure handling

- Alpaca authentication or request failure: log the error and use static symbols.
- Empty candidate set: write an empty scan result and use static symbols for live mode.
- Stale output: ignore it and use static symbols.
- Partial symbol data: reject only that symbol and continue scanning.

## Verification

- Unit-test asset filtering, metric filters, scoring, stale-date handling, and fallback behavior.
- Run the scanner against a mocked Alpaca client without network access.
- Run a live Alpaca smoke scan if credentials are available, recording counts and output path.
- Confirm the existing backtest command and static 13-symbol behavior are unchanged.

## Explicit non-goals

- No automatic order placement.
- No replacement of the static universe in historical backtests.
- No external news provider or paid market-data dependency.
- No options-chain backtest claims from equity-only data.
