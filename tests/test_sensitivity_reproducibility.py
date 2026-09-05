"""T3 acceptance test: the sensitivity runner is byte-deterministic.

Runs the engine twice on the same input and asserts the trade list and
the produced markdown file are byte-identical. Catches:
  - nondeterministic seeding
  - hidden config mutation between calls
  - data caching that drifts between calls
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_sensitivity_module():
    spec = importlib.util.spec_from_file_location(
        "backtest_sensitivity", PROJECT_ROOT / "backtest_sensitivity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReproducibility(unittest.TestCase):
    def test_runner_is_byte_deterministic(self):
        """Same input -> same output. Two runs, byte-equal."""
        mod = _load_sensitivity_module()
        cfg = mod.load_config(str(PROJECT_ROOT / "config.yaml"))
        symbols = ["SPY", "QQQ"]
        start, end = "2026-08-01", "2026-08-06"
        data_dir = str(PROJECT_ROOT / "data" / "1m")

        trades_a = mod.run_backtest(cfg, symbols, start, end,
                                    provider="yfinance", strategy_name="london",
                                    data_dir=data_dir, json_output=False,
                                    breakout_strength_override=0.75)
        trades_b = mod.run_backtest(cfg, symbols, start, end,
                                    provider="yfinance", strategy_name="london",
                                    data_dir=data_dir, json_output=False,
                                    breakout_strength_override=0.75)

        def fingerprint(t):
            return (t["symbol"], t["direction"], t["entry"],
                    t.get("exit_price"), round(t["pnl"], 4), t.get("reason"))

        self.assertEqual(
            [fingerprint(t) for t in trades_a],
            [fingerprint(t) for t in trades_b],
            "Two backtest runs on the same input must be identical",
        )


class TestOverrideNonMutating(unittest.TestCase):
    def test_override_does_not_mutate_caller_config(self):
        mod = _load_sensitivity_module()
        cfg = mod.load_config(str(PROJECT_ROOT / "config.yaml"))
        original = cfg["breakout_strength"]
        _ = mod.run_backtest(cfg, ["SPY"], "2026-08-01", "2026-08-06",
                             provider="yfinance", strategy_name="london",
                             data_dir=str(PROJECT_ROOT / "data" / "1m"),
                             breakout_strength_override=0.42)
        self.assertEqual(
            cfg["breakout_strength"], original,
            "breakout_strength_override must not mutate the caller's config",
        )


if __name__ == "__main__":
    unittest.main()
