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

def _avg(values):
    return sum(values) / len(values) if values else 0.0

def _group_metric(results, key):
    groups = {}
    for row in results:
        try:
            value = float(row.get(key))
            groups.setdefault(value, []).append(float((row.get("test") or {}).get("total_return_pct", 0)))
        except (TypeError, ValueError):
            pass
    return {str(k): _avg(v) for k, v in sorted(groups.items())}

def analyze(experiment):
    results = experiment.get("results") or []
    if not results:
        raise ValueError("EXPERIMENT_HAS_NO_RESULTS")
    train=[float((r.get("train") or {}).get("total_return_pct",0)) for r in results]
    test=[float((r.get("test") or {}).get("total_return_pct",0)) for r in results]
    dd=[float((r.get("test") or {}).get("max_drawdown_pct",0)) for r in results]
    wins=[float((r.get("test") or {}).get("win_rate_pct",0)) for r in results]
    deltas=[float(r.get("return_delta_pct",0)) for r in results]
    positive_test=sum(x>0 for x in test)
    positive_both=sum(a>0 and b>0 for a,b in zip(train,test))
    idx=max(range(len(results)),key=lambda i:test[i])
    sensitivity={
      "risk_test_return_by_value":_group_metric(results,"risk_per_trade_pct"),
      "stop_test_return_by_value":_group_metric(results,"atr_stop_multiple"),
      "reward_test_return_by_value":_group_metric(results,"reward_multiple"),
    }
    sensitivity_facts=[]
    for key,label in [("risk_per_trade_pct","risk"),("atr_stop_multiple","ATR stop"),("reward_multiple","reward")]:
        groups={}
        for row in results:
            try:
                groups.setdefault(float(row.get(key)),[]).append(float((row.get("test") or {}).get("total_return_pct",0)))
            except (TypeError,ValueError):
                pass
        if len(groups)>=2:
            means={k:_avg(v) for k,v in groups.items()}
            lo=min(means,key=means.get); hi=max(means,key=means.get)
            sensitivity_facts.append(f"{label} grid test-return averages ranged from {means[lo]:.2f}% at {lo:g} to {means[hi]:.2f}% at {hi:g}.")
    negative_delta_pct=sum(x<0 for x in deltas)/len(deltas)*100
    spread=max(test)-min(test)
    observed={
      "runs":len(results),"positive_test_runs":positive_test,"positive_test_pct":positive_test/len(results)*100,
      "positive_train_and_test_runs":positive_both,"positive_train_and_test_pct":positive_both/len(results)*100,
      "average_train_return_pct":_avg(train),"average_test_return_pct":_avg(test),
      "average_test_drawdown_pct":_avg(dd),"average_test_win_rate_pct":_avg(wins),
      "average_return_delta_pct":_avg(deltas),"negative_return_delta_pct":negative_delta_pct,
      "test_return_spread_pct":spread,"max_test_return_pct":max(test),"min_test_return_pct":min(test),
      "max_test_drawdown_pct":max(dd),"min_test_drawdown_pct":min(dd),
      "highest_test_return_run":idx+1,
      "highest_test_return_parameters":{
        "risk_per_trade_pct":results[idx].get("risk_per_trade_pct"),
        "atr_stop_multiple":results[idx].get("atr_stop_multiple"),
        "reward_multiple":results[idx].get("reward_multiple")},
      "sensitivity":sensitivity}
    facts=[
      f"{positive_test} of {len(results)} configurations had positive test return.",
      f"{positive_both} of {len(results)} configurations were positive in both train and test.",
      f"Average test return was {observed['average_test_return_pct']:.2f}%, versus {observed['average_train_return_pct']:.2f}% on train.",
      f"Average test drawdown was {observed['average_test_drawdown_pct']:.2f}%.",
      f"Average test win rate was {observed['average_test_win_rate_pct']:.1f}%.",
      f"{negative_delta_pct:.1f}% of configurations had test return below train return.",
      f"Observed test-return spread across the grid was {spread:.2f} percentage points.",
      f"The largest observed test return was {observed['max_test_return_pct']:.2f}% in run {idx+1}.",
      *sensitivity_facts]
    diagnostics={
      "parameter_sensitivity":sensitivity,
      "notes":[
        "Sensitivity is descriptive and uses only this experiment's recorded test results.",
        "A large train/test gap or concentrated positive results can indicate instability or overfitting risk, but does not prove future behavior.",
        "Cross-asset and cross-timeframe stability requires additional experiments; it is not inferred from one run."]}
    return observed,facts,diagnostics

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query)
            eid=str(q.get("experiment_id",[""])[0])
            if not eid: raise ValueError("EXPERIMENT_ID_REQUIRED")
            store=SupabaseStrategyStore()
            exp=store.experiment(eid)
            observed,facts,diagnostics=analyze(exp)
            payload={
              "experiment_id":eid,
              "strategy_name":exp["strategy_name"],
              "strategy_version":exp["strategy_version"],
              "instrument":exp["instrument"],
              "timeframe":exp["timeframe"],
              "observed":observed,
              "facts":facts,
              "diagnostics":diagnostics,
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
              "facts":{"observed":observed,"facts":facts,"diagnostics":diagnostics},
            })
            return _json(self,{"insight":row,"mode":"research","live_trading_enabled":False})
        except Exception as exc:
            return _json(self,{"error":str(exc),"mode":"research","live_trading_enabled":False},400)
