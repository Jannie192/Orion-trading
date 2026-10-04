from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler
import requests
import sys, os as _os
ROOT=_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
SRC_PATH=_os.path.join(ROOT,"src")
if SRC_PATH not in sys.path: sys.path.insert(0,SRC_PATH)

def broker_status():
    try:
        from orion_trading.broker_manager import create_broker_manager
        s=create_broker_manager().health()
        return {"adapter":s.adapter,"mode":s.mode,"connected":s.connected,"live_enabled":s.live_enabled,"live_locked":s.live_locked,"reason":s.reason}
    except Exception as exc:
        return {"adapter":_os.getenv("ORION_BROKER_ADAPTER","paper"),"mode":_os.getenv("ORION_EXECUTION_MODE","paper"),"connected":False,"live_enabled":False,"live_locked":True,"reason":"BROKER_STATUS_ERROR:"+str(exc)}

def read_status():
    url=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
    if not url or not key:
        return {"status":"UNKNOWN","stage":"CONFIGURATION","message":"Supabase telemetry is not configured.","live_trading_enabled":False,"broker":broker_status()}
    r=requests.get(
        f"{url}/rest/v1/orion_bot_telemetry",
        params={"select":"created_at,status,stage,instrument,timeframe,provider,message,progress_pct,last_scan_at,metadata","order":"created_at.desc","limit":"1"},
        headers={"apikey":key,"Authorization":f"Bearer {key}"},
        timeout=10,
    )
    r.raise_for_status()
    row=(r.json() or [None])[0]
    if not row:
        return {"status":"STARTING","stage":"WAITING","message":"Waiting for the Railway worker heartbeat.","live_trading_enabled":False,"broker":broker_status()}
    return {**row,"live_trading_enabled":False,"mode":"paper","broker":broker_status()}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload=json.dumps(read_status(),separators=(",",":")).encode()
            code=200
        except Exception as exc:
            payload=json.dumps({"status":"ERROR","stage":"TELEMETRY","message":str(exc),"live_trading_enabled":False,"broker":broker_status()}).encode()
            code=502
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
