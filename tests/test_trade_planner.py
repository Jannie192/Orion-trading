import pandas as pd

from orion_trading.models import Direction, Regime, SignalCandidate
from orion_trading.trade_planner import plan_trade


def _cand(direction=Direction.LONG):
    return SignalCandidate(
        instrument="BTCUSDT",
        detected_at=pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
        regime=Regime.TREND_UP,
        direction=direction,
        opportunities=(),
        evidence={},
        valid=True,
    )


def _candles():
    idx = pd.date_range("2026-01-01", periods=80, freq="h", tz="UTC")
    base = pd.Series(range(100, 180), index=idx, dtype=float)
    return pd.DataFrame({
        "open": base,
        "high": base + 2,
        "low": base - 2,
        "close": base + 1,
        "volume": 1000.0,
    })


def test_plan_trade_adds_long_levels():
    planned = plan_trade(_cand(), _candles())
    assert planned.entry is not None
    assert planned.stop is not None
    assert planned.target is not None
    assert planned.entry > planned.stop
    assert planned.target > planned.entry
    assert planned.evidence["risk_reward"] == 2.0


def test_plan_trade_adds_short_levels():
    planned = plan_trade(_cand(Direction.SHORT), _candles())
    assert planned.entry > planned.target
    assert planned.stop > planned.entry


def test_invalid_candidate_is_unchanged():
    candidate = _cand()
    invalid = SignalCandidate(**{**candidate.__dict__, "valid": False, "rejection_reason": "X"})
    assert plan_trade(invalid, _candles()) == invalid
