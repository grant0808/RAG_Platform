from __future__ import annotations

import asyncio
import re

from foundry.core.config import Settings
from foundry.services.web_search import WebSearchResult


class DuckDuckGoSearchFallback:
    provider = "duckduckgo"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        if not self.settings.web_fallback_enabled:
            return []
        limit = max_results or self.settings.duckduckgo_max_results
        try:
            return await asyncio.to_thread(self._search_sync, query, limit)
        except Exception:
            return []

    def _search_sync(self, query: str, limit: int) -> list[WebSearchResult]:
        from langchain_community.tools import DuckDuckGoSearchRun

        search = DuckDuckGoSearchRun()
        raw = search.run(query)
        if not raw:
            return []
        snippets = self._split_results(str(raw), limit)
        return [
            WebSearchResult(
                title=f"DuckDuckGo result {index}",
                url="",
                snippet=snippet,
                provider=self.provider,
            )
            for index, snippet in enumerate(snippets, start=1)
        ]

    @staticmethod
    def _split_results(raw: str, limit: int) -> list[str]:
        parts = [part.strip() for part in re.split(r"\n+|(?<=\.)\s+(?=[A-Z가-힣])", raw)]
        snippets = [part for part in parts if part]
        if not snippets:
            snippets = [raw.strip()]
        return snippets[:limit]
