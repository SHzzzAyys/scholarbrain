"""PubMed client via NCBI E-utilities (esearch + esummary + efetch + elink). No LLM."""
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from xml.etree import ElementTree as ET

from .config import NCBI_EMAIL, PUBMED_API_KEY

TOOL = "obsidian-second-brain-research"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
DEFAULT_PMC_CACHE = Path.home() / ".cache" / "obsidian-second-brain" / "pmc"
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


# ============================================================
# Single-PMID fetch + PMC OA PDF download (v0.2 Day 2)
# ============================================================
def fetch_by_pmid(pmid: str, *, fetch_abstract: bool = True) -> Optional[dict]:
    """Fetch a single PubMed record by exact PMID. Same return shape as call().

    Returns None if PMID does not exist.
    """
    try:
        key_val = PUBMED_API_KEY() if callable(PUBMED_API_KEY) else PUBMED_API_KEY
    except Exception:
        key_val = ""
    has_key = bool(key_val)

    print(f"[PubMed] fetch_by_pmid: {pmid}", file=sys.stderr)
    sm_params = {**_base_params(has_key), "db": "pubmed", "id": pmid, "retmode": "json"}
    rs = _get(ESUMMARY_URL, sm_params)
    _sleep_rate(has_key)
    sm_data = rs.json()
    result = sm_data.get("result", {}) or {}
    s = result.get(pmid, {})
    if not s:
        return None

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
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    lines = [
        f"### [{title or '(no title)'}]({url})",
        f"- **Authors**: {first3}",
        f"- **Journal**: {journal} ({year})",
        f"- **PMID**: {pmid} | DOI: {doi or 'N/A'}",
    ]
    abstract = ""
    if fetch_abstract:
        ef_params = {**_base_params(has_key), "db": "pubmed",
                     "id": pmid, "rettype": "abstract", "retmode": "xml"}
        rf = _get(EFETCH_URL, ef_params)
        _sleep_rate(has_key)
        abstracts_dict = _parse_abstracts(rf.text)
        abstract = abstracts_dict.get(pmid, "")
        if abstract:
            lines.append(f"- **Abstract**: {abstract}")

    return {
        "text": "\n".join(lines),
        "citations": [{"pmid": pmid, "url": url, "title": title, "year": year}],
        "model": "pubmed",
        "raw": {"esummary": sm_data, "abstract_text": abstract},
    }


def pmid_to_pmc_pdf(pmid: str, cache_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolve PMID -> PMC ID -> download PMC OA PDF. Returns Path or None.

    Returns None silently (with stderr explanation) on any of:
    - PMID has no PMC mapping
    - PMC article not in Open Access subset
    - OA record has no PDF link
    - PDF HTTP download fails

    Caller should fallback to fetch_by_pmid() abstract on None.
    """
    try:
        key_val = PUBMED_API_KEY() if callable(PUBMED_API_KEY) else PUBMED_API_KEY
    except Exception:
        key_val = ""
    has_key = bool(key_val)

    # Step 1: elink PMID -> PMC ID
    elink_params = {**_base_params(has_key), "dbfrom": "pubmed", "db": "pmc",
                    "id": pmid, "retmode": "json"}
    print(f"[PubMed] elink PMID->PMC: {pmid}", file=sys.stderr)
    try:
        r = _get(ELINK_URL, elink_params)
        _sleep_rate(has_key)
        data = r.json()
    except Exception as e:
        print(f"[PubMed] elink failed: {e}", file=sys.stderr)
        return None

    pmc_id: Optional[str] = None
    for linkset in data.get("linksets", []) or []:
        for lsdb in linkset.get("linksetdbs", []) or []:
            if lsdb.get("linkname") == "pubmed_pmc":
                links = lsdb.get("links", []) or []
                if links:
                    pmc_id = str(links[0])
                    break
        if pmc_id:
            break
    if not pmc_id:
        print(f"[PubMed] PMID {pmid} has no PMC mapping", file=sys.stderr)
        return None

    # Step 2: OA API for PDF link
    print(f"[PubMed] OA query: PMC{pmc_id}", file=sys.stderr)
    try:
        oa_params = {"id": f"PMC{pmc_id}"}
        r_oa = DIRECT_SESSION.get(OA_URL, params=oa_params, headers=_ua(), timeout=30)
        if r_oa.status_code != 200:
            print(f"[PubMed] OA API {r_oa.status_code}", file=sys.stderr)
            return None
        root = ET.fromstring(r_oa.text)
        # OA returns either <records><record>...</record></records> or <error>...</error>
        err = root.find(".//error")
        if err is not None:
            print(f"[PubMed] PMC{pmc_id} not in OA subset: {err.text}", file=sys.stderr)
            return None
        record = root.find(".//record")
        if record is None:
            print(f"[PubMed] PMC{pmc_id} no OA record", file=sys.stderr)
            return None
        pdf_link = None
        for link in record.findall("link"):
            if link.attrib.get("format") == "pdf":
                pdf_link = link.attrib.get("href")
                break
        if not pdf_link:
            print(f"[PubMed] PMC{pmc_id} OA record has no PDF link", file=sys.stderr)
            return None
    except (requests.RequestException, ET.ParseError) as e:
        print(f"[PubMed] OA parse failed: {e}", file=sys.stderr)
        return None

    # FTP -> HTTPS (NCBI's OA still returns ftp:// in href)
    if pdf_link.startswith("ftp://"):
        pdf_link = pdf_link.replace("ftp://", "https://", 1)

    # Step 3: download
    if cache_dir is None:
        cache_dir = DEFAULT_PMC_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"PMC{pmc_id}.pdf"
    if target.exists() and target.stat().st_size > 1000:
        print(f"[PubMed] PDF cache hit: {target} ({target.stat().st_size} bytes)", file=sys.stderr)
        return target

    print(f"[PubMed] downloading PDF: {pdf_link}", file=sys.stderr)
    try:
        r_pdf = DIRECT_SESSION.get(pdf_link, headers=_ua(), timeout=120)
        if r_pdf.status_code != 200:
            print(f"[PubMed] PDF download {r_pdf.status_code}", file=sys.stderr)
            return None
        if len(r_pdf.content) < 5000:
            print(f"[PubMed] PDF suspiciously small: {len(r_pdf.content)} bytes", file=sys.stderr)
            return None
        target.write_bytes(r_pdf.content)
        print(f"[PubMed] PDF saved: {target} ({target.stat().st_size} bytes)", file=sys.stderr)
        return target
    except requests.RequestException as e:
        print(f"[PubMed] PDF download failed: {e}", file=sys.stderr)
        return None
