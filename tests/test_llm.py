"""LLM-path tests with a fake model: no network, no API key needed."""

import os
import pytest

from src import explain, llm, tag_notes
from src.load import load_all
from src.pipeline import run


@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    return tmp_path


def test_no_api_key_falls_back_quietly(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = run(mode="llm")
    assert result.top[0].asset_id == "FRZ-12"
    assert set(result.notes["tag_source"]) == {"manual"}
    assert all(ex["source"] == "template" for ex in result.explanations.values())
    assert any("ANTHROPIC_API_KEY" in w for w in result.warnings)


KEY_SETTINGS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER", "LLM_MODEL")


@pytest.fixture
def no_keys(monkeypatch):
    """No keys before, and none left behind: load_api_key writes straight into the environment."""
    for name in KEY_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    yield
    for name in KEY_SETTINGS:
        os.environ.pop(name, None)


def test_key_comes_from_the_secrets_file_when_not_in_the_environment(monkeypatch, tmp_path, no_keys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    secrets = tmp_path / "secrets.toml"
    monkeypatch.setenv("BATON_SECRETS_FILE", str(secrets))
    assert llm.load_api_key() is False                        # no file: offline
    secrets.write_text('ANTHROPIC_API_KEY = "  sk-ant-test  "\n', encoding="utf-8")
    assert llm.load_api_key() is True
    assert llm.has_api_key() and os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test"


def test_environment_key_wins_over_the_file(monkeypatch, tmp_path, no_keys):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('ANTHROPIC_API_KEY = "from-file"\n', encoding="utf-8")
    monkeypatch.setenv("BATON_SECRETS_FILE", str(secrets))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert llm.load_api_key() and os.environ["ANTHROPIC_API_KEY"] == "from-env"


def test_a_broken_secrets_file_means_offline_not_a_crash(monkeypatch, tmp_path, no_keys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    secrets = tmp_path / "secrets.toml"
    secrets.write_text("this is = not [ toml", encoding="utf-8")
    monkeypatch.setenv("BATON_SECRETS_FILE", str(secrets))
    assert llm.load_api_key() is False




def test_provider_follows_the_keys_and_the_setting(monkeypatch, no_keys):
    assert llm.provider() is None
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert llm.provider() == "gemini" and llm.model_name() == llm.DEFAULT_GEMINI_MODEL
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert llm.provider() == "anthropic" and llm.model_name() == llm.DEFAULT_MODEL   # Anthropic first by default
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert llm.provider() == "gemini"
    monkeypatch.delenv("GEMINI_API_KEY")
    assert llm.provider() is None          # asked for Gemini, but it has no key: offline, not a surprise switch


def test_secrets_file_can_hold_a_gemini_key_and_the_choice(monkeypatch, tmp_path, no_keys):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('GEMINI_API_KEY = "g-key"\nLLM_PROVIDER = "gemini"\n', encoding="utf-8")
    monkeypatch.setenv("BATON_SECRETS_FILE", str(secrets))
    assert llm.load_api_key() and llm.provider() == "gemini" and llm.provider_label() == "Gemini"


def test_gemini_reply_is_read_and_checked():
    ok = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "thinking", "thought": True},
                                                                        {"text": '{"a": 1}'}]}}]}
    assert llm.gemini_answer(ok) == {"a": 1}                          # thought parts are skipped
    for bad in ({"candidates": []}, {"candidates": [{"finishReason": "SAFETY"}]},
                {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "[1]"}]}}]}):
        with pytest.raises(llm.AnswerUnusable):
            llm.gemini_answer(bad)


def test_gemini_errors_fall_back_quietly(monkeypatch, no_keys):
    import io
    import urllib.error
    import urllib.request

    monkeypatch.setenv("GEMINI_API_KEY", "g")

    def limited(*a, **k):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(urllib.request, "urlopen", limited)
    monkeypatch.setattr(llm, "GEMINI_RETRY_WAITS", (0, 0))
    monkeypatch.setattr(llm, "_gemini_spent", set())
    with pytest.raises(llm.LLMUnavailable, match="free-tier limit"):
        llm.ask_json("s", "u", {"type": "object"})
    assert llm.last_unavailable and "free-tier limit" in llm.last_unavailable


def test_gemini_busy_retries_on_the_lighter_model(monkeypatch, no_keys):
    import io
    import json as _json
    import urllib.error
    import urllib.request

    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(llm, "GEMINI_RETRY_WAITS", (0, 0))
    monkeypatch.setattr(llm, "_gemini_spent", set())
    seen = []

    class Reply(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def busy_then_ok(request, timeout=0):
        seen.append(request.full_url.split("/models/")[1].split(":")[0])
        if len(seen) == 1:
            raise urllib.error.HTTPError("u", 503, "busy", {}, io.BytesIO(b"{}"))
        ok = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"a": 1}'}]}}]}
        return Reply(_json.dumps(ok).encode())

    monkeypatch.setattr(urllib.request, "urlopen", busy_then_ok)
    assert llm.ask_json("s", "u", {"type": "object"}) == {"a": 1}
    assert seen == [llm.DEFAULT_GEMINI_MODEL, llm.GEMINI_BUSY_FALLBACK]


