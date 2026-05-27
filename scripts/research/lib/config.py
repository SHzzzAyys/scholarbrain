"""Loads research-toolkit credentials and model defaults from ~/.config/obsidian-second-brain/.env"""

from pathlib import Path
from dotenv import load_dotenv
import os

CONFIG_DIR = Path.home() / ".config" / "obsidian-second-brain"
ENV_PATH = CONFIG_DIR / ".env"

load_dotenv(ENV_PATH)


def get_required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise SystemExit(
            f"\n{name} not configured.\n"
            f"Add it to {ENV_PATH}\n"
            f"Or run install.sh from the obsidian-second-brain repo to set it up.\n"
        )
    return val


def get_optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default


XAI_API_KEY = lambda: get_required("XAI_API_KEY")
PERPLEXITY_API_KEY = lambda: get_required("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = lambda: get_required("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = get_optional("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_REASONER_MODEL = get_optional("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")
NCBI_EMAIL = lambda: get_required("NCBI_EMAIL")
PUBMED_API_KEY = lambda: get_optional("PUBMED_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY = lambda: get_optional("SEMANTIC_SCHOLAR_API_KEY", "")
PUSHGATE_URL = lambda: get_optional("PUSHGATE_URL", "")
PUSHGATE_KEY = lambda: get_optional("PUSHGATE_KEY", "")
BARK_URL = lambda: get_optional("BARK_URL", "")
MAIL_TO = lambda: get_optional("MAIL_TO", "")
MAIL_FROM = lambda: get_optional("MAIL_FROM", "")
SMTP_HOST = lambda: get_optional("SMTP_HOST", "")
SMTP_PORT = lambda: get_optional("SMTP_PORT", "465")
SMTP_USER = lambda: get_optional("SMTP_USER", "")
SMTP_PASS = lambda: get_optional("SMTP_PASS", "")
GEMINI_API_KEY = lambda: get_required("GEMINI_API_KEY")
YOUTUBE_API_KEY = lambda: get_optional("YOUTUBE_API_KEY", "")

GROK_MODEL = get_optional("GROK_MODEL", "grok-4")
PERPLEXITY_RESEARCH_MODEL = get_optional("PERPLEXITY_RESEARCH_MODEL", "sonar-pro")
PERPLEXITY_DEEP_MODEL = get_optional("PERPLEXITY_DEEP_MODEL", "sonar-deep-research")
NOTEBOOKLM_MODEL = get_optional("NOTEBOOKLM_MODEL", "gemini-2.5-flash")

VAULT_PATH = Path(get_required("OBSIDIAN_VAULT_PATH")).expanduser()
USAGE_LOG = Path.home() / ".research-toolkit" / "usage.log"
