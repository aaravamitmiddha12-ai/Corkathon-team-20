"""Drive the real Streamlit screens (no browser) with Streamlit's AppTest."""

import re
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


def button_keys(at: AppTest) -> set:
    return {b.key for b in at.button}


def test_sign_off_appears_only_when_every_item_has_a_response():
    at = start()
    assert "signoff-night" not in button_keys(at)
    assert "0 of 5 handled" in page_html(at)
    for asset in TOP_NIGHT[:4]:
        at.button(key=f"got-night-{asset}").click().run()
        assert "signoff-night" not in button_keys(at)
    at.button(key="got-night-BAL-03").click().run()
    assert "5 of 5 handled · 5 got it" in page_html(at)
    assert not at.button(key="signoff-night").disabled

    at.button(key="signoff-night").click().run()
    assert not at.exception, at.exception
    html = page_html(at)
    assert "Signed off by" in html and "read-only" in html
    at.button(key="open-night-FRZ-12").click().run()       # still readable after sign-off...
    assert at.button(key="got-night-FRZ-12").disabled      # ...but locked


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
    assert 'role="heading" aria-level="2" aria-label="Carried over from last handover"' in page_html(at)
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
    html = page_html(at)
    assert all(f'role="heading" aria-level="2" aria-label="{h}"' in html for h in ("What the notes say", "Needs you first"))
    assert any(e.label.startswith("Checked, not urgent") for e in at.expander)
    assert "Key:" in page_html(at)


def test_dismiss_until_ticket_closed_without_reference_explains_why():
    at = start()
    at.button(key="dis-night-HPLC-07").click().run()
    at.radio(key="expiry-night-HPLC-07").set_value("ticket")
    at.button(key="FormSubmitter:dismiss-form-night-HPLC-07-Save dismissal").click().run()
    assert not at.exception, at.exception
    assert any("needs the ticket id" in e.value for e in at.error)
    assert "HPLC-07" not in respond.load_responses("night")


def test_carried_row_shows_the_outgoing_comment():
    from src import review
    night = run(mode="manual", shift="night")
    respond.dismiss("night", SHIFTS["night"].handover, night.findings["FRZ-12"], "S. O'Brien",
                    "Known sensor or instrument fault", expiry="24h")
    review.save("day", "FRZ-12", "fine", "Probe replacement booked for Monday", "S. O'Brien")
    html = page_html(start("day"))
    assert "Probe replacement booked for Monday" in html
    assert "<b>FRZ-12</b> · FRZ-12:" not in html                     # no repeated asset id


def test_typed_incoming_name_survives_switching_shifts():
    at = start()
    at.text_input(key="incoming_night").input("Jane Doe").run()
    at.radio(key="shift").set_value("day").run()
    at.radio(key="shift").set_value("night").run()
    assert at.text_input(key="incoming_night").value == "Jane Doe"
    at.button(key="got-night-FRZ-12").click().run()
    assert respond.load_responses("night")["FRZ-12"]["name"] == "Jane Doe"


def transient_style(at: AppTest) -> str:
    """The responses fragment's per-render rules (not the permanent style block or the sidebar's copy)."""
    return next(m.value for m in at.markdown if m.value.startswith("<style>") and "html .baton-nav-progress" in m.value)


def test_header_shows_the_name_and_no_expert_badge():
    html = page_html(start())
    assert "Baton · Sat 7 Nov, 07:00 handover" in re.sub(r"<[^>]+>", "", html)   # the title's words are masked one by one
    assert "From D. Murphy · night shift" in html
    assert "expert ranking" not in html


def test_handled_item_collapses_to_one_line_and_can_be_reopened():
    at = start()
    at.button(key="got-night-HPLC-07").click().run()
    assert "got-night-HPLC-07" not in button_keys(at)
    slim = [m.value for m in at.markdown if 'class="baton-slim' in m.value]
    assert len(slim) == 1 and "HPLC-07" in slim[0] and "Got it" in slim[0]
    assert '<span class="baton-mono">' in slim[0]  # the brief: times in monospace
    at.button(key="open-night-HPLC-07").click().run()
    assert "got-night-HPLC-07" in button_keys(at)
    at.button(key="collapse-night-HPLC-07").click().run()
    assert "got-night-HPLC-07" not in button_keys(at)


