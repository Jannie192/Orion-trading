from __future__ import annotations
from datetime import datetime
from typing import Protocol
import pandas as pd

class MarketDataAdapter(Protocol):
    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return canonical OHLCV candles indexed by UTC timestamp."""
