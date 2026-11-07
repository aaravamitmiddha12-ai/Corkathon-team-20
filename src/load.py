"""Step 1: load the sample pack into clean pandas DataFrames."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "handover-sample-pack"

# The demo's "now": the 07:00 handover on Sat 7 Nov 2026.
NOW = pd.Timestamp("2026-11-07 07:00")

# The night shift runs Fri 6 Nov 19:00 -> Sat 7 Nov 07:00.
SHIFT_FIRST_DAY = pd.Timestamp("2026-11-06")
SHIFT_END_HOUR = 7  # note times before 07:00 belong to the second day

NOTE_LINE = re.compile(r"^(\d{1,2}):(\d{2})\s+(.+)$")

SEVERITIES = ["info", "low", "medium", "high"]
SEVERITY_ALIASES = {"critical": "high", "warning": "medium", "warn": "medium", "": "info"}
NO_ASSET = "(no asset)"  # rows with a blank asset column are kept under this name, never dropped


def clean_severity(value: str) -> str:
    """Map other systems' words onto our 4 levels. Unknown words count as medium, so nothing is hidden."""
    value = SEVERITY_ALIASES.get(value, value)
    return value if value in SEVERITIES else "medium"


def fmt_time(ts, pattern: str) -> str:
    """Format a timestamp, or return '' if it's missing (a blank cell in the CSV)."""
    return "" if pd.isna(ts) else ts.strftime(pattern)


@dataclass
class Pack:
    notes: pd.DataFrame
    alerts: pd.DataFrame
    tickets: pd.DataFrame
    assets: pd.DataFrame
    answer_key: pd.DataFrame


def note_timestamp(hour: int, minute: int) -> pd.Timestamp:
    """Turn an HH:MM from the night log into a full timestamp."""
    day = SHIFT_FIRST_DAY
    if hour < SHIFT_END_HOUR:
        day += pd.Timedelta(days=1)
    return day + pd.Timedelta(hours=hour, minutes=minute)


def load_notes(path: Path) -> pd.DataFrame:
    """One row per timed note line. Header lines (no HH:MM) are skipped."""
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = NOTE_LINE.match(line)
        if not match:
            continue
        hour, minute, text = int(match[1]), int(match[2]), match[3].strip()
        rows.append(
            {
                "time": f"{hour:02d}:{minute:02d}",
                "timestamp": note_timestamp(hour, minute),
                "text": text,
                "line": line,  # the full line, used as the tag cache key
            }
        )
    return pd.DataFrame(rows, columns=["time", "timestamp", "text", "line"])


def load_alerts(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["severity"] = df["severity"].str.strip().str.lower().map(clean_severity)
    df["asset"] = df["asset"].str.strip().replace("", NO_ASSET)
    df["acknowledged_by"] = df["acknowledged_by"].str.strip()
    df["time"] = df["timestamp"].dt.strftime("%H:%M").fillna("??:??")
    return df.sort_values("timestamp").reset_index(drop=True)


def load_tickets(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["opened"] = pd.to_datetime(df["opened"])
    df["due"] = pd.to_datetime(df["due"])
    df["status"] = df["status"].str.strip().str.lower()
    df["asset"] = df["asset"].str.strip().replace("", NO_ASSET)
    return df


def load_assets(path: Path) -> pd.DataFrame:
    """One row per asset. `details` holds every field from the JSON (type, rule, notes...)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        {
            "asset_id": asset_id,
            "type": info.get("type", ""),
            "criticality": str(info.get("criticality", "low")).lower(),
            "details": info,
        }
        for asset_id, info in raw.items()
    ]
    return pd.DataFrame(rows).set_index("asset_id")


def load_answer_key(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_all(data_dir: Path = DATA_DIR) -> Pack:
    return Pack(
        notes=load_notes(data_dir / "shift_notes_night.txt"),
        alerts=load_alerts(data_dir / "alerts.csv"),
        tickets=load_tickets(data_dir / "tickets.csv"),
        assets=load_assets(data_dir / "assets.json"),
        answer_key=load_answer_key(data_dir / "answer_key.csv"),
    )
