# ORION Dashboard

The ORION dashboard is a static command-center frontend.

## Current capabilities
- Responsive dark command-center UI
- Overview / Markets / Signals / Research / Backtests / Risk / Settings navigation shell
- Asset and timeframe filters
- Customizable dashboard panels
- Local preference persistence
- Explicit research-only / execution-disabled state
- Ready for API-backed market, research, risk and execution adapters

## Safety
The dashboard does not place trades. Live execution remains disabled until the backend execution layer is deliberately connected and separately authorized.

## Next integration
Connect the dashboard to ORION's Python research engine through a small API service, then replace placeholder metrics with validated research artifacts and live paper-trading state.
