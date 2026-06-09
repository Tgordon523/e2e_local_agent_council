import pytest

from council.agents.base import AgentReport


@pytest.fixture
def sample_idea():
    return "A subscription service for personalized dog food"


@pytest.fixture
def sample_market_report():
    return AgentReport(
        agent_name="market",
        report_text="## Market Analysis\n\nThe pet food market is $50B globally with 8% CAGR.",
        metadata={"queries": ["dog food market size 2024"]},
    )


@pytest.fixture
def all_prior_reports():
    return {
        "market": AgentReport("market", "Market is large and growing."),
        "product": AgentReport("product", "Product landscape is moderately competitive."),
        "art_direction": AgentReport("art_direction", "Clean design opportunity with mobile focus."),
        "developer": AgentReport("developer", "Medium complexity. Python + FastAPI recommended."),
        "qa": AgentReport("qa", "Testability is good. Main risk: third-party API reliability."),
    }
