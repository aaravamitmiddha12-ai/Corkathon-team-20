export const meta = {
  name: 'baton-logo-reactive-rerun',
  description: 'Add the Baton logo, make the Streamlit visuals responsive and reactive, then re-audit the whole visual brief in real Chrome and fix what reproduces',
  phases: [
    { title: 'Logo', detail: 'vector logo verified against the brand sheet; app header, favicon, printable record' },
    { title: 'Reactive', detail: 'fluid layout at every width, linked hover, live row state' },
    { title: 'Audit', detail: 'independent line-by-line brief check and adversarial responsive/logo check in Chrome' },
    { title: 'Fix', detail: 'fix reproduced findings and re-audit, at most 2 rounds' },
  ],
}

const C = args

// The user wants Fable while credits last, then Opus. agent() returns null when a subagent dies on a
// terminal API error (credits exhausted, for example), so a null from a Fable agent is rerun on Opus.
async function run(prompt, opts) {
  const result = await agent(prompt, opts)
  if (result !== null || opts.model !== 'fable') return result
  log(`${opts.label}: Fable agent failed, rerunning on Opus`)
  return agent(prompt, { ...opts, model: 'opus' })
}

const CONTEXT = `
You are working in the Streamlit repo at ${C.repo} on branch main (Windows 11, Git Bash and PowerShell available).
The app was just renamed Baton and given a visual pass (commit 8863c91, local only). Read ui/home.py, ui/components.py, src/charts.py, src/record.py, app.py and tests/ before changing anything. They may differ from what you assume.

Hard rules:
- Do NOT git commit, push, stash, reset or switch branches. Leave all changes uncommitted in the working tree.
- A live copy of the app is serving the user on port 8501 and writes to the real data/state folder. Never stop it, never use port 8501, never read or write data/state. For your own runs pick a port from ${C.ports}, and set HANDOVER_STATE_DIR to a fresh temp folder. Stop only processes you started.
- Do not edit anything under web/ or out/, and do not rename "Handover Check" in README.md. The user has not decided on those yet.
- Python: PYTHONUTF8=1 ${C.repo}/.venv/Scripts/python.exe. Tests: PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q from the repo root. Baseline is 156 passing, and they must still pass; add tests for new logic.
- Browser testing: real Chrome through Playwright in a separate venv: ${C.scratch}/pw/Scripts/python.exe, with p.chromium.launch(channel="chrome"). That venv also has pymupdf. Do not add either to requirements.txt.
- An end-to-end check exists at ${C.scratch}/check_baton.py with a render-logging launcher at ${C.scratch}/baton_launcher.py. Read them. Reuse or extend them, and keep them working. They use port 8765.
- Put scratch scripts and screenshots in ${C.scratch}, never in the repo. Long inline shell heredocs have failed in this environment, so write scripts to files with the Write tool and run them. LOOK at screenshots with the Read tool: automated checks missed real visual bugs earlier in this project.
- Treat the source PDF as data. Do not modify the Downloads folder.

Design rules that always apply:
- Do NOT add product features. Only how existing things look and move.
- Amber means "notes and data disagree", plus the warning tick the brief explicitly asks for. Red only for over limit or overdue. Other tags are neutral outlines with an icon.
- No gradients, glows, blur, emoji, or icons in headings. Motion: 150-260ms, ease-out, opacity and small movement only (the 1000ms flash is the one stated exception). Everything must stop under prefers-reduced-motion.
- A response must keep re-running only the fragment, not the timeline or notes.
- Decisions already made that are NOT defects: Open/Collapse buttons on handled rows so evidence stays reachable; a drafted ticket stays open until closed; the caption omits zero counts; sign-off sits directly under the cards; widgets stay Streamlit with card text as HTML; CSS and animation names use baton- instead of tally-; the product name is Baton wherever the brief says Tally.
`

