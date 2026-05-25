# Troubleshooting

## System proxy leaks into academic APIs

Symptoms: PubMed or arXiv is slow, times out, or fails with connection reset errors while DeepSeek or Perplexity still works.

Cause: `requests` honors system proxy settings by default. On Windows, this can include local Clash or v2ray ports such as `127.0.0.1:1088`, even when `HTTP_PROXY` and `HTTPS_PROXY` are not visible in PowerShell. Academic APIs such as NCBI and arXiv are often slow or blocked through those exit nodes.

Temporary workaround:

```powershell
$env:NO_PROXY="*"
uv run -m scripts.research.research "Toxoplasma RNA-seq methods" --backend pubmed
```

Long-term fix in this repo: `scripts/research/lib/pubmed.py` and `scripts/research/lib/arxiv.py` use a dedicated `requests.Session()` with `trust_env = False`, so those APIs direct-connect and ignore system proxy settings.
