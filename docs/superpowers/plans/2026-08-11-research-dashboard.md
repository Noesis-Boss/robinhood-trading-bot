# Research Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local browser dashboard that launches real historical backtests through the existing Python engine and renders research results.

**Architecture:** Add a small Python standard-library HTTP API that validates JSON requests and runs `backtest.py` through an argument array, with a React/Vite frontend under `web/` consuming the API. Extend the backtest engine with a JSON output mode so the API receives structured results without parsing human-formatted logs.

**Tech Stack:** Python 3.12 standard library, existing backtest Python modules, React, Vite, TypeScript, CSS.

## Global Constraints

- No live trading controls or order endpoints.
- Existing CLI defaults and historical behavior remain unchanged.
- Shell arguments must be passed as an argument array, never interpolated into a shell command.
- Dashboard results must label provider, interval, and historical research status.
- Preserve existing tests and compile behavior.

### Task 1: Add structured backtest output

**Files:**
- Modify: `backtest.py`
- Test: `tests/test_backtest_output.py`

**Interfaces:**
- Add `summarize_trades(trades, start_date, end_date, symbols, initial_capital) -> dict`.
- Add optional `json_output: bool = False` to `run_backtest`.
- CLI flag `--json` prints one JSON object and suppresses human result lines.

- [ ] Write tests for empty and non-empty summaries.
- [ ] Run `PYTHONPATH=. pytest -q tests/test_backtest_output.py` and confirm failure.
- [ ] Implement summary fields: `start_date`, `end_date`, `symbols`, `initial_capital`, `final_capital`, `total_pnl`, `trade_count`, `wins`, `losses`, `win_rate`, `profit_factor`, `avg_win`, `avg_loss`, `reason_counts`, and `trades`.
- [ ] Run the focused test and the existing test suite.
- [ ] Commit `feat: add structured backtest output`.

### Task 2: Add safe backtest API

**Files:**
- Create: `web/api.py`
- Create: `web/test_api.py`
- Create: `web/run_api.sh`

**Interfaces:**
- `POST /api/backtests` accepts JSON `{strategy, symbols, start, end, capital, provider, interval, theta, breakout_strength, max_bars, rr_ratio}` and returns `{job_id, status}`.
- `GET /api/backtests/<job_id>` returns `{job_id, status, result?, error?}`.
- `GET /api/health` returns `{status: "ok"}`.

- [ ] Write validation tests for strategy, ticker syntax, dates, capital, and max symbol count.
- [ ] Run API tests and confirm failure.
- [ ] Implement `validate_request`, `build_backtest_args`, and one-active-job protection using `subprocess.Popen` with a list of arguments.
- [ ] Parse the child process JSON output and preserve stderr in failures.
- [ ] Run API tests, compile `web/api.py`, and smoke-test health.
- [ ] Commit `feat: add research backtest api`.

### Task 3: Scaffold frontend

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/styles.css`

- [ ] Create the minimal Vite React app without changing Python dependencies.
- [ ] Add configuration controls for all API fields and the 13-symbol universe.
- [ ] Add explicit idle, running, success, empty, and error states.
- [ ] Run `bun install` and `bun run build`.
- [ ] Commit `feat: add research dashboard ui`.

### Task 4: Wire results and verify visually

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`
- Create: `web/src/components/Results.tsx`
- Create: `web/src/components/ConfigPanel.tsx`

- [ ] Implement polling from job creation to completion.
- [ ] Render metric cards, a lightweight SVG equity curve, reason breakdown, and trade table.
- [ ] Add provider/interval/research labels and actionable error messages.
- [ ] Run frontend build and Python tests.
- [ ] Start the API and Vite preview, take a browser screenshot, and verify the dashboard renders with controls and result states.
- [ ] Commit `feat: wire research dashboard results`.

### Task 5: Document usage

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] Document API/frontend startup commands and the research-only boundary.
- [ ] Record the feature in the project Feature Log.
- [ ] Run final tests and inspect git diff.
- [ ] Commit `docs: document research dashboard`.

