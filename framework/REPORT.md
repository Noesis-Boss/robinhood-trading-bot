# 100-Variant Strategy Evaluation

## Backtest

- Window: 2026-07-01 through 2026-08-06
- Universe: SPY, QQQ, AAPL, TSLA, NVDA
- Variants evaluated: 100
- Variants producing trades: 75
- Execution failures: 0

The three highest-ranked results were `london_021`, `london_025`, and `london_029`. Each produced only nine backtest trades. Their high profit factors are not statistically reliable enough for live-capital deployment.

| Variant | Max holding bars | Trades | Win rate | Profit factor | P&L |
|---|---:|---:|---:|---:|---:|
| london_021 | 30 | 9 | 44.44% | 7.94 | $736.41 |
| london_025 | 45 | 9 | 44.44% | 7.94 | $736.41 |
| london_029 | 60 | 9 | 44.44% | 7.94 | $736.41 |

## Forward incubation

- Paper capital: $100 per variant
- Evaluation window: latest 10 calendar days through 2026-08-25
- Result: zero trades for all three variants; ending paper equity remained $100 each

Alpaca IEX was active, but the inspected August 24 session contained only two premarket bars, at 08:25 and 08:30 ET. That is insufficient to construct the required 08:00–09:25 premarket box. The zero-trade result is therefore a data-coverage limitation, not evidence for or against the strategies.

## Status

The boilerplate and 100-variant batch are operational. The top three are configured for paper-only incubation. No live trading is authorized. A valid forward test requires a feed with continuous premarket coverage or a strategy window redesigned for IEX coverage and then re-backtested from scratch.
