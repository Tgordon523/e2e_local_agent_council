"""
Orchestrator tests.

The orchestrator is driven against a real RunStore backed by in-memory SQLite —
the same models that run in production, so there is no parallel test schema. The
agent pipeline is passed directly to run_council; no module-level patching needed.
"""
import logging
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from council.domain import AgentReport
from council.models import Base
from council.orchestrator import run_council
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


def mock_agent_class(
    name: str,
    report: AgentReport | None = None,
    required_priors: list[str] | None = None,
) -> MagicMock:
    cls = MagicMock()
    cls.return_value.agent_name = name
    cls.return_value.required_priors = required_priors if required_priors is not None else []
    cls.return_value.run.return_value = report or canned_report(name)
    return cls


def default_pipeline(overrides: dict[str, AgentReport] | None = None) -> list:
    overrides = overrides or {}
    return [
        mock_agent_class(name, overrides.get(name))
        for name in AGENT_NAMES
    ]


class TestOrchestrator:
    def test_run_council_creates_run_and_six_results(self, store):
        run_id, verdict = run_council("A test idea", store=store, pipeline=default_pipeline())

        assert isinstance(run_id, str)
        assert len(verdict) > 0

        view = store.get(run_id)
        assert view is not None
        assert view.status is RunStatus.COMPLETED
        assert view.idea_text == "A test idea"
        assert {r.agent_name for r in view.reports} == set(AGENT_NAMES)
        assert len(view.reports) == 6

    def test_failed_agent_marks_run_failed(self, store):
        failing = MagicMock()
        failing.return_value.agent_name = "market"
        failing.return_value.run.side_effect = RuntimeError("API timeout")

        with pytest.raises(RuntimeError, match="API timeout"):
            run_council("A failing idea", store=store, pipeline=[failing])

        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0].status is RunStatus.FAILED

    def test_synthesis_verdict_is_returned(self, store):
        synthesis_report = AgentReport("synthesis", "VERDICT: GO\n\nConfidence: high")
        pipeline = default_pipeline(overrides={"synthesis": synthesis_report})

        _run_id, verdict = run_council("A great idea", store=store, pipeline=pipeline)

        assert "GO" in verdict
        assert "Confidence" in verdict

    def test_custom_pipeline_runs_only_given_agents(self, store):
        market = mock_agent_class("market")
        synthesis = mock_agent_class("synthesis", AgentReport("synthesis", "VERDICT: GO"))

        run_id, verdict = run_council("Quick idea", store=store, pipeline=[market, synthesis])

        view = store.get(run_id)
        assert {r.agent_name for r in view.reports} == {"market", "synthesis"}
        assert "GO" in verdict

    def test_missing_required_prior_emits_warning(self, store, caplog):
        # synthesis declares required_priors = ["market"], but pipeline skips market.
        synthesis = mock_agent_class(
            "synthesis",
            AgentReport("synthesis", "VERDICT: GO"),
            required_priors=["market"],
        )

        with caplog.at_level(logging.WARNING, logger="council.orchestrator"):
            run_council("Idea with missing prior", store=store, pipeline=[synthesis])

        assert any("market" in msg and "Missing required priors" in msg for msg in caplog.messages)

    def test_satisfied_required_priors_emit_no_warning(self, store, caplog):
        market = mock_agent_class("market")
        synthesis = mock_agent_class(
            "synthesis",
            AgentReport("synthesis", "VERDICT: GO"),
            required_priors=["market"],
        )

        with caplog.at_level(logging.WARNING, logger="council.orchestrator"):
            run_council("Idea with all priors", store=store, pipeline=[market, synthesis])

        assert not any("Missing required priors" in msg for msg in caplog.messages)

    def test_required_priors_declared_on_real_agents(self):
        from council.agents.developer import DeveloperAgent
        from council.agents.qa import QAAgent
        from council.agents.synthesis import SynthesisAgent
        from council.agents.product import ProductAgent
        from council.agents.art_direction import ArtDirectionAgent
        from council.agents.market import MarketAgent

        assert MarketAgent.required_priors == []
        assert ProductAgent.required_priors == ["market"]
        assert ArtDirectionAgent.required_priors == ["product"]
        assert DeveloperAgent.required_priors == ["market", "product", "art_direction"]
        assert QAAgent.required_priors == ["developer"]
        assert SynthesisAgent.required_priors == ["market", "product", "art_direction", "developer", "qa"]
