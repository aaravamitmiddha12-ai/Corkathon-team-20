"""Small shared helper for the two LLM jobs (tagging notes, writing explanations).

The LLM never decides the ranking. It only returns JSON that matches a schema,
and every answer is cached on disk so the demo can run offline.

Two providers: Anthropic (Claude) and Google (Gemini, which has a free tier). The one used is
LLM_PROVIDER if set, otherwise whichever has a key, Anthropic first. Keys and settings come from the
environment or from .streamlit/secrets.toml.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"   # answers in a few seconds on the free tier
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}
SETTINGS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER", "LLM_MODEL")

# Models that accept the server-side refusal fallback on the Claude API.
# If one of these declines a request, the API retries it on a suitable model.
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}


class LLMUnavailable(Exception):
    """Raised when we can't get a usable answer. Callers fall back to offline logic."""


# Why the provider last failed as a whole (bad key, no credits, rate limit, no network), or None. The app reads
# this after a live run and, if it's set, switches itself to offline instead of showing errors.
last_unavailable: str | None = None


class AnswerUnusable(LLMUnavailable):
    """The API worked but this one reply can't be used (refused, cut off, bad JSON). Worth trying the next item."""


def provider() -> str | None:
    """Which provider to call, or None when there's no key for one."""
    chosen = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if chosen in KEYS:
        return chosen if os.environ.get(KEYS[chosen]) else None
    return next((name for name, key in KEYS.items() if os.environ.get(key)), None)


def provider_label() -> str:
    return {"anthropic": "Claude", "gemini": "Gemini"}.get(provider() or "", "")


def model_name() -> str:
    return os.environ.get("LLM_MODEL") or (DEFAULT_GEMINI_MODEL if provider() == "gemini" else DEFAULT_MODEL)


def secrets_file() -> Path:
    """Where a key can be kept so it needn't be set in every terminal. Git ignores this file."""
    return Path(os.environ.get("BATON_SECRETS_FILE", ROOT / ".streamlit" / "secrets.toml"))


def load_api_key() -> bool:
    """Put the keys and settings from the secrets file into the environment, where the clients read them.
    Anything already set in the environment wins. Returns whether a provider is now usable."""
    path = secrets_file()
    if path.is_file():
        import tomllib
        try:
            saved = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):  # a broken file means no keys, not a crash
            saved = {}
        for name in SETTINGS:
            value = saved.get(name)
            if isinstance(value, str) and value.strip() and not os.environ.get(name):
                os.environ[name] = value.strip()
    return provider() is not None


def has_api_key() -> bool:
    return provider() is not None


# ---------- disk cache ----------

def read_cache(name: str) -> dict:
    path = CACHE_DIR / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig also accepts a BOM from Notepad
    except (ValueError, OSError):  # bad JSON or bad encoding: ignore the cache rather than crash
        return {}
    return data if isinstance(data, dict) else {}


