"""Step 5: write a headline, a "why" sentence and one action for each top-5 item.

The LLM sees ONLY that item's evidence and must not invent values. We check its
answer: unknown citations are dropped, and if it uses a number that isn't in the
evidence we throw the answer away and use the template instead.

Modes match tag_notes: "manual" (template only), "demo" (cache, else template),
"llm" (cache, else ask the LLM and cache it, else template).
"""

import hashlib
import json
import re

from src import llm
from src.detect import past_limit
from src.load import NOW, fmt_time
from src.score import REASON_LABELS, ScoredItem

CACHE_FILE = "explanations.json"
MAX_HEADLINE_WORDS = 10
# Numbers not glued to a name ("FRZ-12", "P2"). Dates are removed first, so "2026-11-07" can't vouch for 11 or 7.
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
               "nine": 9, "ten": 10}
ALERT_COUNT = re.compile(r"\b(\d+|" + "|".join(COUNT_WORDS) + r")\s+(?:\w+\s+)?(?:alerts?|alarms?|excursions?)\b",
                         re.IGNORECASE)


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
        elif r == "due_today":
            out.append(f"{label}: {', '.join(f.due_ticket_ids)} due {NOW:%d %b}")
        elif r == "unacknowledged_latest":
            out.append(f"{label}: latest alert at {f.alerts.iloc[-1]['time']} has no acknowledgement")
        elif r == "repeated":
            out.append(f"{label}: {f.repeats} alerts this shift")
    return out


def build_evidence(item: ScoredItem) -> dict:
    f = item.finding
    return {
        "handover_time": f"{NOW:%Y-%m-%d %H:%M}",
        "asset_id": f.asset_id,
        "asset": f.details or {"note": "not in the asset list"},
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
        "fired_reasons": reason_details(item),
    }


def allowed_citations(evidence: dict) -> list[str]:
    return [x["cite"] for key in ("alerts", "notes", "tickets") for x in evidence[key]]


# ---------- template fallback (no API key needed) ----------

def _join_times(times: list[str]) -> str:
    return times[0] if len(times) == 1 else ", ".join(times[:-1]) + " and " + times[-1]


