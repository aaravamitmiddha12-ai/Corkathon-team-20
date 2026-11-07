# Handover Check

At shift change, Handover Check reads the outgoing shift's free-text notes, the machine
alerts, the open tickets and the asset list. It shows the incoming engineer what needs
attention first, why, and by when. It catches where the **notes contradict or understate the
data** ("seems ok" while the freezer keeps alarming), and problems that have **no ticket**.

**Design principle:** plain, testable code decides the ranking. The LLM only (a) tags note
lines and (b) writes the explanation text. A person responds to every item and signs off.

## The five features

1. **Ranked handover with due-by times.** A top 5 with "Due by Sun 03:09 · 20 h left"
   (red "Overdue by 2 h" when late), worked out from asset rules, ticket due dates and
   calibration dates.
2. **Notes vs data check.** Amber marks every place where a note said it was fine but a
   medium or high alert came after it. Problems with no open ticket are tagged "No ticket".
3. **Before you go.** The outgoing engineer reviews the clashes and missing tickets from their
   shift ("It's fine - here's why" / "It's a real issue" / "I didn't know about this") and leaves
   a one-line comment for the incoming engineer.
4. **Respond.** Each card has **Got it**, **Dismiss with reason** and (for "No ticket" items)
   **Draft ticket**. Dismissals carry forward to later handovers, and come back if things get worse.
5. **Handover record.** When every top-5 item has a response, **Sign off handover** saves a
   read-only record and offers a printable HTML download.

