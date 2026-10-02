import pandas as pd

from orion_trading.validation_report import build_validation_report


def test_validation_report_accepts_walk_forward_results():
    results = [{
        "instrument": "EUR_USD",
        "trades": 1,
        "wins": 1,
        "losses": 0,
        "net_r": 2.0,
        "trade_log": [{
            "instrument": "EUR_USD",
            "entry_time": "2026-01-02T00:00:00Z",
            "exit_time": "2026-01-02T01:00:00Z",
            "pnl_r": 2.0,
            "regime": "TREND_UP",
            "opportunities": ["BREAKOUT"],
        }],
        "rejections": [],
    }]
    oos_result = {
        **results[0],
        "trade_log": [{
            **results[0]["trade_log"][0],
            "pnl_r": -1.0,
        }],
        "net_r": -1.0,
        "wins": 0,
        "losses": 1,
    }
    wf = {
        "method": "rolling_walk_forward",
        "train_days": 180,
        "test_days": 60,
        "step_days": 60,
        "folds": [],
        "oos_portfolio": {"trades": 1, "net_r": -1.0},
        "oos_results": [oos_result],
    }

    report = build_validation_report(
        results,
        "2026-01-01",
        "2026-12-31",
        simulations=50,
        walk_forward=wf,
    )

    assert report["walk_forward"] is wf
    assert report["walk_forward"]["oos_portfolio"]["net_r"] == -1.0
    assert report["monte_carlo"]["source"] == "walk_forward_oos"
    assert report["monte_carlo"]["trades"] == 1
