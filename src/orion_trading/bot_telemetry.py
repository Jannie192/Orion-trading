from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

def heartbeat(*, status="ONLINE", stage="IDLE", instrument=None, timeframe=None,
              provider="dukascopy", message=None, progress_pct=None,
              last_scan_at=None, metadata=None):
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return False
    payload = {
        "service": "orion-research-worker",
        "status": status,
        "stage": stage,
        "instrument": instrument,
        "timeframe": timeframe,
        "provider": provider,
        "message": message,
        "progress_pct": progress_pct,
        "last_scan_at": last_scan_at,
        "metadata": metadata or {},
    }
    try:
        r = requests.post(
            f"{url}/rest/v1/orion_bot_telemetry",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=10,
        )
        return r.ok
    except Exception:
        return False

def latest_heartbeat():
    return datetime.now(timezone.utc).isoformat()
