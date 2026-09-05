"""Generate parameter grids for 100 unique strategy variants across all strategies."""

import itertools
from src.strategy import LondonBreakoutStrategy
from src.ross_momentum import RossMomentumStrategy
from src.sneaky_pivot import SneakyPivotStrategy
from src.ha_scalp import HAScalpStrategy
from src.auction_flow_proxy import AuctionFlowProxyStrategy
from src.vwap_liquidity_proxy import VWAPLiquidityProxyStrategy
from src.t3_range_filter import T3RangeFilterStrategy
from src.reversal_zone_confirmation import ReversalZoneConfirmationStrategy
from src.ema_cci_macd import EmaCciMacdStrategy
from src.candle_narrative import CandleNarrativeStrategy
from src.supply_demand_swing import SupplyDemandSwingStrategy


def grid_london(n: int) -> list:
    """London Breakout variants — vary breakout_strength, rr, max_bars, box_pct, trend_filter, bias, window."""
    strengths = [0.3, 0.5, 0.75, 1.0]
    rrs = [1.5, 2.0, 3.0]
    bars = [15, 30, 45]
    boxes = [0.003, 0.005, 0.01]
    trends = [True, False]
    biases = [True, False]
    windows = [1.5, 3, 6]
    combos = list(itertools.product(strengths, rrs, bars, boxes, trends, biases, windows))
    return [{
        "name": f"london_s{s}_r{r}_b{b}_x{box}_t{tr}_bi{bi}_w{w}",
        "breakout_strength": s, "rr_ratio": r, "max_holding_bars": b,
        "min_box_pct": box, "trend_filter": tr, "directional_bias": bi,
        "entry_window_hours": w, "backtest_interval": "5m",
    } for s, r, b, box, tr, bi, w in combos[:n]]


def grid_ross(n: int) -> list:
    """Ross momentum — vary min_gap, min_rel_vol, pullback, ema, cutoff, rr, max_bars."""
    gaps = [0.01, 0.02, 0.04]
    rvs = [1.0, 1.5, 2.0]
    pullbacks = [3, 4, 6]
    emas = [5, 9, 20]
    cutoffs = ["09:30", "10:00", "10:30"]
    rrs = [1.0, 1.5, 2.0]
    bars = [20, 30, 45]
    combos = list(itertools.product(gaps, rvs, pullbacks, emas, cutoffs, rrs, bars))
    return [{
        "name": f"ross_g{g}_rv{rv}_p{bb}_e{e}_c{c}_r{r}_b{b}",
        "ross_momentum.min_gap_pct": g,
        "ross_momentum.min_relative_volume": rv,
        "ross_momentum.pullback_lookback": bb,
        "ross_momentum.ema_length": e,
        "ross_momentum.entry_cutoff": c,
        "ross_momentum.rr_ratio": r,
        "ross_momentum.max_holding_bars": b,
        "backtest_interval": "5m",
        "_section": "ross_momentum",
    } for g, rv, bb, e, c, r, b in combos[:n]]


def grid_sneaky(n: int) -> list:
    """Sneaky pivot — vary swing_lookback, proximity, session_start/end, rr, max_bars."""
    swings = [2, 3, 5]
    prox = [0.001, 0.003, 0.005]
    starts = ["09:30", "10:00"]
    ends = ["15:00", "15:45"]
    rrs = [1.0, 1.5, 2.0]
    bars = [15, 26, 35]
    combos = list(itertools.product(swings, prox, starts, ends, rrs, bars))
    return [{
        "name": f"sneaky_sw{sw}_px{p}_ss{s}_se{e}_r{r}_b{b}",
        "sneaky_pivot.swing_lookback": sw,
        "sneaky_pivot.proximity_pct": p,
        "sneaky_pivot.session_start": s,
        "sneaky_pivot.session_end": e,
        "sneaky_pivot.rr_ratio": r,
        "sneaky_pivot.max_holding_bars": b,
        "backtest_interval": "5m",
        "_section": "sneaky_pivot",
    } for sw, p, s, e, r, b in combos[:n]]


def grid_ha_scalp(n: int) -> list:
    """HA scalp — vary ema, doji_ratio, wick_ratio, vol_ratio, rr, interval."""
    emas = [50, 100, 200]
    doji = [0.25, 0.35, 0.5]
    wicks = [0.1, 0.2, 0.3]
    vols = [0.8, 1.0, 1.5]
    rrs = [0.8, 1.0, 1.5]
    intervals = ["5m", "15m"]
    combos = list(itertools.product(emas, doji, wicks, vols, rrs, intervals))
    return [{
        "name": f"ha_e{e}_d{d}_w{w}_v{v}_r{r}_i{i}",
        "ha_scalp.ema_length": e,
        "ha_scalp.doji_body_ratio": d,
        "ha_scalp.min_wick_ratio": w,
        "ha_scalp.min_volume_ratio": v,
        "ha_scalp.rr_ratio": r,
        "ha_scalp.backtest_interval": i,
        "backtest_interval": i,
        "_section": "ha_scalp",
    } for e, d, w, v, r, i in combos[:n]]


