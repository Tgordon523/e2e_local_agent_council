"""
Unit tests for all six council agents.
No real API calls — ChatAnthropic and search tools are mocked.
"""
from unittest.mock import MagicMock, patch

import pytest

from council.agents.base import AgentReport, BaseCouncilAgent, content_to_text
from council.agents.art_direction import ArtDirectionAgent
from council.agents.developer import DeveloperAgent
from council.agents.market import MarketAgent
from council.agents.product import ProductAgent
from council.agents.qa import QAAgent
from council.agents.synthesis import SynthesisAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_executor_mock(output: str = "Mock agent output.") -> MagicMock:
    """Return a mock AgentExecutor whose .invoke() returns the given output."""
    mock = MagicMock()
    mock.invoke.return_value = {"output": output}
    return mock


def make_llm_mock(content: str = "Mock LLM content.") -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=content)
    return mock


# ---------------------------------------------------------------------------
# BaseCouncilAgent contract
# ---------------------------------------------------------------------------

class TestContentToText:
    def test_plain_string_passthrough(self):
        assert content_to_text("hello world") == "hello world"

    def test_list_of_blocks_collapsed(self):
        content = [{"type": "text", "text": "part one "}, {"type": "text", "text": "part two"}]
        assert content_to_text(content) == "part one part two"

    def test_list_with_plain_strings(self):
        assert content_to_text(["a", "b", "c"]) == "abc"

    def test_block_without_text_key_ignored(self):
        content = [{"type": "tool_use", "id": "x"}, {"type": "text", "text": "kept"}]
        assert content_to_text(content) == "kept"


class TestBaseCouncilAgent:
    def test_agent_report_defaults(self):
        report = AgentReport(agent_name="test", report_text="hello")
        assert report.metadata == {}

    def test_all_agents_have_agent_name(self):
        for cls in [MarketAgent, ProductAgent, ArtDirectionAgent, DeveloperAgent, QAAgent, SynthesisAgent]:
            assert hasattr(cls, "agent_name"), f"{cls.__name__} missing agent_name"
            assert isinstance(cls.agent_name, str)
            assert cls.agent_name  # non-empty

    def test_search_agents_flagged(self):
        assert MarketAgent.use_search is True
        assert ProductAgent.use_search is True
        assert ArtDirectionAgent.use_search is True

    def test_no_search_agents_flagged(self):
        assert DeveloperAgent.use_search is False
        assert QAAgent.use_search is False
        assert SynthesisAgent.use_search is False


# ---------------------------------------------------------------------------
# Market Agent
# ---------------------------------------------------------------------------

class TestMarketAgent:
    @patch("council.agents.base.ChatAnthropic")
    @patch("council.agents.market.MarketAgent._build_tools")
    def test_run_returns_agent_report(self, mock_build_tools, mock_llm_class, sample_idea):
        mock_build_tools.return_value = [MagicMock()]  # non-empty triggers _run_with_tools
        executor_mock = make_executor_mock("## Market Report\n\nLarge market.")

        with patch("council.agents.base.create_tool_calling_agent", return_value=MagicMock()), \
             patch("council.agents.base.AgentExecutor", return_value=executor_mock):
            agent = MarketAgent()
            report = agent.run(idea=sample_idea, prior_reports={})

        assert report.agent_name == "market"
        assert "Market" in report.report_text
        assert isinstance(report.metadata, dict)

    def test_prompt_contains_idea(self, sample_idea):
        agent = MarketAgent.__new__(MarketAgent)
        prompt = agent._build_prompt(sample_idea, {})
        assert sample_idea in prompt
        assert "market size" in prompt.lower()


# ---------------------------------------------------------------------------
# Product Agent
# ---------------------------------------------------------------------------

class TestProductAgent:
    def test_prompt_includes_market_context(self, sample_idea, sample_market_report):
        agent = ProductAgent.__new__(ProductAgent)
        prompt = agent._build_prompt(sample_idea, {"market": sample_market_report})
        assert sample_market_report.report_text in prompt

    def test_prompt_without_market_still_works(self, sample_idea):
        agent = ProductAgent.__new__(ProductAgent)
        prompt = agent._build_prompt(sample_idea, {})
        assert sample_idea in prompt


# ---------------------------------------------------------------------------
# Art Direction Agent
# ---------------------------------------------------------------------------

class TestArtDirectionAgent:
    def test_prompt_includes_product_context(self, sample_idea, all_prior_reports):
        agent = ArtDirectionAgent.__new__(ArtDirectionAgent)
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["product"].report_text in prompt

    def test_agent_name(self):
        assert ArtDirectionAgent.agent_name == "art_direction"


# ---------------------------------------------------------------------------
# Developer Agent (no search)
# ---------------------------------------------------------------------------

class TestDeveloperAgent:
    @patch("council.agents.base.ChatAnthropic")
    def test_run_direct_invokes_llm(self, mock_llm_class, sample_idea, all_prior_reports):
        llm_mock = make_llm_mock("## Tech Plan\n\nUse FastAPI.")
        mock_llm_class.return_value = llm_mock

        agent = DeveloperAgent()
        report = agent.run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "developer"
        assert "Tech Plan" in report.report_text
        llm_mock.invoke.assert_called_once()

    def test_prompt_includes_all_three_prior_reports(self, sample_idea, all_prior_reports):
        agent = DeveloperAgent.__new__(DeveloperAgent)
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["market"].report_text in prompt
        assert all_prior_reports["product"].report_text in prompt
        assert all_prior_reports["art_direction"].report_text in prompt


# ---------------------------------------------------------------------------
# QA Agent (no search)
# ---------------------------------------------------------------------------

class TestQAAgent:
    @patch("council.agents.base.ChatAnthropic")
    def test_run_direct_invokes_llm(self, mock_llm_class, sample_idea, all_prior_reports):
        llm_mock = make_llm_mock("## QA Review\n\nTestability: good.")
        mock_llm_class.return_value = llm_mock

        agent = QAAgent()
        report = agent.run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "qa"
        llm_mock.invoke.assert_called_once()

    def test_prompt_includes_developer_report(self, sample_idea, all_prior_reports):
        agent = QAAgent.__new__(QAAgent)
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["developer"].report_text in prompt


# ---------------------------------------------------------------------------
# Synthesis Agent (no search)
# ---------------------------------------------------------------------------

class TestSynthesisAgent:
    @patch("council.agents.base.ChatAnthropic")
    def test_run_returns_verdict(self, mock_llm_class, sample_idea, all_prior_reports):
        llm_mock = make_llm_mock("## Verdict\n\n**VERDICT: GO**\n\nConfidence: high")
        mock_llm_class.return_value = llm_mock

        agent = SynthesisAgent()
        report = agent.run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "synthesis"
        assert "GO" in report.report_text

    def test_prompt_includes_all_five_reports(self, sample_idea, all_prior_reports):
        agent = SynthesisAgent.__new__(SynthesisAgent)
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        for key in ["market", "product", "art_direction", "developer", "qa"]:
            assert all_prior_reports[key].report_text in prompt
