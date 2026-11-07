"""The five features: due-by, notes vs data, Before you go, Respond (incl. carry-forward), Handover record."""

import json

import pandas as pd
import pytest

from src import record, respond, review
from src.due import due_label
from src.load import SHIFTS, load_all
from src.pipeline import run

NIGHT, DAY = SHIFTS["night"], SHIFTS["day"]


def ids(items):
    return [i.asset_id for i in items]


def dismiss_at_night(asset, reason, expiry="24h", reference=""):
    night = run(mode="manual", shift="night")
    respond.dismiss("night", NIGHT.handover, night.findings[asset], "S. O'Brien", reason,
                    reference=reference, note="test", expiry=expiry)


# ----- Feature 1: due-by -----

def test_wfi_due_by_is_first_excursion_plus_24h():
    f = run(mode="manual", shift="night").findings["WFI-LOOP-1"]
    assert f.due_by == pd.Timestamp("2026-11-08 03:09")


def test_due_by_from_tickets_and_calibration():
    findings = run(mode="manual", shift="night").findings
    assert findings["HPLC-07"].due_by == pd.Timestamp("2026-11-07 09:00")
    assert findings["BAL-03"].due_by == pd.Timestamp("2026-11-07 17:00")
    assert "calibration" in findings["BAL-03"].due_by_source


def test_due_soon_means_before_end_of_incoming_shift():
    findings = run(mode="manual", shift="night").findings
    assert findings["HPLC-07"].due_soon and findings["BAL-03"].due_soon
    assert not findings["WFI-LOOP-1"].due_soon      # Sun 03:09 is after Sat 19:00
    day = run(mode="manual", shift="day").findings
    assert day["WFI-LOOP-1"].due_soon               # DEV-2207 due Sun 03:09, before Sun 07:00


def test_due_label_text():
    now = pd.Timestamp("2026-11-07 07:00")
    assert due_label(pd.Timestamp("2026-11-08 03:09"), now) == ("Due by Sun 03:09 · 20 h left", False)
    assert due_label(pd.Timestamp("2026-11-07 07:45"), now) == ("Due by Sat 07:45 · 45 min left", False)
    assert due_label(pd.Timestamp("2026-11-07 05:00"), now) == ("Overdue by 2 h", True)
    assert due_label(None, now) == ("", False)


# ----- Feature 2: notes vs data, on the new day shift too -----

def test_day_shift_clash_and_no_ticket():
    f = run(mode="manual", shift="day").findings
    assert f["CH-2-P3"].clash and f["CH-2-P3"].no_open_ticket     # "seems stable", 8.6 and 8.9 after
    assert f["CR-B2"].no_open_ticket and f["CR-B2"].trend_worsening  # floor limit, falling
    assert not f["CR-B2"].higher_worse
    assert f["INC-2"].no_open_ticket                             # note only, no alerts


# ----- Feature 3: Before you go -----

def test_before_you_go_lists_only_clash_or_no_ticket():
    result = run(mode="manual", shift="night")
    assert ids(result.review_items) == ["FRZ-12", "WFI-LOOP-1", "CH-2-P3"]
    assert not result.review_complete


def test_real_issue_adds_score_and_fine_does_not_lower_it():
    before = {i.asset_id: i.score for i in run(mode="manual", shift="night").top}
    review.save("night", "CH-2-P3", "real_issue", "Bearing is going", "D. Murphy")
    review.save("night", "FRZ-12", "fine", "Probe is faulty", "D. Murphy")
    after = run(mode="manual", shift="night")
    scores = {i.asset_id: i.score for i in after.top}
    assert scores["CH-2-P3"] == before["CH-2-P3"] + 20
    assert scores["FRZ-12"] == before["FRZ-12"]
    assert not after.review_complete
    review.save("night", "WFI-LOOP-1", "didnt_know", "", "D. Murphy")
    assert run(mode="manual", shift="night").review_complete


# ----- Feature 4: Respond and carry-forward -----

def test_dismissed_sensor_fault_carries_forward_quietly():
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault")
    day = run(mode="manual", shift="day")
    assert "FRZ-12" not in ids(day.top)
    assert "FRZ-12" in ids(day.rest) and "FRZ-12" in ids(day.carried)
    item = next(i for i in day.rest if i.asset_id == "FRZ-12")
    assert item.dismissal_status == "active"
    assert ("previously dismissed", "x0.3") in item.breakdown


