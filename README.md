# Handover Check

At shift change, Handover Check reads the outgoing shift's free-text notes, the machine
alerts, the open tickets and the asset list. It shows the incoming engineer a ranked
**top 5**: what needs attention first, why, and one action for each.

Its key feature: it catches where the **notes contradict or understate the data**
("seems ok" while the freezer keeps alarming), and problems that have **no ticket**.

**Design principle:** plain, testable code decides the ranking. The LLM only
(a) tags note lines and (b) writes the explanation sentences. A human confirms each item.

---

## Setup (about 2 minutes)

Needs Python 3.11 or newer.

```bash
python -m venv .venv            # macOS: python3 -m venv .venv
# Windows:      .venv\Scripts\activate
#   (if PowerShell blocks scripts: Set-ExecutionPolicy -Scope Process Bypass)
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

streamlit run app.py      # opens http://localhost:8501
pytest                    # all offline
```

That's all you need for the demo. It runs **fully offline**: no API key and no network.

### Web home page

```bash
python -m src.export      # writes out/handover.json (and out/handover.js, the copy the pages load)
```

Then open `web/home.html` by double-clicking it: no server needed. Add `?stage` to the URL to force
the dark theme for a stage demo. Press `?` on the page for the keyboard shortcuts. Re-run the export
whenever the data or the ranking changes. `web/handover.html` is a minimal target for the page's
links, to be replaced by the full handover screen.

### Optional: live LLM

```bash
# Windows PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
# macOS/Linux:         export ANTHROPIC_API_KEY=sk-ant-...
# optional, default claude-sonnet-5-5:
#                      export LLM_MODEL=claude-sonnet-5-5

python -m src.pipeline --llm   # calls the LLM once and fills cache/
```

After that, the app's default **demo mode** reads `cache/` and shows the LLM's tags and
sentences without calling the API. That's the safe way to present: warm the cache
before judging, then demo offline. The sidebar toggle **Use live LLM** allows real
calls for anything not cached yet.

Never put the key in code. It is read only from the `ANTHROPIC_API_KEY` environment variable.

---

## 60-second demo script

| Time | Do | Say |
|---|---|---|
| 0:00 | App open. Point at the header. | "It's 07:00 Saturday. The night engineer wrote *'quiet enough night overall'*. Handover Check read the same notes plus 14 alerts, 6 tickets and the asset list." |
| 0:10 | Point at the 3 amber note lines on the left. | "Amber means the note said it was fine, but the data kept alarming afterwards. *'Seems ok'* at 21:05, yet the freezer alarmed 3 more times." |
| 0:20 | Card 1, FRZ-12. Read the tags. | "Top item: a -80 freezer with GMP samples. Four high alarms, each one warmer than the last. No ticket, and the latest alarm isn't acknowledged." |
| 0:28 | Open **Evidence** on card 1. | "Every claim cites its source: these exact alerts and note lines. The score is plain arithmetic. You can see each step." |
| 0:36 | Card 2, WFI loop. | "The notes call it 'a blip'. The data shows **three** excursions, no ticket, and a site rule saying it must be logged as a deviation within 24 hours." |
| 0:44 | Card 3 + sidebar sparkline for CH-2-P3. | "Chiller pump vibration is climbing toward its alarm line. The note says 'will log it tomorrow', so there's no ticket yet." |
| 0:50 | Click **Got it** on card 1. | "The engineer confirms each item. The tool ranks; a person decides." |
| 0:55 | Point at the badge, then open **Checked, not urgent**. | "It finds all five of the expert's items. The only difference is the order of the chiller and the HPLC. The noise (printer toner, a door alarm, a routine defrost) is pushed down, never deleted." |

---

## How it works

```
handover-sample-pack/  ->  load.py  ->  tag_notes.py  ->  detect.py  ->  score.py  ->  explain.py  ->  app.py
                                         (LLM or manual)   (rules)       (weights)     (LLM or template)
                                                                                         evaluate.py -> badge
```

