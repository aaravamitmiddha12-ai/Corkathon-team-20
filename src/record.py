"""Feature 5: Handover record. Signing off writes a read-only record (JSON + printable HTML)."""

import html
import json
from datetime import datetime
from pathlib import Path

from src import respond, review, state
from src.due import due_label


def _rest_entry(result, i) -> dict:
    return {
        "asset": i.asset_id,
        "headline": result.explanations[i.asset_id]["headline"],
        "carried_over": i.carried_over,
        "previously_dismissed": respond.dismissal_line(i.dismissal) if i.carried_over else "",
    }


def build(result, signer: str, incoming: str | None = None) -> dict:
    shift = result.shift
    items = []
    for n, item in enumerate(result.top, start=1):
        ex = result.explanations[item.asset_id]
        r = result.responses.get(item.asset_id, {})
        rv = item.review or {}
        items.append({
            "rank": n,
            "asset": item.asset_id,
            "headline": ex["headline"],
            "action": ex["action"],
            "due": due_label(item.finding.due_by, shift.handover)[0],
            "outgoing_choice": review.CHOICES.get(rv.get("choice"), ""),
            "outgoing_comment": rv.get("comment", ""),
            "response": respond.RESPONSE_LABELS.get(r.get("kind"), ""),
            "responder": r.get("name", ""),
            "response_time": r.get("at", ""),
            "reason": r.get("reason", ""),
            "reference": r.get("reference", ""),
            "note": r.get("note", ""),
            "expiry": respond.EXPIRY_OPTIONS.get(r.get("expiry"), ""),
            "dismissed_earlier": item.dismissal_status == "now_worse",
        })
    return {
        "shift": shift.title,
        "shift_id": shift.id,
        "outgoing_engineer": result.pack.outgoing_engineer,
        "outgoing_review_completed": result.review_complete,
        "incoming_engineer": (incoming or signer).strip(),
        "signed_off_by": signer.strip(),
        "signed_off_at": state.now_iso(),
        "items": items,
        # The same two groups the screen shows below the top 5.
        "carried_over": [_rest_entry(result, i) for i in result.carried],
        "not_urgent": [_rest_entry(result, i) for i in result.not_urgent],
    }


def sign_off(result, signer: str, incoming: str | None = None) -> tuple[dict, Path, Path]:
    """Save the record. Refuses unless every top-5 item has a response, a name is given,
    and this handover hasn't been signed off already (the record is read-only)."""
    if not respond.all_responded(result.top, result.responses):
        raise ValueError("every item in the top 5 needs a response before sign-off")
    if not signer.strip():
        raise ValueError("a name is needed to sign off")
    with state.LOCK:
        if latest(result.shift.id) is not None:
            raise ValueError("this handover has already been signed off")
        rec = build(result, signer, incoming)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = state.state_dir() / "records"
        json_path = folder / f"{result.shift.id}_{stamp}.json"
        html_path = folder / f"{result.shift.id}_{stamp}.html"
        with open(json_path, "x", encoding="utf-8") as fh:  # "x": never overwrite an existing record
            fh.write(json.dumps(rec, indent=2, ensure_ascii=False))
        with open(html_path, "x", encoding="utf-8") as fh:
            fh.write(to_html(rec))
    return rec, json_path, html_path


def latest(shift_id: str) -> dict | None:
    """The most recent signed-off record for a shift, or None."""
    paths = sorted((state.state_dir() / "records").glob(f"{shift_id}_*.json"))
    for path in reversed(paths):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
    return None


def to_html(rec: dict) -> str:
    e = html.escape

    def when(iso: str) -> str:
        return e(state.short_time(iso)) if iso else ""

    rows = []
    for i in rec["items"]:
        response = e(i["response"])
        if i["responder"]:
            response += f"<br><span class='muted'>{e(i['responder'])} · {when(i['response_time'])}</span>"
        if i["reason"]:
            ref = f" ({e(i['reference'])})" if i["reference"] else ""
            response += f"<br>Reason: {e(i['reason'])}{ref}"
            if i["expiry"]:
                response += f"<br><span class='muted'>Expires: {e(i['expiry'])}</span>"
        if i["note"]:
            response += f"<br><span class='muted'>{e(i['note'])}</span>"
        outgoing = e(i["outgoing_choice"])
        if i["outgoing_comment"]:
            outgoing += f"<br><span class='muted'>{e(i['outgoing_comment'])}</span>"
        due = f"<br><span class='muted'>{e(i['due'])}</span>" if i["due"] else ""
        rows.append(f"<tr><td>{i['rank']}</td><td><b>{e(i['asset'])}</b><br>{e(i['headline'])}{due}</td>"
                    f"<td>{e(i['action'])}</td><td>{outgoing or '—'}</td><td>{response}</td></tr>")

    carried = "".join(
        f"<li><b>{e(i['asset'])}</b> · {e(i['headline'])}"
        f" <span class='muted'>(previously dismissed: {e(i['previously_dismissed'])})</span></li>"
        for i in rec.get("carried_over", [])
    )
    rest = "".join(f"<li><b>{e(i['asset'])}</b> · {e(i['headline'])}</li>" for i in rec["not_urgent"])
    review_state = "completed" if rec["outgoing_review_completed"] else "not completed"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Handover record · {e(rec['shift'])}</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #1a1a19; background: #fff;
          max-width: 1000px; margin: 24px auto; padding: 0 16px; line-height: 1.45; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  .meta {{ display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; margin: 12px 0 20px; }}
  .meta dt {{ color: #52514e; }} .meta dd {{ margin: 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; }}
  th, td {{ border: 1px solid #d6d5d0; padding: 6px 8px; text-align: left; vertical-align: top; }}
  th {{ background: #f3f2ef; }}
  .muted {{ color: #6b6a66; font-size: 0.85rem; }}
  .readonly {{ color: #52514e; font-size: 0.85rem; margin-top: 24px; }}
  @media print {{ body {{ margin: 0; }} .noprint {{ display: none; }} }}
</style></head><body>
<h1>Handover record</h1>
<div class="muted">{e(rec['shift'])}</div>
<dl class="meta">
  <dt>Outgoing engineer</dt><dd>{e(rec['outgoing_engineer'])} (review {review_state})</dd>
  <dt>Incoming engineer</dt><dd>{e(rec['incoming_engineer'])}</dd>
  <dt>Signed off</dt><dd>{e(rec['signed_off_by'])} · {e(rec['signed_off_at'].replace('T', ' '))}</dd>
</dl>
<h2>Needs you first</h2>
<table><thead><tr><th>#</th><th>Item</th><th>Action</th><th>Outgoing engineer</th><th>Response</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>Carried over from last handover</h2>
<ul>{carried or '<li>None</li>'}</ul>
<h2>Checked, not urgent</h2>
<ul>{rest or '<li>None</li>'}</ul>
<p class="readonly">Read-only record produced by Handover Check. Print with your browser (Ctrl+P / Cmd+P).</p>
</body></html>"""
