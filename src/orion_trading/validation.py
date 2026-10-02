from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class Split:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp

def walk_forward_splits(start, end, train_days=180, test_days=60, step_days=60):
    start=pd.Timestamp(start,tz="UTC"); end=pd.Timestamp(end,tz="UTC")
    splits=[]; cursor=start
    i=1
    while cursor + pd.Timedelta(days=train_days+test_days) <= end:
        train_end=cursor+pd.Timedelta(days=train_days)
        test_end=train_end+pd.Timedelta(days=test_days)
        splits.append((Split(f"train_{i}",cursor,train_end),Split(f"test_{i}",train_end,test_end)))
        cursor += pd.Timedelta(days=step_days); i+=1
    return splits

def equity_stats(pnl):
    s=pd.Series(pnl,dtype=float).fillna(0)
    if s.empty:
        return {"net_r":0.0,"max_drawdown_r":0.0,"trades":0,"win_rate_pct":0.0}
    eq=s.cumsum(); dd=eq-eq.cummax()
    return {"net_r":float(s.sum()),"max_drawdown_r":float(-dd.min()),"trades":int(len(s)),"win_rate_pct":float((s>0).mean()*100)}
