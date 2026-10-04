from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler
import requests

def read_status():
    url=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
    if not url or not key:
        return {"status":"UNKNOWN","stage":"CONFIGURATION","message":"Supabase telemetry is not configured.","live_trading_enabled":False}
    r=requests.get(
        f"{url}/rest/v1/orion_bot_telemetry",
        params={"select":"created_at,status,stage,instrument,timeframe,provider,message,progress_pct,last_scan_at,metadata","order":"created_at.desc","limit":"1"},
        headers={"apikey":key,"Authorization":f"Bearer {key}"},
        timeout=10,
    )
    r.raise_for_status()
    row=(r.json() or [None])[0]
    if not row:
        return {"status":"STARTING","stage":"WAITING","message":"Waiting for the Railway worker heartbeat.","live_trading_enabled":False}
    return {**row,"live_trading_enabled":False,"mode":"paper"}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload=json.dumps(read_status(),separators=(",",":")).encode()
            code=200
        except Exception as exc:
            payload=json.dumps({"status":"ERROR","stage":"TELEMETRY","message":str(exc),"live_trading_enabled":False}).encode()
            code=502
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
