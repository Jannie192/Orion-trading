import pandas as pd
import pytest

from orion_trading.supabase_market_store import SupabaseMarketDataStore


def test_store_requires_credentials(monkeypatch):
    monkeypatch.delenv("ORION_SUPABASE_URL", raising=False)
    monkeypatch.delenv("ORION_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(ValueError, match="ORION_SUPABASE_URL"):
        SupabaseMarketDataStore()


def test_store_normalises_candles_and_batches(monkeypatch):
    store = SupabaseMarketDataStore(
        url="https://example.supabase.co",
        service_role_key="test-key",
        batch_size=2,
    )
    calls = []

    def fake_post(endpoint, headers, json, timeout):
        calls.append((endpoint, json))
        class Response:
            ok = True
            status_code = 201
            text = ""
        return Response()

    monkeypatch.setattr(
        "orion_trading.supabase_market_store.requests.post",
        fake_post,
    )

    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00:00+00:00"),
            pd.Timestamp("2026-01-01 00:15:00+00:00"),
            pd.Timestamp("2026-01-01 00:30:00+00:00"),
        ]
    )
    frame = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0.5, 1.5, 2.5],
            "close": [1.5, 2.5, 3.5],
            "volume": [10, 11, 12],
        },
        index=index,
    )

    assert store.save("EUR_USD", "M15", frame, "dukascopy") == 3
    assert len(calls) == 2
    assert all(row["instrument"] == "EUR_USD" for _, batch in calls for row in batch)
    assert calls[0][1][0]["timeframe"] == "M15"
    assert calls[0][1][0]["provider"] == "dukascopy"


def test_store_loads_persisted_candles(monkeypatch):
    store = SupabaseMarketDataStore(
        url="https://example.supabase.co",
        service_role_key="test-key",
    )
    calls = []

    def fake_get(endpoint, headers, params, timeout):
        calls.append((endpoint, params))
        class Response:
            ok = True
            status_code = 200
            text = ""
            def json(self):
                return [
                    {
                        "ts": "2026-01-01T00:15:00+00:00",
                        "open": "2",
                        "high": "3",
                        "low": "1",
                        "close": "2.5",
                        "volume": "11",
                    }
                ]
        return Response()

    monkeypatch.setattr(
        "orion_trading.supabase_market_store.requests.get",
        fake_get,
    )

    frame = store.load(
        "EUR_USD",
        "M15",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T01:00:00+00:00",
    )
    assert len(frame) == 1
    assert str(frame.index.tz) == "UTC"
    assert frame.iloc[0]["close"] == 2.5
    assert calls[0][1]["and"] == "(ts.gte.2026-01-01T00:00:00+00:00,ts.lt.2026-01-01T01:00:00+00:00)"
