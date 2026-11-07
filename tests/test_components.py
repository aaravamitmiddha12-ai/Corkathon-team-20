"""The small HTML pieces of the Streamlit screens, and the timeline's shape."""

import re
from types import SimpleNamespace

import pandas as pd
import pytest

from src.charts import timeline
from src.pipeline import run
from ui.components import chip, limit_bar, limit_share, progress_caption, progress_segments, short_name


def finding(value, limit, warn=None, higher_worse=True, unit="mm/s"):
    return SimpleNamespace(latest_value=value, limit=limit, warn_limit=warn, higher_worse=higher_worse, unit=unit)


def item(asset):
    return SimpleNamespace(asset_id=asset)


@pytest.mark.parametrize("value, limit, higher_worse, inside", [
    (8.1, 9.0, True, True),       # positive ceiling, within
    (9.5, 9.0, True, False),      # positive ceiling, past
    (-75, -70, True, True),       # freezer colder than its limit: fine
    (-61.9, -70, True, False),    # freezer warmer than its limit: past it, though -61.9 / -70 < 1
    (11, 10, False, True),        # floor limit, within
    (9, 10, False, False),        # floor limit, past
])
def test_limit_share_respects_direction(value, limit, higher_worse, inside):
    assert (limit_share(value, limit, higher_worse) <= 1) == inside


@pytest.mark.parametrize("value, limit", [(0, 5), (5, 0), (-1, 5)])
def test_limit_share_gives_up_when_a_ratio_means_nothing(value, limit):
    assert limit_share(value, limit, True) is None


def test_limit_bar_within_the_limit():
    html = limit_bar(finding(8.1, 9.0, warn=6.0))
    assert "8.1 / 9.0 mm/s" in html and "width:90.0%" in html and "left:66.7%" in html
    assert "baton-limit over" not in html


def test_limit_bar_turns_red_past_the_limit():
    html = limit_bar(finding(-61.9, -70, unit="°C"))
    assert "baton-limit over" in html and "width:100.0%" in html and "-61.9 / -70.0 °C" in html


def test_limit_bar_on_a_floor_limit_puts_the_warning_before_the_alarm():
    html = limit_bar(finding(11, 10, warn=12, higher_worse=False, unit="Pa"))
    assert "baton-limit over" not in html
    assert "left:83.3%" in html and "width:90.9%" in html


@pytest.mark.parametrize("f", [finding(None, 9.0), finding(8.1, None)])
def test_no_bar_without_a_reading_and_a_limit(f):
    assert limit_bar(f) == ""


def test_only_the_clash_tag_has_a_colour_class():
    assert "hc-chip clash" in chip("Notes say OK, data disagrees", "clash")
    for key in ("no_open_ticket", "trend_worsening", "due_soon", "near_limit", "repeated"):
        html = chip("x", key)
        assert 'class="hc-chip"' in html and "<svg" in html and "style=" not in html


def test_progress_caption_counts_each_kind_and_skips_empty_ones():
    top = [item(a) for a in "ABCDE"]
    responses = {"A": {"kind": "got_it"}, "B": {"kind": "got_it"}, "C": {"kind": "dismissed"},
                 "D": {"kind": "ticket_drafted"}}
    assert progress_caption(top, responses) == "4 of 5 handled · 2 got it · 1 dismissed · 1 ticket drafted"
    assert progress_caption(top, {}) == "0 of 5 handled"


def test_progress_segments_mark_each_state_and_animate_only_the_new_one():
    top = [item(a) for a in "ABCD"]
    responses = {"A": {"kind": "got_it"}, "B": {"kind": "dismissed"}, "C": {"kind": "ticket_drafted"}}
    html = progress_segments(top, responses, just_changed="C")
    assert re.findall(r'class="(baton-seg [^"]*|baton-seg)"', html) == [
        "baton-seg got_it", "baton-seg dismissed", "baton-seg ticket_drafted baton-seg-new", "baton-seg"]


@pytest.mark.parametrize("asset_type, name", [
    ("-80C freezer", "freezer"), ("Water for Injection distribution loop", "water loop"),
    ("Chiller pump", "chiller pump"), ("HPLC", "HPLC"), ("Something new", "something new"), ("", ""),
])
def test_short_name(asset_type, name):
    assert short_name(asset_type) == name


@pytest.fixture(scope="module")
def night_timeline():
    return timeline(run(mode="manual", shift="night"))


def test_timeline_has_no_transitions_and_a_handover_line(night_timeline):
    fig = night_timeline
    assert fig.layout.transition.duration == 0 and not fig.frames
    assert fig.layout.shapes[0].line.dash == "dash"
    assert fig.layout.annotations[0].text == "Handover 07:00"
    assert fig.layout.xaxis.dtick == 2 * 3600 * 1000


def test_timeline_bands_run_from_the_note_to_the_last_alert_on_clash_rows(night_timeline):
    bands = [t for t in night_timeline.data if t.type == "bar"]
    assert sorted(b.y[0] for b in bands) == [0, 1]                      # FRZ-12 and WFI-LOOP-1
    wfi = next(b for b in bands if b.y[0] == 1)
    start = pd.Timestamp(wfi.base[0])
    assert start == pd.Timestamp("2026-11-07 03:10")
    assert start + pd.Timedelta(milliseconds=wfi.x[0]) == pd.Timestamp("2026-11-07 04:58:33")


def test_timeline_notes_sit_above_the_row_line(night_timeline):
    notes = next(t for t in night_timeline.data if t.name == "Note written")
    assert all(y != round(y) for y in notes.y)
