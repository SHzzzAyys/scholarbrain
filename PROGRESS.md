# Progress Log

## 2026-05-25 - v0.1 start

- HARDEN_PLAN.md landed.
- lib/deepseek.py, lib/pubmed.py, and lib/arxiv.py landed.
- config.py adds DeepSeek, NCBI, PubMed, and Semantic Scholar config fields.
- External .env created at C:\Users\zheng shang\.config\obsidian-second-brain\.env.
- NCBI_EMAIL and OBSIDIAN_VAULT_PATH are configured; DEEPSEEK_API_KEY is still empty.
- DeepSeek smoke test is pending until DEEPSEEK_API_KEY is configured.
- PubMed smoke test returned 3 PMID records; lib/pubmed.py now bypasses system proxies.
- arXiv smoke test returned 3 arXiv records; lib/arxiv.py now bypasses system proxies.
- research.py supports --backend {perplexity,pubmed,arxiv}.
- research_deep.py now uses DeepSeek for gap analysis and synthesis, plus web/pubmed/arxiv/x routing.
- GAP_PROMPT now supports academic source selection and Chinese output rules.
- PubMed end-to-end run wrote a note under D:\ToxoVault\Research\Web.
- First commit on feat/deepseek-pubmed-arxiv completed: c30bbf0.

## Todo (HARDEN_PLAN sections 1.4 / 1.6 / 1.8 / 1.9 / 1.10)

- [ ] Write lib/semantic_scholar.py (deferred to v0.2 backlog).
- [x] Update research_deep.py: move Phase 2/4 to DeepSeek and add four-way Phase 3 routing.
- [x] Update GAP_PROMPT with academic sources and Chinese output.
- [x] Add Chinese trigger docs to commands/research.md (commit 2521bee).
- [ ] Add end-to-end tests and cassette fixtures.

---

## 2026-05-26 - v0.1.0 tagged + v0.3 PushGate + v0.2 Day 1

### v0.1.0 milestone (commits ab9bc1c, 6af7eb4)

- End-to-end research_deep run on "Toxoplasma gondii Chinese1 strain transcriptome"
  produced 5KB synthesis at Research/Deep/2026-05-26 — ... .md
- Tagged v0.1.0 on commit ab9bc1c.
- Windows hardening: DeepSeek DIRECT_SESSION (bypass v2ray/clash proxy) +
  UTF-8 stdout/file IO (vault.py, research_deep.py).

### v0.3 PushGate webhook (commit 6af7eb4)

- New lib/pushgate.py: notify(title, desp) with DIRECT_SESSION + custom UA.
- config.py: PUSHGATE_URL + PUSHGATE_KEY (both optional).
- research_deep.py emits push notification after vault write (silent skip when
  PUSHGATE not configured).
- Pending: real test on user's pushgate.shangzzchin.workers.dev (needs PUSH_KEY).

### v0.2 Day 1 - paper_extract.py (in progress)

- V02_PAPER_EXTRACT_SPEC.md landed - design spec for 3-day v0.2 work.
- lib/paper_extract.py created:
  - Schema ported from paper_extractor/core/schema.py with 3 new fields:
    metadata.model_organism, technical_route.method_tags, main_results.result_direction.
  - 3 controlled vocabs: MODEL_ORGANISM_VOCAB (15), METHOD_TAGS_VOCAB (31),
    RESULT_DIRECTION_VOCAB (4).
  - Generic SYSTEM_PROMPT + vault-level _DOMAIN.md override mechanism.
  - TASK_PROMPT ported with new field constraints.
  - extract() entry point reuses fork's deepseek.call (max_tokens=8000).
- D:\ToxoVault\_DOMAIN.md landed with full Toxo domain knowledge from
  paper_extractor's original SYSTEM_PROMPT.
- Real end-to-end test passed on PubMed PMID 40830525 (m5C methylation paper):
  - JSON parse: OK
  - model_organism: 'Toxoplasma gondii' (vocab hit)
  - method_tags: ['RNA-seq', 'bioinformatics', 'qRT-PCR', 'in vitro infection']
    (2/4 hit vocab; 'bioinformatics' + 'qRT-PCR' should be added or mapped)
  - result_direction: 'mixed' (4-way hit)
  - primary_findings: 2 with quantitative evidence (~1000 peaks, 30%, p<0.05)

### Todo for v0.2 Day 2-3