def write_cache(name: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


# ---------- the API call ----------

def ask_json(system: str, user: str, schema: dict, effort: str = "low") -> dict:
    """Send one request and return the JSON object the model produced. A failure of the provider as a whole
    (not just of this one answer) is also noted in last_unavailable."""
    global last_unavailable
    try:
        return _ask_json(system, user, schema, effort)
    except AnswerUnusable:
        raise
    except LLMUnavailable as e:
        last_unavailable = str(e)
        raise


def _ask_json(system: str, user: str, schema: dict, effort: str = "low") -> dict:
    """Send one request and return the JSON object the model produced.

    Uses structured outputs, so the reply is guaranteed to match `schema`.
    (Current Claude models reject `temperature`; the schema plus the cache keep
    results stable instead.)
    """
    if not has_api_key():
        raise LLMUnavailable("no API key is set (ANTHROPIC_API_KEY or GEMINI_API_KEY)")
    if provider() == "gemini":
        return ask_gemini(system, user, schema)

    import anthropic  # imported here so demo mode never needs it

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    model = model_name()
    request = dict(
        model=model,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )

    try:
        if model in FALLBACK_MODELS:
            response = client.beta.messages.create(
                **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            response = client.messages.create(**request)
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("API key was rejected") from e
    except anthropic.NotFoundError as e:
        raise LLMUnavailable(f"model '{model}' not found") from e
    except anthropic.RateLimitError as e:
        raise LLMUnavailable("rate limited, try again shortly") from e
    except anthropic.APIStatusError as e:
        if "credit balance" in str(e.message).lower():
            raise LLMUnavailable("the Anthropic account has no API credits (add some under Plans & Billing)") from e
        raise LLMUnavailable(f"API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMUnavailable("could not reach the API (offline?)") from e

    if response.stop_reason == "refusal":
        raise AnswerUnusable("the model declined this request")
    if response.stop_reason == "max_tokens":
        raise AnswerUnusable("the reply was cut off")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if not text:
        raise AnswerUnusable("empty reply")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnswerUnusable("reply was not valid JSON") from e
    if not isinstance(data, dict):
        raise AnswerUnusable("reply was not a JSON object")
    return data

# ---------- Gemini ----------

GEMINI_BUSY_FALLBACK = "gemini-3.1-flash-lite"   # lighter, quicker, and its own free-tier allowance
GEMINI_RETRY_WAITS = (1.0, 4.0)                   # seconds before each retry on "too many" or "busy"
_gemini_spent: set[str] = set()                   # models whose daily free allowance ran out (this run of the app)


def ask_gemini(system: str, user: str, schema: dict) -> dict:
    """The same job through Google's Gemini API, with its JSON-schema output. Plain HTTPS, so nothing
    extra to install. The free tier has small daily allowances per model and busy spells, so "too many" and
    "busy" move to the lighter model (which has its own allowance) and retry before giving up. A model whose
    daily allowance is gone isn't asked again until the app restarts."""
    import time
    import urllib.error

    chosen = model_name()
    model = GEMINI_BUSY_FALLBACK if chosen in _gemini_spent and not os.environ.get("LLM_MODEL") else chosen
    last_code = 0
    for attempt in range(len(GEMINI_RETRY_WAITS) + 1):
        try:
            return gemini_answer(_gemini_post(model, system, user, schema))
        except urllib.error.HTTPError as e:
            last_code = e.code
            detail = e.read().decode("utf-8", "replace")
            if e.code == 429 and "PerDay" in detail:
                _gemini_spent.add(model)
            if e.code in (429, 503) and attempt < len(GEMINI_RETRY_WAITS):
                if not os.environ.get("LLM_MODEL") and model != GEMINI_BUSY_FALLBACK:
                    model = GEMINI_BUSY_FALLBACK  # try the lighter model straight away
                elif model in _gemini_spent:
                    break                         # nothing left today on any model we'd try
                else:
                    time.sleep(GEMINI_RETRY_WAITS[attempt])
                continue
            if e.code in (401, 403):
                raise LLMUnavailable("Gemini API key was rejected") from e
            if e.code == 404:
                raise LLMUnavailable(f"Gemini model '{model}' not found") from e
            if e.code not in (429, 503):
                raise LLMUnavailable(f"Gemini API error {e.code}") from e
            break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMUnavailable("could not reach the Gemini API (offline?)") from e
        except ValueError as e:
            raise AnswerUnusable("Gemini sent something that wasn't JSON") from e
    if last_code == 429:
        raise LLMUnavailable("Gemini's free daily limit is used up, it resets tomorrow"
                             if model in _gemini_spent else "Gemini free-tier limit reached, try again in a minute")
    raise LLMUnavailable("Gemini is busy right now, try again shortly")


def _gemini_post(model: str, system: str, user: str, schema: dict) -> dict:
    import urllib.request

    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "maxOutputTokens": 4000}}
    request = urllib.request.Request(GEMINI_URL.format(model=model), data=json.dumps(body).encode("utf-8"),
                                     headers={"x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
                                              "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def gemini_answer(reply: dict) -> dict:
    """The JSON object inside a Gemini reply, or AnswerUnusable."""
    candidates = reply.get("candidates") or []
    if not candidates:
        raise AnswerUnusable("the model declined this request")
    finish = candidates[0].get("finishReason", "")
    if finish == "MAX_TOKENS":
        raise AnswerUnusable("the reply was cut off")
    if finish not in ("", "STOP"):
        raise AnswerUnusable("the model declined this request")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text:
        raise AnswerUnusable("empty reply")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnswerUnusable("reply was not valid JSON") from e
    if not isinstance(data, dict):
        raise AnswerUnusable("reply was not a JSON object")
    return data
