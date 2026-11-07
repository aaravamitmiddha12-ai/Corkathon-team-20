"""Home screen: ranked handover (feature 1), notes vs data (2), respond (4), sign-off (5)."""

import pandas as pd
import streamlit as st

from src import record, respond, review, state
from src.charts import reading_chart, timeline
from src.due import due_label
from src.explain import evidence_rows
from ui.components import chip, esc, key_line, reason_chips, show

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------- callbacks (run before the next rerun) ----------

def _name(shift_id: str) -> str:
    return st.session_state.get(f"incoming_{shift_id}", "").strip()


def _need_name(shift_id: str) -> bool:
    if not _name(shift_id):
        st.session_state["flash"] = "Enter your name (Incoming engineer) at the top first."
        return True
    return False


def _changed() -> None:
    st.session_state["state_version"] = st.session_state.get("state_version", 0) + 1


def on_got_it(shift_id: str, asset: str) -> None:
    if _need_name(shift_id):
        return
    respond.got_it(shift_id, asset, _name(shift_id))
    st.session_state.pop("open_form", None)
    _changed()


def on_draft(shift_id: str, asset: str) -> None:
    if st.session_state.get("open_form") == (shift_id, asset, "draft"):
        st.session_state["open_form"] = None  # just closing the draft: record nothing
        return
    if _need_name(shift_id):
        return
    st.session_state["open_form"] = (shift_id, asset, "draft")
    if respond.ticket_drafted(shift_id, asset, _name(shift_id)):  # never overwrites a saved response
        _changed()


def on_dismiss_open(shift_id: str, asset: str) -> None:
    current = st.session_state.get("open_form")
    st.session_state["open_form"] = None if current == (shift_id, asset, "dismiss") else (shift_id, asset, "dismiss")


# ---------- pieces ----------

def notes_column(result) -> None:
    st.subheader("What the notes say")
    for _, note in result.notes.iterrows():
        asset = note["asset_id"]
        finding = result.findings.get(asset) if isinstance(asset, str) else None
        is_clash = bool(finding and note["time"] in finding.clash_note_times)
        tag = chip("data disagrees", "clash") if is_clash else ""
        label = f'<span class="hc-asset">{esc(asset)}</span>' if isinstance(asset, str) else ""
        show(f'<div class="hc-note{" clash" if is_clash else ""}"><span class="hc-time">{esc(note["time"])}</span>'
             f'{esc(note["text"])} {tag}{label}</div>')
    show('<div class="hc-muted">Amber = the note said it was fine, but a medium or high alert came after it.</div>')


def response_status(r: dict | None) -> str:
    if not r:
        return ""
    who = f" · {esc(r.get('name', ''))} · {esc(state.short_time(r.get('at', '')))}"
    if r["kind"] == "got_it":
        return f'<div class="hc-status done">✓ Got it{who}</div>'
    if r["kind"] == "ticket_drafted":
        return f'<div class="hc-status done">✓ Ticket drafted{who}</div>'
    ref = f" ({esc(r['reference'])})" if r.get("reference") else ""
    expiry = respond.EXPIRY_OPTIONS.get(r.get("expiry"), "")
    return (f'<div class="hc-status done">✓ Dismissed: {esc(r.get("reason", ""))}{ref}{who}'
            f'<span class="hc-muted"> · expires: {esc(expiry)}</span></div>')


def outgoing_box(rv: dict | None) -> str:
    if not rv:
        return ""
    choice = review.CHOICES.get(rv.get("choice"), "")
    comment = f": {esc(rv['comment'])}" if rv.get("comment") else ""
    return (f'<div class="hc-quiet"><span class="who">Outgoing engineer · {esc(rv.get("name", ""))} · '
            f'{esc(state.short_time(rv.get("at", "")))}</span>“{esc(choice)}”{comment}</div>')


def dismiss_form(result, item) -> None:
    shift_id, asset = result.shift.id, item.asset_id
    with st.form(key=f"dismiss-form-{shift_id}-{asset}"):
        reason = st.selectbox("Reason", respond.DISMISS_REASONS, key=f"reason-{shift_id}-{asset}")
        reference = st.text_input("Reference (optional)", placeholder="e.g. WO-1195", key=f"ref-{shift_id}-{asset}")
        note = st.text_input("Note", key=f"note-{shift_id}-{asset}")
        expiry = st.radio("Expires", list(respond.EXPIRY_OPTIONS), format_func=respond.EXPIRY_OPTIONS.get,
                          index=1, horizontal=True, key=f"expiry-{shift_id}-{asset}")
        saved = st.form_submit_button("Save dismissal", type="primary")
    if saved:
        if _need_name(shift_id):
            st.rerun()
        try:
            respond.dismiss(shift_id, result.shift.handover, item.finding, _name(shift_id), reason,
                            reference=reference, note=note, expiry=expiry)
        except ValueError as e:
            st.error(str(e).capitalize() + ".")
            return
        st.session_state["open_form"] = None
        _changed()
        st.rerun()


