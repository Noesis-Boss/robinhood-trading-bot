# T3 Range Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a disabled-by-default, long-only `t3_range_filter` research strategy using the existing strategy interface, CLI, and Strategy Lab without enabling paper or live execution.

**Architecture:** Implement deterministic T3, ATR, and range-filter calculations in a focused strategy module. Reuse existing signal/trade/risk objects and backtest dispatch, then add explicit research-only routing guards in the API and bot execution paths.

**Tech Stack:** Python 3, pandas, pytest, existing RiskManager/backtest engine, React/Vite Strategy Lab.

## Global Constraints

- London remains the default strategy.
- `t3_range_filter` is long-only and research-only.
- No new Python or frontend dependencies.
- Use 1-hour bars when available; retain configured interval as fallback.
- Test 1R, 2R, and 3R targets; do not assume 3.8R.
- Use ATR stops with existing fractional-risk limits.
- Include U.S. session, gap, abnormal-range, halt-like, slippage, and end-of-day rules.
- Do not add order placement or paper/live activation.

---

### Task 1: Add the strategy calculations and signal contract

**Files:**
- Create: `src/t3_range_filter.py`
- Create: `tests/test_t3_range_filter.py`

**Interfaces:**
- Consumes: strategy bars as used by `src/auction_flow_proxy.py` and existing `RiskManager`.
- Produces: `T3RangeFilterStrategy(config, risk, journal)`, `generate_signal(symbol, bars)`, and exit metadata compatible with `backtest.py`.

- [ ] Write tests for T3 direction, green range-filter direction, long-only signals, ATR stop/target, and each safety rejection.
- [ ] Run `pytest tests/test_t3_range_filter.py -q` and confirm the new tests fail before implementation.
- [ ] Implement the smallest compatible strategy module with configurable lengths, session times, ATR multiplier, target R, gap/range/halt/slippage thresholds, and EOD exit.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit: `git add src/t3_range_filter.py tests/test_t3_range_filter.py && git commit -m "Add T3 range filter research strategy"`.

### Task 2: Wire configuration and backtest CLI

**Files:**
- Modify: `config.yaml`
- Modify: `backtest.py`
- Modify: `src/bot.py`
- Modify: `tests/test_backtest_output.py`

**Interfaces:**
- Consumes: `T3RangeFilterStrategy` from Task 1.
- Produces: `--strategy t3_range_filter`, JSON summaries, 1-hour interval selection, and an execution guard that rejects this strategy outside research backtests.

- [ ] Add disabled-by-default `t3_range_filter` configuration and the strategy registry/CLI choice.
- [ ] Add a regression test proving CLI dispatch and research JSON output.
- [ ] Add a regression test proving bot/paper/live execution rejects `t3_range_filter`.
- [ ] Run focused backtest and guard tests.
- [ ] Commit: `git add config.yaml backtest.py src/bot.py tests/test_backtest_output.py && git commit -m "Wire T3 range filter into research backtests"`.

### Task 3: Wire Strategy Lab selection

**Files:**
- Modify: `web/api.py`
- Modify: `web/src/App.tsx`
- Modify: `web/test_api.py`

**Interfaces:**
- Consumes: backtest CLI strategy name from Task 2.
- Produces: selectable Strategy Lab option, research-only labeling, and request forwarding.

- [ ] Add `t3_range_filter` to API validation and CLI argument forwarding.
- [ ] Add the strategy option and research-only label to the dashboard without changing existing defaults.
- [ ] Add API validation tests for acceptance and invalid execution modes.
- [ ] Run `pytest web/test_api.py -q`.
- [ ] Build the dashboard with `cd web && bun run build`.
- [ ] Commit: `git add web/api.py web/src/App.tsx web/test_api.py web/dist && git commit -m "Add T3 range filter to Strategy Lab"`.

### Task 4: Document and validate the research strategy

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: completed implementation and test results from Tasks 1–3.
- Produces: operator-facing usage, limitations, and validation record.

- [ ] Document CLI usage, indicator proxy limitations, safety rules, and disabled execution status.
- [ ] Run the full test suite with `pytest -q`.
- [ ] Run a full 13-symbol research backtest using 1-hour data where available.
- [ ] Run walk-forward and out-of-sample comparisons for 1R, 2R, and 3R targets.
- [ ] Record results without presenting them as live-performance evidence.
- [ ] Commit: `git add README.md AGENTS.md && git commit -m "Document T3 range filter research validation"`.

## Self-review

The plan covers the spec's architecture, integration, safety, testing, documentation, and validation requirements. It contains no unresolved placeholders and keeps frontend, engine, and documentation work in separate testable tasks.
