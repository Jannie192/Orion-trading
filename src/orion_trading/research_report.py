from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

def build_research_report(results: list[dict]) -> dict:
    rows=[]
    for result in results:
        summary={k:v for k,v in result.items() if k not in {"trade_log","rejections"}}
        rows.append(summary)
    trades=[]
    rejects=[]
    for result in results:
        for t in result.get("trade_log", []):
            x=dict(t); x["instrument"]=result.get("instrument"); trades.append(x)
        for x in result.get("rejections", []):
            y=dict(x); y["instrument"]=result.get("instrument"); rejects.append(y)
    trade_df=pd.DataFrame(trades)
    module={}
    if not trade_df.empty and "opportunity_types" in trade_df:
        exploded=trade_df.explode("opportunity_types")
        for name,g in exploded.groupby("opportunity_types"):
            pnl=pd.to_numeric(g.get("pnl_r"),errors="coerce").fillna(0)
            module[str(name)]={"trades":int(len(g)),"net_r":float(pnl.sum()),"win_rate_pct":float((pnl>0).mean()*100)}
    pair={str(x.get("instrument")):x for x in rows}
    return {"pairs":pair,"opportunity_types":module,"trade_count":len(trades),"rejection_count":len(rejects)}

def write_research_report(results:list[dict],directory="reports/research")->Path:
    out=Path(directory); out.mkdir(parents=True,exist_ok=True)
    report=build_research_report(results)
    path=out/"report.json"; path.write_text(json.dumps(report,indent=2,default=str))
    return path
