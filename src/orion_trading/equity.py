from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def equity_frame(trades: list[dict]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["time","pnl_r","equity_r","drawdown_r"])
    df=pd.DataFrame(trades)
    df["time"]=pd.to_datetime(df["exit_time"],utc=True,errors="coerce")
    df["pnl_r"]=pd.to_numeric(df["pnl_r"],errors="coerce").fillna(0.0)
    df=df.sort_values("time").reset_index(drop=True)
    df["equity_r"]=df["pnl_r"].cumsum()
    df["drawdown_r"]=df["equity_r"]-df["equity_r"].cummax()
    return df[["time","pnl_r","equity_r","drawdown_r"]]

def write_equity_charts(trades:list[dict],directory="reports/research/charts")->list[Path]:
    out=Path(directory); out.mkdir(parents=True,exist_ok=True)
    df=equity_frame(trades)
    paths=[]
    for column,name,ylabel in [("equity_r","equity_curve.png","Equity (R)"),("drawdown_r","drawdown.png","Drawdown (R)")]:
        fig,ax=plt.subplots(figsize=(10,5))
        ax.plot(df["time"],df[column])
        ax.set_title(name.replace(".png","").replace("_"," ").title())
        ax.set_ylabel(ylabel); ax.grid(True,alpha=.2); fig.autofmt_xdate()
        path=out/name; fig.savefig(path,bbox_inches="tight"); plt.close(fig); paths.append(path)
    return paths
