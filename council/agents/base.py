from abc import ABC, abstractmethod

from council.agents.model import AnthropicModel, CouncilModel, content_to_text
from council.domain import AgentReport

# content_to_text is re-exported for callers that import it from here.
__all__ = ["BaseCouncilAgent", "content_to_text"]


class BaseCouncilAgent(ABC):
    """
    Abstract base for all council agents.

    An agent is a *prompt author*: subclasses declare `agent_name` / `use_search`
    and implement `_build_prompt()`. Calling the language model is delegated to an
    injected `CouncilModel` (default: `AnthropicModel`), so agents hold no
    LangChain knowledge and are tested by injecting a fake model.
    """

    agent_name: str
    model_id: str = "claude-sonnet-4-6"
    use_search: bool = False
    required_priors: list[str] = []
    # Reports are multi-section markdown; the SDK default of 1024 truncates them.
    max_tokens: int = 8192

    def __init__(self, model: CouncilModel | None = None):
        self.model = model or AnthropicModel(model_id=self.model_id, max_tokens=self.max_tokens)

    def _build_tools(self) -> list:
        from council.agents._tools import build_search_tool  # noqa: PLC0415

        return [build_search_tool()]

    @abstractmethod
    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        ...

    def run(self, idea: str, prior_reports: dict[str, AgentReport]) -> AgentReport:
        prompt = self._build_prompt(idea, prior_reports)
        tools = self._build_tools() if self.use_search else None
        text = self.model.complete(prompt, tools=tools)
        return AgentReport(agent_name=self.agent_name, report_text=text, metadata={})
