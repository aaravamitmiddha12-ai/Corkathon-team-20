"""The per-render style rules that keep the timeline labels in step with the cards. The timeline sits outside
the fragment, so these rules are the only way a response can change its label."""

import re
from types import SimpleNamespace

import pytest

import ui.home as home

ASSETS = ["FRZ-12", "WFI-LOOP-1", "CH-2-P3"]


@pytest.fixture
def session(monkeypatch):
    """A plain dict stands in for st.session_state, so the rules can be built without a running app."""
    state = {}
    monkeypatch.setattr(home, "st", SimpleNamespace(session_state=state))
    return state


def result(responses):
    top = [SimpleNamespace(asset_id=a) for a in ASSETS]
    return SimpleNamespace(shift=SimpleNamespace(id="night"), top=top, responses=responses)


def rule_for(css, asset):
    match = re.search(r'a\.baton-tl-label\[href="#card-' + re.escape(asset) + r'"\] \{([^}]*)\}', css)
    return match.group(1) if match else None


def test_no_response_means_no_label_rules(session):
    css = home.motion_css(result({}), None, intro=False, ready=False)
    assert "baton-tl-label" not in css


def test_a_handled_item_gets_a_tick_and_is_muted_while_collapsed(session):
    css = home.motion_css(result({"FRZ-12": {"kind": "got_it"}}), None, intro=False, ready=False)
    rule = rule_for(css, "FRZ-12")
    assert '--baton-tick: "✓"' in rule
    assert "--baton-row-fade: 0.7" in rule
    assert rule_for(css, "WFI-LOOP-1") is None and rule_for(css, "CH-2-P3") is None


def test_a_reopened_item_keeps_its_tick_but_is_not_muted(session):
    session["reopened"] = {("night", "FRZ-12")}
    rule = rule_for(home.motion_css(result({"FRZ-12": {"kind": "got_it"}}), None, False, False), "FRZ-12")
    assert '--baton-tick: "✓"' in rule
    assert "--baton-row-fade" not in rule


@pytest.mark.parametrize("form", ["draft", "dismiss"])
def test_an_item_with_its_form_open_is_not_muted(session, form):
    session["open_form"] = ("night", "CH-2-P3", form)
    rule = rule_for(home.motion_css(result({"CH-2-P3": {"kind": "ticket_drafted"}}), None, False, False), "CH-2-P3")
    assert '--baton-tick: "✓"' in rule and "--baton-row-fade" not in rule


def test_a_form_open_on_another_shift_does_not_count(session):
    session["open_form"] = ("day", "CH-2-P3", "draft")
    rule = rule_for(home.motion_css(result({"CH-2-P3": {"kind": "ticket_drafted"}}), None, False, False), "CH-2-P3")
    assert "--baton-row-fade: 0.7" in rule


def test_rules_follow_each_render_not_the_last_one(session):
    """Built from the responses each time: a later render with fewer responses drops the old rule."""
    assert rule_for(home.motion_css(result({"FRZ-12": {"kind": "got_it"}}), None, False, False), "FRZ-12")
    assert rule_for(home.motion_css(result({}), None, False, False), "FRZ-12") is None


def test_label_rules_target_the_same_href_the_labels_use(session, monkeypatch):
    """An id with characters that can't go in an anchor is slugged the same way on both sides."""
    r = result({"A B/1": {"kind": "got_it"}})
    r.top = [SimpleNamespace(asset_id="A B/1", finding=SimpleNamespace(asset_type="pump"))]
    r.pack = SimpleNamespace(alerts={"asset": []})
    r.notes = {"asset_id": []}
    hrefs = re.findall(r'href="([^"]+)"', home.timeline_labels(r))
    css = home.motion_css(r, None, False, False)
    assert hrefs == ["#card-A-B-1"] and 'href="#card-A-B-1"' in css


def test_asset_id_column_is_marked_so_it_stays_whole():
    html = home.html_table(["#", "Asset", "Action"], [(1, "WFI-LOOP-1", "Check it")], plain_first=True, id_col=1)
    assert '<td class="baton-id">WFI-LOOP-1</td>' in html
    assert html.count("baton-id") == 1
