"""Small shared pieces for the Streamlit screens: the one style block, tags, safe HTML."""

import html
import re

import streamlit as st

from src.detect import past_limit
from src.score import REASON_LABELS

MAX_TAGS = 3
EASE = "cubic-bezier(.2,0,0,1)"

CSS = """
<style>
.block-container { padding-top: 4.5rem; max-width: 1400px; }
html, [data-testid="stMain"] { scroll-behavior: smooth; }
/* Style-only markdown blocks take up no space in the layout. */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) { display: none; }

.hc-header h1 { font-size: 1.8rem; margin: 0; padding: 0; font-variant-numeric: tabular-nums; }
.hc-sub { opacity: 0.75; font-size: 0.92rem; margin-bottom: 10px; }
.hc-banner { padding: 8px 12px; border-radius: 8px; font-size: 0.9rem; margin: 6px 0 10px 0;
             background: rgba(128, 128, 128, 0.12); border-left: 3px solid rgba(128, 128, 128, 0.6); }
.hc-banner.done { background: rgba(21, 128, 61, 0.10); border-left-color: #15803d; }
.hc-note { padding: 7px 10px; border-radius: 6px; margin-bottom: 4px; font-size: 0.93rem;
           line-height: 1.45; border-left: 3px solid transparent; transition: background-color 150ms ease-out; }
.hc-note:hover { background: rgba(128, 128, 128, 0.12); }
.hc-note.clash { background: rgba(245, 166, 35, 0.18); border-left-color: #f5a623; }
.hc-note.clash:hover { background: rgba(245, 166, 35, 0.28); }
.hc-time, .baton-mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }
.hc-time { opacity: 0.65; margin-right: 8px; }
.hc-asset { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.72rem; opacity: 0.6;
            margin-left: 6px; white-space: nowrap; }
.hc-chip { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border-radius: 999px;
           font-size: 0.76rem; font-weight: 500; margin: 0 5px 5px 0; white-space: nowrap;
           border: 1px solid rgba(128, 128, 128, 0.5); }
.hc-chip svg { flex: none; display: block; }
.hc-chip.clash { background: #ffe1a1; color: #6b4100; border-color: #ffe1a1; font-weight: 600; }
.hc-key { font-size: 0.8rem; opacity: 0.9; margin: 2px 0 10px 0; line-height: 1.9; }
.hc-toprow { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.hc-due { font-size: 0.85rem; opacity: 0.8; white-space: nowrap; font-variant-numeric: tabular-nums; }
.hc-due.overdue { color: #c62828; font-weight: 700; opacity: 1; }
.hc-card-head { display: flex; align-items: baseline; gap: 10px; margin: 2px 0 6px 0; }
.hc-num { font-size: 1.35rem; font-weight: 700; opacity: 0.55; min-width: 1.2em;
          font-family: ui-monospace, Menlo, Consolas, monospace; }
.hc-headline { font-size: 1.12rem; font-weight: 650; flex: 1; }
.hc-action { margin: 2px 0 4px 0; line-height: 1.5; font-weight: 700; }
.hc-bullets { margin: 0 0 6px 0; padding-left: 1.2rem; line-height: 1.5; font-variant-numeric: tabular-nums; }
.hc-bullets li { margin-bottom: 1px; }
.hc-quiet { padding: 7px 10px; border-radius: 6px; font-size: 0.88rem; margin: 6px 0;
            background: rgba(128, 128, 128, 0.12); line-height: 1.45; }
.hc-quiet .who { font-size: 0.78rem; opacity: 0.75; display: block; margin-bottom: 2px; }
.hc-worse { padding: 7px 10px; border-radius: 6px; font-size: 0.88rem; margin: 6px 0;
            background: rgba(128, 128, 128, 0.12); border-left: 3px solid rgba(128, 128, 128, 0.6); }
.hc-status { font-size: 0.88rem; font-weight: 600; margin: 4px 0; font-variant-numeric: tabular-nums; }
.hc-status.done { color: #15803d; }
.hc-muted { opacity: 0.7; font-size: 0.82rem; }
.hc-row { padding: 6px 0; border-bottom: 1px solid rgba(128, 128, 128, 0.2); font-size: 0.92rem; }
.hc-row:last-child { border-bottom: none; }
.hc-ev { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 2px 0 10px 0;
         font-variant-numeric: tabular-nums; }
.hc-ev th, .hc-ev td { text-align: left; vertical-align: top; padding: 5px 8px;
                       border-bottom: 1px solid rgba(128, 128, 128, 0.22); }
.hc-ev th { font-weight: 600; opacity: 0.75; }
.hc-ev:not(.plain) td:first-child { font-family: ui-monospace, Menlo, Consolas, monospace; white-space: nowrap; }
.hc-ev:not(.plain) td:nth-child(2) { white-space: nowrap; }
.hc-ev.plain td:first-child { font-weight: 600; white-space: nowrap; }

/* ---------- timeline ---------- */
.baton-section { font-size: 0.95rem; font-weight: 600; margin: 4px 0 0 0; font-variant-numeric: tabular-nums; }
.st-key-baton-timeline [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.25rem; align-items: flex-start; }
.st-key-baton-timeline [data-testid="stColumn"] { min-width: 0; }
.st-key-baton-timeline [data-testid="stColumn"]:first-child { flex: 0 0 clamp(148px, 24%, 280px); }
.st-key-baton-timeline .nsewdrag { cursor: pointer !important; }
.baton-tl-label { display: flex; align-items: center; gap: 8px; padding-inline: 6px; border-radius: 6px;
                  font-size: 0.82rem; white-space: nowrap; overflow: hidden;
                  color: inherit !important; text-decoration: none !important;
                  transition: background-color 150ms ease-out; }
a.baton-tl-label:hover { background: rgba(128, 128, 128, 0.14); }
.baton-tl-rank { font-family: ui-monospace, Menlo, Consolas, monospace; opacity: 0.55; min-width: 1ch; }
.baton-tl-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: 600; }
.baton-tl-name { opacity: 0.7; overflow: hidden; text-overflow: ellipsis; }
.baton-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 0.8rem; opacity: 0.85; margin: 0 0 12px 0; }
.baton-legend span { display: inline-flex; align-items: center; gap: 6px; }
.baton-legend i { display: block; flex: none; }
.baton-legend .dot { width: 10px; height: 10px; border-radius: 50%; background: #8a8984; }
.baton-legend .dot.after { background: #f5a623; }
.baton-legend .note { width: 8px; height: 8px; background: #5b6b84; transform: rotate(45deg); }
.baton-legend .band { width: 22px; height: 10px; border-radius: 4px; background: rgba(245, 166, 35, 0.28); }

/* ---------- progress ---------- */
.baton-segments { display: flex; gap: 4px; margin: 4px 0 6px 0; }
.baton-seg { flex: 1 1 0; min-width: 0; height: 28px; display: flex; align-items: center; justify-content: center;
             gap: 5px; border-radius: 6px; font: 600 0.78rem ui-monospace, Menlo, Consolas, monospace;
             background: rgba(128, 128, 128, 0.18); border: 1px solid transparent; }
.baton-seg svg { flex: none; display: block; }
.baton-seg.got_it, .baton-seg.ticket_drafted { background: #15803d; color: #ffffff; }
.baton-seg.dismissed { background: transparent; border: 1px dashed rgba(128, 128, 128, 0.8); }
.baton-progress-caption { font-size: 0.85rem; opacity: 0.85; margin-bottom: 4px; font-variant-numeric: tabular-nums; }

/* ---------- cards ---------- */
[id^="card-"] { scroll-margin-top: 4.5rem; }
div[class*="st-key-baton-card-"] { transition: border-color 150ms ease-out; }
div[class*="st-key-baton-card-"]:hover { border-color: rgba(128, 128, 128, 0.75); }
div[class*="st-key-baton-card-"]:has(.baton-slim) { padding-block: 0.35rem; }
div[class*="st-key-baton-card-"]:has(:target) { animation: baton-flash 1000ms ease-out 1; }
[data-testid="stMarkdownContainer"]:has(> .baton-slim) { margin-bottom: 0; }
div[class*="st-key-baton-card-"]:has(.baton-slim) button { min-height: 1.75rem; }
.baton-slim { font-size: 0.9rem; line-height: 1.4; font-variant-numeric: tabular-nums; }
.baton-slim b { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: 600; }
.baton-slim .tick { color: #15803d; font-weight: 700; }
.baton-limit { display: flex; align-items: center; gap: 10px; margin: 2px 0 8px 0; }
.baton-limit-track { position: relative; flex: 1; height: 6px; border-radius: 3px;
                     background: rgba(128, 128, 128, 0.22); }
.baton-limit-fill { position: absolute; inset: 0 auto 0 0; border-radius: 3px; background: #6f7078; }
.baton-limit.over .baton-limit-fill { background: #c62828; }
.baton-limit-tick { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; border-radius: 1px; }
.baton-limit-tick.warn { background: #f5a623; }
.baton-limit-tick.alarm { background: #c62828; margin-left: -2px; }
.baton-limit-text { font-family: ui-monospace, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums;
                    font-size: 0.8rem; white-space: nowrap; }
.baton-limit.over .baton-limit-text { color: #c62828; font-weight: 600; }

/* ---------- motion ---------- */
@keyframes baton-in { from { opacity: 0; transform: translateY(6px); } }
@keyframes baton-done { from { opacity: 0; transform: translateY(-4px); } }
@keyframes baton-seg-in { from { opacity: 0; } }
@keyframes baton-flash { from { outline: 2px solid #f5a623; } to { outline: 2px solid transparent; } }
.baton-enter { animation: baton-in 240ms cubic-bezier(.2,0,0,1) both; animation-delay: calc(var(--i) * 50ms); }
.baton-done { animation: baton-done 220ms cubic-bezier(.2,0,0,1) both; }
.baton-seg-new { animation: baton-seg-in 200ms ease-out both; }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
"""