There is nothing else: no login, upload, settings, history or chat.

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
pytest                    # 125 tests, all offline
```

The first time you run Streamlit it may ask for an email address in the terminal. Press Enter to skip.
The app runs **fully offline** in demo mode: no API key and no network.

### Web home page

```bash
python -m src.export                # writes out/handover.json (and out/handover.js, the copy the pages load)
python -m src.export --shift day    # the Sat 19:00 handover instead
```

Then open `web/home.html` by double-clicking it: no server needed. Add `?stage` to the URL to force
the dark theme for a stage demo. Press `?` on the page for the keyboard shortcuts. Re-run the export
whenever the data, the ranking or the saved responses change. `web/handover.html` is a minimal target
for the page's links; the full handover screen with responses and sign-off is the Streamlit app.

### Reset the demo

Responses, dismissals, reviews and sign-offs are saved in `data/state/` and survive restarts.
To start again, run one of these (they keep `records/.gitkeep`), then **refresh the browser tab**:

```bash
# Windows PowerShell
Remove-Item data/state/*.json; Get-ChildItem data/state/records -Exclude .gitkeep | Remove-Item
# macOS / Linux
rm -f data/state/*.json; find data/state/records -type f ! -name .gitkeep -delete
```

The files are recreated empty on the next run.

### Optional: live LLM

**The app runs offline for now:** it never calls an AI service, and shows the AI answers saved in `cache/`
(or its own templates). To fill or refresh `cache/`, run the pipeline with a key: **Anthropic** (Claude, paid)
or **Google Gemini** (has a free tier, from aistudio.google.com). Each answer is saved, so it's only asked for
once. On Gemini's free tier, a busy or used-up model moves to `gemini-3.1-flash-lite`.

1. **A file (simplest):** create `.streamlit/secrets.toml` (git ignores it), for example:
   `GEMINI_API_KEY = "..."` and `LLM_PROVIDER = "gemini"`, or `ANTHROPIC_API_KEY = "sk-ant-..."`.
   See `.streamlit/secrets.toml.example`. With both keys, `LLM_PROVIDER` picks; without it, Anthropic goes first.
2. **Environment variables**, which win over the file:

```bash
# Windows PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
# macOS/Linux:         export ANTHROPIC_API_KEY=sk-ant-...
# optional, default claude-sonnet-5-5:   LLM_MODEL=...

python -m src.pipeline --llm                 # Sat 07:00 handover: fills cache/
python -m src.pipeline --llm --shift day     # Sat 19:00 handover
```

Restart the app after adding or changing the key. Never commit a key: `.streamlit/secrets.toml` and `.env` are
in `.gitignore`.

---

## Demo script (about 90 seconds)

Start from a reset state (see above). "Sat 07:00 handover" is selected.

| Time | Do | Say |
|---|---|---|
| 0:00 | Point at the timeline and the notes. | "07:00 Saturday. The night engineer wrote *'quiet enough night overall'*. Amber dots are alerts that came **after** a note said it was fine." |
| 0:12 | Card 1, FRZ-12. | "A -80 freezer with GMP samples: 4 alarms, each warmer than the last, and no ticket. The notes said 'seems ok'." |
| 0:20 | Card 2, WFI loop. Point at "Due by Sun 03:09 · 20 h left". Open **Evidence**. | "The notes call it a blip. The data shows three separate excursions. The site rule gives 24 hours to log a deviation, so it's due by 03:09 tomorrow. Every claim cites its source in this table, and the chart shows each excursion." |
| 0:35 | Card 3, CH-2-P3: **Draft ticket**. | "Vibration is climbing toward the alarm line with no ticket. One click drafts the ticket with the evidence attached." |
| 0:45 | Card 1: **Dismiss with reason** → Known sensor or instrument fault, 24 hours. Card 3: **Dismiss** → Already handled, 24 hours. **Got it** on the rest. **Sign off handover**. | "Every item needs a response before sign-off. The record is saved and printable." |
| 1:05 | Switch to **Sat 19:00 handover**. | "Twelve hours later. FRZ-12 kept alarming at the same values. It was dismissed as a sensor fault, so it carries over quietly, at the bottom with who dismissed it and why." |
| 1:15 | Card 1, CH-2-P3: the red box. | "The chiller was dismissed too, but it got **worse**: 8.9 against 8.1 mm/s. The dismissal is ignored and it's back on top." |
| 1:25 | **Outgoing engineer? Before you go →** | "Before leaving, the day engineer sees what they wrote next to what the data shows, and says whether it's real. That comment appears on the incoming engineer's card." |

---

## How it works

```
handover-sample-pack/  ->  load  ->  tag_notes  ->  detect + due  ->  score  ->  explain  ->  ui/
 (night)  day_shift/       (shifts)  (LLM/manual)    (rules)          (weights)   (LLM/template)
                                       data/state/ (reviews, responses, dismissals) feeds score
```

| Module | Job |
|---|---|
| `src/load.py` | Reads one shift's files into pandas. Defines the two shifts (`night`: Sat 07:00 handover, `day`: Sat 19:00 handover). |
| `src/tag_notes.py` | Each note line becomes `{asset_id, reassuring, mentions_future_action}`. Hand-written tags for both sample shifts; the LLM version uses the same function and caches to `cache/tags.json`. |
| `src/detect.py` | Plain rules per asset: repeats, getting worse, near limit, no ticket, clash, not acknowledged, due soon, rule breaches. Limits, units and direction come from `assets.json`. |
| `src/due.py` | Due-by: the earliest of an asset rule (e.g. first excursion + 24 h deviation window) and live ticket due dates (including calibration). |
| `src/score.py` | The weighted score (all weights in one `WEIGHTS` dict), top 5 and the rest. Nothing is dropped. |
| `src/explain.py` | Headline, 2-3 bullets and one action per item. The LLM sees **only that item's evidence**. Falls back to a template. |
| `src/review.py` | "Before you go" reviews (`data/state/outgoing_reviews.json`). |
| `src/respond.py` | Got it / Dismiss / Draft ticket (`responses.json`, `dismissals.json`) and the carry-forward rules. |
| `src/record.py` | Sign-off: a JSON record and a printable HTML page in `data/state/records/`. |
| `src/charts.py` | Plotly charts: the shift timeline and each card's reading chart. |
| `src/evaluate.py` | Compares the Sat 07:00 top 5 with `answer_key.csv`. The ranking never sees the answer key. |
| `src/export.py` | Writes `out/handover.json` for `web/`. Adds `projected_limit_time`: a straight line through 3+ readings, extended to the alarm limit. Also `projected_limit_time_recent_pace`, the same from the last two readings; the page shows both as a range. |
| `ui/`, `app.py` | The Streamlit screens: home and "Before you go". |

### The score

```
base = criticality(low 1, medium 2, high 3) x severity(info 0.5, low 1, medium 2, high 3)
       x (1 + 0.5 x (alerts - 1))                     (0 if the asset had no alerts)
x1.5 if getting worse
+50 clash   +40 no ticket   +30 due before the end of the incoming shift
+20 close to alarm limit   +15 latest alert not acknowledged
+20 if the outgoing engineer said "It's a real issue"   ("It's fine" never lowers the score)
x0.3 if an earlier dismissal still applies (and it can't be in the top 5)
```

### Carry-forward rules for dismissals

A dismissal is saved per asset with the worst reading at that time and the rule breaches that
were already known. At a **later** handover:

- **Still applies** (not expired, and no worse): score x0.3. The item moves to "Carried over from
  last handover" with a grey line: *Previously dismissed: reason · who · when*.
- **Now worse**: the latest reading is worse than the worst reading when it was dismissed, a
  new rule breach appeared (past the alarm or warning limit, or overdue), or the next outgoing
  engineer marked it "It's a real issue" in Before you go. The dismissal is ignored, the item
  ranks normally and the card says **"Dismissed earlier, now worse"**. Dismissing it again
  keeps that history on the card and in the record.
- **Expired**: "This handover only"; "24 hours" once 24 hours have passed since the handover it
  was made at; "Until a ticket is closed" once the referenced ticket (the reference is required;
  case doesn't matter) is closed or resolved. If that ticket id isn't in the ticket list, the
  dismissal lasts only while the asset still has a live ticket.

"Draft ticket" never replaces a response you already gave, and a handover can only be signed off once.

Expiry runs on the handover clock (the dismissal was made at the Sat 07:00 handover), so the demo
behaves the same on any day. Responses and sign-offs record the real time.

### Rule details (decisions we made, and why)

- **clash** needs a **medium or high** alert after the reassuring note. Otherwise an info reading
  logged 2 minutes after "within limits" (AHU-4) would count as a contradiction.
- **no ticket** fires when something is wrong (a medium+ alert, or a note that raises a concern)
  and there's no open, scheduled or approved ticket.
- **getting worse** means each reading is worse than the one before, on the side `assets.json`
  marks as bad (`direction`: above or below). CR-B2's pressure falling 11.2 → 10.4 → 9.6 Pa
  against a 10 Pa floor is getting worse.
- **near limit** means within 15% of the alarm limit and not yet past it.
- **Charts:** amber is used only for "notes say OK, data disagrees". The spec asked for an amber
  warning line too, so we drew the warning level in **orange** to keep amber's single meaning.
  WFI excursions are short separate events, so they're drawn as separate spikes from the limit
  line, never joined up.

### Result against the expert (Sat 07:00 handover)

**5/5 of the expert's items, 3/5 in the same position, rank agreement (Spearman) 0.90.**
The one swap: the formula ranks the chiller (getting worse, no owner) above the HPLC (already
ticketed, vendor booked). The expert ranked the HPLC higher because it blocks a batch release.
We did not tune the weights to force the order. The Sat 19:00 shift has no expert answer key.
The score is printed by `python -m src.pipeline`; the app itself doesn't show it.

### LLM guard rails

- Structured outputs: the API must return JSON that matches our schema. Current Claude models
  don't accept `temperature`, so results are kept stable by the schema and the cache.
- Explanations: citations that aren't in the evidence are dropped. If the text uses a number
  that isn't in the evidence (signs count; dates and ids don't vouch for numbers), or claims
  more alerts than there were, the answer is rejected and the template is shown.
- Any failure (no key, offline, rate limit, refusal) falls back to manual tags or templates.

---

## Project layout

```
app.py                         Streamlit entry point (shift selector, routing)
ui/home.py                     home screen: timeline, notes, cards, lists, sign-off
ui/before_you_go.py            the outgoing engineer's review page
ui/components.py               CSS, tags, the colour key
web/                           home page + minimal handover page (plain HTML/CSS/JS, bundled fonts)
out/                           generated by `python -m src.export`
src/                           pipeline modules (see table above)
handover-sample-pack/          Sat 07:00 handover data + answer key + assets.json
handover-sample-pack/day_shift Sat 19:00 handover data (carry-forward demo)
data/state/                    saved reviews, responses, dismissals, records (not committed)
tests/                         125 offline tests, including UI tests with Streamlit's AppTest
```