- [x] Day 2: lib/arxiv.py add download_pdf(); lib/pubmed.py add pmid_to_pmc_pdf() + fetch_by_pmid(); new lib/pdf_load.py with unified entry.
- [x] Day 3: scripts/research/research_paper.py + commands/research-paper.md + vault template Research/Papers/.
- [ ] METHOD_TAGS_VOCAB: add 'qRT-PCR', 'Western blot', 'Bisulfite-seq' (surfaced on PMID 40830525); also add CS terms 'Transformer', 'self-attention', 'encoder-decoder' (surfaced on arxiv:1706.03762).
- [x] Test with a real PDF (local file) once PDF parser layer is in.

---

## 2026-05-26 - v0.2 Day 2 complete (PDF fetch + unified loader)

### What landed

- `pyproject.toml`: added optional-dependencies `pdf = ["pymupdf>=1.24.0"]`. Install with `uv sync --extra pdf`. Keeps default install lean; fork users who skip /research-paper don't pay 18MB for pymupdf.
- `lib/arxiv.py`: `download_pdf(arxiv_id, cache_dir=None)` -- strips version suffix, caches by base ID under `~/.cache/obsidian-second-brain/arxiv/`, content-type sanity check (rejects HTML on invalid IDs), POLITE_SLEEP=3s after success.
- `lib/pubmed.py`:
  - `fetch_by_pmid(pmid, fetch_abstract=True)` -- single PMID -> dict with same shape as `call()`. Used by the abstract fallback path.
  - `pmid_to_pmc_pdf(pmid, cache_dir=None)` -- 3 steps: elink PMID->PMC ID -> OA API for PDF link -> HTTP download. Returns None silently (with stderr explanation) on any failure mode so caller falls back to abstract.
- `lib/pdf_load.py` (new, 132 lines): `load_text(source: str)` router. Source prefixes: `arxiv:<id>`, `pmid:<id>`, `doi:<doi>` (NotImplementedError -> v0.4), or bare path. `parse_pdf()` wraps page 0 in `<FRONT_MATTER>` and pages 1+ in `<BODY>` matching paper_extract.TASK_PROMPT sectioning.

### Real-world verification (Day 2.4)

| Source | Result | Time |
|---|---|---|
| `arxiv:1706.03762` (Attention Is All You Need, 2.2 MB PDF) | downloaded + parsed 39572 chars, 11 pages | 9.5s (incl 2 SSL EOF retries) |
| local PDF (same cached file) | text identical to arxiv route | <1s |
| `pmid:40830525` (Toxo m5C) | PMC OA had no PDF link -> abstract fallback, 3011 chars | 4.3s |

### End-to-end pdf_load + paper_extract

Ran on arxiv:1706.03762 (truncated to 30k chars, fed under Toxo `_DOMAIN.md`):
- JSON parse OK
- `model_organism: 'in silico'` -- LLM correctly identified non-biological paper despite Toxo domain prompt
- `method_tags: ['other']` -- LLM honored controlled vocab (no biological method matches a CS paper)
- `result_direction: 'positive'` -- Transformer > RNN is a positive result
- `extract` time: 21s

### Cumulative state

6 fork commits on `feat/deepseek-pubmed-arxiv` (after v0.1.0 tag):
- cad2128: paper_extract.py + V02 spec (Day 1)
- 6af7eb4: pushgate webhook (v0.3)
- ab9bc1c: windows utf-8 + proxy bypass (v0.1.0 tagged)
- 2521bee: zh-CN triggers
- 4829592: research_deep academic routing
- c30bbf0: lib/deepseek + pubmed + arxiv

---

## 2026-05-26 - v0.2.0 milestone (Day 3 complete)

### What landed

- `scripts/research/research_paper.py` (340 lines): main entry for /research-paper.
  - 3-phase pipeline: load via pdf_load -> extract via paper_extract -> vault write.
  - Filename convention: `Research/Papers/<YYYY-MM-DD>__<author-year>__<title-slug>.md`
  - Lastname extraction handles PubMed "Zheng XN" and Western "John Smith" formats.
  - YAML frontmatter with 4 controlled-vocab fields for cross-paper comparison +
    3 user-curation fields (user_relevance, research_priority, read_status).
  - Best-effort PushGate notification after vault write.
  - UTF-8 stdout/stderr hardening (matches research_deep.py pattern).
- `commands/research-paper.md`: command doc with both EN and zh-CN triggers.

### Real-world verification (Day 3.5, 2 cases)

