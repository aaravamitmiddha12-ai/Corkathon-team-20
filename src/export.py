"""Writes the pipeline's result to out/handover.json for the web pages in web/.

    python -m src.export                       # Sat 07:00 handover, demo mode (offline)
    python -m src.export --shift day           # Sat 19:00 handover
    python -m src.export --llm                 # live LLM, same as src.pipeline --llm
    python -m src.export --engineer "A. Walsh" # name shown as the incoming engineer

out/handover.js holds the same data as a script. Browsers refuse fetch() on file:// pages,
so the pages load that copy, and they work when opened by double-click with no server.

No decisions are made here: clashes, ranking and flags come straight from detect.py and
score.py. The only new calculation is projected_limit_time.
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src import respond, review
from src.detect import NUMBER, Finding, parse_value, past_limit
from src.due import due_label
from src.load import DEFAULT_SHIFT, NOW, ROOT, SHIFTS, fmt_time
from src.pipeline import Result, run
from src.score import REASON_LABELS, ScoredItem

OUT_DIR = ROOT / "out"
SHIFT_START = SHIFTS["night"].start
OTHER_ROW = "Other"
MIN_READINGS_TO_PROJECT = 3

# The sample pack doesn't say what earlier handovers looked like. That list is invented for the
# demo and marked as sample data in the JSON. The incoming engineer defaults to the shift's
# default name (the same one the Streamlit app uses) unless --engineer is given.
SAMPLE_RECENT_HANDOVERS = [
    {"time": "Fri 19:00", "direction": "Day → Night", "acknowledged": 4, "total": 4},
    {"time": "Fri 07:00", "direction": "Night → Day", "acknowledged": 5, "total": 5},
    {"time": "Thu 19:00", "direction": "Day → Night", "acknowledged": 3, "total": 4},
]

# The words quoted on the timeline, always taken verbatim from the note. First match wins;
# a note with no match shows its first three words.
KEY_PHRASES = ["seems ok", "prob sensor?", "only a few secs", "will log it tmrw", "within limits", "closed it",
               "quiet enough", "out of toner", "vendor engineer booked", "due today", "will log", "will mention",
               "seems fine", "all good", "only a blip", "no issue", "sorted"]

READING_UNIT = re.compile(r"\s*(°?C\b|[uµ]S/cm|mm/s|Pa\b|bar\b|%)")
UNIT_NAMES = {"C": "°C", "uS/cm": "µS/cm"}


def reading_unit(message: str) -> str:
    """The unit straight after the message's first number: "-64.8C above..." gives "°C"."""
    number = NUMBER.search(message)
    match = READING_UNIT.match(message, number.end()) if number else None
    return UNIT_NAMES.get(match[1], match[1]) if match else ""


def with_unit(value: float, unit: str) -> str:
    return f"{value:g}{' ' if unit else ''}{unit}"


def key_phrase(text: str) -> str:
    lower = text.lower()
    for phrase in KEY_PHRASES:
        if phrase in lower:
            return phrase
    return " ".join(lower.split()[:3])


def readings(f: Finding) -> list[tuple[pd.Timestamp, float]]:
    """[(timestamp, value)] for the asset's alerts that carry a number and a time."""
    values = [(ts, parse_value(m)) for ts, m in zip(f.alerts["timestamp"], f.alerts["message"])]
    return [(ts, v) for ts, v in values if v is not None and not pd.isna(ts)]


def project_limit_time(points: list[tuple[pd.Timestamp, float]], limit: float | None, higher_worse: bool,
                       now: pd.Timestamp = NOW) -> pd.Timestamp | None:
    """When a straight line through the readings reaches the limit, or None if that isn't a useful answer.

    None when: fewer than 3 readings, no limit, already past the limit, heading away from it,
    or the line crosses before `now`.
    """
    if len(points) < MIN_READINGS_TO_PROJECT:
        return None
    return line_crossing(points, limit, higher_worse, now)


def recent_pace_limit_time(points: list[tuple[pd.Timestamp, float]], limit: float | None, higher_worse: bool,
                           now: pd.Timestamp = NOW) -> pd.Timestamp | None:
    """The same idea using only the last two readings, which shows a climb that is speeding up."""
    if len(points) < MIN_READINGS_TO_PROJECT:
        return None
    return line_crossing(points[-2:], limit, higher_worse, now)


