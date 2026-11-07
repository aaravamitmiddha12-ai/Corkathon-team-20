"""Handover Check: one screen for the 07:00 shift handover.

    streamlit run app.py
"""

import html

import altair as alt
import pandas as pd
import streamlit as st

from src import llm
from src.detect import parse_limit, parse_value
from src.load import fmt_time
from src.pipeline import run
from src.score import REASON_LABELS, WEIGHTS

st.set_page_config(page_title="Handover Check", page_icon="🔁", layout="wide")

# Tag colours: (text, background). Fixed pairs, so they read the same in light and dark themes.
TAG_STYLE = {
    "clash": ("#7a4a00", "#ffe7b0"),            # amber: notes vs data
    "no_open_ticket": ("#8f1d1d", "#fbd5d5"),   # red: nobody owns it
    "trend_worsening": ("#8a3412", "#fed7c3"),  # orange: getting worse
    "near_limit": ("#8a3412", "#fde6d8"),
    "due_today": ("#1c4f95", "#d6e6fb"),        # blue: a deadline
    "unacknowledged_latest": ("#3f3f3c", "#e6e5e0"),
    "repeated": ("#3f3f3c", "#e6e5e0"),
}
READING_COLOUR = "#2a78d6"
LIMIT_COLOUR = "#d03b3b"

st.markdown(
    """
<style>
.block-container { padding-top: 3.5rem; max-width: 1400px; }
.hc-header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 2px; }
.hc-header h1 { font-size: 1.9rem; margin: 0; padding: 0; }
.hc-badge { padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: 0.9rem;
            background: #d7f0dc; color: #14532d; border: 1px solid #9fd8ab; }
.hc-badge.partial { background: #ffe7b0; color: #7a4a00; border-color: #f5c55a; }
.hc-sub { opacity: 0.75; font-size: 0.92rem; margin-bottom: 18px; }
.hc-note { padding: 7px 10px; border-radius: 6px; margin-bottom: 4px; font-size: 0.93rem;
           line-height: 1.45; border-left: 3px solid transparent; }
.hc-note.clash { background: rgba(245, 166, 35, 0.18); border-left-color: #f5a623; }
.hc-time { font-family: ui-monospace, Menlo, Consolas, monospace; opacity: 0.65; margin-right: 8px; }
.hc-asset { font-size: 0.72rem; opacity: 0.6; margin-left: 6px; white-space: nowrap; }
.hc-chip { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 0.76rem;
           font-weight: 600; margin: 0 5px 5px 0; white-space: nowrap; }
.hc-card-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px; }
.hc-num { font-size: 1.35rem; font-weight: 700; opacity: 0.55; min-width: 1.2em; }
.hc-headline { font-size: 1.12rem; font-weight: 650; flex: 1; }
.hc-state { font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
.hc-state.done { color: #15803d; }
.hc-state.moved { color: #1c5cab; }
.hc-why { margin: 4px 0 6px 0; line-height: 1.5; }
.hc-action { margin-bottom: 4px; line-height: 1.5; }
.hc-ev { font-size: 0.88rem; line-height: 1.5; margin-bottom: 3px; }
.hc-ev-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: 600; margin-right: 6px; }
.hc-muted { opacity: 0.7; font-size: 0.85rem; }
</style>
""",
    unsafe_allow_html=True,
)


def esc(text) -> str:
    return html.escape(str(text))


def show(html_text: str) -> None:
    """Render one line of HTML. Keeping it on one line stops Markdown from touching the text."""
    st.markdown(html_text.replace("\n", " "), unsafe_allow_html=True)


def chip(label: str, style_key: str) -> str:
    fg, bg = TAG_STYLE.get(style_key, ("#3f3f3c", "#e6e5e0"))
    return f'<span class="hc-chip" style="color:{fg};background:{bg}">{esc(label)}</span>'


def reason_chip(reason: str, finding) -> str:
    label = REASON_LABELS[reason]
    if reason == "repeated":
        label = f"{finding.repeats} alerts"
    return chip(label, reason)


# ---------- state for "Got it" / "Reassign" ----------

st.session_state.setdefault("ack", {})
st.session_state.setdefault("reassigned", {})


def toggle(kind: str, asset_id: str) -> None:
    st.session_state[kind][asset_id] = not st.session_state[kind].get(asset_id, False)


# ---------- sidebar controls ----------

with st.sidebar:
    use_llm = st.toggle(
        "Use live LLM",
        value=False,
        help="Off = demo mode: cached LLM answers if present, otherwise manual tags and template text. "
             "Never calls the API.",
    )
    st.caption(f"Model: `{llm.model_name()}`" if use_llm else "Demo mode: offline, no API calls.")

