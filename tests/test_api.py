"""
API tests.

The API reads and writes through the RunStore seam, injected via FastAPI's
dependency system. Here we override that dependency with a store backed by
in-memory SQLite — the same real models used everywhere else — so the HTTP
edge is exercised end-to-end with no Postgres and no LLM calls.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from council import api
from council.api import app, get_store
from council.domain import AgentReport
from council.models import Base
from council.run_store import RunStore


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return RunStore(engine)


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def seed_run(store: RunStore, idea: str = "A seeded idea", verdict: str = "VERDICT: GO") -> str:
    run_id = store.create_run(idea)
    store.record_report(run_id, AgentReport("market", "Market looks large."))
    store.record_report(run_id, AgentReport("synthesis", verdict))
    store.complete(run_id, verdict)
    return run_id


class TestReadEndpoints:
    def test_get_run_returns_run_and_reports(self, client, store):
        run_id = seed_run(store)

        resp = client.get(f"/runs/{run_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["idea_text"] == "A seeded idea"
        assert body["status"] == "completed"
        assert body["final_verdict"] == "VERDICT: GO"
        assert {r["agent_name"] for r in body["agent_results"]} == {"market", "synthesis"}

    def test_get_missing_run_404(self, client):
        resp = client.get(f"/runs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_runs_returns_recent(self, client, store):
        seed_run(store, idea="first idea")
        seed_run(store, idea="second idea")

        resp = client.get("/runs")

        assert resp.status_code == 200
        ideas = {r["idea_text"] for r in resp.json()}
        assert {"first idea", "second idea"} <= ideas

    def test_list_runs_limit_is_validated(self, client):
        assert client.get("/runs?limit=0").status_code == 422
        assert client.get("/runs?limit=101").status_code == 422


class TestEvaluateEndpoint:
    def test_evaluate_persists_through_injected_store(self, client, store, monkeypatch):
        # Stub the orchestrator so the endpoint is tested without LLM calls,
        # while still proving it threads the injected store through run_council.
        def fake_run_council(idea, store):
            run_id = store.create_run(idea)
            store.record_report(run_id, AgentReport("synthesis", "VERDICT: GO"))
            store.complete(run_id, "VERDICT: GO")
            return run_id, "VERDICT: GO"

        monkeypatch.setattr(api, "run_council", fake_run_council)

        resp = client.post("/evaluate", json={"idea": "A testable idea"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["idea_text"] == "A testable idea"
        assert body["status"] == "completed"
        assert body["final_verdict"] == "VERDICT: GO"
        # The run really landed in the store the API was given.
        assert store.get(body["id"]) is not None

    def test_evaluate_rejects_empty_idea(self, client):
        assert client.post("/evaluate", json={"idea": ""}).status_code == 422


def test_importing_api_opens_no_database():
    # Importing the API must not construct an engine or a store at import time.
    # (Regression guard for the old module-level `store = default_run_store()`.)
    assert "store" not in vars(api) or not isinstance(vars(api).get("store"), RunStore)
