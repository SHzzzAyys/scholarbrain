"""PushGate client — self-hosted Cloudflare Worker push gateway (Server酱 替代品).

接口契约: POST <url>/<key>.send  body {title, desp}
渠道: Bark / DingTalk / Feishu / Email (由 worker 端按 secret 自动 fan-out)

This module is OPTIONAL: if PUSHGATE_URL or PUSHGATE_KEY is missing, notify()
silently returns False so the main research flow is never blocked by missing
notification config. Any HTTP/network error is also swallowed (logged to stderr).
"""
import sys
import requests
from typing import Any

from .config import PUSHGATE_URL, PUSHGATE_KEY

# Cloudflare Workers 边界把默认 python-urllib/3.x 当机器人 403，必须自定义 UA.
USER_AGENT = "obsidian-second-brain-research/0.1 (pushgate-client)"
TIMEOUT = 10  # 推送是 best-effort, 短超时, 不要阻塞主流程

DIRECT_SESSION = requests.Session()
DIRECT_SESSION.trust_env = False


def is_configured() -> bool:
    """Check if PushGate is fully configured. Used to skip notify() early."""
    try:
        url = PUSHGATE_URL()
        key = PUSHGATE_KEY()
        return bool(url and key)
    except Exception:
        return False


def notify(title: str, desp: str) -> bool:
    """Send a push notification through PushGate.

    Returns True on success, False on any failure. NEVER raises — notification
    is best-effort, the main research flow must never crash because pushgate
    is down or misconfigured.

    Args:
        title: 推送标题 (短, 在 Bark/钉钉是顶部加粗)
        desp:  推送正文 (支持 markdown, 各渠道长度上限不一, 建议 ≤ 2000 字)
    """
    if not is_configured():
        return False
    try:
        url_base = PUSHGATE_URL().rstrip("/")
        key = PUSHGATE_KEY()
        endpoint = f"{url_base}/{key}.send"
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        body: dict[str, Any] = {"title": title, "desp": desp}
        r = DIRECT_SESSION.post(endpoint, json=body, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"[PushGate] notify sent: {title!r}", file=sys.stderr)
            return True
        print(f"[PushGate] failed {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    except requests.RequestException as e:
        print(f"[PushGate] network error: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        # 兜底: 任何异常都不能炸到调用方
        print(f"[PushGate] unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return False