def test_dismissal_that_gets_worse_is_ignored():
    dismiss_at_night("CH-2-P3", "Already handled")
    day = run(mode="manual", shift="day")
    item = next(i for i in day.top if i.asset_id == "CH-2-P3")
    assert item.dismissal_status == "now_worse"     # 8.9 > 8.1
    assert "8.9" in item.dismissal_detail and "8.1" in item.dismissal_detail
    assert ids(day.top)[0] == "CH-2-P3"             # ranked normally, still first


def test_dismissal_does_not_change_its_own_handover():
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault")
    night = run(mode="manual", shift="night")
    assert ids(night.top)[0] == "FRZ-12"
    assert night.responses["FRZ-12"]["kind"] == "dismissed"


def test_this_handover_only_dismissal_does_not_carry():
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault", expiry="handover")
    day = run(mode="manual", shift="day")
    assert "FRZ-12" not in ids(day.carried)


def test_until_ticket_closed_dismissal():
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault", expiry="ticket", reference="WO-1195")
    assert "FRZ-12" in ids(run(mode="manual", shift="day").carried)       # WO-1195 is open
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault", expiry="ticket", reference="INC-4459")
    assert "FRZ-12" not in ids(run(mode="manual", shift="day").carried)   # INC-4459 is resolved


def test_got_it_replaces_a_dismissal_made_at_the_same_handover():
    dismiss_at_night("FRZ-12", "Known sensor or instrument fault")
    respond.got_it("night", "FRZ-12", "S. O'Brien")
    assert "FRZ-12" not in respond.load_dismissals()
    assert run(mode="manual", shift="night").responses["FRZ-12"]["kind"] == "got_it"


def test_draft_ticket_is_prefilled():
    result = run(mode="manual", shift="night")
    from src.explain import evidence_rows
    item = result.top[2]  # CH-2-P3
    text = respond.draft_ticket(item, result.explanations[item.asset_id]["headline"],
                                evidence_rows(item), result.shift.label, "S. O'Brien")
    assert "CH-2-P3" in text and "P2 (suggested)" in text
    assert "Pump vibration 8.1 mm/s" in text and "01:30" in text


def test_progress_and_sign_off_gate():
    result = run(mode="manual", shift="night")
    assert result.responded_count == 0
    assert not respond.all_responded(result.top, result.responses)
    for item in result.top[:4]:
        respond.got_it("night", item.asset_id, "S. O'Brien")
    result = run(mode="manual", shift="night")
    assert result.responded_count == 4
    assert not respond.all_responded(result.top, result.responses)
    respond.ticket_drafted("night", result.top[4].asset_id, "S. O'Brien")
    result = run(mode="manual", shift="night")
    assert respond.all_responded(result.top, result.responses)


# ----- Feature 5: Handover record -----

def test_sign_off_writes_a_record(isolated_state):
    for asset in ["FRZ-12", "WFI-LOOP-1", "CH-2-P3", "HPLC-07"]:
        respond.got_it("night", asset, "S. O'Brien")
    result = run(mode="manual", shift="night")
    with pytest.raises(ValueError):
        record.sign_off(result, "S. O'Brien")          # not everything has a response yet
    night = run(mode="manual", shift="night")
    respond.dismiss("night", NIGHT.handover, night.findings["BAL-03"], "S. O'Brien",
                    "Expected - planned work", reference="CAL-0932", expiry="handover")
    review.save("night", "FRZ-12", "real_issue", "Please check it first", "D. Murphy")
    result = run(mode="manual", shift="night")
    rec, json_path, html_path = record.sign_off(result, "S. O'Brien")

    assert json_path.exists() and html_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["shift"] == "Sat 7 Nov, 07:00 handover"
    assert saved["outgoing_engineer"] == "D. Murphy" and saved["signed_off_by"] == "S. O'Brien"
    assert [i["asset"] for i in saved["items"]] == ids(result.top)
    bal = next(i for i in saved["items"] if i["asset"] == "BAL-03")
    assert bal["response"] == "Dismissed" and bal["reason"] == "Expected - planned work"
    frz = next(i for i in saved["items"] if i["asset"] == "FRZ-12")
    assert frz["outgoing_comment"] == "Please check it first"
    assert len(saved["not_urgent"]) == len(result.rest)
    assert "PRN-QC-02" in html_path.read_text(encoding="utf-8")
    assert record.latest("night")["signed_off_by"] == "S. O'Brien"
    assert record.latest("day") is None
