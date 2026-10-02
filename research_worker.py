from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
from datetime import datetime, timezone
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


def _now():
    return datetime.now(timezone.utc).isoformat()


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
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "X-Orion-Worker-Key": worker_key,
        "Content-Type": "application/json",
        **kwargs.pop("headers", {}),
    }
    response = requests.request(method, f"{url}/rest/v1/{path}", headers=headers, timeout=15, **kwargs)
    if not response.ok:
        raise RuntimeError(f"Supabase request failed ({response.status_code}): {response.text[:500]}")
    return response.json() if response.content else []


def _update_job(job_id, patch):
    patch = {**patch, "updated_at": _now()}
    rows = _supabase_request(
        "PATCH",
        f"research_jobs?job_id=eq.{job_id}",
        json=patch,
        headers={"Prefer": "return=representation"},
    )
    if not rows:
        raise RuntimeError("RESEARCH_JOB_NOT_FOUND")
    return rows[0]


def _run_job(job_id, payload):
    try:
        _update_job(job_id, {"status": "RUNNING", "progress_pct": 5, "started_at": _now()})
        _update_job(job_id, {"progress_pct": 15})
        result = MODULE.run(
            str(payload.get("instrument", "BTCUSDT")).upper(),
            str(payload.get("timeframe", "H1")).upper(),
            int(payload.get("days", 90)),
            str(payload.get("risks", "0.25,0.5,0.75")),
            str(payload.get("stops", "1,1.5,2")),
            str(payload.get("rewards", "1.5,2,3")),
            train_bars=payload.get("train_bars"),
            test_bars=payload.get("test_bars"),
            step_bars=payload.get("step_bars"),
            max_folds=payload.get("max_folds", 8),
        )
        _update_job(job_id, {
            "status": "COMPLETED",
            "progress_pct": 100,
            "result": {**result, "worker": "railway", "stage": "COMPLETED"},
            "completed_at": _now(),
            "error": None,
        })
    except Exception as exc:
        try:
            _update_job(job_id, {
                "status": "FAILED",
                "progress_pct": 100,
                "error": str(exc),
                "completed_at": _now(),
            })
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
            return _json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "orion-research-worker",
                    "live_trading_enabled": False,
                    "job_mode": "asynchronous",
                },
            )
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
            _json_response(
                self,
                202,
                {"mode": "research", "live_trading_enabled": False, "worker": "railway", "job_id": job_id, "status": "STARTED"},
            )
        except Exception as exc:
            _json_response(
                self,
                400,
                {"mode": "research", "live_trading_enabled": False, "worker": "railway", "error": str(exc)},
            )


if __name__ == "__main__":
    print(f"ORION research worker listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
