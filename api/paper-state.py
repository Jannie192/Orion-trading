from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repository's Python package importable in Vercel's Python runtime.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.paper_state_api import PaperStateAdapter  # noqa: E402

_adapter = PaperStateAdapter()


def handler(request):
    body = json.dumps(_adapter.snapshot(), separators=(",", ":"))
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store, max-age=0",
        },
        "body": body,
    }
