"""Drive the real Streamlit screens (no browser) with Streamlit's AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import respond
from src.load import SHIFTS
from src.pipeline import run

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TOP_NIGHT = ["FRZ-12", "WFI-LOOP-1", "CH-2-P3", "HPLC-07", "BAL-03"]


def start(shift: str = "night") -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, at.exception
    if shift != "night":
        at.radio(key="shift").set_value(shift).run()
        assert not at.exception, at.exception
    return at


def page_html(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def test_sign_off_disabled_until_every_item_has_a_response():
    at = start()
    assert at.button(key="signoff-night").disabled
    assert "0 of 5 responded" in page_html(at)
    for asset in TOP_NIGHT[:4]:
        at.button(key=f"got-night-{asset}").click().run()
        assert at.button(key="signoff-night").disabled
    at.button(key="got-night-BAL-03").click().run()
    assert "5 of 5 responded" in page_html(at)
    assert not at.button(key="signoff-night").disabled

    at.button(key="signoff-night").click().run()
    assert not at.exception, at.exception
    html = page_html(at)
    assert "Signed off by" in html and "read-only" in html
    assert at.button(key="got-night-FRZ-12").disabled      # locked after sign-off


def test_card_shows_dismissed_earlier_now_worse():
    night = run(mode="manual", shift="night")
    respond.dismiss("night", SHIFTS["night"].handover, night.findings["CH-2-P3"], "S. O'Brien",
                    "Already handled", expiry="24h")
    respond.dismiss("night", SHIFTS["night"].handover, night.findings["FRZ-12"], "S. O'Brien",
                    "Known sensor or instrument fault", reference="WO-1195", expiry="ticket")
    at = start("day")
    html = page_html(at)
    assert "Dismissed earlier, now worse" in html
    assert "8.9 mm/s is worse than 8.1 mm/s" in html
    assert "Carried over from last handover" in [s.value for s in at.subheader]
    assert "Previously dismissed: Known sensor or instrument fault (WO-1195)" in html


def test_dismiss_form_saves_a_response():
    at = start()
    at.button(key="dis-night-HPLC-07").click().run()
    at.selectbox(key="reason-night-HPLC-07").set_value("Expected - planned work")
    at.text_input(key="ref-night-HPLC-07").input("INC-4471")
    at.radio(key="expiry-night-HPLC-07").set_value("handover")
    at.button(key="FormSubmitter:dismiss-form-night-HPLC-07-Save dismissal").click().run()
    assert not at.exception, at.exception
    saved = respond.load_responses("night")["HPLC-07"]
    assert saved["kind"] == "dismissed" and saved["reference"] == "INC-4471"
    assert "Dismissed: Expected - planned work (INC-4471)" in page_html(at)


def test_draft_ticket_only_on_no_ticket_items_and_shows_a_code_block():
    at = start()
    keys = {b.key for b in at.button}
    assert "draft-night-CH-2-P3" in keys and "draft-night-HPLC-07" not in keys
    at.button(key="draft-night-CH-2-P3").click().run()
    assert any("DRAFT TICKET" in c.value and "CH-2-P3" in c.value for c in at.code)
    assert respond.load_responses("night")["CH-2-P3"]["kind"] == "ticket_drafted"


def test_before_you_go_saves_and_clears_the_banner():
    at = start()
    assert "Outgoing review not completed" in page_html(at)
    at.button(key="open-before-you-go").click().run()
    assert [t.value for t in at.title] == ["Before you go"]
    for asset in ["FRZ-12", "WFI-LOOP-1", "CH-2-P3"]:
        at.radio(key=f"choice-night-{asset}").set_value("real_issue" if asset == "CH-2-P3" else "fine")
    at.text_input(key="comment-night-CH-2-P3").input("Bearing noise, please raise it today")
    at.button(key="FormSubmitter:before-you-go-night-Save review").click().run()
    assert not at.exception, at.exception
    at.button(key="back-home").click().run()
    html = page_html(at)
    assert "Outgoing review not completed" not in html
    assert "Bearing noise, please raise it today" in html


@pytest.mark.parametrize("shift", ["night", "day"])
def test_both_handovers_render_all_sections(shift):
    at = start(shift)
    subheaders = [s.value for s in at.subheader]
    assert {"What the notes say", "Needs you first", "Handover record"} <= set(subheaders)
    assert any(e.label.startswith("Checked, not urgent") for e in at.expander)
    assert "Key:" in page_html(at)
