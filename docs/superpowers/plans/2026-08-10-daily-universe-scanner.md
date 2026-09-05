# Daily Universe Scanner Implementation Plan

1. Add `src/daily_universe.py` with asset filtering, metric filtering, weighted scoring, deterministic output, and static-symbol fallback.
2. Add scanner configuration and a manual CLI entry point without changing historical backtest defaults.
3. Wire live-mode symbol selection to today’s valid scan only; otherwise retain configured symbols.
4. Add focused unit tests for filtering, scoring, stale output, and fallback behavior.
5. Run tests, compile checks, and an Alpaca smoke scan when credentials are available; document results.
