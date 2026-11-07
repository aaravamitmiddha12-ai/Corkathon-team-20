# Baton: handoff

This work was pushed automatically so you can pick it up. It's a work in progress: the person
running it reached their Claude usage limit, so the snapshot may stop partway through a task. **The
"State when this was pushed" section below says exactly how far it got.**

## Get it running

```bash
git fetch origin
git switch Soleeu            # or: git switch -c Soleeu origin/Soleeu
python -m venv .venv         # Windows: py -3.13 -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt      # Streamlit must be 1.67 or newer
pytest
streamlit run app.py
```

## What this is

A visual and motion pass on the Streamlit app, which has been renamed **Baton**, plus the Baton logo
and a responsive, reactive layout. The rule for all of it: **no new product features**, only how
existing things look and move.

Where the commits are:

- `8863c91`: the visual pass (renamed to Baton, new timeline, tags, progress segments, limit bars, slim rows).
  This is **not on `main` yet**. Its owner hadn't decided whether to push it there.
- The commit at the tip of this branch: everything since, as a snapshot.

## What's done and what's left

1. **Done: logo.** `assets/`, `src/brand.py`, `tests/test_brand.py`. Shown on both screens, the browser tab
   and the downloadable record. Amber and the primary colour now match the brand sheet.
2. **Reactive, see the state below.** May be unstarted or partial. Details are in the next section.
3. **Not done unless the state below says so: audit.** Check every line of the brief below in the running
   app in a real browser, then try to break the logo and responsive work.
4. **Fix** whatever the audit reproduces.
5. **Then decide with the owner:**
   - Should this go on `main`?
   - Should `README.md`, `web/home.html` and `web/handover.html` be renamed too? They still say
     "Handover Check", on purpose, until that's decided.

`handoff/workflow-script.js` holds the exact instructions the agents were given for steps 2 to 4, which is
the most precise spec available. `handoff/check_baton.py`, `baton_launcher.py` and `check_logo.py` are the
Chrome checks (Playwright, with `channel="chrome"`). They have paths from the original machine hard-coded,
so edit those first.

## The reactive work (step 2)

**Responsive at every width**, tested at 320, 360, 390, 600, 768, 900, 1024, 1280, 1400 and 1920, with the
sidebar open and collapsed, and resizing live without a reload:

- Streamlit only stacks columns at 640px, so the 2:3 notes and list columns are cramped from about 768 to
  1000. Stack them at a sensible breakpoint.
- The top controls row must not wrap badly. The title sizes fluidly with `clamp()`.
- Timeline labels stay vertically aligned with the chart rows at every width (under 3px of drift), and the
  chart re-fits on resize and sidebar collapse. Ticks must not collide on phones: use fewer on narrow charts
  only if they'd overlap, and keep the 2-hour ticks on desktop. Asset names may truncate, asset IDs never.
- Card buttons, chips, due-by text and limit bars reflow cleanly. On slim rows the text may wrap on a phone,
  but "Open" stays on the row. Evidence tables scroll sideways in their own box.
- At least 44px targets on touch screens. The page body never scrolls sideways.

**Reacting to what the user does**, visual only:

- Hovering a timeline label highlights its chart row, and hovering a row highlights its label. Keyboard focus
  does the same. Neutral colour, not amber, 150ms. It must not break Plotly's tooltip or click-to-jump.
- When an item is handled, its timeline label changes straight away (for example muted with a small tick)
  **without re-running the timeline**, which sits outside the fragment. `motion_css` in `ui/home.py` already
  emits a per-render style block that can target labels by `href`. It must stay right after a fragment rerun,
  a full rerun, a shift switch, and when an item is reopened or its response changes.
- Clear hover, press and focus states on buttons and clickable rows.

## Rules and decisions already made

- A response must re-run only the fragment, not the timeline or notes.
- Amber means "notes and data disagree", plus the warning tick the brief asks for. Red is only for over limit
  or overdue. Other tags are neutral outlines with an icon.
