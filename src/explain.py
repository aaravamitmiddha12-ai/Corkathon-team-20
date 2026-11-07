"""Write a headline, 2-3 short "why" bullets and one action for each item.

The LLM sees ONLY that item's evidence and must not invent values. We check its
answer: unknown citations are dropped, and if it uses a number that isn't in the
evidence (or claims more alerts than there were) we use the template instead.

Modes match tag_notes: "manual" (template only), "demo" (cache, else template),
"llm" (cache, else ask the LLM and cache it, else template).
"""

import hashlib
import json
import re

import pandas as pd

from src import llm
from src.due import when
from src.load import fmt_time
from src.score import REASON_LABELS, ScoredItem

CACHE_FILE = "explanations.json"
MAX_HEADLINE_WORDS = 10
MAX_BULLETS = 3

# Numbers not glued to a name ("FRZ-12", "P2"). Dates are removed first, so "2026-11-07" can't vouch for 11 or 7.
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
               "nine": 9, "ten": 10}
ALERT_COUNT = re.compile(r"\b(\d+|" + "|".join(COUNT_WORDS) + r")\s+(?:\w+\s+)?(?:alerts?|alarms?|excursions?)\b",
                         re.IGNORECASE)


# ---------- small formatting helpers ----------

def value_with_unit(value: float, unit: str) -> str:
    return f"{value:g} {unit}".strip()


def join_times(times: list[str]) -> str:
    return times[0] if len(times) == 1 else ", ".join(times[:-1]) + " and " + times[-1]


def rule_text(rule: dict) -> str:
    """Plain-language version of a structured asset rule."""
    kind = rule.get("type")
    if kind == "deviation_window_hours":
        return f"every excursion must be logged as a deviation within {rule.get('value', 24)} h"
    if kind == "unusable_after_calibration_due":
        return "it can't be used after its calibration is due"
    return str(kind or "").replace("_", " ")


def latest_past_limit(f) -> bool:
    return f.latest_value is not None and f.limit is not None and f.is_worse(f.latest_value, f.limit)


def short_type(f) -> str:
    """The asset type, but only if it's short enough for a headline ("Chiller pump", not "Water for ...")."""
    if not f.asset_type or len(f.asset_type.split()) > 2 or f.asset_type.lower() in f.asset_id.lower():
        return ""  # too long, or it just repeats the id ("HPLC-07 HPLC")
    return f.asset_type


def _alarm_word(f) -> str:
    return "alarms" if f.max_severity == "high" else "alerts"


# ---------- evidence: the only facts an explanation may use ----------

def reason_details(item: ScoredItem) -> list[str]:
    f = item.finding
    out = []
    for r in item.reasons:
        label = REASON_LABELS[r]
        if r == "clash":
            out.append(f"{label}: note(s) at {', '.join(f.clash_note_times)} said it was fine; "
                       f"medium+ alerts followed at {', '.join(f.clash_alert_times)}")
        elif r == "no_open_ticket":
            out.append(f"{label}: no open, scheduled or approved ticket for {f.asset_id}")
        elif r == "trend_worsening":
            out.append(f"{label}: readings {' -> '.join(f'{v:g}' for _, v in f.values)}")
        elif r == "near_limit":
            out.append(f"{label}: latest {f.values[-1][1]:g} vs alarm limit {f.limit:g}")
        elif r == "due_soon":
            out.append(f"{label}: due by {fmt_time(f.due_by, '%Y-%m-%d %H:%M')} ({f.due_by_source})")
        elif r == "unacknowledged_latest":
            out.append(f"{label}: latest alert at {f.alerts.iloc[-1]['time']} has no acknowledgement")
        elif r == "outgoing_real_issue":
            out.append(f"{label}: the outgoing engineer marked this as a real issue")
        elif r == "repeated":
            out.append(f"{label}: {f.repeats} alerts this shift")
    return out


def build_evidence(item: ScoredItem) -> dict:
    f = item.finding
    details = {k: v for k, v in f.details.items() if k != "rules"}
    evidence = {
        "handover_time": fmt_time(f.now, "%Y-%m-%d %H:%M"),
        "asset_id": f.asset_id,
        "asset": details or {"note": "not in the asset list"},
        "site_rules": [rule_text(r) for r in f.rules],
        "alert_count": f.repeats,
        "alerts": [
            {"cite": f"alert {a['time']}", "timestamp": fmt_time(a["timestamp"], "%Y-%m-%d %H:%M"),
             "severity": a["severity"], "message": a["message"],
             "acknowledged_by": a["acknowledged_by"] or None}
            for _, a in f.alerts.iterrows()
        ],
        "notes": [
            {"cite": f"note {n['time']}", "text": n["text"], "reassuring": bool(n["reassuring"]),
             "mentions_future_action": bool(n["mentions_future_action"])}
            for _, n in f.notes.iterrows()
        ],
        "tickets": [
            {"cite": t["id"], "priority": t["priority"], "status": t["status"],
             "due": fmt_time(t["due"], "%Y-%m-%d %H:%M"), "assignee": t["assignee"], "summary": t["summary"]}
            for _, t in f.tickets.iterrows()
        ],
        "due_by": fmt_time(f.due_by, "%Y-%m-%d %H:%M") if f.due_by is not None else None,
        "fired_reasons": reason_details(item),
    }
    if item.review:
        evidence["outgoing_engineer_review"] = {"choice": item.review.get("choice"),
                                                "comment": item.review.get("comment", "")}
    return evidence