mode = "llm" if use_llm else "demo"
# Keep the result for this browser session, so clicking "Got it" doesn't re-run the LLM.
if st.session_state.get("result_mode") != mode:
    with st.spinner("Asking the LLM (results are cached after the first run)..." if use_llm else "Loading..."):
        st.session_state["result"] = run(mode=mode)
        st.session_state["result_mode"] = mode
result = st.session_state["result"]

ev = result.evaluation
ack = st.session_state["ack"]
moved = st.session_state["reassigned"]

# ---------- header ----------

badge_class = "hc-badge" if ev["matches"] == ev["out_of"] else "hc-badge partial"
badge_tip = (f"{ev['same_position']}/{ev['out_of']} in the same position; "
             f"rank agreement {ev['spearman']:.2f} (1.00 = identical order)" if ev["spearman"] is not None else "")
confirmed = sum(bool(ack.get(i.asset_id)) for i in result.top)
show(f'<div class="hc-header"><h1>Handover Check: Sat 7 Nov, 07:00 handover</h1>'
     f'<span class="{badge_class}" title="{esc(badge_tip)}">Matches expert ranking: {ev["matches"]}/{ev["out_of"]}</span></div>')
show(f'<div class="hc-sub">Night shift Fri 6 Nov 19:00 to Sat 7 Nov 07:00. '
     f'Plain rules rank the items; the LLM only tags notes and writes sentences; you confirm. '
     f'Confirmed: {confirmed}/{len(result.top)}.</div>')

for warning in result.warnings:
    st.info(warning)

left, right = st.columns([2, 3], gap="large")

# ---------- left: the notes ----------

with left:
    st.subheader("What the notes say")
    for _, note in result.notes.iterrows():
        asset = note["asset_id"]
        finding = result.findings.get(asset) if isinstance(asset, str) else None
        is_clash = bool(finding and note["time"] in finding.clash_note_times)
        tag = chip("data disagrees", "clash") if is_clash else ""
        asset_label = f'<span class="hc-asset">{esc(asset)}</span>' if isinstance(asset, str) else ""
        show(f'<div class="hc-note{" clash" if is_clash else ""}"><span class="hc-time">{esc(note["time"])}</span>'
             f'{esc(note["text"])} {tag}{asset_label}</div>')
    sources = sorted(set(result.notes["tag_source"]))
    st.caption(f"Note tags from: {', '.join(sources)}. Amber = the note sounded fine, "
               f"but a medium or high alert came after it.")


# ---------- right: the top 5 ----------

def evidence_lines(item, explanation: dict) -> list[str]:
    f = item.finding
    cited = set(explanation["citations"])
    lines = []
    for _, a in f.alerts.iterrows():
        if f"alert {a['time']}" in cited:
            who = f"ack {esc(a['acknowledged_by'])}" if a["acknowledged_by"] else "<b>not acknowledged</b>"
            lines.append(f'<span class="hc-ev-id">alert {esc(a["time"])}</span>{esc(a["severity"])} · '
                         f'{esc(a["message"])} · {who}')
    for _, n in f.notes.iterrows():
        if f"note {n['time']}" in cited:
            lines.append(f'<span class="hc-ev-id">note {esc(n["time"])}</span>"{esc(n["text"])}"')
    for _, t in f.tickets.iterrows():
        if t["id"] in cited:
            lines.append(f'<span class="hc-ev-id">{esc(t["id"])}</span>{esc(t["priority"])} {esc(t["status"])}, '
                         f'due {fmt_time(t["due"], "%a %d %b %H:%M") or "not set"} · '
                         f'{esc(t["assignee"])} · {esc(t["summary"])}')
    return lines


