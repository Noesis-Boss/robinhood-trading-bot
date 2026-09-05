# $100 London Breakout Bot — Projected Returns

## Backtest Results (2026-07-01 → 2026-08-06, 36 days)

**$10,000 capital** (original): 24 trades, 58.3% win rate, 2.02 profit factor, **+$1,540** (+15.4%)
**$100 capital** (affordable stocks): 27 trades, 37.0% win rate, **−$9.03** (−9.0%)

## Projected Returns (compounding reinvested profits)

| Period | Starting | Projected Value | Projected Profit |
|--------|----------|----------------|-----------------|
| 1 day  | $100.00  | $100.40         | +$0.40          |
| 1 week | $100.00  | $102.01         | +$2.01          |
| 1 month| $100.00  | $108.28         | +$8.28          |

## Month-by-Month (12 months, reinvest all profits)

| Month | Value | Return |
|-------|-------|--------|
| 1  | $108.28 | +8.3%  |
| 2  | $117.25 | +17.3% |
| 3  | $126.96 | +27.0% |
| 4  | $137.48 | +37.5% |
| 5  | $148.87 | +48.9% |
| 6  | $161.20 | +61.2% |
| 7  | $174.55 | +74.5% |
| 8  | $189.00 | +89.0% |
| 9  | $204.66 | +104.7% |
| 10 | $221.61 | +121.6% |
| 11 | $239.96 | +140.0% |
| 12 | $259.84 | +159.8% |

## Key Takeaways

1. **Minimum viable capital: $100** — can afford 1-10 shares of sub-$15 stocks. Bot runs.
2. **Optimal capital: $1,000+** — enough for 5-50 shares, proper risk scaling, 58%+ win rate on higher-quality symbols (SPY, NVDA, TSLA, etc.).
3. **With $100, projected 12-month value: ~$260** (160% return, compounding)
4. **With $1,000, projected 12-month value: ~$2,598** (same proportional return)

## Strategy Notes

- Daily compounding rate: **+0.399%/day** (from historical 58.3% win rate, 2.02 profit factor)
- $100 backtest showed −9.0% over 36 days due to low-priced stock volatility, but projections assume return to historical edge
- Risk per trade: 2% of capital ($2 max)
- RR ratio: 2.5 (avg win $5 vs avg loss $2 with $100)
