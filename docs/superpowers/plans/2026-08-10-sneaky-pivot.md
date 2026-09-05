# Sneaky Pivot Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with tests after each task.

**Goal:** Add Sneaky Pivot as a selectable research strategy while preserving existing defaults.

**Architecture:** Create an isolated strategy class matching the backtest engine's strategy interface. Wire strategy selection through `backtest.py`, reuse existing risk/journal/theta accounting, and validate with deterministic synthetic-bar tests plus a smoke run.

**Tech Stack:** Python 3, pandas, pytest, existing Alpaca/yfinance data layer.

## Global Constraints

- `london` remains the default strategy.
- `ross` behavior remains unchanged.
- Sneaky Pivot is research-only; do not change live bot defaults.
- Use the existing shared `RiskManager`, journal, and theta-compounding path.
- Significant swing detection uses configurable local-extrema lookback and proximity threshold.

### Task 1: Add deterministic Sneaky Pivot tests

**Files:**
- Create: `tests/test_sneaky_pivot.py`

- [ ] Test local swing levels from synthetic 15-minute bars.
- [ ] Test a valid lower-level long confirmation.
- [ ] Test a valid upper-level short confirmation.
- [ ] Test rejection when price is outside the proximity threshold.
- [ ] Test invalid stop/target geometry is rejected.

Run: `pytest tests/test_sneaky_pivot.py -q`
Expected: collection/import failure before implementation.

### Task 2: Implement the strategy module

**Files:**
- Create: `src/sneaky_pivot.py`

- [ ] Implement `SneakyPivotStrategy(config, risk, journal)`.
- [ ] Implement prior-day high/low and local swing detection.
- [ ] Implement three-candle confirmation and support/resistance proximity checks.
- [ ] Return the existing signal shape: `symbol`, `side`, `entry_price`, `stop_loss`, `take_profit`, and `reason`.
- [ ] Implement exit handling compatible with the backtest engine, including stop, target, breakeven, and session close.

Run: `pytest tests/test_sneaky_pivot.py -q`
Expected: all strategy tests pass.

### Task 3: Wire selectable backtesting

**Files:**
- Modify: `backtest.py`
- Modify: `config.yaml`

- [ ] Import `SneakyPivotStrategy`.
- [ ] Add `sneaky` to strategy choices.
- [ ] Instantiate it without changing London or Ross branches.
- [ ] Add documented Sneaky Pivot configuration defaults.
- [ ] Keep theta accounting on the shared path.

Run: `python3 backtest.py --help`
Expected: strategy choices include `london`, `ross`, and `sneaky`.

### Task 4: Verify and document

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] Run the complete unit test suite.
- [ ] Run a Sneaky Pivot smoke backtest with Alpaca and the canonical symbol universe.
- [ ] Record actual trade count, P&L, win rate, and profit factor.
- [ ] If the data provider produces no qualifying signals, report that fact without inventing performance.

Run: `pytest -q` and `python3 backtest.py --strategy sneaky --provider alpaca --symbols SPY QQQ AAPL TSLA NVDA SOFI F AAL MARA RIVN NIO RBLX DKNG --start 2026-07-01 --end 2026-08-06`
Expected: tests pass; backtest completes or reports a concrete provider limitation.

