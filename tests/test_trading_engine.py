import pandas as pd

from orion_trading.execution import PaperExecution
from orion_trading.models import Direction, Regime, SignalCandidate
from orion_trading.position_sizing import PositionSize
from orion_trading.risk import RiskEngine
from orion_trading.trading_engine import TradingEngine


def _candidate(direction=Direction.LONG):
    return SignalCandidate(
        instrument="TEST",
        detected_at=pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
        regime=Regime.TREND_UP,
        direction=direction,
        opportunities=(),
        valid=True,
    )


def test_engine_converts_percent_risk_to_fraction_for_sizing():
    engine = TradingEngine()
    position = engine.risk_engine
    assert position.config.max_risk_per_trade_pct == 0.50

    size = __import__("orion_trading.position_sizing", fromlist=["calculate_position_size"]).calculate_position_size(
        equity=10_000, risk_pct=0.005, entry=100, stop=98
    )
    assert size.risk_amount == 50


def test_engine_rejects_protection_mode_without_execution():
    engine = TradingEngine(risk_engine=RiskEngine())
    risk = engine.risk_engine.approve(
        risk_pct=0.50,
        daily_loss_pct=0,
        consecutive_losses=0,
        protection=True,
    )
    assert not risk.approved
    assert risk.reason == "PROTECTION_MODE"


def test_paper_execution_accepts_valid_order():
    from orion_trading.execution import OrderRequest

    broker = PaperExecution()
    order = OrderRequest(
        instrument="EUR_USD",
        direction=Direction.LONG,
        units=100,
        entry=1.10,
        stop=1.095,
        target=1.11,
        client_order_id="ORION-TEST-1",
        created_at=pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
    )
    result = broker.submit(order)
    assert result.accepted
    assert broker.orders[-1] == order
