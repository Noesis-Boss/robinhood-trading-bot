# VWAP and T3 Research Strategies Implementation Plan

> **For agentic workers:** Execute inline task-by-task with tests after each task. Both strategies remain research-only.

**Goal:** Add the approved VWAP OHLCV proxy and the previously approved T3/Range Filter strategy as selectable, disabled-by-default research strategies.

**Architecture:** Each strategy gets a focused module and tests, then is wired through the existing backtest registry, dashboard selector, and research-only safeguards. London remains the default and no broker execution path is changed.

**Tech Stack:** Python 3, pandas, pytest, existing backtest/risk interfaces, React/Vite Strategy Lab.

## Global Constraints

- Preserve existing user changes and generated artifacts.
- London remains the default strategy.
- Both strategies are selectable for historical research only.
- Neither strategy may execute paper or live orders.
- Do not add dependencies.
- Label VWAP as an OHLCV proxy; it does not reproduce Bookmap or iceberg data.

### Task 1: Implement VWAP proxy

**Files:** `src/vwap_liquidity_proxy.py`, `tests/test_vwap_liquidity_proxy.py`

- Add session VWAP, volume-confirmed reclaim signals, ATR-based stop/target, VWAP-failure/EOD/max-bar exits, and existing abnormal-data filters.
- Add tests for long reclaim, short reclaim, volume rejection, invalid data, stop/target, and one-entry-per-session behavior.
- Run focused tests and commit.

### Task 2: Wire VWAP through research interfaces

**Files:** `backtest.py`, `config.yaml`, `web/api.py`, `web/src/App.tsx`, relevant tests, `README.md`, `AGENTS.md`

- Add registry, CLI choice, dashboard option, configuration, research-only guard, and documentation.
- Run focused tests, dashboard build, and full regression suite.
- Run the canonical six-month 13-symbol research backtest and record metrics.
- Commit.

### Task 3: Implement T3/Range Filter

**Files:** `src/t3_range_filter.py`, `tests/test_t3_range_filter.py`

- Implement deterministic T3, green Range Filter, long-only signals, ATR risk, session/gap/range/halt/slippage/EOD filters, and configurable 1R/2R/3R targets.
- Add tests for indicator direction, signal qualification, safety rejection, and risk calculations.
- Run focused tests and commit.

### Task 4: Wire T3 through research interfaces

**Files:** `backtest.py`, `config.yaml`, `src/bot.py`, `web/api.py`, `web/src/App.tsx`, relevant tests, `README.md`, `AGENTS.md`

- Add registry, CLI choice, one-hour preference/fallback, dashboard option, explicit execution guard, and documentation.
- Run focused tests, dashboard build, and full regression suite.
- Run the canonical 13-symbol research backtest and compare 1R/2R/3R results.
- Commit.

## Completion Criteria

- Both strategy names appear in research backtest and Strategy Lab selectors.
- London remains default.
- Paper/live execution rejects both strategies.
- Focused and full tests pass.
- Research results are documented with limitations and no live-performance claim.
