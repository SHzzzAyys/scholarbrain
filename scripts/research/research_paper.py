#!/usr/bin/env python3
"""/research-paper <source> -- extract a paper to a structured 6-module vault note.

Sources:
    arxiv:<id>          arXiv paper by ID (e.g., arxiv:1706.03762)
    pmid:<id>           PubMed paper by PMID (e.g., pmid:40830525)
    doi:<doi>           NotImplementedError (deferred to v0.4 via Unpaywall)
    <local path>        local PDF file

Pipeline:
    1. Load paper text via lib.pdf_load (downloads PDF + parses with pymupdf,
       or falls back to PubMed abstract if PMC OA PDF is unavailable)
    2. Extract 6-module schema via lib.paper_extract (DeepSeek + vault _DOMAIN.md)
    3. Write to <vault>/Research/Papers/<YYYY-MM-DD>__<author-year>__<title>.md
    4. Best-effort PushGate notification

Output: prints the saved file path to stdout (parseable by callers).
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from .lib import paper_extract, pdf_load, pushgate
from .lib.config import VAULT_PATH


def _looks_truncated(result: paper_extract.ExtractionResult) -> bool:
    """Detect JSON truncation from DeepSeek's 8k output cap.

    Signals: _missing contains JSON_PARSE_FAILED, _raw_json has unbalanced braces,
    or _raw_json tail ends mid-token.
    """
    if "JSON_PARSE_FAILED" not in result._missing:
        return False
    raw = (result._raw_json or "").rstrip()
    if not raw:
        return False
    # Tail-character clues
    if raw[-1] in (",", "{", "[", ":", '"'):
        return True
    # Unbalanced braces (more { than }) means JSON was cut off
    if raw.count("{") > raw.count("}"):
        return True
    return False


# ============================================================
# Slug / filename helpers
# ============================================================
def _slug(text: str, max_len: int = 40) -> str:
    """Lowercase, alnum + hyphen, truncated to max_len."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-")
    return text[:max_len] or "untitled"


def _first_author_lastname(authors: list[str]) -> str:
    """Best-effort lastname extraction.

    PubMed format: 'Zheng XN' -> 'zheng'
    Western format: 'John Smith' -> 'smith'
    Single token: 'Vaswani' -> 'vaswani'
    """
    if not authors:
        return "anon"
    first = (authors[0] or "").strip()
    if not first:
        return "anon"
    tokens = first.split()
    # If 2 tokens and second looks like initials (all caps short), first is lastname
    if len(tokens) >= 2 and tokens[-1].isupper() and len(tokens[-1]) <= 3:
        return _slug(tokens[0], 20)
    # Otherwise assume western order, take last token
    return _slug(tokens[-1], 20)


def _first_author_year(result: paper_extract.ExtractionResult) -> str:
    """Build 'lastname-year' identifier, falls back gracefully."""
    last = _first_author_lastname(result.metadata.authors or [])
    year = (result.metadata.year or "unknown").strip() or "unknown"
    return f"{last}-{year}"


# ============================================================
# YAML frontmatter
# ============================================================
def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v) if v is not None else ""
    # Quote if contains YAML-significant chars, leading/trailing whitespace, or is empty
    if not s or s != s.strip() or any(c in s for c in ':#&*?[]{},\n'):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def _yaml_kv(key: str, value) -> str:
    if isinstance(value, list):
        if not value:
            return f"{key}: []"
        return f"{key}:\n" + "\n".join(f"  - {_yaml_scalar(v)}" for v in value)
    return f"{key}: {_yaml_scalar(value)}"


def build_frontmatter(result: paper_extract.ExtractionResult, source: str) -> dict:
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": "research-paper",
        "source": source,
        "title": result.metadata.title,
        "first_author": result.metadata.authors[0] if result.metadata.authors else "",
        "year": result.metadata.year,
        "journal": result.metadata.journal,
        "doi": result.metadata.doi,
        "model_organism": result.metadata.model_organism,
        "method_tags": result.technical_route.method_tags,
        "result_direction": result.main_results.result_direction,
        "novelty_type": result.innovations.actual_novelty.type,
        "position_in_field": result.relation_to_literature.position_in_field,
        # User-curated layer (left empty for the user to fill)
        "user_relevance": "",
        "research_priority": "",
        "read_status": "skimmed",
        "tags": (
            ["research", "research-paper"]
            + [_slug(t, 30) for t in result.technical_route.method_tags[:3]]
        ),
        "ai-first": True,
    }


