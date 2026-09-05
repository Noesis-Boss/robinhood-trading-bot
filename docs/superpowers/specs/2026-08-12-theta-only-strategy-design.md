# Theta-Only Farming Strategy

## Goal

Add a selectable theta-only strategy that sells defined-risk credit spreads without opening directional stock positions.

## Universe

Use the premarket scanner first. If it returns no actionable candidates, fall back to the configured fixed universe. The selected source and fallback reason must be visible in results.

## Aggressiveness picker

Expose Conservative, Balanced, and Aggressive presets:

- Conservative: 80–90% target POP, 2–5 DTE, 1% maximum risk per spread.
- Balanced: 75–85% target POP, 3–7 DTE, 2% maximum risk per spread.
- Aggressive: 65–80% target POP, 7–14 DTE, 3–5% maximum risk per spread.

Balanced is the default. The preset controls target POP, DTE range, and risk percentage together, while preserving defined-risk spreads and capital-based contract sizing.

## Strategy rules

- Evaluate each selected ticker once per trading day by default.
- Choose put spreads when the symbol has bullish relative strength and call spreads when bearish; skip ambiguous direction.
- Require liquid underlying conditions and a valid estimated credit before opening a spread.
- Cap spread width and max loss using the existing realistic theta bounds.
- Record every spread separately from directional trades; theta-only runs contain no directional trades.
- Resolve spreads using the existing seeded realistic win/loss model in backtests, never guaranteed credit.

## Integration

Add `theta_only` as a selectable backtest strategy. It disables directional strategy execution and runs the theta evaluator directly. Existing London, Ross, Sneaky Pivot, and Heikin-Ashi behavior remains unchanged.

## Results

Report theta trade count, theta P&L, wins, losses, win rate, profit factor, ending capital, and selection mode. The dashboard should make clear that the result is options-only research and not a live-order recommendation.

## Validation

- Unit tests cover all aggressiveness presets, scanner fallback, ambiguous-direction skips, max-loss bounds, and no directional trades.
- A deterministic backtest proves Conservative/Balanced/Aggressive produce different risk parameters.
- API and dashboard tests cover strategy selection and picker submission.
- Frontend build passes and the live dashboard is screenshot-verified.

## Scope

No live orders, broker authentication, automatic options approval, or changes to existing directional strategy defaults.