- No gradients, glows, blur, emoji, or icons in headings. Motion is 150-260ms, ease-out, opacity and small
  movement only (the 1000ms flash is the one exception). Everything stops under `prefers-reduced-motion`.
- These are deliberate, not bugs:
  - Open and Collapse buttons on handled rows, so evidence stays reachable.
  - A drafted ticket stays open until it's closed.
  - The progress caption omits zero counts.
  - Sign-off sits directly under the cards.
  - Widgets stay Streamlit, with card text as HTML.
  - CSS names use `baton-`, not `tally-`.
- Dark mode isn't reachable as shipped: `.streamlit/config.toml` sets a custom theme, so the app stays light.
- Tests use a throwaway state folder (`tests/conftest.py`). Running the app writes to `data/state/`, which git
  ignores. A sign-off makes that handover read-only, so clear that folder for a clean demo.

The brand sheet itself (`Primary logo.pdf`) isn't in the repo. Ask its owner if you need it.

## The brief (read "Tally" as "Baton")

**1. Header.** Remove the "Matches expert ranking" badge and the explanatory subtitle. Title:
"Tally · Sat 7 Nov, 07:00 handover". Subtitle: "From D. Murphy · night shift".

**2. Timeline (Plotly).**
- Row labels: rank number (muted, monospace) + asset ID + short plain name (e.g. "1  FRZ-12  freezer"). Rows
  ordered by rank; "Other (n)" last.
- Notes = small diamond markers slightly ABOVE the row line, so they never overlap alert dots. Alerts = dots on
  the line: grey, or amber if after a note that said it was fine.
- For each clash: a translucent amber rounded band behind the row, from the reassuring note's time to the last
  alert after it.
- x-axis runs to the handover time with ticks every 2 h; add a dashed vertical line labelled "Handover 07:00".
- Legend below the chart: Alert · Alert after a note said it was fine · Note written · Said fine, kept alerting.
  Hover shows exact time and message.
- Clicking a row or its label scrolls to that item's card (anchor #card-<id>).
- Disable all Plotly transitions and animations.

**3. Tags and key.** All tags are neutral grey outline chips with a small icon. ONLY "Notes say OK, data
disagrees" uses amber fill. Red is used only for "over limit" or "overdue". Remove every other tag colour and
update the key to match.

**4. Progress.** Replace "n of 5 responded" with 5 equal numbered segments above the list. Empty = grey; Got it =
green with a tick; Dismissed = dashed outline with a minus icon; Ticket drafted = green with a ticket icon.
Caption: "4 of 5 handled · 3 got it · 1 dismissed · 1 ticket drafted".

**5. Cards.**
- For items with a numeric reading and a limit, add a thin distance-to-limit bar: fill = latest value as a share
  of the alarm limit (respect "direction"), amber tick at the warning level, red tick at the alarm limit, and
  text such as "8.1 / 9.0 mm/s" on the right. Fill turns red when over the limit.
- Handled items collapse into a slim one-line row: "✓ <asset> · <response> · <time>".
- "Sign off handover" appears below the list only when all 5 are handled.

**6. Performance.** Wrap the card list and progress segments in @st.fragment so responding to an item re-runs only
that section. Keep the timeline and notes outside it. Render cards as HTML via st.markdown(unsafe_allow_html=True)
so CSS classes apply.

**7. Styles and transitions (one injected style block).**
- Cards: border-color transition 150ms; stronger border on hover.
- Note lines and timeline labels: background-color transition 150ms on hover.
- `@keyframes tally-in { from { opacity:0; transform:translateY(6px) } }`
  `.tally-enter { animation: tally-in 240ms cubic-bezier(.2,0,0,1) both; animation-delay: calc(var(--i) * 50ms); }`
- `@keyframes tally-done { from { opacity:0; transform:translateY(-4px) } }` for the slim handled row, plus a
  fade-in for a newly filled progress segment.
- `@keyframes tally-flash`: a 2px amber outline fading to transparent over 1000ms, for the card reached via the
  timeline.
- `html { scroll-behavior: smooth; }`
- `font-variant-numeric: tabular-nums` on all times and readings; monospace for times and asset IDs.
- `@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; scroll-behavior:auto !important; } }`
- No gradients, glows, blur, emoji, or icons in headings.

