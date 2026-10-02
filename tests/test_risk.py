from orion_trading.risk import RiskEngine


def test_risk_engine_vetoes_daily_loss():
    decision = RiskEngine().approve(risk_pct=0.5, daily_loss_pct=1.5, consecutive_losses=0)
    assert not decision.approved
    assert decision.reason == "DAILY_LOSS_LIMIT"


def test_risk_engine_approves_clean_candidate():
    decision = RiskEngine().approve(risk_pct=0.5, daily_loss_pct=0.0, consecutive_losses=0)
    assert decision.approved