def card(result, n: int, item, locked: bool) -> None:
    shift, f = result.shift, item.finding
    ex = result.explanations[item.asset_id]
    r = result.responses.get(item.asset_id)
    due_text, overdue = due_label(f.due_by, shift.handover)

    with st.container(border=True):
        due_html = f'<span class="hc-due{" overdue" if overdue else ""}">{esc(due_text)}</span>' if due_text else ""
        show(f'<div class="hc-toprow"><div>{reason_chips(item)}</div>{due_html}</div>')
        show(f'<div class="hc-card-head"><span class="hc-num">{n}</span>'
             f'<span class="hc-headline">{esc(ex["headline"])}</span></div>')
        if item.dismissal_status == "now_worse":
            show(f'<div class="hc-worse"><b>Dismissed earlier, now worse.</b> '
                 f'{esc(respond.dismissal_line(item.dismissal))} · {esc(item.dismissal_detail)}</div>')
        show(f'<div class="hc-action">{esc(ex["action"])}</div>')
        show('<ul class="hc-bullets">' + "".join(f"<li>{esc(b)}</li>" for b in ex["bullets"]) + "</ul>")
        show(outgoing_box(item.review))

        with st.expander("Evidence"):
            rows = evidence_rows(item, ex["citations"])
            if rows:
                show(evidence_table(rows))
            chart = reading_chart(f, shift)
            if chart is not None:
                st.plotly_chart(chart, config=PLOTLY_CONFIG, key=f"chart-{shift.id}-{item.asset_id}")
            steps = " → ".join(f"{effect} {label}" for label, effect in item.breakdown[1:])
            base = item.breakdown[0][1]
            show(f'<div class="hc-muted">Score {item.score:g} (base {esc(base)}'
                 f'{" → " + esc(steps) if steps else ""}). Text written by: {esc(ex["source"])}.</div>')

        show(response_status(r))
        cols = st.columns(3)
        cols[0].button("Got it", key=f"got-{shift.id}-{item.asset_id}", on_click=on_got_it,
                       args=(shift.id, item.asset_id), disabled=locked, width="stretch",
                       type="primary" if not r else "secondary")
        cols[1].button("Dismiss with reason", key=f"dis-{shift.id}-{item.asset_id}", on_click=on_dismiss_open,
                       args=(shift.id, item.asset_id), disabled=locked, width="stretch")
        if f.no_open_ticket:
            cols[2].button("Draft ticket", key=f"draft-{shift.id}-{item.asset_id}", on_click=on_draft,
                           args=(shift.id, item.asset_id), disabled=locked, width="stretch")

        open_form = st.session_state.get("open_form")
        if not locked and open_form == (shift.id, item.asset_id, "dismiss"):
            dismiss_form(result, item)
        if open_form == (shift.id, item.asset_id, "draft"):
            text = respond.draft_ticket(item, ex["headline"], evidence_rows(item, ex["citations"]),
                                        shift.label, _name(shift.id))
            st.caption("Copy this into your ticketing system:")
            st.code(text, language=None)


