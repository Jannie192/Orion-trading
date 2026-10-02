from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import pandas as pd

from .market_data import MarketDataAdapter
from .regime import classify_regime
from .signals import detect
from .models import SignalCandidate

DEFAULT_TIMEFRAMES = ("H4", "H1", "M15")


@dataclass(frozen=True)
class ScanResult:
    instrument: str
    timeframe: str
    scanned_at: datetime
    regime: str
    direction: str
    candidates: tuple[SignalCandidate, ...]


class MarketScanner:
    """Broker-neutral multi-market scanner.

    It discovers and explains opportunities; execution remains separate.
    """

    def __init__(self, provider: MarketDataAdapter, timeframes: Iterable[str] = DEFAULT_TIMEFRAMES):
        self.provider = provider
        self.timeframes = tuple(timeframes)

    def scan(self, instruments: Iterable[str], *, start: datetime, end: datetime) -> list[ScanResult]:
        results: list[ScanResult] = []
        for instrument in instruments:
            for timeframe in self.timeframes:
                candles = self.provider.candles(instrument, timeframe, start, end)
                if candles.empty or len(candles) < 60:
                    results.append(ScanResult(instrument, timeframe, end, "INSUFFICIENT_DATA", "NEUTRAL", ()))
                    continue
                candles = candles.sort_index()
                regime, direction = classify_regime(candles)
                candidates = tuple(detect(candles, regime, instrument))
                results.append(ScanResult(instrument, timeframe, end, regime.value, direction.value, candidates))
        return results

    @staticmethod
    def actionable(results: Iterable[ScanResult]) -> list[SignalCandidate]:
        return [c for r in results for c in r.candidates if c.valid]
