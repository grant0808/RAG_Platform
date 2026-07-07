from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from foundry.core.config import Settings


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    provider: str

    def model_dump(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "provider": self.provider,
        }


class WebSearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        """Return web search results that can be used as fallback RAG context."""


class DisabledWebSearchProvider:
    provider = "none"

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        del query, max_results
        return []


class TavilyWebSearchProvider:
    provider = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        return [
            WebSearchResult(
                title=str(item.get("title") or "Untitled"),
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or item.get("snippet") or ""),
                provider=self.provider,
            )
            for item in payload.get("results", [])
            if isinstance(item, dict)
        ]


class DuckDuckGoWebSearchProvider:
    provider = "duckduckgo"

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        try:
            from langchain_community.tools import DuckDuckGoSearchRun
            from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
        except ImportError:
            return [
                WebSearchResult(
                    title="DuckDuckGoSearchRun is unavailable",
                    url="about:blank",
                    snippet=(
                        "DuckDuckGoSearchRun requires langchain-community and duckduckgo-search. "
                        f"Fallback was requested for query: {query}"
                    ),
                    provider=self.provider,
                )
            ][:max_results]

        wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results)
        search = DuckDuckGoSearchRun(api_wrapper=wrapper)
        try:
            raw = await search.ainvoke(query)
        except Exception as exc:
            return [
                WebSearchResult(
                    title="DuckDuckGo search failed",
                    url="about:blank",
                    snippet=(
                        "Uploaded documents and DuckDuckGo web search did not provide enough "
                        f"evidence. Error: {str(exc)[:300]}"
                    ),
                    provider=self.provider,
                )
            ][:max_results]
        if not raw:
            return []
        return [
            WebSearchResult(
                title="DuckDuckGo search result",
                url="https://duckduckgo.com/",
                snippet=str(raw),
                provider=self.provider,
            )
        ][:max_results]


def build_web_search_provider(settings: Settings) -> WebSearchProvider:
    provider = (settings.web_fallback_provider or settings.web_search_provider).lower()
    if provider in {"duckduckgo", "ddg"}:
        return DuckDuckGoWebSearchProvider()
    if provider == "tavily" and settings.tavily_api_key is not None:
        return TavilyWebSearchProvider(settings.tavily_api_key.get_secret_value())
    if provider == "none":
        return DisabledWebSearchProvider()
    return DuckDuckGoWebSearchProvider()
