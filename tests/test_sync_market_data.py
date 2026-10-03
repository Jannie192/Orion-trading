from datetime import datetime, timezone

from scripts.sync_market_data import parse_utc


def test_parse_utc_handles_z_suffix():
    value = parse_utc("2026-01-01T12:00:00Z")
    assert value == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_parse_utc_assigns_utc_to_naive_input():
    value = parse_utc("2026-01-01T12:00:00")
    assert value == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
