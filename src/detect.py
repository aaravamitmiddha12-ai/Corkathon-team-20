"""Plain rules that look at each asset's data and raise flags.

No LLM here. Each flag is a simple, testable rule:
  repeats               how many alerts the asset had
  trend_worsening       each alert reading is worse than the one before (2+ readings)
  near_limit            latest reading is not yet past its alarm limit but within 15% of it
  no_open_ticket        something is wrong (a medium+ alert, or a note raising a concern)
                        but there's no open / scheduled / approved ticket
  clash                 a note said it was fine, and a medium+ alert came AFTER that note
  unacknowledged_latest the most recent alert has no one in acknowledged_by
  due_soon              due_by falls before the end of the incoming shift (or is already past)
  due_today             a live ticket is due on the handover day (kept as a plain fact)

Limits, units and which side is bad come from assets.json when it has them,
otherwise from the alert message ("above alarm limit -70C", "alarm below 10 Pa").
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from src.due import compute_due_by
from src.load import NOW, SEVERITIES, Pack

ACTIVE_TICKET_STATUSES = {"open", "scheduled", "approved"}
SERIOUS_SEVERITIES = {"medium", "high"}  # "a real problem", used by no_open_ticket and clash
SEVERITY_ORDER = SEVERITIES
NEAR_LIMIT_FRACTION = 0.15
HANDOVER_DAY = NOW.date()

# A number that isn't part of a name like "AHU-4" or "FRZ-12".
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?")
# "alarm limit -70C", "(alarm 250 Pa)", "alarm below 1000". Tried first, so warn levels are ignored.
ALARM_LIMIT = re.compile(r"alarm(?: limit)?\s*(?:below|above|<|>)?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
# "exceeds limit 1.3 uS/cm" (no alarm wording), but never "warn limit 6.0".
ANY_LIMIT = re.compile(r"(?<!warn )limit\s*(?:below|above|<|>)?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_value(message: str) -> float | None:
    """The first number in the message is the reading."""
    match = NUMBER.search(message)
    return float(match[0]) if match else None


def parse_limit(message: str) -> float | None:
    match = ALARM_LIMIT.search(message) or ANY_LIMIT.search(message)
    return float(match[1]) if match else None


def higher_is_worse(message: str) -> bool:
    """Most limits are ceilings (temperature above, conductivity exceeds, vibration up)."""
    return "below" not in message.lower()


@dataclass
class Finding:
    asset_id: str
    asset_type: str
    criticality: str
    details: dict
    alerts: pd.DataFrame
    notes: pd.DataFrame
    tickets: pd.DataFrame
    now: pd.Timestamp = NOW
    repeats: int = 0
    max_severity: str | None = None
    values: list = field(default_factory=list)   # [(time "HH:MM", value)] for alerts that have a reading
    limit: float | None = None
    warn_limit: float | None = None
    higher_worse: bool = True
    unit: str = ""
    measurement: str = ""
    trend_worsening: bool = False
    near_limit: bool = False
    no_open_ticket: bool = False
    clash: bool = False
    clash_note_times: list = field(default_factory=list)
    clash_alert_times: list = field(default_factory=list)
    unacknowledged_latest: bool = False
    due_today: bool = False
    due_ticket_ids: list = field(default_factory=list)
    due_by: pd.Timestamp | None = None
    due_by_source: str = ""
    due_soon: bool = False
    breaches: list = field(default_factory=list)  # e.g. ["past_alarm_limit", "overdue"]

    @property
    def active_tickets(self) -> pd.DataFrame:
        return self.tickets[self.tickets["status"].isin(ACTIVE_TICKET_STATUSES)]

    @property
    def rules(self) -> list:
        rules = self.details.get("rules", [])
        return rules if isinstance(rules, list) else []

    @property
    def latest_value(self) -> float | None:
        return self.values[-1][1] if self.values else None

    @property
    def worst_value(self) -> float | None:
        """The worst reading this shift: highest for a ceiling limit, lowest for a floor."""
        if not self.values:
            return None
        values = [v for _, v in self.values]
        return max(values) if self.higher_worse else min(values)

    @property
    def readings_are_events(self) -> bool:
        """Short separate events (e.g. 4-6 s excursions) rather than a continuous measurement."""
        return self.details.get("readings") == "events"

    def is_worse(self, a: float, b: float) -> bool:
        """True if reading a is worse than reading b."""
        return a > b if self.higher_worse else a < b


def all_asset_ids(pack: Pack, tagged_notes: pd.DataFrame) -> list[str]:
    """Every asset mentioned anywhere, so nothing is ever dropped."""
    ids = set(pack.assets.index) | set(pack.alerts["asset"]) | set(pack.tickets["asset"])
    ids |= {a for a in tagged_notes["asset_id"] if isinstance(a, str)}
    return sorted(a for a in ids if isinstance(a, str) and a.strip())


def is_worsening(values: list[float], higher_worse: bool) -> bool:
    if len(values) < 2:
        return False
    steps = zip(values, values[1:])
    return all((b > a) if higher_worse else (b < a) for a, b in steps)


def past_limit(value: float, limit: float, higher_worse: bool) -> bool:
    return value > limit if higher_worse else value < limit


def is_near_limit(value: float, limit: float, higher_worse: bool) -> bool:
    if past_limit(value, limit, higher_worse):
        return False  # already past the limit: severity covers that
    return abs(limit - value) <= NEAR_LIMIT_FRACTION * abs(limit)


def _number(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def detect_asset(asset_id: str, pack: Pack, tagged_notes: pd.DataFrame) -> Finding:
    if asset_id in pack.assets.index:
        row = pack.assets.loc[asset_id]
        asset_type, criticality, details = row["type"], row["criticality"], row["details"]
    else:
        asset_type, criticality, details = "", "low", {}  # not in the asset list: treat as low

    alerts = pack.alerts[pack.alerts["asset"] == asset_id].sort_values("timestamp")
    notes = tagged_notes[tagged_notes["asset_id"] == asset_id].sort_values("timestamp")
    tickets = pack.tickets[pack.tickets["asset"] == asset_id]
    now = pack.shift.handover

    f = Finding(asset_id, asset_type, criticality, details, alerts, notes, tickets, now=now)
    f.repeats = len(alerts)
    f.unit = details.get("unit", "")
    f.measurement = details.get("measurement", "")
    f.warn_limit = _number(details.get("warn_limit"))
    readings = [parse_value(m) for m in alerts["message"]]

    if f.repeats:
        f.max_severity = max(alerts["severity"], key=SEVERITY_ORDER.index)
        f.unacknowledged_latest = alerts.iloc[-1]["acknowledged_by"] == ""

        numeric = [(t, v, m) for t, v, m in zip(alerts["time"], readings, alerts["message"]) if v is not None]
        f.values = [(t, v) for t, v, _ in numeric]
        if numeric:
            # Limit and direction: assets.json first, else the latest alert that has a reading.
            _, latest_value, latest_msg = numeric[-1]
            direction = details.get("direction")
            f.higher_worse = (direction != "below") if direction in ("above", "below") else higher_is_worse(latest_msg)
            f.limit = _number(details.get("alarm_limit"))
            if f.limit is None:
                f.limit = parse_limit(latest_msg)
            f.trend_worsening = is_worsening([v for _, v in f.values], f.higher_worse)
            if f.limit is not None:
                f.near_limit = is_near_limit(latest_value, f.limit, f.higher_worse)
    elif details.get("direction") in ("above", "below"):
        f.higher_worse = details["direction"] != "below"
        f.limit = _number(details.get("alarm_limit"))

    serious = alerts[alerts["severity"].isin(SERIOUS_SEVERITIES)]
    concern_notes = notes[~notes["reassuring"]]
    something_wrong = len(serious) > 0 or len(concern_notes) > 0
    f.no_open_ticket = something_wrong and f.active_tickets.empty

    for _, note in notes[notes["reassuring"]].iterrows():
        later = serious[serious["timestamp"] > note["timestamp"]]
        if len(later):
            f.clash = True
            if note["time"] not in f.clash_note_times:
                f.clash_note_times.append(note["time"])
            f.clash_alert_times.extend(t for t in later["time"] if t not in f.clash_alert_times)

    due = f.active_tickets[f.active_tickets["due"].dt.date == now.date()]
    f.due_today = not due.empty
    f.due_ticket_ids = list(due["id"])

    def past(value, limit):
        return past_limit(value, limit, f.higher_worse)

    earlier = None
    if pack.previous_alerts is not None:
        earlier = pack.previous_alerts[pack.previous_alerts["asset"] == asset_id].sort_values("timestamp")
    f.due_by, f.due_by_source = compute_due_by(
        f.rules, alerts, readings, f.limit, past, f.active_tickets,
        earlier, [parse_value(m) for m in earlier["message"]] if earlier is not None else None)
    f.due_soon = f.due_by is not None and f.due_by <= pack.shift.incoming_end

    if f.limit is not None and any(past(v, f.limit) for _, v in f.values):
        f.breaches.append("past_alarm_limit")
    if f.warn_limit is not None and any(past(v, f.warn_limit) for _, v in f.values):
        f.breaches.append("past_warn_limit")
    if f.due_by is not None and f.due_by < now:
        f.breaches.append("overdue")
    return f


def detect(pack: Pack, tagged_notes: pd.DataFrame) -> dict[str, Finding]:
    return {a: detect_asset(a, pack, tagged_notes) for a in all_asset_ids(pack, tagged_notes)}
