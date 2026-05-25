# Progress Log

## 2026-05-25 - v0.1 start

- HARDEN_PLAN.md landed.
- lib/deepseek.py, lib/pubmed.py, and lib/arxiv.py landed.
- config.py adds DeepSeek, NCBI, PubMed, and Semantic Scholar config fields.
- External .env created at C:\Users\zheng shang\.config\obsidian-second-brain\.env.
- NCBI_EMAIL and OBSIDIAN_VAULT_PATH are configured; DEEPSEEK_API_KEY is still empty.
- DeepSeek smoke test is pending until DEEPSEEK_API_KEY is configured.
- PubMed smoke test returned 3 PMID records with NO_PROXY=*.
- arXiv smoke test returned 3 arXiv records with NO_PROXY=*.
- research.py supports --backend {perplexity,pubmed,arxiv}.
- PubMed end-to-end run wrote a note under D:\ToxoVault\Research\Web.
- First commit on feat/deepseek-pubmed-arxiv is planned for this change set.

## Todo (HARDEN_PLAN sections 1.4 / 1.6 / 1.8 / 1.9 / 1.10)

- [ ] Write lib/semantic_scholar.py.
- [ ] Update research_deep.py: move Phase 2/4 to DeepSeek and add four-way Phase 3 routing.
- [ ] Update GAP_PROMPT with academic sources and Chinese output.
- [ ] Add Chinese trigger docs to commands/research.md.
- [ ] Add end-to-end tests and cassette fixtures.
