# Research Dashboard Design

## Goal

Provide a browser-based research dashboard for configuring and running the existing Robinhood trading bot backtests, then reviewing the returned research metrics. The dashboard is research-only and must not expose live trading controls.

## Scope

- Add a small web application under `web/` in the trading-bot repository.
- Add a local backend adapter that starts the existing `backtest.py` process with validated arguments.
- Support all current selectable strategies: `london`, `ross`, `sneaky`, and `ha_scalp`.
- Support capital, symbols, start/end dates, provider, interval, theta toggle, and core tuning parameters.
- Stream job status and return structured JSON results to the UI.
- Display summary metrics, equity curve, strategy breakdown, and trade table.
- Keep the current CLI, config, and historical behavior unchanged.

## Architecture

The web app uses a minimal React/Vite frontend and a Python HTTP API in the same `web/` directory. The API validates request fields, invokes the existing backtest engine as a child process, captures stdout/stderr, parses the result, and returns a job result. Jobs are in-memory and limited to one active backtest at a time to protect the server and Alpaca limits.

## UI

The primary view has a left configuration panel and a right results workspace. The configuration panel uses grouped controls for run setup, universe, strategy, and risk. The results workspace starts with metric cards, followed by an equity curve, strategy comparison, and trades. Empty, running, success, and error states are explicit.

## Safety and errors

- No Robinhood order endpoints are called.
- Shell arguments are passed as an argument array, never interpolated into a shell command.
- Symbols are restricted to ticker syntax and bounded in count.
- Dates and numeric values are validated before execution.
- Missing Alpaca credentials or unavailable historical data produce a visible error with the provider and requested range.
- The UI labels results as historical research and shows the data provider and interval used.

## Success criteria

1. The dashboard loads locally.
2. A user can configure and launch a real existing backtest from the browser.
3. A completed run renders metrics and trades from the actual result.
4. Invalid input and failed backtests render actionable errors.
5. Existing Python tests and CLI smoke behavior remain passing.

