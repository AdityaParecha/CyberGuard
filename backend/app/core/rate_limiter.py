"""
Client-side rate limiting and provider fallback for hosted LLM APIs.

Every hosted model call in CyberGuard (CrewAI, the per-agent notes, Google
ADK and the artifact analyser) goes through ``litellm.completion`` /
``litellm.acompletion``, which this module wraps.

Provider chain
--------------
LLM_MODELS is an ordered, comma-separated list, for example::

    groq/openai/gpt-oss-20b,gemini/gemini-2.5-flash-lite

Each call goes to the first model that can take it. A model is skipped when
its per-minute window would make the call wait longer than
LLM_FALLBACK_WAIT_SECONDS (default 15), when its daily budget is used up, or
when the provider returns an error. The last model in the chain waits as long
as needed for its per-minute window instead of being skipped.

Limits
------
Each provider has its own limiter. Limits come from <PROVIDER>_RPM_LIMIT,
<PROVIDER>_TPM_LIMIT, <PROVIDER>_RPD_LIMIT and <PROVIDER>_TPD_LIMIT (for
example GROQ_TPM_LIMIT), then from the generic LLM_* variables, then from
the built-in defaults below. Only LLM_LIMIT_SAFETY (default 0.8) of each
limit is used, as headroom for token-estimate error.

Retries are done here, not inside LiteLLM, so every attempt is counted.
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger("cyberguard.rate_limiter")

MINUTE = 60.0
DAY = 24 * 60 * 60.0
DEFAULT_OUTPUT_TOKENS = 1024

# Free-tier defaults. Groq: console.groq.com -> Settings -> Limits for
# openai/gpt-oss-20b. Gemini: conservative guesses; set the real numbers
# from aistudio.google.com -> Rate limit.
PROVIDER_DEFAULTS = {
    "groq": {"rpm": 30, "tpm": 8000, "rpd": 1000, "tpd": 200000},
    "gemini": {"rpm": 10, "tpm": 250000, "rpd": 250, "tpd": 2000000},
}
GENERIC_DEFAULTS = {"rpm": 30, "tpm": 8000, "rpd": 1000, "tpd": 200000}


class DailyBudgetExceeded(RuntimeError):
    """A provider's daily request or token budget is used up."""


class WouldWaitTooLong(RuntimeError):
    """The provider's per-minute window is full for longer than allowed."""


@dataclass
class _Entry:
    at: float
    tokens: int