def template_explanation(item: ScoredItem) -> dict:
    f = item.finding
    rule = str(f.details.get("rule", ""))
    reasons = item.reasons

    # Headline: what it is + the most important reason.
    if "clash" in reasons:
        phrase = "notes say OK, alerts continued"
    elif "trend_worsening" in reasons and "near_limit" in reasons:
        phrase = "getting worse, near alarm limit"
    elif "trend_worsening" in reasons:
        phrase = "readings getting worse"
    elif "no_open_ticket" in reasons:
        phrase = "problem with no ticket"
    elif "due_today" in reasons:
        phrase = "ticket due today"
    elif "unacknowledged_latest" in reasons:
        phrase = "latest alert not acknowledged"
    else:
        phrase = "worth a check"
    headline = f"{f.asset_id} {f.asset_type}: {phrase}"
    if not f.asset_type or len(headline.split()) > MAX_HEADLINE_WORDS:
        headline = f"{f.asset_id}: {phrase}"  # long asset types don't fit in 10 words

    # Why: one sentence built from the facts that fired.
    parts = []
    if f.repeats:
        counted = f"{f.repeats} {f.max_severity} alert{'s' if f.repeats > 1 else ''} this shift"
        if len(f.values) >= 2:
            span = f"{f.values[0][1]:g} to {f.values[-1][1]:g}"
            if f.limit is not None and all(past_limit(v, f.limit, f.higher_worse) for _, v in f.values):
                span += f", all past the {f.limit:g} limit"
            counted += f" ({span})"
        parts.append(counted)
    if "clash" in reasons:
        times = f.clash_note_times
        noun = "note" if len(times) == 1 else "notes"
        parts.append(f"the {_join_times(times)} {noun} said it was fine but alerts kept coming")
    if "near_limit" in reasons:
        parts.append(f"latest reading {f.values[-1][1]:g} is close to the {f.limit:g} alarm limit")
    if "no_open_ticket" in reasons:
        parts.append("there is no open ticket")
    for ticket_id in f.due_ticket_ids:
        t = f.tickets[f.tickets["id"] == ticket_id].iloc[0]
        parts.append(f"{ticket_id} ({t['priority']}) is due today at {fmt_time(t['due'], '%H:%M')}")
    if "unacknowledged_latest" in reasons:
        parts.append("the latest alert is not acknowledged")
    if rule:
        parts.append(f"site rule: {rule}")
    elif f.details.get("note"):
        parts.append(f"{f.details['note']}")
    why = ("; ".join(parts) or "nothing urgent fired").strip()
    why = why[0].upper() + why[1:] + "."

    # Action: one imperative sentence.
    if "no_open_ticket" in reasons:
        extra = " and log a deviation, as the site rule requires" if "deviation" in rule.lower() else ""
        if "clash" in reasons:
            action = f"Check {f.asset_id} on site now, then raise a ticket{extra}."
        elif "trend_worsening" in reasons or "near_limit" in reasons:
            action = f"Raise a ticket for {f.asset_id} and get it inspected before it reaches the alarm limit."
        else:
            action = f"Raise a ticket for {f.asset_id}{extra}."
    elif "due_today" in reasons:
        t = f.tickets[f.tickets["id"] == f.due_ticket_ids[0]].iloc[0]
        action = f"Confirm with {t['assignee']} that {t['id']} will be done before {fmt_time(t['due'], '%H:%M')} today"
        if "cannot be used" in rule.lower():
            action += f", or tag {f.asset_id} out of use"
        action += "."
    elif "unacknowledged_latest" in reasons:
        action = f"Acknowledge the latest {f.asset_id} alert and check the asset."
    else:
        action = f"Review {f.asset_id} when convenient."

    evidence = build_evidence(item)
    return {
        "headline": _limit_words(headline),
        "why": why,
        "action": action,
        "citations": allowed_citations(evidence),
        "source": "template",
    }


# ---------- LLM version ----------

SYSTEM_PROMPT = f"""You help an incoming shift engineer at a pharma site. You get the evidence for ONE item
that our rules have already ranked as needing attention. Write:
- headline: at most {MAX_HEADLINE_WORDS} words saying what is wrong
- why: ONE sentence explaining why it needs attention now
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
        "why": {"type": "string"},
        "action": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "why", "action", "citations"],
    "additionalProperties": False,
}


def _limit_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_HEADLINE_WORDS])


def _numbers(text: str) -> set[float]:
    text = DATE.sub(" ", text.replace("\u2212", "-"))  # treat a typographic minus like "-"
    return {float(n) for n in NUMBER.findall(text)}


def invented_numbers(answer: dict, evidence: dict) -> set[float]:
    """Numbers in the answer that appear nowhere in the evidence. Signs count: 61.9 is not -61.9."""
    known = _numbers(json.dumps(evidence, ensure_ascii=False))
    written = _numbers(" ".join([answer["headline"], answer["why"], answer["action"]]))
    return written - known


def overcounted_alerts(answer: dict, evidence: dict) -> list[str]:
    """Claims like "6 alarms" when the asset only had 4."""
    text = " ".join([answer["headline"], answer["why"], answer["action"]])
    bad = []
    for match in ALERT_COUNT.finditer(text):
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
    for key in ("headline", "why", "action"):
        if not isinstance(answer.get(key), str) or not answer[key].strip():
            raise BadAnswer(f"missing {key}")
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
        "why": answer["why"].strip(),
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
                cache[key] = {k: result[k] for k in ("headline", "why", "action", "citations")}
                changed = True
            except llm.LLMUnavailable as e:
                warnings.append(f"{item.asset_id}: LLM explanation not used ({e}); showing the template.")
                if not isinstance(e, llm.AnswerUnusable):
                    llm_ok = False  # the API itself failed: don't retry for every item

        out[item.asset_id] = result or template_explanation(item)

    if changed:
        llm.write_cache(CACHE_FILE, cache)
    return out, warnings
