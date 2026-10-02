"""Default research universe and provider-neutral market metadata."""

from dataclasses import dataclass
from typing import Literal


AssetClass = Literal["crypto", "forex", "index"]


@dataclass(frozen=True)
class ResearchInstrument:
    symbol: str
    asset_class: AssetClass
    provider_symbol: str | None = None


DEFAULT_UNIVERSE: tuple[ResearchInstrument, ...] = (
    ResearchInstrument("BTCUSDT", "crypto", "BTCUSDT"),
    ResearchInstrument("ETHUSDT", "crypto", "ETHUSDT"),
    ResearchInstrument("EURUSD", "forex", None),
    ResearchInstrument("GBPUSD", "forex", None),
    ResearchInstrument("USDJPY", "forex", None),
    ResearchInstrument("NAS100", "index", None),
    ResearchInstrument("US30", "index", None),
    ResearchInstrument("SPX500", "index", None),
)


def symbols_for(asset_class: AssetClass | None = None) -> tuple[str, ...]:
    items = DEFAULT_UNIVERSE
    if asset_class is not None:
        items = tuple(item for item in items if item.asset_class == asset_class)
    return tuple(item.symbol for item in items)