# ============================================================
# Body (6-module markdown)
# ============================================================
def build_body(result: paper_extract.ExtractionResult, source: str) -> str:
    now = datetime.now()
    preamble = (
        f"For future Claude: This is a 6-module structured extraction of an academic paper "
        f"performed on {now.strftime('%Y-%m-%d %H:%M')} from source `{source}`. "
        f"Extracted by `lib.paper_extract` using DeepSeek + the vault's `_DOMAIN.md`. "
        f"Sections capture purpose / method / results / innovations / limitations / literature position. "
        f"Use this card as the canonical reference for this paper in the vault. "
        f"`user_relevance` / `research_priority` / `read_status` frontmatter fields are for human curation."
    )

    parts: list[str] = [f"## For future Claude\n\n{preamble}\n"]

    # Metadata
    md = result.metadata
    parts.append("## Metadata\n")
    parts.append(f"- **Title**: {md.title or '_(missing)_'}")
    parts.append(f"- **Authors**: {', '.join(md.authors) if md.authors else '_(missing)_'}")
    parts.append(f"- **Journal**: {md.journal or '_(missing)_'} ({md.year or '?'})")
    if md.doi:
        parts.append(f"- **DOI**: {md.doi}")
    if md.model_organism:
        parts.append(f"- **Model organism**: `{md.model_organism}`")
    parts.append(f"- **Source**: `{source}`")
    parts.append("")

    # Research Purpose
    rp = result.research_purpose
    parts.append("## Research Purpose\n")
    if rp.core_question:
        parts.append(f"- **Core question**: {rp.core_question}")
    if rp.background_gap:
        parts.append(f"- **Background gap**: {rp.background_gap}")
    if rp.significance:
        parts.append(f"- **Significance**: {rp.significance}")
    parts.append("")

    # Technical Route
    tr = result.technical_route
    parts.append("## Technical Route\n")
    if tr.main_strategy:
        parts.append(f"- **Main strategy**: {tr.main_strategy}")
    if tr.method_tags:
        parts.append(f"- **Method tags** (controlled): `{', '.join(tr.method_tags)}`")
    if tr.notable_methods:
        parts.append(f"- **Notable methods**: {', '.join(tr.notable_methods)}")
    if tr.key_steps:
        parts.append("- **Key steps**:")
        for i, step in enumerate(tr.key_steps, 1):
            parts.append(f"  {i}. **{step.goal}** — {step.approach} ({step.key_technique})")
    parts.append("")

    # Main Results
    mr = result.main_results
    parts.append("## Main Results\n")
    if mr.result_direction:
        parts.append(f"- **Result direction**: `{mr.result_direction}`")
    if mr.primary_findings:
        parts.append("- **Primary findings**:")
        for i, f in enumerate(mr.primary_findings, 1):
            parts.append(f"  {i}. **{f.finding}**")
            if f.evidence:
                parts.append(f"     - Evidence: {f.evidence}")
            if f.figure_ref or f.robustness:
                parts.append(f"     - Ref: {f.figure_ref or '?'} | Robustness: {f.robustness or '?'}")
    if mr.secondary_findings:
        parts.append("- **Secondary findings**:")
        for s in mr.secondary_findings:
            parts.append(f"  - {s}")
    parts.append("")

    # Innovations
    inn = result.innovations
    parts.append("## Innovations\n")
    if inn.claimed_novelty:
        parts.append(f"- **Claimed novelty**: {inn.claimed_novelty}")
    an = inn.actual_novelty
    if an.type:
        parts.append(f"- **Actual novelty type**: `{an.type}`")
    if an.essence:
        parts.append(f"  - Essence: {an.essence}")
    if an.honest_assessment:
        parts.append(f"  - Honest assessment: {an.honest_assessment}")
    parts.append("")

    # Limitations
    lim = result.limitations
    parts.append("## Limitations\n")
    if lim.acknowledged:
        parts.append("- **Acknowledged**:")
        for x in lim.acknowledged:
            parts.append(f"  - {x}")
    if lim.reviewer_perspective:
        parts.append("- **Reviewer perspective**:")
        for x in lim.reviewer_perspective:
            parts.append(f"  - {x}")
    parts.append("")

    # Relation to Literature
    rel = result.relation_to_literature
    parts.append("## Relation to Literature\n")
    if rel.builds_on:
        parts.append("- **Builds on**:")
        for x in rel.builds_on:
            parts.append(f"  - {x}")
    if rel.differs_from:
        parts.append("- **Differs from**:")
        for d in rel.differs_from:
            parts.append(f"  - **{d.reference}** — {d.key_difference}")
    if rel.position_in_field:
        parts.append(f"- **Position in field**: `{rel.position_in_field}`")
    parts.append("")

    if result._missing:
        parts.append(f"\n---\n\n## _missing\n\n```\n{result._missing}\n```")

    return "\n".join(parts)


