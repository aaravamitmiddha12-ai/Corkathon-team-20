"""Step 4: a transparent weighted score. All the numbers live in WEIGHTS.

  base  = criticality x severity x (1 + 0.5 x (repeats - 1))     (0 if the asset had no alerts)
  x1.5 if trend_worsening
  then add points for each flag that fired.
"""

from dataclasses import dataclass, field

from src.detect import Finding

WEIGHTS = {
    "criticality": {"low": 1, "medium": 2, "high": 3},
    "severity": {"info": 0.5, "low": 1, "medium": 2, "high": 3},
    "per_extra_repeat": 0.5,
    "trend_worsening_multiplier": 1.5,
    "no_open_ticket": 40,
    "clash": 50,
    "due_today": 30,
    "unacknowledged_latest": 15,
    "near_limit": 20,
}
TOP_N = 5

# How each reason is shown in the UI.
REASON_LABELS = {
    "clash": "Notes say OK, data disagrees",
    "no_open_ticket": "No ticket",
    "trend_worsening": "Getting worse",
    "due_today": "Due today",
    "near_limit": "Close to alarm limit",
    "unacknowledged_latest": "Not acknowledged",
    "repeated": "Repeated alerts",
}
ADDED_FLAGS = ["clash", "no_open_ticket", "due_today", "near_limit", "unacknowledged_latest"]


@dataclass
class ScoredItem:
    finding: Finding
    score: float
    base: float
    reasons: list = field(default_factory=list)    # keys of REASON_LABELS, most important first
    breakdown: list = field(default_factory=list)  # [(label, effect)] to show how the score was built

    @property
    def asset_id(self) -> str:
        return self.finding.asset_id


def base_score(f: Finding) -> float:
    if f.repeats == 0:
        return 0.0
    crit = WEIGHTS["criticality"].get(f.criticality, 1)
    sev = WEIGHTS["severity"].get(f.max_severity, 1)
    return crit * sev * (1 + WEIGHTS["per_extra_repeat"] * (f.repeats - 1))


def score_finding(f: Finding) -> ScoredItem:
    base = base_score(f)
    score = base
    breakdown = [(f"base: {f.criticality} criticality x {f.max_severity or 'no'} severity x {f.repeats} alert(s)",
                  f"{base:g}")]
    reasons = []

    if f.trend_worsening:
        score *= WEIGHTS["trend_worsening_multiplier"]
        breakdown.append(("getting worse", f"x{WEIGHTS['trend_worsening_multiplier']:g}"))

    for flag in ADDED_FLAGS:
        if getattr(f, flag):
            score += WEIGHTS[flag]
            breakdown.append((REASON_LABELS[flag].lower(), f"+{WEIGHTS[flag]}"))

    # Reasons in the order a reader cares about: biggest effect first.
    for flag in ["clash", "no_open_ticket", "trend_worsening", "due_today", "near_limit", "unacknowledged_latest"]:
        if getattr(f, flag):
            reasons.append(flag)
    if f.repeats > 1:
        reasons.append("repeated")

    return ScoredItem(f, round(score, 2), round(base, 2), reasons, breakdown)


def rank(findings: dict[str, Finding]) -> tuple[list[ScoredItem], list[ScoredItem]]:
    """Return (top 5, everything else). Nothing is dropped."""
    items = [score_finding(f) for f in findings.values()]
    crit_order = WEIGHTS["criticality"]
    items.sort(key=lambda i: (-i.score, -crit_order.get(i.finding.criticality, 1), i.asset_id))
    return items[:TOP_N], items[TOP_N:]
