---
description: Extract an academic paper to a structured 6-module vault note via DeepSeek + paper_extract — input arxiv:<id> / pmid:<id> / DOI / local PDF path; output Research/Papers/<date>__author-year__title.md with model_organism / method_tags / result_direction / novelty_type frontmatter for cross-paper comparison and review writing
category: research
triggers_en: ["research paper", "extract paper", "analyze paper", "paper card", "deep read paper"]
triggers_zh: ["论文卡", "抽取论文", "分析论文", "深读论文", "论文六模块", "做论文卡"]
---

Use the obsidian-second-brain skill. Execute `/research-paper [source]`:

1. Resolve the source from the user's argument. Accepted formats:
   - `arxiv:<id>` — e.g. `arxiv:1706.03762` (downloads PDF from arXiv)
   - `pmid:<id>` — e.g. `pmid:40830525` (tries PMC OA PDF, falls back to abstract)
   - `doi:<doi>` — NotImplementedError (deferred to v0.4 via Unpaywall)
   - local file path — e.g. `D:/papers/zheng2025.pdf`

   If no source given, ask: "Which paper? Give me a PMID, arXiv ID, or PDF path."

2. Run the Python command from the repo root (`~/Projects/personal/obsidian-second-brain/`):
   ```bash
   uv run -m scripts.research.research_paper "<source>" [--max-chars 30000]
   ```
   - `--max-chars` truncates paper text before sending to DeepSeek (default 30000, safe for context limit). Increase if the paper is short and you want full coverage; decrease if cost-sensitive.

3. The script runs a 3-phase pipeline:
   - **Phase 1** — load via `lib.pdf_load`: downloads PDF if arxiv/pmid, parses via pymupdf into `<FRONT_MATTER>` + `<BODY>` markers.
   - **Phase 2** — extract via `lib.paper_extract`: DeepSeek + vault's `_DOMAIN.md`, output a 6-module ExtractionResult with 4 controlled-vocab fields (`model_organism`, `method_tags`, `result_direction`, `novelty_type`).
   - **Phase 3** — write to vault: `Research/Papers/<YYYY-MM-DD>__<author-year>__<title-slug>.md`. Frontmatter is rich (for dataview filtering) and ends with 3 user-curated fields (`user_relevance` / `research_priority` / `read_status`) left empty for human edits.

4. **Save behavior: saves and prints path to stdout.**
   - File path is printed verbatim on stdout (parseable for chained calls).
   - Best-effort PushGate notification fires if `PUSHGATE_URL` + `PUSHGATE_KEY` configured (silent skip otherwise).

5. After save, surface to the user:
   - The saved path
   - 1-line core question summary
   - The 4 controlled-vocab fields (model_organism / method_tags / result_direction / novelty_type) — these are the cross-paper comparison primitives
   - Suggest follow-ups:
     - "Want me to also run `/obsidian-save` to propagate insights into related notes?"
     - "Compare with other papers tagged `<method_tag>`?" or "Filter your `Research/Papers/` by `result_direction: positive`?"

6. Plain English triggers: "research paper [source]", "extract [PMID/arXiv]", "analyze this paper [path]", "make a paper card for [source]", "deep read [source]".

   中文触发: "论文卡 [source]"、"抽取论文 [source]"、"分析论文 [source]"、"深读论文 [source]"、"论文六模块 [source]"、"做论文卡 [source]"。

7. Errors and graceful degradation:
   - arxiv PDF download fails → script raises with arXiv error message; user can retry or pass `arxiv:<id>` again later.
   - PMC OA PDF unavailable for PMID → script auto-falls back to abstract-only mode and warns user on stderr. The extracted card will note partial evidence but still has good metadata + claimed_novelty.
   - DOI passed → NotImplementedError; ask user to find the PMID or arXiv ID, or download PDF manually and pass the local path.
   - LLM JSON parse failure → script exits non-zero with `_raw_json` head dumped to stderr for debugging.

8. Cost: DeepSeek `deepseek-chat` call ≈ $0.01-0.03 per paper. PubMed/arXiv free. Truncation at 30k chars keeps cost predictable.

---

**AI-first rule:** Every note created by this command follows the AI-first vault rule from `references/ai-first-rules.md` — `## For future Claude` preamble, rich frontmatter (`type: research-paper`, source, model_organism, method_tags, result_direction, novelty_type, position_in_field, user_relevance, read_status, `ai-first: true`), structured 6-module body. The vault is for future-Claude retrieval; the card is the canonical reference for this paper across all other vault notes.
