"""Home screen: ranked handover (feature 1), notes vs data (2), respond (4), sign-off (5)."""

import pandas as pd
import streamlit as st

from src import record, respond, review, state
from src.charts import OTHER_ROW, ROW_HEIGHT, TIMELINE_TOP, reading_chart, timeline
from src.due import due_label
from src.explain import evidence_rows
from ui.components import (EASE, chip, esc, eyebrow, heading, heading_words, key_line, limit_bar, nav_state_rules, progress_caption,
                           progress_segments, reason_chips,
                           short_name, show, slug)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

# Plotly can't link a row to an anchor or highlight one without redrawing, so the chart borrows the HTML label
# at the same height: a click follows it, and hover or keyboard focus on either side lights up the label and the
# band behind that chart row. Every listener is on the document, once, and looks the rows up each time, so
# Streamlit re-rendering or Plotly redrawing can't double them up or leave them on old elements.
TIMELINE_SCRIPT = r"""<script>
(function () {
  if (window.batonTimelineBound) return;
  window.batonTimelineBound = true;
  var root = ".st-key-baton-timeline ", hovered = -1;

  function labels() { return Array.prototype.slice.call(document.querySelectorAll(root + ".baton-tl-label")); }

  function rowAt(y) {
    return labels().findIndex(function (label) {
      var box = label.getBoundingClientRect();
      return y >= box.top && y < box.bottom;
    });
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  function translateOf(el) {
    var m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(el.getAttribute("transform") || "");
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : null;
  }

  // The chart's marks for one row: the others dim, these grow a little. Rows are numbered like the labels.
  function markRow(row) {
    var box = document.querySelector(".st-key-baton-timeline"), gd = box && box.querySelector(".js-plotly-plot");
    var ya = gd && gd._fullLayout && gd._fullLayout.yaxis;
    if (!box || !ya) return;
    if (row < 0) box.removeAttribute("data-baton-hot"); else box.setAttribute("data-baton-hot", row);
    box.querySelectorAll(".scatterlayer .point").forEach(function (p) {
      var at = translateOf(p), on = row >= 0 && at && Math.round(ya.p2l(at[1])) === row;
      if (on) p.setAttribute("data-baton-row-hot", ""); else p.removeAttribute("data-baton-row-hot");
      p.style.transform = on && !reduce.matches ? "translate(" + at[0] + "px," + at[1] + "px) scale(1.3)" : "";
    });
    box.querySelectorAll(".barlayer .point").forEach(function (b) {
      var r = b.getBBox(), on = row >= 0 && Math.round(ya.p2l(r.y + r.height / 2)) === row;
      if (on) b.setAttribute("data-baton-row-hot", ""); else b.removeAttribute("data-baton-row-hot");
    });
  }

  var lastHot = -1;
  function paint() {
    var rows = labels(), bands = document.querySelectorAll(root + ".baton-tl-band"), active = document.activeElement;
    var focused = active && active.matches && active.matches("a.baton-tl-label:focus-visible") ? rows.indexOf(active) : -1;
    var hotRow = hovered >= 0 ? hovered : focused;
    rows.forEach(function (label, i) {
      var hot = i === hovered || i === focused;
      label.classList.toggle("baton-tl-hot", hot);
      if (bands[i]) bands[i].classList.toggle("baton-tl-hot", hot);
    });
    if (hotRow !== lastHot) { lastHot = hotRow; markRow(hotRow); }
  }

  // A note's own mark on the chart (a diamond: drawn without arcs, unlike the round alerts) pulses once.
  function pulse(note) {
    var box = document.querySelector(".st-key-baton-timeline"), gd = box && box.querySelector(".js-plotly-plot");
    var lay = gd && gd._fullLayout, slug = note.getAttribute("data-slug"), time = note.getAttribute("data-time");
    if (!lay || !slug || !time || reduce.matches) return;
    var rows = labels(), row = rows.findIndex(function (l) { return l.getAttribute("href") === "#card-" + slug; });
    if (row < 0) row = rows.length - 1;  // not a top item: the "Other" row
    box.querySelectorAll(".scatterlayer .point").forEach(function (p) {
      var at = translateOf(p);
      if (!at || /A/.test(p.getAttribute("d") || "") || Math.round(lay.yaxis.p2l(at[1])) !== row) return;
      var t = new Date(Math.round(lay.xaxis.p2l(at[0]) / 60000) * 60000);
      var hhmm = ("0" + t.getUTCHours()).slice(-2) + ":" + ("0" + t.getUTCMinutes()).slice(-2);
      if (hhmm !== time || !p.animate) return;
      var base = "translate(" + at[0] + "px," + at[1] + "px)";
      p.animate([{ transform: base + " scale(1)" }, { transform: base + " scale(1.9)" }, { transform: base + " scale(1)" }],
                { duration: 320, easing: "ease-out" });
    });
  }
  document.addEventListener("pointerover", function (e) {
    var note = e.target && e.target.closest ? e.target.closest(".hc-note") : null;
    if (note && e.pointerType !== "touch" && !(e.relatedTarget && note.contains(e.relatedTarget))) pulse(note);
  });
  document.addEventListener("focusin", function (e) {
    if (e.target && e.target.matches && e.target.matches(".hc-note:focus-visible")) pulse(e.target);
  });

  function track(e) {
    var row = -1, target = e.target;
    if (e.pointerType !== "touch" && target && target.closest) {
      var label = target.closest(root + ".baton-tl-label");
      if (label) row = labels().indexOf(label);
      else if (target.closest(root + ".js-plotly-plot")) row = rowAt(e.clientY);
    }
    if (row !== hovered || row !== -1) { hovered = row; paint(); }
  }

  document.addEventListener("pointermove", track, true);
  document.addEventListener("pointerover", track, true);
  document.documentElement.addEventListener("pointerleave", function () { hovered = -1; paint(); });
  document.addEventListener("focusin", paint, true);
  document.addEventListener("focusout", function () { setTimeout(paint); }, true);
  document.addEventListener("click", function (e) {
    if (!e.target.closest || !e.target.closest(root + ".js-plotly-plot")) return;
    var label = labels()[rowAt(e.clientY)];
    if (label && label.matches("a")) label.click();
  });
})();
</script>"""


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


