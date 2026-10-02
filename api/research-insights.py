from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_strategy_store import SupabaseStrategyStore

def _json(handler, payload, status=200):
    body=json.dumps(payload,separators=(",",":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Content-Length",str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def analyze(experiment):
    results=experiment.get("results") or []
    if not results:
        raise ValueError("EXPERIMENT_HAS_NO_RESULTS")
    train=[float(r.get("train",{}).get("total_return_pct",0)) for r in results]
    test=[float(r.get("test",{}).get("total_return_pct",0)) for r in results]
    dd=[float(r.get("test",{}).get("max_drawdown_pct",0)) for r in results]
    wins=[float(r.get("test",{}).get("win_rate_pct",0)) for r in results]
    deltas=[float(r.get("return_delta_pct",0)) for r in results]
    positive_test=sum(x>0 for x in test)
    positive_both=sum(a>0 and b>0 for a,b in zip(train,test))
    stable=sum(a>=b for a,b in zip(train,test))
    def avg(xs): return sum(xs)/len(xs)
    idx=max(range(len(results)), key=lambda i: test[i])
    observed={
        "runs":len(results),
        "positive_test_runs":positive_test,
        "positive_test_pct":positive_test/len(results)*100,
        "positive_train_and_test_runs":positive_both,
        "positive_train_and_test_pct":positive_both/len(results)*100,
        "average_train_return_pct":avg(train),
        "average_test_return_pct":avg(test),
        "average_test_drawdown_pct":avg(dd),
        "average_test_win_rate_pct":avg(wins),
        "average_return_delta_pct":avg(deltas),
        "max_test_return_pct":max(test),
        "min_test_return_pct":min(test),
        "max_test_drawdown_pct":max(dd),
        "min_test_drawdown_pct":min(dd),
        "highest_test_return_run":idx+1,
        "highest_test_return_parameters": {
            "risk_per_trade_pct":results[idx].get("risk_per_trade_pct"),
            "atr_stop_multiple":results[idx].get("atr_stop_multiple"),
            "reward_multiple":results[idx].get("reward_multiple"),
        },
    }
    facts=[
      f"{positive_test} of {len(results)} configurations had positive test return.",
      f"{positive_both} of {len(results)} configurations were positive in both train and test.",
      f"Average test return was {observed['average_test_return_pct']:.2f}%, versus {observed['average_train_return_pct']:.2f}% on train.",
      f"Average test drawdown was {observed['average_test_drawdown_pct']:.2f}%.",
      f"Average test win rate was {observed['average_test_win_rate_pct']:.1f}%.",
      f"The largest observed test return was {observed['max_test_return_pct']:.2f}% in run {idx+1}.",
    ]
    return observed, facts

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query)
            eid=str(q.get("experiment_id",[""])[0])
            if not eid: raise ValueError("EXPERIMENT_ID_REQUIRED")
            store=SupabaseStrategyStore()
            exp=store.experiment(eid)
            observed,facts=analyze(exp)
            payload={
              "experiment_id":eid,
              "strategy_name":exp["strategy_name"],
              "strategy_version":exp["strategy_version"],
              "instrument":exp["instrument"],
              "timeframe":exp["timeframe"],
              "observed":observed,
              "facts":facts,
              "mode":"research",
              "live_trading_enabled":False
            }
            return _json(self,payload)
        except Exception as exc:
            return _json(self,{"error":str(exc),"mode":"research","live_trading_enabled":False},400)

    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length","0"))
            body=json.loads(self.rfile.read(length) or b"{}")
            eid=str(body.get("experiment_id",""))
            if not eid: raise ValueError("EXPERIMENT_ID_REQUIRED")
            store=SupabaseStrategyStore()
            exp=store.experiment(eid)
            observed,facts=analyze(exp)
            summary=f"{observed['positive_test_runs']}/{observed['runs']} configurations positive on unseen test data; average test return {observed['average_test_return_pct']:.2f}%; average test drawdown {observed['average_test_drawdown_pct']:.2f}%."
            row=store.create_insight({
              "experiment_id":eid,
              "strategy_name":exp["strategy_name"],
              "strategy_version":exp["strategy_version"],
              "instrument":exp["instrument"],
              "timeframe":exp["timeframe"],
              "summary":summary,
              "facts":{"observed":observed,"facts":facts},
            })
            return _json(self,{"insight":row,"mode":"research","live_trading_enabled":False})
        except Exception as exc:
            return _json(self,{"error":str(exc),"mode":"research","live_trading_enabled":False},400)