def line_crossing(points: list[tuple[pd.Timestamp, float]], limit: float | None, higher_worse: bool,
                  now: pd.Timestamp) -> pd.Timestamp | None:
    if limit is None or past_limit(points[-1][1], limit, higher_worse):
        return None
    hours = np.array([(ts - points[0][0]).total_seconds() / 3600 for ts, _ in points])
    if np.ptp(hours) == 0:
        return None
    slope, intercept = np.polyfit(hours, [v for _, v in points], 1)
    if (slope <= 0) if higher_worse else (slope >= 0):
        return None
    crossing = points[0][0] + pd.Timedelta(hours=float((limit - intercept) / slope))
    return crossing.round("s") if crossing > now else None


def clock_label(moment: pd.Timestamp, now: pd.Timestamp = NOW) -> str:
    """Rounded to 5 minutes, because a straight-line guess isn't minute-accurate."""
    rounded = moment.round("5min")
    day = "" if rounded.date() == now.date() else f"{rounded:%a} "
    return f"{day}{rounded:%H:%M}"


def projected_label(crossing: pd.Timestamp, recent: pd.Timestamp | None = None, now: pd.Timestamp = NOW) -> str:
    """ "Trips ~09:40", or a range when the recent pace gives a different answer: "Trips ~07:50–09:40"."""
    times = sorted({clock_label(t, now): t for t in (crossing, recent) if t is not None}.items(),
                   key=lambda kv: kv[1])
    return "Trips ~" + "–".join(label for label, _ in times)


def reading_decimals(points: list[tuple[pd.Timestamp, float]]) -> int:
    """How many decimals the readings use, so a limit shows as "9.0" next to "8.1"."""
    return max(len(f"{v:g}".partition(".")[2]) for _, v in points)


def evidence_line(f: Finding) -> str:
    """One plain sentence for a list row. Built only from the detector's facts."""
    parts = []
    if f.repeats:
        text = f"{f.repeats} {f.max_severity} alert{'s' if f.repeats != 1 else ''}"
        points = readings(f)
        if points:
            unit = reading_unit(f.alerts.iloc[-1]["message"])
            span = with_unit(points[-1][1], unit) if len(points) == 1 else f"{points[0][1]:g} to {with_unit(points[-1][1], unit)}"
            text += f", {span}"
            if f.limit is not None:
                limit = f"{f.limit:.{reading_decimals(points)}f}"
                text += f", limit {limit}{' ' if unit else ''}{unit}"
        parts.append(text)
    for ticket_id in f.due_ticket_ids:
        due = f.tickets[f.tickets["id"] == ticket_id].iloc[0]["due"]
        parts.append(f"{ticket_id} due {fmt_time(due, '%H:%M')} today")
    if f.unacknowledged_latest:
        parts.append("latest not acknowledged")
    return " · ".join(parts) or "Mentioned in the notes"


def export_item(rank: int, item: ScoredItem, explanation: dict, response: dict | None = None) -> dict:
    f = item.finding
    now = f.now
    due_text, overdue = due_label(f.due_by, now)
    out = {
        "rank": rank,
        "asset_id": item.asset_id,
        "title": explanation["headline"],
        "why": " ".join(explanation["bullets"]),   # one string, for pages that show a single line
        "bullets": explanation["bullets"],
        "action": explanation["action"],
        "evidence": evidence_line(f),
        "clash": bool(f.clash),
        "tags": [{"key": r, "label": f"{f.repeats} alerts" if r == "repeated" else REASON_LABELS[r]}
                 for r in item.reasons],
        "due_by": f.due_by.isoformat() if f.due_by is not None else None,
        "due_label": due_text,
        "overdue": overdue,
        "dismissed_earlier_now_worse": item.dismissal_status == "now_worse",
    }
    if item.review:
        out["outgoing_review"] = {"choice": review.CHOICES.get(item.review.get("choice"), ""),
                                  "comment": item.review.get("comment", ""), "name": item.review.get("name", "")}
    if response:
        out["response"] = {"kind": respond.RESPONSE_LABELS.get(response.get("kind"), ""),
                           "name": response.get("name", ""), "at": response.get("at", ""),
                           "reason": response.get("reason", "")}
    if f.trend_worsening:
        crossing = project_limit_time(readings(f), f.limit, f.higher_worse, now)
        if crossing is not None:
            recent = recent_pace_limit_time(readings(f), f.limit, f.higher_worse, now)
            out["projected_limit_time"] = crossing.isoformat()
            if recent is not None:
                out["projected_limit_time_recent_pace"] = recent.isoformat()
            out["projected_limit_label"] = projected_label(crossing, recent, now)
    return out


