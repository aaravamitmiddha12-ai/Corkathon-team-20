"""Load a shift's sample pack into clean pandas DataFrames.

Two sample shifts:
  "night"  Fri 6 Nov 19:00 -> Sat 7 Nov 07:00, handed over at Sat 07:00
  "day"    Sat 7 Nov 07:00 -> Sat 7 Nov 19:00, handed over at Sat 19:00
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "handover-sample-pack"


@dataclass(frozen=True)
class Shift:
    id: str
    label: str              # what the shift selector shows
    start: pd.Timestamp     # when the outgoing shift began
    handover: pd.Timestamp  # "now" for this handover
    data_dir: Path
    notes_file: str
    incoming_engineer: str  # default name for the person taking over
    previous: str | None = None  # the shift before this one, if we have its data

    @property
    def incoming_end(self) -> pd.Timestamp:
        """End of the incoming shift (12-hour shifts)."""
        return self.handover + pd.Timedelta(hours=12)

    @property
    def title(self) -> str:
        return f"{self.handover:%a} {self.handover.day} {self.handover:%b}, {self.handover:%H:%M} handover"


SHIFTS = {
    "night": Shift("night", "Sat 07:00 handover", pd.Timestamp("2026-11-06 19:00"), pd.Timestamp("2026-11-07 07:00"),
                   DATA_DIR, "shift_notes_night.txt", "S. O'Brien"),
    "day": Shift("day", "Sat 19:00 handover", pd.Timestamp("2026-11-07 07:00"), pd.Timestamp("2026-11-07 19:00"),
                 DATA_DIR / "day_shift", "shift_notes_day.txt", "K. Walsh", previous="night"),
}
DEFAULT_SHIFT = "night"

# Kept for older code and tests: the first sample's handover moment.
NOW = SHIFTS["night"].handover

NOTE_LINE = re.compile(r"^(\d{1,2}):(\d{2})\s+(.+)$")
ENGINEER = re.compile(r"Engineer:\s*(.+?)\s*$", re.MULTILINE)

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
    answer_key: pd.DataFrame  # empty when the shift has no expert answer key
    shift: Shift
    outgoing_engineer: str
    previous_alerts: pd.DataFrame | None = None  # the previous shift's alerts (for rule windows)


def note_timestamp(hour: int, minute: int, shift_start: pd.Timestamp = SHIFTS["night"].start) -> pd.Timestamp:
    """Turn an HH:MM from a shift log into a full timestamp. Times earlier than the shift start are the next day."""
    t = shift_start.normalize() + pd.Timedelta(hours=hour, minutes=minute)
    if t < shift_start:
        t += pd.Timedelta(days=1)
    return t


def load_notes(path: Path, shift_start: pd.Timestamp = SHIFTS["night"].start) -> pd.DataFrame:
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
                "timestamp": note_timestamp(hour, minute, shift_start),
                "text": text,
                "line": line,  # the full line, used as the tag cache key
            }
        )
    return pd.DataFrame(rows, columns=["time", "timestamp", "text", "line"])


def engineer_name(path: Path) -> str:
    match = ENGINEER.search(path.read_text(encoding="utf-8"))
    return match[1] if match else "Outgoing engineer"


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
    """One row per asset. `details` holds every field from the JSON (type, rules, unit, limits...)."""
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
    if not path.exists():
        return pd.DataFrame(columns=["rank", "item", "why", "evidence", "action"], dtype=str)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _find_assets_file(data_dir: Path) -> Path:
    """A shift folder can have its own assets.json, or share its parent's."""
    for folder in (data_dir, data_dir.parent):
        if (folder / "assets.json").exists():
            return folder / "assets.json"
    raise FileNotFoundError(f"no assets.json in {data_dir} or its parent")


def load_all(data_dir: Path | None = None, shift: str | Shift = DEFAULT_SHIFT) -> Pack:
    """Load one shift. `data_dir` overrides the shift's folder (used by tests with a copied pack)."""
    s = SHIFTS[shift] if isinstance(shift, str) else shift
    folder = Path(data_dir) if data_dir else s.data_dir
    notes_path = folder / s.notes_file
    return Pack(
        notes=load_notes(notes_path, s.start),
        alerts=load_alerts(folder / "alerts.csv"),
        tickets=load_tickets(folder / "tickets.csv"),
        assets=load_assets(_find_assets_file(folder)),
        answer_key=load_answer_key(folder / "answer_key.csv"),
        shift=s,
        outgoing_engineer=engineer_name(notes_path),
        previous_alerts=_previous_alerts(s, data_dir),
    )


def _previous_alerts(s: Shift, data_dir) -> pd.DataFrame | None:
    """Only for the built-in sample folders: a copied test pack has no 'previous shift'."""
    if s.previous is None or data_dir is not None:
        return None
    path = SHIFTS[s.previous].data_dir / "alerts.csv"
    return load_alerts(path) if path.exists() else None