def _env_number(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def provider_of(model: str) -> str:
    return str(model).split("/", 1)[0].lower() if "/" in str(model) else "default"


class RateLimiter:
    def __init__(self, provider: str = "default") -> None:
        self.provider = provider
        defaults = PROVIDER_DEFAULTS.get(provider, GENERIC_DEFAULTS)
        safety = _env_number("LLM_LIMIT_SAFETY") or 0.8

        def limit(kind: str, floor: int) -> int:
            value = (
                _env_number(f"{provider.upper()}_{kind.upper()}_LIMIT")
                or _env_number(f"LLM_{kind.upper()}_LIMIT")
                or defaults[kind]
            )
            return max(floor, int(value * safety))

        self.rpm = limit("rpm", 1)
        self.tpm = limit("tpm", 500)
        self.rpd = limit("rpd", 1)
        self.tpd = limit("tpd", 1000)

        self._minute: deque[_Entry] = deque()
        self._day: deque[_Entry] = deque()
        self._lock = threading.Lock()

        self.total_calls = 0
        self.total_tokens = 0
        self.total_wait_seconds = 0.0
        self.failures = 0

    def _prune(self, now: float) -> None:
        while self._minute and now - self._minute[0].at >= MINUTE:
            self._minute.popleft()
        while self._day and now - self._day[0].at >= DAY:
            self._day.popleft()

    def acquire(self, estimated_tokens: int, max_wait: float | None = None) -> _Entry:
        """
        Reserve room for one call. Waits for the per-minute window; raises
        WouldWaitTooLong if that would take longer than ``max_wait`` seconds
        (None = wait as long as needed), and DailyBudgetExceeded when the
        daily budget is used up.
        """
        estimated = max(1, min(int(estimated_tokens), self.tpm))
        started = time.monotonic()

        while True:
            with self._lock:
                now = time.monotonic()
                self._prune(now)

                day_tokens = sum(e.tokens for e in self._day)
                if len(self._day) + 1 > self.rpd or day_tokens + estimated > self.tpd:
                    raise DailyBudgetExceeded(
                        f"{self.provider}: daily budget reached."
                    )

                minute_tokens = sum(e.tokens for e in self._minute)
                if (
                    len(self._minute) + 1 <= self.rpm
                    and minute_tokens + estimated <= self.tpm
                ):
                    entry = _Entry(at=now, tokens=estimated)
                    self._minute.append(entry)
                    self._day.append(entry)
                    self.total_calls += 1
                    waited = now - started
                    self.total_wait_seconds += waited
                    if waited > 0.5:
                        logger.info(
                            "LLM call waited %.1fs for %s rate limit "
                            "(est_tokens=%d)", waited, self.provider, estimated,
                        )
                    return entry

                oldest = self._minute[0].at if self._minute else now
                ready_in = max(0.25, oldest + MINUTE - now + 0.05)

                if max_wait is not None and (now - started) + ready_in > max_wait:
                    raise WouldWaitTooLong(
                        f"{self.provider}: per-minute limit busy for "
                        f"{ready_in:.0f}s."
                    )

            time.sleep(min(ready_in, 5.0))

    def settle(self, entry: _Entry, actual_tokens: int | None) -> None:
        """Replace the estimate with the provider-reported token count."""
        if not actual_tokens:
            return
        with self._lock:
            entry.tokens = max(int(actual_tokens), 1)
            self.total_tokens += entry.tokens

    def release(self, entry: _Entry) -> None:
        """Give back a reservation for a call that failed before running."""
        with self._lock:
            try:
                self._minute.remove(entry)
            except ValueError:
                pass
            try:
                self._day.remove(entry)
            except ValueError:
                pass
            self.total_calls -= 1
            self.failures += 1

    def stats(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            return {
                "limits_used": {
                    "requests_per_minute": self.rpm,
                    "tokens_per_minute": self.tpm,
                    "requests_per_day": self.rpd,
                    "tokens_per_day": self.tpd,
                },
                "last_minute": {
                    "requests": len(self._minute),
                    "tokens": sum(e.tokens for e in self._minute),
                },
                "last_day": {
                    "requests": len(self._day),
                    "tokens": sum(e.tokens for e in self._day),
                },
                "total_calls": self.total_calls,
                "total_tokens": self.total_tokens,
                "total_wait_seconds": round(self.total_wait_seconds, 1),
                "failed_calls": self.failures,
            }


_limiters: dict[str, RateLimiter] = {}
_limiters_lock = threading.Lock()
_fallback_count = 0


def limiter_for(model: str) -> RateLimiter:
    provider = provider_of(model)
    with _limiters_lock:
        if provider not in _limiters:
            _limiters[provider] = RateLimiter(provider)
        return _limiters[provider]


def model_chain(requested: str) -> list[str]:
    """The configured chain, with the requested model first if absent."""
    configured = [
        m.strip() for m in os.getenv("LLM_MODELS", "").split(",") if m.strip()
    ]
    if not configured:
        return [requested]
    if requested and requested not in configured:
        # A caller asked for a specific non-chain model; honour it first.
        return [requested, *configured]
    start = configured.index(requested) if requested in configured else 0
    return configured[start:] + configured[:start]


def stats() -> dict[str, Any]:
    with _limiters_lock:
        providers = {name: lim.stats() for name, lim in _limiters.items()}
    return {
        "model_chain": model_chain(""),
        "fallbacks": _fallback_count,
        "providers": providers,
    }


def estimate_tokens(model: str, kwargs: dict[str, Any]) -> int:
    """Input tokens (messages + tools) plus the requested output budget."""
    messages = kwargs.get("messages") or []
    tools = kwargs.get("tools")

    try:
        import litellm

        prompt_tokens = litellm.token_counter(model=model, messages=messages)
    except Exception:
        prompt_tokens = len(json.dumps(messages, default=str)) // 3

    if tools:
        prompt_tokens += len(json.dumps(tools, default=str)) // 3

    output = (
        kwargs.get("max_tokens")
        or kwargs.get("max_completion_tokens")
        or DEFAULT_OUTPUT_TOKENS
    )
    return int(prompt_tokens) + int(output)


def _usage_tokens(response: Any) -> int | None:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return None
    total = getattr(usage, "total_tokens", None)
    if total is None and isinstance(usage, dict):
        total = usage.get("total_tokens")
    return int(total) if total else None


def _is_rate_limit(error: Exception) -> bool:
    return (
        "RateLimit" in type(error).__name__
        or "429" in str(getattr(error, "status_code", ""))
    )


def _fallback_wait() -> float:
    return _env_number("LLM_FALLBACK_WAIT_SECONDS") or 15.0


def _max_retries() -> int:
    value = _env_number("LLM_NUM_RETRIES")
    return int(value) if value is not None else 3


def _kwargs_for(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Point the call at ``model`` and drop options another model rejects."""
    call_kwargs = dict(kwargs)
    call_kwargs["model"] = model
    if "gpt-oss" not in model:
        call_kwargs.pop("reasoning_effort", None)
    return call_kwargs


def _plan(requested: str) -> list[tuple[str, float | None]]:
    chain = model_chain(requested)
    return [
        (model, None if index == len(chain) - 1 else _fallback_wait())
        for index, model in enumerate(chain)
    ]


def _note_fallback(failed: str, error: Exception, next_model: str) -> None:
    global _fallback_count
    _fallback_count += 1
    # Error class only: provider messages can echo prompt content.
    logger.warning(
        "LLM fallback: %s -> %s (reason=%s)",
        failed, next_model, type(error).__name__,
    )


def call_with_limit(original: Callable, requested: str, args: tuple, kwargs: dict) -> Any:
    """Synchronous call through the provider chain."""
    plan = _plan(requested)
    last_error: Exception | None = None

    for index, (model, max_wait) in enumerate(plan):
        is_last = index == len(plan) - 1
        limiter = limiter_for(model)
        call_kwargs = _kwargs_for(model, kwargs)
        estimate = estimate_tokens(model, call_kwargs)
        attempts = _max_retries() + 1 if is_last else 1

        for attempt in range(attempts):
            try:
                entry = limiter.acquire(estimate, max_wait=max_wait)
            except (WouldWaitTooLong, DailyBudgetExceeded) as error:
                last_error = error
                break

            try:
                response = original(*args, **call_kwargs)
            except Exception as error:
                last_error = error
                if is_last and _is_rate_limit(error) and attempt + 1 < attempts:
                    time.sleep(min(60.0, 8.0 * (attempt + 1)))
                    continue
                break

            if not call_kwargs.get("stream"):
                limiter.settle(entry, _usage_tokens(response))
            return response

        if not is_last:
            _note_fallback(model, last_error, plan[index + 1][0])

    raise last_error or RuntimeError("No LLM provider available.")


async def acall_with_limit(original: Callable, requested: str, args: tuple, kwargs: dict) -> Any:
    """Asynchronous call through the provider chain."""
    plan = _plan(requested)
    last_error: Exception | None = None

    for index, (model, max_wait) in enumerate(plan):
        is_last = index == len(plan) - 1
        limiter = limiter_for(model)
        call_kwargs = _kwargs_for(model, kwargs)
        estimate = estimate_tokens(model, call_kwargs)
        attempts = _max_retries() + 1 if is_last else 1

        for attempt in range(attempts):
            try:
                entry = await asyncio.to_thread(
                    limiter.acquire, estimate, max_wait
                )
            except (WouldWaitTooLong, DailyBudgetExceeded) as error:
                last_error = error
                break

            try:
                response = await original(*args, **call_kwargs)
            except Exception as error:
                last_error = error
                if is_last and _is_rate_limit(error) and attempt + 1 < attempts:
                    await asyncio.sleep(min(60.0, 8.0 * (attempt + 1)))
                    continue
                break

            if not call_kwargs.get("stream"):
                limiter.settle(entry, _usage_tokens(response))
            return response

        if not is_last:
            _note_fallback(model, last_error, plan[index + 1][0])

    raise last_error or RuntimeError("No LLM provider available.")


_installed = False


def install_litellm_rate_limit() -> None:
    """Wrap litellm.completion / acompletion so every call is limited."""
    global _installed
    if _installed:
        return

    import litellm

    original_completion = litellm.completion
    original_acompletion = litellm.acompletion

    def _split_model(args: tuple, kwargs: dict) -> tuple[str, tuple]:
        if "model" in kwargs:
            return str(kwargs.pop("model")), args
        return (str(args[0]), args[1:]) if args else ("", args)

    def limited_completion(*args: Any, **kwargs: Any) -> Any:
        model, args = _split_model(args, kwargs)
        return call_with_limit(original_completion, model, args, kwargs)

    async def limited_acompletion(*args: Any, **kwargs: Any) -> Any:
        model, args = _split_model(args, kwargs)
        return await acall_with_limit(original_acompletion, model, args, kwargs)

    litellm.completion = limited_completion
    litellm.acompletion = limited_acompletion

    # Google ADK copies these functions into its own module the first time
    # it is used. If that already happened, patch its copies as well.
    adk_lite_llm = sys.modules.get("google.adk.models.lite_llm")
    if adk_lite_llm is not None:
        for name, func in (
            ("completion", limited_completion),
            ("acompletion", limited_acompletion),
        ):
            if name in vars(adk_lite_llm):
                setattr(adk_lite_llm, name, func)

    # LiteLLM's own retries would bypass the limiter; retry here instead.
    litellm.num_retries = 0
    _installed = True
