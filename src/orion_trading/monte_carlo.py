from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class MonteCarloSummary:
    simulations: int
    trades: int
    median_net_r: float
    p05_net_r: float
    p95_net_r: float
    median_max_drawdown_r: float
    p95_max_drawdown_r: float
    p95_max_losing_streak: int
    negative_finish_pct: float

def _path_stats(pnl: np.ndarray) -> tuple[float,float,int]:
    equity=np.cumsum(pnl)
    dd=equity-np.maximum.accumulate(equity)
    streak=best=0
    for x in pnl:
        streak=streak+1 if x<0 else 0
        best=max(best,streak)
    return float(equity[-1]), float(-dd.min()), best

def monte_carlo(pnl_r, simulations=10000, seed=42) -> MonteCarloSummary:
    pnl=np.asarray(list(pnl_r),dtype=float)
    if len(pnl)==0:
        return MonteCarloSummary(0,0,0,0,0,0,0,0,0)
    rng=np.random.default_rng(seed)
    outcomes=np.empty((simulations,3),dtype=float)
    for i in range(simulations):
        sample=rng.choice(pnl,size=len(pnl),replace=True)
        outcomes[i]=_path_stats(sample)
    return MonteCarloSummary(
        simulations,len(pnl),
        float(np.percentile(outcomes[:,0],50)),
        float(np.percentile(outcomes[:,0],5)),
        float(np.percentile(outcomes[:,0],95)),
        float(np.percentile(outcomes[:,1],50)),
        float(np.percentile(outcomes[:,1],95)),
        int(np.percentile(outcomes[:,2],95)),
        float((outcomes[:,0]<0).mean()*100),
    )
