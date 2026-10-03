"""
web_search tool.

SEARCH_PROVIDER=tavily      -> https://api.tavily.com
SEARCH_PROVIDER=brave       -> Brave Search API
SEARCH_PROVIDER=duckduckgo  -> DuckDuckGo HTML endpoint (no key required)
SEARCH_PROVIDER=offline     -> local demo corpus (default; zero network)

Every provider returns the same shape: a list of {title, url, snippet}.
Nothing downstream cares which provider produced it.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_settings

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "corpus" / "corpus.json"


class SearchError(RuntimeError):
    pass


async def _search_tavily(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise SearchError("TAVILY_API_KEY is not set")
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": settings.tavily_api_key, "query": query, "max_results": max_results},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in data.get("results", [])[:max_results]
        ]


async def _search_brave(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    if not settings.brave_api_key:
        raise SearchError("BRAVE_API_KEY is not set")
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": settings.brave_api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])[:max_results]
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
            for r in results
        ]


async def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
        resp.raise_for_status()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result in soup.select(".result")[:max_results]:
            link = result.select_one(".result__a")
            snippet = result.select_one(".result__snippet")
            if link:
                results.append({
                    "title": link.get_text(strip=True),
                    "url": link.get("href", ""),
                    "snippet": snippet.get_text(strip=True) if snippet else "",
                })
        return results


_CORPUS_CACHE: list[dict] | None = None


def _load_corpus() -> list[dict]:
    global _CORPUS_CACHE
    if _CORPUS_CACHE is None:
        _CORPUS_CACHE = json.loads(CORPUS_PATH.read_text())
    return _CORPUS_CACHE


async def _search_offline(query: str, max_results: int) -> list[dict]:
    """Real TF-IDF ranked retrieval over the bundled demo corpus."""
    docs = _load_corpus()
    corpus_texts = [f"{d['title']} {d['content']}" for d in docs]
    vec = TfidfVectorizer(stop_words="english").fit_transform([query] + corpus_texts)
    sims = cosine_similarity(vec[0:1], vec[1:]).flatten()
    ranked = sorted(zip(docs, sims), key=lambda x: x[1], reverse=True)
    results = []
    for doc, score in ranked[:max_results]:
        if score <= 0.02:
            continue
        results.append({
            "title": doc["title"],
            "url": doc["url"],
            "snippet": doc["content"][:220] + "...",
            "_offline_doc": doc,  # carried through so web_fetch doesn't need to re-fetch
        })
    return results


PROVIDERS = {
    "tavily": _search_tavily,
    "brave": _search_brave,
    "duckduckgo": _search_duckduckgo,
    "offline": _search_offline,
}


async def web_search(query: str, max_results: int | None = None) -> list[dict]:
    settings = get_settings()
    max_results = max_results or settings.max_sources_per_query
    provider = settings.search_provider
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise SearchError(f"Unknown SEARCH_PROVIDER: {provider}")
    try:
        return await fn(query, max_results)
    except SearchError:
        raise
    except Exception as exc:  # network failure, rate limit, etc.
        raise SearchError(f"{provider} search failed: {exc}") from exc
