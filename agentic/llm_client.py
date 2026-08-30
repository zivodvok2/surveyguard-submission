from __future__ import annotations

import os
import re
import time

# Provider / model used for all LLM calls in this repo.
# OpenRouter is used as the inference provider (OpenAI-compatible endpoint).
PROVIDER = "openrouter"
MODEL = "minimax/minimax-m3:free"

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Retry configuration for transient failures (rate limits and empty responses).
_MAX_RETRIES = 4
_RATE_LIMIT_BASE_SECONDS = 10   # doubles each attempt: 10, 20, 40, 80
_EMPTY_RESPONSE_BASE_SECONDS = 3  # doubles each attempt: 3, 6, 12, 24

# Minimum gap between calls to stay within free-tier rate limits.
_INTER_CALL_SECONDS = 1

_logged_provider = False


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError(
            "No API key found. Set OPENROUTER_API_KEY (preferred) or GROQ_API_KEY."
        )
    return key


def call_llm(user_prompt: str, max_tokens: int = 512, expect_json: bool = True) -> str:
    """Call the LLM via OpenRouter and return the raw text response.

    Retries up to _MAX_RETRIES times on rate-limit (429) and empty responses.
    Raises RuntimeError loudly on all other failures so they are never silently
    scored as "no issues found."
    """
    import requests  # stdlib-adjacent; always available

    global _logged_provider
    if not _logged_provider:
        print(f"[call_llm] provider={PROVIDER} model={MODEL} endpoint={_OPENROUTER_BASE}", flush=True)
        _logged_provider = True

    time.sleep(_INTER_CALL_SECONDS)  # throttle to stay within rate limits

    rl_delay = _RATE_LIMIT_BASE_SECONDS
    er_delay = _EMPTY_RESPONSE_BASE_SECONDS
    raw = ""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{_OPENROUTER_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_api_key()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/surveyguard",
                    "X-Title": "SurveyGuard",
                },
                json={
                    "model": MODEL,
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
