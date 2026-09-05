"""Data feed abstraction.

Supports two providers:
  - provider="auto"  -> use Alpaca (IEX feed, free) when ALPACA_API_KEY and
                        ALPACA_SECRET_KEY env vars are present, else yfinance.
  - provider="alpaca"  -> require Alpaca keys (Settings > Advanced secrets).
  - provider="yfinance"-> force yfinance (Yahoo, ~60-day limit on 5m bars).

All providers return a DataFrame indexed by a timezone-aware DatetimeIndex with
columns: open, high, low, close, volume.
"""
import os

import pandas as pd

INTERVAL_ALPACA = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour"}


def _has_alpaca_keys() -> bool:
    return bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))


class DataFeed:
    def __init__(self, timezone: str = "America/New_York", provider: str = "auto"):
        self.timezone = timezone
        if provider == "auto":
            provider = "alpaca" if _has_alpaca_keys() else "yfinance"
        if provider == "alpaca" and not _has_alpaca_keys():
            raise RuntimeError(
                "provider='alpaca' requires ALPACA_API_KEY and ALPACA_SECRET_KEY "
                "secrets (Settings > Advanced)."
            )
        self.provider = provider
        self._alpaca = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_bars(
        self,
        symbol: str,
        interval: str = "5m",
        period: str = "1d",
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars.

        When start/end are given, they take precedence over period (needed for
        multi-day backtests that Alpaca supports but Yahoo does not).
        """
        if self.provider == "alpaca":
            return self._alpaca_bars(symbol, interval, start=start, end=end, period=period)
        return self._yf_bars(symbol, interval, start=start, end=end, period=period)

    def get_latest_bar(self, symbol: str, interval: str = "5m") -> pd.DataFrame:
        return self.get_bars(symbol, interval=interval, period="2d")

    # ------------------------------------------------------------------ #
    # Alpaca (IEX feed — free, real-time, supports historical 5m beyond 60d)
    # ------------------------------------------------------------------ #
    def _alpaca_client(self):
        if self._alpaca is None:
            from alpaca.data.historical import StockHistoricalDataClient

            self._alpaca = StockHistoricalDataClient(
                os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
            )
        return self._alpaca

    def _alpaca_bars(self, symbol, interval, start=None, end=None, period="1d"):
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        client = self._alpaca_client()
        # Map interval string -> TimeFrame
        if interval == "5m":
            timeframe = TimeFrame(5, TimeFrameUnit.Minute)
        elif interval == "1m":
            timeframe = TimeFrame(1, TimeFrameUnit.Minute)
        elif interval == "15m":
            timeframe = TimeFrame(15, TimeFrameUnit.Minute)
        elif interval == "1h":
            timeframe = TimeFrame(1, TimeFrameUnit.Hour)
        elif interval == "1d":
            timeframe = TimeFrame(1, TimeFrameUnit.Day)
        else:
            raise ValueError(f"Unsupported interval: {interval}")

        if end is None:
            end = pd.Timestamp.now(tz="US/Eastern")
        else:
            end = pd.Timestamp(end)
            if end.tzinfo is None:
                end = end.tz_localize(self.timezone)
        if start is None:
            # period like "1d" / "2d" -> look back that many calendar days
            days = int(str(period).rstrip("d")) if str(period).rstrip("d").isdigit() else 1
            start = end - pd.Timedelta(days=days)
        else:
            start = pd.Timestamp(start)
            if start.tzinfo is None:
                start = start.tz_localize(self.timezone)

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            feed="iex",
            adjustment="all",
        )
        bars = client.get_stock_bars(req)
        if bars.df is None or bars.df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = bars.df.reset_index()
        df = df[df["symbol"] == symbol].copy()
        df = df.rename(columns={"timestamp": "time"})
        df["time"] = pd.to_datetime(df["time"]).dt.tz_convert(self.timezone)
        df = df.set_index("time").sort_index()
        cols = ["open", "high", "low", "close", "volume"]
        return df[[c for c in cols if c in df.columns]]

    # ------------------------------------------------------------------ #
    # yfinance (fallback)
    # ------------------------------------------------------------------ #
    def _yf_bars(self, symbol, interval, start=None, end=None, period="1d"):
        import yfinance as yf

        kwargs = {"interval": interval, "auto_adjust": True, "prepost": True}
        if start is not None and end is not None:
            kwargs["start"] = start
            kwargs["end"] = end
        else:
            kwargs["period"] = period

        df = yf.Ticker(symbol).history(**kwargs)
        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if df.index.tz is None:
            df.index = df.index.tz_localize("US/Eastern")
        else:
            df.index = df.index.tz_convert("US/Eastern")
        df.columns = [c.lower() for c in df.columns]
        cols = ["open", "high", "low", "close", "volume"]
        return df[[c for c in cols if c in df.columns]].sort_index()
