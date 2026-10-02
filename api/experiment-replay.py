from __future__ import annotations
import json, os, sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from orion_trading.provider_factory import provider_from_env
from orion_trading.backtest import Backtester, BacktestConfig
from orion_trading.trading_engine import TradingEngine, TradingEngineConfig
from orion_trading.supabase_strategy_store import SupabaseStrategyStore

def _json(h,payload,status=200):
    body=json.dumps(payload,default=str,separators=(",",":")).encode()
    h.send_response(status); h.send_header("Content-Type","application/json; charset=utf-8"); h.send_header("Cache-Control","no-store, max-age=0"); h.send_header("Content-Length",str(len(body))); h.end_headers(); h.wfile.write(body)

def replay(instrument,timeframe,days,risk,stop,reward):
    if instrument not in {"BTCUSDT","ETHUSDT"} or timeframe not in {"M15","H1","H4","D1"}: raise ValueError("UNSUPPORTED_REPLAY_REQUEST")
    days=max(7,min(int(days),365)); end=datetime.now(timezone.utc); start=end-timedelta(days=days)
    os.environ.setdefault("ORION_DATA_PROVIDER","binance"); provider=provider_from_env()
    try: candles=provider.candles(instrument,timeframe,start,end)
    finally:
        close=getattr(provider,"close",None)
        if close: close()
    engine=TradingEngine(config=TradingEngineConfig(risk_per_trade_pct=float(risk),atr_stop_multiple=float(stop),reward_multiple=float(reward)))
    result,events=Backtester(engine=engine,config=BacktestConfig(initial_equity=10000.0,risk_per_trade_pct=float(risk))).run_replay(candles,instrument=instrument)
    return {"mode":"research","live_trading_enabled":False,"instrument":instrument,"timeframe":timeframe,"days":days,"parameters":{"risk_per_trade_pct":float(risk),"atr_stop_multiple":float(stop),"reward_multiple":float(reward)},"initial_equity":result.initial_equity,"final_equity":result.final_equity,"total_return_pct":result.total_return_pct,"max_drawdown_pct":result.max_drawdown_pct,"trades_count":len(result.trades),"replay":events,"replay_bars":len(events)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query); eid=q.get("experiment_id",[None])[0]
            if eid:
                exp=SupabaseStrategyStore().experiment(eid)
                idx=int(q.get("result_index",["0"])[0]); results=exp.get("results") or []
                if idx<0 or idx>=len(results): raise ValueError("RESULT_INDEX_OUT_OF_RANGE")
                r=results[idx]
                payload=replay(exp["instrument"],exp["timeframe"],exp["days"],r["risk_per_trade_pct"],r["atr_stop_multiple"],r["reward_multiple"])
                payload["experiment_id"]=eid; payload["result_index"]=idx; payload["strategy_name"]=exp["strategy_name"]; payload["strategy_version"]=exp["strategy_version"]
            else:
                payload={"mode":"research","live_trading_enabled":False,"error":"experiment_id_required"}
            _json(self,payload)
        except Exception as exc: _json(self,{"mode":"research","live_trading_enabled":False,"error":str(exc)},400)