def allowed_citations(evidence: dict) -> list[str]:
    return [x["cite"] for key in ("alerts", "notes", "tickets") for x in evidence[key]]


def evidence_rows(item: ScoredItem, cited: list[str] | None = None) -> list[tuple[str, str, str]]:
    """The evidence as a small table: (Time, Source, What). Only cited rows if `cited` is given."""
    f = item.finding
    keep = set(cited) if cited else None
    timed = []
    for _, a in f.alerts.iterrows():
        if keep is None or f"alert {a['time']}" in keep:
            ack = f"ack {a['acknowledged_by']}" if a["acknowledged_by"] else "not acknowledged"
            timed.append((a["timestamp"], a["time"], f"Alert · {a['system']}",
                          f"{a['severity'].capitalize()}: {a['message']} ({ack})"))
    for _, n in f.notes.iterrows():
        if keep is None or f"note {n['time']}" in keep:
            timed.append((n["timestamp"], n["time"], "Shift note", n["text"]))
    timed.sort(key=lambda r: (pd.isna(r[0]), r[0] if not pd.isna(r[0]) else pd.Timestamp.min))
    rows = [(t, s, w) for _, t, s, w in timed]
    for _, t in f.tickets.iterrows():
        if keep is None or t["id"] in keep:
            due = when(t["due"], f.now)
            rows.append(("—", f"Ticket {t['id']}", f"{t['priority']} {t['status']}, due {due} · "
                                                   f"{t['assignee']} · {t['summary']}"))
    return rows


# ---------- template explanation (no API key needed) ----------

def template_headline(item: ScoredItem) -> str:
    f = item.finding
    r = set(item.reasons)
    meas = f.measurement or "reading"
    past_now = latest_past_limit(f)
    kind = short_type(f)
    toward = "rising toward" if f.higher_worse else "falling toward"
    calibration = any(x.get("type") == "unusable_after_calibration_due" for x in f.rules)

    if "clash" in r:
        text = f"{f.asset_id}: {f.repeats} {meas} {_alarm_word(f)}, notes said OK"
    elif "trend_worsening" in r and past_now:
        text = f"{f.asset_id} {meas} past alarm limit and getting worse"
    elif "trend_worsening" in r and "near_limit" in r:
        text = f"{f.asset_id} {meas} {toward} {value_with_unit(f.limit, f.unit)} alarm"
    elif "trend_worsening" in r:
        text = f"{f.asset_id} {meas} getting worse"
    elif "no_open_ticket" in r:
        text = f"{f.asset_id} {kind}: problem noted, no ticket".replace(" :", ":")
    elif "due_soon" in r and calibration:
        text = f"{f.asset_id} calibration due {when(f.due_by, f.now)}"
    elif "due_soon" in r:
        what = f.due_by_source.split(" ")[0] if f.active_tickets.shape[0] else "deviation"
        text = f"{f.asset_id} {kind}: {what} due {when(f.due_by, f.now)}".replace(" :", ":")
    elif "near_limit" in r:
        text = f"{f.asset_id} {meas} close to {value_with_unit(f.limit, f.unit)} alarm"
    elif "unacknowledged_latest" in r:
        text = f"{f.asset_id}: latest alert not acknowledged"
    else:
        text = f"{f.asset_id}: worth a check"
    return _limit_words(text)