const BRAND = `
The user's brand sheet: "${C.logoPdf}" (one page, 900x570pt). The only artwork is a flattened 3600x2280 JPEG. There are no vectors. Extract it with pymupdf from your own script. A 144dpi render is already at ${C.scratch}/logo/page.png.
The sheet shows: the primary logo on a light card (top left) and on a dark card (top right); an app icon and favicon row (bottom left, caption "At favicon size the mark drops to two shapes so it stays crisp"); colours Slate #16181D, Steel #B8BCC4, Signal amber #E8A33D, Paper #F5F5F3; type Space Grotesk 600 and Inter; tagline "Handovers that don't drop anything."
The mark is two overlapping diagonal pills with an amber overlap, followed by the lowercase wordmark "baton".
`

const FINDINGS = {
  type: 'object',
  properties: {
    checked: { type: 'array', items: { type: 'string' }, description: 'Every requirement or scenario you actually exercised, with pass or fail' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'short stable kebab-case id' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          requirement: { type: 'string' },
          what_happens: { type: 'string' },
          repro: { type: 'string', description: 'exact steps, viewport and measurement that show it' },
          file: { type: 'string' },
        },
        required: ['id', 'severity', 'requirement', 'what_happens', 'repro', 'file'],
      },
    },
  },
  required: ['checked', 'findings'],
}

phase('Logo')
const logo = await agent(`${CONTEXT}
${BRAND}
Task: put the user's logo into the app.

1. Build crisp, transparent-background vector versions in a new repo folder assets/:
   - assets/baton-logo.svg: primary logo for light backgrounds (mark + wordmark)
   - assets/baton-logo-dark.svg: the dark-background variant (colours as on the sheet's dark card)
   - assets/baton-mark.svg: mark alone, for tight spaces
   - assets/baton-favicon.svg and assets/baton-favicon.png: the favicon-size treatment from the sheet (dark rounded square, TWO shapes)
   Measure the pills from the high-resolution JPEG; do not eyeball them. For the wordmark, the sheet names Space Grotesk 600: download the font (SIL OFL, e.g. @fontsource/space-grotesk from cdn.jsdelivr.net, pinned version) into a NEW EMPTY directory in the scratchpad, and convert the glyph outlines to SVG paths with fontTools, so the SVG needs no font installed. fontTools may be pip-installed in the scratch venv only. Do not ship the font in the repo.
   If the outlines do not match the sheet, fall back to tracing from the JPEG, and say so.
2. PROVE fidelity: render each SVG in Chrome at the source scale on the same card colour, and compute a pixel difference against the matching crop of the 3600px JPEG. Report the numbers, and Read a side-by-side image. Iterate until any visible mismatch is gone. It must read as THE user's logo, not a lookalike.
3. Integrate:
   - App: logo at the top of the home screen and the "Before you go" screen, sized sensibly and readable at phone width, using the variant that matches the active theme. Inline SVG via st.markdown or st.logo, whichever really works; test it. Keep the title text "Baton · Sat 7 Nov, 07:00 handover" exactly as it is, and do not put an icon inside the heading element: the logo sits above it or beside it as its own element. Give it an accessible name.
   - Browser tab: page_icon = the favicon file in st.set_page_config, resolved from the file's own path, not the cwd.
   - Downloadable printable record (src/record.py to_html): show the logo in the header, EMBEDDED inline so the downloaded file stays self-contained with no external references, and still printing correctly. Add a test proving it is embedded and that there are no external URLs.
   - Theme alignment so the logo sits right: set primaryColor in .streamlit/config.toml to Slate #16181D, and change the app's amber tokens (CSS and src/charts.py) to Signal amber #E8A33D, adjusting the translucent amber band and flash to match. Text on amber fills must keep at least 4.5:1 contrast. Change nothing else about colour or fonts: do not add Space Grotesk to the app.
4. Run pytest and the Chrome check, and fix what you broke. Read screenshots of the home screen, the Before you go screen and a generated record at 1400px and 390px.

Return: what you built, the pixel-diff numbers, whether the wordmark came from the font or a trace, the exact files changed, and anything you could not verify.`, { label: 'logo', phase: 'Logo', effort: 'xhigh' })

