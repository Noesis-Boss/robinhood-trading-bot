"""Thin CLI shim for the backtest engine.

The implementation lives in `src/backtest_runner.py` so the engine can be
called as a function from other scripts (e.g. sensitivity sweeps, tests).
This shim preserves the original CLI surface verbatim.
"""

from src.backtest_runner import main


if __name__ == "__main__":
    main()
