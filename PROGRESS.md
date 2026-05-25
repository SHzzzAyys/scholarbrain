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

- [ ] Write lib/semantic_scholar.py.
- [x] Update research_deep.py: move Phase 2/4 to DeepSeek and add four-way Phase 3 routing.
- [x] Update GAP_PROMPT with academic sources and Chinese output.
- [ ] Add Chinese trigger docs to commands/research.md.
- [ ] Add end-to-end tests and cassette fixtures.
