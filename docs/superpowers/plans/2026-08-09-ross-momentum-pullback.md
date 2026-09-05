# Ross Momentum Pullback Strategy Implementation Plan

> **For agentic workers:** Implement task-by-task with tests and commits.

**Goal:** Add a selectable Ross Cameron-style momentum pullback strategy while preserving London Breakout as the default.

**Architecture:** Add an isolated `RossMomentumStrategy` implementing the existing strategy lifecycle. Update the backtest factory/CLI and config only; reuse the existing risk, journal, theta, and Alpaca data layers.

**Tech Stack:** Python 3, pandas, PyYAML, pytest, Alpaca IEX.

## Global Constraints

- Default `--strategy` remains `london`.
- Use only bars available through the current bar; no look-ahead.
- Preserve shared theta compounding through `RiskManager`.
- No live-order activation, news API, scanner service, or float vendor.

### Task 1: Add deterministic indicator and setup tests

**Files:**
- Create: `tests/test_ross_momentum.py`

- [ ] Add tests for cumulative VWAP, EMA reclaim, long/short first-pullback signals, pullback stop placement, 10:00 ET cutoff, and one-trade-per-symbol behavior.
- [ ] Run `pytest tests/test_ross_momentum.py -q`; expected initial failure because the strategy does not exist.
- [ ] Commit the failing tests: `git add tests/test_ross_momentum.py && git commit -m "test: specify Ross momentum setups"`.

### Task 2: Implement the isolated strategy

**Files:**
- Create: `src/ross_momentum.py`

**Interface:**
- `RossMomentumStrategy(config, risk, journal)`
- `generate_signal(symbol, bars, context=None) -> dict | None`
- `on_trade_entered(symbol, signal) -> None`
- `check_exit(symbol, bars, broker) -> dict | None`

- [ ] Calculate cumulative session VWAP and EMA using data through `bars.iloc[-1]`.
- [ ] Detect an impulse, an orderly pullback within the configured lookback, and a reclaim bar with stronger volume than the pullback.
- [ ] Require configurable gap/price/relative-volume evidence when those fields are available; do not reject missing optional float/catalyst metadata.
- [ ] Create long and short signals with stop at pullback extreme and target at configured R multiple.
- [ ] Implement breakeven after 1R, maximum holding bars, and forced exit at the 10:00 ET cutoff.
- [ ] Run `pytest tests/test_ross_momentum.py -q`; expected PASS.
- [ ] Commit: `git add src/ross_momentum.py tests/test_ross_momentum.py && git commit -m "feat: add Ross momentum pullback strategy"`.

### Task 3: Wire selection and configuration

**Files:**
- Modify: `backtest.py`
- Modify: `config.yaml`

- [ ] Add `--strategy` choices `london` and `ross`, defaulting to `london`.
- [ ] Instantiate `LondonBreakoutStrategy` or `RossMomentumStrategy` without changing the shared risk/journal/theta flow.
- [ ] Add the Ross thresholds and session cutoff under `ross_momentum`.
- [ ] Run `python3 -m py_compile backtest.py src/ross_momentum.py`.
- [ ] Run the existing test suite; expected PASS.
- [ ] Commit: `git add backtest.py config.yaml && git commit -m "feat: select trading strategy in backtest"`.

### Task 4: Run comparison and document results

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] Run Ross on Alpaca for the canonical dates and full universe:
  `python3 backtest.py --provider alpaca --strategy ross --symbols SPY QQQ AAPL TSLA NVDA SOFI F AAL MARA RIVN NIO RBLX DKNG --start 2026-07-01 --end 2026-08-06`.
- [ ] Run London with the same command except `--strategy london`.
- [ ] Record trade count, P&L, win rate, profit factor, directional/theta split, and any data gaps.
- [ ] Document that results are historical research, not a live-performance claim.
- [ ] Commit documentation and result updates.

## Self-review

The plan covers transcript rules, isolated architecture, selectable CLI behavior, configuration, tests, Alpaca verification, comparison, theta reuse, and documentation. It introduces no live trading or external data dependency.
