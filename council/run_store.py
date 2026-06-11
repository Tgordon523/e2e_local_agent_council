"""
RunStore — the persistence seam for the Idea Council.

The orchestrator writes through it; the API reads through it. Callers never see
the ORM session or models: writes take an `AgentReport`, reads return detached
`RunView` data. Each method is its own short transaction, so a run's reports are
committed agent-by-agent and survive a mid-pipeline crash.

The store is constructed with a SQLAlchemy engine, which is the only seam that
varies: Postgres in production, in-memory SQLite in the test suite. Because the
models are dialect-portable, both run the same schema.
"""
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from council.domain import AgentReport
from council.models import AgentResult, Run


class RunStatus(str, Enum):
    """Lifecycle state of a run. Mirrors the CHECK constraint in init.sql."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportView:
    """A persisted agent report as read back through the seam."""

    agent_name: str
    report_text: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)


@dataclass
class RunView:
    """A detached, read-only snapshot of a run. Never a live ORM row."""

    id: str
    idea_text: str
    created_at: datetime
    status: RunStatus
    final_verdict: str | None
    reports: list[ReportView] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunStore:
    def __init__(self, engine: Engine):
        self._sessions = sessionmaker(bind=engine)

    @contextmanager
    def _session(self):
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- writes (orchestrator) ------------------------------------------

    def create_run(self, idea: str) -> str:
        run_id = uuid.uuid4()
        with self._session() as s:
            s.add(
                Run(
                    id=run_id,
                    idea_text=idea,
                    created_at=_now(),
                    status=RunStatus.RUNNING.value,
                )
            )
        return str(run_id)

    def record_report(self, run_id: str, report: AgentReport) -> None:
        with self._session() as s:
            s.add(
                AgentResult(
                    run_id=uuid.UUID(run_id),
                    agent_name=report.agent_name,
                    report_text=report.report_text,
                    metadata_json=report.metadata,
                    created_at=_now(),
                )
            )

    def complete(self, run_id: str, verdict: str) -> None:
        self._set_status(run_id, RunStatus.COMPLETED, verdict)

    def fail(self, run_id: str) -> None:
        self._set_status(run_id, RunStatus.FAILED)

    def _set_status(self, run_id: str, status: RunStatus, verdict: str | None = None) -> None:
        with self._session() as s:
            run = s.get(Run, uuid.UUID(run_id))
            if run is None:
                return
            run.status = status.value
            if verdict is not None:
                run.final_verdict = verdict

    # --- reads (API) ----------------------------------------------------

    def get(self, run_id: str) -> RunView | None:
        with self._session() as s:
            run = s.get(Run, uuid.UUID(run_id))
            if run is None:
                return None
            results = (
                s.query(AgentResult)
                .filter(AgentResult.run_id == run.id)
                .order_by(AgentResult.created_at)
                .all()
            )
            return _to_view(run, results)

    def list_recent(self, limit: int = 20) -> list[RunView]:
        with self._session() as s:
            runs = s.query(Run).order_by(Run.created_at.desc()).limit(limit).all()
            return [_to_view(run, ()) for run in runs]


def _to_view(run: Run, results) -> RunView:
    return RunView(
        id=str(run.id),
        idea_text=run.idea_text,
        created_at=run.created_at,
        status=RunStatus(run.status),
        final_verdict=run.final_verdict,
        reports=[
            ReportView(
                agent_name=r.agent_name,
                report_text=r.report_text,
                created_at=r.created_at,
                metadata=r.metadata_json or {},
            )
            for r in results
        ],
    )


def default_run_store() -> RunStore:
    """A RunStore bound to the application's configured Postgres engine."""
    from council.db import engine

    return RunStore(engine)