# ============================================================
# Main
# ============================================================
def main(argv: list[str]) -> int:
    # Windows UTF-8 hardening (matches research_deep.py).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and getattr(stream, "encoding", "").lower() != "utf-8":
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="research-paper",
        description="Extract an academic paper to a 6-module vault note",
    )
    parser.add_argument(
        "source",
        help="arxiv:<id> / pmid:<id> / doi:<doi> / local PDF path",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=30000,
        help="Truncate paper text to N chars before LLM (default 30000)",
    )
    args = parser.parse_args(argv[1:])

    source = args.source.strip()
    source_type = pdf_load.detect_source_type(source)
    print(f"[/research-paper] source: {source!r} (type={source_type})", file=sys.stderr)

    # Phase 1: load text
    print("[/research-paper] Phase 1: loading paper text...", file=sys.stderr)
    try:
        text = pdf_load.load_text(source)
    except FileNotFoundError as e:
        print(f"[/research-paper] ERROR: {e}", file=sys.stderr)
        return 2
    except NotImplementedError as e:
        print(f"[/research-paper] ERROR: {e}", file=sys.stderr)
        return 3

    truncated = text[: args.max_chars]
    print(
        f"[/research-paper] loaded {len(text)} chars; feeding {len(truncated)} to extract()",
        file=sys.stderr,
    )

    # Phase 2: extract (with truncation auto-retry for long PDFs)
    print("[/research-paper] Phase 2: extracting via DeepSeek...", file=sys.stderr)
    result = paper_extract.extract(truncated)

    # Retry path: long PDFs (eg 4.7MB / 86k chars MIC11 case) produce JSON that
    # exceeds DeepSeek's 8k max_tokens output, leaving _raw_json mid-token. We
    # detect this and halve the input so the JSON also halves.
    if _looks_truncated(result) and args.max_chars > 15001:
        retry_chars = args.max_chars // 2
        print(
            f"[/research-paper] JSON looks truncated (raw_json={len(result._raw_json)} chars, "
            f"unbalanced braces); retrying with --max-chars {retry_chars}...",
            file=sys.stderr,
        )
        truncated_retry = text[:retry_chars]
        result = paper_extract.extract(truncated_retry)

    if "JSON_PARSE_FAILED" in result._missing:
        print(
            f"[/research-paper] JSON parse failed even after retry. "
            f"_raw_json head:\n{result._raw_json[:500]}",
            file=sys.stderr,
        )
        return 4

    # Phase 3: write vault note
    print("[/research-paper] Phase 3: writing to vault...", file=sys.stderr)
    fm = build_frontmatter(result, source)
    body = build_body(result, source)

    date_str = datetime.now().strftime("%Y-%m-%d")
    author_year = _first_author_year(result)
    title_slug = _slug(result.metadata.title or "untitled", max_len=50)
    fname = f"{date_str}__{author_year}__{title_slug}.md"

    folder = VAULT_PATH / "Research" / "Papers"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / fname

    fm_lines = ["---"]
    for k, v in fm.items():
        fm_lines.append(_yaml_kv(k, v))
    fm_lines.append("---")
    full = "\n".join(fm_lines) + "\n\n" + body
    path.write_text(full, encoding="utf-8")
    print(f"[/research-paper] saved: {path}", file=sys.stderr)
    # Print path to stdout for caller consumption
    print(str(path))

    # Phase 4: best-effort PushGate
    title_short = (result.metadata.title or source)[:40]
    notify_title = f"📄 论文卡: {title_short}"
    core_q = result.research_purpose.core_question or "(no core question)"
    notify_desp = (
        f"**Source**: {source}\n"
        f"**Saved**: `{path.relative_to(VAULT_PATH)}`\n\n"
        f"**Core question**: {core_q[:500]}\n\n"
        f"**Model organism**: `{result.metadata.model_organism or 'unspecified'}`\n"
        f"**Method tags**: `{', '.join(result.technical_route.method_tags) or 'none'}`\n"
        f"**Result direction**: `{result.main_results.result_direction or 'unspecified'}`\n"
        f"**Novelty type**: `{result.innovations.actual_novelty.type or 'unspecified'}`\n"
    )
    pushgate.notify(notify_title, notify_desp)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
