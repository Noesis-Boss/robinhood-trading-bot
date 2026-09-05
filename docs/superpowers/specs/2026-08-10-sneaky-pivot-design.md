# Sneaky Pivot Strategy Design

## Goal

Add the Sneaky Pivot reversal strategy as a selectable backtest module without changing the existing London or Ross defaults.

## Strategy Contract

- Resample or consume 15-minute bars.
- Establish the prior trading day high and low.
- Detect the nearest significant swing high above and swing low below the current range.
- Consider short entries only near upper resistance levels and long entries only near lower support levels.
- Require three consecutive candles: setup/opening candle, confirmation candle, and entry candle crossing the prior candle's level.
- Place the stop beyond the tested buyer/seller level.
- Set the target at the opposite side of the active range.
- Allow one active trade per symbol/session and force-close remaining positions at the session cutoff.

## Integration

- Add `src/sneaky_pivot.py` with the same strategy-facing interface used by the backtest engine.
- Add `sneaky` to `--strategy` choices.
- Keep `london` as the default and preserve `ross` behavior.
- Use the existing risk manager, journal, shared cash, and theta-compounding path.
- Make the module research-only until a historical run establishes evidence; do not alter live bot defaults.

## Testing

- Unit-test support/resistance detection.
- Unit-test valid long and short three-candle confirmations.
- Unit-test rejection away from levels and invalid stop/target geometry.
- Run the full existing test suite and a Sneaky Pivot backtest smoke test.
- Report trade count, win rate, profit factor, and P&L without presenting them as forecasts.

## Known Limitation

The source description does not provide a mathematically precise definition of “significant swing.” The first implementation will use a configurable local-extrema lookback and proximity threshold, documented in config, so the rule can be tuned and audited rather than hidden in code.