def minutes_into_shift(ts, start: pd.Timestamp = SHIFT_START) -> float | None:
    return None if pd.isna(ts) else round((ts - start).total_seconds() / 60, 2)


def export_events(result: Result) -> list[dict]:
    """Every alert and note line, in time order. Amber comes from the detector's clash lists."""
    top_ids = {i.asset_id for i in result.top}
    row_of = lambda asset: asset if asset in top_ids else OTHER_ROW
    events = []
    for _, a in result.pack.alerts.iterrows():
        f = result.findings.get(a["asset"])
        events.append({
            "kind": "alert", "time": a["time"], "minutes": minutes_into_shift(a["timestamp"], result.shift.start),
            "asset_id": a["asset"], "row": row_of(a["asset"]), "system": a["system"], "severity": a["severity"],
            "text": a["message"], "value": parse_value(a["message"]),
            "clash": bool(f and a["time"] in f.clash_alert_times),
        })
    for _, n in result.notes.iterrows():
        asset = n["asset_id"] if isinstance(n["asset_id"], str) else None
        f = result.findings.get(asset)
        events.append({
            "kind": "note", "time": n["time"], "minutes": minutes_into_shift(n["timestamp"], result.shift.start),
            "asset_id": asset, "row": row_of(asset), "system": "Shift notes", "text": n["text"],
            "key_words": key_phrase(n["text"]), "reassuring": bool(n["reassuring"]),
            "clash": bool(f and n["time"] in f.clash_note_times),
        })
    # Events with no time go last, so a blank cell can't drop anything.
    events.sort(key=lambda e: (e["minutes"] is None, e["minutes"] or 0, e["kind"] == "note"))
    return events


def export_trend(f: Finding, start: pd.Timestamp = SHIFT_START) -> dict | None:
    """The dashed line on the timeline. Only for assets the detector says are getting worse."""
    points = readings(f)
    if not f.trend_worsening or len(points) < 2:
        return None
    unit = reading_unit(f.alerts.iloc[-1]["message"])
    decimals = reading_decimals(points)
    labels = [f"{v:g}" for _, v in points]
    labels[0] = with_unit(points[0][1], unit)
    if f.limit is not None:
        labels[-1] = f"{points[-1][1]:.{decimals}f} / {f.limit:.{decimals}f}"
    return {
        "higher_is_worse": bool(f.higher_worse),
        "unit": unit,
        "limit": f.limit,
        "points": [{"minutes": minutes_into_shift(ts, start), "value": v, "label": label}
                   for (ts, v), label in zip(points, labels)],
    }


def describe_asset(f: Finding) -> str:
    """The muted line under a timeline row label, e.g. "-80 °C freezer · GMP"."""
    text = re.sub(r"(-?\d+)C\b", r"\1 °C", f.asset_type) or "Not in the asset list"
    return f"{text} · GMP" if "GMP" in str(f.details.get("contents", "")) else text


def export_rows(result: Result) -> list[dict]:
    rows = [{"id": i.asset_id, "description": describe_asset(i.finding),
             "trend": export_trend(i.finding, result.shift.start)}
            for i in result.top]
    return rows + [{"id": OTHER_ROW, "description": "Everything else", "trend": None}]


def summary_lines(top: list[ScoredItem]) -> dict:
    n = len(top)
    clashes = sum(bool(i.finding.clash) for i in top)
    lead = "Nothing needs you." if n == 0 else "1 thing needs you." if n == 1 else f"{n} things need you."
    if clashes == 0:
        clash = ""
    elif n == 1:
        clash = "The notes got it wrong."
    else:
        clash = f"{clashes} of them the notes got wrong."
    return {"lead": lead, "clash": clash}


