from council.agents.base import AgentReport, BaseCouncilAgent


class ArtDirectionAgent(BaseCouncilAgent):
    agent_name = "art_direction"
    use_search = True

    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        product_context = ""
        if "product" in prior_reports:
            product_context = f"""
EXISTING PRODUCTS CONTEXT (from Product Availability Agent):
{prior_reports['product'].report_text}
"""
        return f"""You are a senior UX designer and creative director evaluating the design opportunity for:

IDEA: {idea}
{product_context}
Assess the design and experience landscape, then produce a structured markdown report covering:

1. **Dominant UX paradigms** — how do existing solutions deliver their experience? (CLI, web app, mobile, conversational, dashboard, etc.)
2. **Design patterns** — navigation models, information architecture patterns, key interaction patterns used by leaders in this space
3. **Aesthetic trends** — visual language, color, typography, motion patterns you observe across the space
4. **Differentiation opportunity** — where is there room for a distinctly better or more delightful experience?
5. **Key UX risks** — accessibility concerns, cognitive load issues, platform constraints
6. **Proposed design direction** — a 2-3 sentence creative brief / design personality for this product

Search for design teardowns, screenshots, UX reviews, and design system docs of similar products."""
