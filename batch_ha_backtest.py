#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
import tempfile
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed


def main():
    parser = argparse.ArgumentParser(description="Run HA scalp one-minute backtests independently per symbol")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--capital", type=float, default=300)
    parser.add_argument("--provider", default="alpaca")
    parser.add_argument("--interval", default="1m", choices=["1m", "5m", "15m"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--data-dir", default="data/1m")
    parser.add_argument("--output", default="ha_scalp_batch_results.json")
    args = parser.parse_args()

    project = Path(__file__).resolve().parent
    cache = subprocess.run(["python3", "cache_1m_data.py", "--symbols", *args.symbols, "--start", args.start, "--end", args.end, "--provider", args.provider, "--output", args.data_dir], cwd=project, capture_output=True, text=True)
    print(cache.stdout, end="")
    if cache.returncode != 0:
        raise SystemExit(f"cache build failed with exit code {cache.returncode}")
    config = yaml.safe_load((project / "config.yaml").read_text())
    config.setdefault("ha_scalp", {})["backtest_interval"] = args.interval
    config_path = Path(tempfile.mkstemp(prefix="ha-scalp-", suffix=".yaml")[1])
    config_path.write_text(yaml.safe_dump(config))
    def run_symbol(symbol):
        command = [
            "python3", "backtest.py", "--strategy", "ha_scalp", "--capital", str(args.capital),
            "--provider", args.provider, "--config", str(config_path), "--data-dir", args.data_dir, "--symbols", symbol, "--start", args.start, "--end", args.end,
        ]
        completed = subprocess.run(command, cwd=project, capture_output=True, text=True)
        output = completed.stdout + completed.stderr
        result = {"symbol": symbol, "returncode": completed.returncode, "output": output}
        for line in output.splitlines():
            if line.startswith("Total trades:"):
                result["trades"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("Total P&L:"):
                result["pnl"] = float(line.split("$", 1)[1])
            elif line.startswith("Win rate:"):
                result["win_rate"] = float(line.split(":", 1)[1].strip().rstrip("%"))
            elif line.startswith("Profit factor:"):
                result["profit_factor"] = float(line.split(":", 1)[1].strip())
        return result

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_symbol, symbol): symbol for symbol in args.symbols}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['symbol']}: {result.get('trades', 0)} trades, ${result.get('pnl', 0):.2f} P&L")

    traded = [r for r in results if "trades" in r]
    aggregate = {
        "symbols": args.symbols,
        "start": args.start,
        "end": args.end,
        "capital_per_symbol": args.capital,
        "total_trades": sum(r.get("trades", 0) for r in traded),
        "total_pnl": round(sum(r.get("pnl", 0) for r in traded), 2),
        "symbols_completed": len(traded),
    }
    payload = {"aggregate": aggregate, "symbols": results}
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
