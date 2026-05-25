"""PubMed client via NCBI E-utilities (esearch + esummary + efetch). No LLM."""
import sys
import time
import requests
from typing import Any
from xml.etree import ElementTree as ET

from .config import NCBI_EMAIL, PUBMED_API_KEY

TOOL = "obsidian-second-brain-research"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
MAX_RETRIES = 3
BACKOFF_SECONDS = (1, 3, 8)
ESUMMARY_BATCH = 200

DIRECT_SESSION = requests.Session()
DIRECT_SESSION.trust_env = False


def _ua() -> dict[str, str]:
    return {"User-Agent": f"{TOOL}/0.1 (mailto:{NCBI_EMAIL()})"}


def _sleep_rate(has_key: bool) -> None:
    time.sleep(0.11 if has_key else 0.34)


def _get(url: str, params: dict[str, Any]) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            # Bypass system proxies; NCBI should direct-connect for reliability.
            r = DIRECT_SESSION.get(url, params=params, headers=_ua(), timeout=60)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                print(f"[PubMed 429, sleeping 5s...]", file=sys.stderr)
                time.sleep(5)
                continue
            if r.status_code in (500, 502, 503, 504):
                wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                print(f"[PubMed {r.status_code}, retrying in {wait}s...]", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"PubMed API error {r.status_code}: {r.text[:500]}")
        except requests.RequestException as e:
            last_err = e
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            print(f"[PubMed network error: {e}, retrying in {wait}s...]", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"PubMed request failed after {MAX_RETRIES} retries: {last_err}")


def _base_params(has_key: bool) -> dict[str, Any]:
    p: dict[str, Any] = {"email": NCBI_EMAIL(), "tool": TOOL}
    if has_key:
        p["api_key"] = PUBMED_API_KEY()
    return p


def _parse_abstracts(xml_text: str) -> dict[str, str]:
    """Map PMID -> abstract text from efetch XML."""
    out: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for art in root.iter("PubmedArticle"):
        pmid_el = art.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()
        chunks: list[str] = []
        for ab in art.iter("AbstractText"):
            label = ab.attrib.get("Label")
            txt = "".join(ab.itertext()).strip()
            if txt:
                chunks.append(f"{label}: {txt}" if label else txt)
        if chunks:
            out[pmid] = " ".join(chunks)
    return out


def call(query: str, *, max_results: int = 10, fetch_abstracts: bool = True) -> dict[str, Any]:
    """Search PubMed and return markdown list + citations.

    Returns {"text", "citations", "model": "pubmed", "raw"}.
    """
    try:
        key_val = PUBMED_API_KEY() if callable(PUBMED_API_KEY) else PUBMED_API_KEY
    except Exception:
        key_val = ""
    has_key = bool(key_val)

    es_params = {**_base_params(has_key), "db": "pubmed", "term": query,
                 "retmax": max_results, "retmode": "json"}
    print(f"[PubMed] esearch: {query!r} (retmax={max_results})", file=sys.stderr)
    r = _get(ESEARCH_URL, es_params)
    _sleep_rate(has_key)
    es_data = r.json()
    raw_ids = es_data.get("esearchresult", {}).get("idlist", []) or []
    seen: set[str] = set()
    pmids: list[str] = []
    for pid in raw_ids:
        if pid and pid not in seen:
            seen.add(pid)
            pmids.append(pid)
    if not pmids:
        return {"text": f"No PubMed results for: {query}", "citations": [],
                "model": "pubmed", "raw": {"esearch": es_data}}

    summaries: dict[str, dict[str, Any]] = {}
    raw_summary_batches: list[dict[str, Any]] = []
    for i in range(0, len(pmids), ESUMMARY_BATCH):
        batch = pmids[i:i + ESUMMARY_BATCH]
        sm_params = {**_base_params(has_key), "db": "pubmed",
                     "id": ",".join(batch), "retmode": "json"}
        print(f"[PubMed] esummary: batch {i//ESUMMARY_BATCH + 1} ({len(batch)} PMIDs)", file=sys.stderr)
        rs = _get(ESUMMARY_URL, sm_params)
        _sleep_rate(has_key)
        sm_data = rs.json()
        raw_summary_batches.append(sm_data)
        result = sm_data.get("result", {}) or {}
        for pid in batch:
            if pid in result:
                summaries[pid] = result[pid]

    abstracts: dict[str, str] = {}
    raw_abstracts_text = ""
    if fetch_abstracts:
        ef_params = {**_base_params(has_key), "db": "pubmed",
                     "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
        print(f"[PubMed] efetch abstracts: {len(pmids)} PMIDs", file=sys.stderr)
        rf = _get(EFETCH_URL, ef_params)
        _sleep_rate(has_key)
        raw_abstracts_text = rf.text
        abstracts = _parse_abstracts(raw_abstracts_text)

    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for pid in pmids:
        s = summaries.get(pid, {})
        title = (s.get("title") or "").strip().rstrip(".")
        authors_list = s.get("authors") or []
        author_names = [a.get("name", "") for a in authors_list if a.get("name")]
        first3 = ", ".join(author_names[:3])
        if len(author_names) > 3:
            first3 += " et al."
        elif not first3:
            first3 = "N/A"
        journal = s.get("fulljournalname") or s.get("source") or "N/A"
        pubdate = s.get("pubdate") or ""
        year = pubdate.split(" ")[0][:4] if pubdate else ""
        doi = ""
        for aid in s.get("articleids", []) or []:
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
        lines.append(f"### [{title or '(no title)'}]({url})")
        lines.append(f"- **Authors**: {first3}")
        lines.append(f"- **Journal**: {journal} ({year})")
        lines.append(f"- **PMID**: {pid} | DOI: {doi or 'N/A'}")
        if fetch_abstracts:
            ab = abstracts.get(pid, "").strip()
            if ab:
                snippet = ab[:500] + ("..." if len(ab) > 500 else "")
            else:
                snippet = "(no abstract)"
            lines.append(f"- **Abstract**: {snippet}")
        lines.append("")
        citations.append({"pmid": pid, "url": url, "title": title, "year": year})

    text = "\n".join(lines).rstrip()
    return {
        "text": text,
        "citations": citations,
        "model": "pubmed",
        "raw": {"esearch": es_data, "esummary": raw_summary_batches, "efetch_xml": raw_abstracts_text},
    }
