from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

API_PATH = os.path.join(ROOT, "api", "walk-forward.py")
SPEC = importlib.util.spec_from_file_location("orion_walk_forward_api", API_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8080"))
MAX_BODY = 64 * 1024
PAPER_INTERVAL_SECONDS = int(os.getenv("ORION_PAPER_INTERVAL_SECONDS", "900"))
RESEARCH_BOOTSTRAP = os.getenv("ORION_RESEARCH_BOOTSTRAP", "0").lower() in {"1", "true", "yes"}
RESEARCH_DAYS = int(os.getenv("ORION_RESEARCH_DAYS", "365"))
RESEARCH_TIMEFRAMES = tuple(x.strip().upper() for x in os.getenv("ORION_RESEARCH_TIMEFRAMES", "H1,H4,D1,M15").split(",") if x.strip())
RESEARCH_INSTRUMENTS = tuple(x.strip().upper() for x in os.getenv("ORION_RESEARCH_INSTRUMENTS", "EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD").split(",") if x.strip())
RESEARCH_INTERVAL_SECONDS = int(os.getenv("ORION_RESEARCH_INTERVAL_SECONDS", "8"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _paper_cycle():
    try:
        from orion_trading.paper_candidate_runner import PaperCandidateRunner
        from orion_trading.paper_performance import PaperPerformanceEngine
        from orion_trading.supabase_market_store import SupabaseMarketDataStore
        from orion_trading.supabase_paper_store import SupabasePaperStore
        from orion_trading.supabase_strategy_store import SupabaseStrategyStore
        market = SupabaseMarketDataStore()
        paper = SupabasePaperStore()
        strategies = SupabaseStrategyStore()
        runner = PaperCandidateRunner(market, paper, strategies)
        performance = PaperPerformanceEngine(paper, strategies)
    except Exception as exc:
        print(f"Paper cycle disabled: {exc}", flush=True)
        return
    while True:
        try:
            candidates = runner.candidates()
            print(f"Paper cycle: candidates={len(candidates)}", flush=True)
            for candidate in candidates:
                result = runner.run_candidate(candidate)
                print(f"Paper candidate {result.strategy_id} {result.instrument}/{result.timeframe}: submitted={result.submitted_orders} closed={result.closed_trades}", flush=True)
                report = performance.evaluate_and_promote(candidate)
                print(f"Paper performance {result.strategy_id}: trades={report.trades} expectancy_r={report.expectancy_r:.3f} eligible={report.eligible}", flush=True)
        except Exception as exc:
            print(f"Paper cycle error: {exc}", flush=True)
        time.sleep(PAPER_INTERVAL_SECONDS)


def _research_bootstrap():
    if not RESEARCH_BOOTSTRAP:
        return
    try:
        from orion_trading.dataset_manager import DatasetManager
        from orion_trading.research_cycle import ResearchCycle
        from orion_trading.strategy_experiments import StrategyExperimenter
        from orion_trading.supabase_market_store import SupabaseMarketDataStore
        from orion_trading.twelve_data_provider import YahooFXProvider
        provider = YahooFXProvider()
        store = SupabaseMarketDataStore()
        manager = DatasetManager(store, provider, "yahoo", fetch_limit=10000)
        cycle = ResearchCycle(manager, result_store=store, experimenter=StrategyExperimenter(max_variants=27), experiment_store=store, experiment_grids={"*": {"risk_per_trade_pct": (0.25, 0.5, 0.75), "atr_stop_multiple": (1.0, 1.5, 2.0), "reward_multiple": (1.5, 2.0, 3.0)}})
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=RESEARCH_DAYS)
        print(f"Research bootstrap starting: instruments={len(RESEARCH_INSTRUMENTS)} timeframes={RESEARCH_TIMEFRAMES} days={RESEARCH_DAYS} provider=yahoo", flush=True)
        for timeframe in RESEARCH_TIMEFRAMES:
            for instrument in RESEARCH_INSTRUMENTS:
                try:
                    result = cycle.run((instrument,), (timeframe,), start, end)[0]
                    print(f"Research complete {instrument}/{timeframe}: rows={result.data_rows} downloaded={result.data_downloaded} approval={result.approval_status} candidate={result.paper_candidate_id}", flush=True)
                except Exception as exc:
                    print(f"Research failed {instrument}/{timeframe}: {exc}", flush=True)
                time.sleep(RESEARCH_INTERVAL_SECONDS)
        print("Research bootstrap finished", flush=True)
    except Exception as exc:
        print(f"Research bootstrap disabled/failed: {exc}", flush=True)


def _json_response(handler, status, payload):
    body = json.dumps(payload, default=str, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Access-Control-Allow-Origin", os.getenv("ORION_WORKER_CORS_ORIGIN", "*"))
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-Orion-Worker-Key")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _authorized(handler):
    expected = os.getenv("ORION_TRIGGER_KEY")
    return not expected or handler.headers.get("X-Orion-Worker-Key") == expected


def _supabase_request(method, path, **kwargs):
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    worker_key = os.getenv("ORION_WORKER_KEY", "")
    if not url or not key or not worker_key:
        raise RuntimeError("WORKER_SUPABASE_CONFIGURATION_MISSING")
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "X-Orion-Worker-Key": worker_key, "Content-Type": "application/json", **kwargs.pop("headers", {})}
    response = requests.request(method, f"{url}/rest/v1/{path}", headers=headers, timeout=15, **kwargs)
    if not response.ok:
        raise RuntimeError(f"Supabase request failed ({response.status_code}): {response.text[:500]}")
    return response.json() if response.content else []


def _update_job(job_id, patch):
    patch = {**patch, "updated_at": _now()}
    rows = _supabase_request("PATCH", f"research_jobs?job_id=eq.{job_id}", json=patch, headers={"Prefer": "return=representation"})
    if not rows:
        raise RuntimeError("RESEARCH_JOB_NOT_FOUND")
    return rows[0]


def _claim_next_job():
    rows = _supabase_request("GET", "research_jobs?select=*&status=eq.QUEUED&order=created_at.asc&limit=1")
    if not rows:
        return None
    job = rows[0]
    claimed = _supabase_request("PATCH", f"research_jobs?job_id=eq.{job['job_id']}&status=eq.QUEUED", json={"status": "RUNNING", "progress_pct": 1, "started_at": _now(), "updated_at": _now()}, headers={"Prefer": "return=representation"})
    return claimed[0] if claimed else None


def _poll_queue():
    while True:
        try:
            job = _claim_next_job()
            if job:
                payload = job.get("request") or job.get("grid") or {}
                print(f"Claimed research job {job['job_id']}", flush=True)
                _run_job(job["job_id"], payload)
            else:
                time.sleep(3)
        except Exception as exc:
            print(f"Research queue poll error: {exc}", flush=True)
            time.sleep(5)


def _run_job(job_id, payload):
    try:
        _update_job(job_id, {"status": "RUNNING", "progress_pct": 5, "started_at": _now()})
        _update_job(job_id, {"progress_pct": 15})
        result = MODULE.run(str(payload.get("instrument", "BTCUSDT")).upper(), str(payload.get("timeframe", "H1")).upper(), int(payload.get("days", 90)), str(payload.get("risks", "0.25,0.5,0.75")), str(payload.get("stops", "1,1.5,2")), str(payload.get("rewards", "1.5,2,3")), train_bars=payload.get("train_bars"), test_bars=payload.get("test_bars"), step_bars=payload.get("step_bars"), max_folds=payload.get("max_folds", 8))
        _update_job(job_id, {"status": "COMPLETED", "progress_pct": 100, "result": {**result, "worker": "railway", "stage": "COMPLETED"}, "completed_at": _now(), "error": None})
    except Exception as exc:
        try:
            _update_job(job_id, {"status": "FAILED", "progress_pct": 100, "error": str(exc), "completed_at": _now()})
        except Exception as update_exc:
            print(f"Failed to persist job error: {update_exc}", flush=True)
        print(f"Research job {job_id} failed: {exc}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)
    def do_OPTIONS(self):
        _json_response(self, 204, {})
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return _json_response(self, 200, {"ok": True, "service": "orion-research-worker", "live_trading_enabled": False, "job_mode": "asynchronous", "paper_cycle_enabled": True, "research_bootstrap_enabled": RESEARCH_BOOTSTRAP})
        return _json_response(self, 404, {"error": "NOT_FOUND"})
    def do_POST(self):
        if not _authorized(self):
            return _json_response(self, 401, {"error": "UNAUTHORIZED"})
        path = urlparse(self.path).path
        if path != "/run-job":
            return _json_response(self, 404, {"error": "NOT_FOUND"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY:
                return _json_response(self, 413, {"error": "REQUEST_TOO_LARGE"})
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8"))
            job_id = str(body.get("job_id", ""))
            payload = body.get("request") if isinstance(body.get("request"), dict) else {}
            if not job_id:
                raise ValueError("JOB_ID_REQUIRED")
            thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
            thread.start()
            _json_response(self, 202, {"mode": "research", "live_trading_enabled": False, "worker": "railway", "job_id": job_id, "status": "STARTED"})
        except Exception as exc:
            _json_response(self, 400, {"mode": "research", "live_trading_enabled": False, "worker": "railway", "error": str(exc)})


if __name__ == "__main__":
    print(f"ORION research worker listening on {HOST}:{PORT}", flush=True)
    threading.Thread(target=_poll_queue, daemon=True).start()
    threading.Thread(target=_paper_cycle, daemon=True).start()
    threading.Thread(target=_research_bootstrap, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
