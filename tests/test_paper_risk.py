from orion_trading.paper_risk import AccountRiskState, PaperRiskController


def test_daily_loss_is_hard_veto():
    controller = PaperRiskController()
    state = AccountRiskState(9850, 10000)
    decision = controller.approve(state, 0.5)
    assert not decision.approved
    assert decision.reason == "DAILY_LOSS_LIMIT"


def test_healthy_account_is_approved():
    controller = PaperRiskController()
    state = AccountRiskState(10000, 10000)
    decision = controller.approve(state, 0.5)
    assert decision.approved


def test_protection_mode_vetoes():
    controller = PaperRiskController()
    state = AccountRiskState(10000, 10000, protection=True)
    decision = controller.approve(state, 0.25)
    assert not decision.approved
    assert decision.reason == "PROTECTION_MODE"
