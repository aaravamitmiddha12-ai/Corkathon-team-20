"""Ranking tests. These use manual tags and template explanations: no API key, no cache."""

import pandas as pd
import pytest

from src.detect import is_near_limit, is_worsening, parse_limit, parse_value
from src.explain import MAX_HEADLINE_WORDS, allowed_citations, build_evidence
from src.load import load_all
from src.pipeline import run
from src.score import TOP_N
from src.tag_notes import MANUAL_TAGS


@pytest.fixture(scope="module")
def result():
    return run(mode="manual")


def top_ids(result):
    return [i.asset_id for i in result.top]


# ----- the four required tests -----

def test_frz12_ranks_first(result):
    assert top_ids(result)[0] == "FRZ-12"


def test_wfi_loop_is_clash_and_no_ticket(result):
    f = result.findings["WFI-LOOP-1"]
    assert f.clash and f.no_open_ticket


def test_ch2_pump_is_worsening_and_no_ticket(result):
    f = result.findings["CH-2-P3"]
    assert f.trend_worsening and f.no_open_ticket


def test_printer_not_in_top5(result):
    assert "PRN-QC-02" not in top_ids(result)


# ----- against the answer key -----

def test_top5_matches_expert_set(result):
    assert result.evaluation["matches"] == 5
    assert set(top_ids(result)) == {"FRZ-12", "WFI-LOOP-1", "HPLC-07", "CH-2-P3", "BAL-03"}


def test_rank_agreement_is_reported(result):
    ev = result.evaluation
    assert ev["out_of"] == 5
    assert ev["spearman"] is not None and ev["spearman"] > 0.5


# ----- nothing is dropped -----

def test_every_asset_is_ranked_somewhere(result):
    pack = result.pack
    everything = set(pack.assets.index) | set(pack.alerts["asset"]) | set(pack.tickets["asset"])
    ranked = [i.asset_id for i in result.top + result.rest]
    assert len(result.top) == TOP_N
    assert set(ranked) == everything
    assert len(ranked) == len(set(ranked))


# ----- loading -----

def test_note_times_cross_midnight():
    notes = load_all().notes.set_index("time")
    assert notes.loc["21:05", "timestamp"] == pd.Timestamp("2026-11-06 21:05")
    assert notes.loc["03:10", "timestamp"] == pd.Timestamp("2026-11-07 03:10")
    assert notes.loc["06:45", "timestamp"] == pd.Timestamp("2026-11-07 06:45")


def test_header_lines_are_not_notes():
    notes = load_all().notes
    assert len(notes) == 10
    assert not notes["line"].str.startswith("Shift:").any()


def test_manual_tags_cover_every_sample_line(result):
    assert set(result.notes["line"]) <= set(MANUAL_TAGS)
    assert set(result.notes["tag_source"]) == {"manual"}


# ----- detection rules -----

def test_frz12_flags(result):
    f = result.findings["FRZ-12"]
    assert f.repeats == 4
    assert f.trend_worsening          # -64.8 -> -63.1 -> -62.5 -> -61.9
    assert f.clash and f.clash_note_times == ["21:05", "23:15"]
    assert f.unacknowledged_latest
    assert f.no_open_ticket
    assert not f.near_limit           # already past the limit, not "near" it


def test_wfi_is_not_worsening(result):
    # 1.6 -> 1.5 -> 1.4: still over the limit, but each reading is better than the last
    assert not result.findings["WFI-LOOP-1"].trend_worsening


def test_ch2_is_near_limit(result):
    f = result.findings["CH-2-P3"]
    assert f.near_limit                # 8.1 vs alarm 9.0
    assert not f.clash                 # the note reported a problem, it didn't downplay it


def test_info_alert_after_reassuring_note_is_not_a_clash(result):
    # AHU-4: "within limits, just noting" at 19:20, info alert at 19:22
    assert not result.findings["AHU-4"].clash


def test_low_alert_after_reassuring_note_is_not_a_clash(result):
    # DOOR-LAB-B: "closed it" at 05:20, low alert at 05:21
    assert not result.findings["DOOR-LAB-B"].clash


def test_reassuring_note_alone_does_not_mean_no_ticket(result):
    assert not result.findings["DOOR-LAB-B"].no_open_ticket


def test_due_today(result):
    assert result.findings["HPLC-07"].due_today
    assert result.findings["BAL-03"].due_today
    assert not result.findings["AHU-4"].due_today  # due 20 Nov


def test_resolved_ticket_is_not_live(result):
    f = result.findings["FRZ-09"]
    assert f.active_tickets.empty and not f.due_today


def test_parsing_helpers():
    assert parse_value("Temperature -64.8C above alarm limit -70C") == -64.8
    assert parse_limit("Temperature -64.8C above alarm limit -70C") == -70
    assert parse_limit("Pump vibration 6.8 mm/s (warn 6.0, alarm 9.0)") == 9.0
    assert parse_limit("Toner empty") is None
    assert is_worsening([1, 2, 3], higher_worse=True)
    assert not is_worsening([1, 3, 2], higher_worse=True)
    assert not is_worsening([5], higher_worse=True)
    assert is_near_limit(8.1, 9.0, higher_worse=True)
    assert not is_near_limit(210, 250, higher_worse=True)   # 16% away
    assert not is_near_limit(1.4, 1.3, higher_worse=True)   # already past


# ----- scoring is transparent -----

def test_scores_are_sorted_and_explained(result):
    items = result.top + result.rest
    assert [i.score for i in items] == sorted((i.score for i in items), reverse=True)
    frz = result.top[0]
    assert frz.score == pytest.approx(3 * 3 * (1 + 0.5 * 3) * 1.5 + 40 + 50 + 15)


# ----- template explanations -----

def test_template_explanations(result):
    for item in result.top:
        ex = result.explanations[item.asset_id]
        assert ex["source"] == "template"
        assert len(ex["headline"].split()) <= MAX_HEADLINE_WORDS
        assert ex["why"].endswith(".") and ex["action"].endswith(".")
        assert set(ex["citations"]) <= set(allowed_citations(build_evidence(item)))
        assert ex["citations"]
