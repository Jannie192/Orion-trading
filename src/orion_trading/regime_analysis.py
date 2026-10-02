from __future__ import annotations

import pandas as pd

def summarize_by_regime(trades: list[dict]) -> dict:
    if not trades:
        return {}
    df=pd.DataFrame(trades)
    if "regime" not in df or "pnl_r" not in df:
        return {}
    df["pnl_r"]=pd.to_numeric(df["pnl_r"],errors="coerce").fillna(0.0)
    out={}
    for regime,g in df.groupby("regime",dropna=False):
        pnl=g["pnl_r"]
        out[str(regime)]={"trades":int(len(g)),"net_r":float(pnl.sum()),"win_rate_pct":float((pnl>0).mean()*100),"expectancy_r":float(pnl.mean())}
    return out