def _reopened() -> set:
    """Handled cards the viewer has opened again. Only for this browser session; nothing is saved."""
    return st.session_state.setdefault("reopened", set())


def _responded(shift_id: str, asset: str) -> None:
    _reopened().discard((shift_id, asset))
    st.session_state["just_changed"] = asset  # this item alone animates on the next render
    _changed()


def on_got_it(shift_id: str, asset: str) -> None:
    if _need_name(shift_id):
        return
    respond.got_it(shift_id, asset, _name(shift_id))
    st.session_state.pop("open_form", None)
    _responded(shift_id, asset)


def on_draft(shift_id: str, asset: str) -> None:
    if st.session_state.get("open_form") == (shift_id, asset, "draft"):
        st.session_state["open_form"] = None  # just closing the draft: record nothing
        st.session_state["just_changed"] = asset  # the card can collapse now
        return
    if _need_name(shift_id):
        return
    st.session_state["open_form"] = (shift_id, asset, "draft")
    if respond.ticket_drafted(shift_id, asset, _name(shift_id)):  # never overwrites a saved response
        st.session_state["just_changed"] = asset
        _changed()


def on_dismiss_open(shift_id: str, asset: str) -> None:
    current = st.session_state.get("open_form")
    st.session_state["open_form"] = None if current == (shift_id, asset, "dismiss") else (shift_id, asset, "dismiss")


def on_dismiss_save(result, item) -> None:
    shift_id, asset = result.shift.id, item.asset_id
    if _need_name(shift_id):
        return
    try:
        respond.dismiss(shift_id, result.shift.handover, item.finding, _name(shift_id),
                        st.session_state[f"reason-{shift_id}-{asset}"],
                        reference=st.session_state[f"ref-{shift_id}-{asset}"],
                        note=st.session_state[f"note-{shift_id}-{asset}"],
                        expiry=st.session_state[f"expiry-{shift_id}-{asset}"])
    except ValueError as e:
        st.session_state["dismiss_error"] = (shift_id, asset, str(e).capitalize() + ".")
        return
    st.session_state["open_form"] = None
    _responded(shift_id, asset)


def on_reopen(shift_id: str, asset: str) -> None:
    _reopened().add((shift_id, asset))


def on_collapse(shift_id: str, asset: str) -> None:
    _reopened().discard((shift_id, asset))
    st.session_state["open_form"] = None


# ---------- timeline ----------

