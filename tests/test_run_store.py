"""
Tests at the RunStore interface — the test surface for persistence.

The fixture builds the *real* models (council.models.Base) against in-memory
SQLite. That only works because the models are dialect-portable, so there is no
parallel TRun/TAgentResult schema to maintain here.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from council.agents.base import AgentReport
from council.models import Base
from council.run_store import RunStatus, RunStore


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)  # real models, portable types
    return RunStore(engine)


def report(name: str) -> AgentReport:
    return AgentReport(agent_name=name, report_text=f"## {name}\n\nbody", metadata={"k": name})


class TestRunStore:
    def test_create_run_starts_running(self, store):
        run_id = store.create_run("an idea")
        assert isinstance(run_id, str)

        view = store.get(run_id)
        assert view is not None
        assert view.id == run_id
        assert view.idea_text == "an idea"
        assert view.status is RunStatus.RUNNING
        assert view.final_verdict is None
        assert view.reports == []

    def test_record_and_get_roundtrip_in_order(self, store):
        run_id = store.create_run("idea")
        store.record_report(run_id, report("market"))
        store.record_report(run_id, report("product"))

        view = store.get(run_id)
        assert [r.agent_name for r in view.reports] == ["market", "product"]
        assert view.reports[0].report_text == "## market\n\nbody"
        assert view.reports[0].metadata == {"k": "market"}
        assert view.reports[0].created_at is not None

    def test_complete_sets_verdict_and_status(self, store):
        run_id = store.create_run("idea")
        store.complete(run_id, "VERDICT: GO")

        view = store.get(run_id)
        assert view.status is RunStatus.COMPLETED
        assert view.final_verdict == "VERDICT: GO"

    def test_fail_sets_status(self, store):
        run_id = store.create_run("idea")
        store.fail(run_id)

        assert store.get(run_id).status is RunStatus.FAILED

    def test_get_missing_returns_none(self, store):
        import uuid

        assert store.get(str(uuid.uuid4())) is None

    def test_list_recent_orders_desc_and_limits(self, store):
        ids = [store.create_run(f"idea {i}") for i in range(3)]

        recent = store.list_recent(limit=2)
        assert len(recent) == 2
        # newest first
        assert recent[0].id == ids[-1]
        # list view need not hydrate reports
        assert recent[0].reports == []

    def test_status_transitions_are_independent_per_run(self, store):
        a = store.create_run("a")
        b = store.create_run("b")
        store.complete(a, "done")
        store.fail(b)

        assert store.get(a).status is RunStatus.COMPLETED
        assert store.get(b).status is RunStatus.FAILED
