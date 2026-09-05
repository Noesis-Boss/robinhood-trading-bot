 # Per-Ticker Daily Entry Limit

 ## Goal

 Add a Strategy Lab control that limits how many directional entries may be opened for each ticker during one trading day.

 ## Behavior

 - Add `max_entries_per_day` to the backtest request and Strategy Lab form.
 - Offer `1`, `2`, `3`, `5`, and `Unlimited` in a select picker.
 - Default to `1`, preserving the Ross strategy's current behavior.
 - Reset the count at each new trading day.
 - Count both active and completed entries for each `(symbol, day)` pair.
 - Apply the limit consistently to London, Ross, Sneaky Pivot, and Heikin-Ashi strategies.
 - `Unlimited` removes only this per-ticker daily entry cap; existing active-position and session-window rules remain.

 ## Architecture

 The web API passes the selected value into the backtest configuration. Each strategy owns a per-day entry counter and exposes one shared entry-eligibility check. The backtest loop continues to check exits before entries, then asks the strategy whether the ticker has reached its daily limit.

 The Ross strategy's existing hard-coded `_traded_days` gate becomes the default value of the shared limit rather than a separate rule. This avoids duplicate counting rules and keeps the default result stable.

 ## UI

 Add a `Max entries / ticker / day` select under Parameters, beside the existing Breakout Strength and Max Bars controls. Include a short hover/focus explanation: higher values allow re-entry after an exit; Unlimited permits every qualifying signal while other safeguards remain active.

 ## Validation

 - Unit tests verify limits of 1, 2, 5, and Unlimited.
 - Tests verify the count resets on a new date and blocks entries while an active trade exists.
 - API tests verify the field is accepted and forwarded.
 - Production frontend build passes.
 - Strategy Lab screenshot shows the picker and its selected default.

 ## Scope

 No live-order behavior, scanner changes, strategy signal formulas, risk sizing, or default strategy selection changes.
