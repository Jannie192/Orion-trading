from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class PortfolioResult:
    trades: int
    wins: int
    losses: int
    net_r: float
    win_rate_pct: float
    profit_factor: float
    expectancy_r: float
    max_drawdown_r: float

def combine_trade_logs(results: list[dict]) -> pd.DataFrame:
    rows=[]
    for result in results:
        for trade in result.get("trade_log", []):
            row=dict(trade)
            row["instrument"]=result.get("instrument", row.get("instrument"))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    df=pd.DataFrame(rows)
    if "exit_time" in df:
        df["exit_time"]=pd.to_datetime(df["exit_time"], utc=True, errors="coerce")
    return df.sort_values("exit_time", kind="stable").reset_index(drop=True)

def summarize_portfolio(results: list[dict]) -> PortfolioResult:
    df=combine_trade_logs(results)
    if df.empty:
        return PortfolioResult(0,0,0,0.0,0.0,0.0,0.0,0.0)
    pnl=pd.to_numeric(df["pnl_r"], errors="coerce").fillna(0.0)
    wins=int((pnl>0).sum()); losses=int((pnl<0).sum())
    net=float(pnl.sum())
    gross_profit=float(pnl[pnl>0].sum())
    gross_loss=float(-pnl[pnl<0].sum())
    equity=pnl.cumsum()
    dd=equity-equity.cummax()
    return PortfolioResult(
        len(pnl), wins, losses, net,
        wins/len(pnl)*100,
        gross_profit/gross_loss if gross_loss else float("inf"),
        net/len(pnl),
        float(-dd.min()) if len(dd) else 0.0,
    )
