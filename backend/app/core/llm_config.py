"""
One place that decides which language model CyberGuard uses.

- Local default: Ollama, using OLLAMA_MODEL (e.g. mistral:latest).
- Hosted: set LLM_MODEL to any LiteLLM model string, for example
  ``groq/qwen/qwen3.8-27b`` (needs GROQ_API_KEY) or
  ``gemini/gemini-2.5-flash`` (needs GEMINI_API_KEY). LiteLLM reads the
  provider API key from the environment itself.

CrewAI, Google ADK and the artifact analyser all read from here, so one
setting switches the whole pipeline.
"""

import os
import time
from threading import Lock
from typing import Any

from dotenv import load_dotenv

# Read .env before any setting below is evaluated.
load_dotenv()

DEFAULT_OLLAMA_MODEL = "mistral:latest"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_PREFIXES = ("ollama/", "ollama_chat/")


def llm_model() -> str:
    """Full LiteLLM model string, e.g. 'ollama/mistral:latest'."""
    chain = [m.strip() for m in os.getenv("LLM_MODELS", "").split(",") if m.strip()]
    if chain:
        return chain[0]

    explicit = os.getenv("LLM_MODEL", "").strip()
    if explicit:
        return explicit

    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
    return model if model.startswith(OLLAMA_PREFIXES) else f"ollama/{model}"


def uses_ollama() -> bool:
    return llm_model().startswith(OLLAMA_PREFIXES)


def ollama_model_name() -> str:
    """Bare Ollama model name, e.g. 'mistral:latest'."""
    model = llm_model()
    for prefix in OLLAMA_PREFIXES:
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)


def adk_model() -> str:
    """Model string for Google ADK's LiteLlm wrapper."""
    if uses_ollama():
        return f"ollama_chat/{ollama_model_name()}"
    return llm_model()


def extra_llm_params() -> dict:
    """Provider-specific options that keep hosted calls short."""
    params: dict = {}
    if "gpt-oss" in llm_model():
        # gpt-oss spends tokens on reasoning; keep it brief so notes fit the
        # token budget and the free tier's tokens-per-minute limit.
        params["reasoning_effort"] = os.getenv("LLM_REASONING_EFFORT", "low")
    return params


def configure_litellm() -> None:
    """Install the hosted-API rate limiter (no-op for local Ollama)."""
    try:
        import litellm
    except ImportError:
        return

    litellm.drop_params = True

    if not uses_ollama():
        from backend.app.core.rate_limiter import install_litellm_rate_limit

        install_litellm_rate_limit()


_pace_lock = Lock()
_last_call = 0.0


def pace_llm_calls() -> None:
    """
    Wait so that consecutive agent calls are at least
    LLM_MIN_SECONDS_BETWEEN_CALLS apart (default 0, i.e. no waiting).
    Used on free hosted tiers with a tokens-per-minute cap.
    """
    global _last_call

    gap = float(os.getenv("LLM_MIN_SECONDS_BETWEEN_CALLS", "0") or 0)
    if gap <= 0:
        return

    with _pace_lock:
        wait = _last_call + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


configure_litellm()
