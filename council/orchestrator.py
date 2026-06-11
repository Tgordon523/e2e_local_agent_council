import logging

from council.agents.art_direction import ArtDirectionAgent
from council.agents.base import BaseCouncilAgent
from council.agents.developer import DeveloperAgent
from council.agents.market import MarketAgent
from council.agents.product import ProductAgent
from council.agents.qa import QAAgent
from council.agents.synthesis import SynthesisAgent
from council.domain import AgentReport
from council.run_store import RunStore, default_run_store

logger = logging.getLogger(__name__)

DEFAULT_PIPELINE: list[type[BaseCouncilAgent]] = [
    MarketAgent,
    ProductAgent,
    ArtDirectionAgent,
    DeveloperAgent,
    QAAgent,
    SynthesisAgent,
]


def run_council(
    idea: str,
    store: RunStore | None = None,
    pipeline: list[type[BaseCouncilAgent]] | None = None,
) -> tuple[str, str]:
    """
    Run an agent pipeline for the given idea.
    Returns (run_id, final_verdict_text).
    Persists through the RunStore seam (commits after each agent).
    Pipeline defaults to DEFAULT_PIPELINE (all six agents in order).
    """
    store = store or default_run_store()
    pipeline = pipeline if pipeline is not None else DEFAULT_PIPELINE
    run_id = store.create_run(idea)

    prior_reports: dict[str, AgentReport] = {}

    try:
        for AgentClass in pipeline:
            agent = AgentClass()
            missing = [p for p in agent.required_priors if p not in prior_reports]
            if missing:
                logger.warning(
                    "[%s] Missing required priors: %s — report quality may be degraded.",
                    agent.agent_name.upper(),
                    missing,
                )
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