with right:
    st.subheader("What needs you first")
    for n, item in enumerate(result.top, start=1):
        f = item.finding
        ex = result.explanations[item.asset_id]
        done, reassigned = ack.get(item.asset_id, False), moved.get(item.asset_id, False)

        with st.container(border=True):
            state = ""
            if done:
                state += '<span class="hc-state done">✓ Got it</span>'
            if reassigned:
                state += '<span class="hc-state moved">↪ Reassigned</span>'
            show(f'<div class="hc-card-head"><span class="hc-num">{n}</span>'
                 f'<span class="hc-headline">{esc(ex["headline"])}</span>{state}</div>')
            show("<div>" + "".join(reason_chip(r, f) for r in item.reasons) + "</div>")
            show(f'<div class="hc-why">{esc(ex["why"])}</div>')
            show(f'<div class="hc-action"><b>{esc(ex["action"])}</b></div>')

            with st.expander("Evidence"):
                for line in evidence_lines(item, ex):
                    show(f'<div class="hc-ev">{line}</div>')
                (base_label, base_value), *steps = item.breakdown
                parts = [f"base {base_value} ({base_label.removeprefix('base: ')})"]
                parts += [f"{effect} {label}" for label, effect in steps]
                show(f'<div class="hc-muted" style="margin-top:8px">Score: {esc(" → ".join(parts))} '
                     f'= <b>{item.score:g}</b>. Text written by: {esc(ex["source"])}.</div>')

            b1, b2, _ = st.columns([1, 1, 2])
            b1.button("Undo" if done else "Got it", key=f"ack-{item.asset_id}",
                      on_click=toggle, args=("ack", item.asset_id), type="secondary" if done else "primary",
                      width="stretch")
            b2.button("Undo reassign" if reassigned else "Reassign", key=f"move-{item.asset_id}",
                      on_click=toggle, args=("reassigned", item.asset_id), width="stretch")


# ---------- below: everything else ----------

def context_line(f) -> str:
    if f.repeats:
        latest = f.alerts.iloc[-1]
        text = f"Latest alert {latest['time']}: {latest['message']}"
    else:
        text = "No alerts this shift"
    live = f.active_tickets
    if len(live):
        t = live.iloc[0]
        text += f" · {t['id']} {t['status']}, due {fmt_time(t['due'], '%d %b') or 'not set'}"
    elif len(f.tickets):
        t = f.tickets.iloc[0]
        text += f" · {t['id']} {t['status']}"
    return text


with st.expander(f"Checked, not urgent ({len(result.rest)} items)", expanded=False):
    rows = [
        {
            "Asset": i.asset_id,
            "What it is": i.finding.asset_type or "not in asset list",
            "Score": i.score,
            "Flags": ", ".join(REASON_LABELS[r] for r in i.reasons) or "none",
            "What we saw": context_line(i.finding),
        }
        for i in result.rest
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------- sidebar: sparklines + how it ranks ----------

def sparkline(f) -> alt.Chart | None:
    a = f.alerts.assign(reading=f.alerts["message"].map(parse_value)).dropna(subset=["reading"])
    if len(a) < 2:
        return None
    base = alt.Chart(a)
    line = base.mark_line(color=READING_COLOUR, strokeWidth=2).encode(
        x=alt.X("timestamp:T", axis=alt.Axis(title=None, format="%H:%M", labelAngle=0, tickCount=3, grid=False)),
        y=alt.Y("reading:Q", axis=alt.Axis(title=None, tickCount=3), scale=alt.Scale(zero=False)),
    )
    points = base.mark_point(color=READING_COLOUR, filled=True, size=60).encode(
        x="timestamp:T", y="reading:Q",
        tooltip=[alt.Tooltip("time:N", title="Time"), alt.Tooltip("reading:Q", title="Reading"),
                 alt.Tooltip("severity:N", title="Severity")],
    )
    layers = [line, points]
    limit = parse_limit(a.iloc[-1]["message"])
    if limit is not None:
        rule = alt.Chart(pd.DataFrame({"limit": [limit]})).mark_rule(
            color=LIMIT_COLOUR, strokeDash=[4, 3], strokeWidth=1.5
        ).encode(y="limit:Q", tooltip=[alt.Tooltip("limit:Q", title="Alarm limit")])
        layers.append(rule)
    return alt.layer(*layers).properties(height=110)


with st.sidebar:
    st.divider()
    st.subheader("Alert readings")
    st.caption("Top items with numeric readings. Dashed red line = alarm limit.")
    for item in result.top:
        chart = sparkline(item.finding)
        if chart is not None:
            st.markdown(f"**{item.asset_id}** · {item.finding.alerts.iloc[-1]['message'].split(' ')[0].lower()}")
            st.altair_chart(chart, width="stretch")

    st.divider()
    with st.expander("How the ranking works"):
        st.markdown(
            "**base** = criticality × severity × (1 + 0.5 × (alerts − 1))  \n"
            f"× {WEIGHTS['trend_worsening_multiplier']} if getting worse  \n"
            f"+{WEIGHTS['clash']} notes say OK, data disagrees  \n"
            f"+{WEIGHTS['no_open_ticket']} no ticket  \n"
            f"+{WEIGHTS['due_today']} due today  \n"
            f"+{WEIGHTS['near_limit']} close to alarm limit  \n"
            f"+{WEIGHTS['unacknowledged_latest']} latest alert not acknowledged  \n\n"
            "Weights live in `src/score.py`. The LLM never changes the score."
        )