| Module | Job |
|---|---|
| `src/load.py` | Reads the 5 input files into pandas. Note times before 07:00 belong to Sat 7 Nov. "Now" = 2026-11-07 07:00. |
| `src/tag_notes.py` | Each note line becomes `{asset_id, reassuring, mentions_future_action}`. `MANUAL_TAGS` is a hand-written dict; the LLM version uses the same function and caches to `cache/tags.json`. |
| `src/detect.py` | Plain rules per asset: repeats, trend_worsening, near_limit, no_open_ticket, clash, unacknowledged_latest, due_today. |
| `src/score.py` | The weighted score. All weights are in one `WEIGHTS` dict at the top. Top 5 + "Checked, not urgent". Nothing is dropped. |
| `src/explain.py` | Headline / why / action / citations per top item. The LLM sees **only that item's evidence**. Falls back to a template. Caches to `cache/explanations.json`. |
| `src/evaluate.py` | Compares our top 5 with `answer_key.csv` (matches x/5 + rank agreement). The ranking never sees the answer key. |
| `src/pipeline.py` | Runs everything once. Used by the app, the tests and the command line. |
| `src/llm.py` | The one place that calls the Anthropic API, plus the JSON cache. |
| `src/export.py` | Writes `out/handover.json` for `web/`. Adds `projected_limit_time`: a straight line through 3+ readings, extended to the alarm limit. Also `projected_limit_time_recent_pace`, the same from the last two readings; the page shows both as a range. |

### The score

```
base = criticality(low 1, medium 2, high 3) x severity(info 0.5, low 1, medium 2, high 3)
       x (1 + 0.5 x (alerts - 1))                       (0 if the asset had no alerts)
x1.5 if trend_worsening
+50 clash   +40 no_open_ticket   +30 due_today   +20 near_limit   +15 unacknowledged_latest
```

Severity is the asset's highest alert severity. Assets that appear in tickets but not in
`assets.json` (FRZ-09, LIMS) count as low criticality.

### Rule details (decisions we made, and why)

- **clash** needs a **medium or high** alert after the reassuring note. Without this, AHU-4
  would be a false clash: the note at 19:20 said "within limits", and an *info* reading
  logged 2 minutes later says the same thing. The door alarm (low) after "closed it" is also
  not a clash.
- **no_open_ticket** fires when something is wrong (a medium+ alert, **or a note that raises
  a concern**, i.e. is not reassuring) and there is no open, scheduled or approved ticket. A
  reassuring note on its own ("cleaners propped the door open... closed it") doesn't need a ticket.
- **trend_worsening** means each reading is worse than the one before. For a ceiling limit,
  that means higher. This covers both "further past the limit" (FRZ-12) and "heading toward
  the limit" (CH-2-P3). WFI went 1.6 -> 1.5 -> 1.4: still over the limit, but not worsening.
- **near_limit** means the latest reading is within 15% of the alarm limit and **not yet past
  it** (CH-2-P3: 8.1 vs 9.0). Readings already past the limit are covered by severity.
- **due_today** only counts live tickets (open / scheduled / approved).

### Result against the expert

| | Expert | Handover Check | Score |
|---|---|---|---|
| 1 | FRZ-12 | FRZ-12 | 138.75 |
| 2 | WFI-LOOP-1 | WFI-LOOP-1 | 123 |
| 3 | HPLC-07 | CH-2-P3 | 87 |
| 4 | CH-2-P3 | HPLC-07 | 30 |
| 5 | BAL-03 | BAL-03 | 30 |

**5/5 of the expert's items, 3/5 in the same position, rank agreement (Spearman) 0.90.**
The one swap is a good talking point. The formula ranks the chiller above the HPLC because
the chiller is getting worse with no owner. The HPLC already has a P2 ticket and a vendor
booked, and the expert ranked it higher because it blocks a batch release. We did not tune
the weights to force the order.

### LLM guard rails

- Structured outputs: the API must return JSON that matches our schema.
- Current Claude models no longer accept a `temperature` setting, so we don't send one.
  Results stay stable because of the strict schema plus the cache.
- Tagging: an `asset_id` the LLM returns that isn't a known asset becomes `null`.
- Explanations: citations that aren't in the evidence are dropped. If the text contains a
  **number that isn't in the evidence** (signs count; dates and ids don't vouch for numbers),
  or claims **more alerts than there were**, the answer is rejected and the template is shown.
  This is a light check, not a proof: it catches invented values, not every wrong sentence.
- Any failure (no key, offline, rate limit, refusal) falls back to manual tags or templates,
  with a short notice in the app. The app never crashes because of the LLM.
- On supported models, the request opts into the API's server-side refusal fallback.

---

## Project layout

```
app.py                     Streamlit screen
web/                       home page + minimal handover page (plain HTML/CSS/JS, bundled fonts)
out/                       generated by `python -m src.export`
src/                       pipeline modules (see table above)
tests/test_pipeline.py     ranking + rule tests (manual tags, no API)
tests/test_llm.py          LLM path with a fake model (no network)
tests/test_robustness.py   odd data (blank cells, unknown severities, bad cache files) + the number guard
handover-sample-pack/      input data + answer key
cache/                     LLM answers (created by `python -m src.pipeline --llm`)
.streamlit/config.toml     theme colour
```
