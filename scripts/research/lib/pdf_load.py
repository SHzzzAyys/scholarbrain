"""Unified paper text loader. Source string -> paper text ready for paper_extract.

Routing by prefix:
- "arxiv:<id>"    -> arxiv.download_pdf -> parse_pdf
- "pmid:<id>"     -> pubmed.pmid_to_pmc_pdf -> parse_pdf
                     Fallback: pubmed.fetch_by_pmid (abstract only)
- "doi:<doi>"     -> NotImplementedError (deferred to v0.4 via Unpaywall)
- "<file path>"   -> local PDF file

Output is wrapped with <FRONT_MATTER> + <BODY> markers matching paper_extract's
TASK_PROMPT expectations.

PDF parsing requires pymupdf, declared as optional extra:
    uv sync --extra pdf
"""
import sys
from pathlib import Path
from typing import Optional

from . import arxiv, pubmed

# Optional dependency: pymupdf (a.k.a. fitz) for PDF text extraction.
try:
    import fitz  # type: ignore[import-not-found]
    HAS_PYMUPDF = True
except ImportError:
    fitz = None  # type: ignore[assignment]
    HAS_PYMUPDF = False


def _ensure_pymupdf() -> None:
    if not HAS_PYMUPDF:
        raise RuntimeError(
            "PDF text extraction requires pymupdf.\n"
            "Install with: uv sync --extra pdf"
        )


def parse_pdf(pdf_path: Path) -> str:
    """Extract paper text from a local PDF.

    Wraps page 1 in <FRONT_MATTER> (where title/authors/journal/abstract usually
    live) and pages 2+ in <BODY>, matching paper_extract.TASK_PROMPT's expected
    sectioning. Empty PDFs return empty string (caller should check).
    """
    _ensure_pymupdf()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    if not pages:
        return ""

    front = pages[0]
    body = "\n\n".join(pages[1:]) if len(pages) > 1 else ""
    parts = [f"<FRONT_MATTER>\n{front}\n</FRONT_MATTER>"]
    if body:
        parts.append(f"<BODY>\n{body}\n</BODY>")
    return "\n\n".join(parts)


def load_text(source: str) -> str:
    """Resolve source string to paper text.

    Args:
        source: one of:
            - "arxiv:<id>"          download + parse arXiv PDF
            - "pmid:<id>"           PMC OA PDF if available, else PubMed abstract
            - "doi:<doi>"           NotImplementedError (v0.4)
            - "<path>" (no prefix)  local file path (PDF only for now)

    Returns:
        Paper text with <FRONT_MATTER> / <BODY> markers. If PMID falls back to
        abstract-only, returns the markdown-formatted abstract from fetch_by_pmid.
    """
    source = source.strip()
    if not source:
        raise ValueError("Empty source string")

    if source.startswith("arxiv:"):
        arxiv_id = source[len("arxiv:"):].strip()
        if not arxiv_id:
            raise ValueError("arxiv: prefix with empty ID")
        pdf_path = arxiv.download_pdf(arxiv_id)
        return parse_pdf(pdf_path)

    if source.startswith("pmid:"):
        pmid = source[len("pmid:"):].strip()
        if not pmid:
            raise ValueError("pmid: prefix with empty ID")
        pdf_path = pubmed.pmid_to_pmc_pdf(pmid)
        if pdf_path is not None:
            return parse_pdf(pdf_path)
        # Fallback: pull abstract
        print(
            f"[pdf_load] PMC OA PDF not available for PMID {pmid}, "
            "falling back to abstract-only",
            file=sys.stderr,
        )
        result = pubmed.fetch_by_pmid(pmid)
        if result is None:
            raise RuntimeError(f"PMID {pmid} not found in PubMed")
        return result["text"]

    if source.startswith("doi:"):
        raise NotImplementedError(
            "DOI resolution deferred to v0.4 (via Unpaywall). "
            "For now: convert to PMID with 'pmid:<id>' or download PDF manually "
            "and pass the local path."
        )

    # Local path
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Local PDF not found: {source}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Only .pdf local files supported, got {path.suffix}")
    return parse_pdf(path)


def detect_source_type(source: str) -> str:
    """Return one of 'arxiv', 'pmid', 'doi', 'local' for routing display."""
    source = source.strip()
    if source.startswith("arxiv:"):
        return "arxiv"
    if source.startswith("pmid:"):
        return "pmid"
    if source.startswith("doi:"):
        return "doi"
    return "local"
