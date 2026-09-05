# Fundamental Candidate Filter Design

Date: 2026-08-15
Project: Robinhood Trading Bot
Status: Approved design; implementation not started

## Goal

Add a deterministic, offline fundamental-quality filter inspired by Investment Council. It will improve candidate ranking without becoming an execution strategy or changing the bot's technical entries, exits, or risk controls.

## Scope

The first version is backend-only. It will:

- read the bot's existing daily-universe candidates and available provider data;
- calculate a repeatable 0–100 fundamental score;
- emit `fundamental_context.json` with scores, component values, and risk flags;
- optionally reject candidates below a configurable floor and add a ranking bonus above a configurable threshold;
- remain disabled by default for backward compatibility.

It will not:

- import the Investment Council's Claude Code stages;
- call an LLM;
- place orders or choose direction;
- alter stops, targets, position sizing, or broker behavior;
- require Yahoo Finance when Alpaca data is configured.

## Architecture

Add `src/fundamental_filter.py` with small, testable functions:

1. `score_candidate(record, config) -> dict` computes the score from normalized fields.
2. `score_candidates(records, config) -> list[dict]` scores a batch deterministically.
3. `write_fundamental_context(path, results, run_metadata)` writes an atomic JSON artifact.
4. `load_fundamental_context(path)` returns only a current, valid artifact or an explicit fallback state.

The filter will consume fields already available or safely optional: price, market cap, average dollar volume, volatility, trend measures, valuation ratios, profitability, growth, leverage, and missing-data indicators. Missing optional values receive neutral treatment and are recorded; they will not silently become bullish points.

The output record will contain:

```json
{
  "symbol": "AAPL",
  "score": 72.0,
  "components": {
    "quality": 18.0,
    "valuation": 14.0,
    "growth": 15.0,
    "financial_health": 16.0,
    "liquidity_and_risk": 9.0
  },
  "risk_flags": ["high_valuation"],
  "missing_fields": [],
  "eligible": true,
  "scored_at": "..."
}
```

## Integration

The existing daily-universe workflow will remain the source of candidate symbols. When `fundamental_filter.enabled` is false, behavior remains byte-for-byte equivalent to the current selection path.

When enabled:

- candidates below `reject_below` are removed;
- candidates at or above `bonus_at` receive a bounded ranking bonus;
- candidates between the thresholds remain unchanged;
- an empty or stale fundamental artifact triggers static fallback and a visible warning rather than blocking the bot;
- the result is written once per run/day, not fetched inside the five-minute order loop.

Initial configuration:

```yaml
fundamental_filter:
  enabled: false
  reject_below: 40
  bonus_at: 60
  max_bonus: 10
  context_path: "fundamental_context.json"
```

No broker or strategy module will import the filter directly. Integration will occur at candidate-universe preparation so the execution loop receives only symbols.

## Error handling and safety

- Invalid numeric values are treated as missing.
- Scores are clamped to 0–100.
- JSON writes use a temporary file followed by replacement.
- Artifacts include a run date and input universe hash to prevent stale reuse.
- Provider failures preserve the existing static-universe fallback.
- Default-disabled behavior is covered by a regression test.
- No credentials, order calls, or external LLM calls are introduced.

## Testing

Add focused tests covering:

- strong, weak, and mixed candidate fixtures;
- missing and malformed fields;
- score bounds and deterministic repeatability;
- risk-flag generation;
- stale or mismatched artifact rejection;
- threshold behavior and bounded ranking bonus;
- default-disabled behavior;
- empty-result fallback.

Run the existing full test suite and a fixed historical comparison with the filter disabled versus enabled. The implementation is successful only if the default suite remains green and the comparison reports trade count, win rate, profit factor, net P&L, and expectancy for both modes without claiming profitability from a short sample.

## Documentation

Update the bot's `AGENTS.md` with the configuration, artifact contract, test results, and the explicit status that this is research-only until broader out-of-sample validation supports enabling it.