# 12px line icons, drawn in the text colour. Every tag has one.
ICONS = {
    "clash": '<path d="M6 1.5 11 10.5H1zM6 5v2.5M6 9v.01"/>',
    "no_open_ticket": '<path d="M1.5 3.5h9v1.75a.75.75 0 0 0 0 1.5V8.5h-9V6.75a.75.75 0 0 0 0-1.5zM7.5 3.5v5"/>',
    "trend_worsening": '<path d="M1.5 9 5 5.5l2 2 3.5-4M7.5 3.5h3v3"/>',
    "due_soon": '<circle cx="6" cy="6" r="4.5"/><path d="M6 3.25V6l2 1.25"/>',
    "near_limit": '<path d="M1.5 9a4.5 4.5 0 0 1 9 0M6 9l2.25-3"/>',
    "outgoing_real_issue": '<circle cx="6" cy="3.75" r="2"/><path d="M2 10.5a4 4 0 0 1 8 0"/>',
    "unacknowledged_latest": '<path d="M3 8.5V5.5a3 3 0 0 1 6 0v3l1 1H2zM5 10.5h2"/>',
    "repeated": '<path d="M2 5.5a4 4 0 0 1 7-2l1.5 1.5M10.5 2v3h-3M10 6.5a4 4 0 0 1-7 2L1.5 7M1.5 10V7h3"/>',
    "tick": '<path d="M2 6.5 5 9.5 10 3"/>',
    "minus": '<path d="M2.5 6h7"/>',
}
SEGMENT_ICON = {"got_it": "tick", "dismissed": "minus", "ticket_drafted": "no_open_ticket"}
PROGRESS_WORDS = {"got_it": "got it", "dismissed": "dismissed", "ticket_drafted": "ticket drafted"}