def shift_words(shift) -> dict:
    """Words that change between the night shift (Sat 07:00 handover) and the day shift (Sat 19:00)."""
    night = shift.start.hour >= 12  # the outgoing shift started in the evening
    return {
        "outgoing": "night" if night else "day",
        "direction": "NIGHT → DAY" if night else "DAY → NIGHT",
        "incoming_shift": "Day shift" if night else "Night shift",
        "greeting": "Good morning." if night else "Good evening.",
    }


def timeline_summary(events: list[dict], shift=SHIFTS["night"]) -> str:
    alerts = [e for e in events if e["kind"] == "alert"]
    notes = [e for e in events if e["kind"] == "note"]
    amber = [e for e in alerts if e["clash"]]
    text = (f"The {shift_words(shift)['outgoing']} from {shift.start:%H:%M} to {shift.handover:%H:%M}: "
            f"{len(alerts)} alerts and {len(notes)} note lines.")
    if amber:
        assets = sorted({e["asset_id"] for e in amber})
        text += f" {len(amber)} alerts came after a note saying things were fine, on {' and '.join(assets)}."
    return text


def read_log_header(path: Path) -> tuple[str, str]:
    """(site, outgoing engineer) from the header lines of the shift log. Blank if not found."""
    lines = path.read_text(encoding="utf-8").splitlines()
    site = lines[0].rsplit(" - ", 1)[-1].strip() if lines and " - " in lines[0] else ""
    match = next((m for m in (re.search(r"Engineer:\s*(.+)$", line) for line in lines) if m), None)
    return site, match[1].strip() if match else ""


def build(result: Result, incoming_engineer: str | None = None) -> dict:
    events = export_events(result)
    shift, pack = result.shift, result.pack
    words = shift_words(shift)
    site, outgoing = read_log_header(shift.data_dir / shift.notes_file)
    now = shift.handover
    return {
        "site": site,
        "handover": {
            "shift_id": shift.id,
            "time": now.isoformat(),
            "eyebrow": f"{words['direction']} · {now:%a} {now.day} {now:%b} · {now:%H:%M}".upper(),
            "incoming_shift": words["incoming_shift"],
            "incoming_engineer": incoming_engineer or shift.incoming_engineer,
            "outgoing_engineer": outgoing,
            "outgoing_review_completed": result.review_complete,
            "responded": result.responded_count,
        },
        "heading": f"{words['greeting']} Your handover is ready.",
        "summary": summary_lines(result.top),
        "counts": {
            "top": len(result.top),
            "clash": sum(bool(f.clash) for f in result.findings.values()),
            "not_urgent": len(result.rest),
            "carried_over": len(result.carried),
            "alerts": len(pack.alerts),
            "tickets": len(pack.tickets),
            "note_lines": len(result.notes),
        },
        "items": [export_item(n, item, result.explanations[item.asset_id], result.responses.get(item.asset_id))
                  for n, item in enumerate(result.top, start=1)],
        "carried_over": [
            {"asset_id": i.asset_id, "title": result.explanations[i.asset_id]["headline"],
             "previously_dismissed": respond.dismissal_line(i.dismissal)}
            for i in result.carried
        ],
        "timeline": {
            "start": f"{shift.start:%H:%M}",
            "end": f"{shift.handover:%H:%M}",
            "minutes": round((shift.handover - shift.start).total_seconds() / 60),
            "summary": timeline_summary(events, shift),
            "rows": export_rows(result),
        },
        "events": events,
        "recent_handovers": {"sample": True, "rows": SAMPLE_RECENT_HANDOVERS},
    }


def write(data: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
    (out_dir / "handover.js").write_text(f"window.HANDOVER_DATA = {text};\n", encoding="utf-8", newline="\n")
    path = out_dir / "handover.json"
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--llm", action="store_true", help="allow live LLM calls")
    parser.add_argument("--shift", default=DEFAULT_SHIFT, choices=list(SHIFTS), help="which handover to export")
    parser.add_argument("--engineer", default=None, help="incoming engineer's name (default: the shift's)")
    args = parser.parse_args()
    run_result = run(mode="llm" if args.llm else "demo", shift=args.shift)
    for warning in run_result.warnings:
        print("WARNING:", warning)
    print("Wrote", write(build(run_result, args.engineer)))
