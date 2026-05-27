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

## Push notification fallback

If `PUSHGATE_KEY` is missing or PushGate fails, `scripts/research/lib/pushgate.py` can send directly by SMTP email or Bark when those channels are configured.

For direct QQ Mail delivery, configure a sender mailbox with SMTP enabled. `SMTP_PASS` should be the mailbox authorization code, not the normal login password.

```env
MAIL_TO=812862383@qq.com
MAIL_FROM=
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=<sender@qq.com>
SMTP_PASS=<smtp_authorization_code>
```

Then smoke test:

```powershell
uv run python -c "from scripts.research.lib import pushgate; pushgate.notify('Email test', 'hello from obsidian-second-brain')"
```

Add the Bark app URL to `~/.config/obsidian-second-brain/.env`:

```env
BARK_URL=https://api.day.app/<your_device_key>
```

Then smoke test:

```powershell
uv run python -c "from scripts.research.lib import pushgate; pushgate.notify('Bark test', 'hello from obsidian-second-brain')"
```
