from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .features import calculate_features

@dataclass(frozen=True)
class BacktestConfig:
    risk_r: float = 1.0
    atr_stop_multiple: float = 1.5
    reward_multiple: float = 2.0

@dataclass(frozen=True)
class BacktestSummary:
    trades:int; wins:int; losses:int; net_r:float; win_rate_pct:float; profit_factor:float|None; expectancy_r:float; max_drawdown_r:float

class SimpleOAFSBacktester:
    def __init__(self,config:BacktestConfig|None=None): self.config=config or BacktestConfig()
    def run(self,candles:pd.DataFrame)->tuple[BacktestSummary,pd.DataFrame]:
        x=calculate_features(candles).dropna().copy(); rows=[]
        for i in range(1,len(x)):
            c,p=x.iloc[i],x.iloc[i-1]; long=bool(c.close>c.ema20>c.ema50 and c.roc10>0 and p.close<=p.ema20); short=bool(c.close<c.ema20<c.ema50 and c.roc10<0 and p.close>=p.ema20)
            if not(long or short): continue
            direction=1 if long else -1; entry=float(c.close); dist=float(c.atr14)*self.config.atr_stop_multiple
            if dist<=0: continue
            stop=entry-direction*dist; target=entry+direction*dist*self.config.reward_multiple; pnl=0.0; reason="DATA_END"; exit_i=len(x)-1
            for j in range(i+1,len(x)):
                b=x.iloc[j]
                if direction==1 and b.low<=stop: pnl=-self.config.risk_r; reason="STOP"; exit_i=j; break
                if direction==1 and b.high>=target: pnl=self.config.reward_multiple*self.config.risk_r; reason="TARGET"; exit_i=j; break
                if direction==-1 and b.high>=stop: pnl=-self.config.risk_r; reason="STOP"; exit_i=j; break
                if direction==-1 and b.low<=target: pnl=self.config.reward_multiple*self.config.risk_r; reason="TARGET"; exit_i=j; break
            if reason=="DATA_END": pnl=direction*(float(x.iloc[exit_i].close)-entry)/dist
            rows.append({"entry_time":x.index[i],"exit_time":x.index[exit_i],"direction":"LONG" if direction==1 else "SHORT","entry":entry,"stop":stop,"target":target,"pnl_r":float(pnl),"exit_reason":reason})
        trades=pd.DataFrame(rows)
        if trades.empty:return BacktestSummary(0,0,0,0.0,0.0,None,0.0,0.0),trades
        pnl=trades.pnl_r.astype(float); wins=pnl[pnl>0]; losses=pnl[pnl<0]; eq=pnl.cumsum(); dd=eq-eq.cummax(); pf=float(wins.sum()/abs(losses.sum())) if not losses.empty else None
        return BacktestSummary(len(pnl),len(wins),len(losses),float(pnl.sum()),float((pnl>0).mean()*100),pf,float(pnl.mean()),float(abs(dd.min()))),trades
