"""LLM-path tests with a fake model: no network, no API key needed."""

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
        "why": "Four high alarms rose from -64.8C to -61.9C after the 21:05 note said it seemed ok.",
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
        "why": "It reached -55C.",
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
        "why": "Notes said ok.", "action": "Check it.", "citations": ["note 21:05"],
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


def test_model_from_env(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.model_name() == "claude-sonnet-5-5"
    monkeypatch.setenv("LLM_MODEL", "claude-opus-5-5")
    assert llm.model_name() == "claude-opus-5-5"
