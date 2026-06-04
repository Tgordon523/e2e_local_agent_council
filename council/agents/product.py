from council.agents.base import AgentReport, BaseCouncilAgent


class ProductAgent(BaseCouncilAgent):
    agent_name = "product"
    use_search = True

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        market_context = ""
        if "market" in prior_reports:
            market_context = f"""
MARKET CONTEXT (from Market Research Agent):
{prior_reports['market'].report_text}
"""
        return f"""You are a product landscape researcher. Given this idea:

IDEA: {idea}
{market_context}
Research existing products, tools, or services that already solve this problem and produce a structured markdown report covering:

1. **Existing solutions** — list 5-10 products/services with brief descriptions and URLs
2. **Solution gaps** — what problems do current solutions NOT solve well?
3. **Competitive density** — sparse / moderate / crowded, with justification
4. **Dominant players** — note any with strong network effects, lock-in, or switching costs
5. **Differentiation opportunities** — where could a new entrant win?

Search the web for current products on Product Hunt, GitHub, app stores, and industry directories. Cite specific URLs."""
