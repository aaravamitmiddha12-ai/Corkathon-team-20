"""Small shared pieces for the Streamlit screens: the one style block, tags, safe HTML."""

import html
import re

import streamlit as st

from src.brand import inline_svg
from src.detect import past_limit
from src.score import REASON_LABELS

MAX_TAGS = 3
EASE = "cubic-bezier(.2,0,0,1)"

CSS = """
<style>
/* ---------- tokens: one set of neutrals, light and dark. Streamlit sets color-scheme on the app from the
   active theme, so light-dark() follows a theme switch with no rerun. Amber means "notes and data disagree",
   green means handled, red means over limit or overdue; nothing else gets a colour. ---------- */
:root {
  --baton-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --baton-text: light-dark(#16181D, #EDEDEB);
  --baton-muted: light-dark(#5F626B, #A1A4AC);
  --baton-line: light-dark(#E7E7E4, #2A2D33);
  --baton-line-strong: light-dark(#BFC1BC, #50545D);
  --baton-fill: light-dark(#F3F3F1, #202227);
  --baton-hover: light-dark(rgba(22, 24, 29, 0.05), rgba(237, 237, 235, 0.07));
  --baton-bg: light-dark(#FFFFFF, #111215);
  --baton-bar: light-dark(rgba(255, 255, 255, 0.78), rgba(17, 18, 21, 0.72));
  --baton-shadow: light-dark(rgba(16, 18, 24, 0.06), rgba(0, 0, 0, 0.45));
  --baton-green: light-dark(#15803D, #4ADE80);
  --baton-red: light-dark(#C62828, #F87171);
  --baton-amber: #E8A33D;
  --baton-focus: light-dark(#16181D, #F5F5F3);
  /* Side gutter, and the content column: at most 1200px, centred. cqw here is the main pane. */
  --baton-gutter: clamp(16px, calc((100cqw - 600px) * 0.16), 80px);
  --baton-offset: max(var(--baton-gutter), calc((100cqw - 1200px) / 2));
  --baton-section-gap: 72px;
}
@container baton-main (max-width: 719px) { :root, [data-testid="stMain"] * { --baton-section-gap: 64px; } }

html, [data-testid="stMain"] { scroll-behavior: smooth; }
/* The sidebar takes room as well as the window, so layouts ask the main pane how wide it is, not the screen. */
[data-testid="stMain"] { container: baton-main / inline-size; }
[data-testid="stPlotlyChart"] { container: baton-plot / inline-size; }
[data-testid="stMainBlockContainer"].block-container { padding-top: 56px; padding-bottom: 96px; padding-inline: var(--baton-gutter);
  max-width: calc(1200px + 2 * var(--baton-gutter)); }
/* Style-only markdown blocks and script blocks take up no space in the layout. */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style),
[data-testid="stElementContainer"]:has(> [data-testid="stHtml"] script) { display: none; }

/* ---------- type: 12 / 14 / 16 / 20 / 32 / 48 ---------- */
.hc-header h1, [data-testid="stMain"] [data-testid="stHeading"] h1 {
  font-size: 48px; line-height: 1.05; font-weight: 800; letter-spacing: -0.035em; margin: 0; padding: 0;
  font-variant-numeric: tabular-nums; }
.hc-sub { color: var(--baton-muted); font-size: 20px; line-height: 1.4; margin: 8px 0 0 0; }
[data-testid="stMain"] [data-testid="stHeading"] h3 { font-size: 32px; line-height: 1.15; font-weight: 700;
  letter-spacing: -0.02em; padding: 0 0 8px 0; }
.baton-h3 { font-size: 20px; line-height: 1.3; font-weight: 650; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
@container baton-main (max-width: 719px) {
  .hc-header h1, [data-testid="stMain"] [data-testid="stHeading"] h1 { font-size: 32px; }
  .hc-sub { font-size: 16px; }
  [data-testid="stMain"] [data-testid="stHeading"] h3 { font-size: 20px; }
}
/* A small label above each section heading. */
.baton-eyebrow { font: 500 12px/16px var(--baton-mono); letter-spacing: 0.08em; text-transform: uppercase;
                 color: var(--baton-muted); margin: var(--baton-section-gap) 0 0 0; }
.baton-eyebrow.first { margin-top: 40px; }

/* Sections: nav jumps land a little below the top edge (below the top bar on narrow screens, further down). */
[id^="sec-"] { scroll-margin-top: 24px; }

/* ---------- the left sidebar: logo, controls, section nav, progress. Streamlit's own sidebar, fixed at 240px
   from 1024px up; below that it becomes a drawer opened from a slim top bar. ---------- */
/* Streamlit's top strip goes see-through, and its sidebar toggles go: the layout here decides when it shows. */
[data-testid="stHeader"] { background: transparent; pointer-events: none; }
/* Only its real buttons (the ⋮ menu) take clicks; the rest of the strip lets them through. */
[data-testid="stHeader"] * { pointer-events: none; }
[data-testid="stHeader"] :is(button, a, [role="button"]) { pointer-events: auto; }
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarResizeHandle"] { display: none !important; }
[data-testid="stSidebar"] { width: 240px !important; min-width: 240px !important; max-width: 240px !important;
  border-right: 1px solid var(--baton-line); margin-left: 0 !important; transform: none !important; }
[data-testid="stSidebarContent"] { overflow-x: hidden; padding: 0 !important; }
[data-testid="stSidebarUserContent"] { padding: 24px 20px !important; min-height: 100%; display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"] > div { flex: 1 1 auto; display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] { flex: 1 1 auto; gap: 12px; }
.st-key-baton-nav-bottom { margin-top: auto; padding-top: 16px; gap: 12px; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(> .baton-logo) { margin-bottom: 0; }
.baton-logo { padding: 0 0 12px 0; }
/* The mark and wordmark are one drawing, so they share a baseline and centre line at any size. */
.baton-logo svg { display: block; height: 45px; width: auto; max-width: 100%; }
/* Each pair is that part's fill in assets/baton-logo.svg and assets/baton-logo-dark.svg. */
.baton-far { fill: light-dark(#B8BCC4, #5C606B); }
.baton-near { fill: light-dark(#16181D, #F5F5F3); }
[data-testid="stSidebar"] [data-testid="stRadio"] label p { font-size: 14px; white-space: nowrap; }
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { flex-wrap: nowrap; gap: 12px; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { margin-right: 0; }
.st-key-open-before-you-go button p { font-size: 14px; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: 12px; color: var(--baton-muted); }

.baton-nav { position: relative; display: flex; flex-direction: column; gap: 2px; margin: 12px 0 0 0; padding-left: 10px; }
/* One bar for the whole list: it slides to the active section rather than jumping. */
.baton-nav-indicator { position: absolute; left: 0; top: 0; width: 2px; height: 32px; border-radius: 1px;
  background: var(--baton-text); opacity: 0; transition: transform 220ms cubic-bezier(.2,0,0,1), opacity 150ms ease-out; }
.baton-nav-link { display: flex; align-items: center; gap: 10px; min-height: 32px; padding: 0 8px; border-radius: 6px;
  font-size: 14px; line-height: 1.25; color: var(--baton-muted) !important; text-decoration: none !important;
  transition: color 150ms ease-out, background-color 150ms ease-out; }
.baton-nav-link .n { font: 500 12px var(--baton-mono); flex: none; }
.baton-nav-link.baton-active { color: var(--baton-text) !important; font-weight: 600; }
.baton-nav-sub { display: flex; flex-direction: column; margin: 0 0 6px 30px; }
.baton-nav-asset { display: flex; align-items: center; gap: 8px; min-height: 26px; padding: 0 8px; border-radius: 6px;
  font: 500 12px var(--baton-mono); color: var(--baton-muted) !important; text-decoration: none !important;
  transition: color 150ms ease-out, background-color 150ms ease-out; }
/* Open = a ring; handled = filled green. The fill comes from the per-render rules in ui/home.py. */
.baton-dot { flex: none; width: 8px; height: 8px; border-radius: 50%; box-sizing: border-box;
  border: 1.5px solid var(--baton-dot-ring, var(--baton-line-strong)); background: var(--baton-dot, transparent);
  transition: background-color 250ms ease-out, border-color 250ms ease-out; }
@media (hover: hover) { .baton-nav-link:hover, .baton-nav-asset:hover { background: var(--baton-hover); color: var(--baton-text) !important; } }
.baton-nav-link:focus-visible, .baton-nav-asset:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: -2px; }
.baton-nav-progress { display: flex; flex-direction: column; gap: 6px; }
.baton-nav-count::before { content: var(--baton-count, ""); font-size: 12px; color: var(--baton-muted); font-variant-numeric: tabular-nums; }
.baton-nav-track { height: 4px; border-radius: 2px; background: var(--baton-line); overflow: hidden; }
.baton-nav-fill { display: block; height: 100%; background: var(--baton-green); transform-origin: left center;
  transform: scaleX(var(--baton-done, 0)); transition: transform 300ms cubic-bezier(.2,0,0,1); }
/* The slim top bar, shown below 1024px: the logo and the menu button that opens the sidebar as a drawer. */
.st-key-baton-topbar { display: none; }
.baton-topbar { display: flex; align-items: center; gap: 12px; height: 56px; }
.baton-topbar .baton-logo { padding: 0; }
.baton-topbar .baton-logo svg { height: 26px; }
.baton-menu { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; margin-left: -10px;
  border: 0; border-radius: 8px; background: transparent; color: var(--baton-text); cursor: pointer; }
.baton-menu:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: 0; }
@media (hover: hover) { .baton-menu:hover { background: var(--baton-hover); } }
/* The dimmed backdrop behind the open drawer. It sits outside the app, so it has its own colour scheme rule. */
.baton-shade { position: fixed; inset: 0; z-index: 1000001; background: rgba(0, 0, 0, 0.45); opacity: 0; pointer-events: none;
  transition: opacity 260ms ease-out; }
html.baton-drawer-open .baton-shade { opacity: 1; pointer-events: auto; }
@media (max-width: 1023px) {
  .st-key-baton-topbar { display: flex; }
  [data-testid="stLayoutWrapper"]:has(> .st-key-baton-topbar) { position: sticky; top: 0; z-index: 999980; }
  .st-key-baton-topbar { position: relative; isolation: isolate; padding-right: 40px; height: 56px !important; min-height: 56px !important; justify-content: center; }
  /* A solid bar, full width of the pane, so nothing shows through it. */
  .st-key-baton-topbar::before { content: ""; position: absolute; inset-block: 0; inset-inline: calc(50% - 50cqw); z-index: -1;
    background: var(--baton-bg); border-bottom: 1px solid var(--baton-line); }
  [data-testid="stMainBlockContainer"].block-container { padding-top: 0; }
  [data-testid="stSidebar"] { position: fixed !important; top: 0; left: 0; bottom: 0; height: 100dvh; z-index: 1000002;
    width: min(300px, 86vw) !important; min-width: 0 !important; max-width: none !important;
    transform: translateX(-100%) !important; visibility: hidden;
    transition: transform 260ms cubic-bezier(.2,0,0,1), visibility 0s linear 260ms !important; }
  [data-testid="stSidebarContent"] { visibility: hidden !important; transition: visibility 0s linear 260ms !important; }
  html.baton-drawer-open [data-testid="stSidebarContent"] { visibility: visible !important; transition: visibility 0s !important; }
  [data-testid="stSidebarContent"] * { visibility: inherit !important; }
  html.baton-drawer-open [data-testid="stSidebar"] { transform: none !important; visibility: visible;
    transition: transform 260ms cubic-bezier(.2,0,0,1), visibility 0s !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25); }
  [id^="sec-"] { scroll-margin-top: 80px; }
}

/* Reading progress along the top of the main pane, and Back to top. Both live outside the app (ui/components.py,
   NAV_SCRIPT), so they move with transform and opacity only. */
.baton-read { position: fixed; top: 0; left: var(--baton-main-left, 0px); right: 0; height: 2px; z-index: 1000000;
  background: var(--baton-text); transform-origin: left center; transform: scaleX(0); pointer-events: none; }
.baton-back { position: fixed; right: 24px; bottom: 24px; z-index: 999985; display: inline-flex; align-items: center; gap: 6px;
  height: 40px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--baton-line-strong);
  background: var(--baton-bg); color: var(--baton-text); font: 500 14px "Source Sans", sans-serif; cursor: pointer;
  box-shadow: 0 2px 8px var(--baton-shadow); opacity: 0; transform: translateY(8px); pointer-events: none;
  transition: opacity 200ms ease-out, transform 200ms ease-out, border-color 150ms ease-out; }
.baton-back::before { content: "↑"; }
.baton-back.baton-show { opacity: 1; transform: none; pointer-events: auto; }
@media (hover: hover) { .baton-back:hover { border-color: var(--baton-text); } }
.baton-back:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: 2px; }
@media (pointer: coarse) { .baton-back { height: 44px; } }


/* ---------- scroll reveal and the timeline drawing itself. Only with motion allowed, and only once the script
   has run (html.baton-js), so nothing stays hidden without it. ---------- */
@keyframes baton-fade { from { opacity: 0; } }
@keyframes baton-grow { from { transform: scaleX(0); } }
@media (prefers-reduced-motion: no-preference) {
  html.baton-js [class*="st-key-baton-sec-"]:not([data-baton-seen]) > * { opacity: 0; transform: translateY(12px); }
  html.baton-js [class*="st-key-baton-sec-"][data-baton-seen="anim"] > * {
    transition: opacity 300ms ease-out, transform 300ms ease-out; transition-delay: calc(var(--baton-i, 0) * 50ms); }
  html.baton-js .st-key-baton-timeline:not([data-baton-chart]) :is(.gridlayer, .shapelayer, .scatterlayer .point, .barlayer .point) { opacity: 0; }
  .st-key-baton-timeline[data-baton-chart="play"] :is(.gridlayer, .shapelayer) { animation: baton-fade 200ms ease-out both; }
  .st-key-baton-timeline[data-baton-chart="play"] .scatterlayer .point { animation: baton-fade 160ms ease-out both; animation-delay: var(--baton-d, 0ms); }
  .st-key-baton-timeline[data-baton-chart="play"] .barlayer .point path { transform-box: fill-box; transform-origin: left center;
    animation: baton-grow var(--baton-len, 300ms) linear both; animation-delay: var(--baton-d, 0ms); }
}

/* The outgoing engineer's button: secondary, its arrow nudges on hover. */
.st-key-open-before-you-go button p::after { content: "→"; display: inline-block; margin-left: 0.4em; transition: transform 200ms ease-out; }
@media (hover: hover) {
  .st-key-open-before-you-go button:hover:not(:disabled) { border-color: var(--baton-text); background-color: transparent; }
  .st-key-open-before-you-go button:hover:not(:disabled) p::after { transform: translateX(2px); }
}

/* ---------- surfaces: hairlines, not filled boxes ---------- */
.hc-banner { padding: 12px 16px; border-radius: 10px; font-size: 14px; line-height: 1.5; margin: 24px 0 0 0;
             border: 1px solid var(--baton-line); }
.hc-banner.done { border-color: var(--baton-green); margin-top: 8px; }
[data-testid="stAlertContainer"] { background: transparent !important; border: 1px solid var(--baton-line); border-radius: 10px; }
[data-testid="stExpander"] details { border-color: var(--baton-line); border-radius: 10px; background: transparent; }
[data-testid="stExpander"] summary { background: transparent; }
.hc-note { padding: 8px 12px; border-radius: 8px; margin-bottom: 4px; font-size: 14px;
           line-height: 1.5; border-left: 3px solid transparent; transition: background-color 150ms ease-out; }
.hc-note.clash { background: rgba(232, 163, 61, 0.18); border-left-color: #E8A33D; }
@media (hover: hover) {
  .hc-note:hover { background: var(--baton-hover); }
  .hc-note.clash:hover { background: rgba(232, 163, 61, 0.28); }
}
.hc-time, .baton-mono { font-family: var(--baton-mono); font-variant-numeric: tabular-nums; }
.hc-time { color: var(--baton-muted); margin-right: 8px; }
.hc-asset { font-family: var(--baton-mono); font-size: 12px; color: var(--baton-muted);
            margin-left: 6px; white-space: nowrap; }
.hc-note.clash .hc-time, .hc-note.clash .hc-asset { opacity: 0.75; color: inherit; }
.hc-chip { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border-radius: 999px;
           font-size: 12px; line-height: 18px; font-weight: 500; margin: 0 4px 4px 0; white-space: nowrap;
           border: 1px solid var(--baton-line-strong); }
.hc-chip svg { flex: none; display: block; }
.hc-chip.clash { background: #E8A33D; color: #16181D; border-color: #E8A33D; font-weight: 600; }
.hc-key { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; font-size: 12px; color: var(--baton-muted); margin: 0 0 8px 0; }
.hc-key .hc-chip { margin: 0; color: var(--baton-text); }
.hc-key .hc-chip.clash { color: #16181D; }
.hc-toprow { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; flex-wrap: wrap; }
.hc-due { font-size: 14px; color: var(--baton-muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.hc-due.overdue { color: var(--baton-red); font-weight: 700; }
.hc-card-head { display: flex; align-items: baseline; gap: 8px; margin: 4px 0 8px 0; }
.hc-num { font-size: 20px; font-weight: 700; color: var(--baton-muted); min-width: 1.2em; font-variant-numeric: tabular-nums; }
.hc-headline { font-size: 20px; line-height: 1.3; font-weight: 650; letter-spacing: -0.01em; flex: 1; min-width: 0; overflow-wrap: break-word; }
.hc-action { margin: 4px 0; line-height: 1.5; font-weight: 700; }
.hc-bullets { margin: 0 0 8px 0; padding-left: 1.2rem; line-height: 1.5; font-variant-numeric: tabular-nums; }
.hc-bullets li { margin-bottom: 2px; }
.hc-quiet { padding: 8px 12px; border-radius: 8px; font-size: 14px; margin: 8px 0;
            border: 1px solid var(--baton-line); line-height: 1.5; }
.hc-quiet .who { font-size: 12px; color: var(--baton-muted); display: block; margin-bottom: 2px; }
.hc-worse { padding: 8px 12px; border-radius: 8px; font-size: 14px; margin: 8px 0;
            border: 1px solid var(--baton-line-strong); }
.hc-status { font-size: 14px; font-weight: 600; margin: 4px 0; font-variant-numeric: tabular-nums; }
.hc-status.done { color: var(--baton-green); }
.hc-muted { color: var(--baton-muted); font-size: 14px; }
.hc-row { padding: 8px 0; border-bottom: 1px solid var(--baton-line); font-size: 14px; }
.hc-row:last-child { border-bottom: none; }
.baton-table-box { overflow-x: auto; overscroll-behavior-x: contain; }
.hc-ev { width: 100%; border-collapse: collapse; font-size: 14px; margin: 2px 0 8px 0;
         font-variant-numeric: tabular-nums; }
.hc-ev th, .hc-ev td { text-align: left; vertical-align: top; padding: 6px 8px;
                       border-bottom: 1px solid var(--baton-line); }
.hc-ev th { font-weight: 600; font-size: 12px; color: var(--baton-muted); }
.hc-ev:not(.plain) td:first-child { font-family: var(--baton-mono); white-space: nowrap; }
.hc-ev:not(.plain) td:nth-child(2) { white-space: nowrap; }
.hc-ev.plain td:first-child { font-weight: 600; white-space: nowrap; }
/* Asset ids are never broken or cut: the table box scrolls sideways instead. */
.hc-ev td.baton-id, .hc-row > b { font-family: var(--baton-mono); white-space: nowrap; }

/* ---------- timeline ---------- */
.st-key-baton-timeline [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.25rem; align-items: flex-start; }
.st-key-baton-timeline [data-testid="stColumn"] { min-width: 0; }
/* The label column can't get narrower than its longest asset id: the name gives way, never the id. */
.st-key-baton-timeline [data-testid="stColumn"]:first-child { flex: 0 0 clamp(148px, 24%, 280px); min-width: min-content; }
.st-key-baton-timeline [data-testid="stColumn"]:last-child { flex: 1 1 0; position: relative; }
.st-key-baton-timeline .nsewdrag { cursor: pointer !important; }
/* Six 2-hour gaps stop fitting their times below these widths, so every other time is hidden. */
@container baton-plot (max-width: 259px) { .st-key-baton-timeline .xtick:nth-child(even) text { visibility: hidden; } }
@container baton-plot (max-width: 319px) { div[class*="st-key-baton-card-"] .xtick:nth-child(even) text { visibility: hidden; } }
.baton-tl-label { display: flex; align-items: center; gap: 8px; padding-inline: 6px; border-radius: 6px;
                  font-size: 14px; white-space: nowrap; overflow: hidden;
                  color: inherit !important; text-decoration: none !important;
                  transition: background-color 150ms ease-out; }
/* --baton-* come from the per-render rules in ui/home.py, row_state_rules. The tick takes the rank's slot, which
   has a fixed width, so a response never moves the label or makes the chart re-fit. */
.baton-tl-rank { flex: none; width: 0.85rem; text-align: center; font-variant-numeric: tabular-nums;
                 font-size: var(--baton-rank-size, 12px); color: var(--baton-muted); opacity: var(--baton-rank-fade, 1); }
.baton-tl-rank::before { content: var(--baton-tick, none); font-size: 14px; font-weight: 700; color: var(--baton-green); }
.baton-tl-id { flex: none; font-family: var(--baton-mono); font-weight: var(--baton-row-weight, 600);
               opacity: var(--baton-row-fade, 1); transition: opacity 150ms ease-out; }
.baton-tl-name { flex: 1 1 0; min-width: 0; contain: inline-size; color: var(--baton-muted); overflow: hidden; text-overflow: ellipsis; }
.baton-tl-label.baton-tl-hot { background: var(--baton-hover); }
.baton-tl-label.baton-tl-hot .baton-tl-id { opacity: 1; }
a.baton-tl-label:active { opacity: 0.7; }
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .baton-tl-bands) { position: absolute; inset: 0; width: auto; pointer-events: none; }
.baton-tl-band { display: block; position: absolute; inset-inline: 0; border-radius: 6px; transition: background-color 150ms ease-out; }
.baton-tl-band.baton-tl-hot { background: var(--baton-hover); }
/* A pane this narrow has no room for a name worth reading: the column shrinks to the ids and the chart gets the rest. */
@container baton-main (max-width: 480px) {
  .baton-tl-name { display: none; }
  .st-key-baton-timeline [data-testid="stColumn"]:first-child { flex: 0 0 auto; width: auto; }
}
.baton-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12px; color: var(--baton-muted); margin: 0 0 8px 0; }
.baton-legend span { display: inline-flex; align-items: center; gap: 6px; }
.baton-legend i { display: block; flex: none; }
.baton-legend .dot { width: 10px; height: 10px; border-radius: 50%; background: #8a8984; }
.baton-legend .dot.after { background: #E8A33D; }
.baton-legend .note { width: 8px; height: 8px; background: #5b6b84; transform: rotate(45deg); }
.baton-legend .band { width: 22px; height: 10px; border-radius: 4px; background: rgba(232, 163, 61, 0.28); }

/* Notes and the list side by side only while the list still has room for a card with its buttons in a row. */
@container baton-main (max-width: 959px) {
  .st-key-baton-main > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { row-gap: 0; }
  .st-key-baton-main > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 100%; min-width: 100%; }
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 260px; min-width: 0; }

/* ---------- progress ---------- */
.baton-segments { display: flex; gap: 4px; margin: 4px 0 8px 0; }
.baton-seg { flex: 1 1 0; min-width: 0; height: 28px; display: flex; align-items: center; justify-content: center;
             gap: 4px; border-radius: 6px; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums;
             background: var(--baton-fill); border: 1px solid var(--baton-line); }
.baton-seg svg { flex: none; display: block; }
.baton-seg.got_it, .baton-seg.ticket_drafted { background: #15803d; border-color: #15803d; color: #ffffff; }
.baton-seg.dismissed { background: transparent; border: 1px dashed var(--baton-line-strong); }
.baton-progress-caption { font-size: 14px; color: var(--baton-muted); margin-bottom: 4px; font-variant-numeric: tabular-nums; }

/* ---------- cards: the only surfaces with a shadow, because they're the ones you act on ---------- */
[id^="card-"] { scroll-margin-top: 72px; }
div[class*="st-key-baton-card-"] { container: baton-card / inline-size; border-color: var(--baton-line) !important;
  border-radius: 12px; background: var(--baton-bg);
  box-shadow: 0 1px 2px var(--baton-shadow), 0 4px 12px -6px var(--baton-shadow);
  transition: border-color 150ms ease-out; }
@media (hover: hover) { div[class*="st-key-baton-card-"]:hover { border-color: var(--baton-line-strong) !important; } }
div[class*="st-key-baton-card-"]:has(.baton-slim) { padding-block: 0.35rem; }
div[class*="st-key-baton-card-"]:has(:target) { animation: baton-flash 1000ms ease-out 1; }
[data-testid="stMarkdownContainer"]:has(> .baton-slim) { margin-bottom: 0; }
div[class*="st-key-baton-card-"]:has(.baton-slim) button { min-height: 1.75rem; }
/* A slim row keeps its Open button beside the text at every width; the text wraps instead. */
div[class*="st-key-baton-card-"]:has(.baton-slim) > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
div[class*="st-key-baton-card-"]:has(.baton-slim) > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex: 1 1 0; min-width: 0; }
div[class*="st-key-baton-card-"]:has(.baton-slim) > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex: 0 0 auto; width: auto; min-width: 0; }
/* Action buttons: three in a row, then two and one, then a stack. An item with no ticket button keeps the empty
   slot while its buttons line up with the cards around it, and drops it once they can't. */
div[class*="st-key-baton-card-"]:not(:has(.baton-slim)) > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 150px; min-width: 0; }
@container baton-card (max-width: 515px) { div[class*="st-key-baton-card-"]:not(:has(.baton-slim)) > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:has(button)) { display: none; } }
.baton-slim { font-size: 14px; line-height: 1.4; font-variant-numeric: tabular-nums; }
.baton-slim b { font-family: var(--baton-mono); font-weight: 600; }
.baton-slim .tick { color: var(--baton-green); font-weight: 700; }
.baton-limit { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; margin: 4px 0 8px 0; }
.baton-limit-track { position: relative; flex: 1 1 7rem; height: 6px; border-radius: 3px; background: var(--baton-fill);
                     box-shadow: inset 0 0 0 1px var(--baton-line); }
.baton-limit-fill { position: absolute; inset: 0 auto 0 0; border-radius: 3px; background: var(--baton-muted); }
.baton-limit.over .baton-limit-fill { background: var(--baton-red); }
.baton-limit-tick { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; border-radius: 1px; }
/* The warning level is a neutral tick: amber is kept for "notes and data disagree". */
.baton-limit-tick.warn { background: var(--baton-text); opacity: 0.55; }
.baton-limit-tick.alarm { background: var(--baton-red); margin-left: -2px; }
.baton-limit-text { font-variant-numeric: tabular-nums; font-size: 12px; font-weight: 500; white-space: nowrap; }
.baton-limit.over .baton-limit-text { color: var(--baton-red); font-weight: 600; }

/* ---------- buttons and rows react to the pointer ---------- */
[data-testid^="stBaseButton-"] { transition: background-color 150ms ease-out, border-color 150ms ease-out,
                                             opacity 150ms ease-out, transform 150ms ease-out; }
/* Primary buttons are near-black in light and near-white in dark; the label takes the page colour. */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] { color: var(--baton-bg); }
[data-testid^="stBaseButton-"]:active:not(:disabled) { transform: translateY(1px); }
[data-testid="stExpander"] summary { transition: background-color 150ms ease-out; }
@media (hover: hover) {
  a.baton-tl-label:hover { background: var(--baton-hover); }
  [data-testid^="stBaseButton-primary"]:hover:not(:disabled) { opacity: 0.85; }
  [data-testid^="stBaseButton-secondary"]:hover:not(:disabled),
  [data-testid^="stBaseButton-tertiary"]:hover:not(:disabled) { background-color: var(--baton-hover); }
  [data-testid="stExpander"] summary:hover { background-color: var(--baton-hover); }
}
[data-testid^="stBaseButton-"]:focus-visible, [data-testid="stExpander"] summary:focus-visible {
  outline: 2px solid var(--baton-focus); outline-offset: 2px; }
a.baton-tl-label:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: -2px; }

/* ---------- touch: anything a finger can hit is at least 44px (timeline rows already are) ---------- */
@media (pointer: coarse) {
  [data-testid^="stBaseButton-"], div[class*="st-key-baton-card-"]:has(.baton-slim) button { min-height: 44px; min-width: 44px; }
  [data-testid="stExpander"] summary { min-height: 44px; }
  [data-testid="stRadio"] label { min-height: 44px; align-items: center; }
}

/* ---------- hover polish: subtle, under 350ms, and the content never moves out of reach. Every hover also
   answers keyboard focus; hover-only parts are skipped on touch; reduced motion keeps only colour and opacity. ---------- */
/* Text roll: the label slides up out of a clip while a copy (a text shadow one line below) slides into its place. */
.baton-roll { display: inline-block; height: 1.25em; line-height: 1.25em; clip-path: inset(0); vertical-align: middle; }
.baton-roll > span { display: inline-block; text-shadow: 0 1.25em currentColor; }
.st-key-open-before-you-go button [data-testid="stMarkdownContainer"] { clip-path: inset(0); }
.st-key-open-before-you-go button p { text-shadow: 0 var(--baton-roll-h, 1.5em) currentColor; }
@media (prefers-reduced-motion: no-preference) {
  .baton-roll > span, .st-key-open-before-you-go button p { transition: transform 250ms ease-out; }
  .baton-nav-link:focus-visible .baton-roll > span { transform: translateY(-1.25em); }
  .st-key-open-before-you-go button:focus-visible p { transform: translateY(calc(-1 * var(--baton-roll-h, 1.5em))); }
  @media (hover: hover) {
    .baton-nav-link:hover .baton-roll > span { transform: translateY(-1.25em); }
    .st-key-open-before-you-go button:hover:not(:disabled) p { transform: translateY(calc(-1 * var(--baton-roll-h, 1.5em))); }
  }
}
.st-key-open-before-you-go button:focus-visible p::after { transform: translateX(2px); }

/* Colour wipe: a soft tint rises from the bottom edge. Amber while an item is open, green once handled. */
div[class*="st-key-baton-card-"], .baton-nav-asset { position: relative; isolation: isolate; }
div[class*="st-key-baton-card-"]::before, .baton-nav-asset::before { content: ""; position: absolute; inset: 0; z-index: -1;
  border-radius: inherit; pointer-events: none; background: var(--baton-wipe, light-dark(rgba(232, 163, 61, 0.09), rgba(232, 163, 61, 0.10)));
  transform: scaleY(0); transform-origin: bottom center; }
div[class*="st-key-baton-card-"]:has(.baton-slim, .hc-status.done) { --baton-wipe: light-dark(rgba(21, 128, 61, 0.07), rgba(74, 222, 128, 0.08)); }
@media (prefers-reduced-motion: no-preference) {
  div[class*="st-key-baton-card-"]::before, .baton-nav-asset::before { transition: transform 280ms cubic-bezier(.2,0,0,1); }
}
@media (hover: hover) {
  div[class*="st-key-baton-card-"]:hover::before, .baton-nav-asset:hover::before { transform: none; }
  .baton-nav-asset:hover { background: transparent; }
}
div[class*="st-key-baton-card-"]:has(:focus-visible)::before, .baton-nav-asset:focus-visible::before { transform: none; }

/* Timeline rows: a band sweeps across the row, its label steps 4px right, the other rows dim, its marks grow
   (the marks are scaled by the hover script in ui/home.py). */
.baton-tl-band { background: var(--baton-hover); transform: scaleX(0); transform-origin: left center; }
.baton-tl-band.baton-tl-hot { transform: none; }
.baton-tl-label { transition: background-color 150ms ease-out, opacity 150ms ease-out; }
.st-key-baton-timeline[data-baton-hot] .baton-tl-label:not(.baton-tl-hot) { opacity: 0.4; }
.st-key-baton-timeline[data-baton-hot] :is(.scatterlayer .point, .barlayer .point):not([data-baton-row-hot]) { opacity: 0.4 !important; }
.st-key-baton-timeline .scatterlayer .point, .st-key-baton-timeline .barlayer .point { transition: opacity 150ms ease-out; }
@media (prefers-reduced-motion: no-preference) {
  .baton-tl-band { transition: transform 250ms ease-out; }
  .baton-tl-label > * { transition: transform 200ms ease-out, opacity 150ms ease-out; }
  .baton-tl-label.baton-tl-hot > * { transform: translateX(4px); }
  .st-key-baton-timeline[data-baton-hot] .scatterlayer .point { transition: opacity 150ms ease-out, transform 150ms ease-out; }
}

/* Notes: a 2px bar grows down the left edge and the time steps right; the hover script pulses its chart mark once. */
.hc-note { position: relative; }
.hc-note::before { content: ""; position: absolute; left: -3px; top: 0; bottom: 0; width: 2px; border-radius: 1px;
  background: var(--baton-text); transform: scaleY(0); transform-origin: top center; }
.hc-time { display: inline-block; }
.hc-note:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: 1px; }
.hc-note:focus-visible::before { transform: none; }
@media (hover: hover) { .hc-note:hover::before { transform: none; } }
@media (prefers-reduced-motion: no-preference) {
  .hc-note::before { transition: transform 220ms ease-out; }
  .hc-time { transition: transform 200ms ease-out; }
  .hc-note:focus-visible .hc-time { transform: translateX(3px); }
  @media (hover: hover) { .hc-note:hover .hc-time { transform: translateX(3px); } }
}

/* Buttons: the border darkens; primary buttons lean up to 4px toward a mouse (NAV_SCRIPT sets --baton-mx/my). */
@media (hover: hover) {
  [data-testid^="stBaseButton-secondary"]:hover:not(:disabled) { border-color: var(--baton-text); }
}
[data-testid^="stBaseButton-secondary"]:focus-visible { border-color: var(--baton-text); }
[data-testid="stBaseButton-primary"] { transform: translate(var(--baton-mx, 0px), var(--baton-my, 0px)); }

/* ---------- headings: words rise from behind a mask as their section comes in; the label above fades first ---------- */
.baton-heading { font-size: 32px; line-height: 1.15; font-weight: 700; letter-spacing: -0.02em; margin: 0; padding: 0 0 8px 0; }
@container baton-main (max-width: 719px) { .baton-heading { font-size: 20px; } }
.baton-words .w { display: inline-block; clip-path: inset(-0.05em -0.1em -0.18em -0.1em); vertical-align: top; }
.baton-words .w > span { display: inline-block; }
@media (prefers-reduced-motion: no-preference) {
  html.baton-js [class*="st-key-baton-sec-"]:not([data-baton-seen]) > :has(.baton-words) { opacity: 1; transform: none; }
  html.baton-js [class*="st-key-baton-sec-"]:not([data-baton-seen]) .baton-words .w > span { transform: translateY(110%); }
  html.baton-js [class*="st-key-baton-sec-"][data-baton-seen="anim"] .baton-words .w > span {
    transition: transform 320ms cubic-bezier(.2,0,0,1); transition-delay: calc(80ms + var(--wi, 0) * 60ms); }
}

/* ---------- the first screen: an overview with room around it, then the detail below ---------- */
.st-key-baton-sec-1 { min-height: calc(100dvh - 152px); justify-content: center; }
@media (max-width: 1023px) { .st-key-baton-sec-1 { min-height: calc(100dvh - 96px); } }
.baton-overview { display: flex; flex-direction: column; }
.baton-lede { font-size: 16px; line-height: 1.5; color: var(--baton-muted); margin: 16px 0 0 0; max-width: 60ch; }
.baton-tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 32px 0 0 0; }
@container baton-main (max-width: 899px) { .baton-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container baton-main (max-width: 339px) { .baton-tiles { grid-template-columns: 1fr; } }
.baton-tile { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 16px; border-radius: 12px;
  border: 1px solid var(--baton-line); }
.baton-tile .k { font: 500 12px/16px var(--baton-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--baton-muted); }
.baton-tile .v { font-size: 32px; line-height: 1.15; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.baton-tile .v.mono { font-family: var(--baton-mono); font-size: 24px; line-height: 1.55; letter-spacing: 0; }
.baton-tile .v.live::before { content: var(--baton-handled, ""); }
.baton-tile .c { font-size: 14px; line-height: 1.4; color: var(--baton-muted); overflow-wrap: anywhere; }
.baton-tile .baton-nav-track { margin-top: 10px; }
/* Amber only where notes and data disagree; red only when something is overdue. */
.baton-tile.clash .v::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  background: #E8A33D; margin-right: 10px; vertical-align: middle; }
.baton-tile.overdue .v, .baton-tile.overdue .c { color: var(--baton-red); }
.baton-actions { display: flex; flex-wrap: wrap; gap: 12px; margin: 32px 0 0 0; }
.baton-cta { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 18px; border-radius: 8px;
  font-size: 16px; font-weight: 600; text-decoration: none !important; border: 1px solid var(--baton-focus);
  background: var(--baton-focus); color: var(--baton-bg) !important;
  transform: translate(var(--baton-mx, 0px), var(--baton-my, 0px)); transition: opacity 150ms ease-out, border-color 150ms ease-out, transform 150ms ease-out; }
.baton-cta .baton-mono { font-weight: 600; }
.baton-cta.ghost { background: transparent; color: var(--baton-text) !important; border-color: var(--baton-line-strong); font-weight: 500; }
.baton-cta .arr { display: inline-block; transition: transform 200ms ease-out; }
.baton-cta:focus-visible { outline: 2px solid var(--baton-focus); outline-offset: 2px; }
.baton-cta:focus-visible .arr { transform: translateX(2px); }
@media (hover: hover) {
  .baton-cta:not(.ghost):hover { opacity: 0.88; }
  .baton-cta.ghost:hover { border-color: var(--baton-text); }
  .baton-cta:hover .arr { transform: translateX(2px); }
}
.baton-steps { display: flex; flex-wrap: wrap; gap: 8px 28px; list-style: none; padding: 0; margin: 32px 0 0 0;
  font-size: 14px; color: var(--baton-muted); counter-reset: baton-step; }
.baton-steps li { display: flex; align-items: baseline; gap: 8px; margin: 0; counter-increment: baton-step; }
.baton-steps li::before { content: counter(baton-step); flex: none; display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border-radius: 50%; border: 1px solid var(--baton-line-strong); font: 600 12px var(--baton-mono);
  color: var(--baton-text); transform: translateY(-1px); }
.baton-steps b { color: var(--baton-text); font-weight: 600; }

/* ---------- motion ---------- */
@keyframes baton-in { from { opacity: 0; transform: translateY(6px); } }
@keyframes baton-done { from { opacity: 0; transform: translateY(-4px); } }
@keyframes baton-seg-in { from { opacity: 0; } }
@keyframes baton-flash { from { outline: 2px solid var(--baton-focus); } to { outline: 2px solid transparent; } }
.baton-enter { animation: baton-in 240ms cubic-bezier(.2,0,0,1) both; animation-delay: calc(var(--i) * 50ms); }
.baton-done { animation: baton-done 220ms cubic-bezier(.2,0,0,1) both; }
.baton-seg-new { animation: baton-seg-in 200ms ease-out both; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
  [data-testid^="stBaseButton-"]:active { transform: none !important; }
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


def logo() -> str:
    """The logo as its own element. The CSS above keeps its colours on the active theme; the choice of
    file only matters to a browser too old for light-dark()."""
    name = "baton-logo-dark.svg" if st.context.theme.type == "dark" else "baton-logo.svg"
    return f'<div class="baton-logo">{inline_svg(name)}</div>'


def eyebrow(n: int | None, text: str, first: bool = False) -> str:
    """The small label above a section heading: "02 · SHIFT AT A GLANCE". A numbered one is also the section's
    anchor (#sec-2), which the sidebar links to and watches."""
    anchor = f' id="sec-{n}"' if n else ""
    number = f"{n:02d} · " if n else ""
    return f'<div class="baton-eyebrow{" first" if first else ""}"{anchor}>{number}{esc(text.upper())}</div>'


def heading_words(text: str) -> str:
    """Each word in its own mask, numbered, so the section reveal can raise them one after another."""
    return " ".join(f'<span class="w" style="--wi:{i}"><span>{esc(word)}</span></span>' for i, word in enumerate(text.split()))


def heading(text: str) -> str:
    """A section heading whose words rise into view (the CSS for .baton-words)."""
    return (f'<div class="baton-heading baton-words" role="heading" aria-level="2" aria-label="{esc(text)}">'
            f'{heading_words(text)}</div>')


# The home screen's sections, as the sidebar lists them. Numbers match the eyebrows in ui/home.py.
SECTIONS = [(1, "Start here"), (2, "Shift at a glance"), (3, "Needs you first"), (4, "What the notes say"),
            (5, "Also checked")]
MENU_ICON = ('<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" '
             'stroke-linecap="round" aria-hidden="true"><path d="M3 5.5h14M3 10h14M3 14.5h14"/></svg>')


def nav(shift_id: str, top: list) -> str:
    """Section links, with the top items listed under "Needs you first". An item link carries the key of its
    card's Open button, so the script can open a handled card as well as scroll to it."""
    links = []
    for n, name in SECTIONS:
        links.append(f'<a class="baton-nav-link" href="#sec-{n}" target="_self" data-sec="sec-{n}">'
                     f'<span class="n">{n:02d}</span><span class="baton-roll"><span>{esc(name)}</span></span></a>')
        if n == 3:
            items = "".join(
                f'<a class="baton-nav-asset" href="#card-{slug(i.asset_id)}" target="_self" '
                f'data-open="open-{esc(shift_id)}-{esc(i.asset_id)}"><i class="baton-dot"></i>{esc(i.asset_id)}</a>'
                for i in top)
            links.append(f'<div class="baton-nav-sub">{items}</div>')
    return (f'<nav class="baton-nav" aria-label="Sections"><i class="baton-nav-indicator"></i>'
            f'{"".join(links)}</nav>')


def nav_progress() -> str:
    """ "X of 5 handled" and its bar. The numbers come from nav_state_rules, so a response can change them
    without re-running the sidebar."""
    return ('<div class="baton-nav-progress"><div class="baton-nav-count" aria-live="polite"></div>'
            '<div class="baton-nav-track"><i class="baton-nav-fill"></i></div></div>')


def nav_state_rules(top: list, responses: dict, strong: bool = False) -> list[str]:
    """The sidebar's live state: a filled dot per handled item, the count and the bar. The sidebar renders these
    on a full run; the responses fragment renders them again with `strong`, so its newer copy wins."""
    lead = "html " if strong else ""
    rules = [f'{lead}a.baton-nav-asset[href="#card-{slug(i.asset_id)}"] '
             f'{{ --baton-dot: var(--baton-green); --baton-dot-ring: var(--baton-green); '
             f'--baton-wipe: light-dark(rgba(21, 128, 61, 0.10), rgba(74, 222, 128, 0.10)); }}'
             for i in top if i.asset_id in responses]
    done = sum(1 for i in top if i.asset_id in responses)
    share = done / len(top) if top else 0
    rules.append(f'{lead}.baton-nav-progress, {lead}.baton-tile-live {{ --baton-count: "{done} of {len(top)} handled"; '
                 f'--baton-done: {share:.3f}; --baton-handled: "{done} of {len(top)}"; }}')
    return rules


def topbar() -> str:
    """The slim bar shown below 1024px: the menu button and the logo."""
    return (f'<div class="baton-topbar"><button class="baton-menu" type="button" aria-label="Open menu" '
            f'aria-expanded="false">{MENU_ICON}</button>{logo()}</div>')


# The sidebar and the scroll effects. Every listener is bound once, on the document, and finds its elements each
# time, so Streamlit re-rendering can't double them up. Elements Streamlit doesn't own (reading progress, Back to
# top, the drawer's backdrop) are added to <body> once. Scroll-spy and reveals use IntersectionObserver; a
# MutationObserver hands them any section Streamlit adds later.
NAV_SCRIPT = """<script>
(function () {
  if (window.batonNavBound) return;
  window.batonNavBound = true;
  var root = document.documentElement, reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var narrow = window.matchMedia("(max-width: 1023px)");
  root.classList.add("baton-js");
  function q(s) { return document.querySelector(s); }
  function main() { return q('[data-testid="stMain"]'); }

  var read = document.createElement("div"); read.className = "baton-read"; read.setAttribute("aria-hidden", "true");
  var back = document.createElement("button"); back.type = "button"; back.className = "baton-back";
  back.append(" Back to top"); back.tabIndex = -1;
  var shade = document.createElement("div"); shade.className = "baton-shade";
  document.body.append(read, back, shade);

  // ----- reading progress and Back to top -----
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      var m = main(); if (!m) return;
      var max = m.scrollHeight - m.clientHeight;
      read.style.transform = "scaleX(" + (max > 0 ? Math.min(1, m.scrollTop / max) : 0) + ")";
      var show = m.scrollTop > m.clientHeight;
      back.classList.toggle("baton-show", show); back.tabIndex = show ? 0 : -1;
      // The hero drifts up a little slower than the page and fades a touch as it leaves (at most 16px, 35%).
      var y = Math.min(m.scrollTop, 320);
      document.querySelectorAll(".st-key-baton-sec-1 .hc-header, .st-key-baton-sec-1 .hc-sub").forEach(function (el) {
        el.style.transform = reduce.matches || !y ? "" : "translateY(" + (y * 0.05).toFixed(1) + "px)";
        el.style.opacity = reduce.matches || !y ? "" : (1 - y / 320 * 0.35).toFixed(3);
      });
    });
  }
  document.addEventListener("scroll", function () { onScroll(); pick(); }, true);
  back.addEventListener("click", function () {
    var m = main(); if (m) m.scrollTo({ top: 0, behavior: reduce.matches ? "auto" : "smooth" });
  });

  // ----- primary buttons lean toward a mouse, at most 4px; never on touch or with reduced motion -----
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)"), pulled = null;
  function release() { if (pulled) { pulled.style.removeProperty("--baton-mx"); pulled.style.removeProperty("--baton-my"); pulled = null; } }
  document.addEventListener("pointermove", function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('[data-testid="stBaseButton-primary"], .baton-cta:not(.ghost)') : null;
    if (pulled && pulled !== btn) release();
    if (!btn || btn.disabled || !fine.matches || reduce.matches || e.pointerType !== "mouse") return;
    var r = btn.getBoundingClientRect();
    var dx = Math.max(-1, Math.min(1, (e.clientX - r.left - r.width / 2) / (r.width / 2)));
    var dy = Math.max(-1, Math.min(1, (e.clientY - r.top - r.height / 2) / (r.height / 2)));
    btn.style.setProperty("--baton-mx", (dx * 4).toFixed(1) + "px");
    btn.style.setProperty("--baton-my", (dy * 2).toFixed(1) + "px");
    pulled = btn;
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", release);

  // ----- scroll-spy: the first section crossing the upper part of the view is active; at the very bottom of the
  // page, the last one on screen (a short last section may never reach that band) -----
  var visible = {}, onScreen = {}, active = null, lockUntil = 0;
  function secId(el) { var m = el.className.match(/st-key-baton-sec-(\\d+)/); return m ? "sec-" + m[1] : ""; }
  function moveIndicator() {
    var navEl = q(".baton-nav"); if (!navEl) return;
    var link = active && navEl.querySelector('[data-sec="' + active + '"]'), bar = navEl.querySelector(".baton-nav-indicator");
    navEl.querySelectorAll(".baton-nav-link").forEach(function (l) {
      var on = l === link; l.classList.toggle("baton-active", on);
      if (on) l.setAttribute("aria-current", "true"); else l.removeAttribute("aria-current");
    });
    if (bar && link) {
      bar.style.height = link.offsetHeight + "px";
      bar.style.transform = "translateY(" + link.offsetTop + "px)";
      bar.style.opacity = "1";
    }
  }
  function pick() {
    if (Date.now() < lockUntil) return;
    var m = main(), atEnd = m && m.scrollTop > 0 && m.scrollTop + m.clientHeight >= m.scrollHeight - 2;
    var pool = atEnd ? onScreen : visible;
    var ids = Object.keys(pool).filter(function (id) { return pool[id]; }).sort();
    var next = atEnd ? ids[ids.length - 1] : ids[0];
    if (next && next !== active) { active = next; moveIndicator(); }
  }
  var spy = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { visible[secId(e.target)] = e.isIntersecting; });
    pick();
  }, { rootMargin: "-10% 0px -55% 0px" });
  var spyAll = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { onScreen[secId(e.target)] = e.isIntersecting; });
    pick();
  });

  // ----- reveal each section once, its children staggered -----
  var seenKeys = {};
  function keyOf(sec) { var m = sec.className.match(/st-key-(baton-sec-\\d+)/); return m ? m[1] : ""; }
  function reveal(sec, animate) {
    seenKeys[keyOf(sec)] = true;
    var i = 0;
    Array.prototype.forEach.call(sec.children, function (c) {
      if (c.offsetParent !== null || getComputedStyle(c).position === "fixed") c.style.setProperty("--baton-i", Math.min(i++, 6));
    });
    sec.setAttribute("data-baton-seen", animate ? "anim" : "done");
    if (animate) setTimeout(function () { sec.setAttribute("data-baton-seen", "done"); }, 1200);
    if (keyOf(sec) === "baton-sec-2") drawChart(animate);
  }
  var revealer = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      var enough = e.intersectionRatio >= 0.15 || e.intersectionRect.height >= window.innerHeight * 0.15;
      if (e.isIntersecting && enough) { revealer.unobserve(e.target); reveal(e.target, !reduce.matches); }
    });
  }, { threshold: [0, 0.05, 0.1, 0.15, 0.3] });

  // ----- the timeline draws in time order: grid, then marks left to right, bands growing -----
  function drawChart(animate) {
    var box = q(".st-key-baton-timeline"); if (!box || box.hasAttribute("data-baton-chart")) return;
    if (!animate) { box.setAttribute("data-baton-chart", "done"); return; }
    var tries = 0;
    (function go() {
      var gd = box.querySelector(".js-plotly-plot"), len = gd && gd._fullLayout && gd._fullLayout.xaxis._length;
      var points = box.querySelectorAll(".scatterlayer .point");
      if (!len || !points.length) { if (tries++ < 60) return requestAnimationFrame(go); box.setAttribute("data-baton-chart", "done"); return; }
      points.forEach(function (p) {
        var m = /translate\\(([-\\d.]+)/.exec(p.getAttribute("transform") || ""), x = m ? parseFloat(m[1]) : 0;
        p.style.setProperty("--baton-d", Math.round(200 + Math.max(0, Math.min(1, x / len)) * 800) + "ms");
      });
      box.querySelectorAll(".barlayer .point path").forEach(function (b) {
        var r = b.getBBox();
        b.style.setProperty("--baton-d", Math.round(200 + Math.max(0, r.x / len) * 800) + "ms");
        b.style.setProperty("--baton-len", Math.max(120, Math.round(r.width / len * 800)) + "ms");
      });
      box.setAttribute("data-baton-chart", "play");
      setTimeout(function () { box.setAttribute("data-baton-chart", "done"); }, 1300);
    })();
  }

  // ----- the drawer, below 1024px -----
  var lastFocus = null;
  function drawer() { return q('[data-testid="stSidebar"]'); }
  function focusables() {
    var d = drawer(); if (!d) return [];
    return Array.prototype.filter.call(d.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'),
      function (el) { return !el.disabled && el.getClientRects().length; });
  }
  function setMenu(open) { document.querySelectorAll(".baton-menu").forEach(function (b) {
    b.setAttribute("aria-expanded", open ? "true" : "false"); b.setAttribute("aria-label", open ? "Close menu" : "Open menu"); }); }
  function openDrawer() {
    lastFocus = document.activeElement; root.classList.add("baton-drawer-open"); setMenu(true);
    setTimeout(function () { var f = focusables()[0]; if (f) f.focus({ preventScroll: true }); }, 30);
  }
  function closeDrawer(giveBack) {
    if (!root.classList.contains("baton-drawer-open")) return;
    root.classList.remove("baton-drawer-open"); setMenu(false);
    var to = q(".baton-menu");
    if (giveBack !== false && to) to.focus({ preventScroll: true });
  }
  narrow.addEventListener("change", function () { closeDrawer(false); });
  shade.addEventListener("click", function () { closeDrawer(); });
  document.addEventListener("keydown", function (e) {
    if (!root.classList.contains("baton-drawer-open")) return;
    if (e.key === "Escape") { e.preventDefault(); closeDrawer(); return; }
    if (e.key !== "Tab") return;
    var f = focusables(); if (!f.length) return;
    var first = f[0], last = f[f.length - 1], at = document.activeElement;
    if (!drawer().contains(at)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && at === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && at === last) { e.preventDefault(); first.focus(); }
  }, true);

  document.addEventListener("click", function (e) {
    var t = e.target; if (!t || !t.closest) return;
    if (t.closest(".baton-menu")) { e.preventDefault(); if (root.classList.contains("baton-drawer-open")) closeDrawer(); else openDrawer(); return; }
    // Going to the Before you go page from the drawer: the drawer shuts, so the new page isn't covered.
    if (narrow.matches && t.closest(".st-key-open-before-you-go button")) { closeDrawer(false); return; }
    var link = t.closest(".baton-nav a"); if (!link) return;
    var sec = link.getAttribute("data-sec") || "sec-3";
    active = sec; lockUntil = Date.now() + 1000; moveIndicator();
    var openKey = link.getAttribute("data-open"), open = openKey && q(".st-key-" + openKey.replace(/[^A-Za-z0-9_-]/g, "-") + " button");
    if (open) open.click();  // a handled item: bring its card back, then the anchor scrolls to it
    if (narrow.matches) closeDrawer(false);
  });

  // ----- find new sections, keep the indicator and the backdrop's colours right -----
  var watched = new WeakSet(), queued = false;
  function refresh() {
    queued = false;
    var app = q('[data-testid="stApp"]');
    if (app) { var scheme = getComputedStyle(app).colorScheme; if (root.style.colorScheme !== scheme) root.style.colorScheme = scheme; }
    var m = main(); if (m) root.style.setProperty("--baton-main-left", m.getBoundingClientRect().left + "px");
    document.querySelectorAll('[class*="st-key-baton-sec-"]').forEach(function (sec) {
      if (watched.has(sec)) return;
      watched.add(sec); spy.observe(sec); spyAll.observe(sec);
      if (sec.hasAttribute("data-baton-seen")) return;
      if (seenKeys[keyOf(sec)]) reveal(sec, false); else revealer.observe(sec);
    });
    // The Before you go label rolls by its own height, which depends on how it wraps.
    document.querySelectorAll(".st-key-open-before-you-go button p").forEach(function (p) {
      if (p.offsetHeight) p.style.setProperty("--baton-roll-h", p.offsetHeight + "px");
    });
    moveIndicator(); onScroll();
  }
  new MutationObserver(function () { if (!queued) { queued = true; requestAnimationFrame(refresh); } })
    .observe(document.body, { childList: true, subtree: true });
  window.addEventListener("resize", function () { if (!queued) { queued = true; requestAnimationFrame(refresh); } });
  refresh();
})();
</script>"""


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
