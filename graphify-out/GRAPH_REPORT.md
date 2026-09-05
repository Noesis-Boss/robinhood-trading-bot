# Graph Report - robinhood-trading-bot  (2026-09-05)

## Corpus Check
- 131 files · ~133,958 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 675 nodes · 1316 edges · 36 communities (28 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 54 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c8468f96`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SupplyDemandSwingStrategy
- ThetaFarmer
- test_monitor.py
- gamma_monitor.py
- daily_universe.py
- RobinhoodReadOnly
- OrbfvgStrategy
- backtest_runner.py
- batch_runner.py
- build_100_variants
- RiskManager
- UniversalBoilerplate
- EmaCciMacdStrategy
- .generate_signal
- ._build_call_spread
- CandleNarrativeStrategy
- batch_backtester.py
- universal_backtester.py
- test_eps_line_put_selling.py
- fundamental_filter.py
- Robinhood Trading Bot — Project Guidance
- ReversalZoneConfirmationStrategy
- HAScalpStrategy
- App.tsx
- RossMomentumStrategy
- batch_backtest.py
- DataFeed
- test_sensitivity_reproducibility.py
- bot.py
- run_all.py
- strategies.py
- VWAPLiquidityProxyStrategy
- grid.py

## God Nodes (most connected - your core abstractions)
1. `RiskManager` - 42 edges
2. `TradeJournal` - 33 edges
3. `DataFeed` - 25 edges
4. `LondonBreakoutStrategy` - 23 edges
5. `CandleNarrativeStrategy` - 21 edges
6. `EmaCciMacdStrategy` - 20 edges
7. `SupplyDemandSwingStrategy` - 19 edges
8. `ThetaFarmer` - 18 edges
9. `RossMomentumStrategy` - 18 edges
10. `Robinhood Trading Bot — Project Guidance` - 17 edges

## Surprising Connections (you probably didn't know these)
- `UniversalBoilerplate` --uses--> `TradeJournal`  [INFERRED]
  framework/boilerplate.py → src/journal.py
- `UniversalBoilerplate` --uses--> `RiskManager`  [INFERRED]
  framework/boilerplate.py → src/risk.py
- `register_strategies()` --uses--> `EmaCciMacdStrategy`  [INFERRED]
  framework/batch_runner.py → src/ema_cci_macd.py
- `build_grid()` --uses--> `EmaCciMacdStrategy`  [INFERRED]
  framework/strategies.py → src/ema_cci_macd.py
- `register_strategies()` --uses--> `CandleNarrativeStrategy`  [INFERRED]
  framework/batch_runner.py → src/candle_narrative.py

## Import Cycles
- None detected.

## Communities (36 total, 5 thin omitted)

### Community 0 - "SupplyDemandSwingStrategy"
Cohesion: 0.09
Nodes (33): load_bars(), main(), metrics(), monte_carlo(), DataFrame, Backtest runner for SupplyDemandSwingStrategy (daily bars). Usage: python3…, run_backtest(), load_state() (+25 more)

### Community 1 - "ThetaFarmer"
Cohesion: 0.15
Nodes (7): Options Theta Farming Module Strategy: After a successful London Breakout…, Calculate position size based on capital and risk., Execute a theta farming trade (paper mode by default)., Resolve a credit spread to its realistic expiry P&L. The short spread expires…, Return summary of theta farming performance., ThetaFarmer, ThetaOnlyStrategy

### Community 2 - "test_monitor.py"
Cohesion: 0.08
Nodes (40): BaseHTTPRequestHandler, fixture, BehaviorLayer, BusinessLayer, check_behavior(), check_business(), check_performance(), check_technical() (+32 more)

### Community 3 - "gamma_monitor.py"
Cohesion: 0.33
Nodes (9): _bs_gamma(), compute_gex(), get_gamma_regime(), log_daily(), main(), _nearest_iv(), SPY gamma-exposure monitor — read-only research proxy (no orders, ever).…, Append (or overwrite) today's GEX snapshot row. One row per calendar day. (+1 more)

### Community 4 - "daily_universe.py"
Cohesion: 0.29
Nodes (8): filter_asset(), hard_rejections(), passes_filters(), Path, Daily premarket universe discovery for live paper trading., scan_candidates(), score_metrics(), write_scan()

### Community 5 - "RobinhoodReadOnly"
Cohesion: 0.21
Nodes (4): RobinhoodReadOnly, FakeRobinhood, test_missing_credentials_is_safe(), test_read_only_snapshot()

### Community 7 - "backtest_runner.py"
Cohesion: 0.11
Nodes (20): Thin CLI shim for the backtest engine. The implementation lives in…, main(), Sensitivity sweep for the London breakout `breakout_strength` knob. Runs the…, Per spec.md AC4. Default row is the one matching the `default` arg. Recommend…, recommend(), _row_md(), annotate_gex(), load_config() (+12 more)

### Community 8 - "batch_runner.py"
Cohesion: 0.15
Nodes (16): BacktestResult, BacktestRunner, Maps strategy name → strategy class., Composite score: PF * sqrt(trades) * (WR/100). Rewards strategies that have…, Run a single strategy variant and return BacktestResult., StrategyRegistry, load_config(), main() (+8 more)

### Community 9 - "build_100_variants"
Cohesion: 0.15
Nodes (19): _auction_grid(), build_100_variants(), _candle_narrative_grid(), _ema_cci_macd_grid(), _ha_scalp_grid(), _london_grid(), Reversal zone confirmation sweep., Candle narrative sweep. (+11 more)

### Community 10 - "RiskManager"
Cohesion: 0.07
Nodes (20): ABC, DataFrame, Timestamp, Universal strategy base class — every strategy implements just two methods., Legacy compatibility — wraps _signals., Legacy compatibility — wraps _exits., Return a list of entry signals (0 or 1 per bar)., Return exit dict if trade should close, else None. (+12 more)

### Community 11 - "UniversalBoilerplate"
Cohesion: 0.12
Nodes (11): BoilerplateConfig, DataFrame, Series, Record a trade entry and update counters., Record a trade exit and update equity., Return boolean mask for session hours., Configuration for the strategy boilerplate., Wraps any strategy with consistent risk management and session logic. (+3 more)

### Community 12 - "EmaCciMacdStrategy"
Cohesion: 0.22
Nodes (8): EmaCciMacdStrategy, _frame(), _strategy(), test_check_exit_respects_stop_target_and_time_limits(), test_defaults_are_fixed_and_research_only(), test_downtrend_bounce_cannot_signal_long_against_trend(), test_flat_and_insufficient_data_produce_no_signal(), test_uptrend_pullback_bounce_can_only_signal_long_with_valid_levels()

### Community 13 - ".generate_signal"
Cohesion: 0.15
Nodes (9): DataFrame, Timestamp, Average volume over the lookback window., Check if the latest close is above the N-bar simple moving average., Check if the latest close is below the N-bar simple moving average., Generate a trading signal from the latest bar., Check if an active trade should be exited., Record a trade as active. (+1 more)

### Community 14 - "._build_call_spread"
Cohesion: 0.20
Nodes (6): Build a call credit spread for a bearish breakout., Strike width (per share) bounded so per-contract max loss stays realistic.…, Realistic per-share credit so per-contract premium lands in the $5-15 range., Generate a single credit spread trade for a confirmed breakout. Args: symbol:…, After a confirmed London Breakout, find credit spread opportunities. Args:…, Build a put credit spread for a bullish breakout.

### Community 15 - "CandleNarrativeStrategy"
Cohesion: 0.23
Nodes (5): CandleNarrativeStrategy, _bars(), _strategy(), test_candle_narrative_flat_market_no_signal(), test_candle_narrative_rejects_short_history_and_defaults()

### Community 16 - "batch_backtester.py"
Cohesion: 0.09
Nodes (23): Execute one backtest with given params., Run a single strategy backtest., run_strategy(), load_config(), main(), run_batch(), run_single_backtest(), Universal Strategy Boilerplate for the Robinhood Trading Bot. Wraps any… (+15 more)

### Community 17 - "universal_backtester.py"
Cohesion: 0.18
Nodes (12): generate_grid(), Any, Strategy Grid Generator. Generates 100 strategy permutations by varying key…, Generate strategy grid with up to max_per_strategy variations per base strategy., Save strategy grid to JSON., save_grid(), main(), rank_results() (+4 more)

### Community 18 - "test_eps_line_put_selling.py"
Cohesion: 0.08
Nodes (34): RiskManager, bs_put_price(), EpsLinePutSellingStrategy, _norm_cdf(), Paper-only long-dated put selling on EPS-line valuation entries. Variant of the…, Mark-to-market liability of open puts under a stressed spot., Sell long-dated puts at the EPS line. Cash-secured by default., main() (+26 more)

### Community 19 - "fundamental_filter.py"
Cohesion: 0.33
Nodes (9): load_fundamental_context(), _number(), _points(), Path, Deterministic fundamental-quality scoring for daily candidate selection., score_candidate(), score_candidates(), _universe_hash() (+1 more)

### Community 20 - "Robinhood Trading Bot — Project Guidance"
Cohesion: 0.11
Nodes (17): Backtest (canonical, via Alpaca, 2026-07-01 to 2026-08-06), Data Provider & Cost (decided 2026-08-08), EPS-Line Put Selling (added 2026-09-04, paper-only), Feature Log, Feature Log, Gamma Monitor (added 2026-09-05, read-only), Issue Log, Key Source Files (+9 more)

### Community 24 - "App.tsx"
Cohesion: 0.25
Nodes (4): App(), strategies, Strategy, symbols

### Community 27 - "batch_backtest.py"
Cohesion: 0.13
Nodes (10): generate_strategies(), main(), Batch Backtest Engine — 100 Strategy Grid. Generates 100 parameter combinations…, Generate 100 strategy variants (10 per strategy type)., Score a strategy result. Higher is better., score_strategy(), Forward Tester for Top 3 Strategies. Takes the top 3 strategies from batch…, Data feed abstraction. Supports two providers: - provider="auto" -> use Alpaca… (+2 more)

### Community 28 - "DataFeed"
Cohesion: 0.08
Nodes (23): date, ClosedTrade, _make_config(), Backtest engine — runs one strategy variant over historical data. Handles…, Build a config dict for a specific strategy variant. - section_key=None: params…, Run one strategy variant. Returns summary dict., run_single(), _summarize() (+15 more)

### Community 30 - "test_sensitivity_reproducibility.py"
Cohesion: 0.32
Nodes (5): _load_sensitivity_module(), T3 acceptance test: the sensitivity runner is byte-deterministic. Runs the…, Same input -> same output. Two runs, byte-equal., TestOverrideNonMutating, TestReproducibility

### Community 31 - "bot.py"
Cohesion: 0.16
Nodes (9): load_config(), main(), Broker, Close an open position., Return current position for a symbol if any., Place an options credit spread (theta farming). Args: symbol: Underlying stock…, Order execution via Robinhood (or paper-trading stub). Set ROBINHOOD_USERNAME /…, Place a buy (long) or sell short order. qty is a float, so fractional-share… (+1 more)

### Community 32 - "run_all.py"
Cohesion: 0.70
Nodes (4): generate_report(), main(), run_batch(), run_forward()

### Community 33 - "strategies.py"
Cohesion: 0.18
Nodes (7): build_grid(), _cfg(), 100-strategy grid for backtesting. Each entry is (strategy_class, section_key,…, Return list of (strategy_class, section_key, params) — 100 entries., SneakyPivotStrategy, LondonBreakoutStrategy, London Breakout day trading strategy. Based on the video's approach: 1. Build a…

### Community 35 - "grid.py"
Cohesion: 0.07
Nodes (26): build_variant_list(), grid_auction(), grid_candle_narrative(), grid_emaccmacd(), grid_ha_scalp(), grid_london(), grid_reversal(), grid_ross() (+18 more)

## Knowledge Gaps
- **19 isolated node(s):** `Data Provider & Cost (decided 2026-08-08)`, `Window Retune (2026-08-08) — option 1 accepted`, `Backtest (canonical, via Alpaca, 2026-07-01 to 2026-08-06)`, `EPS-Line Put Selling (added 2026-09-04, paper-only)`, `ORB + FVG (added 2026-09-05, paper-only)` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 227 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RiskManager` connect `RiskManager` to `strategies.py`, `backtest_runner.py`, `batch_runner.py`, `UniversalBoilerplate`, `EmaCciMacdStrategy`, `batch_backtester.py`, `test_eps_line_put_selling.py`, `batch_backtest.py`, `DataFeed`, `bot.py`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `LondonBreakoutStrategy` connect `strategies.py` to `grid.py`, `batch_runner.py`, `RiskManager`, `.generate_signal`, `batch_backtester.py`, `batch_backtest.py`, `bot.py`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `TradeJournal` connect `batch_backtester.py` to `strategies.py`, `backtest_runner.py`, `batch_runner.py`, `UniversalBoilerplate`, `batch_backtest.py`, `DataFeed`, `bot.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `RiskManager` (e.g. with `BacktestRunner` and `UniversalStrategy`) actually correct?**
  _`RiskManager` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `TradeJournal` (e.g. with `BacktestRunner` and `UniversalBoilerplate`) actually correct?**
  _`TradeJournal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `DataFeed` (e.g. with `BacktestRunner` and `ForwardTester`) actually correct?**
  _`DataFeed` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LondonBreakoutStrategy` (e.g. with `register_strategies()` and `build_grid()`) actually correct?**
  _`LondonBreakoutStrategy` has 4 INFERRED edges - model-reasoned connections that need verification._