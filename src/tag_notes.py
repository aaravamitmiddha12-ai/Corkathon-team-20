"""Step 2: tag each shift-note line.

Every line gets: {asset_id or None, reassuring: bool, mentions_future_action: bool}
  reassuring             = the writer implies it's fine or minor ("seems ok", "only a blip")
  mentions_future_action = the writer defers something ("will log it tomorrow")

Three modes, one function:
  "manual" - the hard-coded tags below (used by the tests)
  "demo"   - cached LLM tags if we have them, otherwise manual. Never calls the API.
  "llm"    - cached tags, otherwise ask the LLM (and cache it), otherwise manual.
"""

import pandas as pd

from src import llm

CACHE_FILE = "tags.json"


def _tag(asset_id, reassuring, future):
    return {"asset_id": asset_id, "reassuring": reassuring, "mentions_future_action": future}


# Hand-written tags for the sample notes, keyed by the full line text.
MANUAL_TAGS = {
    "19:20 walked round, all quiet. HVAC AHU-4 filter dP a bit high, within limits, just noting.":
        _tag("AHU-4", True, False),
    "21:05 FRZ-12 (-80 freezer, QC retained samples) temp alarm. Reset it, temp came back down. Seems ok.":
        _tag("FRZ-12", True, False),
    "22:40 printer in QC office out of toner again, left note for admin.":
        _tag("PRN-QC-02", False, False),
    "23:15 FRZ-12 alarmed again, reset again, door was shut properly. Prob sensor? Will mention to day shift.":
        _tag("FRZ-12", True, True),
    "01:30 chiller CH-2 pump 3 making a grinding noise on and off. Vibration looks a bit up. Will log it tmrw if it keeps going.":
        _tag("CH-2-P3", False, True),
    "03:10 WFI loop conductivity blipped, came straight back in spec. Didn't raise anything as it was only a few secs.":
        _tag("WFI-LOOP-1", True, False),
    "04:00 HPLC-07 still down from yesterday, vendor engineer booked for this morning apparently. Lab said they need it for the batch 2611 release test.":
        _tag("HPLC-07", False, True),
    "05:20 cleaners propped the lab B door open, alarm, closed it.":
        _tag("DOOR-LAB-B", True, False),
    "06:10 BAL-03 balance calibration sticker says due today.":
        _tag("BAL-03", False, False),
    "06:45 handing over. Quiet enough night overall.":
        _tag(None, True, False),
}

# Used only for lines that aren't in MANUAL_TAGS (e.g. someone edits the notes file).
REASSURING_PHRASES = ["seems ok", "seems fine", "all good", "only a blip", "blipped", "came straight back",
                      "came back", "within limits", "in spec", "no issue", "quiet", "closed it", "sorted"]
FUTURE_PHRASES = ["will log", "will mention", "will raise", "will check", "tomorrow", "tmrw", "later",
                  "booked for", "next shift", "day shift"]


def keyword_tag(line: str, known_assets: list[str]) -> dict:
    lower = line.lower()
    asset = next((a for a in sorted(known_assets, key=len, reverse=True) if a.lower() in lower), None)
    return _tag(
        asset,
        any(p in lower for p in REASSURING_PHRASES),
        any(p in lower for p in FUTURE_PHRASES),
    )


def manual_tag(line: str, known_assets: list[str]) -> tuple[dict, str]:
    if line in MANUAL_TAGS:
        return dict(MANUAL_TAGS[line]), "manual"
    return keyword_tag(line, known_assets), "keywords"


# ---------- LLM version ----------

SYSTEM_PROMPT = """You tag single lines from an engineer's night-shift handover log at a pharma site.

Return JSON with exactly these fields:
- asset_id: the id of the asset the line is about, chosen ONLY from the asset list given, or null if none fits.
  Lines often use informal names ("chiller CH-2 pump 3", "WFI loop", "printer in QC office").
- reassuring: true if the writer implies the issue is fine, resolved or minor
  (e.g. "seems ok", "only a blip", "came straight back", "within limits", "closed it", "prob sensor?").
  false if the writer reports a problem without downplaying it.
- mentions_future_action: true if the writer defers or promises a later action
  (e.g. "will log it tomorrow", "will mention to day shift", "vendor booked for this morning").

Judge only the words in the line. Do not guess beyond them."""


def _schema(known_assets: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "asset_id": {"anyOf": [{"type": "string", "enum": known_assets}, {"type": "null"}]},
            "reassuring": {"type": "boolean"},
            "mentions_future_action": {"type": "boolean"},
        },
        "required": ["asset_id", "reassuring", "mentions_future_action"],
        "additionalProperties": False,
    }


def llm_tag(line: str, asset_list_text: str, known_assets: list[str]) -> dict:
    user = f"Asset list:\n{asset_list_text}\n\nLog line:\n{line}"
    raw = llm.ask_json(SYSTEM_PROMPT, user, _schema(known_assets), effort="low")
    asset = raw.get("asset_id")
    return _tag(
        asset if asset in known_assets else None,  # never trust an id we don't know
        bool(raw.get("reassuring")),
        bool(raw.get("mentions_future_action")),
    )


def _clean_cached(entry: dict, known_assets: list[str]) -> dict | None:
    if not isinstance(entry, dict) or not {"reassuring", "mentions_future_action"} <= entry.keys():
        return None
    asset = entry.get("asset_id")
    return _tag(asset if asset in known_assets else None,
                bool(entry["reassuring"]), bool(entry["mentions_future_action"]))


# ---------- the one function everything else uses ----------

def tag_notes(notes: pd.DataFrame, assets: pd.DataFrame, mode: str = "manual",
              extra_assets: list[str] = ()) -> tuple[pd.DataFrame, list[str]]:
    """Return (notes with tag columns added, list of warnings for the UI)."""
    known = sorted(set(assets.index) | set(extra_assets))
    asset_list_text = "\n".join(
        f"- {a}: {assets.loc[a, 'type']}" if a in assets.index else f"- {a}" for a in known
    )
    cache = llm.read_cache(CACHE_FILE) if mode in ("demo", "llm") else {}
    cache_changed = False
    warnings: list[str] = []
    llm_ok = mode == "llm"  # set to False after the first failure, so we don't wait on every line

    tags, sources = [], []
    for line in notes["line"]:
        tag, source = None, None

        entry = cache.get(line)
        if isinstance(entry, dict) and entry.get("model", llm.model_name()) == llm.model_name():
            tag = _clean_cached(entry, known)
            source = "llm (cached)" if tag else None

        if tag is None and llm_ok:
            try:
                tag = llm_tag(line, asset_list_text, known)
                source = "llm"
                cache[line] = {**tag, "model": llm.model_name()}
                cache_changed = True
            except llm.LLMUnavailable as e:
                warnings.append(f"LLM tag for the {line[:5]} note not used ({e}); using the manual tag.")
                if not isinstance(e, llm.AnswerUnusable):
                    llm_ok = False  # the API itself failed: don't wait on every line

        if tag is None:
            tag, source = manual_tag(line, known)

        tags.append(tag)
        sources.append(source)

    if cache_changed:
        llm.write_cache(CACHE_FILE, cache)

    out = notes.copy()
    out["asset_id"] = pd.Series([t["asset_id"] for t in tags], index=out.index, dtype=object)
    out["reassuring"] = [t["reassuring"] for t in tags]
    out["mentions_future_action"] = [t["mentions_future_action"] for t in tags]
    out["tag_source"] = sources
    return out, warnings
