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


def test_backtester_can_run_from_store(monkeypatch):
    from orion_trading.backtest import Backtester

    idx = pd.date_range("2026-01-01", periods=61, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0, "volume": 1.0},
        index=idx,
    )

    class FakeStore:
        def __init__(self):
            self.called = None
        def load(self, instrument, timeframe, **kwargs):
            self.called = (instrument, timeframe, kwargs)
            return frame

    store = FakeStore()
    result = Backtester().run_from_store(
        store,
        instrument="EUR_USD",
        timeframe="H1",
        start_at="2026-01-01T00:00:00+00:00",
        end_at="2026-01-03T00:00:00+00:00",
        limit=500,
    )
    assert result.initial_equity == 10_000.0
    assert store.called[0:2] == ("EUR_USD", "H1")
    assert store.called[2]["limit"] == 500


def test_store_records_research_result_and_returns_run_id(monkeypatch):
    from orion_trading.backtest import BacktestResult
    from orion_trading.research_cycle import ResearchResult

    store = SupabaseMarketDataStore(
        url="https://example.supabase.co",
        service_role_key="test-key",
    )
    calls = []

    def fake_post(endpoint, headers, json, timeout):
        calls.append((endpoint, headers, json))
        class Response:
            ok = True
            status_code = 201
            text = ""
            def json(self):
                return [{"run_id": "abc-123"}]
        return Response()

    monkeypatch.setattr(
        "orion_trading.supabase_market_store.requests.post",
        fake_post,
    )

    backtest = BacktestResult(10000, 11000, 10.0, 2.0, (), 1, 0, 100.0, float("inf"))
    result = ResearchResult("EURUSD", "H1", 500, 100, 2, backtest)

    run_id = store.record_research_result(
        strategy_name="ORION",
        strategy_version="1.0",
        result=result,
        start_at="2026-01-01T00:00:00+00:00",
        end_at="2026-02-01T00:00:00+00:00",
    )

    assert run_id == "abc-123"
    assert calls[0][0].endswith("/rest/v1/research_runs")
    assert calls[0][2]["trade_count"] == 0
    assert calls[0][2]["profit_factor"] is None
    assert calls[0][2]["profit_factor_infinite"] is True


def test_store_records_strategy_experiment_in_existing_schema(monkeypatch):
    from orion_trading.strategy_experiments import StrategyExperimentResult

    store = SupabaseMarketDataStore(
        url="https://example.supabase.co",
        service_role_key="test-key",
    )
    calls = []

    def fake_get(endpoint, headers, params, timeout):
        calls.append(("GET", endpoint, params))
        class Response:
            ok = True
            status_code = 200
            text = ""
            def json(self):
                return [{"strategy_id": "strategy-123"}]
        return Response()

    def fake_post(endpoint, headers, json, timeout):
        calls.append(("POST", endpoint, json))
        class Response:
            ok = True
            status_code = 201
            text = ""
            def json(self):
                return [{"experiment_id": "experiment-123"}]
        return Response()

    monkeypatch.setattr("orion_trading.supabase_market_store.requests.get", fake_get)
    monkeypatch.setattr("orion_trading.supabase_market_store.requests.post", fake_post)

    experiment = StrategyExperimentResult(
        strategy_name="ORION",
        strategy_version="experiment",
        instrument="EURUSD",
        timeframe="H1",
        variants=(),
        best=None,
    )
    experiment_id = store.record_strategy_experiment(experiment=experiment, days=365)

    assert experiment_id == "experiment-123"
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"
    assert calls[1][1].endswith("/rest/v1/strategy_experiments")
    assert calls[1][2]["strategy_id"] == "strategy-123"
    assert calls[1][2]["days"] == 365
    assert calls[1][2]["strategy_name"] == "ORION"
    assert calls[1][2]["results"]["variant_count"] == 0
    assert calls[1][2]["grid"] == {}
    assert "variants" not in calls[1][2]
    assert "best" not in calls[1][2]
