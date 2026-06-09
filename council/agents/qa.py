from council.agents.base import AgentReport, BaseCouncilAgent


class QAAgent(BaseCouncilAgent):
    agent_name = "qa"
    use_search = False

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        dev_report = ""
        if "developer" in prior_reports:
            dev_report = prior_reports["developer"].report_text

        return f"""You are a senior QA engineer and software tester. Critically review the following technical plan.

IDEA: {idea}

TECHNICAL PLAN (from Developer Agent):
{dev_report}

Produce a QA review as a structured markdown report covering:

1. **Top 5 technical risks** — security, scalability, correctness, reliability; rank by severity
2. **Hardest-to-test components** — and suggested testing strategies for each
3. **Integration risks** — third-party dependencies, external APIs, versioning concerns
4. **Missing error handling / edge cases** — gaps in the proposed plan
5. **Showstoppers** — anything that would block a v1 release; be explicit if there are none
6. **Testability rating** — poor / fair / good / excellent with justification
7. **Recommended testing stack** — unit, integration, E2E tools suited to the proposed tech stack

Be critical but constructive. Flag showstoppers clearly with a ⚠️ marker."""
