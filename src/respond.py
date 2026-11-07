"""Feature 4: Respond. "Got it", "Dismiss with reason", "Draft ticket".

Dismissals carry forward to later handovers:
  - active    -> score x 0.3 and the item moves to "Carried over from last handover"
  - now_worse -> ignored: the latest reading is worse than the worst reading when it was
                 dismissed, or a new rule breach appeared. The item ranks normally.
  - expired   -> ignored silently
A dismissal never hides an item. At most it moves it out of the top 5.
"""

import pandas as pd

from src import state

RESPONSES_FILE = "responses.json"
DISMISSALS_FILE = "dismissals.json"

RESPONSE_LABELS = {"got_it": "Got it", "dismissed": "Dismissed", "ticket_drafted": "Ticket drafted"}
DISMISS_REASONS = [
    "Known sensor or instrument fault",
    "Expected - planned work",
    "Already handled",
    "Other",
]
EXPIRY_OPTIONS = {
    "handover": "This handover only",
    "24h": "24 hours",
    "ticket": "Until a ticket is closed",
}
CLOSED_TICKET_STATUSES = {"closed", "resolved", "cancelled"}
ACTIVE_TICKET_STATUSES = {"open", "scheduled", "approved"}


# ---------- responses (one per item per handover) ----------

def load_responses(shift_id: str) -> dict:
    data = state.read(RESPONSES_FILE).get(shift_id, {})
    if not isinstance(data, dict):
        return {}
    return {a: r for a, r in data.items() if isinstance(r, dict) and r.get("kind") in RESPONSE_LABELS}


def _save_response(shift_id: str, asset: str, response: dict) -> None:
    def change(data):
        if not isinstance(data.get(shift_id), dict):
            data[shift_id] = {}
        data[shift_id][asset] = response
    state.update(RESPONSES_FILE, change)


def _drop_dismissal_made_here(shift_id: str, asset: str) -> None:
    """Changing a response from "Dismissed" to something else removes that dismissal,
    and puts back the earlier one it replaced (if any)."""
    def change(dismissals):
        d = dismissals.get(asset)
        if isinstance(d, dict) and d.get("shift") == shift_id:
            if isinstance(d.get("previous"), dict):
                dismissals[asset] = d["previous"]
            else:
                del dismissals[asset]
    state.update(DISMISSALS_FILE, change)


def got_it(shift_id: str, asset: str, name: str) -> None:
    _drop_dismissal_made_here(shift_id, asset)
    _save_response(shift_id, asset, {"kind": "got_it", "name": name.strip(), "at": state.now_iso()})


def ticket_drafted(shift_id: str, asset: str, name: str) -> bool:
    """Record "Ticket drafted", unless the item already has a response (looking at the draft
    must never overwrite a "Got it" or a dismissal). Returns True if it was recorded."""
    if asset in load_responses(shift_id):
        return False
    _save_response(shift_id, asset, {"kind": "ticket_drafted", "name": name.strip(), "at": state.now_iso()})
    return True


def known_ticket(reference: str, tickets: pd.DataFrame) -> str | None:
    """The ticket id matching a typed reference (ignoring case and spaces), or None."""
    ref = reference.strip().upper()
    if not ref:
        return None
    match = tickets[tickets["id"].str.strip().str.upper() == ref]
    return match.iloc[0]["id"] if len(match) else None


def dismiss(shift_id: str, handover: pd.Timestamp, finding, name: str, reason: str,
            reference: str = "", note: str = "", expiry: str = "24h") -> dict:
    """Save a dismissal (keyed by asset) and record it as this handover's response."""
    if reason not in DISMISS_REASONS:
        raise ValueError(f"unknown reason {reason!r}")
    if expiry not in EXPIRY_OPTIONS:
        raise ValueError(f"unknown expiry {expiry!r}")
    if expiry == "ticket" and not reference.strip():
        raise ValueError("'Until a ticket is closed' needs the ticket id as the reference")
    dismissal = {
        "asset": finding.asset_id,
        "reason": reason,
        "reference": reference.strip(),
        "note": note.strip(),
        "expiry": expiry,
        "shift": shift_id,
        "made_at": f"{handover:%Y-%m-%dT%H:%M}",   # the demo clock: which handover it was made at
        "recorded_at": state.now_iso(),            # the real clock, for the record
        "by": name.strip(),
        "worst_value": finding.worst_value,         # the bar a later reading must not pass
        "unit": finding.unit,
        "breaches": list(finding.breaches),
    }

    def change(dismissals):
        old = dismissals.get(finding.asset_id)
        if isinstance(old, dict) and old.get("shift") != shift_id:
            dismissal["previous"] = {k: v for k, v in old.items() if k != "previous"}  # keep the history
        elif isinstance(old, dict) and isinstance(old.get("previous"), dict):
            dismissal["previous"] = old["previous"]
        dismissals[finding.asset_id] = dismissal

    state.update(DISMISSALS_FILE, change)
    _save_response(shift_id, finding.asset_id, {
        "kind": "dismissed", "name": name.strip(), "at": dismissal["recorded_at"],
        "reason": reason, "reference": dismissal["reference"], "note": dismissal["note"], "expiry": expiry,
    })
    return dismissal


