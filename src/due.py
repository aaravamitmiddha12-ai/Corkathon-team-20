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
                   active_tickets: pd.DataFrame) -> tuple[pd.Timestamp | None, str]:
    """Return (due_by rounded down to the minute, a short note saying where it came from)."""
    candidates = []

    for rule in rules:
        if rule.get("type") == "deviation_window_hours":
            start = first_excursion(alerts, readings, limit, past)
            if start is not None:
                hours = rule.get("value", 24)
                candidates.append((start + pd.Timedelta(hours=hours),
                                   f"first excursion {start:%H:%M} + {hours} h deviation window"))

    calibration_rule = any(r.get("type") == "unusable_after_calibration_due" for r in rules)
    for _, t in active_tickets.iterrows():
        if pd.notna(t["due"]):
            what = "calibration due" if calibration_rule and "calibrat" in t["summary"].lower() else "due"
            candidates.append((t["due"], f"{t['id']} {what}"))

    if not candidates:
        return None, ""
    when, source = min(candidates, key=lambda c: c[0])
    return when.floor("min"), source


def due_label(due_by: pd.Timestamp | None, now: pd.Timestamp) -> tuple[str, bool]:
    """("Due by Sun 03:09 · 20 h left", overdue?) or ("", False) when there's no deadline."""
    if due_by is None:
        return "", False
    minutes = int((due_by - now).total_seconds() // 60)
    if minutes < 0:
        late = -minutes
        return (f"Overdue by {late // 60} h" if late >= 60 else f"Overdue by {late} min"), True
    left = f"{minutes // 60} h left" if minutes >= 60 else f"{minutes} min left"
    return f"Due by {due_by:%a %H:%M} · {left}", False
