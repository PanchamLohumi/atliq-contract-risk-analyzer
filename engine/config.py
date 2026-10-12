"""Resolves the API key from configuration, never from the user.

Karandeep is the user of this product. He should never be shown a credential
field: a key is deployment configuration, like a database URL. Resolution order
is Streamlit secrets (how it is set in production), then the process
environment, then a local .env file (how it is set on a developer machine).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "GROQ_API_KEY"


def _from_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == KEY:
            return v.strip().strip('"').strip("'")
    return None


def load_key():
    """Put the key into the environment if configured. Returns (found, source)."""
    if os.getenv(KEY, "").strip():
        return True, "environment"
    try:
        import streamlit as st
        v = st.secrets.get(KEY, "") if hasattr(st, "secrets") else ""
        if v:
            os.environ[KEY] = str(v).strip()
            return True, "Streamlit secrets"
    except Exception:
        pass  # no secrets file configured; normal on a dev machine
    v = _from_dotenv()
    if v:
        os.environ[KEY] = v
        return True, ".env file"
    return False, None