def test_drafted_ticket_stays_open_until_it_is_closed():
    at = start()
    at.button(key="draft-night-CH-2-P3").click().run()
    assert any("DRAFT TICKET" in c.value for c in at.code)   # handled, but still on screen to copy
    at.button(key="draft-night-CH-2-P3").click().run()
    assert not any("DRAFT TICKET" in c.value for c in at.code)
    assert "1 of 5 handled · 1 ticket drafted" in page_html(at)
    assert "open-night-CH-2-P3" in button_keys(at)


def test_no_entrance_on_render_and_only_the_item_just_responded_to_animates():
    """Sections reveal as they scroll into view (the page script), so no render carries an entrance."""
    at = start()
    assert "baton-in" not in transient_style(at) and "baton-segments baton-enter" not in page_html(at)
    at.button(key="got-night-FRZ-12").click().run()
    assert "baton-in" not in transient_style(at)
    at.button(key="got-night-WFI-LOOP-1").click().run()
    html = " ".join(m.value for m in at.markdown if "scroll-behavior" not in m.value)
    assert html.count("baton-seg-new") == 1 and html.count("baton-slim baton-done") == 1
    assert 'class="baton-slim baton-done"><span class="tick">✓</span> <b>WFI-LOOP-1' in html.replace('id="card-WFI-LOOP-1" ', "")


def test_every_anchor_target_exists():
    html = page_html(start())
    for asset in TOP_NIGHT:
        assert f'href="#card-{asset}"' in html and f'id="card-{asset}"' in html
    assert "Other (" in html


def test_first_screen_is_an_overview_of_the_handover():
    html = page_html(start())
    assert "Good morning, S. O&#x27;Brien. Here" in html or "Good morning, S. O'Brien. Here" in html
    assert '<div class="k">Needs you</div><div class="v">5</div>' in html
    assert '<div class="k">Notes vs data</div><div class="v">2</div>' in html          # FRZ-12 and WFI-LOOP-1
    assert '<div class="v mono">Sat 09:00</div>' in html and ">HPLC-07</span> · 2 h left" in html
    assert 'class="baton-cta" href="#card-FRZ-12"' in html and "Sign off</b> once all 5 are handled" in html


def test_app_stays_offline_even_with_a_key(monkeypatch):
    """For now the app never calls an AI service, whatever keys are set."""
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    from src import llm

    def no_calls(*a, **k):
        raise AssertionError("the app called the AI")

    monkeypatch.setattr(llm, "ask_json", no_calls)
    at = start()
    assert not at.exception and at.session_state["result"].mode == "demo"
    assert not any(b.key and b.key.startswith("baton-ai") for b in at.button)


def test_sidebar_lists_every_section_and_the_top_items():
    html = page_html(start())
    for n in range(1, 6):
        assert f'href="#sec-{n}"' in html and f'id="sec-{n}"' in html   # every nav link has its section
    for asset in TOP_NIGHT:
        assert f'class="baton-nav-asset" href="#card-{asset}"' in html and f'data-open="open-night-{asset}"' in html


def test_sidebar_dot_and_progress_follow_a_response():
    at = start()
    assert '--baton-count: "0 of 5 handled"' in transient_style(at)
    at.button(key="got-night-FRZ-12").click().run()
    style = transient_style(at)
    assert '--baton-count: "1 of 5 handled"; --baton-done: 0.200' in style
    assert 'html a.baton-nav-asset[href="#card-FRZ-12"] { --baton-dot: var(--baton-green)' in style
    assert 'href="#card-WFI-LOOP-1"] { --baton-dot' not in style
