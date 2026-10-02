from __future__ import annotations
import json, sys
from collections import defaultdict
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from orion_trading.supabase_strategy_store import SupabaseStrategyStore

def avg(v): return sum(v)/len(v) if v else 0.0

def analyze(experiments, iterations):
    groups=defaultdict(list)
    for e in experiments:
        results=e.get("results") or []
        if not results: continue
        tests=[float((r.get("test") or {}).get("total_return_pct",0)) for r in results]
        dds=[float((r.get("test") or {}).get("max_drawdown_pct",0)) for r in results]
        both=sum(float((r.get("train") or {}).get("total_return_pct",0))>0 and x>0 for r,x in zip(results,tests))
        groups[(e.get("instrument"),e.get("timeframe"))].append({
            "experiment_id":e.get("experiment_id"),"strategy_name":e.get("strategy_name"),
            "strategy_version":e.get("strategy_version"),"created_at":e.get("created_at"),
            "runs":len(results),"avg_test_return_pct":avg(tests),"avg_test_drawdown_pct":avg(dds),
            "positive_both_pct":both/len(results)*100,"max_test_return_pct":max(tests)
        })
    stability=[]
    for (instrument,timeframe),rows in groups.items():
        returns=[x["avg_test_return_pct"] for x in rows]
        positive=sum(x>0 for x in returns)
        stability.append({"instrument":instrument,"timeframe":timeframe,"experiments":len(rows),
          "positive_experiment_pct":positive/len(rows)*100,"average_experiment_test_return_pct":avg(returns),
          "test_return_spread_pct":(max(returns)-min(returns)) if returns else 0,
          "latest_experiment_id":rows[0]["experiment_id"],
          "latest_avg_test_return_pct":rows[0]["avg_test_return_pct"]})
    cross=[]
    by_strategy=defaultdict(list)
    for e in experiments:
        by_strategy[(e.get("strategy_name"),e.get("strategy_version"))].append(e)
    for (name,version),rows in by_strategy.items():
        contexts={(e.get("instrument"),e.get("timeframe")) for e in rows}
        if len(contexts)>=2:
            cross.append({"strategy_name":name,"strategy_version":version,
              "contexts":len(contexts),"context_list":[f"{a}/{t}" for a,t in sorted(contexts)],
              "average_context_test_return_pct":avg([avg([float((r.get("test") or {}).get("total_return_pct",0)) for r in (e.get("results") or [])]) for e in rows])})
    generations=[]
    for it in iterations:
        generations.append({"generation":it.get("generation"),"status":it.get("status"),
          "instrument":it.get("instrument"),"timeframe":it.get("timeframe"),
          "parent_experiment_id":it.get("parent_experiment_id"),"child_experiment_id":it.get("child_experiment_id")})
    facts=[]
    if stability:
        stable=sum(1 for x in stability if x["positive_experiment_pct"]>=50)
        facts.append(f"{stable} of {len(stability)} instrument/timeframe contexts have at least half of recorded experiments with positive average test return.")
    if cross:
        facts.append(f"{len(cross)} strategy/version groups have been tested across at least two instrument/timeframe contexts.")
    if generations:
        completed=sum(1 for x in generations if x["status"]=="COMPLETED")
        facts.append(f"{completed} recorded research iterations are completed out of {len(generations)}.")
    facts.append("Cross-experiment observations are descriptive; they do not establish future profitability or select a strategy automatically.")
    return {"contexts":stability,"cross_context_strategies":cross,"lineage":generations[:20],"facts":facts,
      "experiments_analyzed":len(experiments)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query); limit=max(1,min(int(q.get("limit",["100"])[0]),100))
            store=SupabaseStrategyStore()
            data=analyze(store.experiments(limit),store.iterations(limit))
            data.update({"mode":"research","live_trading_enabled":False})
            body=json.dumps(data,separators=(",",":")).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        except Exception as exc:
            body=json.dumps({"error":str(exc),"mode":"research","live_trading_enabled":False}).encode()
            self.send_response(400); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
