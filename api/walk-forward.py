from __future__ import annotations
import os
from datetime import datetime,timedelta,timezone
from orion_trading.provider_factory import provider_from_env
from orion_trading.backtest import Backtester,BacktestConfig
from orion_trading.trading_engine import TradingEngine,TradingEngineConfig

_ALLOWED={"BTCUSDT","ETHUSDT"}; _TFS={"M15","H1","H4","D1"}

def _floats(value,lo,hi):
    out=[]
    for raw in str(value).split(","):
        if raw.strip():
            x=float(raw)
            if lo<=x<=hi: out.append(x)
    if not out: raise ValueError("EMPTY_PARAMETER_GRID")
    return list(dict.fromkeys(out))

def _metrics(candles,instrument,risk,stop,reward):
    engine=TradingEngine(config=TradingEngineConfig(risk_per_trade_pct=risk,atr_stop_multiple=stop,reward_multiple=reward))
    result=Backtester(engine=engine,config=BacktestConfig(initial_equity=10000.0,risk_per_trade_pct=risk)).run(candles,instrument=instrument)
    pf=result.profit_factor
    return {"final_equity":result.final_equity,"total_return_pct":result.total_return_pct,"max_drawdown_pct":result.max_drawdown_pct,
            "trades_count":len(result.trades),"wins":result.wins,"losses":result.losses,"win_rate_pct":result.win_rate_pct,
            "profit_factor":None if pf==float("inf") else pf}

def run(instrument,timeframe,days,risks,stops,rewards,train_bars=None,test_bars=None,step_bars=None):
    if instrument not in _ALLOWED or timeframe not in _TFS: raise ValueError("WALK_FORWARD_PROVIDER_CURRENTLY_SUPPORTS_CRYPTO_ONLY")
    days=max(7,min(int(days),365))
    rv=_floats(risks,.05,2); sv=_floats(stops,.5,4); wv=_floats(rewards,.5,6)
    if len(rv)*len(sv)*len(wv)>100: raise ValueError("EXPERIMENT_GRID_TOO_LARGE_MAX_100_RUNS")
    end=datetime.now(timezone.utc); start=end-timedelta(days=days)
    os.environ.setdefault("ORION_DATA_PROVIDER","binance"); provider=provider_from_env()
    try: candles=provider.candles(instrument,timeframe,start,end)
    finally:
        close=getattr(provider,"close",None)
        if close: close()
    n=len(candles)
    if n<240: raise ValueError("NOT_ENOUGH_CANDLES_FOR_WALK_FORWARD")
    train_n=int(train_bars or max(100,n*.5)); test_n=int(test_bars or max(40,n*.15)); step=int(step_bars or test_n)
    train_n=max(100,min(train_n,n-40)); test_n=max(40,min(test_n,n-train_n)); step=max(20,step)
    folds=[]; offset=0
    while offset+train_n+test_n<=n and len(folds)<8:
        train=candles.iloc[offset:offset+train_n]; test=candles.iloc[offset+train_n:offset+train_n+test_n]
        fold_results=[]
        for risk in rv:
            for stop in sv:
                for reward in wv:
                    tr=_metrics(train,instrument,risk,stop,reward); te=_metrics(test,instrument,risk,stop,reward)
                    fold_results.append({"risk_per_trade_pct":risk,"atr_stop_multiple":stop,"reward_multiple":reward,
                      "train":tr,"test":te,"return_delta_pct":te["total_return_pct"]-tr["total_return_pct"]})
        folds.append({"fold":len(folds)+1,"train_start":str(train.index[0]),"train_end":str(train.index[-1]),
                      "test_start":str(test.index[0]),"test_end":str(test.index[-1]),"train_bars":len(train),"test_bars":len(test),"results":fold_results})
        offset+=step
    if len(folds)<2: raise ValueError("WALK_FORWARD_NEEDS_AT_LEAST_TWO_FOLDS")
    aggregate=[]
    for risk in rv:
      for stop in sv:
       for reward in wv:
        cells=[]
        for f in folds:
          cells.append(next(x for x in f["results"] if x["risk_per_trade_pct"]==risk and x["atr_stop_multiple"]==stop and x["reward_multiple"]==reward))
        tests=[x["test"]["total_return_pct"] for x in cells]
        dds=[x["test"]["max_drawdown_pct"] for x in cells]
        wins=[x["test"]["win_rate_pct"] for x in cells]
        aggregate.append({"risk_per_trade_pct":risk,"atr_stop_multiple":stop,"reward_multiple":reward,
          "folds_positive":sum(x>0 for x in tests),"fold_count":len(tests),
          "positive_fold_pct":sum(x>0 for x in tests)/len(tests)*100,
          "average_test_return_pct":sum(tests)/len(tests),"average_test_drawdown_pct":sum(dds)/len(dds),
          "average_test_win_rate_pct":sum(wins)/len(wins),
          "test_return_spread_pct":max(tests)-min(tests),
          "fold_test_returns":tests})
    return {"mode":"research","live_trading_enabled":False,"instrument":instrument,"timeframe":timeframe,"days":days,
      "validation":{"method":"rolling walk-forward","folds":len(folds),"train_bars":train_n,"test_bars":test_n,"step_bars":step,
        "chronological":True,"no_random_shuffle":True},"count":len(aggregate),"folds":folds,"results":aggregate}
