# Shared Research Execution Realism Design

Date: 2026-08-16

## Goal

Make comparisons among all eight Strategy Lab strategies more realistic without changing their signal definitions or enabling research strategies for paper/live execution.

## Scope

The backtest engine will apply one shared execution-cost model to directional strategies. It will expose gross P&L, execution costs, and net P&L. Existing strategy-specific signal logic remains intact except for explicit research parameterization already required by the source strategy.

Included strategies: `london`, `ross`, `sneaky`, `ha_scalp`, `auction_flow_proxy`, `vwap_liquidity_proxy`, `t3_range_filter`, and `theta_only`.

## Execution model

- Entry and exit prices receive configurable adverse slippage in basis points.
- A configurable spread/liquidity cost is applied to directional fills.
- If a bar reaches both stop and target, the stop is considered first.
- Zero-volume and invalid OHLC bars cannot create fills.
- Gross P&L remains available for comparison with older reports; net P&L is the default research result.
- Defaults are conservative and configurable in `config.yaml`; no live execution path consumes these research settings.

## Strategy-specific rules

- `ha_scalp`: retain 100 EMA, two-candle clean pullback, and doji confirmation; make body-to-range, wick, and relative-volume thresholds explicit and testable. Entries use real bar prices rather than synthetic Heikin-Ashi prices while indicators remain Heikin-Ashi-derived.
- `vwap_liquidity_proxy`: retain reclaim confirmation, relative volume, ATR risk, and existing safety filters.
- `t3_range_filter`: retain T3, green Range Filter, ATR risk, and configurable 1R/2R/3R targets.
- Other strategies receive the shared execution model without speculative signal changes.

## Reporting

Backtest summaries will include trade count, win rate, profit factor, gross P&L, execution cost, net P&L, drawdown, exit reasons, and zero-trade diagnostics where available. The Strategy Lab result view will label gross and net values clearly.

## Testing and acceptance

- Unit tests cover adverse entry/exit slippage, stop-first resolution, zero-volume rejection, and HA threshold behavior.
- Existing tests remain green.
- Every registered strategy can execute through the common model.
- Research strategies remain blocked from paper/live execution.
- A full 13-symbol research run compares gross versus net results; no profitability claim is made from the run.

## Non-goals

- No new trading strategy.
- No broker or live-order changes.
- No claim that OHLCV reproduces order-book, footprint, or true bid/ask data.
- No automatic parameter optimization.
