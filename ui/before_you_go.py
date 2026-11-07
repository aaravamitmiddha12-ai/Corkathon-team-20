"""Feature 3: "Before you go". The outgoing engineer reviews the items the data flagged in their shift."""

import streamlit as st

from src import review
from src.explain import template_bullets
from ui.components import chip, esc, eyebrow, show


def render(result, on_saved) -> None:
    shift = result.shift
    outgoing = result.pack.outgoing_engineer
    items = result.review_items
    by_asset = {i.asset_id: i for i in result.top + result.rest}

    st.button("← Back to handover", key="back-home", on_click=lambda: st.session_state.update(page="home"))
    show(eyebrow(1, "Outgoing review", first=True))
    st.title("Before you go")
    show(f'<div class="hc-sub">For {esc(outgoing)}, outgoing engineer ({esc(shift.label)}). '
         f'For these items your notes and the data disagree, or there is no ticket. '
         f'Tell the incoming engineer what you know. Your answer doesn\'t lower any item\'s priority: '
         f'the data still decides.</div>')

    if not items:
        st.success("Nothing to review: no clashes and no missing tickets this shift.")
        return

    saved = result.reviews
    with st.form(key=f"before-you-go-{shift.id}"):
        st.session_state.setdefault(f"review-name-{shift.id}", outgoing)
        name = st.text_input("Your name", key=f"review-name-{shift.id}")
        choices, comments = {}, {}
        for f in items:
            item = by_asset[f.asset_id]
            with st.container(border=True):
                tags = (chip("Notes say OK, data disagrees", "clash") if f.clash else "") + \
                       (chip("No ticket", "no_open_ticket") if f.no_open_ticket else "")
                kind = f" · {esc(f.asset_type)}" if f.asset_type else ""
                show(f'<div><b>{esc(f.asset_id)}</b>{kind}</div><div>{tags}</div>')
                wrote, data = st.columns(2, gap="medium")
                with wrote:
                    show('<div class="baton-eyebrow" style="margin:0 0 8px">What you wrote</div>')
                    if len(f.notes):
                        for _, note in f.notes.iterrows():
                            clash = note["time"] in f.clash_note_times
                            show(f'<div class="hc-note{" clash" if clash else ""}"><span class="hc-time">'
                                 f'{esc(note["time"])}</span>{esc(note["text"])}</div>')
                    else:
                        show('<div class="hc-muted">You didn\'t write anything about this.</div>')
                with data:
                    show('<div class="baton-eyebrow" style="margin:0 0 8px">What the data shows</div>')
                    show('<ul class="hc-bullets">' + "".join(f"<li>{esc(b)}</li>" for b in template_bullets(item))
                         + "</ul>")
                previous = saved.get(f.asset_id, {})
                options = list(review.CHOICES)
                index = options.index(previous["choice"]) if previous.get("choice") in options else None
                choices[f.asset_id] = st.radio(
                    f"Your view on {f.asset_id}", options, format_func=review.CHOICES.get, index=index,
                    horizontal=True, key=f"choice-{shift.id}-{f.asset_id}")
                comments[f.asset_id] = st.text_input(
                    "One-line comment for the incoming engineer", value=previous.get("comment", ""),
                    max_chars=200, key=f"comment-{shift.id}-{f.asset_id}")
        submitted = st.form_submit_button("Save review", type="primary")

    if submitted:
        if not name.strip():
            st.error("Enter your name first.")
            return
        orphan = [a for a, c in comments.items() if c.strip() and not choices.get(a)]
        if orphan:
            st.error("Pick a view for " + ", ".join(orphan) + " (or clear the comment), then save again.")
            return
        done = 0
        for asset, choice in choices.items():
            if choice:
                review.save(shift.id, asset, choice, comments.get(asset, ""), name)
                done += 1
        missing = len(items) - done
        on_saved()
        if missing:
            st.info(f"Saved {done}. {missing} item(s) still need a choice.")  # not st.warning: amber is reserved
        else:
            st.success("Review saved. The incoming engineer will see your comments on their cards.")