**8. When things animate.**
- Entrance: add "tally-enter" (with --i = index) ONLY while `st.session_state.get("intro_done")` is False; then
  set it True, so it never replays on later clicks.
- On a response: set `st.session_state.just_changed = item_id`. Only that item's slim row gets tally-done and only
  its progress segment animates. Clear just_changed after rendering.
- Jump from timeline: the target card gets tally-flash once.
- Sign-off button: fades in with tally-in when the fifth item is handled.

All durations 150-260 ms, ease-out, opacity and small movements only. Run the existing tests and the app after the
changes and fix anything that breaks.

## Update: reactive step finished (Sat 07 Nov 2026)

Step 2 is done. Picked up on a second machine and checked in Edge (`BATON_CHANNEL=msedge`, same engine as Chrome).

- **Added:** `tests/test_row_state.py` (8 tests for the live timeline-label rules) and `handoff/check_reactive.py`
  (212 browser checks: every width with the sidebar open and shut, live resizing, linked hover and focus, live
  label state across responses, reopen, shift switch, reload and full reruns, listeners bound once, touch sizes).
- **Fixed:** on narrow phones Plotly turned the timeline times sideways and cut them off ("19:", "23:"). Times are
  now always level (`tickangle=0`), and the existing CSS hides every other one on narrow charts.
- **Check scripts:** no longer hard-code the original machine's paths. They find the repo from their own folder,
  put screenshots in a temp folder (or `BATON_SHOTS`), and take the browser from `BATON_CHANNEL`.
- **Results:** pytest 194 passed; `check_baton.py`, `check_logo.py` and `check_reactive.py` all pass.

Then **steps 3 and 4 (audit and fix)** were done the same day. The audit found and fixed: handled-row and
response times weren't monospace; asset IDs in the "Checked, not urgent" and record tables weren't monospace and
split at hyphens on phones (they now stay whole and the table scrolls); timeline times turned sideways on phones.

## Update: new style brief (sections 4 to 7), Sat 07 Nov 2026

The owner then asked for a restyle in four parts. Where it changes a rule above, the newer brief wins:

- **4. Style:** Linear/Stripe-like. Neutral colours with tokens on `:root` that switch with `light-dark()`;
  type steps 12/14/16/20/32/48; a 48px hero; small mono uppercase labels above each section ("02 · SHIFT AT A
  GLANCE"); hairline borders instead of grey boxes; soft shadows on cards only; content capped at 1200px.
  **Dark mode** is on: `.streamlit/config.toml` defines `[theme.light]` and `[theme.dark]`, so the app follows
  the computer and the ⋮ menu can switch it. `toolbarMode = "viewer"` hides the Deploy button.
- **Amber now means only** "notes and data disagree" / "said fine, kept alerting". The limit-bar warning tick,
  the evidence chart's warning line and the jump flash are neutral. Green = handled. Red = over limit/overdue.
- **5. Sidebar** (replaced the sticky header from section 4): Streamlit's own sidebar, fixed at 240px, holds the
  logo, the handover picker, the incoming engineer, section nav with the 5 items and status dots, progress, the
  Before you go button and the LLM toggle. Below 1024px it's a drawer opened from a slim top bar (Esc, backdrop
  click and nav clicks close it; focus is trapped). Scroll-spy uses IntersectionObserver; the indicator slides.
  "Needs you first" now comes before "What the notes say" (left column / first when stacked) to match the nav
  numbering, and "Also checked" moved below both columns as section 05.
- **6. Scroll:** sections reveal once as they enter view (replacing the on-load entrance); the timeline draws
  in time order once; a reading-progress bar; Back to top after one screen.
