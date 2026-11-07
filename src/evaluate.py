"""Step 6: compare our top 5 with the expert's answer key.

The answer key is only used here, for scoring. The ranking never sees it.
"""

import pandas as pd

# Answer-key rows that describe an asset without writing its id.
ALIASES = {
    "WFI loop": "WFI-LOOP-1",
    "CH-2 pump 3": "CH-2-P3",
}


def item_to_asset(item: str, known_assets: list[str]) -> str | None:
    lower = item.lower()
    for asset in sorted(known_assets, key=len, reverse=True):  # longest id first
        if asset.strip() and asset.lower() in lower:
            return asset
    for phrase, asset in ALIASES.items():
        if phrase.lower() in lower:
            return asset
    return None


def expert_ranking(answer_key: pd.DataFrame, known_assets: list[str]) -> list[str]:
    """Asset ids in the expert's order. The '-' (noise) row is skipped."""
    ranked = answer_key[answer_key["rank"].str.strip().str.isdigit()].copy()
    ranked["rank_num"] = ranked["rank"].astype(int)
    ranked = ranked.sort_values("rank_num")
    out = []
    for item in ranked["item"]:
        asset = item_to_asset(item, known_assets)
        if asset not in out:  # two rows about the same asset count once
            out.append(asset)
    return out


def spearman(ours: list[str], expert: list[str]) -> float | None:
    """Rank correlation over the assets both lists share (1.0 = same order)."""
    common = [a for a in expert if a is not None and a in ours]
    n = len(common)
    if n < 2:
        return None
    expert_pos = {a: i for i, a in enumerate(common)}
    our_order = [a for a in ours if a in common]
    d2 = sum((expert_pos[a] - i) ** 2 for i, a in enumerate(our_order))
    return 1 - 6 * d2 / (n * (n * n - 1))


def evaluate(our_top: list[str], answer_key: pd.DataFrame, known_assets: list[str]) -> dict:
    expert = expert_ranking(answer_key, known_assets)
    rows = []
    for i, asset in enumerate(expert, start=1):
        our_rank = our_top.index(asset) + 1 if asset in our_top else None
        rows.append({"asset": asset, "expert_rank": i, "our_rank": our_rank})
    return {
        "matches": sum(a in our_top for a in expert),
        "out_of": len(expert),
        "same_position": sum(1 for i, a in enumerate(expert) if i < len(our_top) and our_top[i] == a),
        "spearman": spearman(our_top, expert),
        "missing": [a for a in expert if a not in our_top],
        "extra": [a for a in our_top if a not in expert],
        "rows": rows,
    }


if __name__ == "__main__":
    from src.pipeline import run

    result = run(mode="manual")
    ev = result.evaluation
    print(f"Matches expert top 5: {ev['matches']}/{ev['out_of']}")
    rho = "n/a" if ev["spearman"] is None else f"{ev['spearman']:.2f}"
    print(f"Same position: {ev['same_position']}/{ev['out_of']}   Spearman rank agreement: {rho}")
    print(pd.DataFrame(ev["rows"]).to_string(index=False))