def timeline_labels(result) -> str:
    """The row labels, as real links to each card. Same height per row as the chart beside them."""
    style = f'style="height:{ROW_HEIGHT}px"'
    labels = []
    for n, item in enumerate(result.top, start=1):
        labels.append(f'<a class="baton-tl-label" href="#card-{slug(item.asset_id)}" target="_self" {style}>'
                      f'<span class="baton-tl-rank">{n}</span><span class="baton-tl-id">{esc(item.asset_id)}</span>'
                      f'<span class="baton-tl-name">{esc(short_name(item.finding.asset_type))}</span></a>')
    top_ids = {i.asset_id for i in result.top}
    others = (set(result.pack.alerts["asset"]) | {a for a in result.notes["asset_id"] if isinstance(a, str)}) - top_ids
    labels.append(f'<div class="baton-tl-label" {style}><span class="baton-tl-id">{OTHER_ROW} ({len(others)})</span></div>')
    return f'<div style="padding-top:{TIMELINE_TOP}px">{"".join(labels)}</div>'


def timeline_bands(result) -> str:
    """An empty band behind each chart row, at the same heights as the labels, for the hover script to light up."""
    bands = "".join(f'<i class="baton-tl-band" style="top:{TIMELINE_TOP + ROW_HEIGHT * n}px;height:{ROW_HEIGHT}px"></i>'
                    for n in range(len(result.top) + 1))
    return f'<div class="baton-tl-bands">{bands}</div>'


def timeline_section(result) -> None:
    shift = result.shift
    show(eyebrow(2, "Shift at a glance"))
    show(f'<div class="baton-h3 baton-words">{heading_words(f"{shift.start:%a %H:%M} to {shift.handover:%a %H:%M}")}</div>')
    with st.container(key="baton-timeline"):
        labels, chart = st.columns([1, 3], gap=None)
        with labels:
            show(timeline_labels(result))
        with chart:
            show(timeline_bands(result))
            st.plotly_chart(timeline(result), config=PLOTLY_CONFIG, key=f"timeline-{shift.id}")
    show('<div class="baton-legend"><span><i class="dot"></i>Alert</span>'
         '<span><i class="dot after"></i>Alert after a note said it was fine</span>'
         '<span><i class="note"></i>Note written</span>'
         '<span><i class="band"></i>Said fine, kept alerting</span></div>')
    st.html(TIMELINE_SCRIPT, unsafe_allow_javascript=True)


# ---------- pieces ----------

def notes_column(result) -> None:
    show(eyebrow(4, "Notes"))
    show(heading("What the notes say"))
    for _, note in result.notes.iterrows():
        asset = note["asset_id"]
        finding = result.findings.get(asset) if isinstance(asset, str) else None
        is_clash = bool(finding and note["time"] in finding.clash_note_times)
        tag = chip("data disagrees", "clash") if is_clash else ""
        label = f'<span class="hc-asset">{esc(asset)}</span>' if isinstance(asset, str) else ""
        where = f' data-slug="{slug(asset)}" data-time="{esc(note["time"])}"' if isinstance(asset, str) else ""
        show(f'<div class="hc-note{" clash" if is_clash else ""}" tabindex="0"{where}><span class="hc-time">{esc(note["time"])}</span>'
             f'{esc(note["text"])} {tag}{label}</div>')
    show('<div class="hc-muted">Amber = the note said it was fine, but a medium or high alert came after it.</div>')


def response_status(r: dict | None) -> str:
    if not r:
        return ""
    who = f" · {esc(r.get('name', ''))} · <span class=\"baton-mono\">{esc(state.short_time(r.get('at', '')))}</span>"
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
        st.selectbox("Reason", respond.DISMISS_REASONS, key=f"reason-{shift_id}-{asset}")
        st.text_input("Reference (optional)", placeholder="e.g. WO-1195", key=f"ref-{shift_id}-{asset}")
        st.text_input("Note", key=f"note-{shift_id}-{asset}")
        st.radio("Expires", list(respond.EXPIRY_OPTIONS), format_func=respond.EXPIRY_OPTIONS.get,
                 index=1, horizontal=True, key=f"expiry-{shift_id}-{asset}")
        st.form_submit_button("Save dismissal", type="primary", on_click=on_dismiss_save, args=(result, item))
    error = st.session_state.get("dismiss_error")
    if error and error[:2] == (shift_id, asset):
        st.error(error[2])
        del st.session_state["dismiss_error"]