def grid_auction(n: int) -> list:
    """Auction flow proxy — vary confirm_rejection, max_gap, max_bar_range."""
    rejects = [True, False]
    gaps = [0.04, 0.08, 0.12]
    bars = [0.04, 0.08, 0.12]
    combos = list(itertools.product(rejects, gaps, bars))
    return [{
        "name": f"auction_cr{g}_gap{ga}_bar{ba}",
        "auction_flow_proxy.confirm_rejection": g,
        "auction_flow_proxy.max_gap_pct": ga,
        "auction_flow_proxy.max_bar_range_pct": ba,
        "backtest_interval": "5m",
        "_section": "auction_flow_proxy",
    } for g, ga, ba in combos[:n]]


def grid_vwap(n: int) -> list:
    """VWAP liquidity proxy — vary vol_mult, rr, max_bars, atr_length, atr_mult, gap, bar_range."""
    vols = [0.8, 1.2, 2.0]
    rrs = [1.5, 2.0, 2.5]
    bars = [20, 30, 45]
    atrs_l = [10, 14, 20]
    atrs_m = [0.8, 1.0, 1.5]
    gaps = [0.04, 0.08]
    bar_ranges = [0.04, 0.08]
    combos = list(itertools.product(vols, rrs, bars, atrs_l, atrs_m, gaps, bar_ranges))
    return [{
        "name": f"vwap_v{v}_r{r}_b{b}_al{am}_am{aa}_g{g}_br{br}",
        "vwap_liquidity_proxy.volume_multiplier": v,
        "vwap_liquidity_proxy.rr_ratio": r,
        "vwap_liquidity_proxy.max_holding_bars": b,
        "vwap_liquidity_proxy.atr_length": am,
        "vwap_liquidity_proxy.atr_multiplier": aa,
        "vwap_liquidity_proxy.max_gap_pct": g,
        "vwap_liquidity_proxy.max_bar_range_pct": br,
        "backtest_interval": "5m",
        "_section": "vwap_liquidity_proxy",
    } for v, r, b, am, aa, g, br in combos[:n]]


def grid_t3(n: int) -> list:
    """T3 range filter — vary t3_length, t3_factor, range_length, range_mult, atr_l, atm_m, target_r, max_bars."""
    t3_l = [5, 8, 12]
    t3_f = [0.5, 0.7, 0.9]
    r_l = [10, 14, 20]
    r_m = [1.5, 2.0, 2.5]
    a_l = [10, 14]
    a_m = [1.0, 1.5, 2.0]
    target = [1.5, 2.0, 2.5]
    bars = [20, 30]
    combos = list(itertools.product(t3_l, t3_f, r_l, r_m, a_l, a_m, target, bars))
    return [{
        "name": f"t3_tl{tl}_tf{fl}_rl{rm}_rm{al}_am{aa}_t{t}_b{b}",
        "t3_range_filter.t3_length": tl,
        "t3_range_filter.t3_factor": fl,
        "t3_range_filter.range_length": rm,
        "t3_range_filter.range_multiplier": al,
        "t3_range_filter.atr_length": aa,
        "t3_range_filter.atr_multiplier": aa,  # alias
        "t3_range_filter.target_r": t,
        "t3_range_filter.max_holding_bars": b,
        "backtest_interval": "1h",
        "_section": "t3_range_filter",
    } for tl, fl, rm, al, aa, a2, t, b in combos[:n]]


def grid_reversal(n: int) -> list:
    """Reversal zone — vary level_lookback, move_lookback, min_move, structure_lookback, confirm_body, vol_mult, rr, max_bars."""
    ll = [10, 20, 30]
    ml = [3, 5]
    mm = [0.002, 0.004, 0.006]
    sl = [3, 5]
    cb = [0.3, 0.5, 0.7]
    vm = [0.8, 1.0, 1.5]
    rrs = [1.5, 2.0, 2.5]
    bars = [20, 30, 45]
    combos = list(itertools.product(ll, ml, mm, sl, cb, vm, rrs, bars))
    return [{
        "name": f"rev_ll{l}_ml{m}_mm{mm}_sl{s}_cb{c}_v{v}_r{r}_b{b}",
        "reversal_zone_confirmation.level_lookback": l,
        "reversal_zone_confirmation.move_lookback": m,
        "reversal_zone_confirmation.min_move_pct": mm,
        "reversal_zone_confirmation.structure_lookback": s,
        "reversal_zone_confirmation.confirmation_body_ratio": c,
        "reversal_zone_confirmation.volume_multiplier": v,
        "reversal_zone_confirmation.rr_ratio": r,
        "reversal_zone_confirmation.max_holding_bars": b,
        "backtest_interval": "1m",
        "_section": "reversal_zone_confirmation",
    } for l, m, mm, s, c, v, r, b in combos[:n]]


