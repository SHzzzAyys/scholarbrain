"""PushGate client — self-hosted Cloudflare Worker push gateway (Server酱 替代品).

接口契约: POST <url>/<key>.send  body {title, desp}
渠道: Bark / DingTalk / Feishu / Email (由 worker 端按 secret 自动 fan-out)

This module is OPTIONAL: notify() tries PushGate first when configured, then
falls back to direct email or Bark when configured. Missing config and
HTTP/network/SMTP errors never block the main research flow.
"""
import sys
import smtplib
import requests
from email.message import EmailMessage
from typing import Any

from .config import (
    BARK_URL,
    MAIL_FROM,
    MAIL_TO,
    PUSHGATE_KEY,
    PUSHGATE_URL,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)

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


def is_bark_configured() -> bool:
    """Check whether direct Bark fallback is configured."""
    try:
        return bool(BARK_URL())
    except Exception:
        return False


def is_email_configured() -> bool:
    """Check whether direct SMTP email fallback is configured."""
    try:
        return bool(MAIL_TO() and SMTP_HOST() and SMTP_USER() and SMTP_PASS())
    except Exception:
        return False


def notify(title: str, desp: str) -> bool:
    """Send a push notification, falling back across configured channels.

    Returns True on success, False on any failure. NEVER raises — notification
    is best-effort, the main research flow must never crash because notification
    is down or misconfigured.

    Args:
        title: 推送标题 (短, 在 Bark/钉钉是顶部加粗)
        desp:  推送正文 (支持 markdown, 各渠道长度上限不一, 建议 ≤ 2000 字)
    """
    if is_configured() and _notify_pushgate(title, desp):
        return True
    if is_email_configured() and _notify_email(title, desp):
        return True
    if is_bark_configured() and _notify_bark(title, desp):
        return True
    return False


def _notify_pushgate(title: str, desp: str) -> bool:
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


def _notify_bark(title: str, desp: str) -> bool:
    try:
        endpoint = BARK_URL().rstrip("/")
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        body: dict[str, Any] = {"title": title, "body": desp}
        r = DIRECT_SESSION.post(endpoint, json=body, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"[Bark] notify sent: {title!r}", file=sys.stderr)
            return True
        print(f"[Bark] failed {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    except requests.RequestException as e:
        print(f"[Bark] network error: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[Bark] unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def _notify_email(title: str, desp: str) -> bool:
    try:
        host = SMTP_HOST()
        port = int(SMTP_PORT() or "465")
        username = SMTP_USER()
        password = SMTP_PASS()
        mail_from = MAIL_FROM() or username
        mail_to = MAIL_TO()

        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = mail_from
        msg["To"] = mail_to
        msg.set_content(desp, subtype="plain", charset="utf-8")

        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT) as smtp:
                smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=TIMEOUT) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(msg)
        print(f"[Email] notify sent: {title!r} -> {mail_to}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[Email] error: {type(e).__name__}: {e}", file=sys.stderr)
        return False
