"""
CouncilModel — the seam between a council agent and the language model.

A council agent is a *prompt author*: it turns an idea plus prior agent reports
into a prompt. Everything about *calling the model* — the Anthropic client, the
tool-calling executor, response normalisation, token limits, the system prompts
that frame each call — lives behind this seam so agents never import LangChain.

Production uses `AnthropicModel`. Tests inject a fake `CouncilModel` that records
the prompt and returns canned text, so the interface (`complete`) is the test
surface — no patching of LangChain internals.
"""
from typing import Protocol, runtime_checkable

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool


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


@runtime_checkable
class CouncilModel(Protocol):
    """The single interface an agent needs to call a language model."""

    def complete(self, prompt: str, *, tools: list[BaseTool] | None = None) -> str:
        """Return the model's text response to `prompt`.

        If `tools` are supplied, the model may call them in a tool-calling loop
        before producing its final answer.
        """
        ...


_DIRECT_SYSTEM = (
    "You are a specialist analyst on an idea evaluation council. "
    "Produce a thorough, well-structured markdown report based on the request."
)

_TOOL_SYSTEM = (
    "You are a specialist research analyst on an idea evaluation council. Use the "
    "available search tools to gather current evidence, then produce a thorough, "
    "well-structured markdown report based on the request."
)


class AnthropicModel:
    """The production CouncilModel — all LangChain/Anthropic machinery lives here."""

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-6",
        max_tokens: int = 8192,
        temperature: float = 0,
    ):
        self.llm = ChatAnthropic(model=model_id, temperature=temperature, max_tokens=max_tokens)

    def complete(self, prompt: str, *, tools: list[BaseTool] | None = None) -> str:
        if tools:
            return self._complete_with_tools(prompt, tools)
        return self._complete_direct(prompt)

    def _complete_with_tools(self, prompt: str, tools: list[BaseTool]) -> str:
        # Anthropic is a native tool-calling model; use the tool-calling agent
        # rather than the legacy ReAct text-parsing loop.
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _TOOL_SYSTEM),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, tools, chat_prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            max_iterations=6,
            handle_parsing_errors=True,
        )
        result = executor.invoke({"input": prompt})
        return content_to_text(result.get("output", ""))

    def _complete_direct(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        response = self.llm.invoke(
            [SystemMessage(content=_DIRECT_SYSTEM), HumanMessage(content=prompt)]
        )
        return content_to_text(response.content)
