"""When does each item have to be dealt with by? ("due by")

The earliest of:
  - an asset rule, e.g. deviation_window_hours: first excursion + N hours
  - the due date of a live ticket (this includes calibration tickets)
"""

import pandas as pd


def first_excursion(alerts: pd.DataFrame, values: list, limit, past) -> pd.Timestamp | None:
    """Time of the first alert whose reading is past the alarm limit."""
    for (_, row), value in zip(alerts.iterrows(), values):
        if value is not None and limit is not None and past(value, limit):
            return row["timestamp"]
    return None


def compute_due_by(rules: list, alerts: pd.DataFrame, readings: list, limit, past,
                   active_tickets: pd.DataFrame, earlier_alerts: pd.DataFrame | None = None,
                   earlier_readings: list | None = None) -> tuple[pd.Timestamp | None, str]:
    """Return (due_by rounded down to the minute, a short note saying where it came from).

    `earlier_alerts` are the previous shift's alerts for the same asset: a deviation window
    opened last shift still runs (and is due) this shift.
    """
    candidates = []

    for rule in rules:
        if rule.get("type") == "deviation_window_hours":
            start = None
            if earlier_alerts is not None and len(earlier_alerts):
                start = first_excursion(earlier_alerts, earlier_readings or [], limit, past)
            if start is None:
                start = first_excursion(alerts, readings, limit, past)
            if start is not None:
                hours = rule.get("value", 24)
                candidates.append((start + pd.Timedelta(hours=hours),
                                   f"first excursion {start:%a %H:%M} + {hours} h deviation window"))

    calibration_rule = any(r.get("type") == "unusable_after_calibration_due" for r in rules)
    for _, t in active_tickets.iterrows():
        if pd.notna(t["due"]):
            what = "calibration due" if calibration_rule and "calibrat" in t["summary"].lower() else "due"
            candidates.append((t["due"], f"{t['id']} {what}"))

    if not candidates:
        return None, ""
    deadline, source = min(candidates, key=lambda c: c[0])
    return deadline.floor("min"), source


DAY_MINUTES = 24 * 60
FAR_MINUTES = 2 * DAY_MINUTES  # beyond 48 h, count in days and show the date


def when(ts: pd.Timestamp, now: pd.Timestamp) -> str:
    """'Sun 03:09' when it's within the next or last 6 days, else 'Fri 20 Nov 17:00' so it can't be misread."""
    if ts is None or pd.isna(ts):
        return "not set"
    return f"{ts:%a %H:%M}" if abs(ts - now) < pd.Timedelta(days=6) else f"{ts:%a %d %b %H:%M}"


def due_label(due_by: pd.Timestamp | None, now: pd.Timestamp) -> tuple[str, bool]:
    """("Due by Sun 03:09 · 20 h left", overdue?) or ("", False) when there's no deadline."""
    if due_by is None:
        return "", False
    minutes = int((due_by - now).total_seconds() // 60)
    if minutes < 0:
        late = -minutes
        if late >= FAR_MINUTES:
            return f"Overdue by {late // DAY_MINUTES} days", True
        return (f"Overdue by {late // 60} h" if late >= 60 else f"Overdue by {late} min"), True
    if minutes >= FAR_MINUTES:
        return f"Due by {due_by:%a %d %b %H:%M} · {minutes // DAY_MINUTES} days left", False
    left = f"{minutes // 60} h left" if minutes >= 60 else f"{minutes} min left"
    return f"Due by {due_by:%a %H:%M} · {left}", False
