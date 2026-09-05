# Changes

> Edits to constitution or spec after approval. Don't rewrite silently — log the change here.

## YYYY-MM-DD — [Brief title]

- **Artifact:** constitution / spec / plan / tasks
- **What changed:** [One sentence.]
- **Why:** [Reason the original was wrong or incomplete.]
- **Impact:** [Tasks invalidated, scope shifted, etc.]

## 2026-08-28 — Breakout-strength sweep

- Refactored `backtest.py` (370 lines) → `src/backtest_runner.py` +
  `backtest.py` shim. Refactor adds `breakout_strength_override` parameter
  to `run_backtest(...)` and the CLI. The original `--breakout-strength`
  flag still works. No behavior change at default.
- New `backtest_sensitivity.py` CLI: runs a multi-value sweep and emits a
  markdown table. Accepts `--values`, `--symbols`, `--start`, `--end`,
  `--provider`. Default sweep: 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0.
- New `tests/test_sensitivity_reproducibility.py`: 2 passed.
- `.specify/` scaffolded and walked through the full 5-stage pipeline as
  a validation of `Skills/spec-driven-development`. All five tasks closed.
