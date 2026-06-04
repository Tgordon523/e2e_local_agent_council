import os

from langchain_core.tools import BaseTool


def build_search_tool() -> BaseTool:
    """Return TavilySearch if TAVILY_API_KEY is set, else DuckDuckGoSearchRun."""
    if os.environ.get("TAVILY_API_KEY"):
        from langchain_tavily import TavilySearch
        return TavilySearch(max_results=5)
    from langchain_community.tools import DuckDuckGoSearchRun
    return DuckDuckGoSearchRun()
