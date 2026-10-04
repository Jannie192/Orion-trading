from __future__ import annotations

from .execution import ExecutionAdapter, OrderRequest, OrderResult
from .models import Direction


class MT5Execution:
    """Optional MetaTrader 5 execution adapter.

    Importing this module does not require MetaTrader5 until an instance is used.
    Live trading is explicitly opt-in and disabled by default.
    """

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        terminal_path: str | None = None,
        live_enabled: bool = False,
    ) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.terminal_path = terminal_path
        self.live_enabled = live_enabled
        self._mt5 = None

    def _module(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:
                raise RuntimeError(
                    "MetaTrader5 is not installed. Install the optional 'mt5' dependency."
                ) from exc
            self._mt5 = mt5
        return self._mt5

    def health_check(self) -> bool:
        mt5 = self._module()
        return bool(mt5.terminal_info() is not None and mt5.account_info() is not None)

    def connect(self) -> bool:
        mt5 = self._module()
        kwargs = {}
        if self.terminal_path:
            kwargs["path"] = self.terminal_path
        if self.login is not None:
            kwargs["login"] = self.login
        if self.password is not None:
            kwargs["password"] = self.password
        if self.server:
            kwargs["server"] = self.server
        return bool(mt5.initialize(**kwargs))

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    def submit(self, order: OrderRequest) -> OrderResult:
        if not self.live_enabled:
            return OrderResult(False, None, "LIVE_TRADING_LOCKED")

        mt5 = self._module()
        if not self.health_check():
            return OrderResult(False, None, "MT5_UNHEALTHY")

        symbol = order.instrument
        if not mt5.symbol_select(symbol, True):
            return OrderResult(False, None, "SYMBOL_UNAVAILABLE")

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return OrderResult(False, None, "MARKET_DATA_UNAVAILABLE")

        order_type = mt5.ORDER_TYPE_BUY if order.direction is Direction.LONG else mt5.ORDER_TYPE_SELL
        price = float(tick.ask if order.direction is Direction.LONG else tick.bid)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(order.units),
            "type": order_type,
            "price": price,
            "sl": float(order.stop),
            "tp": float(order.target or 0),
            "deviation": 20,
            "magic": 20261004,
            "comment": order.client_order_id[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": getattr(info, "filling_mode", mt5.ORDER_FILLING_IOC),
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, "MT5_ORDER_SEND_FAILED")

        retcode = int(result.retcode)
        if retcode != int(mt5.TRADE_RETCODE_DONE):
            return OrderResult(False, str(retcode), f"MT5_REJECTED:{retcode}")

        return OrderResult(True, str(result.order or result.deal), "ACCEPTED")
