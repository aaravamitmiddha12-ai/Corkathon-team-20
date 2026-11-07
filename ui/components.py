"""Small shared pieces for the Streamlit screens: CSS, tags, safe HTML."""

import html

import streamlit as st

from src.score import REASON_LABELS

# Tag colours: (text, background). Fixed pairs, so they read the same in light and dark themes.
# Amber is reserved for "Notes say OK, data disagrees" everywhere in the app.
TAG_STYLE = {
    "clash": ("#6b4100", "#ffe1a1"),                # amber: notes vs data (only use of amber)
    "no_open_ticket": ("#8f1d1d", "#fbd5d5"),       # red: nobody owns it
    "trend_worsening": ("#8a3412", "#fed7c3"),      # orange: getting worse
    "near_limit": ("#5b21b6", "#ede9fe"),           # violet: close to a limit
    "due_soon": ("#1c4f95", "#d6e6fb"),             # blue: a deadline
    "outgoing_real_issue": ("#1f2937", "#d9dde3"),  # slate: the outgoing engineer flagged it
    "unacknowledged_latest": ("#3f3f3c", "#e6e5e0"),
    "repeated": ("#3f3f3c", "#e6e5e0"),
}
MAX_TAGS = 3

CSS = """
<style>
.block-container { padding-top: 3.2rem; max-width: 1400px; }
.hc-header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 2px; }
.hc-header h1 { font-size: 1.8rem; margin: 0; padding: 0; }
.hc-badge { padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: 0.88rem;
            background: #d7f0dc; color: #14532d; border: 1px solid #9fd8ab; }
.hc-sub { opacity: 0.75; font-size: 0.92rem; margin-bottom: 10px; }
.hc-banner { padding: 8px 12px; border-radius: 8px; font-size: 0.9rem; margin: 6px 0 10px 0;
             background: rgba(91, 107, 132, 0.12); border-left: 3px solid #5b6b84; }
.hc-banner.done { background: rgba(21, 128, 61, 0.10); border-left-color: #15803d; }
.hc-note { padding: 7px 10px; border-radius: 6px; margin-bottom: 4px; font-size: 0.93rem;
           line-height: 1.45; border-left: 3px solid transparent; }
.hc-note.clash { background: rgba(245, 166, 35, 0.18); border-left-color: #f5a623; }
.hc-time { font-family: ui-monospace, Menlo, Consolas, monospace; opacity: 0.65; margin-right: 8px; }
.hc-asset { font-size: 0.72rem; opacity: 0.6; margin-left: 6px; white-space: nowrap; }
.hc-chip { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 0.76rem;
           font-weight: 600; margin: 0 5px 5px 0; white-space: nowrap; }
.hc-key { font-size: 0.8rem; opacity: 0.9; margin: 2px 0 10px 0; line-height: 1.9; }
.hc-progress { font-size: 0.95rem; font-weight: 600; margin: 0 0 4px 0; }
.hc-toprow { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.hc-due { font-size: 0.85rem; opacity: 0.8; white-space: nowrap; }
.hc-due.overdue { color: #c62828; font-weight: 700; opacity: 1; }
.hc-card-head { display: flex; align-items: baseline; gap: 10px; margin: 2px 0 6px 0; }
.hc-num { font-size: 1.35rem; font-weight: 700; opacity: 0.55; min-width: 1.2em; }
.hc-headline { font-size: 1.12rem; font-weight: 650; flex: 1; }
.hc-action { margin: 2px 0 4px 0; line-height: 1.5; font-weight: 700; }
.hc-bullets { margin: 0 0 6px 0; padding-left: 1.2rem; line-height: 1.5; }
.hc-bullets li { margin-bottom: 1px; }
.hc-quiet { padding: 7px 10px; border-radius: 6px; font-size: 0.88rem; margin: 6px 0;
            background: rgba(128, 128, 128, 0.12); line-height: 1.45; }
.hc-quiet .who { font-size: 0.78rem; opacity: 0.75; display: block; margin-bottom: 2px; }
.hc-worse { padding: 7px 10px; border-radius: 6px; font-size: 0.88rem; margin: 6px 0;
            background: rgba(198, 40, 40, 0.10); border-left: 3px solid #c62828; }
.hc-status { font-size: 0.88rem; font-weight: 600; margin: 4px 0; }
.hc-status.done { color: #15803d; }
.hc-muted { opacity: 0.7; font-size: 0.82rem; }
.hc-row { padding: 6px 0; border-bottom: 1px solid rgba(128, 128, 128, 0.2); font-size: 0.92rem; }
.hc-row:last-child { border-bottom: none; }
.hc-ev { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 2px 0 10px 0; }
.hc-ev th, .hc-ev td { text-align: left; vertical-align: top; padding: 5px 8px;
                       border-bottom: 1px solid rgba(128, 128, 128, 0.22); }
.hc-ev th { font-weight: 600; opacity: 0.75; }
.hc-ev td:first-child { font-family: ui-monospace, Menlo, Consolas, monospace; white-space: nowrap; }
.hc-ev td:nth-child(2) { white-space: nowrap; }
.hc-side { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 700px) { .hc-side { grid-template-columns: 1fr; } }
.hc-side h4 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.7; margin: 0 0 4px 0; }
</style>
"""


def esc(text) -> str:
    return html.escape(str(text))


def show(html_text: str) -> None:
    """Render HTML on one line, so Markdown never rewrites the text inside it."""
    st.markdown(html_text.replace("\n", " "), unsafe_allow_html=True)


def chip(label: str, style_key: str) -> str:
    fg, bg = TAG_STYLE.get(style_key, ("#3f3f3c", "#e6e5e0"))
    return f'<span class="hc-chip" style="color:{fg};background:{bg}">{esc(label)}</span>'


def reason_chips(item, limit: int = MAX_TAGS) -> str:
    chips = []
    for reason in item.reasons[:limit]:
        label = f"{item.finding.repeats} alerts" if reason == "repeated" else REASON_LABELS[reason]
        chips.append(chip(label, reason))
    return "".join(chips)


def key_line() -> str:
    parts = [
        chip("Notes say OK, data disagrees", "clash"),
        chip("No ticket", "no_open_ticket"),
        chip("Getting worse", "trend_worsening"),
        chip("Close to alarm limit", "near_limit"),
        chip("Due soon", "due_soon"),
        chip("Outgoing: real issue", "outgoing_real_issue"),
        chip("Other facts", "repeated"),
    ]
    return f'<div class="hc-key"><b>Key:</b> {"".join(parts)}</div>'
