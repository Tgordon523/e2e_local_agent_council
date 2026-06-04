from council.agents.base import AgentReport, BaseCouncilAgent


class MarketAgent(BaseCouncilAgent):
    agent_name = "market"
    use_search = True

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        return f"""You are a senior market research analyst evaluating the market opportunity for the following idea:

IDEA: {idea}

Research the following aspects and produce a structured markdown report:
1. **Market size** — TAM/SAM/SOM estimates if available, cite data sources and years
2. **Growth trends** — CAGR, momentum indicators, key drivers
3. **Top competitors** — 3-5 companies or analogous products with brief descriptions
4. **Market maturity** — emerging / growing / mature / declining, and why
5. **Key risks and tailwinds** — regulatory, economic, behavioral factors

Use web search to find current data. Cite sources inline with URLs where possible.
Format your final answer as clean markdown with clear section headers."""
