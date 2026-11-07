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
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


FILES = ["outgoing_reviews.json", "responses.json", "dismissals.json"]

# Streamlit runs every browser session in its own thread of one process, so two people clicking
# at the same moment would otherwise overwrite each other's saves.
LOCK = threading.RLock()


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
    except ValueError:
        # Unreadable: keep a copy instead of letting the next save silently replace it.
        path.replace(path.with_name(f"{path.stem}.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json"))
        return {}
    except OSError:
        return {}
    return data if isinstance(data, dict) else {}


def write(name: str, data: dict) -> None:
    """Write to a unique temp file, then rename over the real one, so a crash never leaves half a file."""
    path = state_dir() / name
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f"{path.stem}-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
    for _ in range(20):  # Windows refuses the rename briefly while another reader has the file open
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def update(name: str, change) -> dict:
    """Read a state file, let `change(data)` edit it, and write it back, one caller at a time."""
    with LOCK:
        data = read(name)
        change(data)
        write(name, data)
        return data


def now_iso() -> str:
    """Real wall-clock time, recorded on every response, review and sign-off."""
    return datetime.now().isoformat(timespec="seconds")


def short_time(iso: str) -> str:
    """'2026-11-07T06:52:10' -> 'Sat 06:52'."""
    try:
        return datetime.fromisoformat(iso).strftime("%a %H:%M")
    except (TypeError, ValueError):
        return ""