def grid_emaccmacd(n: int) -> list:
    """EMA/CCI/MACD — vary ema_fast, ema_slow, cci_length, macd params, zone_touch, vol_mult, rr, max_bars."""
    ef = [20, 50, 80]
    es = [110, 150, 200]
    cc = [14, 20, 30]
    mf = [8, 12, 20]
    ms = [20, 26, 30]
    zt = [2, 3, 5]
    vm = [0.8, 1.0, 1.5]
    rrs = [1.5, 2.0]
    bars = [20, 30, 45]
    combos = list(itertools.product(ef, es, cc, mf, ms, zt, vm, rrs, bars))
    return [{
        "name": f"emaccmacd_ef{e}_es{s}_cc{c}_mf{mf}_ms{ms}_zt{z}_v{v}_r{r}_b{b}",
        "ema_cci_macd.ema_fast": e,
        "ema_cci_macd.ema_slow": s,
        "ema_cci_macd.cci_length": c,
        "ema_cci_macd.macd_fast": mf,
        "ema_cci_macd.macd_slow": ms,
        "ema_cci_macd.zone_touch_bars": z,
        "ema_cci_macd.volume_multiplier": v,
        "ema_cci_macd.rr_ratio": r,
        "ema_cci_macd.max_holding_bars": b,
        "backtest_interval": "1m",
        "_section": "ema_cci_macd",
    } for e, s, c, mf, ms, z, v, r, b in combos[:n]]


def grid_candle_narrative(n: int) -> list:
    """Candle narrative — vary trend_ema, zone_lookback, pivot_L/R, impulse_L, pullback_L, engulf_ratio, pin_wick, body_ratio, vol_mult, rr."""
    te = [15, 20, 30]
    zl = [20, 30, 40]
    plr = [2, 3, 5]
    il = [3, 4, 6]
    pl = [2, 3, 5]
    er = [1.0, 1.2, 1.5]
    pw = [1.5, 2.0, 2.5]
    br = [0.5, 0.6, 0.7]
    vm = [0.8, 1.2, 2.0]
    rrs = [1.5, 2.0]
    combos = list(itertools.product(te, zl, plr, il, pl, er, pw, br, vm, rrs))
    return [{
        "name": f"cn_te{t}_zl{z}_p{plr}_i{i}_pb{pl}_e{e}_pw{w}_b{b}_v{v}_r{r}",
        "candle_narrative.trend_ema": t,
        "candle_narrative.zone_lookback": z,
        "candle_narrative.pivot_left_right": plr,
        "candle_narrative.impulse_lookback": i,
        "candle_narrative.pullback_lookback": pl,
        "candle_narrative.min_engulf_ratio": e,
        "candle_narrative.pin_wick_ratio": w,
        "candle_narrative.min_body_ratio": b,
        "candle_narrative.volume_multiplier": v,
        "candle_narrative.rr_ratio": r,
        "backtest_interval": "5m",
        "_section": "candle_narrative",
    } for t, z, plr, i, pl, e, w, b, v, r in combos[:n]]


def grid_supply_demand(n: int) -> list:
    """Supply/demand swing — vary pivot_k, move_bars, min_move_pct, RR, break_even_trigger."""
    ks = [2, 3, 5]
    mb = [3, 5]
    mm = [0.005, 0.01, 0.02]
    rrs = [1.5, 2.0, 2.5]
    bet = [0.5, 1.0, 1.5]
    combos = list(itertools.product(ks, mb, mm, rrs, bet))
    return [{
        "name": f"sd_k{k}_mb{m}_mm{mm}_r{r}_be{be}",
        "supply_demand_swing.pivot_lookback": k,
        "supply_demand_swing.move_bars": m,
        "supply_demand_swing.min_move_pct": mm,
        "supply_demand_swing.target_rr": r,
        "supply_demand_swing.break_even_trigger_r": be,
        "backtest_interval": "1d",
        "_section": "supply_demand_swing",
    } for k, m, mm, r, be in combos[:n]]


# Registry: (strategy_cls, section_key, grid_fn, budget)
# Section key: None = top-level config merge; string = section sub-dict merge
STRATEGY_REGISTRY = [
    (LondonBreakoutStrategy, None, grid_london, 20),
    (RossMomentumStrategy, "ross_momentum", grid_ross, 12),
    (SneakyPivotStrategy, "sneaky_pivot", grid_sneaky, 8),
    (HAScalpStrategy, "ha_scalp", grid_ha_scalp, 10),
    (AuctionFlowProxyStrategy, "auction_flow_proxy", grid_auction, 5),
    (VWAPLiquidityProxyStrategy, "vwap_liquidity_proxy", grid_vwap, 10),
    (T3RangeFilterStrategy, "t3_range_filter", grid_t3, 10),
    (ReversalZoneConfirmationStrategy, "reversal_zone_confirmation", grid_reversal, 10),
    (EmaCciMacdStrategy, "ema_cci_macd", grid_emaccmacd, 8),
    (CandleNarrativeStrategy, "candle_narrative", grid_candle_narrative, 5),
    (SupplyDemandSwingStrategy, None, grid_supply_demand, 2),
]


def build_variant_list(target_total: int = 100) -> list:
    """Build a list of (strategy_cls, section_key, params) totaling ~target_total."""
    variants = []
    for cls, section, fn, budget in STRATEGY_REGISTRY:
        for params in fn(budget):
            variants.append((cls, section, params))
    return variants[:target_total]
