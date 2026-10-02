import pandas as pd

from orion_trading.mtf import align_completed_frames
from orion_trading.validation_report import build_validation_report

def _frame(start, periods, freq):
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.0, "close": 1.0}, index=idx)

def test_alignment_accepts_d1_key():
    frames = {
        "D1": _frame("2026-01-01", 3, "1D"),
        "H4": _frame("2026-01-01", 6, "4h"),
        "H1": _frame("2026-01-01", 24, "1h"),
        "M15": _frame("2026-01-01 00:00", 16, "15min"),
    }
    event = pd.Timestamp("2026-01-01 03:15", tz="UTC")
    aligned = align_completed_frames(frames, event)
    assert "D" in aligned
    assert aligned["M15"].index[-1] == pd.Timestamp("2026-01-01 03:00", tz="UTC")
    assert aligned["H1"].index[-1] == pd.Timestamp("2026-01-01 02:00", tz="UTC")
    assert aligned["H4"].empty
    assert aligned["D"].empty

def test_validation_report_has_core_sections():
    results = [{
        "instrument": "EUR_USD",
        "trades": 2,
        "wins": 1,
        "losses": 1,
        "net_r": 1.0,
        "trade_log": [
            {"instrument": "EUR_USD", "entry_time": "2026-01-02T00:00:00Z",
             "exit_time": "2026-01-02T01:00:00Z", "pnl_r": 2.0,
             "regime": "TREND_UP", "opportunities": ["BREAKOUT"]},
            {"instrument": "EUR_USD", "entry_time": "2026-01-03T00:00:00Z",
             "exit_time": "2026-01-03T01:00:00Z", "pnl_r": -1.0,
             "regime": "RANGE", "opportunities": ["PULLBACK"]},
        ],
        "rejections": [{"reason": "NEWS"}],
    }]
    report = build_validation_report(results, "2026-01-01", "2026-12-31", simulations=100)
    assert report["portfolio"]["trades"] == 2
    assert "TREND_UP" in report["regimes"]
    assert "BREAKOUT" in report["opportunity_types"]
    assert report["rejections"]["NEWS"] == 1
    assert report["monte_carlo"]["simulations"] == 100