def html_table(headers: list[str], rows: list, plain_first: bool = False) -> str:
    """A small table that wraps long text (st.dataframe would cut it off)."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    cls = "hc-ev plain" if plain_first else "hc-ev"
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def evidence_table(rows: list[tuple[str, str, str]]) -> str:
    return html_table(["Time", "Source", "What"], rows)


def context_line(f) -> str:
    if f.repeats:
        latest = f.alerts.iloc[-1]
        text = f"Latest alert {latest['time']}: {latest['message']}"
    elif len(f.notes):
        text = f"Note {f.notes.iloc[-1]['time']}: {f.notes.iloc[-1]['text']}"
    else:
        text = "No alerts or notes this shift"
    live = f.active_tickets
    if len(live):
        t = live.iloc[0]
        due = t["due"].strftime("%a %d %b") if pd.notna(t["due"]) else "not set"
        text += f" · {t['id']} {t['status']}, due {due}"
    elif len(f.tickets):
        t = f.tickets.iloc[0]
        text += f" · {t['id']} {t['status']}"
    return text


def lists_below(result) -> None:
    if result.carried:
        st.subheader("Carried over from last handover")
        rows = []
        for item in result.carried:
            headline = result.explanations[item.asset_id]["headline"].removeprefix(f"{item.asset_id}: ")
            rows.append(f'<div class="hc-row"><b>{esc(item.asset_id)}</b> · {esc(headline)}'
                        f'<div class="hc-quiet">Previously dismissed: {esc(respond.dismissal_line(item.dismissal))}'
                        f'</div>{outgoing_box(item.review)}</div>')
        show("".join(rows))
        st.caption("Still dismissed, and no worse than when it was dismissed. "
                   "It comes back to the top list if it gets worse.")

    with st.expander(f"Checked, not urgent ({len(result.not_urgent)} items)", expanded=False):
        rows = [(i.asset_id, i.finding.asset_type or "not in asset list", context_line(i.finding))
                for i in result.not_urgent]
        show(html_table(["Asset", "What it is", "What we saw"], rows, plain_first=True))


def sign_off_section(result, signed: dict | None) -> None:
    st.subheader("Handover record")
    shift = result.shift
    if signed:
        show(f'<div class="hc-banner done">Signed off by <b>{esc(signed["signed_off_by"])}</b> at '
             f'{esc(state.short_time(signed["signed_off_at"]))}. This handover is now read-only.</div>')
        st.download_button("Download printable record (HTML)", data=record.to_html(signed),
                           file_name=f"handover-record-{shift.id}.html", mime="text/html",
                           key=f"download-{shift.id}")
        with st.expander("View record"):
            show(html_table(
                ["#", "Asset", "Action", "Outgoing comment", "Response", "Reason", "By", "When"],
                [(i["rank"], i["asset"], i["action"], i["outgoing_comment"], i["response"], i["reason"],
                  i["responder"], state.short_time(i["response_time"])) for i in signed["items"]],
                plain_first=True))
            carried = signed.get("carried_over", [])
            if carried:
                st.caption("Carried over from last handover: " + ", ".join(i["asset"] for i in carried))
            st.caption("Checked, not urgent: " + ", ".join(i["asset"] for i in signed["not_urgent"]))
        return

    ready = respond.all_responded(result.top, result.responses)
    # No widget key: the default follows the Incoming engineer field until someone types here.
    signer = st.text_input("Signed off by (your name)", value=_name(shift.id))
    if not ready:
        st.caption(f"Respond to every item first ({result.responded_count} of {len(result.top)} done).")
    if st.button("Sign off handover", key=f"signoff-{shift.id}", type="primary",
                 disabled=not ready or not signer.strip()):
        try:
            record.sign_off(result, signer, incoming=_name(shift.id))
        except ValueError as e:  # e.g. someone else signed off a moment ago
            st.session_state["flash"] = str(e).capitalize() + "."
        _changed()
        st.rerun()


def render(result) -> None:
    shift = result.shift
    ev = result.evaluation
    signed = record.latest(shift.id)

    badge = ""
    if ev:
        tip = f"{ev['same_position']}/{ev['out_of']} in the same position"
        badge = f'<span class="hc-badge" title="{esc(tip)}">Matches expert ranking: {ev["matches"]}/{ev["out_of"]}</span>'
    show(f'<div class="hc-header"><h1>Handover Check: {esc(shift.title)}</h1>{badge}</div>')
    show(f'<div class="hc-sub">Outgoing: {esc(result.pack.outgoing_engineer)} · shift {shift.start:%a %H:%M} '
         f'to {shift.handover:%a %H:%M}. Plain rules rank the items; you confirm each one.</div>')

    if result.review_items and not result.review_complete:
        show('<div class="hc-banner"><b>Outgoing review not completed.</b> '
             'The outgoing engineer hasn\'t said yet whether the flagged items are real issues.</div>')
    if message := st.session_state.pop("flash", None):
        st.info(message)
    for warning in result.warnings:
        st.info(warning)

    st.plotly_chart(timeline(result), config=PLOTLY_CONFIG, key=f"timeline-{shift.id}")

    left, right = st.columns([2, 3], gap="large")
    with left:
        notes_column(result)
    with right:
        st.subheader("Needs you first")
        show(f'<div class="hc-progress">{result.responded_count} of {len(result.top)} responded</div>')
        show(key_line())
        for n, item in enumerate(result.top, start=1):
            card(result, n, item, locked=bool(signed))
        lists_below(result)
        sign_off_section(result, signed)