def template_bullets(item: ScoredItem) -> list[str]:
    f = item.finding
    r = set(item.reasons)
    side = "above" if f.higher_worse else "below"
    out = []

    if "clash" in r:
        n = len(f.clash_alert_times)
        noun = "Note" if len(f.clash_note_times) == 1 else "Notes"
        word = ("alarm" if f.max_severity == "high" else "alert") + ("s" if n > 1 else "")
        out.append(f"{noun} at {join_times(f.clash_note_times)} said it was fine, but {n} more {word} came after.")

    if f.values:
        values = [v for _, v in f.values]
        limit = value_with_unit(f.limit, f.unit) if f.limit is not None else None
        all_past = limit is not None and all(f.is_worse(v, f.limit) for v in values)
        if f.readings_are_events and limit:
            listed = ", ".join(f"{v:g}" for v in values)
            out.append(f"{len(values)} separate excursions {side} the {limit} limit: {listed} {f.unit}.".replace("  ", " "))
        elif len(values) >= 2:
            span = f"{len(values)} readings from {value_with_unit(values[0], f.unit)} to {value_with_unit(values[-1], f.unit)}"
            if all_past:
                out.append(f"{span}, all {side} the {limit} alarm limit.")
            elif limit and latest_past_limit(f):
                out.append(f"{span}; the latest is {side} the {limit} alarm limit.")
            elif limit:
                out.append(f"{span}; the alarm is at {limit}.")
            else:
                out.append(f"{span}.")
        elif limit:
            out.append(f"Reading {value_with_unit(values[-1], f.unit)}; the alarm is at {limit}.")

    for rule in f.rules:
        if rule.get("type") == "deviation_window_hours" and ("past_alarm_limit" in f.breaches or f.due_by):
            out.append(f"Site rule: {rule_text(rule)}.")
        elif rule.get("type") == "unusable_after_calibration_due" and f.due_by is not None:
            out.append(f"Site rule: {rule_text(rule)}.")

    if "no_open_ticket" in r and not f.repeats and len(f.notes):
        concern = f.notes[~f.notes["reassuring"]]
        if len(concern):
            n = concern.iloc[-1]
            text = n["text"] if len(n["text"]) <= 90 else n["text"][:87] + "..."
            out.append(f'The {n["time"]} note reports a problem: "{text}"')

    if "no_open_ticket" in r:
        later = f.notes["mentions_future_action"].any() if len(f.notes) else False
        out.append("No open ticket, although the note said it would be dealt with later."
                   if later else "No open ticket.")

    for _, t in f.active_tickets.iterrows():
        if f.due_by is not None and t["id"] in f.due_by_source:
            out.append(f"{t['id']} ({t['priority']}, {t['assignee']}) is due {when(t['due'], f.now)}.")

    if f.details.get("note"):
        note = str(f.details["note"])
        out.append(note[0].upper() + note[1:] + ".")

    if "unacknowledged_latest" in r:
        out.append(f"Latest alert at {f.alerts.iloc[-1]['time']} is not acknowledged.")

    if not out:
        out.append("Nothing urgent fired for this item.")
    return out[:MAX_BULLETS]


def template_action(item: ScoredItem) -> str:
    f = item.finding
    r = set(item.reasons)
    deviation = any(x.get("type") == "deviation_window_hours" for x in f.rules)
    calibration = any(x.get("type") == "unusable_after_calibration_due" for x in f.rules)

    if "no_open_ticket" in r:
        extra = " and log a deviation, as the site rule requires" if deviation else ""
        if "clash" in r:
            return f"Check {f.asset_id} on site now, then raise a ticket{extra}."
        if latest_past_limit(f):
            return f"Raise a ticket for {f.asset_id} and get it checked now: it is past its alarm limit."
        if "trend_worsening" in r or "near_limit" in r:
            return f"Raise a ticket for {f.asset_id} and get it inspected before it reaches the alarm limit."
        return f"Raise a ticket for {f.asset_id}{extra}."
    if "clash" in r:
        return f"Check {f.asset_id} on site and confirm the open ticket covers what the data shows."
    if "due_soon" in r and len(f.active_tickets):
        t = f.active_tickets.sort_values("due").iloc[0]
        action = f"Confirm with {t['assignee']} that {t['id']} will be done before {when(t['due'], f.now)}"
        if calibration:
            action += f", or tag {f.asset_id} out of use"
        return action + "."
    if "due_soon" in r:
        return f"Make sure {f.asset_id} is dealt with before {when(f.due_by, f.now)}."
    if "near_limit" in r:
        return f"Keep an eye on {f.asset_id} and check it before it reaches the alarm limit."
    if "unacknowledged_latest" in r:
        return f"Acknowledge the latest {f.asset_id} alert and check the asset."
    return f"Review {f.asset_id} when convenient."


def template_explanation(item: ScoredItem) -> dict:
    return {
        "headline": template_headline(item),
        "bullets": template_bullets(item),
        "action": template_action(item),
        "citations": allowed_citations(build_evidence(item)),
        "source": "template",
    }


# ---------- LLM version ----------

