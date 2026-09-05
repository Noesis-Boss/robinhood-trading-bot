# Theta-Only Strategy Implementation Plan

## 1. Strategy module

- Add `ThetaOnlyStrategy` with Conservative, Balanced, and Aggressive presets.
- Select scanner actionable candidates first, then fixed-universe fallback.
- Infer bullish/bearish direction from available daily/premarket movement and skip ambiguous candidates.
- Use existing `ThetaFarmer` realistic credit, max-loss, contract-sizing, and seeded expiry behavior.
- Enforce one spread per ticker per day by default.

## 2. Backtest integration

- Add `theta_only` to CLI strategy choices.
- Run the theta-only evaluator without constructing or invoking a directional strategy.
- Return options-only trades and summary fields including selection mode.

## 3. API and dashboard

- Add strategy option and aggressiveness picker to Strategy Lab.
- Forward the preset through the API and CLI.
- Display options-only labeling and theta-specific result metrics.

## 4. Verification

- Add tests for presets, fallback, ambiguity skips, max-loss bounds, and zero directional trades.
- Run the full Python test suite and frontend build.
- Run deterministic theta-only smoke tests for all three presets.
- Screenshot the live Strategy Lab state with the new controls.
