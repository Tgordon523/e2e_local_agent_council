import logging

from council.agents.art_direction import ArtDirectionAgent
from council.agents.base import AgentReport
from council.agents.developer import DeveloperAgent
from council.agents.market import MarketAgent
from council.agents.product import ProductAgent
from council.agents.qa import QAAgent
from council.agents.synthesis import SynthesisAgent
from council.run_store import RunStore, default_run_store

logger = logging.getLogger(__name__)


def run_council(idea: str, store: RunStore | None = None) -> tuple[str, str]:
    """
    Run the full agent pipeline for the given idea.
    Returns (run_id, final_verdict_text).
    Persists through the RunStore seam (commits after each agent).
    """
    store = store or default_run_store()
    run_id = store.create_run(idea)

    pipeline = [MarketAgent, ProductAgent, ArtDirectionAgent, DeveloperAgent, QAAgent, SynthesisAgent]
    prior_reports: dict[str, AgentReport] = {}

    try:
        for AgentClass in pipeline:
            agent = AgentClass()
            logger.info("[%s] Starting...", agent.agent_name.upper())
            report = agent.run(idea=idea, prior_reports=prior_reports)
            prior_reports[agent.agent_name] = report
            store.record_report(run_id, report)
            logger.info("[%s] Done.", agent.agent_name.upper())

        final_verdict = prior_reports.get("synthesis", AgentReport("synthesis", "")).report_text
        store.complete(run_id, final_verdict)

    except Exception:
        # Best-effort status update; never let bookkeeping mask the real error.
        try:
            store.fail(run_id)
        except Exception:
            pass
        raise

    return run_id, final_verdict