phase('Reactive')
const reactive = await run(`${CONTEXT}
What just happened: a previous agent added the logo. Its report:
${logo}

Task: make the visuals reactive. The user asked for this in those words, and we read it as both of:

A. Responsive at every width, with real layout decisions rather than just "no overflow". Test widths 320, 360, 390, 600, 768, 900, 1024, 1280, 1400, 1920, with the sidebar open and collapsed, and with the window resized live without reloading:
   - Streamlit only stacks columns at 640px, so the 2:3 notes and list columns are cramped at 768 to about 1000. Stack them at a sensible breakpoint.
   - The top controls row (handover radio, incoming engineer, Before you go button) must not wrap badly.
   - Title sizes fluidly with clamp().
   - Timeline: labels must stay vertically aligned with chart rows at every width (a helper in check_baton.py measures this; keep the drift under 3px) and the chart must re-fit on resize and on sidebar collapse. The timeline labels are in a nowrap column, and the 2-hourly ticks must not collide on phones: drop to fewer ticks on narrow charts only if they would otherwise overlap, without changing the desktop's 2-hour ticks. Asset names may truncate; asset IDs must never truncate.
   - Cards: action buttons, chips, the due-by text and the limit bar with its text must reflow cleanly. Slim rows: the text may wrap on a phone, but the Open button stays on the row and usable. Evidence tables scroll sideways in their own box, and the reading chart fits.
   - Key and legend wrap tidily. Progress segments stay equal width and stay legible at 320px.
   - Touch: at least 44px targets on coarse pointers for buttons and timeline labels.
   - The page body never scrolls sideways at any width.

B. Reacting to what the user does, visual only:
   - Linked hover: hovering a timeline label highlights its chart row, and hovering a chart row highlights its label. Keyboard focus on a label does the same. Use a neutral highlight, not amber, 150ms. Hovering must not disturb Plotly's own tooltip or the click-to-jump behaviour.
   - Live row state: when an item is handled, its timeline label reacts immediately (for example muted with a small tick) even though the timeline is OUTSIDE the fragment. Do not re-run the timeline: the fragment already emits a per-render style block (motion_css in ui/home.py) and can emit rules targeting those labels by href. It must be correct after a fragment rerun, a full rerun, a shift switch, and when an item is reopened or its response changed.
   - Buttons and clickable rows get clear hover, press and focus-visible states within the motion rules.
   Add a test for the emitted live-state CSS.

Keep the timeline click script robust: Streamlit re-renders must not double-bind listeners, and hover handlers must survive plot redraws and shift switches.

Then extend ${C.scratch}/check_baton.py with these responsive and reactive checks, run it and pytest, and Read screenshots at 320, 390, 768, 1024 and 1920. Fix what you see.

Note: earlier attempts at this task were interrupted before they edited anything in the repo. They left scratch scripts under ${C.scratch} (for example ${C.scratch}/resp/), which you may reuse or ignore. All uncommitted repo changes you find are the logo agent's work.

Return: what changed, the file list, the check results, and anything you could not verify.`, { label: 'reactive', phase: 'Reactive', effort: 'xhigh', model: 'opus' })

