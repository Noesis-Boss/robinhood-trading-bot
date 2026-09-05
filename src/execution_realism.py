"""Shared research-only execution cost model."""


def valid_bar(bar) -> bool:
    try:
        values = [float(bar[field]) for field in ("open", "high", "low", "close")]
        return all(value > 0 for value in values) and float(bar.get("volume", 0)) > 0 and float(bar.high) >= float(bar.low)
    except (KeyError, TypeError, ValueError):
        return False


def finalize_trade(result: dict, config: dict) -> dict:
    """Add conservative research costs while retaining theoretical gross P&L."""
    cfg = config.get("execution_realism", {})
    slippage_bps = float(cfg.get("slippage_bps", 5.0))
    spread_bps = float(cfg.get("spread_bps", 5.0))
    qty = abs(float(result.get("qty", 0)))
    entry = abs(float(result.get("entry", 0)))
    exit_price = abs(float(result.get("exit_price", entry)))
    notional = qty * (entry + exit_price)
    cost = notional * (slippage_bps + spread_bps) / 10000
    gross = float(result.get("pnl", 0))
    result["gross_pnl"] = round(gross, 2)
    result["execution_cost"] = round(cost, 2)
    result["pnl"] = round(gross - cost, 2)
    result["net_pnl"] = result["pnl"]
    result["slippage_bps"] = slippage_bps
    result["spread_bps"] = spread_bps
    return result
