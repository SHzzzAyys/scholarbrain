"""Semantic Scholar Graph API client. Stdlib only (urllib.request, json, time)."""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"
USER_AGENT = "para-prot-signal/1.0"
MAX_RETRIES = 3
BACKOFF_SECONDS = (1, 3, 8)
POLITE_SLEEP = 0.5  # 100 req / 5 min public rate limit

SEARCH_FIELDS = "paperId,title,year,abstract,authors,externalIds,citationCount"
FETCH_FIELDS = "paperId,title,year,abstract,authors,externalIds,citationCount,fieldsOfStudy"


def _get(url: str) -> dict[str, Any]:
    """HTTP GET with retries (5xx only). Returns parsed JSON. Raises RuntimeError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 504):
                wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                print(f"[SemanticScholar {e.code}, retrying in {wait}s...]", file=sys.stderr)
                last_err = e
                time.sleep(wait)
                continue
            # 4xx errors are non-retryable
            raise RuntimeError(f"Semantic Scholar API error {e.code}: {e.read()[:500].decode('utf-8', errors='replace')}") from e
        except urllib.error.URLError as e:
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            print(f"[SemanticScholar network error: {e.reason}, retrying in {wait}s...]", file=sys.stderr)
            last_err = e
            time.sleep(wait)
    raise RuntimeError(f"Semantic Scholar request failed after {MAX_RETRIES} retries: {last_err}")


def _normalise_paper(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw API paper dict into a consistent output dict."""
    authors_raw = raw.get("authors") or []
    author_names = [a.get("name", "") for a in authors_raw if a.get("name")]
    return {
        "paperId": raw.get("paperId", ""),
        "title": raw.get("title", ""),
        "year": raw.get("year"),
        "abstract": raw.get("abstract", ""),
        "authors": author_names,
        "externalIds": raw.get("externalIds") or {},
        "citationCount": raw.get("citationCount"),
        "fieldsOfStudy": raw.get("fieldsOfStudy") or [],
    }


def search_papers(query: str, limit: int = 10) -> list[dict]:
    """Search papers via Semantic Scholar Graph API.

    Returns a list of dicts, each containing:
        paperId, title, year, abstract, authors (list of name strings),
        externalIds (dict: DOI, ArXiv, PubMed, etc.), citationCount.
    Returns [] on failure.
    """
    params = urllib.parse.urlencode({
        "query": query,
        "limit": limit,
        "fields": SEARCH_FIELDS,
    })
    url = f"{BASE_URL}/search?{params}"
    print(f"[SemanticScholar] search: {query!r} (limit={limit})", file=sys.stderr)
    try:
        data = _get(url)
    except RuntimeError as e:
        print(f"[SemanticScholar] search_papers failed: {e}", file=sys.stderr)
        return []
    time.sleep(POLITE_SLEEP)
    papers_raw = data.get("data") or []
    return [_normalise_paper(p) for p in papers_raw]


def fetch_paper(identifier: str) -> Optional[dict]:
    """Fetch a single paper by identifier.

    Accepted identifier forms:
        - Semantic Scholar Paper ID (plain hash)
        - "DOI:10.1234/xxx"
        - "ARXIV:2106.xxxxx"
        - "PMID:12345678"

    Returns a dict with the same keys as search_papers() entries, or None on failure.
    """
    params = urllib.parse.urlencode({"fields": FETCH_FIELDS})
    url = f"{BASE_URL}/{identifier}?{params}"
    print(f"[SemanticScholar] fetch: {identifier!r}", file=sys.stderr)
    try:
        data = _get(url)
    except RuntimeError as e:
        print(f"[SemanticScholar] fetch_paper failed: {e}", file=sys.stderr)
        return None
    time.sleep(POLITE_SLEEP)
    return _normalise_paper(data)


# ============================================================
# CLI smoke test
# ============================================================
if __name__ == "__main__":
    results = search_papers("Toxoplasma gondii CRISPR", limit=3)
    for r in results:
        print(r.get("title"), r.get("year"))