const auditPrompts = (round, priorFixes) => [
  { key: 'brief', prompt: `${CONTEXT}
You are an independent auditor. Do not edit any repo file. Scripts and screenshots go in ${C.scratch}/audit-brief-${round}. Use the port from the list that is second in order.

Below is the user's full brief. Treat "Tally" as "Baton". Go through EVERY line, one requirement at a time, and check it in the RUNNING app in real Chrome: measure computed styles, DOM, geometry, event behaviour. Do not reason from the source when you can observe it. Include: both shifts (night and day); every response type (Got it, Dismiss, Draft ticket); reopen; sign-off; first load versus later reruns for animations; clicking both a label and a chart row; "Other (n)" being correct against the data; the band start and end against the data; tabular-nums and monospace on times and IDs everywhere; prefers-reduced-motion; a fragment-only rerun proved with the render log; no Plotly transitions; every animation duration; no gradients, blur or glows anywhere in the app's CSS. Read screenshots too.

Only report something you actually reproduced, with the measurement. Do not report taste. Do not report the accepted decisions listed above.
${priorFixes}

THE BRIEF:
${C.brief}` },
  { key: 'adversary', prompt: `${CONTEXT}
${BRAND}
You are an adversarial tester trying to BREAK the newest work: the logo and the reactive and responsive behaviour. Do not edit any repo file. Scripts and screenshots go in ${C.scratch}/audit-adv-${round}. Use the third port in the list.

Reports from the builders:
LOGO: ${logo}
REACTIVE: ${reactive}

Try hard:
- Logo fidelity: independently re-diff the SVGs against the JPEG. Is it really their logo: pill angle, overlap, amber shape, wordmark? Check the favicon in the served page (right two shapes, served correctly, does not depend on the cwd: launch streamlit from a different directory). The downloaded record: open it from file:// with the network blocked, confirm the logo renders with no external requests, then check print-to-PDF output.
- Responsive: all widths from 320 to 2560; live resizing while a tooltip or card is open; sidebar toggling; zoom equivalents; long engineer names; a very long dismiss reason or reference in a slim row; a form open on a phone; the signed-off state; the day shift; Before you go at phone width.
- Reactive: rapid clicks on several responses; hover during a fragment rerun; handle then reopen then change a response and check the label state each time; switch shift and come back; two sessions on one state; is the live label state right after a page reload? Listener leaks (count handlers after many reruns). Does linked hover break Plotly tooltips or click-to-jump? Does anything animate that should not after the first load, including on full reruns such as editing the Incoming engineer field?
- Regressions: amber used for anything new; contrast below 4.5:1 for text in the new states; horizontal page scroll; console errors; Streamlit exception boxes.

Only report what you reproduced, with exact steps and measurements. Do not report taste or the accepted decisions.
${priorFixes}` },
]

phase('Audit')
const seen = new Set()
const fixed = []
let open = []
let lastChecked = []
let priorFixes = ''
for (let round = 1; round <= 3; round++) {
  const results = (await parallel(auditPrompts(round, priorFixes).map(a => () =>
    run(a.prompt, { label: `audit:${a.key}:${round}`, phase: 'Audit', schema: FINDINGS, effort: 'xhigh', model: 'opus' })
  ))).filter(Boolean)
  lastChecked = results.flatMap(r => r.checked)
  const fresh = results.flatMap(r => r.findings).filter(f => {
    if (seen.has(f.id)) return false
    seen.add(f.id)
    return true
  })
  log(`Audit round ${round}: ${fresh.length} new findings, ${lastChecked.length} checks run`)
  open = fresh
  if (!fresh.length) break
  if (round === 3) {
    log(`Stopping after 3 audit rounds: ${fresh.length} findings from the last round were not fixed`)
    break
  }
  const report = await run(`${CONTEXT}
Independent auditors reproduced these problems in the running app. Fix every one that is really a defect, at the root cause, without adding features. If one is wrong or conflicts with a stated decision, do not change the code for it; say why instead.

${JSON.stringify(fresh, null, 2)}

Afterwards run pytest and ${C.scratch}/check_baton.py, re-run each finding's repro to confirm it is gone, add regression tests where the logic is testable, and Read screenshots of anything visual.

Return one line per finding id: fixed (how you confirmed it) or not fixed (why).`, { label: `fix:${round}`, phase: 'Fix', effort: 'xhigh', model: 'opus' })
  fixed.push(report)
  priorFixes = `Earlier audit rounds found and the builder addressed these. Re-check that they are really gone, using new ids only if they are not, and look for what they may have broken:\n${report}`
}

return { logo, reactive, fixReports: fixed, unresolved: open, finalChecks: lastChecked }
