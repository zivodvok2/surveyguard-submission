from __future__ import annotations

import os
import re
import time

_GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_OPENROUTER_MODEL = "minimax/minimax-m3:free"

# Prefer Groq when its key is available — much higher rate limits than the
# OpenRouter free tier which 429s on the very first call.
def _provider_config() -> tuple[str, str, str]:
    """Return (base_url, model, api_key)."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if groq_key:
        return _GROQ_BASE, _GROQ_MODEL, groq_key
    if or_key:
        return _OPENROUTER_BASE, _OPENROUTER_MODEL, or_key
    raise RuntimeError("No API key found. Set GROQ_API_KEY or OPENROUTER_API_KEY.")

# Retry configuration for transient failures (rate limits and empty responses).
_MAX_RETRIES = 4
_RATE_LIMIT_BASE_SECONDS = 5    # doubles each attempt: 5, 10, 20, 40
_EMPTY_RESPONSE_BASE_SECONDS = 3

_INTER_CALL_SECONDS = 0.5       # Groq handles faster throughput than free OpenRouter

_logged_provider = False


def call_llm(user_prompt: str, max_tokens: int = 512, expect_json: bool = True) -> str:
    """Call the LLM via OpenRouter and return the raw text response.

    Retries up to _MAX_RETRIES times on rate-limit (429) and empty responses.
    Raises RuntimeError loudly on all other failures so they are never silently
    scored as "no issues found."
    """
    import requests  # stdlib-adjacent; always available

    base_url, model, api_key = _provider_config()

    global _logged_provider
    if not _logged_provider:
        print(f"[call_llm] provider={base_url} model={model}", flush=True)
        _logged_provider = True

    time.sleep(_INTER_CALL_SECONDS)

    rl_delay = _RATE_LIMIT_BASE_SECONDS
    er_delay = _EMPTY_RESPONSE_BASE_SECONDS
    raw = ""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": (
                        [
                            {"role": "system", "content": "Respond with valid JSON only. No explanation, no prose, no markdown code fences."},
                            {"role": "user", "content": user_prompt},
                        ]
                        if expect_json
                        else [{"role": "user", "content": user_prompt}]
                    ),
                },
                timeout=60,
            )
            if resp.status_code == 429:
                if attempt == _MAX_RETRIES:
                    raise RuntimeError(f"call_llm rate-limited after all retries. Last response: {resp.text[:300]}")
                print(f"[call_llm] rate-limited (attempt {attempt + 1}/{_MAX_RETRIES}), waiting {rl_delay}s …", flush=True)
                time.sleep(rl_delay)
                rl_delay *= 2
                continue
            if not resp.ok:
                raise RuntimeError(f"call_llm HTTP {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            # OpenRouter may return 200 with an error body (provider-level 429/502 etc.)
            if "error" in data and "choices" not in data:
                err = data["error"]
                code = err.get("code", 0)
                msg = str(err).lower()
                retryable = code in (429, 502, 503) or "rate" in msg or "overload" in msg or "unavailable" in msg
                if retryable:
                    if attempt == _MAX_RETRIES:
                        raise RuntimeError(f"call_llm provider error after all retries: {err}")
                    print(f"[call_llm] retryable provider error {code} (attempt {attempt + 1}/{_MAX_RETRIES}), waiting {rl_delay}s …", flush=True)
                    time.sleep(rl_delay)
                    rl_delay *= 2
                    continue
                raise RuntimeError(f"call_llm provider error: {err}")

            raw = (data["choices"][0]["message"]["content"] or "").strip()
            if raw:
                break
            # Empty response
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"call_llm received empty response after all retries. Full response: {data}")
            print(f"[call_llm] empty response (attempt {attempt + 1}/{_MAX_RETRIES}), waiting {er_delay}s …", flush=True)
            time.sleep(er_delay)
            er_delay *= 2

        except requests.Timeout:
            if attempt == _MAX_RETRIES:
                raise RuntimeError("call_llm timed out after all retries")
            print(f"[call_llm] timeout (attempt {attempt + 1}/{_MAX_RETRIES}), waiting {rl_delay}s …", flush=True)
            time.sleep(rl_delay)
            rl_delay *= 2

    if expect_json:
        # Strip markdown code fences that some models wrap JSON in.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return raw
