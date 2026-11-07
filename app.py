"""Baton.

    streamlit run app.py

Five features: ranked handover with due-by times, notes vs data check, "Before you go"
(outgoing engineer review), respond (Got it / Dismiss with reason / Draft ticket),
and the signed-off handover record.
"""

import streamlit as st

from src import llm
from src.brand import FAVICON
from src.load import DEFAULT_SHIFT, SHIFTS
from src.pipeline import run
from ui import before_you_go, home
from ui.components import CSS, NAV_SCRIPT, logo, nav, nav_progress, nav_state_rules, show, topbar

st.set_page_config(page_title="Baton", page_icon=str(FAVICON), layout="wide", initial_sidebar_state="expanded")
show(CSS)

st.session_state.setdefault("page", "home")
st.session_state.setdefault("state_version", 0)
for _shift in SHIFTS:
    if f"incoming_{_shift}" in st.session_state:
        st.session_state[f"incoming_{_shift}"] = st.session_state[f"incoming_{_shift}"]


def state_changed() -> None:
    st.session_state["state_version"] += 1


def get_result(mode: str, shift_id: str):
    """Run the pipeline once per (mode, shift, saved-state version), so button clicks don't re-run it."""
    key = (mode, shift_id, st.session_state["state_version"])
    if st.session_state.get("result_key") != key:
        with st.spinner("Loading..."):
            st.session_state["result"] = run(mode=mode, shift=shift_id)
            st.session_state["result_key"] = key
    return st.session_state["result"]


# ----- the left sidebar: logo, which handover, who is taking over, the sections, progress, the outgoing
# engineer's page. Below 1024px it's a drawer, opened from the top bar in the main pane.
side_top, side_nav, side_bottom = st.sidebar.container(), st.sidebar.container(), st.sidebar.container(key="baton-nav-bottom")
on_home = st.session_state["page"] == "home"
with side_bottom:
    progress_slot = st.container()
    if on_home:
        st.button("Outgoing engineer? Before you go", key="open-before-you-go",  # the arrow is CSS, so it can move
                  on_click=lambda: st.session_state.update(page="before"), width="stretch")

with side_top:
    show(logo())
    shift_id = st.radio("Handover", list(SHIFTS), format_func=lambda s: SHIFTS[s].label.removesuffix(" handover"),
                        horizontal=True, index=list(SHIFTS).index(DEFAULT_SHIFT), key="shift")
    st.session_state.setdefault(f"incoming_{shift_id}", SHIFTS[shift_id].incoming_engineer)
    st.text_input("Incoming engineer", key=f"incoming_{shift_id}")

# Offline for now: the app never calls an AI service. It still shows AI answers already saved in cache/, and
# falls back to its own templates. (src/llm.py can still use a key from .streamlit/secrets.toml for
# `python -m src.pipeline --llm`; see the README.)
mode = "demo"
result = get_result(mode, shift_id)

with side_nav:
    if on_home:
        show(nav(shift_id, result.top))
with progress_slot:
    show(nav_progress())
    show(f"<style>{' '.join(nav_state_rules(result.top, result.responses))}</style>")

with st.container(key="baton-topbar"):
    show(topbar())

if st.session_state["page"] == "before":
    before_you_go.render(result, on_saved=state_changed)
else:
    home.render(result, refresh=lambda: get_result(mode, shift_id))

st.html(NAV_SCRIPT, unsafe_allow_javascript=True)
