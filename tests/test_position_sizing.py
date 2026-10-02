import pytest

from orion_trading.models import Direction
from orion_trading.position_sizing import calculate_position_size, direction_valid


def test_position_size_uses_stop_distance():
    result = calculate_position_size(
        equity=10000,
        risk_pct=0.005,
        entry=100,
        stop=98,
    )
    assert result.risk_amount == pytest.approx(50)
    assert result.units == pytest.approx(25)


def test_position_size_respects_cap():
    result = calculate_position_size(
        equity=10000,
        risk_pct=0.005,
        entry=100,
        stop=99,
        max_units=10,
    )
    assert result.units == 10


def test_direction_validation():
    assert direction_valid(Direction.LONG, 100, 99)
    assert direction_valid(Direction.SHORT, 100, 101)
    assert not direction_valid(Direction.LONG, 100, 101)
