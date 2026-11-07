"""Edge cases found in review: odd data must never crash the app or skew the ranking."""

import shutil

import pytest

from src import explain, llm
from src.detect import detect, parse_limit, parse_value
from src.load import DATA_DIR, NO_ASSET, load_all
from src.pipeline import run
from src.score import rank
from src.tag_notes import tag_notes


@pytest.fixture
def pack_copy(tmp_path):
    """A writable copy of the sample pack."""
    dest = tmp_path / "pack"
    shutil.copytree(DATA_DIR, dest)
    return dest


def append(path, row):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(row + "\n")


def pipeline_on(data_dir):
    pack = load_all(data_dir)
    notes, _ = tag_notes(pack.notes, pack.assets, mode="manual")
    findings = detect(pack, notes)
    top, rest = rank(findings)
    explanations, _ = explain.explain_all(top, mode="manual")
    return pack, findings, top, rest, explanations


def test_unknown_severity_does_not_crash(pack_copy):
    append(pack_copy / "alerts.csv", "2026-11-07T06:40:00,BMS,AHU-4,critical,Fan failure,")
    append(pack_copy / "alerts.csv", "2026-11-07T06:41:00,BMS,AHU-4,weird,Something odd,")
    pack, findings, *_ = pipeline_on(pack_copy)
    assert set(pack.alerts["severity"]) <= {"info", "low", "medium", "high"}
    assert findings["AHU-4"].max_severity == "high"


def test_blank_asset_is_kept_but_not_matched_to_answer_key(pack_copy):
    append(pack_copy / "tickets.csv", "INC-5000,2026-11-06T10:00,,P4,open,2026-11-20T17:00,IT,Site-wide wifi outage")
    pack, findings, top, rest, _ = pipeline_on(pack_copy)
    assert NO_ASSET in findings                     # never dropped
    assert "" not in findings
    from src.evaluate import evaluate
    ev = evaluate([i.asset_id for i in top], pack.answer_key, list(findings))
    assert ev["matches"] == 5


def test_blank_due_date_does_not_crash(pack_copy):
    append(pack_copy / "tickets.csv", "INC-6000,2026-11-06T10:00,CH-2-P3,P3,open,,Maint,Check pump")
    _, findings, top, _, explanations = pipeline_on(pack_copy)
    assert "CH-2-P3" in explanations
    assert not findings["CH-2-P3"].no_open_ticket   # it has a live ticket now


def test_limit_comes_from_latest_alert_with_a_reading(pack_copy):
    append(pack_copy / "alerts.csv", "2026-11-07T06:05:00,BMS,CH-2-P3,low,Comms restored,")
    _, findings, *_ = pipeline_on(pack_copy)
    f = findings["CH-2-P3"]
    assert f.limit == 9.0 and f.near_limit and f.trend_worsening


def test_number_parsing_ignores_ids_and_warn_levels():
    assert parse_value("AHU-4 supply fan vibration 7.4 mm/s (alarm 9.0)") == 7.4
    assert parse_value("Temperature -64.8C above alarm limit -70C") == -64.8
    assert parse_limit("Pump vibration 6.8 mm/s (warn limit 6.0, alarm limit 9.0)") == 9.0
    assert parse_limit("Supply flow 1050 L/min (alarm below 1000 L/min)") == 1000
    assert parse_limit("Conductivity 1.6 uS/cm exceeds limit 1.3 uS/cm (duration 6s)") == 1.3


def test_sample_ranking_unchanged_by_fixes():
    result = run(mode="manual")
    assert [i.asset_id for i in result.top] == ["FRZ-12", "WFI-LOOP-1", "CH-2-P3", "HPLC-07", "BAL-03"]


# ----- the "never invent values" guard -----

@pytest.fixture(scope="module")
def frz_evidence():
    result = run(mode="manual")
    return explain.build_evidence(result.top[0])


def good(why, headline="FRZ-12 freezer alarming", action="Check FRZ-12 now."):
    return {"headline": headline, "why": why, "action": action, "citations": []}


@pytest.mark.parametrize("why", [
    "Readings rose from -64.8C to -61.9C after the 21:05 note said it seemed ok.",
    "Four high alarms overnight; the latest at 06:19 is not acknowledged.",
    "3 more alarms followed the 21:05 note, all past the -70C limit.",
    "It holds GMP retained samples in a -80C freezer.",
])
def test_guard_accepts_faithful_answers(frz_evidence, why):
    explain.check_llm_answer(good(why), frz_evidence)


@pytest.mark.parametrize("why", [
    "Freezer reached 61.9C, far above 70C.",          # signs dropped
    "There were 7 high alarms overnight.",             # 7 only appears in the date
    "Six alarms overnight and no ticket.",            # more alerts than the data has
    "Temperature hit -55C.",                           # invented value
])
def test_guard_rejects_unfaithful_answers(frz_evidence, why):
    with pytest.raises(explain.BadAnswer):
        explain.check_llm_answer(good(why), frz_evidence)


def test_guard_rejects_non_dict(frz_evidence):
    with pytest.raises(explain.BadAnswer):
        explain.check_llm_answer(["not", "a", "dict"], frz_evidence)


# ----- cache robustness -----

@pytest.mark.parametrize("content", [b"\xef\xbb\xbf{}", b"null", b"5", b"\xff\xfe{\x00}\x00", b"{broken"])
def test_bad_cache_files_are_ignored(tmp_path, monkeypatch, content):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    (tmp_path / "tags.json").write_bytes(content)
    (tmp_path / "explanations.json").write_bytes(content)
    result = run(mode="demo")
    assert result.top[0].asset_id == "FRZ-12"


def test_bom_cache_is_still_read(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    (tmp_path / "x.json").write_bytes(b'\xef\xbb\xbf{"a": 1}')
    assert llm.read_cache("x.json") == {"a": 1}


def test_cached_tags_from_another_model_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    pack = load_all()
    line = pack.notes["line"].iloc[1]
    llm.write_cache("tags.json", {line: {"asset_id": None, "reassuring": False,
                                         "mentions_future_action": False, "model": "some-old-model"}})
    tagged, _ = tag_notes(pack.notes, pack.assets, mode="demo")
    assert tagged["tag_source"].iloc[1] == "manual"


def test_one_refusal_does_not_stop_the_other_items(monkeypatch):
    result = run(mode="manual")
    calls = []

    def fake(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise llm.AnswerUnusable("the model declined this request")
        raise llm.AnswerUnusable("the reply was cut off")

    monkeypatch.setattr(llm, "ask_json", fake)
    monkeypatch.setattr(llm, "write_cache", lambda *a, **k: None)
    monkeypatch.setattr(llm, "read_cache", lambda *a, **k: {})
    explain.explain_all(result.top, mode="llm")
    assert len(calls) == len(result.top)
