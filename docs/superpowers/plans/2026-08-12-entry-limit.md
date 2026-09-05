# Per-Ticker Daily Entry Limit Implementation Plan

## 1. Shared strategy limit

- Add `max_entries_per_day` parsing to each strategy with `1` as the default.
- Track entry counts by `(symbol, date)`.
- Reject entries at the limit while preserving active-trade blocking and session rules.
- Increment the count only when `on_trade_entered` succeeds.

## 2. Backtest and API wiring

- Add a CLI argument for the limit.
- Pass the value through `web/api.py` to `backtest.py`.
- Preserve `Unlimited` as a sentinel value without changing other risk rules.

## 3. Strategy Lab UI

- Add a Parameters select with `1`, `2`, `3`, `5`, and `Unlimited`.
- Add the approved hover/focus explanation.
- Keep the default selected value at `1`.

## 4. Verification

- Add unit coverage for limit one, higher limits, unlimited, date reset, and active trades.
- Run existing tests plus the new tests.
- Run the frontend production build.
- Screenshot the live Strategy Lab Parameters section with the picker visible.
