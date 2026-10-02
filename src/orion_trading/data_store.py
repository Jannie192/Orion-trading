from __future__ import annotations

from pathlib import Path
import pandas as pd

class CsvDataStore:
    """Simple provider-neutral research store; one file per instrument/timeframe."""
    def __init__(self, root: str = "data/market"):
        self.root = Path(root)

    def save(self, instrument: str, timeframe: str, frame: pd.DataFrame) -> Path:
        path = self.root / instrument
        path.mkdir(parents=True, exist_ok=True)
        out = path / f"{timeframe}.csv"
        frame.to_csv(out, index=True, date_format="%Y-%m-%dT%H:%M:%S%z")
        return out

    def load(self, instrument: str, timeframe: str) -> pd.DataFrame:
        path = self.root / instrument / f"{timeframe}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
        return df.sort_index()
