import pytest
from orion_trading.costs import ExecutionCostConfig, apply_cost

def test_execution_cost_reduces_pnl():
    cfg = ExecutionCostConfig(spread_bps=1.0, slippage_bps=1.0)
    assert apply_cost(2.0, 1.0, 0.01, cfg) < 2.0

def test_zero_cost_is_identity():
    cfg = ExecutionCostConfig()
    assert apply_cost(1.5, 1.0, 0.01, cfg) == pytest.approx(1.5)
