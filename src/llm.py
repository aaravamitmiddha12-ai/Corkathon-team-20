"""Small shared helper for the two LLM jobs (tagging notes, writing explanations).

The LLM never decides the ranking. It only returns JSON that matches a schema,
and every answer is cached on disk so the demo can run offline.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"

DEFAULT_MODEL = "claude-sonnet-5-5"

# Models that accept the server-side refusal fallback on the Claude API.
# If one of these declines a request, the API retries it on a suitable model.
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}


class LLMUnavailable(Exception):
    """Raised when we can't get a usable answer. Callers fall back to offline logic."""


class AnswerUnusable(LLMUnavailable):
    """The API worked but this one reply can't be used (refused, cut off, bad JSON). Worth trying the next item."""


def model_name() -> str:
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


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
    """Send one request and return the JSON object the model produced.

    Uses structured outputs, so the reply is guaranteed to match `schema`.
    (Current Claude models reject `temperature`; the schema plus the cache keep
    results stable instead.)
    """
    if not has_api_key():
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")

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
