# Fundamental Filter Implementation Plan

1. Add deterministic scoring and atomic context-artifact loading/writing in `src/fundamental_filter.py`.
2. Add disabled-by-default configuration and integrate filtering at daily-universe preparation only.
3. Add fixture-based tests for scoring, missing data, stale artifacts, thresholds, fallback, and default behavior.
4. Run the full test suite and a fixed comparison with the filter disabled and enabled.
5. Update `AGENTS.md` with the final implementation and verification results.
