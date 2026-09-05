---
title: T3 Range Filter research strategy
date: 2026-08-16
status: approved
---

# Goal

Add the video-inspired `t3_range_filter` strategy as a selectable, disabled-by-default research strategy without changing London's default behavior or enabling paper/live execution.

# Design

Reuse the existing strategy interface used by `RossMomentumStrategy`, `SneakyPivotStrategy`, and the other research strategies. Add a focused `src/t3_range_filter.py` implementation with deterministic OHLCV calculations and no new dependency.

The strategy will be long-only and use 1-hour bars when the selected data provider supplies them; the configured interval remains the fallback for unavailable data. A signal requires the U.S. session window, price above a Tillson T3 trend line, a green Donovan Wall-style range filter, and valid risk conditions. The range filter is an OHLCV proxy, not a claim of access to TradingView's original indicator.

Risk and execution rules are research-only: ATR-based stop, configurable 1R/2R/3R target, fractional-risk sizing through the existing `RiskManager`, abnormal-gap and abnormal-range rejection, halt-like/no-movement rejection, configurable slippage, and end-of-day exit. The strategy will not be accepted by live or paper bot dispatch.

# Integration

- Add `t3_range_filter` to the backtest strategy registry and CLI choices.
- Add it to the Strategy Lab request validation and picker with an explicit research-only label.
- Preserve London as the default and preserve existing strategies unchanged.
- Add configuration defaults for session, indicator lengths, ATR/target settings, safety filters, and disabled status.
- Update `README.md` and `AGENTS.md` with the strategy limits and validation requirements.

# Testing and acceptance

- Unit tests cover T3 calculation, range-filter direction, long-only signal rules, ATR stop/target construction, safety filters, and no live/paper dispatch.
- Existing full test suite remains green.
- CLI and Strategy Lab can select the strategy and return structured research results.
- A walk-forward and out-of-sample run across the full 13-symbol universe is recorded as research evidence; no profitability claim or activation follows from a positive result.

# Out of scope

TradingView alert integration, order-flow data, short signals, replacement of London, live execution, paper execution, and automatic parameter optimization.
