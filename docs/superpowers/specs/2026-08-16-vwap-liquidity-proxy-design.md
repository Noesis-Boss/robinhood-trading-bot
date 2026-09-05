# VWAP Liquidity Proxy Research Strategy

## Scope

Add a selectable, disabled-by-default research strategy named `vwap_liquidity_proxy`. It adapts the video’s VWAP/liquidity idea to the bot’s available equity OHLCV data. It does not claim to reproduce Bookmap heatmaps, iceberg detection, bid/ask flow, ES futures behavior, or VIX-based discretionary sizing.

London remains the default strategy. The new strategy must not be available to live or paper execution paths.

## Signal design

- Operate on the configured intraday bars, defaulting to 5-minute data.
- Calculate session VWAP from typical price times volume divided by cumulative volume.
- Long setup: a prior completed bar closes below VWAP, the current completed bar closes above VWAP, and current volume is at least the configured relative-volume threshold.
- Short setup: the inverse VWAP reclaim with the same volume requirement.
- Require a minimum number of prior bars and reject missing, zero-volume, or invalid OHLCV data.
- Permit only one entry per symbol per session.

## Risk and exits

- Initial stop uses the reclaim candle extreme with an ATR floor/cap to prevent zero or excessive risk.
- Target uses configurable reward:risk, default 2R.
- Exit at stop, target, VWAP failure, end of session, or maximum holding bars.
- Reuse the existing `RiskManager` and trade result structures.
- Do not add broker behavior or change existing risk defaults.

## Safety filters

- Reject abnormal gaps and abnormal bar ranges using existing project conventions.
- Reject signals outside the regular-session window.
- Label all output as an OHLCV proxy and research-only.

## Integration

- Add a focused strategy module and unit tests.
- Add the strategy to the backtest CLI dispatch while preserving London as default.
- Add Strategy Lab selection and research-only labeling if the existing dashboard dispatch supports it without exposing execution controls.
- Update README and AGENTS.md with the rules, limitations, and validation result.

## Validation

- Run focused tests and the full regression suite.
- Run a six-month research backtest across the canonical 13-symbol universe.
- Report trade count, win rate, profit factor, P&L, drawdown, and exit reasons.
- Do not enable paper/live execution regardless of backtest outcome.
