"""Handover Check.

    streamlit run app.py

Five features: ranked handover with due-by times, notes vs data check, "Before you go"
(outgoing engineer review), respond (Got it / Dismiss with reason / Draft ticket),
and the signed-off handover record.
"""

import streamlit as st

from src import llm
from src.load import DEFAULT_SHIFT, SHIFTS
from src.pipeline import run
from ui import before_you_go, home
from ui.components import CSS, show

st.set_page_config(page_title="Handover Check", page_icon="🔁", layout="wide")
show(CSS)

st.session_state.setdefault("page", "home")
st.session_state.setdefault("state_version", 0)


def state_changed() -> None:
    st.session_state["state_version"] += 1


def get_result(mode: str, shift_id: str):
    """Run the pipeline once per (mode, shift, saved-state version), so button clicks don't re-run the LLM."""
    key = (mode, shift_id, st.session_state["state_version"])
    if st.session_state.get("result_key") != key:
        spinner = "Asking the LLM (results are cached after the first run)..." if mode == "llm" else "Loading..."
        with st.spinner(spinner):
            st.session_state["result"] = run(mode=mode, shift=shift_id)
            st.session_state["result_key"] = key
    return st.session_state["result"]


with st.sidebar:
    use_llm = st.toggle(
        "Use live LLM",
        value=False,
        help="Off = demo mode: cached LLM answers if present, otherwise manual tags and template text. "
             "Never calls the API.",
    )
    st.caption(f"Model: `{llm.model_name()}`" if use_llm else "Demo mode: offline, no API calls.")

# ----- top bar: which handover, who is taking over, and the outgoing engineer's page -----
top = st.columns([3, 2, 2], vertical_alignment="bottom")
with top[0]:
    shift_id = st.radio("Handover", list(SHIFTS), format_func=lambda s: SHIFTS[s].label, horizontal=True,
                        index=list(SHIFTS).index(DEFAULT_SHIFT), key="shift")
with top[1]:
    st.session_state.setdefault(f"incoming_{shift_id}", SHIFTS[shift_id].incoming_engineer)
    st.text_input("Incoming engineer", key=f"incoming_{shift_id}")
with top[2]:
    if st.session_state["page"] == "home":
        st.button("Outgoing engineer? Before you go →", key="open-before-you-go",
                  on_click=lambda: st.session_state.update(page="before"), width="stretch")

result = get_result("llm" if use_llm else "demo", shift_id)

if st.session_state["page"] == "before":
    before_you_go.render(result, on_saved=state_changed)
else:
    home.render(result)