| Case | Result |
|---|---|
| `pmid:40830525` (Toxo m5C, abstract fallback) | saved `2026-05-26__zheng-2025__cross-lineage-5-methylcytosine-methylome-profiling.md`. model_organism=`Toxoplasma gondii` (domain hit), method_tags=`['RNA-seq', 'other']`, novelty_type=`数据创新`, position_in_field=`开创`. Used domain-aware terminology (速殖子, 基因型). |
| `arxiv:1706.03762` (Attention Is All You Need, full PDF) | saved `2026-05-26__vaswani-2017__attention-is-all-you-need.md`. model_organism=`in silico` (cross-domain LLM correctly rejected biological vocab), method_tags=`['other']`, novelty_type=`方法学创新`, position_in_field=`开创`. 3 key_steps with full goal/approach/technique, BLEU 28.4 vs 26.03 quantitative evidence. |

### v0.2.0 milestone definition met

- [x] paper_extract.py with 4 new schema fields + controlled vocabs
- [x] _DOMAIN.md override mechanism (verified does not pollute cross-domain papers)
- [x] PDF fetch layer (arXiv + PMC OA + local + abstract fallback)
- [x] /research-paper command + zh-CN triggers
- [x] 2 real cases end-to-end (1 Toxo, 1 CS) producing high-quality vault notes

### Deferred to v0.2.1 / v0.4 backlog

- [x] METHOD_TAGS_VOCAB expansion 31 -> 50 tags (commit a78d814, v0.2.1)
- Language consistency: position_in_field/novelty_type emit Chinese ("开创"), result_direction emits English ("positive"). Pick one.
- lib/semantic_scholar.py (v0.2 Day 1 task 1.4, deferred per spec section 6)
- DOI resolution via Unpaywall (v0.4)
- MinerU/Docling PDF parser upgrade (v0.4)
- cassette/VCR fixtures for real API tests (v0.5)

---

## 2026-05-26 - 10-paper batch + v0.2.1 fixes

### Pushed to GitHub
- Repo created: `github.com/SHzzzAyys/scholarbrain` (public, default branch
  `feat/deepseek-pubmed-arxiv`)
- 9 fork commits + tags v0.1.0, v0.2.0 pushed (unshallow required for first
  push to resolve dangling object 74321375... from `git clone --depth 1`).

### 10-paper batch run

Ran `/research-paper` on
`D:/ToxoVault/outputs/literature_downloads/2026-05-19_protozoa_top10/*.pdf`:

| # | Paper | Time | Status |
|---|---|---|---|
| 01 | Alrubaye 2026 -- single-cell Toxo sexual atlas | 36.7s | OK |
| 02 | Ulu 2026 -- bradyzoite subtypes | 25.9s | OK |
| 03 | Tachibana 2026 -- MIC11/PLP1 egress (4.7MB) | 30.3s | **FAIL (JSON truncated)** |
| 04 | Schwarz 2026 -- SWI/SNF complexes | 27.2s | OK |
| 05 | Gurung 2026 -- apical polar ring Pf | 23.5s | OK |
| 06 | Marapana 2026 -- GID/CTLH E3 ligase | 29.2s | OK |
| 07 | Billows 2026 -- Pf population genetics | 23.0s | OK |
| 08 | Hagedorn 2026 -- Leishmania macrophage proteomics | 22.6s | OK |
| 09 | Sadlova 2026 -- Leishmania sand fly transporters | 22.3s | OK |
| 10 | Carnielli 2026 -- Leishmania KKT2/CRK9 chem genetics | 25.7s | OK |

9/10 OK in 4 min 26s. Card #3 succeeded on manual retry with `--max-chars 15000`.

### 3 real-world findings (driving v0.2.1)

1. **JSON truncation on long PDFs**: 4.7MB PDF (86550 parsed chars) at default
   max-chars 30000 made the LLM JSON exceed DeepSeek's 8k max_tokens, leaving
   `_raw_json` mid-token. v0.2.1 fix: `_looks_truncated()` detector + auto-retry
   with halved max-chars.

2. **result_direction biased toward 'positive'**: All 12 cards (10 new + 2
   prior) came out `positive`. High-IF journals are biased that way but LLM
   was also defaulting too aggressively. v0.2.1 fix: TASK_PROMPT now has
   explicit calibration ("~30% of top-tier papers should be 'mixed'").

3. **method_tags 75% controlled-vocab coverage**: 3/12 cards have `[other]` in
   `method_tags`. Vocab is now 50 tags (was 31). Incremental expansion ongoing.