def slim_text(r: dict) -> str:
    """What a handled item's one-line row says it got."""
    if r["kind"] == "dismissed":
        ref = f" ({r['reference']})" if r.get("reference") else ""
        return f"Dismissed: {r.get('reason', '')}{ref}"
    return respond.RESPONSE_LABELS[r["kind"]]


def slim_row(result, item, r: dict, just_changed: str | None) -> None:
    """A handled item: one line. "Open" brings back its evidence and the way to change the response."""
    shift_id, asset = result.shift.id, item.asset_id
    animate = " baton-done" if asset == just_changed else ""
    with st.container(border=True, key=f"baton-card-{shift_id}-{slug(asset)}"):
        text, action = st.columns([6, 1], vertical_alignment="center")
        with text:
            show(f'<div id="card-{slug(asset)}" class="baton-slim{animate}"><span class="tick">✓</span> '
                 f'<b>{esc(asset)}</b> · {esc(slim_text(r))} · '
                 f'<span class="baton-mono">{esc(state.short_time(r.get("at", "")))}</span></div>')
        action.button("Open", key=f"open-{shift_id}-{asset}", on_click=on_reopen, args=(shift_id, asset),
                      type="tertiary", width="stretch")


def card(result, n: int, item, locked: bool) -> None:
    shift, f = result.shift, item.finding
    ex = result.explanations[item.asset_id]
    r = result.responses.get(item.asset_id)
    due_text, overdue = due_label(f.due_by, shift.handover)

    with st.container(border=True, key=f"baton-card-{shift.id}-{slug(item.asset_id)}"):
        due_html = f'<span class="hc-due{" overdue" if overdue else ""}">{esc(due_text)}</span>' if due_text else ""
        show(f'<div id="card-{slug(item.asset_id)}" class="hc-toprow"><div>{reason_chips(item)}</div>{due_html}</div>')
        show(f'<div class="hc-card-head"><span class="hc-num">{n}</span>'
             f'<span class="hc-headline">{esc(ex["headline"])}</span></div>')
        if item.dismissal_status == "now_worse":
            show(f'<div class="hc-worse"><b>Dismissed earlier, now worse.</b> '
                 f'{esc(respond.dismissal_line(item.dismissal))} · {esc(item.dismissal_detail)}</div>')
        show(limit_bar(f))
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

        if (shift.id, item.asset_id) in _reopened():
            st.button("Collapse", key=f"collapse-{shift.id}-{item.asset_id}", on_click=on_collapse,
                      args=(shift.id, item.asset_id), type="tertiary")


