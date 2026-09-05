# Plan — Breakout-Strength Sensitivity Analysis

## Tech stack

- **Language**: Python 3.12 (matches existing `backtest.py`)
- **Data**: `data/` yfinance cache (matches `backtest.py`)
- **Config**: `config.yaml` (read-only; we do not modify it)
- **Output**: plain text + markdown, no new deps

## How

### Step 1 — Reuse, don't re-implement

Import `backtest.py`'s run function. If it's not currently importable as a function (i.e. it's a script body), refactor it minimally: extract `run_backtest(config, breakout_strength_override) -> BacktestResult` into a new `src/backtest_runner.py`. Keep `backtest.py` as a thin CLI wrapper that calls the new function. No behavior change.

### Step 2 — Build the sensitivity runner

New file: `backtest_sensitivity.py` at the project root. It:

1. Reads `config.yaml`.
2. For each `breakout_strength` in the value list:
   - Calls `run_backtest(config, breakout_strength_override=value)`.
   - Captures: total trades, win rate, profit factor, total P&L, theta P&L, equity P&L.
3. Prints the table to stdout.
4. Writes the same table to `.specify/memory/sensitivity-result.md`.
5. Computes the recommendation per AC #4 and prints it.

### Step 3 — Reproducibility test

New test: `tests/test_sensitivity_reproducibility.py`. It runs the runner twice on the same config + same values and asserts the outputs are byte-identical. Locks N4.

### Step 4 — Run + record

Don runs `backtest_sensitivity.py` (or I do, with the result going to a file Don can read). Update `memory/decisions.md` with: what the recommended value is, whether it differs from the current 0.75, and the follow-up action.

## Spec coverage matrix

| Spec AC | Covered by |
|---|---|
| AC1 — `backtest_sensitivity.py` with `--config` and `--values` flags | Step 2 |
| AC2 — Markdown table output | Step 2 |
| AC3 — 0.75 reproduces published benchmark | Step 2 (asserted) + Step 3 (locked) |
| AC4 — Recommendation rule | Step 2 (computed) |
| AC5 — Writes to `.specify/memory/sensitivity-result.md` | Step 2 |
| AC6 — No change to `config.yaml` or `backtest.py` (except thin wrapper) | Step 1 (minimal refactor only) |
| AC7 — Reproducibility test | Step 3 |

## Constitution check

- N1 (equity load-bearing): output table separates theta vs equity. ✅
- N2 (theta realism): refactor doesn't touch `_estimate_credit` or `simulate_expiry`. ✅
- N3 (live benchmark floor): AC3 enforces 0.75 reproduces. ✅
- N4 (reproducibility): Step 3 locks it. ✅
- N8 (scope discipline): only one tuning knob touched. ✅

## Files touched

- `src/backtest_runner.py` (NEW) — extracted `run_backtest` function
- `backtest.py` (MODIFIED) — becomes a 5-line wrapper
- `backtest_sensitivity.py` (NEW) — the runner
- `tests/test_sensitivity_reproducibility.py` (NEW) — locks N4
- `.specify/memory/sensitivity-result.md` (NEW, generated) — the result
- `.specify/memory/decisions.md` (MODIFIED) — appends the decision

## Files NOT touched

- `config.yaml`
- `config_swing.yaml`
- `src/theta_farming.py`
- `src/broker.py`
- `src/supply_demand_swing.py`
- `framework/`
- `docs/`
