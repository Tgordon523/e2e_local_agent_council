from abc import ABC, abstractmethod

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from council.domain import AgentReport


def content_to_text(content) -> str:
    """
    Normalize a LangChain message `content` to plain text.

    Anthropic responses are usually a str, but can be a list of content
    blocks (dicts with a "text" key, or plain strings). This collapses both
    forms to a single string so it is safe to persist and interpolate.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


class BaseCouncilAgent(ABC):
    """
    Abstract base for all council agents.

    Subclasses declare `agent_name` and `use_search` class variables, then
    implement `_build_prompt()`. Agents with `use_search = True` run a ReAct
    loop via AgentExecutor; others call the LLM directly.
    """

    agent_name: str
    model_id: str = "claude-sonnet-4-6"
    use_search: bool = False
    required_priors: list[str] = []
    # Reports are multi-section markdown; the SDK default of 1024 truncates them.
    max_tokens: int = 8192

    def __init__(self):
        self.llm = ChatAnthropic(model=self.model_id, temperature=0, max_tokens=self.max_tokens)
        self.tools: list[BaseTool] = self._build_tools() if self.use_search else []

    def _build_tools(self) -> list[BaseTool]:
        from council.agents._tools import build_search_tool
        return [build_search_tool()]

    @abstractmethod
    def _build_prompt(self, idea: str, prior_reports: dict[str, AgentReport]) -> str:
        ...

    def run(self, idea: str, prior_reports: dict[str, AgentReport]) -> AgentReport:
        prompt = self._build_prompt(idea, prior_reports)

        if self.use_search and self.tools:
            return self._run_with_tools(prompt)
        return self._run_direct(prompt)

    def _run_with_tools(self, prompt: str) -> AgentReport:
        # Anthropic is a native tool-calling model; use the tool-calling agent
        # rather than the legacy ReAct text-parsing loop.
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a specialist research analyst on an idea evaluation "
                    "council. Use the available search tools to gather current "
                    "evidence, then produce a thorough, well-structured markdown "
                    "report based on the request.",
                ),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        agent = create_tool_calling_agent(self.llm, self.tools, chat_prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=False,
            max_iterations=6,
            handle_parsing_errors=True,
        )
        result = executor.invoke({"input": prompt})
        return AgentReport(
            agent_name=self.agent_name,
            report_text=content_to_text(result.get("output", "")),
            metadata={},
        )

    def _run_direct(self, prompt: str) -> AgentReport:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        system = (
            "You are a specialist analyst on an idea evaluation council. "
            "Produce a thorough, well-structured markdown report based on the request."
        )
        response = self.llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        return AgentReport(
            agent_name=self.agent_name,
            report_text=content_to_text(response.content),
            metadata={},
        )