def test_llm_tags_are_used_and_cached(monkeypatch, temp_cache):
    calls = []

    def fake_ask(system, user, schema, effort="low"):
        calls.append(user)
        line = user.split("Log line:\n")[1]
        tag = tag_notes.MANUAL_TAGS[line]
        return {**tag, "asset_id": tag["asset_id"]}

    monkeypatch.setattr(llm, "ask_json", fake_ask)
    pack = load_all()
    tagged, warnings = tag_notes.tag_notes(pack.notes, pack.assets, mode="llm")
    assert not warnings
    assert set(tagged["tag_source"]) == {"llm"}
    assert len(calls) == len(pack.notes)
    assert (temp_cache / "tags.json").exists()

    # Demo mode now reads the cache and makes no calls.
    calls.clear()
    tagged2, _ = tag_notes.tag_notes(pack.notes, pack.assets, mode="demo")
    assert not calls
    assert set(tagged2["tag_source"]) == {"llm (cached)"}


def test_unknown_asset_from_llm_becomes_none(monkeypatch):
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: {
        "asset_id": "MADE-UP-9", "reassuring": True, "mentions_future_action": False})
    pack = load_all()
    tagged, _ = tag_notes.tag_notes(pack.notes.head(1), pack.assets, mode="llm")
    assert tagged["asset_id"].iloc[0] is None


def _top_item():
    result = run(mode="manual")
    return result.top[0]


def test_good_llm_explanation_is_used_and_bad_citations_dropped(monkeypatch, temp_cache):
    item = _top_item()
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: {
        "headline": "Freezer FRZ-12 keeps alarming; notes say fine",
        "bullets": ["Four high alarms rose from -64.8C to -61.9C after the 21:05 note said it seemed ok."],
        "action": "Move the retained samples to a backup freezer and raise a ticket.",
        "citations": ["alert 21:03", "alert 06:19", "note 21:05", "INC-9999"],
    })
    out, warnings = explain.explain_all([item], mode="llm")
    ex = out["FRZ-12"]
    assert not warnings
    assert ex["source"] == "llm"
    assert ex["citations"] == ["alert 21:03", "alert 06:19", "note 21:05"]  # INC-9999 removed
    assert (temp_cache / "explanations.json").exists()

    # The cached answer is reused in demo mode.
    out2, _ = explain.explain_all([item], mode="demo")
    assert out2["FRZ-12"]["source"] == "llm (cached)"


def test_llm_explanation_with_invented_number_is_rejected(monkeypatch):
    item = _top_item()
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: {
        "headline": "Freezer at -55C",
        "bullets": ["It reached -55C."],
        "action": "Check it.",
        "citations": [],
    })
    out, warnings = explain.explain_all([item], mode="llm")
    assert out["FRZ-12"]["source"] == "template"
    assert any("not in the evidence" in w for w in warnings)


def test_headline_is_trimmed_to_ten_words(monkeypatch):
    item = _top_item()
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: {
        "headline": "one two three four five six seven eight nine ten eleven twelve",
        "bullets": ["Notes said ok."], "action": "Check it.", "citations": ["note 21:05"],
    })
    out, _ = explain.explain_all([item], mode="llm")
    assert len(out["FRZ-12"]["headline"].split()) == 10


def test_api_failure_falls_back_to_template(monkeypatch):
    def boom(*a, **k):
        raise llm.LLMUnavailable("could not reach the API (offline?)")

    monkeypatch.setattr(llm, "ask_json", boom)
    out, warnings = explain.explain_all([_top_item()], mode="llm")
    assert out["FRZ-12"]["source"] == "template"
    assert warnings


def test_ask_json_without_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailable):
        llm.ask_json("s", "u", {"type": "object"})


def test_model_from_env(monkeypatch, no_keys):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.model_name() == "claude-sonnet-5-5"
    monkeypatch.setenv("LLM_MODEL", "claude-opus-5-5")
    assert llm.model_name() == "claude-opus-5-5"


def test_gemini_daily_limit_moves_to_the_lighter_model_and_stays_there(monkeypatch, no_keys):
    import io
    import json as _json
    import urllib.error
    import urllib.request

    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(llm, "GEMINI_RETRY_WAITS", (0, 0))
    monkeypatch.setattr(llm, "_gemini_spent", set())
    seen = []

    class Reply(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def main_spent(request, timeout=0):
        model = request.full_url.split("/models/")[1].split(":")[0]
        seen.append(model)
        if model == llm.DEFAULT_GEMINI_MODEL:
            raise urllib.error.HTTPError("u", 429, "quota", {}, io.BytesIO(b'{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}'))
        ok = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"a": 1}'}]}}]}
        return Reply(_json.dumps(ok).encode())

    monkeypatch.setattr(urllib.request, "urlopen", main_spent)
    assert llm.ask_json("s", "u", {"type": "object"}) == {"a": 1}
    assert llm.ask_json("s", "u", {"type": "object"}) == {"a": 1}
    assert seen == [llm.DEFAULT_GEMINI_MODEL, llm.GEMINI_BUSY_FALLBACK, llm.GEMINI_BUSY_FALLBACK]   # not asked again
