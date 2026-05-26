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

- [ ] Day 2: lib/arxiv.py add download_pdf(); lib/pubmed.py add pmid_to_pmc_pdf();
      new lib/pdf_load.py with unified entry.
- [ ] Day 3: scripts/research/research_paper.py + commands/research-paper.md +
      vault template Research/Papers/.
- [ ] METHOD_TAGS_VOCAB: add 'qRT-PCR', 'Western blot', 'Bisulfite-seq'
      (surfaced by real test on PMID 40830525).
- [ ] Test with a real PDF (local file) once PDF parser layer is in.
