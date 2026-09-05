 # Auction Flow OHLCV Proxy

 ## Purpose

 Add a selectable research strategy inspired by Chris Kmer's auction-market process while clearly separating it from true footprint/order-flow trading.

 ## Scope

 The strategy uses only existing OHLCV bars. It combines higher-timeframe SMA trend, Fibonacci premium/discount location, VWAP, relative volume, candle-body/wick failure, swing-point risk levels, and trailing exits. It does not use GEX, bid/ask footprint data, delta, or live orders.

 ## Behavior

 `auction_flow_proxy` is an opt-in strategy name. London remains the default. A valid signal requires trend alignment, price in a premium/discount zone, and a failed opposing move with volume confirmation. Stops use the local swing extreme; targets use the next swing or configured reward/risk fallback. Session-quality filtering removes bars outside the configured trading window and low-activity conditions.

 ## Transparency

 Results and dashboard labels must identify this as an `OHLCV proxy`, not order-flow validation. No performance claim from the source video is transferred to this implementation.

 ## Verification

 Add deterministic unit tests for trend/location/failed-move signals, long and short exits, and no-signal cases. Preserve all existing strategy defaults and pass the existing test suite.
