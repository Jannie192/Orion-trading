from __future__ import annotations
import json, os, html
from http.server import BaseHTTPRequestHandler
import requests

SUPABASE_URL=os.getenv("ORION_SUPABASE_URL") or os.getenv("SUPABASE_URL","")
SUPABASE_KEY=os.getenv("ORION_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY","")

def db(path, params=None, limit=100):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("DASHBOARD_SUPABASE_CONFIGURATION_MISSING")
    p=dict(params or {})
    p.setdefault("limit",str(limit))
    r=requests.get(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path}",headers={
        "apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}",
    },params=p,timeout=12)
    if not r.ok: raise RuntimeError(f"SUPABASE_{r.status_code}: {r.text[:300]}")
    return r.json()

def payload():
    account=db("paper_accounts",{"select":"*","order":"updated_at.desc"})
    orders=db("paper_orders",{"select":"order_id,account_id,instrument,timeframe,direction,units,entry,stop,target,regime,signal_type,detected_at,created_at,status,strategy_id,strategy_name,strategy_version","order":"created_at.desc"})
    trades=db("paper_trades",{"select":"trade_id,order_id,instrument,direction,units,entry,exit,pnl,risk_amount,reason,opened_at,closed_at,regime,signal_type,strategy_id,strategy_name,strategy_version","order":"closed_at.desc"})
    strategies=db("strategy_versions",{"select":"*","order":"updated_at.desc"})
    experiments=db("strategy_experiments",{"select":"experiment_id,strategy_id,strategy_name,strategy_version,instrument,timeframe,days,grid,validation,created_at","order":"created_at.desc"})
    runs=db("research_runs",{"select":"run_id,strategy_name,strategy_version,instrument,timeframe,start_at,end_at,data_rows,data_downloaded,gaps_filled,initial_equity,final_equity,total_return_pct,max_drawdown_pct,trade_count,wins,losses,win_rate_pct,profit_factor,profit_factor_infinite,created_at","order":"created_at.desc"})
    datasets=db("market_data_datasets",{"select":"dataset_id,provider,instrument,timeframe,start_at,end_at,row_count,missing_bars,quality_passed,created_at","order":"created_at.desc"})
    jobs=db("research_jobs",{"select":"job_id,job_type,status,instrument,timeframe,days,progress_pct,progress,stage,error,created_at,started_at,completed_at,updated_at,result","order":"updated_at.desc"})
    return {"account":account,"orders":orders,"trades":trades,"strategies":strategies,"experiments":experiments,"runs":runs,"datasets":datasets,"jobs":jobs,
            "guardrails":{"min_oos_trades":500,"min_oos_win_rate_pct":75,"live_trading_enabled":False}}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body=json.dumps(payload(),default=str,separators=(",",":")).encode()
            status=200
        except Exception as e:
            body=json.dumps({"error":str(e)}).encode(); status=500
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Cache-Control","no-store"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
