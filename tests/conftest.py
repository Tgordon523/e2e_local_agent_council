import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from council.agents.base import AgentReport
from council.models import Base


@pytest.fixture
def sample_idea():
    return "A subscription service for personalized dog food"


@pytest.fixture
def sample_market_report():
    return AgentReport(
        agent_name="market",
        report_text="## Market Analysis\n\nThe pet food market is $50B globally with 8% CAGR.",
        metadata={"queries": ["dog food market size 2024"]},
    )


@pytest.fixture
def all_prior_reports():
    return {
        "market": AgentReport("market", "Market is large and growing."),
        "product": AgentReport("product", "Product landscape is moderately competitive."),
        "art_direction": AgentReport("art_direction", "Clean design opportunity with mobile focus."),
        "developer": AgentReport("developer", "Medium complexity. Python + FastAPI recommended."),
        "qa": AgentReport("qa", "Testability is good. Main risk: third-party API reliability."),
    }


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine for testing (no Postgres needed)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite doesn't enforce FK constraints by default
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Re-create tables using simple types (SQLite-compatible)
    from sqlalchemy import Column, DateTime, String, Text
    from sqlalchemy.orm import DeclarativeBase

    class TestBase(DeclarativeBase):
        pass

    from sqlalchemy import JSON, ForeignKey, Index

    class TestRun(TestBase):
        __tablename__ = "runs"
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        idea_text = Column(Text, nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False)
        status = Column(String(20), nullable=False, default="pending")
        final_verdict = Column(Text)

    class TestAgentResult(TestBase):
        __tablename__ = "agent_results"
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        run_id = Column(String(36), ForeignKey("runs.id"), nullable=False)
        agent_name = Column(Text, nullable=False)
        report_text = Column(Text, nullable=False)
        metadata_json = Column(JSON)
        created_at = Column(DateTime(timezone=True), nullable=False)

    TestBase.metadata.create_all(engine)

    # Expose test model classes via engine attrs for orchestrator tests
    engine._test_run_class = TestRun
    engine._test_result_class = TestAgentResult
    engine._test_base = TestBase

    return engine


@pytest.fixture
def mock_llm_response():
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Mock report text from LLM.")
    return mock
