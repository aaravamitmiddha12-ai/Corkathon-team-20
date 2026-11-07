"""Feature 3: "Before you go". The outgoing engineer reviews what the data flagged in their shift.

Only items with a clash or no ticket are listed. "It's a real issue" adds score;
"It's fine" never lowers it (the data still decides).
"""

from src import state

FILE = "outgoing_reviews.json"
CHOICES = {
    "fine": "It's fine - here's why",
    "real_issue": "It's a real issue",
    "didnt_know": "I didn't know about this",
}


def items_to_review(findings: dict) -> list:
    """Findings from this shift with a clash or no ticket, most serious first."""
    flagged = [f for f in findings.values() if f.clash or f.no_open_ticket]
    return sorted(flagged, key=lambda f: (not f.clash, f.asset_id))


def load(shift_id: str) -> dict:
    """{asset: {"choice", "comment", "name", "at"}} for one shift."""
    data = state.read(FILE).get(shift_id, {})
    if not isinstance(data, dict):
        return {}
    return {a: r for a, r in data.items() if isinstance(r, dict) and r.get("choice") in CHOICES}


def save(shift_id: str, asset: str, choice: str, comment: str, name: str) -> None:
    if choice not in CHOICES:
        raise ValueError(f"unknown choice {choice!r}")
    review = {
        "choice": choice,
        "comment": comment.strip(),
        "name": name.strip() or "Outgoing engineer",
        "at": state.now_iso(),
    }

    def change(data):
        if not isinstance(data.get(shift_id), dict):
            data[shift_id] = {}
        data[shift_id][asset] = review

    state.update(FILE, change)


def is_complete(shift_id: str, findings: dict) -> bool:
    reviews = load(shift_id)
    return all(f.asset_id in reviews for f in items_to_review(findings))