- **7. Hover polish:** text roll on nav items and the Before you go button; amber/green tint wipe on cards and
  sidebar items; timeline row hover (band sweep, other rows dim, marks grow); note hover (left bar, time nudge,
  its chart mark pulses once); a 4px pull on primary buttons; word-masked heading reveals; slight hero parallax.
  No framer-motion or Lenis (none installed, and Lenis needs the owner's approval). Everything stops or becomes
  plain colour/opacity under reduced motion.
- **Judgement calls:** "01 · START HERE" labels the hero, read as the page order the example implied. Chips don't
  react to hover, because they aren't clickable and a hover would suggest they are. Notes got `tabindex="0"` so
  their hover effect also works from the keyboard.

How it's built: `ui/components.py` holds the CSS and `NAV_SCRIPT` (sidebar, drawer, reveals, chart draw, progress,
Back to top, button pull, parallax); `ui/home.py`'s `TIMELINE_SCRIPT` handles the timeline and note hovers. The
sidebar's dots and count update without a rerun through per-render CSS rules (`nav_state_rules`), the same trick
as the timeline ticks.

Checks: `handoff/check_reactive.py` covers all of the above. On a machine without Chrome, set
`BATON_CHANNEL=msedge`.

## State when this was pushed

- **When:** Sat 07 Nov 2026 14:50
- **Why:** Pushed on request so the work can continue on a teammate's machine
- **Built on:** `8863c91 Rename the Streamlit app to Baton and do a visual and motion pass`
- **Tests at this moment:** 186 passed in 54.01s

This is a snapshot of files that may have been mid-edit. Don't assume it's finished or consistent
just because it's committed. Run the tests first.

### Uncommitted changes included, compared with `8863c91`

```
 .streamlit/config.toml     |   2 +-
 app.py                     |   9 +-
 assets/baton-favicon.png   | Bin 0 -> 1839 bytes
 assets/baton-favicon.svg   |   5 ++
 assets/baton-logo-dark.svg |   6 ++
 assets/baton-logo.svg      |   6 ++
 assets/baton-mark.svg      |   5 ++
 src/brand.py               |  14 +++
 src/charts.py              |  14 +--
 src/record.py              |   3 +
 tests/test_brand.py        | 220 +++++++++++++++++++++++++++++++++++++++++++++
 tests/test_components.py   |   2 +-
 ui/components.py           | 133 ++++++++++++++++++++++-----
 ui/home.py                 |  89 +++++++++++++++---
 14 files changed, 462 insertions(+), 46 deletions(-)
```

## Agent reports so far

Finished: logo

Started but not finished: reactive

### logo

I've put your logo into the app. The wordmark is built from the Space Grotesk 600 font outlines, not traced. All 186 tests pass (the 156 you had plus 30 new), the existing Chrome check passes 68 of 68 on port 8765, and a new Chrome check passes 87 of 87 on port 8770. Nothing is committed, the app on 8501 was not touched, and nothing under `web/`, `out/`, `README.md` or `data/state` changed.

**The logo files** (in a new `assets/` folder, transparent background, plain shapes with no text, fonts or links):
- `baton-logo.svg`: mark plus wordmark in Slate, Steel and Signal amber, for light backgrounds.
- `baton-logo-dark.svg`: Paper, `#5C606B` and amber, taken from the sheet's dark card.
- `baton-mark.svg`: the mark alone.
- `baton-favicon.svg` and `baton-favicon.png` (96×96): dark rounded square with corner radius 24, a Paper pill and an amber pill on top.

The pills were measured from the 3600px image, not by eye. Both are 240 × 82.5 source pixels, tilted −30.0°, and the far pill sits 120 along and 30 across from the near one.

**Wordmark:** I fitted the font's own outlines to the sheet. It is set at 312 source pixels with letter spacing of −0.035em plus the font's own kerning. Letting each letter move freely shifted none of them by more than 0.07px, so it is the same font and spacing as the sheet. The font file stays in the scratchpad, not the repo.

