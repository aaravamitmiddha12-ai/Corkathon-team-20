"""out/handover.json: what the web pages show. Uses manual tags, no API."""

import json

import pandas as pd
import pytest

from src.export import build, key_phrase, project_limit_time, projected_label, reading_unit, write
from src.pipeline import run


@pytest.fixture(scope="module")
def data():
    return build(run(mode="manual"))


def item(data, asset_id):
    return next(i for i in data["items"] if i["asset_id"] == asset_id)


def ts(hhmm):
    return pd.Timestamp(f"2026-11-07 {hhmm}")


def test_counts_match_the_sample_pack(data):
    # not_urgent is 8: assets.json gained CR-B2 and INC-2 (used by the day shift); nothing is ever dropped.
    assert data["counts"] == {"top": 5, "clash": 2, "not_urgent": 8, "carried_over": 0,
                              "alerts": 14, "tickets": 6, "note_lines": 10}


def test_items_carry_the_new_card_fields(data):
    wfi = item(data, "WFI-LOOP-1")
    assert wfi["due_by"] == "2026-11-08T03:09:00"
    assert wfi["due_label"] == "Due by Sun 03:09 · 20 h left" and wfi["overdue"] is False
    assert 2 <= len(wfi["bullets"]) <= 3 and wfi["why"] == " ".join(wfi["bullets"])
    assert item(data, "FRZ-12")["due_by"] is None


def test_day_shift_export_and_carry_forward():
    from src import respond
    from src.load import SHIFTS
    night = run(mode="manual", shift="night")
    respond.dismiss("night", SHIFTS["night"].handover, night.findings["FRZ-12"], "S. O'Brien",
                    "Known sensor or instrument fault", expiry="24h")
    respond.dismiss("night", SHIFTS["night"].handover, night.findings["CH-2-P3"], "S. O'Brien",
                    "Already handled", expiry="24h")
    day = build(run(mode="manual", shift="day"))
    assert day["handover"]["eyebrow"] == "DAY → NIGHT · SAT 7 NOV · 19:00"
    assert day["handover"]["outgoing_engineer"] == "S. O'Brien"
    assert day["heading"].startswith("Good evening.")
    assert day["timeline"]["start"] == "07:00" and day["timeline"]["minutes"] == 720
    assert [c["asset_id"] for c in day["carried_over"]] == ["FRZ-12"]
    assert item(day, "CH-2-P3")["dismissed_earlier_now_worse"] is True
    minutes = [e["minutes"] for e in day["events"]]
    assert minutes == sorted(minutes) and 0 <= minutes[0] and minutes[-1] <= 720


def test_summary_is_generated_from_the_counts(data):
    assert data["summary"] == {"lead": "5 things need you.", "clash": "2 of them the notes got wrong."}


def test_header_fields_come_from_the_log(data):
    assert data["handover"]["eyebrow"] == "NIGHT → DAY · SAT 7 NOV · 07:00"
    assert data["handover"]["outgoing_engineer"] == "D. Murphy"
    assert data["site"] == "BrightLeaf Biologics (Cork site)"


def test_only_freezer_and_wfi_are_clashes(data):
    assert {i["asset_id"] for i in data["items"] if i["clash"]} == {"FRZ-12", "WFI-LOOP-1"}


def test_amber_alerts_match_the_detector(data):
    amber = [(e["asset_id"], e["time"]) for e in data["events"] if e["kind"] == "alert" and e["clash"]]
    assert amber == [("FRZ-12", "23:14"), ("FRZ-12", "02:41"), ("WFI-LOOP-1", "03:52"),
                     ("WFI-LOOP-1", "04:58"), ("FRZ-12", "06:19")]


def test_low_alert_after_a_reassuring_note_is_not_amber(data):
    """AHU-4 (info) and the door (low) follow reassuring notes, but the detector doesn't call them clashes."""
    others = [e for e in data["events"] if e["asset_id"] in ("AHU-4", "DOOR-LAB-B")]
    assert others and not any(e["clash"] for e in others)


def test_clash_notes_are_marked(data):
    assert [e["time"] for e in data["events"] if e["kind"] == "note" and e["clash"]] == ["21:05", "23:15", "03:10"]


def test_events_are_complete_and_in_time_order(data):
    minutes = [e["minutes"] for e in data["events"]]
    assert len(minutes) == 14 + 10
    assert minutes == sorted(minutes)
    assert 0 <= minutes[0] and minutes[-1] <= data["timeline"]["minutes"]


def test_quoted_words_are_really_in_the_note(data):
    for e in data["events"]:
        if e["kind"] == "note":
            assert e["key_words"] in e["text"].lower()


