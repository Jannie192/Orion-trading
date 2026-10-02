from __future__ import annotations
from datetime import datetime
import os
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

TIMEFRAMES = {"M15":"TIMEFRAME_M15","H1":"TIMEFRAME_H1","H4":"TIMEFRAME_H4","D1":"TIMEFRAME_D1"}

class MT5Client:
    """Optional MT5 market-data adapter. No broker is hard-coded."""
    def __init__(self, path: str | None = None):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        self.path = path or os.getenv("MT5_TERMINAL_PATH")

    def connect(self, login: int | None = None, password: str | None = None, server: str | None = None) -> None:
        kwargs = {}
        if login is not None:
            kwargs.update(login=login, password=password or "", server=server or "")
        ok = mt5.initialize(self.path, **kwargs) if self.path else mt5.initialize(**kwargs)
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    def close(self) -> None:
        mt5.shutdown()

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        start = pd.Timestamp(start).tz_convert("UTC").to_pydatetime()
        end = pd.Timestamp(end).tz_convert("UTC").to_pydatetime()
        rates = mt5.copy_rates_range(instrument, getattr(mt5, TIMEFRAMES[timeframe]), start, end)
        if rates is None:
            raise RuntimeError(f"MT5 history failed for {instrument}/{timeframe}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        if df.empty:
            return pd.DataFrame(columns=["open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index().rename(columns={"tick_volume":"volume"})
        return df[["open","high","low","close","volume","spread","real_volume"]]
