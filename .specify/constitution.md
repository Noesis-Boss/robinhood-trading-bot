# Project Constitution — Robinhood Trading Bot

> Non-negotiables. Every spec/plan/task must respect these. If a change breaks one, the change is wrong, not the constitution.

## Mission

A reproducible, paper-validated London-breakout day-trading system for a $10k account that earns its edge on equity day-trades, with theta spreads as a small secondary income layer (capital-gated at ~$200+).

## Non-Negotiables

### N1. Equity day-trades are the load-bearing edge
The bot's P&L must come primarily from directional day-trades, not theta. Any change that makes the system theta-dependent is rejected.

### N2. Theta realism is mandatory
Spreads are NEVER booked as guaranteed full-credit wins. Premium is clamped to a realistic $5–$15/contract band, spread width bounded to ~$20–$30 max loss, and resolution uses POP (80% win full credit / 20% take max loss) with a fixed random seed for reproducibility. Source of truth: `src/theta_farming.py`.

### N3. Live benchmark floor
No change is "good" if it regresses the published benchmark:
- 198 trades, 67.2% win rate, 1.71 profit factor, +$4,156.27 P&L (2026-07-01 → 2026-08-06, 13-symbol universe, capital $10,000, theta realistic & seeded).
Any change must hold or improve this on the same window with the same seed.

### N4. Reproducibility
Backtests are deterministic. Same code + same config + same seed = same result. No hidden randomness, no undated market data, no live-API calls in tests.

### N5. Capital-aware theta
Theta is DISABLED below $200 capital. Above $200, contracts scale as `int(risk_amount / $20 max_loss)`. No minimum-contract floor.

### N6. Risk controls before signals
Daily-loss circuit breakers (current: -2% weekly / +8% monthly in the swing module) and per-trade risk caps (current: 1% fixed) are enforced BEFORE signal generation, not after.

### N7. Test coverage on critical math
Any change to `_estimate_credit`, `simulate_expiry`, breakout-strength logic, or capital-scaling math requires a unit test that locks the current behavior.

### N8. Scope discipline
Do not silently widen scope. If a change touches the swing methodology, day-trading logic, AND theta, those are three separate tasks, not one. Per SOUL.md: name side-effects before doing them.

## Definition of Done

See `references/definition-of-done.md`. Every task must clear it.

## Approval Gate

Stages 2–4 of the pipeline require explicit approval from Don before Stage 5 (implementation) begins. Implementation logs to `memory/changes.md` and `memory/decisions.md`.