**Pixel difference** (each SVG drawn in Chrome at source scale on the sheet's card colour, compared with the matching crop; values 0–255 per channel):

| Asset | Average error | Pixels off by more than 32 | Best alignment shift |
|---|---|---|---|
| Light logo | 0.67 (mark 0.71, word 0.90) | 0.43% | 0, 0 |
| Dark logo | 0.60 | 0.39% | 0, 0 |
| Mark | 0.72 | 0.39% | 0, 0 |
| Favicon | 1.58 | 0.67% | 0, 0 |

Measured edge by edge, the outer pill edges are within 0.1 source pixels of the sheet. I looked at the side-by-sides and see no visible mismatch. The remaining differences come from two deliberate choices:
- **Letter corners:** the sheet's letter corners are slightly rounded (about 2 source pixels) by how it was rasterised. The font's corners are sharp, and I kept them sharp.
- **Seam around the amber:** the sheet's dark card has a thin dark line around the amber. Copying the sheet's layering gave a visible dark line at 30px tall, so I built the overlap so it has no seam. The amber edge differs from the sheet by about 0.25 source pixels.

**In the app:**
- **Screens:** the logo is the first thing on both the home screen and "Before you go", 30px tall, as its own element with the accessible name "Baton". The title "Baton · Sat 7 Nov, 07:00 handover" is unchanged and has nothing new inside it.
- **Theme:** the logo's colours switch on the app's active theme straight away, with no rerun. Very old browsers fall back to whichever file the server picks for the theme.
- **Browser tab:** `page_icon` is the PNG, found from the file's own location. A test runs the app from a different folder to prove it.
- **Printable record:** the logo sits above the heading, embedded in the file. A test confirms the saved and downloaded record contain no links at all. Opened offline at 1400px and 390px, it requests nothing beyond itself, and printing it to PDF with background graphics off keeps the logo in colour.
- **Theme colours:** primary is now Slate `#16181D`. Every amber is Signal amber, with the translucent amounts unchanged. The "data disagrees" tag is now solid amber with Slate text (8.2:1). To keep 4.5:1, the faded time and asset text on amber notes went from 0.65/0.6 opacity to 0.75 (now 5.7:1, 5.5:1 on hover).

I read screenshots of the home screen, Before you go and the record at 1400px and 390px, plus the dark-theme screens, the printed page and the logo enlarged at 1×. Adding space under the logo was the only fix the screenshots needed.

**Files changed:**
- Changed: `.streamlit/config.toml`, `app.py`, `src/charts.py`, `src/record.py`, `ui/components.py`
- New: `src/brand.py`, `tests/test_brand.py`, `assets/baton-logo.svg`, `assets/baton-logo-dark.svg`, `assets/baton-mark.svg`, `assets/baton-favicon.svg`, `assets/baton-favicon.png`
- Scratchpad: I added logo and favicon checks to `check_baton.py`, and changed its "no icon in the title" check to ignore the link icon Streamlit puts in every heading.

**Not verified, or worth knowing:**
- **Dark mode isn't reachable as shipped:** with this config the app is always light, even on a dark-mode computer, and the menu offers no theme switch. That was already the case before this change. I tested the dark logo by starting the app with a dark base theme.
- **Slate in a dark theme:** if a dark theme is ever turned on, the selected radio button and primary buttons almost disappear against the background. You'd need a separate dark primary colour, which I didn't add.
- **Real tab strip and old browsers:** headless Chrome has no tab strip. I confirmed the page's icon link serves the same PNG pixels and looked at previews at 16 to 48px. The old-browser fallback is covered by a unit test only.
- **The live app on 8501:** I didn't touch it. It uses these same files, so it may need a restart to show the new primary colour.
- **Paper printing:** checked by printing to PDF, not on a real printer.

Proof images and scripts are in `C:/Users/ksole/AppData/Local/Temp/claude/fb631dcb63e87003/d35fdfa8-230a-4ee6-8ffd-e18116660985/scratchpad/logo/`. The side-by-sides are `proof/*_sbs.png` and the app and record screenshots are in `app/`. The two Chrome checks are `C:/Users/ksole/AppData/Local/Temp/claude/fb631dcb63e87003/d35fdfa8-230a-4ee6-8ffd-e18116660985/scratchpad/check_baton.py` and `C:/Users/ksole/AppData/Local/Temp/claude/fb631dcb63e87003/d35fdfa8-230a-4ee6-8ffd-e18116660985/scratchpad/logo/check_logo.py`.
