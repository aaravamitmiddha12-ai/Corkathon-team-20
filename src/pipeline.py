"""Runs the whole pipeline once. Used by the app, the tests and the command line.

    python -m src.pipeline          # demo mode (offline)
    python -m src.pipeline --llm    # live LLM, fills cache/ for offline demos
"""

import sys
from dataclasses import dataclass

import pandas as pd

from src import llm
from src.detect import Finding, detect
from src.evaluate import evaluate
from src.explain import explain_all
from src.load import NO_ASSET, Pack, load_all
from src.score import ScoredItem, rank
from src.tag_notes import tag_notes


@dataclass
class Result:
    pack: Pack
    notes: pd.DataFrame            # note lines with their tags
    findings: dict[str, Finding]
    top: list[ScoredItem]
    rest: list[ScoredItem]
    explanations: dict[str, dict]
    evaluation: dict
    warnings: list[str]
    mode: str


def run(mode: str = "demo") -> Result:
    """mode: "manual" (no cache, no API), "demo" (cache or manual) or "llm" (live calls allowed)."""
    warnings = []
    if mode == "llm" and not llm.has_api_key():
        warnings.append("Live LLM is on, but ANTHROPIC_API_KEY is not set: showing offline results.")
        mode = "demo"

    pack = load_all()
    extra = sorted((set(pack.alerts["asset"]) | set(pack.tickets["asset"])) - {NO_ASSET})
    notes, tag_warnings = tag_notes(pack.notes, pack.assets, mode=mode, extra_assets=extra)
    findings = detect(pack, notes)
    top, rest = rank(findings)
    explanations, explain_warnings = explain_all(top, mode=mode)
    evaluation = evaluate([i.asset_id for i in top], pack.answer_key, list(findings))
    return Result(pack, notes, findings, top, rest, explanations, evaluation,
                  warnings + tag_warnings + explain_warnings, mode)


if __name__ == "__main__":
    result = run(mode="llm" if "--llm" in sys.argv else "demo")
    for w in result.warnings:
        print("WARNING:", w)
    for n, item in enumerate(result.top, start=1):
        ex = result.explanations[item.asset_id]
        print(f"{n}. [{item.score:g}] {ex['headline']}  ({ex['source']})")
        print(f"   why: {ex['why']}")
        print(f"   do:  {ex['action']}")
        print(f"   cites: {', '.join(ex['citations'])}")
    print("Checked, not urgent:", ", ".join(f"{i.asset_id} ({i.score:g})" for i in result.rest))
    ev = result.evaluation
    rho = "n/a" if ev["spearman"] is None else f"{ev['spearman']:.2f}"
    print(f"Matches expert ranking: {ev['matches']}/{ev['out_of']} "
          f"(same position {ev['same_position']}/{ev['out_of']}, rank agreement {rho})")