def test_key_phrase_falls_back_to_first_words():
    assert key_phrase("Compressor making a noise") == "compressor making a"


def test_chiller_gets_a_projected_limit_time(data):
    chiller = item(data, "CH-2-P3")
    assert chiller["projected_limit_time"].startswith("2026-11-07T09:41")
    assert chiller["projected_limit_time_recent_pace"].startswith("2026-11-07T07:49")
    assert chiller["projected_limit_label"] == "Trips ~07:50–09:40"


def test_label_is_a_single_time_when_both_estimates_agree():
    assert projected_label(ts("09:41")) == "Trips ~09:40"
    assert projected_label(ts("09:41"), ts("09:39")) == "Trips ~09:40"


def test_label_range_runs_earliest_first_when_the_climb_is_slowing():
    assert projected_label(ts("08:00"), ts("09:30")) == "Trips ~08:00–09:30"


def test_evidence_lines_use_real_units(data):
    assert item(data, "CH-2-P3")["evidence"] == "3 medium alerts, 6.8 to 8.1 mm/s, limit 9.0 mm/s · latest not acknowledged"
    assert item(data, "HPLC-07")["evidence"] == "INC-4471 due 09:00 today"


def test_only_the_chiller_is_projected(data):
    """The freezer and WFI are already past their limits; the others have no readings."""
    assert [i["asset_id"] for i in data["items"] if "projected_limit_time" in i] == ["CH-2-P3"]


def test_projection_fits_a_straight_line():
    points = [(ts("01:00"), 1.0), (ts("02:00"), 2.0), (ts("03:00"), 3.0)]
    assert project_limit_time(points, 5.0, True, now=ts("03:00")) == ts("05:00")


def test_projection_for_a_floor_limit():
    points = [(ts("01:00"), 5.0), (ts("02:00"), 4.0), (ts("03:00"), 3.0)]
    assert project_limit_time(points, 1.0, False, now=ts("03:00")) == ts("05:00")


@pytest.mark.parametrize("points, limit", [
    ([(ts("01:00"), 1.0), (ts("02:00"), 2.0)], 5.0),                           # fewer than 3 readings
    ([(ts("01:00"), 1.0), (ts("02:00"), 2.0), (ts("03:00"), 3.0)], None),      # no limit
    ([(ts("01:00"), 1.0), (ts("02:00"), 2.0), (ts("03:00"), 6.0)], 5.0),       # already past it
    ([(ts("01:00"), 3.0), (ts("02:00"), 2.0), (ts("03:00"), 1.0)], 5.0),       # heading away
    ([(ts("01:00"), 2.0), (ts("01:00"), 3.0), (ts("01:00"), 4.0)], 5.0),       # same time: no line
])
def test_projection_is_omitted(points, limit):
    assert project_limit_time(points, limit, True, now=ts("00:00")) is None


def test_projection_before_now_is_omitted():
    points = [(ts("01:00"), 1.0), (ts("02:00"), 2.0), (ts("03:00"), 3.0)]
    assert project_limit_time(points, 5.0, True, now=ts("06:00")) is None


def test_trend_lines_only_for_worsening_assets(data):
    trending = {r["id"]: r["trend"] for r in data["timeline"]["rows"] if r["trend"]}
    assert set(trending) == {"FRZ-12", "CH-2-P3"}
    assert [p["label"] for p in trending["CH-2-P3"]["points"]] == ["6.8 mm/s", "7.4", "8.1 / 9.0"]
    assert trending["FRZ-12"]["points"][-1]["label"] == "-61.9 / -70.0"


def test_timeline_has_a_row_per_top_asset_plus_other(data):
    assert [r["id"] for r in data["timeline"]["rows"]] == [i["asset_id"] for i in data["items"]] + ["Other"]
    assert data["timeline"]["rows"][0]["description"] == "-80 °C freezer · GMP"


@pytest.mark.parametrize("message, unit", [
    ("Temperature -64.8C above alarm limit -70C", "°C"),
    ("Conductivity 1.6 uS/cm exceeds limit 1.3 uS/cm (duration 6s)", "µS/cm"),
    ("Pump vibration 6.8 mm/s (warn 6.0, alarm 9.0)", "mm/s"),
    ("Toner empty", ""),
])
def test_reading_unit(message, unit):
    assert reading_unit(message) == unit


def test_written_files_hold_the_same_data(data, tmp_path):
    path = write(data, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == data
    script = (tmp_path / "handover.js").read_text(encoding="utf-8")
    assert script.startswith("window.HANDOVER_DATA = ")
    assert json.loads(script.removeprefix("window.HANDOVER_DATA = ").rstrip().removesuffix(";")) == data
