import pandas as pd

from orion_trading import walk_forward as wf


def _result(net_r, trades):
    return {
        "trades": trades,
        "wins": max(0, trades // 2),
        "losses": trades - max(0, trades // 2),
        "net_r": net_r,
        "expectancy_r": net_r / trades if trades else 0.0,
        "max_drawdown_r": 1.0,
        "profit_factor": 1.5,
        "trade_log": [],
    }


def test_walk_forward_uses_test_window_after_training(monkeypatch):
    calls = []

    def fake_backtest(frames, instrument, config, start=None, end=None):
        calls.append((instrument, pd.Timestamp(start), pd.Timestamp(end)))
        return _result(2.0, 10)

    monkeypatch.setattr(wf, "run_oafs_backtest", fake_backtest)

    frames = {
        "EUR_USD": {
            "M15": pd.DataFrame(
                index=pd.date_range("2026-01-01", "2026-11-01", freq="15min", tz="UTC")
            )
        }
    }
    result = wf.run_walk_forward(
        frames,
        ["EUR_USD"],
        "2026-01-01",
        "2026-10-01",
        wf.WalkForwardConfig(train_days=30, test_days=10, step_days=10),
    )

    assert result["method"] == "rolling_walk_forward"
    assert result["folds"]
    assert result["oos_portfolio"]["trades"] > 0

    first = result["folds"][0]
    train_end = pd.Timestamp(first["train"]["end"])
    test_start = pd.Timestamp(first["test"]["start"])
    assert train_end == test_start

    train_calls = [c for c in calls if c[1] < train_end]
    test_calls = [c for c in calls if c[1] >= test_start]
    assert train_calls
    assert test_calls


def test_walk_forward_has_no_result_when_period_is_too_short():
    frames = {
        "EUR_USD": {
            "M15": pd.DataFrame(index=pd.date_range("2026-01-01", periods=20, freq="15min", tz="UTC"))
        }
    }
    result = wf.run_walk_forward(
        frames,
        ["EUR_USD"],
        "2026-01-01",
        "2026-01-20",
        wf.WalkForwardConfig(train_days=180, test_days=60, step_days=60),
    )
    assert result["folds"] == []
    assert result["oos_portfolio"]["trades"] == 0
