"""
Orchestrator tests.

The orchestrator is driven against a real RunStore backed by in-memory SQLite —
the same models that run in production, so there is no parallel test schema. The
six agents are mocked via patching the pipeline classes; no real LLM calls.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from council.agents.base import AgentReport
from council.models import Base
from council.run_store import RunStatus, RunStore

AGENT_NAMES = ["market", "product", "art_direction", "developer", "qa", "synthesis"]


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return RunStore(engine)


def canned_report(name: str) -> AgentReport:
    return AgentReport(
        agent_name=name,
        report_text=f"## {name.title()} Report\n\nThis is the {name} analysis.",
        metadata={"mocked": True},
    )


def build_mock_pipeline(overrides: dict[str, AgentReport] | None = None) -> list:
    """Build a list of 6 mock AgentClass objects that return canned reports."""
    overrides = overrides or {}
    pipeline = []
    for name in AGENT_NAMES:
        mock_class = MagicMock()
        mock_class.return_value.agent_name = name
        report = overrides.get(name, canned_report(name))
        mock_class.return_value.run.return_value = report
        pipeline.append(mock_class)
    return pipeline


def _patch_pipeline(mock_pipeline):
    return patch.multiple(
        "council.orchestrator",
        MarketAgent=mock_pipeline[0],
        ProductAgent=mock_pipeline[1],
        ArtDirectionAgent=mock_pipeline[2],
        DeveloperAgent=mock_pipeline[3],
        QAAgent=mock_pipeline[4],
        SynthesisAgent=mock_pipeline[5],
    )


class TestOrchestrator:
    def test_run_council_creates_run_and_six_results(self, store):
        with _patch_pipeline(build_mock_pipeline()):
            from council.orchestrator import run_council
            run_id, verdict = run_council("A test idea", store=store)

        assert isinstance(run_id, str)
        assert len(verdict) > 0

        view = store.get(run_id)
        assert view is not None
        assert view.status is RunStatus.COMPLETED
        assert view.idea_text == "A test idea"
        assert {r.agent_name for r in view.reports} == set(AGENT_NAMES)
        assert len(view.reports) == 6

    def test_failed_agent_marks_run_failed(self, store):
        failing_market = MagicMock()
        failing_market.return_value.agent_name = "market"
        failing_market.return_value.run.side_effect = RuntimeError("API timeout")

        with patch("council.orchestrator.MarketAgent", failing_market):
            with pytest.raises(RuntimeError, match="API timeout"):
                from council.orchestrator import run_council
                run_council("A failing idea", store=store)

        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0].status is RunStatus.FAILED

    def test_synthesis_verdict_is_returned(self, store):
        synthesis_report = AgentReport("synthesis", "VERDICT: GO\n\nConfidence: high")
        mock_pipeline = build_mock_pipeline(overrides={"synthesis": synthesis_report})

        with _patch_pipeline(mock_pipeline):
            from council.orchestrator import run_council
            _run_id, verdict = run_council("A great idea", store=store)

        assert "GO" in verdict
        assert "Confidence" in verdict
