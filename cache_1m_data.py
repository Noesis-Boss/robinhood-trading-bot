#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
from src.data import DataFeed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--provider", default="alpaca")
    p.add_argument("--output", default="data/1m")
    args = p.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    feed = DataFeed("America/New_York", provider=args.provider)
    for symbol in args.symbols:
        path = out / f"{symbol}_{args.start}_{args.end}.pkl"
        if path.exists():
            print(f"cached {symbol}")
            continue
        df = feed.get_bars(symbol, interval="1m", start=args.start, end=args.end)
        if df.empty:
            print(f"empty {symbol}")
            continue
        df.to_pickle(path)
        print(f"saved {symbol}: {len(df)} bars -> {path}")


if __name__ == "__main__":
    main()