SYSTEM_PROMPT = f"""You help an incoming shift engineer at a pharma site. You get the evidence for ONE item
that our rules have already ranked as needing attention. Write:
- headline: at most {MAX_HEADLINE_WORDS} words saying specifically what is wrong
- bullets: 2 or 3 short plain-language points explaining why, with units on every value. No paragraphs.
- action: ONE imperative sentence: the single most useful next step
- citations: the "cite" values of the alerts, notes and tickets you relied on

Rules:
- Use ONLY the evidence given. Never invent values, times, names or ticket ids.
- Every number you write must appear in the evidence. Write times exactly as given (24-hour HH:MM).
  Don't calculate differences, durations or totals.
- If the notes downplay something the data shows, say so plainly.
- Plain, calm language. No markdown."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "action": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "bullets", "action", "citations"],
    "additionalProperties": False,
}


def _limit_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_HEADLINE_WORDS])


def _numbers(text: str) -> set[float]:
    text = DATE.sub(" ", text.replace("−", "-"))  # treat a typographic minus like "-"
    return {float(n) for n in NUMBER.findall(text)}


def _answer_text(answer: dict) -> str:
    return " ".join([answer["headline"], *answer["bullets"], answer["action"]])


def invented_numbers(answer: dict, evidence: dict) -> set[float]:
    """Numbers in the answer that appear nowhere in the evidence. Signs count: 61.9 is not -61.9."""
    known = _numbers(json.dumps(evidence, ensure_ascii=False))
    return _numbers(_answer_text(answer)) - known


def overcounted_alerts(answer: dict, evidence: dict) -> list[str]:
    """Claims like "6 alarms" when the asset only had 4."""
    bad = []
    for match in ALERT_COUNT.finditer(_answer_text(answer)):
        word = match[1].lower()
        n = COUNT_WORDS.get(word) or int(word)
        if n > evidence["alert_count"]:
            bad.append(match[0])
    return bad


class BadAnswer(llm.AnswerUnusable):
    """The API worked, but this answer broke our rules."""


def check_llm_answer(answer: dict, evidence: dict) -> dict:
    """Clean the answer, or raise BadAnswer if it can't be trusted."""
    if not isinstance(answer, dict):
        raise BadAnswer("not a JSON object")
    for key in ("headline", "action"):
        if not isinstance(answer.get(key), str) or not answer[key].strip():
            raise BadAnswer(f"missing {key}")
    bullets = answer.get("bullets")
    if not isinstance(bullets, list) or not all(isinstance(b, str) for b in bullets):
        raise BadAnswer("bullets must be a list of strings")
    bullets = [b.strip() for b in bullets if b.strip()][:MAX_BULLETS]
    if not bullets:
        raise BadAnswer("no bullets")
    answer = {**answer, "bullets": bullets}
    bad = invented_numbers(answer, evidence)
    if bad:
        raise BadAnswer(f"used values not in the evidence: {sorted(bad)}")
    too_many = overcounted_alerts(answer, evidence)
    if too_many:
        raise BadAnswer(f"claimed more alerts than the data has: {too_many}")
    allowed = allowed_citations(evidence)
    citations = answer.get("citations")
    cited = [c for c in citations if c in allowed] if isinstance(citations, list) else []
    return {
        "headline": _limit_words(answer["headline"].strip()),
        "bullets": bullets,
        "action": answer["action"].strip(),
        "citations": cited or allowed,
    }


def cache_key(evidence: dict) -> str:
    """Asset + a hash of its evidence + model, so a changed input never reuses an old answer."""
    blob = json.dumps(evidence, sort_keys=True) + llm.model_name()
    return f"{evidence['asset_id']}:{hashlib.sha1(blob.encode()).hexdigest()[:12]}"


def explain_all(top: list[ScoredItem], mode: str = "manual") -> tuple[dict, list[str]]:
    """Return ({asset_id: explanation}, warnings)."""
    cache = llm.read_cache(CACHE_FILE) if mode in ("demo", "llm") else {}
    changed = False
    warnings: list[str] = []
    llm_ok = mode == "llm"  # set to False after a failure that would repeat (network, key, rate limit)
    out = {}

    for item in top:
        evidence = build_evidence(item)
        key = cache_key(evidence)
        result = None

        if key in cache:
            try:
                result = {**check_llm_answer(cache[key], evidence), "source": "llm (cached)"}
            except llm.LLMUnavailable:
                result = None

        if result is None and llm_ok:
            try:
                raw = llm.ask_json(SYSTEM_PROMPT, json.dumps(evidence, indent=2), SCHEMA, effort="medium")
                result = {**check_llm_answer(raw, evidence), "source": "llm"}
                cache[key] = {k: result[k] for k in ("headline", "bullets", "action", "citations")}
                changed = True
            except llm.LLMUnavailable as e:
                warnings.append(f"{item.asset_id}: LLM explanation not used ({e}); showing the template.")
                if not isinstance(e, llm.AnswerUnusable):
                    llm_ok = False  # the API itself failed: don't retry for every item

        out[item.asset_id] = result or template_explanation(item)

    if changed:
        llm.write_cache(CACHE_FILE, cache)
    return out, warnings
