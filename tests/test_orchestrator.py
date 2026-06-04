"""
Orchestrator tests using SQLite in-memory DB — no Postgres needed.
All six agents are mocked via patching the pipeline list; no real LLM calls.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from council.agents.base import AgentReport

AGENT_NAMES = ["market", "product", "art_direction", "developer", "qa", "synthesis"]


# ---------------------------------------------------------------------------
# SQLite-compatible schema fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_session_factory():
    from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
    from sqlalchemy.orm import DeclarativeBase

    class TBase(DeclarativeBase):
        pass

    class TRun(TBase):
        __tablename__ = "runs"
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        idea_text = Column(Text, nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False)
        status = Column(String(20), nullable=False, default="pending")
        final_verdict = Column(Text)

    class TAgentResult(TBase):
        __tablename__ = "agent_results"
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        run_id = Column(String(36), ForeignKey("runs.id"), nullable=False)
        agent_name = Column(Text, nullable=False)
        report_text = Column(Text, nullable=False)
        metadata_json = Column(JSON)
        created_at = Column(DateTime(timezone=True), nullable=False)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session, TRun, TAgentResult, engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def make_fake_session(Session):
    """Return a context-manager factory that wraps the given SQLAlchemy Session."""
    from contextlib import contextmanager

    @contextmanager
    def fake_session():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return fake_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def test_run_council_creates_run_and_six_results(self, sqlite_session_factory):
        Session, TRun, TAgentResult, _ = sqlite_session_factory
        fake_session = make_fake_session(Session)
        mock_pipeline = build_mock_pipeline()

        with patch("council.orchestrator.get_session", fake_session), \
             patch("council.orchestrator.Run", TRun), \
             patch("council.orchestrator.AgentResult", TAgentResult), \
             patch.multiple(
                 "council.orchestrator",
                 MarketAgent=mock_pipeline[0],
                 ProductAgent=mock_pipeline[1],
                 ArtDirectionAgent=mock_pipeline[2],
                 DeveloperAgent=mock_pipeline[3],
                 QAAgent=mock_pipeline[4],
                 SynthesisAgent=mock_pipeline[5],
             ):
            from council.orchestrator import run_council
            run_id, verdict = run_council("A test idea")

        assert isinstance(run_id, str)
        assert isinstance(verdict, str)
        assert len(verdict) > 0

        session = Session()
        runs = session.query(TRun).all()
        assert len(runs) == 1
        assert runs[0].id == run_id
        assert runs[0].status == "completed"
        assert runs[0].idea_text == "A test idea"

        results = session.query(TAgentResult).all()
        assert len(results) == 6
        found_names = {r.agent_name for r in results}
        assert found_names == set(AGENT_NAMES)
        session.close()

    def test_failed_agent_marks_run_failed(self, sqlite_session_factory):
        Session, TRun, TAgentResult, _ = sqlite_session_factory
        fake_session = make_fake_session(Session)

        failing_market = MagicMock()
        failing_market.return_value.agent_name = "market"
        failing_market.return_value.run.side_effect = RuntimeError("API timeout")

        with patch("council.orchestrator.get_session", fake_session), \
             patch("council.orchestrator.Run", TRun), \
             patch("council.orchestrator.AgentResult", TAgentResult), \
             patch("council.orchestrator.MarketAgent", failing_market):
            with pytest.raises(RuntimeError, match="API timeout"):
                from council.orchestrator import run_council
                run_council("A failing idea")

        session = Session()
        run = session.query(TRun).first()
        assert run is not None
        assert run.status == "failed"
        session.close()

    def test_synthesis_verdict_is_returned(self, sqlite_session_factory):
        Session, TRun, TAgentResult, _ = sqlite_session_factory
        fake_session = make_fake_session(Session)

        synthesis_report = AgentReport("synthesis", "VERDICT: GO\n\nConfidence: high")
        mock_pipeline = build_mock_pipeline(overrides={"synthesis": synthesis_report})

        with patch("council.orchestrator.get_session", fake_session), \
             patch("council.orchestrator.Run", TRun), \
             patch("council.orchestrator.AgentResult", TAgentResult), \
             patch.multiple(
                 "council.orchestrator",
                 MarketAgent=mock_pipeline[0],
                 ProductAgent=mock_pipeline[1],
                 ArtDirectionAgent=mock_pipeline[2],
                 DeveloperAgent=mock_pipeline[3],
                 QAAgent=mock_pipeline[4],
                 SynthesisAgent=mock_pipeline[5],
             ):
            from council.orchestrator import run_council
            _run_id, verdict = run_council("A great idea")

        assert "GO" in verdict
        assert "Confidence" in verdict
