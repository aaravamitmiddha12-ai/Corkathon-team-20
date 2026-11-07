"""JSON files in data/state/ that persist between runs.

  outgoing_reviews.json  {shift_id: {asset: review}}
  responses.json         {shift_id: {asset: response}}
  dismissals.json        {asset: dismissal}           (the latest dismissal per asset)
  records/               one JSON + one printable HTML per signed-off handover

Set HANDOVER_STATE_DIR to use another folder (the tests do this).
To reset the demo, delete the JSON files and the records folder's contents.
"""

import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


FILES = ["outgoing_reviews.json", "responses.json", "dismissals.json"]


def state_dir() -> Path:
    """The state folder, created with empty JSON files on first use."""
    path = Path(os.environ.get("HANDOVER_STATE_DIR", ROOT / "data" / "state"))
    (path / "records").mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if not (path / name).exists():
            (path / name).write_text("{}\n", encoding="utf-8")
    return path


def read(name: str) -> dict:
    path = state_dir() / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def write(name: str, data: dict) -> None:
    path = state_dir() / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)  # write-then-rename, so a crash never leaves half a file


def now_iso() -> str:
    """Real wall-clock time, recorded on every response, review and sign-off."""
    return datetime.now().isoformat(timespec="seconds")


def short_time(iso: str) -> str:
    """'2026-11-07T06:52:10' -> 'Sat 06:52'."""
    try:
        return datetime.fromisoformat(iso).strftime("%a %H:%M")
    except (TypeError, ValueError):
        return ""
