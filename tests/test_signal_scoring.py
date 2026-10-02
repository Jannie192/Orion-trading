from datetime import datetime, timezone
from orion_trading.models import Direction, Regime, SignalCandidate
from orion_trading.signal_scoring import score_candidate


def test_score_rewards_valid_mtf_aligned_signal():
    c = SignalCandidate(
        instrument="BTCUSDT",
        detected_at=datetime.now(timezone.utc),
        regime=Regime.TREND_UP,
        direction=Direction.LONG,
        opportunities=(),
        evidence={"rsi14": 60.0, "roc10": 0.01},
        valid=True,
    )
    s = score_candidate(c, timeframe="M15", aligned_timeframes=("H1", "H4"))
    assert s.score >= 80
    assert s.confidence == "HIGH"
    assert "MTF_ALIGNMENT" in s.confirmations
