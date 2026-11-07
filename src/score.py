"""A transparent weighted score. All the numbers live in WEIGHTS.

  base  = criticality x severity x (1 + 0.5 x (repeats - 1))     (0 if the asset had no alerts)
  x1.5 if trend_worsening
  + points for each flag that fired (clash, no ticket, due soon, near limit, not acknowledged)
  + 20 if the outgoing engineer said "It's a real issue"
  x0.3 if an earlier dismissal still applies (and then it can't be in the top 5)
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
    "due_soon": 30,
    "unacknowledged_latest": 15,
    "near_limit": 20,
    "outgoing_real_issue": 20,
    "dismissed_multiplier": 0.3,
}
TOP_N = 5

# How each reason is shown in the UI, in the order a reader cares about.
REASON_LABELS = {
    "clash": "Notes say OK, data disagrees",
    "no_open_ticket": "No ticket",
    "trend_worsening": "Getting worse",
    "due_soon": "Due soon",
    "near_limit": "Close to alarm limit",
    "outgoing_real_issue": "Outgoing: real issue",
    "unacknowledged_latest": "Not acknowledged",
    "repeated": "Repeated alerts",
}
ADDED_FLAGS = ["clash", "no_open_ticket", "due_soon", "near_limit", "unacknowledged_latest"]


@dataclass
class ScoredItem:
    finding: Finding
    score: float
    base: float
    reasons: list = field(default_factory=list)    # keys of REASON_LABELS, most important first
    breakdown: list = field(default_factory=list)  # [(label, effect)] to show how the score was built
    review: dict | None = None                     # the outgoing engineer's review, if any
    dismissal: dict | None = None                  # an earlier dismissal for this asset, if any
    dismissal_status: str | None = None            # None / "here" / "active" / "now_worse" / "expired"
    dismissal_detail: str = ""

    @property
    def asset_id(self) -> str:
        return self.finding.asset_id

    @property
    def carried_over(self) -> bool:
        return self.dismissal_status == "active"


def base_score(f: Finding) -> float:
    if f.repeats == 0:
        return 0.0
    crit = WEIGHTS["criticality"].get(f.criticality, 1)
    sev = WEIGHTS["severity"].get(f.max_severity, 1)
    return crit * sev * (1 + WEIGHTS["per_extra_repeat"] * (f.repeats - 1))


def score_finding(f: Finding, review: dict | None = None, dismissal: dict | None = None,
                  dismissal_status: str | None = None, dismissal_detail: str = "") -> ScoredItem:
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

    real_issue = bool(review and review.get("choice") == "real_issue")
    if real_issue:
        score += WEIGHTS["outgoing_real_issue"]
        breakdown.append(("outgoing engineer: real issue", f"+{WEIGHTS['outgoing_real_issue']}"))

    if dismissal_status == "active":
        score *= WEIGHTS["dismissed_multiplier"]
        breakdown.append(("previously dismissed", f"x{WEIGHTS['dismissed_multiplier']:g}"))

    for key in REASON_LABELS:
        if key == "outgoing_real_issue":
            fired = real_issue
        elif key == "repeated":
            fired = f.repeats > 1
        else:
            fired = getattr(f, key)
        if fired:
            reasons.append(key)

    return ScoredItem(f, round(score, 2), round(base, 2), reasons, breakdown,
                      review, dismissal, dismissal_status, dismissal_detail)


def sort_items(items: list[ScoredItem]) -> list[ScoredItem]:
    crit = WEIGHTS["criticality"]
    return sorted(items, key=lambda i: (-i.score, -crit.get(i.finding.criticality, 1), i.asset_id))


def rank(findings: dict[str, Finding], reviews: dict | None = None,
         dismissals: dict | None = None) -> tuple[list[ScoredItem], list[ScoredItem]]:
    """Return (top 5, everything else). Nothing is dropped.

    `dismissals` maps asset -> (dismissal, status, detail). An item whose earlier dismissal is
    still active never makes the top 5; it goes into "everything else" (carried over).
    """
    reviews, dismissals = reviews or {}, dismissals or {}
    items = []
    for asset, f in findings.items():
        d, status, detail = dismissals.get(asset, (None, None, ""))
        items.append(score_finding(f, reviews.get(asset), d, status, detail))
    ranked = sort_items(items)
    eligible = [i for i in ranked if not i.carried_over]
    top = eligible[:TOP_N]
    top_ids = {i.asset_id for i in top}
    rest = sort_items([i for i in ranked if i.asset_id not in top_ids])
    return top, rest
