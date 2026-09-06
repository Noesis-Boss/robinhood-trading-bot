import { useEffect, useState } from "react";

const symbols = [
  "SPY",
  "QQQ",
  "AAPL",
  "TSLA",
  "NVDA",
  "SOFI",
  "F",
  "AAL",
  "MARA",
  "RIVN",
  "NIO",
  "RBLX",
  "DKNG",
];
const strategies = {
  london: {
    label: "London breakout",
    params: [
      ["breakout_strength", "Breakout strength", 0.75],
      ["min_box_pct", "Minimum box %", 0.005],
      ["max_box_pct", "Maximum box %", 0.04],
      ["entry_window_hours", "Entry window hours", 3],
      ["volume_multiplier", "Volume multiplier", 0.8],
      ["trend_lookback", "Trend lookback", 20],
      ["rr_ratio", "Reward/risk", 2],
      ["max_holding_bars", "Max holding bars", 30],
    ],
  },
  ross: {
    label: "Ross momentum",
    params: [
      ["min_gap_pct", "Minimum gap %", 0.02],
      ["min_price", "Minimum price", 1],
      ["min_relative_volume", "Minimum relative volume", 1.5],
      ["pullback_lookback", "Pullback lookback", 4],
      ["ema_length", "EMA length", 9],
      ["entry_cutoff", "Entry cutoff", "10:00"],
      ["rr_ratio", "Reward/risk", 1.5],
      ["max_holding_bars", "Max holding bars", 30],
    ],
  },
  sneaky: {
    label: "Sneaky pivot",
    params: [
      ["swing_lookback", "Swing lookback", 2],
      ["proximity_pct", "Level proximity %", 0.003],
      ["session_start", "Session start", "09:30"],
      ["session_end", "Session end", "15:45"],
      ["rr_ratio", "Reward/risk", 1],
      ["max_holding_bars", "Max holding bars", 26],
    ],
  },
  ha_scalp: {
    label: "Heikin-Ashi scalp",
    params: [
      ["backtest_interval", "Backtest interval", "15m"],
      ["ema_length", "EMA length", 100],
      ["doji_body_ratio", "Doji body ratio", 0.35],
      ["min_wick_ratio", "Minimum wick ratio", 0.2],
      ["min_volume_ratio", "Minimum volume ratio", 1],
      ["rr_ratio", "Reward/risk", 1],
      ["session_start", "Session start", "09:30"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  auction_flow_proxy: {
    label: "Auction flow proxy (OHLCV)",
    params: [
      ["trend_length", "Trend length", 20],
      ["location_lookback", "Location lookback", 40],
      ["volume_multiplier", "Volume multiplier", 1],
      ["rr_ratio", "Reward/risk", 2],
      ["max_holding_bars", "Max holding bars", 30],
      ["max_gap_pct", "Maximum gap %", 0.08],
      ["max_bar_range_pct", "Maximum bar range %", 0.08],
      ["confirm_rejection", "Confirm rejection", true],
    ],
  },
  vwap_liquidity_proxy: {
    label: "VWAP liquidity proxy (research)",
    params: [
      ["volume_multiplier", "Volume multiplier", 1.2],
      ["rr_ratio", "Reward/risk", 2],
      ["max_holding_bars", "Max holding bars", 30],
      ["atr_length", "ATR length", 14],
      ["atr_multiplier", "ATR multiplier", 1],
      ["max_gap_pct", "Maximum gap %", 0.08],
      ["max_bar_range_pct", "Maximum bar range %", 0.08],
      ["session_start", "Session start", "09:30"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  t3_range_filter: {
    label: "T3 range filter (research)",
    params: [
      ["backtest_interval", "Backtest interval", "1h"],
      ["t3_length", "T3 length", 8],
      ["t3_factor", "T3 factor", 0.7],
      ["range_length", "Range length", 14],
      ["range_multiplier", "Range multiplier", 2],
      ["atr_length", "ATR length", 14],
      ["atr_multiplier", "ATR multiplier", 1.5],
      ["target_r", "Target R", 2],
      ["max_holding_bars", "Max holding bars", 30],
      ["max_gap_pct", "Maximum gap %", 0.08],
      ["max_bar_range_pct", "Maximum bar range %", 0.08],
      ["session_start", "Session start", "09:30"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  reversal_zone_confirmation: {
    label: "Reversal zone confirmation (research)",
    params: [
      ["backtest_interval", "Backtest interval", "1m"],
      ["level_lookback", "Zone lookback", 20],
      ["move_lookback", "Fast move bars", 3],
      ["min_move_pct", "Minimum move %", 0.004],
      ["structure_lookback", "Structure lookback", 3],
      ["confirmation_body_ratio", "Confirmation body ratio", 0.5],
      ["volume_multiplier", "Volume multiplier", 1],
      ["rr_ratio", "Reward/risk", 2],
      ["max_holding_bars", "Max holding bars", 30],
      ["session_start", "Session start", "09:35"],
      ["session_end", "Session end", "11:00"],
    ],
  },
  ema_cci_macd: {
    label: "EMA/CCI/MACD pullback (research)",
    params: [
      ["ema_fast", "Fast EMA", 50],
      ["ema_slow", "Slow EMA", 110],
      ["cci_length", "CCI length", 20],
      ["macd_fast", "MACD fast", 12],
      ["macd_slow", "MACD slow", 26],
      ["macd_signal", "MACD signal", 9],
      ["zone_touch_bars", "Zone touch lookback", 3],
      ["zone_proximity_pct", "Zone proximity %", 0.002],
      ["volume_multiplier", "Volume multiplier", 1],
      ["atr_length", "ATR length", 14],
      ["rr_ratio", "Reward/risk", 2],
      ["max_holding_bars", "Max holding bars", 30],
      ["session_start", "Session start", "09:35"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  ema9_continuation: {
    label: "9 EMA continuation (research)",
    params: [
      ["ema_length", "EMA length", 9],
      ["volume_multiplier", "Volume multiplier", 1.2],
      ["pullback_bars", "Pullback lookback", 3],
      ["touch_tolerance_pct", "Touch tolerance %", 0.002],
      ["rr_ratio", "Reward/risk", 2],
      ["atr_length", "ATR length", 14],
      ["atr_multiplier", "ATR stop multiplier", 0.5],
      ["max_holding_bars", "Max holding bars", 30],
      ["max_gap_pct", "Maximum gap %", 0.08],
      ["max_bar_range_pct", "Maximum bar range %", 0.08],
      ["session_start", "Session start", "09:35"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  ema20_stoch_pullback: {
    label: "20 EMA/Stochastic pullback (research)",
    params: [
      ["backtest_interval", "Backtest interval", "1m"],
      ["ema_length", "EMA length", 20],
      ["k_length", "Stochastic %K", 8],
      ["d_length", "Stochastic %D", 5],
      ["slowing", "Stochastic slowing", 3],
      ["deviation_pct", "Deviation threshold %", 0.002],
      ["target_fraction", "Target fraction to EMA", 0.25],
      ["atr_length", "ATR length", 14],
      ["atr_multiplier", "ATR stop multiplier", 1],
      ["max_holding_bars", "Max holding bars", 30],
      ["session_start", "Session start", "09:35"],
      ["session_end", "Session end", "15:45"],
    ],
  },
  theta_only: {
    label: "Theta only",
    params: [["theta_aggressiveness", "Theta aggressiveness", "balanced"]],
  },
  eps_line_put_selling: {
    label: "EPS-line put selling (paper)",
    params: [
      ["target_pe", "Target P/E", 15],
      ["dte", "Days to expiry", 730],
      ["iv", "IV", 0.30],
      ["max_collateral_pct", "Max collateral %", 0.30],
      ["min_days_between_entries", "Min days between entries", 21],
      ["min_yield_annual_pct", "Min annual yield %", 5.0],
      ["max_distance_to_line_pct", "Max distance to line %", 2.0],
      ["rsi_period", "RSI period", 14],
      ["rsi_max", "RSI max", 40],
      ["securing", "Securing (cash|margin)", "cash"],
    ],
  },
  trailing_stop_ladder: {
    label: "Trailing stop ladder (paper)",
    params: [
      ["ema_fast", "EMA fast", 9],
      ["ema_slow", "EMA slow", 50],
      ["volume_multiplier", "Volume multiplier", 1.2],
      ["stop_buffer_atr", "Stop buffer ATR", 0.5],
      ["rung_r", "Rung size (R)", 1.0],
      ["lock_offset_r", "Lock offset (R)", 1.0],
      ["max_holding_bars", "Max holding bars", 78],
    ],
  },
} as const;
type Strategy = keyof typeof strategies;

function App() {
  const [strategy, setStrategy] = useState<Strategy>("london");
  const [params, setParams] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState(symbols.slice(0, 5));
  const [form, setForm] = useState<any>({
    start: "2026-07-01",
    end: "2026-08-06",
    capital: 300,
    provider: "alpaca",
    interval: "5m",
    theta: false,
    max_entries_per_day: "1",
  });
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [account, setAccount] = useState<any>(null);
  const [monitor, setMonitor] = useState<any>(null);

  useEffect(() => {
    fetch("/api/robinhood/status")
      .then((response) => response.json())
      .then(setAccount)
      .catch(() =>
        setAccount({
          status: "error",
          message: "Unable to reach account adapter.",
        }),
      );
  }, []);

  useEffect(() => {
    const load = () => {
      fetch("/api/monitor")
        .then((r) => r.json())
        .then(setMonitor)
        .catch(() => setMonitor({ error: "unavailable" }));
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const definition = strategies[strategy];
  const changeStrategy = (value: Strategy) => {
    setStrategy(value);
    setParams(
      Object.fromEntries(
        strategies[value].params.map(([key, , defaultValue]) => [
          key,
          defaultValue,
        ]),
      ),
    );
    setForm((v: any) => ({
      ...v,
      interval:
        value === "t3_range_filter"
          ? "1h"
          : value === "ha_scalp"
            ? "15m"
            : "5m",
    }));
  };
  const setParam = (key: string, value: any) =>
    setParams((v) => ({ ...v, [key]: value }));
  const run = async () => {
    setStatus("running");
    setError("");
    setResult(null);
    try {
      const response = await fetch("/api/backtests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          strategy,
          symbols: selected,
          interval: form.interval,
          strategy_params: params,
        }),
      });
      const started = await response.json();
      if (!response.ok) throw new Error(started.error);
      let job;
      do {
        await new Promise((r) => setTimeout(r, 1000));
        job = await (await fetch(`/api/backtests/${started.job_id}`)).json();
      } while (job.status === "running");
      if (job.status === "error") throw new Error(job.error);
      setResult(job.result);
      setStatus("complete");
    } catch (e: any) {
      setError(e.message || "Backtest failed.");
      setStatus("error");
    }
  };
  return (
    <main>
      <header>
        <div>
          <span className="eyebrow">MARKET RESEARCH / PAPER ONLY</span>
          <h1>Strategy lab</h1>
          <p>Configure, run, and compare historical trading models.</p>
        </div>
        <div className="status">
          <i /> Alpaca IEX <span>●</span> connected
        </div>
      </header>
      <section className="layout">
        <aside className="panel config">
          <div className="panel-title">
            <span>01</span>
            <h2>Run setup</h2>
          </div>
          <label>
            Strategy
            <select
              value={strategy}
              onChange={(e) => changeStrategy(e.target.value as Strategy)}
            >
              {Object.entries(strategies).map(([key, value]) => (
                <option value={key} key={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>
          <div className="grid2">
            <label>
              Start
              <input
                type="date"
                value={form.start}
                onChange={(e) => setForm({ ...form, start: e.target.value })}
              />
            </label>
            <label>
              End
              <input
                type="date"
                value={form.end}
                onChange={(e) => setForm({ ...form, end: e.target.value })}
              />
            </label>
          </div>
          <div className="grid2">
            <label>
              Capital
              <input
                type="number"
                value={form.capital}
                onChange={(e) =>
                  setForm({ ...form, capital: Number(e.target.value) })
                }
              />
            </label>
            <label>
              Interval
              <select
                value={form.interval}
                onChange={(e) => setForm({ ...form, interval: e.target.value })}
              >
                <option>1m</option>
                <option>5m</option>
                <option>15m</option>
                <option>1h</option>
              </select>
            </label>
          </div>
          <div className="panel-title second">
            <span>02</span>
            <h2>Universe</h2>
          </div>
          <div className="chips">
            {symbols.map((symbol) => (
              <button
                className={selected.includes(symbol) ? "chip active" : "chip"}
                onClick={() =>
                  setSelected((v) =>
                    v.includes(symbol)
                      ? v.filter((x) => x !== symbol)
                      : [...v, symbol],
                  )
                }
                key={symbol}
              >
                {symbol}
              </button>
            ))}
          </div>
          <div className="panel-title second">
            <span>03</span>
            <h2>Parameters</h2>
          </div>
          <div className="grid2">
            {definition.params.map(([key, label, defaultValue]) => (
              <label key={key}>
                {label}
                <input
                  type={typeof defaultValue === "number" ? "number" : "text"}
                  step="any"
                  value={params[key] ?? defaultValue}
                  onChange={(e) =>
                    setParam(
                      key,
                      typeof defaultValue === "number"
                        ? Number(e.target.value)
                        : e.target.value,
                    )
                  }
                />
              </label>
            ))}
          </div>
          <label>
            Max entries / ticker / day
            <select
              value={form.max_entries_per_day}
              onChange={(e) =>
                setForm({ ...form, max_entries_per_day: e.target.value })
              }
            >
              <option value="1">1 entry</option>
              <option value="2">2 entries</option>
              <option value="3">3 entries</option>
              <option value="5">5 entries</option>
              <option value="Unlimited">Unlimited</option>
            </select>
          </label>
          <label className="switch">
            <input
              type="checkbox"
              checked={form.theta}
              onChange={(e) => setForm({ ...form, theta: e.target.checked })}
            />
            <span /> Include theta farming
          </label>
          <button
            className="run"
            disabled={status === "running" || !selected.length}
            onClick={run}
          >
            {status === "running" ? "RUNNING…" : "RUN BACKTEST  →"}
          </button>
          {error && <div className="error">{error}</div>}
        </aside>
        <section className="workspace">
          <div className="panel account-panel">
            <div>
              <span className="eyebrow">ROBINHOOD / READ ONLY</span>
              <h2>Live account</h2>
            </div>
            <strong>{account?.status === 'ok' ? 'Connected' : account?.status === 'error' ? 'Unavailable' : 'Not configured'}</strong>
            <p>{account?.status === 'ok' ? `Cash $${account.account.cash} · Buying power $${account.account.buying_power} · ${account.positions.length} positions` : account?.message || 'Checking credentials…'}</p>
          </div>
          <div className="workspace-head">
            <div>
              <span className="eyebrow">RESULTS</span>
              <h2>
                {status === "complete" ? "Latest backtest" : "Ready for a run"}
              </h2>
            </div>
            <span className="research-pill">
              {definition.label.toUpperCase()} / RESEARCH
            </span>
          </div>
          {status === "idle" && (
            <div className="empty">
              <div className="empty-mark">⌁</div>
              <h3>Your next experiment starts here.</h3>
              <p>
                Choose a model and date range, then run the real backtest
                engine.
              </p>
            </div>
          )}
          {status === "running" && (
            <div className="empty">
              <div className="loader" />
              <h3>Running historical test</h3>
              <p>Fetching {selected.length} symbols.</p>
            </div>
          )}
          {status === "complete" && <Results data={result} />}
        </section>
      </section>
      <MonitorPanel data={monitor} />
    </main>
  );
}
function Results({ data }: { data: any }) {
  return (
    <>
      <div className="meta">
        {data.start_date} → {data.end_date} <span>·</span> {data.symbols.length}{" "}
        symbols <span>·</span> {data.trade_count} trades
      </div>
      <div className="metrics">
        <Metric
          label="Net P&L"
          value={`${data.net_pnl >= 0 ? "+" : ""}$${data.net_pnl.toFixed(2)}`}
          tone={data.net_pnl >= 0 ? "green" : "red"}
        />
        <Metric label="Gross P&L" value={`$${data.gross_pnl.toFixed(2)}`} />
        <Metric
          label="Execution cost"
          value={`-$${data.execution_cost.toFixed(2)}`}
        />
        <Metric label="Win rate" value={`${data.win_rate.toFixed(1)}%`} />
        <Metric
          label="Profit factor"
          value={data.profit_factor?.toFixed(2) || "—"}
        />
        <Metric
          label="Ending capital"
          value={`$${data.final_capital.toFixed(2)}`}
        />
        {data.strategy === "eps_line_put_selling" && (
          <>
            <Metric
              label="Premium collected"
              value={`$${(data.premium_collected ?? 0).toLocaleString()}`}
              tone="green"
            />
            <Metric
              label="Open max liability"
              value={`$${(data.open_max_liability ?? 0).toLocaleString()}`}
            />
            <Metric
              label="Unrealized MTM"
              value={`${(data.unrealized_mtm ?? 0) >= 0 ? "+" : ""}$${(data.unrealized_mtm ?? 0).toFixed(2)}`}
              tone={(data.unrealized_mtm ?? 0) >= 0 ? "green" : "red"}
            />
            <Metric
              label="Open positions"
              value={`${data.open_positions ?? 0} · ${data.securing ?? "cash"} · ${data.dte ?? "—"}dte`}
            />
          </>
        )}
      </div>
    </>
  );
}
function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone || ""}>{value}</strong>
    </div>
  );
}
function MonitorPanel({ data }: { data: any }) {
  const statusColor = (s: string) => s === "ok" ? "green" : s === "warning" || s === "degraded" ? "yellow" : "red";
  return (
    <section className="panel monitor-panel">
      <div className="monitor-head">
        <div>
          <span className="eyebrow">FOUR-LAYER MONITORING</span>
          <h2>System health</h2>
        </div>
        <strong className={statusColor(data?.overall_status)}>{data?.overall_status?.toUpperCase() || "UNKNOWN"}</strong>
      </div>
      {data?.alerts?.length > 0 && (
        <div className="monitor-alerts">
          {data.alerts.map((a: string, i: number) => (
            <div className="alert" key={i}>{a}</div>
          ))}
        </div>
      )}
      <div className="monitor-grid">
        <div className="monitor-layer">
          <div className="layer-head">
            <span>01 — TECHNICAL</span>
            <strong className={statusColor(data?.technical?.status)}>{data?.technical?.status}</strong>
          </div>
          <div className="layer-body">
            <div className="layer-metric"><span>Bot alive</span><strong>{data?.technical?.bot_alive ? "yes" : "no"}</strong></div>
            <div className="layer-metric"><span>API reachable</span><strong>{data?.technical?.api_reachable ? "yes" : "no"}</strong></div>
            <div className="layer-metric"><span>Data feed</span><strong>{data?.technical?.data_feed}</strong></div>
            <div className="layer-metric"><span>Latency</span><strong>{data?.technical?.data_feed_latency_ms >= 0 ? `${data.technical.data_feed_latency_ms}ms` : "—"}</strong></div>
          </div>
        </div>
        <div className="monitor-layer">
          <div className="layer-head">
            <span>02 — PERFORMANCE</span>
            <strong className={statusColor(data?.performance?.status)}>{data?.performance?.status}</strong>
          </div>
          <div className="layer-body">
            <div className="layer-metric"><span>Win rate</span><strong>{data?.performance?.win_rate?.toFixed(1)}%</strong></div>
            <div className="layer-metric"><span>Profit factor</span><strong>{data?.performance?.profit_factor === Infinity ? "∞" : data?.performance?.profit_factor?.toFixed(2) || "—"}</strong></div>
            <div className="layer-metric"><span>Max drawdown</span><strong>{data?.performance?.max_drawdown_pct?.toFixed(1)}%</strong></div>
            <div className="layer-metric"><span>Trades / expected</span><strong>{data?.performance?.total_trades} / {data?.performance?.trade_count_expected}</strong></div>
          </div>
        </div>
        <div className="monitor-layer">
          <div className="layer-head">
            <span>03 — BEHAVIOR</span>
            <strong className={statusColor(data?.behavior?.status)}>{data?.behavior?.status}</strong>
          </div>
          <div className="layer-body">
            <div className="layer-metric"><span>Signal interval</span><strong>{data?.behavior?.avg_signal_interval_min} min</strong></div>
            <div className="layer-metric"><span>Signal freq</span><strong>{data?.behavior?.signal_frequency_status}</strong></div>
            <div className="layer-metric"><span>Slippage</span><strong>{data?.behavior?.avg_slippage_bps} bps ({data?.behavior?.slippage_status})</strong></div>
            <div className="layer-metric"><span>After hours</span><strong>{data?.behavior?.after_hours_trades}</strong></div>
          </div>
        </div>
        <div className="monitor-layer">
          <div className="layer-head">
            <span>04 — BUSINESS</span>
            <strong className={statusColor(data?.business?.status)}>{data?.business?.status}</strong>
          </div>
          <div className="layer-body">
            <div className="layer-metric"><span>Net P&L</span><strong>${data?.business?.net_pnl?.toFixed(2)}</strong></div>
            <div className="layer-metric"><span>Theta P&L</span><strong>${data?.business?.theta_pnl?.toFixed(2)}</strong></div>
            <div className="layer-metric"><span>Risk budget used</span><strong>{data?.business?.risk_budget_used_pct?.toFixed(1)}% ({data?.business?.risk_budget_status})</strong></div>
            <div className="layer-metric"><span>Target</span><strong>{data?.business?.pnl_vs_target_pct?.toFixed(0)}% of ${data?.business?.target_monthly_pnl?.toFixed(0)}</strong></div>
          </div>
        </div>
      </div>
    </section>
  )
}
export default App;
