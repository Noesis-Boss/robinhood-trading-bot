# Tasks — Breakout-Strength Sensitivity Analysis

Ordered. Each task atomic, acceptance-checked. Stage 5 (implement) does not start until Don approves this list.

- [x] **T1. Refactor `backtest.py` into `src/backtest_runner.py`**
  - Extract `run_backtest(config_path: str, breakout_strength_override: float | None = None) -> dict` from the current `backtest.py` body.
  - The function returns: `{"trades", "wins", "win_rate", "profit_factor", "pnl", "theta_pnl", "equity_pnl"}`.
  - Replace `backtest.py` body with: `from src.backtest_runner import run_backtest; if __name__ == "__main__": print(run_backtest("config.yaml"))` (plus the existing argparse if any).
  - Acceptance: `python3 backtest.py` produces the SAME published P&L ($4,156.27 ±$0.01) on the same window. Diff stdout before/after.
  - No change to any other file in `src/`.

- [x] **T2. Write `backtest_sensitivity.py`**
  - Accepts `--config` (default `config.yaml`) and `--values` (CSV, default `0.50,0.60,0.70,0.75,0.80,0.90,1.00`).
  - For each value, calls `run_backtest(config, breakout_strength_override=value)`.
  - Prints a markdown table to stdout.
  - Writes the same table to `.specify/memory/sensitivity-result.md`.
  - Computes recommendation per AC4 and prints it.
  - Acceptance: `python3 backtest_sensitivity.py` exits 0, produces a 7-row table, and writes the result file.

- [x] **T3. Write `tests/test_sensitivity_reproducibility.py`**
  - Runs the sensitivity runner twice on the same input.
  - Asserts the two outputs are byte-identical.
  - Acceptance: `python3 -m pytest tests/test_sensitivity_reproducibility.py` passes.

- [x] **T4. Run T2 + append to `memory/decisions.md`**
  - Don runs (or I run) `backtest_sensitivity.py` against the published window.
  - Append to `.specify/memory/decisions.md`: the recommended value, whether it differs from 0.75, and the follow-up action (none / change default / open new spec).
  - Acceptance: decisions.md has a new dated entry.

- [x] **T5. Verify the 0.75 row in the result file matches the published benchmark**
  - Read `.specify/memory/sensitivity-result.md`.
  - Assert the 0.75 row's `pnl` is within $0.01 of $4,156.27 and trade count is 198.
  - Acceptance: printed PASS line, or FAIL with the delta.

