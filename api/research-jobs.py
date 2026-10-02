from __future__ import annotations

import json
import os
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_strategy_store import SupabaseStrategyStore

WORKER_URL = os.getenv("ORION_RESEARCH_WORKER_URL", "https://orion-research-worker-production.up.railway.app").rstrip("/")


def _json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 64 * 1024:
        raise ValueError("REQUEST_TOO_LARGE")
    return json.loads(handler.rfile.read(length) or b"{}")


def _trigger_worker(job_id: str, request_payload: dict) -> None:
    body = json.dumps({"job_id": job_id, "request": request_payload}, separators=(",", ":")).encode()
    req = urllib.request.Request(
        WORKER_URL + "/run-job",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"WORKER_TRIGGER_HTTP_{response.status}")
    except Exception as exc:
        try:
            SupabaseStrategyStore().update_research_job(job_id, {
                "status": "FAILED",
                "error": f"WORKER_TRIGGER_FAILED: {exc}",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            job_id = parse_qs(urlparse(self.path).query).get("job_id", [""])[0]
            if not job_id:
                raise ValueError("JOB_ID_REQUIRED")
            job = SupabaseStrategyStore().research_job(job_id)
            _json(self, {"mode": "research", "live_trading_enabled": False, "job": job})
        except Exception as exc:
            _json(self, {"error": str(exc), "mode": "research", "live_trading_enabled": False}, 404)

    def do_POST(self):
        try:
            body = _read_json(self)
            if body.get("action") == "update":
                job_id = str(body.get("job_id", ""))
                if not job_id:
                    raise ValueError("JOB_ID_REQUIRED")
                allowed = {"status", "progress", "stage", "result", "error", "started_at", "completed_at", "updated_at"}
                patch = {k: body[k] for k in allowed if k in body}
                job = SupabaseStrategyStore().update_research_job(job_id, patch)
                return _json(self, {"mode": "research", "live_trading_enabled": False, "job": job})
            request_payload = body.get("request") if isinstance(body.get("request"), dict) else body
            instrument = str(request_payload.get("instrument", "BTCUSDT")).upper()
            timeframe = str(request_payload.get("timeframe", "H1")).upper()
            days = max(7, min(int(request_payload.get("days", 90)), 365))
            job_type = str(body.get("job_type", "WALK_FORWARD")).upper()
            if job_type != "WALK_FORWARD":
                raise ValueError("UNSUPPORTED_RESEARCH_JOB_TYPE")

            request_payload = {
                "instrument": instrument,
                "timeframe": timeframe,
                "days": days,
                "risks": str(request_payload.get("risks", "0.25,0.5,0.75")),
                "stops": str(request_payload.get("stops", "1,1.5,2")),
                "rewards": str(request_payload.get("rewards", "1.5,2,3")),
                "train_bars": request_payload.get("train_bars"),
                "test_bars": request_payload.get("test_bars"),
                "step_bars": request_payload.get("step_bars"),
                "max_folds": request_payload.get("max_folds", 8),
            }

            store = SupabaseStrategyStore()
            job = store.create_research_job({
                "job_type": "WALK_FORWARD",
                "status": "QUEUED",
                "request": request_payload,
                "progress": 0,
                "stage": "QUEUED",
            })

            threading.Thread(target=_trigger_worker, args=(job["job_id"], request_payload), daemon=True).start()
            _json(self, {"mode": "research", "live_trading_enabled": False, "job": job}, 202)
        except Exception as exc:
            _json(self, {"error": str(exc), "mode": "research", "live_trading_enabled": False}, 400)
