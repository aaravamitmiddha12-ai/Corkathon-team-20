"""Runs the whole pipeline for one handover. Used by the app, the tests and the command line.

    python -m src.pipeline                  # Sat 07:00 handover, demo mode (offline)
    python -m src.pipeline --shift day      # Sat 19:00 handover
    python -m src.pipeline --llm            # live LLM, fills cache/ for offline demos
"""

import sys
from dataclasses import dataclass

import pandas as pd

from src import llm, respond, review
from src.detect import Finding, detect
from src.evaluate import evaluate
from src.explain import explain_all, template_explanation
from src.load import DEFAULT_SHIFT, NO_ASSET, Pack, load_all
from src.score import ScoredItem, rank
from src.tag_notes import tag_notes


@dataclass
class Result:
    pack: Pack
    notes: pd.DataFrame            # note lines with their tags
    findings: dict[str, Finding]
    top: list[ScoredItem]          # "Needs you first"
    rest: list[ScoredItem]         # everything else, including carried-over dismissals
    explanations: dict[str, dict]  # for every item, top or not
    evaluation: dict | None        # None when the shift has no expert answer key
    warnings: list[str]
    mode: str
    reviews: dict                  # outgoing engineer's reviews for this shift
    responses: dict                # incoming engineer's responses for this handover
    review_items: list[Finding]    # what "Before you go" asks about

    @property
    def shift(self):
        return self.pack.shift

    @property
    def carried(self) -> list[ScoredItem]:
        """Dismissed at an earlier handover and still active."""
        return [i for i in self.rest if i.carried_over]

    @property
    def not_urgent(self) -> list[ScoredItem]:
        return [i for i in self.rest if not i.carried_over]

    @property
    def review_complete(self) -> bool:
        return all(f.asset_id in self.reviews for f in self.review_items)

    @property
    def responded_count(self) -> int:
        return sum(i.asset_id in self.responses for i in self.top)


def run(mode: str = "demo", shift: str = DEFAULT_SHIFT) -> Result:
    """mode: "manual" (no cache, no API), "demo" (cache or manual) or "llm" (live calls allowed)."""
    warnings = []
    if mode == "llm" and not llm.load_api_key():  # the environment, or .streamlit/secrets.toml
        warnings.append("Live LLM is on, but no API key is set (ANTHROPIC_API_KEY or GEMINI_API_KEY): "
                        "showing offline results.")
        mode = "demo"

    pack = load_all(shift=shift)
    extra = sorted((set(pack.alerts["asset"]) | set(pack.tickets["asset"])) - {NO_ASSET})
    notes, tag_warnings = tag_notes(pack.notes, pack.assets, mode=mode, extra_assets=extra)
    findings = detect(pack, notes)

    reviews = review.load(pack.shift.id)
    saved = respond.load_dismissals()
    dismissals = {}
    for asset, f in findings.items():
        d = saved.get(asset)
        status, detail = respond.dismissal_status(d, f, pack.shift.id, pack.shift.handover, pack.tickets)
        if status == "here" and d.get("previous"):
            # Dismissed again at this handover: keep showing that the earlier dismissal was outgrown.
            before, why = respond.dismissal_status(d["previous"], f, pack.shift.id, pack.shift.handover,
                                                   pack.tickets)
            if before == "now_worse":
                d, status, detail = d["previous"], before, why
        if status == "active" and reviews.get(asset, {}).get("choice") == "real_issue":
            # The outgoing engineer saw it during the shift and says it's real: that outranks the dismissal.
            status, detail = "now_worse", "the outgoing engineer says it's a real issue"
        if status:
            dismissals[asset] = (d, status, detail)

    top, rest = rank(findings, reviews, dismissals)
    explanations, explain_warnings = explain_all(top, mode=mode)
    for item in rest:
        explanations[item.asset_id] = template_explanation(item)

    evaluation = None
    if len(pack.answer_key):
        evaluation = evaluate([i.asset_id for i in top], pack.answer_key, list(findings))

    return Result(pack, notes, findings, top, rest, explanations, evaluation,
                  warnings + tag_warnings + explain_warnings, mode,
                  reviews, respond.load_responses(pack.shift.id), review.items_to_review(findings))


if __name__ == "__main__":
    shift = sys.argv[sys.argv.index("--shift") + 1] if "--shift" in sys.argv else DEFAULT_SHIFT
    result = run(mode="llm" if "--llm" in sys.argv else "demo", shift=shift)
    print(f"Baton: {result.shift.title}")
    for w in result.warnings:
        print("WARNING:", w)
    for n, item in enumerate(result.top, start=1):
        ex = result.explanations[item.asset_id]
        print(f"{n}. [{item.score:g}] {ex['headline']}  ({ex['source']})")
        for b in ex["bullets"]:
            print(f"   - {b}")
        print(f"   do: {ex['action']}")
    if result.carried:
        print("Carried over:", ", ".join(f"{i.asset_id} ({i.score:g})" for i in result.carried))
    print("Checked, not urgent:", ", ".join(f"{i.asset_id} ({i.score:g})" for i in result.not_urgent))
    ev = result.evaluation
    if ev:
        rho = "n/a" if ev["spearman"] is None else f"{ev['spearman']:.2f}"
        print(f"Matches expert ranking: {ev['matches']}/{ev['out_of']} "
              f"(same position {ev['same_position']}/{ev['out_of']}, rank agreement {rho})")
