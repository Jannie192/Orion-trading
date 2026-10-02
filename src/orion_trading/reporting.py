from __future__ import annotations
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import pandas as pd

@dataclass(frozen=True)
class PerformanceReport:
    trades: int
    net_r: float
    win_rate_pct: float
    profit_factor: float | None
    expectancy_r: float
    max_drawdown_r: float
    best_trade_r: float
    worst_trade_r: float

def performance_report(trades: pd.DataFrame) -> PerformanceReport:
    if trades.empty: return PerformanceReport(0,0.0,0.0,None,0.0,0.0,0.0,0.0)
    pnl=pd.to_numeric(trades["pnl_r"],errors="coerce").dropna(); wins=pnl[pnl>0]; losses=pnl[pnl<0]
    equity=pnl.cumsum(); dd=equity-equity.cummax(); pf=float(wins.sum()/abs(losses.sum())) if not losses.empty else None
    return PerformanceReport(len(pnl),float(pnl.sum()),float((pnl>0).mean()*100),pf,float(pnl.mean()),float(abs(dd.min())),float(pnl.max()),float(pnl.min()))

def write_backtest_report(summary: object,trades: pd.DataFrame,directory: str="reports") -> dict[str,str]:
    out=Path(directory); out.mkdir(parents=True,exist_ok=True); sp=out/"summary.json"; tp=out/"trades.csv"; ep=out/"equity.csv"
    sp.write_text(json.dumps(asdict(summary) if hasattr(summary,"__dataclass_fields__") else asdict(performance_report(trades)),indent=2),encoding="utf-8")
    trades.to_csv(tp,index=False); equity=trades[["entry_time","pnl_r"]].copy() if not trades.empty else pd.DataFrame(columns=["entry_time","pnl_r"])
    if not equity.empty: equity["equity_r"]=equity["pnl_r"].cumsum(); equity["drawdown_r"]=equity["equity_r"]-equity["equity_r"].cummax()
    equity.to_csv(ep,index=False); return {"summary":str(sp),"trades":str(tp),"equity":str(ep)}

def write_json(report: PerformanceReport,path: str|Path)->None: Path(path).write_text(json.dumps(asdict(report),indent=2),encoding="utf-8")
