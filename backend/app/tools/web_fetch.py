"""
fetch_webpage / extract_content tool.

Fetches a URL, strips nav/ads/script/style, and pulls out title, author,
published date (best-effort, from common meta tags), and domain. For
offline-provider search results, the corpus document is used directly
instead of an HTTP fetch (there is nothing to fetch — the URL is a
placeholder demo-corpus identifier), which is the correct behavior for
that provider rather than a special-cased shortcut.

Includes basic SSRF protection: only http(s) schemes, and localhost /
link-local / private-range hosts are rejected unless the URL came from
the offline corpus.
"""
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings


class FetchError(RuntimeError):
    pass


def _is_private_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True  # unresolvable -> treat as unsafe, fail closed
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _guard_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise FetchError("URL has no hostname")
    if parsed.hostname == "localhost" or _is_private_host(parsed.hostname):
        raise FetchError("Refusing to fetch a private/internal address (SSRF protection)")


def _extract_readable(html: str) -> tuple[str, str | None, str | None]:
    """Returns (text, author, published_date) best-effort."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    author = None
    for sel in [
        {"name": "author"}, {"property": "article:author"}, {"name": "twitter:creator"},
    ]:
        meta = soup.find("meta", attrs=sel)
        if meta and meta.get("content"):
            author = meta["content"]
            break

    published = None
    for sel in [
        {"property": "article:published_time"}, {"name": "date"}, {"name": "pubdate"},
    ]:
        meta = soup.find("meta", attrs=sel)
        if meta and meta.get("content"):
            published = meta["content"]
            break

    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator=" ", strip=True) if main else soup.get_text(" ", strip=True)
    text = " ".join(text.split())
    return text, author, published


async def fetch_webpage(url: str, *, offline_doc: dict | None = None) -> dict:
    settings = get_settings()

    if offline_doc is not None:
        return {
            "title": offline_doc["title"],
            "content": offline_doc["content"][: settings.max_document_chars],
            "author": offline_doc.get("author"),
            "published_date": offline_doc.get("published_date"),
            "domain": offline_doc.get("domain", urlparse(url).hostname or ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    _guard_url(url)
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds, follow_redirects=True,
        headers={"User-Agent": "ResearchPilotAI/1.0 (+research-agent)"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content) > 5_000_000:
            raise FetchError("Document exceeds maximum allowed size")
        text, author, published = _extract_readable(resp.text)
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else url

    return {
        "title": title,
        "content": text[: settings.max_document_chars],
        "author": author,
        "published_date": published,
        "domain": urlparse(url).hostname or "",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
