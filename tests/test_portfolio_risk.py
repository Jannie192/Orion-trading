from orion_trading.models import Direction
from orion_trading.portfolio_risk import PortfolioPosition, PortfolioRiskGate


def test_blocks_third_position_on_same_instrument():
    positions = [
        PortfolioPosition("BTCUSDT", Direction.LONG, 1000, 25),
        PortfolioPosition("BTCUSDT", Direction.LONG, 1000, 25),
    ]
    d = PortfolioRiskGate().approve(
        equity=10000,
        proposed_instrument="BTCUSDT",
        proposed_direction=Direction.LONG,
        proposed_risk_pct=0.5,
        positions=positions,
    )
    assert not d.approved
    assert d.reason == "MAX_CORRELATED_POSITIONS"


def test_blocks_total_portfolio_risk():
    positions = [
        PortfolioPosition("BTCUSDT", Direction.LONG, 1000, 50),
        PortfolioPosition("ETHUSDT", Direction.LONG, 1000, 50),
    ]
    d = PortfolioRiskGate().approve(
        equity=10000,
        proposed_instrument="SOLUSDT",
        proposed_direction=Direction.LONG,
        proposed_risk_pct=0.5,
        positions=positions,
    )
    assert d.approved


def test_blocks_when_total_risk_would_exceed_limit():
    positions = [
        PortfolioPosition("BTCUSDT", Direction.LONG, 1000, 100),
        PortfolioPosition("ETHUSDT", Direction.LONG, 1000, 50),
    ]
    d = PortfolioRiskGate().approve(
        equity=10000,
        proposed_instrument="SOLUSDT",
        proposed_direction=Direction.LONG,
        proposed_risk_pct=0.5,
        positions=positions,
    )
    assert not d.approved
    assert d.reason == "MAX_TOTAL_PORTFOLIO_RISK"
