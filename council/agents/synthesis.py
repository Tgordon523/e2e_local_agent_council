from council.agents.base import AgentReport, BaseCouncilAgent


class SynthesisAgent(BaseCouncilAgent):
    agent_name = "synthesis"
    use_search = False

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        sections = []
        for key, label in [
            ("market", "Market Research Report"),
            ("product", "Product Availability Report"),
            ("art_direction", "Art Direction / UX Report"),
            ("developer", "Technical Implementation Plan"),
            ("qa", "QA / Risk Review"),
        ]:
            if key in prior_reports:
                sections.append(f"--- {label} ---\n{prior_reports[key].report_text}")

        all_reports = "\n\n".join(sections)

        return f"""You are the chief analyst for an idea evaluation council. You have received five expert reports on the following idea and must render a final verdict.

IDEA: {idea}

{all_reports}

Read all reports carefully and produce a final verdict as a structured markdown report:

1. **VERDICT** — GO, NO-GO, or CONDITIONAL GO (with specific conditions)
2. **Confidence** — low / medium / high
3. **Top 3 reasons supporting your verdict** — cite specific evidence from the reports
4. **Top 3 concerns or conditions** — what must be true for success
5. **Recommended immediate next steps** — if GO or CONDITIONAL GO, what should happen in the next 30 days?
6. **Executive summary** — one paragraph suitable for a non-technical stakeholder

Your verdict carries the weight of all five specialists. Be decisive."""
