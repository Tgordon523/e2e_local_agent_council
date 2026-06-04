from council.agents.base import AgentReport, BaseCouncilAgent


class DeveloperAgent(BaseCouncilAgent):
    agent_name = "developer"
    use_search = False

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        sections = []
        for key, label in [
            ("market", "Market Research"),
            ("product", "Existing Products"),
            ("art_direction", "UX / Design Direction"),
        ]:
            if key in prior_reports:
                sections.append(f"--- {label} ---\n{prior_reports[key].report_text}")

        context = "\n\n".join(sections)

        return f"""You are a senior Python software architect. Design a technical implementation plan for the following idea.

IDEA: {idea}

RESEARCH CONTEXT:
{context}

Produce a technical implementation plan as a structured markdown report covering:

1. **Recommended tech stack** — languages, frameworks, key libraries with brief justifications
2. **System architecture** — high-level components and data flow (use ASCII diagram if helpful)
3. **Data model** — key entities, relationships, and storage strategy
4. **API surface** — key endpoints or interfaces (REST, GraphQL, CLI, SDK, etc.)
5. **Implementation complexity** — low / medium / high with rationale
6. **MVP scope** — the smallest shippable version that proves the core value
7. **Full product scope** — what comes after MVP
8. **Key technical risks** — unknowns, hard problems, dependency risks

Prefer Python ecosystem solutions where appropriate. Be specific and opinionated."""
