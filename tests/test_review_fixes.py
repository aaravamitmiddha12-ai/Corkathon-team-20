"""Regression tests for the problems found in the second review."""

import json
import threading

import pandas as pd
import pytest

from src import record, respond, review, state
from src.charts import timeline
from src.detect import detect
from src.due import due_label
from src.load import SHIFTS, load_all
from src.pipeline import run
from src.tag_notes import tag_notes

NIGHT = SHIFTS["night"]


def ids(items):
    return [i.asset_id for i in items]


def dismiss_at_night(asset, reason="Known sensor or instrument fault", **kw):
    night = run(mode="manual", shift="night")
    return respond.dismiss("night", NIGHT.handover, night.findings[asset], "S. O'Brien", reason, **kw)


def test_real_issue_from_outgoing_engineer_brings_a_carried_item_back():
    dismiss_at_night("FRZ-12", expiry="24h")
    assert "FRZ-12" in ids(run(mode="manual", shift="day").carried)
    review.save("day", "FRZ-12", "real_issue", "Probe swap didn't fix it", "S. O'Brien")
    day = run(mode="manual", shift="day")
    item = next(i for i in day.top if i.asset_id == "FRZ-12")
    assert item.dismissal_status == "now_worse" and "real issue" in item.dismissal_detail


def test_ticket_expiry_needs_a_reference():
    with pytest.raises(ValueError):
        dismiss_at_night("HPLC-07", expiry="ticket")


def test_ticket_reference_matches_ignoring_case_and_expires_when_closed():
    dismiss_at_night("BAL-03", reason="Expected - planned work", expiry="ticket", reference=" cal-0932 ")
    assert "BAL-03" not in ids(run(mode="manual", shift="day").carried)   # CAL-0932 is closed by then


def test_unknown_ticket_reference_expires_once_the_asset_has_no_live_ticket():
    dismiss_at_night("HPLC-07", reason="Already handled", expiry="ticket", reference="WO-9999")
    assert "HPLC-07" not in ids(run(mode="manual", shift="day").carried)  # INC-4471 closed, WO-9999 unknown


def test_24_hour_dismissal_has_expired_exactly_24_hours_later():
    night = run(mode="manual", shift="night")
    d = respond.dismiss("night", NIGHT.handover, night.findings["FRZ-12"], "x", "Other", expiry="24h")
    f = night.findings["FRZ-12"]
    later = NIGHT.handover + pd.Timedelta(hours=24)
    assert respond.dismissal_status(d, f, "next", later, night.pack.tickets)[0] == "expired"
    assert respond.dismissal_status(d, f, "next", later - pd.Timedelta(minutes=1), night.pack.tickets)[0] == "active"


def test_draft_ticket_never_overwrites_a_dismissal():
    dismiss_at_night("CH-2-P3", reason="Already handled", expiry="24h")
    assert respond.ticket_drafted("night", "CH-2-P3", "S. O'Brien") is False
    assert respond.load_responses("night")["CH-2-P3"]["kind"] == "dismissed"
    assert "CH-2-P3" in respond.load_dismissals()


def test_redismissing_keeps_the_now_worse_history():
    dismiss_at_night("CH-2-P3", reason="Already handled", expiry="24h")
    day = run(mode="manual", shift="day")
    respond.dismiss("day", SHIFTS["day"].handover, day.findings["CH-2-P3"], "K. Walsh", "Other", expiry="24h")
    item = next(i for i in run(mode="manual", shift="day").top if i.asset_id == "CH-2-P3")
    assert item.dismissal_status == "now_worse"
    respond.got_it("day", "CH-2-P3", "K. Walsh")       # changing the response restores the earlier dismissal
    assert respond.load_dismissals()["CH-2-P3"]["shift"] == "night"


def test_second_sign_off_is_refused():
    result = run(mode="manual", shift="night")
    for item in result.top:
        respond.got_it("night", item.asset_id, "S. O'Brien")
    result = run(mode="manual", shift="night")
    rec, *_ = record.sign_off(result, "S. O'Brien", incoming="Jane Doe")
    assert rec["incoming_engineer"] == "Jane Doe" and rec["signed_off_by"] == "S. O'Brien"
    with pytest.raises(ValueError):
        record.sign_off(result, "Someone Else")


def test_damaged_state_entries_are_skipped_not_fatal(isolated_state):
    state.state_dir()
    (isolated_state / "dismissals.json").write_text(json.dumps({
        "FRZ-12": {"made_at": "yesterday", "reason": "x"},
        "CH-2-P3": {"made_at": "2026-11-07T07:00", "reason": "x", "worst_value": "8.1"},
        "WFI-LOOP-1": {"made_at": "2026-11-07T07:00", "reason": "x", "breaches": None},
        "AHU-4": {"made_at": "2026-11-07T07:00"},
    }), encoding="utf-8")
    (isolated_state / "responses.json").write_text('{"night": []}', encoding="utf-8")
    assert respond.load_dismissals() == {}
    run(mode="manual", shift="day")
    respond.got_it("night", "FRZ-12", "S. O'Brien")                 # a broken shift entry is replaced
    assert respond.load_responses("night")["FRZ-12"]["kind"] == "got_it"


def test_unreadable_state_file_is_kept_as_a_backup(isolated_state):
    state.state_dir()
    (isolated_state / "responses.json").write_text("{broken", encoding="utf-8")
    assert respond.load_responses("night") == {}
    assert list(isolated_state.glob("responses.corrupt-*.json"))


def test_simultaneous_saves_all_land():
    assets = [f"A-{n}" for n in range(30)]
    threads = [threading.Thread(target=respond.got_it, args=("night", a, "x")) for a in assets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(respond.load_responses("night")) == set(assets)


def test_far_deadlines_show_the_date_and_days():
    now = pd.Timestamp("2026-11-07 19:00")
    assert due_label(pd.Timestamp("2026-11-20 17:00"), now) == ("Due by Fri 20 Nov 17:00 · 12 days left", False)
    assert due_label(pd.Timestamp("2026-11-08 03:09"), now) == ("Due by Sun 03:09 · 8 h left", False)
    assert due_label(pd.Timestamp("2026-11-04 17:00"), now) == ("Overdue by 3 days", True)


def test_deviation_window_carries_into_the_next_shift_without_a_ticket():
    pack = load_all(shift="day")
    pack.tickets = pack.tickets[pack.tickets["id"] != "DEV-2207"]   # nobody raised the deviation
    notes, _ = tag_notes(pack.notes, pack.assets, mode="manual")
    f = detect(pack, notes)["WFI-LOOP-1"]
    assert f.due_by == pd.Timestamp("2026-11-08 03:09") and f.due_soon
    assert "Sat 03:09" in f.due_by_source


def test_timeline_ticks_start_at_the_shift_start():
    for shift in ("night", "day"):
        fig = timeline(run(mode="manual", shift=shift))
        assert pd.Timestamp(fig.layout.xaxis.tick0) == SHIFTS[shift].start
