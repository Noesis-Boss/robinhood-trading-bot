# Ross Momentum Pullback Strategy

Date: 2026-08-09

## Goal

Add Ross Cameron-style momentum pullback trading as a selectable strategy while preserving London Breakout as the default.

## Transcript-derived rules

- Scan for stocks with a meaningful gap, strong percentage gain, high total volume, and high relative volume.
- Prefer a clear catalyst and low float when float data is available.
- Identify an initial momentum surge, then wait for the first orderly pullback.
- Enter when price reclaims the 9 EMA after the pullback while holding above VWAP for longs; invert these conditions for shorts.
- Require stronger volume on the impulse/reclaim than on the pullback.
- Place the hard stop at the pullback low for longs or pullback high for shorts.
- Use a configurable reward-to-risk target, move the stop to breakeven after 1R, and exit by 10:00 ET.
- Allow at most one trade per symbol per day.

## Architecture

Create `src/ross_momentum.py` with a `RossMomentumStrategy` interface matching the existing strategy's `generate_signal`, `check_exit`, and trade lifecycle methods. It will calculate VWAP and EMA from the supplied bars and use only data available through the current bar.

Add `--strategy {london,ross}` to `backtest.py`. `london` remains the default. The backtest will instantiate the selected strategy and keep the existing shared risk manager, journal, and theta compounding path.

## Configuration

Add a `ross_momentum` section to `config.yaml` with thresholds for minimum gap, minimum price, relative volume, total volume, maximum float when known, pullback lookback, EMA length, entry cutoff, reward-to-risk, and maximum holding bars. Missing float/catalyst metadata will not automatically reject a symbol; the strategy will require price/volume evidence.

## Testing and verification

- Unit tests for VWAP/EMA calculations, first-pullback detection, long/short signals, stop placement, cutoff exit, and one-trade-per-day behavior.
- Import and syntax checks.
- Alpaca backtest over the canonical 2026-07-01 through 2026-08-06 period using the full 13-symbol universe.
- Separate reporting for Ross directional trades and theta trades, plus a comparison against the unchanged London strategy.

## Scope exclusions

No live-order activation, scanner service, news API, or float-data vendor will be added in this pass. Those can be evaluated after the historical strategy produces enough trades for meaningful comparison.
