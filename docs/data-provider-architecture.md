# ORION Market Data Provider Architecture

ORION is broker-independent by design.

The strategy and backtester consume a canonical MarketDataAdapter interface. Provider-specific code stays behind adapters.

Current adapters:
- OANDA: existing REST client
- MT5: optional terminal adapter

Required canonical fields:
- UTC candle timestamp
- open/high/low/close
- volume
- provider-specific spread/real-volume fields when available

MT5 Python integration provides M15, H1, H4 and D1 bars through the installed terminal. ORION normalizes provider timestamps to UTC before strategy processing.

Provider selection must never alter OAFS logic. Data-provider differences are recorded as data-quality differences rather than silently changing the strategy.

Live execution remains separate from market-data ingestion.
