# Graph Report - robinhood-trading-bot  (2026-09-04)

## Corpus Check
- 127 files · ~129,263 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 640 nodes · 1258 edges · 38 communities (29 shown, 6 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 54 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `635bf2c8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SupplyDemandSwingStrategy
- ThetaFarmer
- test_monitor.py
- batch_backtester.py
- daily_universe.py
- api.py
- VWAPLiquidityProxyStrategy
- RiskManager
- SneakyPivotStrategy
- build_100_variants
- UniversalStrategy
- UniversalBoilerplate
- EmaCciMacdStrategy
- .generate_signal
- DataFeed
- CandleNarrativeStrategy
- TradeJournal
- universal_backtester.py
- test_eps_line_put_selling.py
- Ema9ContinuationStrategy
- Robinhood Trading Bot — Project Guidance
- run_backtest
- Broker
- Ema20StochPullbackStrategy
- App.tsx
- .get_bars
- ._calc_max_drawdown
- HAScalpStrategy
- test_sensitivity_reproducibility.py
- batch_backtest.py
- run_all.py
- RossMomentumStrategy
- grid.py
- AuctionFlowProxyStrategy
- T3RangeFilterStrategy

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
10. `finalize_trade()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `UniversalStrategy` --uses--> `RiskManager`  [INFERRED]
  framework/base_strategy.py → src/risk.py
- `BacktestRunner` --uses--> `RiskManager`  [INFERRED]
  framework/base.py → src/risk.py
- `UniversalBoilerplate` --uses--> `RiskManager`  [INFERRED]
  framework/boilerplate.py → src/risk.py
- `ForwardTestRunner` --uses--> `RiskManager`  [INFERRED]
  framework/forward_tester.py → src/risk.py
- `UniversalBoilerplate` --uses--> `TradeJournal`  [INFERRED]
  framework/boilerplate.py → src/journal.py

## Import Cycles
- None detected.

## Communities (38 total, 6 thin omitted)

### Community 0 - "SupplyDemandSwingStrategy"
Cohesion: 0.09
Nodes (33): load_bars(), main(), metrics(), monte_carlo(), DataFrame, Backtest runner for SupplyDemandSwingStrategy (daily bars). Usage: python3…, run_backtest(), load_state() (+25 more)

### Community 1 - "ThetaFarmer"
Cohesion: 0.10
Nodes (13): Options Theta Farming Module Strategy: After a successful London Breakout…, Build a call credit spread for a bearish breakout., Strike width (per share) bounded so per-contract max loss stays realistic.…, Realistic per-share credit so per-contract premium lands in the $5-15 range., Calculate position size based on capital and risk., Execute a theta farming trade (paper mode by default)., Resolve a credit spread to its realistic expiry P&L. The short spread expires…, Return summary of theta farming performance. (+5 more)

### Community 2 - "test_monitor.py"
Cohesion: 0.10
Nodes (34): fixture, BehaviorLayer, BusinessLayer, check_behavior(), check_business(), check_performance(), check_technical(), _detect_provider() (+26 more)

### Community 3 - "batch_backtester.py"
Cohesion: 0.18
Nodes (13): date, load_config(), main(), run_batch(), run_single_backtest(), Universal Strategy Boilerplate for the Robinhood Trading Bot. Wraps any…, DataFrame, Process a single bar. Returns trade result if one was closed. (+5 more)

### Community 4 - "daily_universe.py"
Cohesion: 0.16
Nodes (18): filter_asset(), hard_rejections(), passes_filters(), Path, Daily premarket universe discovery for live paper trading., scan_candidates(), score_metrics(), symbols_for_today() (+10 more)

### Community 5 - "api.py"
Cohesion: 0.13
Nodes (10): BaseHTTPRequestHandler, RobinhoodReadOnly, FakeRobinhood, test_missing_credentials_is_safe(), test_read_only_snapshot(), build_backtest_args(), Handler, _monitor_snapshot() (+2 more)

### Community 6 - "VWAPLiquidityProxyStrategy"
Cohesion: 0.12
Nodes (13): BacktestResult, Maps strategy name → strategy class., Composite score: PF * sqrt(trades) * (WR/100). Rewards strategies that have…, StrategyRegistry, load_config(), main(), Save results to JSON., Register all strategies with their parameter grids. (+5 more)

### Community 7 - "RiskManager"
Cohesion: 0.11
Nodes (12): ForwardResult, ForwardTester, Any, Paper-trade a strategy on live/latest available data., Run forward-test for a given strategy variant., Check if an order passes risk validation. Returns (True, "ok") or (False,…, Calculate position size based on fixed-dollar risk. Args: entry: Entry price.…, Position sizing and risk validation for the London Breakout strategy. From the… (+4 more)

### Community 9 - "build_100_variants"
Cohesion: 0.15
Nodes (19): _auction_grid(), build_100_variants(), _candle_narrative_grid(), _ema_cci_macd_grid(), _ha_scalp_grid(), _london_grid(), Reversal zone confirmation sweep., Candle narrative sweep. (+11 more)

### Community 10 - "UniversalStrategy"
Cohesion: 0.14
Nodes (10): ABC, DataFrame, Timestamp, Universal strategy base class — every strategy implements just two methods., Legacy compatibility — wraps _signals., Legacy compatibility — wraps _exits., Return a list of entry signals (0 or 1 per bar)., Return exit dict if trade should close, else None. (+2 more)

### Community 11 - "UniversalBoilerplate"
Cohesion: 0.12
Nodes (11): BoilerplateConfig, DataFrame, Series, Record a trade entry and update counters., Record a trade exit and update equity., Return boolean mask for session hours., Configuration for the strategy boilerplate., Wraps any strategy with consistent risk management and session logic. (+3 more)

### Community 12 - "EmaCciMacdStrategy"
Cohesion: 0.22
Nodes (8): EmaCciMacdStrategy, _frame(), _strategy(), test_check_exit_respects_stop_target_and_time_limits(), test_defaults_are_fixed_and_research_only(), test_downtrend_bounce_cannot_signal_long_against_trend(), test_flat_and_insufficient_data_produce_no_signal(), test_uptrend_pullback_bounce_can_only_signal_long_with_valid_levels()

### Community 13 - ".generate_signal"
Cohesion: 0.15
Nodes (9): DataFrame, Timestamp, Average volume over the lookback window., Check if the latest close is above the N-bar simple moving average., Check if the latest close is below the N-bar simple moving average., Generate a trading signal from the latest bar., Check if an active trade should be exited., Record a trade as active. (+1 more)

### Community 14 - "DataFeed"
Cohesion: 0.20
Nodes (12): ClosedTrade, _make_config(), Backtest engine — runs one strategy variant over historical data. Handles…, Build a config dict for a specific strategy variant. - section_key=None: params…, Run one strategy variant. Returns summary dict., run_single(), _summarize(), load_config() (+4 more)

### Community 15 - "CandleNarrativeStrategy"
Cohesion: 0.23
Nodes (5): CandleNarrativeStrategy, _bars(), _strategy(), test_candle_narrative_flat_market_no_signal(), test_candle_narrative_rejects_short_history_and_defaults()

### Community 16 - "TradeJournal"
Cohesion: 0.09
Nodes (16): BacktestRunner, Run a single strategy variant and return BacktestResult., Execute one backtest with given params., ForwardTestRunner, main(), Run forward tests on top N strategies., Runs a single strategy in paper mode with small capital., run_forward_tests() (+8 more)

### Community 17 - "universal_backtester.py"
Cohesion: 0.18
Nodes (12): generate_grid(), Any, Strategy Grid Generator. Generates 100 strategy permutations by varying key…, Generate strategy grid with up to max_per_strategy variations per base strategy., Save strategy grid to JSON., save_grid(), main(), rank_results() (+4 more)

### Community 18 - "test_eps_line_put_selling.py"
Cohesion: 0.08
Nodes (28): RiskManager, bs_put_price(), EpsLinePutSellingStrategy, _norm_cdf(), Paper-only long-dated put selling on EPS-line valuation entries. Variant of the…, Mark-to-market liability of open puts under a stressed spot., Sell long-dated puts at the EPS line. Cash-secured by default., main() (+20 more)

### Community 19 - "Ema9ContinuationStrategy"
Cohesion: 0.24
Nodes (5): Ema9ContinuationStrategy, Research-only 9 EMA continuation strategy from the SMB Capital tutorial., make_bars(), test_research_strategy_has_no_signal_without_volume_confirmation(), test_signal_contains_defined_risk_levels()

### Community 20 - "Robinhood Trading Bot — Project Guidance"
Cohesion: 0.17
Nodes (11): Backtest (canonical, via Alpaca, 2026-07-01 to 2026-08-06), Data Provider & Cost (decided 2026-08-08), EPS-Line Put Selling (added 2026-09-04, paper-only), Feature Log, Feature Log, Issue Log, Key Source Files, Robinhood Trading Bot — Project Guidance (+3 more)

### Community 21 - "run_backtest"
Cohesion: 0.20
Nodes (13): Thin CLI shim for the backtest engine. The implementation lives in…, main(), Sensitivity sweep for the London breakout `breakout_strength` knob. Runs the…, Per spec.md AC4. Default row is the one matching the `default` arg. Recommend…, recommend(), _row_md(), load_config(), main() (+5 more)

### Community 22 - "Broker"
Cohesion: 0.20
Nodes (6): Broker, Close an open position., Return current position for a symbol if any., Place an options credit spread (theta farming). Args: symbol: Underlying stock…, Order execution via Robinhood (or paper-trading stub). Set ROBINHOOD_USERNAME /…, Place a buy (long) or sell short order. qty is a float, so fractional-share…

### Community 24 - "App.tsx"
Cohesion: 0.25
Nodes (4): App(), strategies, Strategy, symbols

### Community 25 - ".get_bars"
Cohesion: 0.29
Nodes (3): DataFrame, Timestamp, Fetch OHLCV bars. When start/end are given, they take precedence over period…

### Community 27 - "HAScalpStrategy"
Cohesion: 0.15
Nodes (5): build_grid(), _cfg(), Return list of (strategy_class, section_key, params) — 100 entries., HAScalpStrategy, ReversalZoneConfirmationStrategy

### Community 30 - "test_sensitivity_reproducibility.py"
Cohesion: 0.32
Nodes (5): _load_sensitivity_module(), T3 acceptance test: the sensitivity runner is byte-deterministic. Runs the…, Same input -> same output. Two runs, byte-equal., TestOverrideNonMutating, TestReproducibility

### Community 31 - "batch_backtest.py"
Cohesion: 0.31
Nodes (8): generate_strategies(), main(), Batch Backtest Engine — 100 Strategy Grid. Generates 100 parameter combinations…, Generate 100 strategy variants (10 per strategy type)., Run a single strategy backtest., Score a strategy result. Higher is better., run_strategy(), score_strategy()

### Community 32 - "run_all.py"
Cohesion: 0.70
Nodes (4): generate_report(), main(), run_batch(), run_forward()

### Community 35 - "grid.py"
Cohesion: 0.08
Nodes (29): Forward Tester for Top 3 Strategies. Takes the top 3 strategies from batch…, build_variant_list(), grid_auction(), grid_candle_narrative(), grid_emaccmacd(), grid_ha_scalp(), grid_london(), grid_reversal() (+21 more)

## Knowledge Gaps
- **13 isolated node(s):** `Strategy`, `Backtest (canonical, via Alpaca, 2026-07-01 to 2026-08-06)`, `Data Provider & Cost (decided 2026-08-08)`, `EPS-Line Put Selling (added 2026-09-04, paper-only)`, `Feature Log` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 215 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RiskManager` connect `RiskManager` to `batch_backtester.py`, `grid.py`, `UniversalStrategy`, `UniversalBoilerplate`, `EmaCciMacdStrategy`, `DataFeed`, `TradeJournal`, `test_eps_line_put_selling.py`, `Ema9ContinuationStrategy`, `run_backtest`, `Broker`, `batch_backtest.py`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Why does `LondonBreakoutStrategy` connect `RiskManager` to `grid.py`, `batch_backtester.py`, `VWAPLiquidityProxyStrategy`, `.generate_signal`, `DataFeed`, `TradeJournal`, `HAScalpStrategy`, `batch_backtest.py`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `TradeJournal` connect `TradeJournal` to `batch_backtester.py`, `grid.py`, `RiskManager`, `UniversalBoilerplate`, `DataFeed`, `run_backtest`, `batch_backtest.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `RiskManager` (e.g. with `BacktestRunner` and `UniversalStrategy`) actually correct?**
  _`RiskManager` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `TradeJournal` (e.g. with `BacktestRunner` and `UniversalBoilerplate`) actually correct?**
  _`TradeJournal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `DataFeed` (e.g. with `BacktestRunner` and `ForwardTester`) actually correct?**
  _`DataFeed` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LondonBreakoutStrategy` (e.g. with `register_strategies()` and `build_grid()`) actually correct?**
  _`LondonBreakoutStrategy` has 4 INFERRED edges - model-reasoned connections that need verification._