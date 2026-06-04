import uuid  # noqa: F401 (uuid.uuid4 used for ID generation)
from datetime import datetime, timezone

from council.agents.art_direction import ArtDirectionAgent
from council.agents.base import AgentReport
from council.agents.developer import DeveloperAgent
from council.agents.market import MarketAgent
from council.agents.product import ProductAgent
from council.agents.qa import QAAgent
from council.agents.synthesis import SynthesisAgent
from council.db import get_session
from council.models import AgentResult, Run

def run_council(idea: str) -> tuple[str, str]:
    """
    Run the full agent pipeline for the given idea.
    Returns (run_id, final_verdict_text).
    Persists all results to Postgres (commits after each agent).
    """
    run_id = str(uuid.uuid4())

    with get_session() as session:
        run = Run(
            id=run_id,
            idea_text=idea,
            created_at=datetime.now(timezone.utc),
            status="running",
        )
        session.add(run)

    pipeline = [MarketAgent, ProductAgent, ArtDirectionAgent, DeveloperAgent, QAAgent, SynthesisAgent]
    prior_reports: dict[str, AgentReport] = {}

    try:
        for AgentClass in pipeline:
            agent = AgentClass()
            print(f"\n[{agent.agent_name.upper()}] Starting...")
            report = agent.run(idea=idea, prior_reports=prior_reports)
            prior_reports[agent.agent_name] = report
            _persist_result(run_id, report)
            print(f"[{agent.agent_name.upper()}] Done.")

        final_verdict = prior_reports.get("synthesis", AgentReport("synthesis", "")).report_text
        _set_run_status(run_id, "completed", final_verdict=final_verdict)

    except Exception:
        # Best-effort status update; never let bookkeeping mask the real error.
        try:
            _set_run_status(run_id, "failed")
        except Exception:
            pass
        raise

    return run_id, final_verdict


def _set_run_status(run_id: str, status: str, final_verdict: str | None = None) -> None:
    with get_session() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.status = status
        if final_verdict is not None:
            run.final_verdict = final_verdict


def _persist_result(run_id: str, report: AgentReport) -> None:
    with get_session() as session:
        result = AgentResult(
            run_id=run_id,
            agent_name=report.agent_name,
            report_text=report.report_text,
            metadata_json=report.metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(result)