# Short plain names for the timeline, by what the asset list says it is.
SHORT_NAMES = [("freezer", "freezer"), ("water for injection", "water loop"), ("chiller", "chiller pump"),
               ("hplc", "HPLC"), ("balance", "balance"), ("air handling", "air handler"), ("printer", "printer"),
               ("door", "door"), ("cleanroom", "cleanroom"), ("incubator", "incubator")]


def esc(text) -> str:
    return html.escape(str(text))


def show(html_text: str) -> None:
    """Render HTML on one line, so Markdown never rewrites the text inside it."""
    st.markdown(html_text.replace("\n", " "), unsafe_allow_html=True)


def slug(asset_id: str) -> str:
    """An asset id as it appears in anchors and Streamlit keys."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(asset_id))


def short_name(asset_type: str) -> str:
    lower = (asset_type or "").lower()
    return next((name for word, name in SHORT_NAMES if word in lower), lower)


def icon(name: str) -> str:
    return (f'<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def chip(label: str, style_key: str) -> str:
    """Tags are neutral outlines. Only "notes and data disagree" gets a colour."""
    cls = "hc-chip clash" if style_key == "clash" else "hc-chip"
    return f'<span class="{cls}">{icon(style_key if style_key in ICONS else "repeated")}{esc(label)}</span>'


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


# ---------- progress ----------

def progress_segments(top: list, responses: dict, just_changed: str | None = None, enter: bool = False) -> str:
    """One numbered segment per top item. Only the item just responded to fades in."""
    segments = []
    for n, item in enumerate(top, start=1):
        kind = responses.get(item.asset_id, {}).get("kind", "")
        cls = f"baton-seg {kind}".strip()
        if kind and item.asset_id == just_changed:
            cls += " baton-seg-new"
        word = PROGRESS_WORDS.get(kind, "not handled")
        mark = icon(SEGMENT_ICON[kind]) if kind else ""
        segments.append(f'<div class="{cls}" role="img" aria-label="{n}, {esc(item.asset_id)}: {esc(word)}">'
                        f'{n}{mark}</div>')
    entrance = ' baton-enter" style="--i:0' if enter else ""
    return f'<div class="baton-segments{entrance}">{"".join(segments)}</div>'


def progress_caption(top: list, responses: dict) -> str:
    """ "4 of 5 handled · 3 got it · 1 dismissed". Kinds nobody has used yet are left out."""
    kinds = [responses[i.asset_id].get("kind") for i in top if i.asset_id in responses]
    parts = [f"{len(kinds)} of {len(top)} handled"]
    parts += [f"{kinds.count(kind)} {word}" for kind, word in PROGRESS_WORDS.items() if kind in kinds]
    return " · ".join(parts)


# ---------- distance to limit ----------

def limit_share(value: float, limit: float, higher_worse: bool) -> float | None:
    """How far a reading has gone towards its limit: 1.0 = at the limit, above 1 = past it.

    A plain value / limit only works for a positive ceiling. Colder is better on a -70 °C freezer,
    so -61.9 is past the limit even though -61.9 / -70 is below 1. The ratio flips for a floor
    limit and for a negative limit, so worse always means a bigger share. None if the two
    numbers can't be compared as a ratio (zero, or opposite signs).
    """
    if limit == 0 or value == 0 or (value > 0) != (limit > 0):
        return None
    direct = higher_worse == (limit > 0)
    return value / limit if direct else limit / value


def _decimals(value: float) -> int:
    return len(f"{value:g}".partition(".")[2])


def limit_bar(f) -> str:
    """A thin bar for items with a reading and an alarm limit. Empty string for anything else."""
    value, limit = f.latest_value, f.limit
    if value is None or limit is None:
        return ""
    share = limit_share(value, limit, f.higher_worse)
    if share is None:
        return ""
    over = past_limit(value, limit, f.higher_worse)
    fill = 100 if over else max(0.0, min(share, 1.0)) * 100
    warn = ""
    if f.warn_limit is not None:
        warn_share = limit_share(f.warn_limit, limit, f.higher_worse)
        if warn_share is not None and 0 < warn_share < 1:
            warn = f'<span class="baton-limit-tick warn" style="left:{warn_share * 100:.1f}%"></span>'
    decimals = _decimals(value)
    text = f"{value:.{decimals}f} / {limit:.{decimals}f} {f.unit}".strip()
    label = f"Latest reading {text}, {'over' if over else 'within'} the alarm limit"
    return (f'<div class="baton-limit{" over" if over else ""}" role="img" aria-label="{esc(label)}">'
            f'<div class="baton-limit-track"><span class="baton-limit-fill" style="width:{fill:.1f}%"></span>{warn}'
            f'<span class="baton-limit-tick alarm" style="left:100%"></span></div>'
            f'<span class="baton-limit-text">{esc(text)}</span></div>')