def html_table(headers: list[str], rows: list, plain_first: bool = False, id_col: int | None = None) -> str:
    """A small table that wraps long text (st.dataframe would cut it off). The id_col column holds asset ids,
    which stay whole on one line in monospace."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f'<td{" class=\"baton-id\"" if n == id_col else ""}>{esc(c)}</td>'
                                    for n, c in enumerate(row)) + "</tr>" for row in rows)
    cls = "hc-ev plain" if plain_first else "hc-ev"
    # The box scrolls sideways on its own when the columns need more room than the card has.
    return (f'<div class="baton-table-box"><table class="{cls}" style="min-width:{len(headers) * 6.5}rem">'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


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
    show(eyebrow(5, "Also checked"))
    if result.carried:
        show(heading("Carried over from last handover"))
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
        show(html_table(["Asset", "What it is", "What we saw"], rows, plain_first=True, id_col=0))


def sign_off_section(result, signed: dict | None) -> None:
    show(eyebrow(None, "Sign off"))
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
                plain_first=True, id_col=1))
            carried = signed.get("carried_over", [])
            if carried:
                st.caption("Carried over from last handover: " + ", ".join(i["asset"] for i in carried))
            st.caption("Checked, not urgent: " + ", ".join(i["asset"] for i in signed["not_urgent"]))
        return

    # No widget key: the default follows the Incoming engineer field until someone types here.
    signer = st.text_input("Signed off by (your name)", value=_name(shift.id))
    if st.button("Sign off handover", key=f"signoff-{shift.id}", type="primary", disabled=not signer.strip()):
        try:
            record.sign_off(result, signer, incoming=_name(shift.id))
        except ValueError as e:  # e.g. someone else signed off a moment ago
            st.session_state["flash"] = str(e).capitalize() + "."
        _changed()
        st.rerun()


def is_collapsed(result, item) -> bool:
    shift_id, asset = result.shift.id, item.asset_id
    if asset not in result.responses or (shift_id, asset) in _reopened():
        return False
    # A drafted ticket has to stay on screen until it has been copied.
    return st.session_state.get("open_form") not in ((shift_id, asset, "draft"), (shift_id, asset, "dismiss"))


def row_state_rules(result) -> list[str]:
    """The timeline is outside the fragment, so a response can't re-render it. These rules reach its labels by
    href instead, and are rebuilt on every render: a tick for an item with a response, plus muted while its card
    is collapsed to a slim row. The looks are in the CSS block; these only switch them on."""
    rules = []
    for item in result.top:
        if item.asset_id in result.responses:
            muted = " --baton-row-fade: 0.7; --baton-row-weight: 400;" if is_collapsed(result, item) else ""
            rules.append(f'a.baton-tl-label[href="#card-{slug(item.asset_id)}"] '
                         f'{{ --baton-tick: "✓"; --baton-rank-size: 0; --baton-rank-fade: 1;{muted} }}')
    return rules


def motion_css(result, just_changed: str | None, intro: bool, ready: bool) -> str:
    """Rules that depend on this render. The sign-off fades in when the fifth item is handled: Streamlit
    containers can't take a class, but they have a key, so the rule exists for that one render. Then the live
    state of everything outside this fragment: the timeline labels and the sidebar's dots and progress.
    (Sections reveal as they scroll into view, in the page script, so `intro` adds nothing here now.)"""
    rules = []
    if ready and just_changed:
        rules.append(f".st-key-baton-signoff {{ animation: baton-in 240ms {EASE} both; }}")
    rules += row_state_rules(result)
    rules += nav_state_rules(result.top, result.responses, strong=True)
    return f"<style>{' '.join(rules)}</style>"


@st.fragment
def responses_section(refresh) -> None:
    """The progress bar, the cards and sign-off. Responding to an item re-runs only this."""
    result = refresh()
    shift = result.shift
    signed = record.latest(shift.id)
    just_changed = st.session_state.get("just_changed")
    intro = not st.session_state.get("intro_done")
    ready = respond.all_responded(result.top, result.responses)

    show(motion_css(result, just_changed, intro, ready))
    if message := st.session_state.pop("flash", None):
        st.info(message)
    show(progress_segments(result.top, result.responses, just_changed))
    show(f'<div class="baton-progress-caption">{esc(progress_caption(result.top, result.responses))}</div>')
    show(key_line())

    for n, item in enumerate(result.top, start=1):
        if is_collapsed(result, item):
            slim_row(result, item, result.responses[item.asset_id], just_changed)
        else:
            card(result, n, item, locked=bool(signed))

    if signed or ready:
        with st.container(key="baton-signoff"):
            sign_off_section(result, signed)

    st.session_state["intro_done"] = True
    st.session_state["just_changed"] = None


def render(result, refresh) -> None:
    """Five sections, each in its own keyed container so the page script can reveal it as it scrolls in.
    The numbers match the sidebar (ui/components.py, SECTIONS)."""
    shift = result.shift

    with st.container(key="baton-sec-1"):
        show(eyebrow(1, "Start here", first=True))
        show(f'<div class="hc-header"><h1 class="baton-words">{heading_words(f"Baton · {shift.title}")}</h1></div>')
        show(f'<div class="hc-sub">From {esc(result.pack.outgoing_engineer)} · {esc(shift.id)} shift</div>')
        if result.review_items and not result.review_complete:
            show('<div class="hc-banner"><b>Outgoing review not completed.</b> '
                 'The outgoing engineer hasn\'t said yet whether the flagged items are real issues.</div>')
        for warning in result.warnings:
            st.info(warning)

    with st.container(key="baton-sec-2"):
        timeline_section(result)

    with st.container(key="baton-main"):
        first, second = st.columns([3, 2], gap="large")
    with first, st.container(key="baton-sec-3"):
        show(eyebrow(3, "Respond"))
        show(heading("Needs you first"))
        responses_section(refresh)
    with second, st.container(key="baton-sec-4"):
        notes_column(result)

    with st.container(key="baton-sec-5"):
        lists_below(result)
