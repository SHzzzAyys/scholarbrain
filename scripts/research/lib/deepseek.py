"""DeepSeek client (OpenAI-compatible /chat/completions). Pure LLM, no web search."""
import time
import requests
from typing import Any

from .config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_REASONER_MODEL

API_URL = "https://api.deepseek.com/chat/completions"
MAX_RETRIES = 3
BACKOFF_SECONDS = (1, 3, 8)


def call(prompt: str, *, model: str | None = None, reasoning: bool = False, max_tokens: int = 8000) -> dict[str, Any]:
    """Call DeepSeek chat/completions. Pure LLM, no web search (citations always []).

    - max_tokens default 8000 (paper_extractor empirically: lower truncates).
    - reasoning=True uses the reasoner model with timeout=600s; else timeout=180s.
    """
    model = model or (DEEPSEEK_REASONER_MODEL if reasoning else DEEPSEEK_MODEL)
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY()}", "Content-Type": "application/json"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    timeout = 600 if reasoning else 180
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(API_URL, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                text = (data["choices"][0]["message"].get("content") or "").strip()
                return {"text": text, "citations": [], "model": model, "raw": data}
            if r.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                print(f"[DeepSeek {r.status_code}, retrying in {wait}s...]")
                time.sleep(wait)
                continue
            raise RuntimeError(f"DeepSeek API error {r.status_code}: {r.text[:500]}")
        except requests.RequestException as e:
            last_err = e
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            print(f"[DeepSeek network error: {e}, retrying in {wait}s...]")
            time.sleep(wait)
    raise RuntimeError(f"DeepSeek API failed after {MAX_RETRIES} retries: {last_err}")
