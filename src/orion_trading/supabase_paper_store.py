from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests


class SupabasePaperStore:
    """Small REST-backed persistence layer for ORION paper trading.

    The service-role key is server-only. RLS remains enabled on the tables;
    this adapter is intended for trusted Vercel/Python server functions.
    """

    def __init__(self, url: str | None = None, key: str | None = None, account_id: str = "orion-default") -> None:
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.account_id = account_id
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for persistent paper trading")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> list[dict[str, Any]]:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        response = requests.request(method, f"{self.url}/rest/v1/{path}", headers=headers, timeout=15, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Supabase request failed ({response.status_code}): {response.text[:500]}")
        return response.json() if response.content else []

    def account(self) -> dict[str, Any]:
        rows = self._request("GET", f"paper_accounts?account_id=eq.{self.account_id}&select=*")
        if rows:
            return rows[0]
        rows = self._request(
            "POST",
            "paper_accounts",
            json={"account_id": self.account_id, "initial_equity": 10000},
            headers={**self._headers, "Prefer": "return=representation"},
        )
        return rows[0]

    def open_orders(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"paper_orders?account_id=eq.{self.account_id}&status=eq.open&select=*&order=created_at.desc"
        )

    def closed_trades(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"paper_trades?account_id=eq.{self.account_id}&select=*&order=closed_at.desc"
        )

    def has_order(self, order_id: str) -> bool:
        rows = self._request("GET", f"paper_orders?order_id=eq.{order_id}&select=order_id")
        return bool(rows)

    def create_order(self, order: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "order_id": order["order_id"],
            "account_id": self.account_id,
            "instrument": order["instrument"],
            "timeframe": order["timeframe"],
            "direction": order["direction"],
            "units": order["units"],
            "entry": order["entry"],
            "stop": order["stop"],
            "target": order["target"],
            "regime": order.get("regime"),
            "signal_type": order.get("signal_type"),
            "detected_at": order["detected_at"],
            "status": "open",
            "strategy_id": order.get("strategy_id"),
            "strategy_name": order.get("strategy_name"),
            "strategy_version": order.get("strategy_version"),
            "source_experiment_id": order.get("source_experiment_id"),
        }
        rows = self._request(
            "POST",
            "paper_orders",
            json=payload,
            headers={**self._headers, "Prefer": "return=representation"},
        )
        return rows[0]

    def mark_bar(self, instrument: str, high: float, low: float, close: float, at: datetime) -> list[dict[str, Any]]:
        """Close persistent paper orders when their stop or target is touched."""
        closed: list[dict[str, Any]] = []
        for order in self.open_orders():
            if order.get("instrument") != instrument:
                continue
            direction = order["direction"]
            exit_price = None
            reason = None
            if direction == "long":
                if low <= float(order["stop"]):
                    exit_price, reason = float(order["stop"]), "stop"
                elif high >= float(order["target"]):
                    exit_price, reason = float(order["target"]), "target"
            else:
                if high >= float(order["stop"]):
                    exit_price, reason = float(order["stop"]), "stop"
                elif low <= float(order["target"]):
                    exit_price, reason = float(order["target"]), "target"
            if reason is None:
                continue
            pnl = (exit_price - float(order["entry"])) * float(order["units"])
            if direction == "short":
                pnl = -pnl
            trade = {
                "order_id": order["order_id"],
                "account_id": self.account_id,
                "instrument": instrument,
                "direction": direction,
                "units": order["units"],
                "entry": order["entry"],
                "exit": exit_price,
                "pnl": pnl,
                "risk_amount": abs(float(order["entry"]) - float(order["stop"])) * float(order["units"]),
                "reason": reason,
                "opened_at": order["detected_at"],
                "closed_at": at.isoformat(),
                "regime": order.get("regime"),
                "signal_type": order.get("signal_type"),
                "strategy_id": order.get("strategy_id"),
                "strategy_name": order.get("strategy_name"),
                "strategy_version": order.get("strategy_version"),
                "source_experiment_id": order.get("source_experiment_id"),
            }
            self._request("POST", "paper_trades", json=trade,
                headers={**self._headers, "Prefer": "return=representation"})
            self._request("PATCH", f"paper_orders?order_id=eq.{order['order_id']}",
                json={"status": "closed"},
                headers={**self._headers, "Prefer": "return=representation"})
            closed.append(trade)
        return closed

    def snapshot(self) -> dict[str, Any]:
        account = self.account()
        orders = self.open_orders()
        trades = self.closed_trades()
        initial = float(account["initial_equity"])
        realized = sum(float(t["pnl"]) for t in trades)
        equity = initial + realized
        wins = sum(1 for t in trades if float(t["pnl"]) > 0)
        losses = sum(1 for t in trades if float(t["pnl"]) < 0)
        gross_profit = sum(float(t["pnl"]) for t in trades if float(t["pnl"]) > 0)
        gross_loss = abs(sum(float(t["pnl"]) for t in trades if float(t["pnl"]) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss else None
        r_values = [
            float(t["pnl"]) / float(t["risk_amount"])
            for t in trades
            if float(t.get("risk_amount") or 0) > 0
        ]
        average_r = sum(r_values) / len(r_values) if r_values else 0.0
        expectancy_r = average_r
        equity_curve = [initial]
        for trade in reversed(trades):
            equity_curve.append(equity_curve[-1] + float(trade["pnl"]))
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            if peak > peak:
                peak = value
            if peak > 0:
                max_dd = max(max_dd, (peak - value) / peak * 100)
        max_losses = 0
        current_losses = 0
        for trade in reversed(trades):
            if float(trade["pnl"]) < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        return {
            "mode": "paper",
            "live_trading_enabled": False,
            "persistence": "supabase",
            "account": {
                "initial_equity": initial,
                "equity": equity,
                "open_orders": len(orders),
                "closed_trades": len(trades),
                "realized_pnl": realized,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "performance": {
                "trades": len(trades),
                "wins": wins,
                "losses": losses,
                "win_rate_pct": (wins / len(trades) * 100) if trades else 0.0,
                "net_pnl": realized,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": profit_factor,
                "expectancy_r": expectancy_r,
                "average_r": average_r,
                "max_consecutive_losses": max_losses,
                "max_drawdown_pct": max_dd,
            },
            "open_positions": orders,
        }
