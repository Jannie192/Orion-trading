from __future__ import annotations

import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
API_DIR = ROOT / "api"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_strategy_store import SupabaseStrategyStore


def _json(handler, payload, status=200):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _load_batch():
    path = API_DIR / "backtest-batch.py"
    spec = importlib.util.spec_from_file_location("orion_batch_engine_iteration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("BATCH_ENGINE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _grid_values(center, step, low, high):
    values = {max(low, min(high, float(center) + delta)) for delta in (-step, 0, step)}
    return sorted(round(x, 4) for x in values)


def propose(experiment, previous_iterations):
    results = experiment.get("results") or []
    if not results:
        raise ValueError("EXPERIMENT_HAS_NO_RESULTS")

    # Prefer configurations with positive test return and positive train/test
    # results, then use test return as the descriptive anchor. This is a research
    # heuristic, not a claim that the configuration will generalize.
    def metrics(row):
        train = row.get("train") or {}
        test = row.get("test") or {}
        return float(train.get("total_return_pct", 0)), float(test.get("total_return_pct", 0)), float(test.get("max_drawdown_pct", 0))
    robust = [i for i, row in enumerate(results) if metrics(row)[0] > 0 and metrics(row)[1] > 0]
    pool = robust or list(range(len(results)))
    idx = max(pool, key=lambda i: (metrics(results[i])[1], metrics(results[i])[0], -abs(metrics(results[i])[2])))
    base = results[idx]
    risk = float(base.get("risk_per_trade_pct", 0.5))
    stop = float(base.get("atr_stop_multiple", 1.5))
    reward = float(base.get("reward_multiple", 2.0))

    grid = {
        "risks": _grid_values(risk, 0.25, 0.05, 2.0),
        "stops": _grid_values(stop, 0.5, 0.5, 4.0),
        "rewards": _grid_values(reward, 0.5, 0.5, 6.0),
        "source": "local_neighborhood_from_observed_test_run",
        "anchor_run": idx + 1,
    }
    generation = max([int(x.get("generation", 0)) for x in previous_iterations] + [0]) + 1
    test_return = float((base.get("test") or {}).get("total_return_pct", 0))
    train_return = float((base.get("train") or {}).get("total_return_pct", 0))
    facts = {
        "anchor_run": idx + 1,
        "anchor_parameters": {
            "risk_per_trade_pct": risk,
            "atr_stop_multiple": stop,
            "reward_multiple": reward,
        },
        "anchor_test_return_pct": test_return,
        "anchor_train_return_pct": train_return,
        "previous_run_count": len(results),
        "robust_candidate_pool": len(robust),
        "selection_rule": "positive_train_and_test_when_available; then descriptive test return; drawdown used as final tie-breaker",
    }
    rationale = (
        f"Generation {generation} proposes a controlled local grid around run {idx + 1}, "
        f"which was selected from the configurations with positive train/test returns when such configurations existed, using observed test return as the primary descriptive measure. "
        f"The grid perturbs risk, ATR stop distance, and reward target one step around that "
        f"observed configuration. This narrows the next experiment without treating the "
        f"observed result as proof of future performance."
    )
    return generation, rationale, facts, grid


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q = parse_qs(urlparse(self.path).query)
            limit = int(q.get("limit", ["20"])[0])
            store = SupabaseStrategyStore()
            _json(self, {
                "mode": "research",
                "live_trading_enabled": False,
                "iterations": store.iterations(limit),
            })
        except Exception as exc:
            _json(self, {"error": str(exc), "mode": "research", "live_trading_enabled": False}, 500)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            action = str(body.get("action", ""))
            store = SupabaseStrategyStore()

            if action == "generate":
                experiment_id = str(body.get("experiment_id", ""))
                if not experiment_id:
                    raise ValueError("EXPERIMENT_ID_REQUIRED")
                experiment = store.experiment(experiment_id)
                prior = [x for x in store.iterations(100) if x.get("parent_experiment_id") == experiment_id]
                generation, rationale, facts, grid = propose(experiment, prior)
                row = store.create_iteration({
                    "parent_experiment_id": experiment_id,
                    "strategy_name": experiment["strategy_name"],
                    "strategy_version": experiment["strategy_version"],
                    "instrument": experiment["instrument"],
                    "timeframe": experiment["timeframe"],
                    "days": experiment["days"],
                    "generation": generation,
                    "rationale": rationale,
                    "facts": facts,
                    "proposed_grid": grid,
                    "status": "PROPOSED",
                })
                return _json(self, {"iteration": row, "mode": "research", "live_trading_enabled": False})

            if action == "run":
                iteration_id = str(body.get("iteration_id", ""))
                if not iteration_id:
                    raise ValueError("ITERATION_ID_REQUIRED")
                iteration = store.iteration(iteration_id)
                if iteration.get("status") != "PROPOSED":
                    raise ValueError("ITERATION_NOT_PROPOSED")

                store.update_iteration(iteration_id, {"status": "RUNNING"})
                grid = iteration["proposed_grid"]
                batch = _load_batch()
                try:
                    result = batch.run(
                        iteration["instrument"],
                        iteration["timeframe"],
                        int(iteration["days"]),
                        ",".join(str(x) for x in grid["risks"]),
                        ",".join(str(x) for x in grid["stops"]),
                        ",".join(str(x) for x in grid["rewards"]),
                    )
                except Exception:
                    store.update_iteration(iteration_id, {"status": "REJECTED"})
                    raise
                experiment = store.create_experiment({
                    "strategy_name": iteration["strategy_name"],
                    "strategy_version": iteration["strategy_version"],
                    "instrument": result["instrument"],
                    "timeframe": result["timeframe"],
                    "days": result["days"],
                    "grid": {**grid, "source_iteration_id": iteration_id},
                    "validation": result["validation"],
                    "results": result["results"],
                })
                completed = store.update_iteration(iteration_id, {
                    "status": "COMPLETED",
                    "child_experiment_id": experiment["experiment_id"],
                })
                return _json(self, {
                    "iteration": completed,
                    "experiment": experiment,
                    "validation": result["validation"],
                    "count": result["count"],
                    "results": result["results"],
                    "mode": "research",
                    "live_trading_enabled": False,
                })

            if action == "reject":
                iteration_id = str(body.get("iteration_id", ""))
                if not iteration_id:
                    raise ValueError("ITERATION_ID_REQUIRED")
                row = store.update_iteration(iteration_id, {"status": "REJECTED"})
                return _json(self, {"iteration": row, "mode": "research", "live_trading_enabled": False})

            raise ValueError("UNKNOWN_RESEARCH_ITERATION_ACTION")
        except Exception as exc:
            _json(self, {"error": str(exc), "mode": "research", "live_trading_enabled": False}, 400)