def _valid_dismissal(d) -> bool:
    """Skip hand-edited or damaged entries instead of crashing the whole app."""
    if not isinstance(d, dict) or not isinstance(d.get("reason"), str):
        return False
    try:
        pd.Timestamp(d.get("made_at"))
    except (ValueError, TypeError):
        return False
    worst = d.get("worst_value")
    if worst is not None and not isinstance(worst, (int, float)):
        return False
    return isinstance(d.get("breaches", []), list)


def load_dismissals() -> dict:
    out = {}
    for asset, d in state.read(DISMISSALS_FILE).items():
        if _valid_dismissal(d) and d.get("made_at"):
            if not _valid_dismissal(d.get("previous")):
                d = {k: v for k, v in d.items() if k != "previous"}
            out[asset] = d
    return out


# ---------- does an earlier dismissal still apply? ----------

def dismissal_status(dismissal: dict | None, finding, shift_id: str, handover: pd.Timestamp,
                     tickets: pd.DataFrame) -> tuple[str | None, str]:
    """Return (status, detail). status: None, "here", "active", "now_worse" or "expired"."""
    if not dismissal:
        return None, ""
    made = pd.Timestamp(dismissal["made_at"])
    if made >= handover:
        # Made at this handover it's just this handover's response; made later it doesn't apply.
        return ("here", "") if dismissal.get("shift") == shift_id else (None, "")

    expiry = dismissal.get("expiry")
    if expiry == "handover":
        return "expired", "was for one handover only"
    if expiry == "24h" and handover >= made + pd.Timedelta(hours=24):
        return "expired", "24 hours have passed"
    if expiry == "ticket":
        ref = known_ticket(dismissal.get("reference", ""), tickets)
        if ref is not None:
            if tickets[tickets["id"] == ref].iloc[0]["status"] in CLOSED_TICKET_STATUSES:
                return "expired", f"{ref} is closed"
        elif finding.active_tickets.empty:
            # Reference missing or unknown: it lasts only while the asset has a live ticket.
            return "expired", "no live ticket for this asset"

    then, now = dismissal.get("worst_value"), finding.latest_value
    if then is not None and now is not None and finding.is_worse(now, then):
        unit = f" {finding.unit}" if finding.unit else ""
        return "now_worse", f"latest reading {now:g}{unit} is worse than {then:g}{unit} when it was dismissed"
    new = sorted(set(finding.breaches) - set(dismissal.get("breaches", [])))
    if new:
        return "now_worse", "new rule breach: " + ", ".join(b.replace("_", " ") for b in new)
    return "active", ""


def dismissal_line(dismissal: dict) -> str:
    """'Known sensor or instrument fault · S. O'Brien · Sat 07:00 handover'."""
    when = pd.Timestamp(dismissal["made_at"])
    parts = [dismissal.get("reason", "Dismissed")]
    if dismissal.get("reference"):
        parts[0] += f" ({dismissal['reference']})"
    parts += [dismissal.get("by") or "unknown", f"{when:%a %H:%M} handover"]
    return " · ".join(parts)


# ---------- draft ticket (template only, no LLM) ----------

def suggested_priority(finding) -> str:
    """Start from criticality (high P2, medium P3, low P4); one step more urgent if a limit
    is breached or close, or a deviation rule applies."""
    level = {"high": 2, "medium": 3}.get(finding.criticality, 4)
    deviation = any(r.get("type") == "deviation_window_hours" for r in finding.rules)
    if "past_alarm_limit" in finding.breaches or finding.near_limit or deviation:
        level -= 1
    return f"P{max(level, 1)}"


def draft_ticket(item, headline: str, evidence_rows: list[tuple[str, str, str]],
                 shift_label: str, raised_by: str) -> str:
    f = item.finding
    what = f"{f.asset_type}, {f.criticality} criticality" if f.asset_type else f"{f.criticality} criticality"
    lines = [
        "DRAFT TICKET (not submitted)",
        f"Asset:      {f.asset_id} ({what})",
        f"Priority:   {suggested_priority(f)} (suggested)",
        f"Summary:    {headline}",
    ]
    if f.due_by is not None:
        lines.append(f"Due by:     {f.due_by:%a %d %b %H:%M} ({f.due_by_source})")
    lines += [f"Raised by:  {raised_by or 'incoming engineer'} at the {shift_label}", "", "Evidence:"]
    lines.append(f"{'Time':<6} {'Source':<16} What")
    for time, source, text in evidence_rows:
        lines.append(f"{time:<6} {source:<16} {text}")
    return "\n".join(lines)


def all_responded(top: list, responses: dict) -> bool:
    """Sign-off is allowed only when every top-5 item has a response."""
    return bool(top) and all(item.asset_id in responses for item in top)
