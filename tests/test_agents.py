"""
Unit tests for the council agents.

Agents are prompt authors; the language model is injected as a CouncilModel.
Tests pass a FakeModel that records the prompt and returns canned text — no
LangChain patching and no real API calls.
"""
from council.agents.base import BaseCouncilAgent, content_to_text
from council.agents.model import CouncilModel
from council.domain import AgentReport
from council.agents.art_direction import ArtDirectionAgent
from council.agents.developer import DeveloperAgent
from council.agents.market import MarketAgent
from council.agents.product import ProductAgent
from council.agents.qa import QAAgent
from council.agents.synthesis import SynthesisAgent


# ---------------------------------------------------------------------------
# A fake CouncilModel — the whole reason agent tests no longer touch LangChain.
# ---------------------------------------------------------------------------

class FakeModel:
    """Records the prompt/tools it was called with and returns canned text."""

    def __init__(self, output: str = "Mock model output."):
        self.output = output
        self.last_prompt: str | None = None
        self.last_tools: list | None = None
        self.calls = 0

    def complete(self, prompt: str, *, tools: list | None = None) -> str:
        self.calls += 1
        self.last_prompt = prompt
        self.last_tools = tools
        return self.output


# ---------------------------------------------------------------------------
# content_to_text
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


# ---------------------------------------------------------------------------
# BaseCouncilAgent contract
# ---------------------------------------------------------------------------

class TestBaseCouncilAgent:
    def test_agent_report_defaults(self):
        report = AgentReport(agent_name="test", report_text="hello")
        assert report.metadata == {}

    def test_fake_model_satisfies_council_model(self):
        # The seam is a runtime-checkable Protocol; the fake stands in for real.
        assert isinstance(FakeModel(), CouncilModel)

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
# Market Agent (search)
# ---------------------------------------------------------------------------

class TestMarketAgent:
    def test_run_returns_agent_report(self, sample_idea):
        model = FakeModel("## Market Report\n\nLarge market.")
        report = MarketAgent(model=model).run(idea=sample_idea, prior_reports={})

        assert report.agent_name == "market"
        assert "Market" in report.report_text
        assert isinstance(report.metadata, dict)
        assert sample_idea in model.last_prompt  # the built prompt reached the model

    def test_search_agent_forwards_tools_to_model(self, sample_idea):
        model = FakeModel()
        MarketAgent(model=model).run(idea=sample_idea, prior_reports={})
        assert model.last_tools  # search agents pass their tools through the seam

    def test_prompt_contains_idea(self, sample_idea):
        agent = MarketAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, {})
        assert sample_idea in prompt
        assert "market size" in prompt.lower()


# ---------------------------------------------------------------------------
# Product Agent (search)
# ---------------------------------------------------------------------------

class TestProductAgent:
    def test_prompt_includes_market_context(self, sample_idea, sample_market_report):
        agent = ProductAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, {"market": sample_market_report})
        assert sample_market_report.report_text in prompt

    def test_prompt_without_market_still_works(self, sample_idea):
        agent = ProductAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, {})
        assert sample_idea in prompt


# ---------------------------------------------------------------------------
# Art Direction Agent (search)
# ---------------------------------------------------------------------------

class TestArtDirectionAgent:
    def test_prompt_includes_product_context(self, sample_idea, all_prior_reports):
        agent = ArtDirectionAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["product"].report_text in prompt

    def test_agent_name(self):
        assert ArtDirectionAgent.agent_name == "art_direction"


# ---------------------------------------------------------------------------
# Developer Agent (no search)
# ---------------------------------------------------------------------------

class TestDeveloperAgent:
    def test_run_direct_calls_model_without_tools(self, sample_idea, all_prior_reports):
        model = FakeModel("## Tech Plan\n\nUse FastAPI.")
        report = DeveloperAgent(model=model).run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "developer"
        assert "Tech Plan" in report.report_text
        assert model.calls == 1
        assert model.last_tools is None  # no-search agents call the model toolless

    def test_prompt_includes_all_three_prior_reports(self, sample_idea, all_prior_reports):
        agent = DeveloperAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["market"].report_text in prompt
        assert all_prior_reports["product"].report_text in prompt
        assert all_prior_reports["art_direction"].report_text in prompt


# ---------------------------------------------------------------------------
# QA Agent (no search)
# ---------------------------------------------------------------------------

class TestQAAgent:
    def test_run_direct_calls_model(self, sample_idea, all_prior_reports):
        model = FakeModel("## QA Review\n\nTestability: good.")
        report = QAAgent(model=model).run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "qa"
        assert model.calls == 1

    def test_prompt_includes_developer_report(self, sample_idea, all_prior_reports):
        agent = QAAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        assert all_prior_reports["developer"].report_text in prompt


# ---------------------------------------------------------------------------
# Synthesis Agent (no search)
# ---------------------------------------------------------------------------

class TestSynthesisAgent:
    def test_run_returns_verdict(self, sample_idea, all_prior_reports):
        model = FakeModel("## Verdict\n\n**VERDICT: GO**\n\nConfidence: high")
        report = SynthesisAgent(model=model).run(idea=sample_idea, prior_reports=all_prior_reports)

        assert report.agent_name == "synthesis"
        assert "GO" in report.report_text

    def test_prompt_includes_all_five_reports(self, sample_idea, all_prior_reports):
        agent = SynthesisAgent(model=FakeModel())
        prompt = agent._build_prompt(sample_idea, all_prior_reports)
        for key in ["market", "product", "art_direction", "developer", "qa"]:
            assert all_prior_reports[key].report_text in prompt
