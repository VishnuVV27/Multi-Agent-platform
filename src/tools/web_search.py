from typing import List, Dict, Any
import asyncio
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single web search result."""
    title: str
    url: str
    snippet: str
    position: int


class WebSearchTool:
    """Web search tool backed by DuckDuckGo (no API key required)."""

    TOOL_ID = "web_search"
    TOOL_NAME = "Web Search"
    DESCRIPTION = "Search the internet for information"
    RISK_LEVEL = "low"
    CATEGORY = "information"

    async def execute(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Execute a web search.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            {
                "success": bool,
                "query": str,
                "results": List[SearchResult],
                "count": int
            }
        """
        try:
            results = await self._search_duckduckgo(query, max_results)

            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "source": "duckduckgo",
            }

        except Exception as e:
            logger.warning(f"Web search failed for '{query}': {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "results": [],
                "count": 0,
                "note": (
                    "Live search unavailable (network or rate limit). "
                    "Answer from model knowledge and say so."
                ),
            }

    async def _search_duckduckgo(
        self, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search DuckDuckGo via the ddgs package.

        ddgs is synchronous, so run it in a thread to avoid blocking the
        event loop (this executes inside Temporal activity workers).
        """
        def _search_sync() -> List[Dict[str, Any]]:
            from ddgs import DDGS

            raw = DDGS().text(query, max_results=max_results)
            results = []
            for i, item in enumerate(raw, start=1):
                results.append(
                    {
                        "position": i,
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "snippet": item.get("body", ""),
                    }
                )
            return results

        return await asyncio.to_thread(_search_sync)

    def get_manifest(self) -> Dict[str, Any]:
        """Return tool metadata."""
        return {
            "tool_id": self.TOOL_ID,
            "tool_name": self.TOOL_NAME,
            "description": self.DESCRIPTION,
            "risk_level": self.RISK_LEVEL,
            "category": self.CATEGORY,
            "input_schema": {
                "query": "string (search query)",
                "max_results": "integer (max 10)",
            },
        }
