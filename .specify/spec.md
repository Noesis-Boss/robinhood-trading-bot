# Spec — Breakout-Strength Sensitivity Analysis

## What

Run a sensitivity analysis of `breakout_strength` (currently 0.75) across the published 13-symbol universe and 2026-07-01 → 2026-08-06 window. Produce a recommendation table showing win rate, profit factor, total P&L, and trade count at each value in [0.50, 0.60, 0.70, 0.75, 0.80, 0.90, 1.00].

## Why

`breakout_strength` is the only tuning knob Don called out as actively user-tunable (0.5–1.0 range). We don't know which value is the empirical optimum on the current universe. The published benchmark is one point (0.75); the recommendation should be the data, not a guess.

## Out of scope

- Changing `rr_ratio`, `max_holding_bars`, or `entry_window_hours` (other tuning knobs). They stay at their current values.
- Touching theta realism (N2) or the swing module.
- Live trading. Paper/sim only.

## Acceptance criteria

1. A new script `backtest_sensitivity.py` at the project root that accepts `--config config.yaml` and `--values 0.50,0.60,0.70,0.75,0.80,0.90,1.00` (defaults to that list).
2. Output: a markdown table with columns `breakout_strength | trades | win_rate | profit_factor | pnl | theta_pnl | equity_pnl`. One row per value.
3. The run at 0.75 must reproduce the published benchmark (±$0.01 P&L, same trade count). If it doesn't, that's a reproducibility bug (N4 violation) and blocks this spec.
4. Recommendation: the value with the highest profit factor among values that hold WR ≥ 60% AND trade count ≥ 80. If no value meets both, recommend the highest-PF value and explain the tradeoff.
5. The script writes its result to `.specify/memory/sensitivity-result.md` for the next agent.
6. No change to `config.yaml`. No change to `backtest.py`. New code only.
7. Tests: a small unit test that confirms the sensitivity runner reuses the same seeded RNG path as `backtest.py` (locks N4).

## Risks

- The 13-symbol universe and the published window are small. One outlier day can swing the result. Mitigation: report the result as "this window, this seed" and don't claim broader generalization.
- The recommendation may not improve on 0.75. That's fine — the output is a data table, not a forced change.

## Definition of Done

See `references/definition-of-done.md`.