### Cross-paper dataview now functional

- Q1: `model_organism = "Toxoplasma gondii"` -> 5 cards
- Q2: `contains(method_tags, "CRISPR-screen")` -> 2 cards (Alrubaye, Tachibana)
- Q3: `contains(method_tags, "scRNA-seq")` -> 2 cards (Alrubaye, Ulu)
- Q4 novelty_type distribution: 5 概念 / 5 数据 / 2 方法学 / 0 增量
- Q5 position_in_field distribution: 6 开创 / 3 跟进 / 2 整合 / 1 修正

INDEX.md (Obsidian dataview queries) shipped to `D:/ToxoVault/Research/Papers/INDEX.md`.

### v0.2.1 deliverables (this commit)

- `research_paper.py`: `_looks_truncated()` detector + auto-retry with halved max-chars
- `paper_extract.py`: result_direction calibration in TASK_PROMPT
- `D:/ToxoVault/Research/Papers/INDEX.md`: starter dataview query page (vault, not repo)

### Cumulative state (after v0.2.1)

10 fork commits on `feat/deepseek-pubmed-arxiv` (after v0.1.0 tag):
- (this commit): v0.2.1 truncation retry + result_direction calibration + INDEX
- a78d814: vocab expansion 31 -> 50
- 149d854: /research-paper command (v0.2.0 tagged)
- bb61d66: pdf fetch + unified loader
- cad2128: paper_extract.py + V02 spec
- 6af7eb4: pushgate webhook
- ab9bc1c: windows utf-8 + proxy bypass (v0.1.0 tagged)
- 2521bee: zh-CN triggers
- 4829592: research_deep academic routing
- c30bbf0: lib/deepseek + pubmed + arxiv

---

## 2026-05-27 - v0.2.2 batch verification (all 12 cards re-extracted)

### Test results vs v0.2.0 baseline

| Test | v0.2.0 baseline | v0.2.2 result | Verdict |
|---|---|---|---|
| novelty_type English | 1/12 (8%) | **12/12 (100%)** | PASS |
| position_in_field English | 1/12 (8%) | **12/12 (100%)** | PASS |
| result_direction diversity | 12/12 positive | **7 positive / 5 mixed** | calibration works |
| method_tags no Chinese leak | 1 card leaked | **0 cards** | PASS |
| vocab coverage ("other") | 25% of cards | **0% (0/64 uses)** | vocab sufficient |

64 method_tag uses across 12 cards, 34 unique tags — all in METHOD_TAGS_VOCAB.

### 5 papers that became 'mixed' (was 0 before v0.2.1 calibration)

- Alrubaye 2026 (single-cell Toxo sexual atlas): dataset + mixed + pioneering
- Schwarz 2026 (Toxo SWI/SNF): conceptual + mixed + pioneering
- Hagedorn 2026 (Leishmania macrophage proteomics)
- Sádlová 2026 (Leishmania sand fly transporters)
- Zheng XN 2025 (Toxo m5C cross-lineage)

These are now filterable: `WHERE result_direction = "positive"` returns
only the 7 high-confidence cards, not all 12.

### Batch stats

- 12/12 OK in 6m13s total (avg 31s/paper)
- Longest: Zheng 2025 at 52s (DeepSeek reasoner mode for pmid: source)
- Shortest: Vaswani 2017 at 22s (arxiv: cached, English-only paper)
- Card #3 (MIC11, 86k chars PDF): 28s with v0.2.1 auto-truncation retry working

### Final cumulative state

14 fork commits on main:
- 9ee4f55: v0.2.2 retrospective
- f73b2e4: v0.2.2 vocab +9 + English-only
- c7c046e: merge feat/deepseek-pubmed-arxiv
- e21e5b4: multi-channel notify fallback
- 552ba9a: semantic_scholar.py + vocab English
- 2adb5bb: v0.2.1 truncation retry + result_direction calibration
- a78d814: vocab 31->50
- 149d854: /research-paper command (v0.2.0)
- bb61d66: pdf fetch layer
- cad2128: paper_extract.py (v0.2 Day 1)
- 6af7eb4: pushgate webhook
- ab9bc1c: windows utf-8 + proxy (v0.1.0)
- 2521bee: zh-CN triggers
- 4829592: research_deep academic routing
- c30bbf0: lib/deepseek + pubmed + arxiv

Vault: 12 v0.2.2-compliant cards in D:/ToxoVault/Research/Papers/ + INDEX.md
