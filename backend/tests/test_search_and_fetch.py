import pytest

from app.tools import web_fetch, web_search


@pytest.mark.asyncio
async def test_offline_search_returns_ranked_results():
    results = await web_search.web_search("retrieval augmented generation limitations", max_results=3)
    assert results
    assert all("title" in r and "url" in r for r in results)


@pytest.mark.asyncio
async def test_offline_fetch_uses_corpus_doc_without_network():
    results = await web_search.web_search("pgvector vector database", max_results=1)
    assert results
    doc = await web_fetch.fetch_webpage(results[0]["url"], offline_doc=results[0].get("_offline_doc"))
    assert doc["content"]
    assert doc["domain"] == "demo-corpus.local"


@pytest.mark.asyncio
async def test_fetch_webpage_refuses_private_hosts():
    with pytest.raises(web_fetch.FetchError):
        await web_fetch.fetch_webpage("http://127.0.0.1:9999/secret")
    with pytest.raises(web_fetch.FetchError):
        await web_fetch.fetch_webpage("http://localhost/secret")
