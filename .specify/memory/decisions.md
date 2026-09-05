# Decisions — Breakout-Strength Sensitivity Analysis

## D1 — 0.75 stays the default; 0.90 is a paper-trial candidate

**Context.** Sweep over 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0 on the 13-symbol,
Alpaca, 2026-07-01→2026-08-06 window. Trade count ranged 50–62.

**Result table.**

| value | trades | WR  | PF   | P&L     |
|------:|-------:|----:|-----:|--------:|
| 0.50  | 62     | 56.5% | 1.35 | $953.10 |
| 0.60  | 62     | 58.1% | 1.33 | $885.03 |
| 0.70  | 62     | 62.9% | 1.29 | $800.62 |
| 0.75  | 60     | 66.7% | 1.38 | $995.67 |  ← baseline
| 0.80  | 60     | 66.7% | 1.30 | $793.33 |
| 0.90  | 56     | 64.3% | 1.43 | $1,011.18 |
| 1.00  | 50     | 62.0% | 1.65 | $1,263.69 |

**Decision.** Keep 0.75 in `config.yaml` (AC6: no change to config).
1.00 has the best PF and P&L, but only 50 trades — thin sample, can't
distinguish real edge from noise on this window.
0.90 has the best trade-count / PF trade (1.43 PF, 56 trades) and is
+1.6% P&L over baseline, but with one fewer trade-day tail. Promote it
to a paper-only parallel run; do **not** switch the live config yet.

**Why not the obvious winner (1.00).** Single-window optimal with the
fewest trades is exactly the kind of result that evaporates out-of-sample.
Need a 3-window out-of-sample confirmation before touching `config.yaml`.

**Next action.** Add a paper-trading parallel run at 0.90 alongside the
live 0.75 for ≥20 trading days; revisit after the comparison run lands.
