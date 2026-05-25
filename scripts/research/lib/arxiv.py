"""arXiv client via export.arxiv.org Atom API. Stdlib XML parsing, no extra deps."""
import sys
import time
import requests
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

API_URL = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
USER_AGENT = "obsidian-second-brain-research/0.1"
MAX_RETRIES = 3
BACKOFF_SECONDS = (1, 3, 8)
POLITE_SLEEP = 3  # arXiv asks >= 3s between requests

DIRECT_SESSION = requests.Session()
DIRECT_SESSION.trust_env = False


def _strip_version(arxiv_id_url: str) -> str:
    tail = arxiv_id_url.rstrip("/").rsplit("/", 1)[-1]
    if "v" in tail:
        base, _, ver = tail.rpartition("v")
        if ver.isdigit():
            return base
    return tail


def call(query: str, *, max_results: int = 10, category: str | None = None) -> dict[str, Any]:
    """Search arXiv and return markdown list + citations.

    Returns {"text", "citations", "model": "arxiv", "raw"}.
    """
    if category:
        search_query = f"cat:{quote(category)}+AND+all:{quote(query)}"
    else:
        search_query = f"all:{quote(query)}"
    url = (f"{API_URL}?search_query={search_query}"
           f"&start=0&max_results={max_results}"
           f"&sortBy=submittedDate&sortOrder=descending")
    headers = {"User-Agent": USER_AGENT}

    last_err: Exception | None = None
    resp_text = ""
    succeeded = False
    for attempt in range(MAX_RETRIES):
        try:
            print(f"[arXiv] query: {query!r} (cat={category}, max={max_results})", file=sys.stderr)
            # Bypass system proxies; arXiv should direct-connect for reliability.
            r = DIRECT_SESSION.get(url, headers=headers, timeout=60)
            if r.status_code == 200:
                resp_text = r.text
                succeeded = True
                break
            if r.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                print(f"[arXiv {r.status_code}, retrying in {wait}s...]", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"arXiv API error {r.status_code}: {r.text[:500]}")
        except requests.RequestException as e:
            last_err = e
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            print(f"[arXiv network error: {e}, retrying in {wait}s...]", file=sys.stderr)
            time.sleep(wait)

    if not succeeded:
        raise RuntimeError(f"arXiv API failed after {MAX_RETRIES} retries: {last_err}")

    time.sleep(POLITE_SLEEP)

    root = ET.fromstring(resp_text)
    entries = root.findall("atom:entry", NS)

    lines: list[str] = []
    citations: list[dict[str, Any]] = []
    for e in entries:
        id_el = e.find("atom:id", NS)
        title_el = e.find("atom:title", NS)
        published_el = e.find("atom:published", NS)
        summary_el = e.find("atom:summary", NS)
        primary_el = e.find("arxiv:primary_category", NS)

        if id_el is None or not id_el.text:
            continue
        arxiv_id = _strip_version(id_el.text.strip())
        title = " ".join((title_el.text or "").split()) if title_el is not None else ""
        authors = [a.findtext("atom:name", default="", namespaces=NS) for a in e.findall("atom:author", NS)]
        authors_csv = ", ".join(a for a in authors if a)
        published = (published_el.text or "")[:10] if published_el is not None else ""
        summary = " ".join((summary_el.text or "").split()) if summary_el is not None else ""
        primary_category = primary_el.attrib.get("term", "") if primary_el is not None else ""
        all_cats = [c.attrib.get("term", "") for c in e.findall("atom:category", NS) if c.attrib.get("term")]

        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        snippet = summary[:500] + ("..." if len(summary) > 500 else "")

        lines.append(f"### [{title or '(no title)'}]({abs_url})")
        lines.append(f"- **Authors**: {authors_csv or 'N/A'}")
        lines.append(f"- **Submitted**: {published}")
        lines.append(f"- **Categories**: {primary_category}")
        lines.append(f"- **arXiv ID**: {arxiv_id} | PDF: {pdf_url}")
        lines.append(f"- **Abstract**: {snippet}")
        lines.append("")

        citations.append({
            "arxiv_id": arxiv_id,
            "url": abs_url,
            "title": title,
            "categories": all_cats or ([primary_category] if primary_category else []),
        })

    text = "\n".join(lines).rstrip() if lines else f"No arXiv results for: {query}"
    return {"text": text, "citations": citations, "model": "arxiv", "raw": {"xml": resp_text}}
