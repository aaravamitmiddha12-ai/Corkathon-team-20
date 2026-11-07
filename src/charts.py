"""Plotly charts. Every chart has a title with the asset and unit, labelled axes (time as HH:MM),
a legend below listing every visual element, and hover tooltips with the exact time and value.

Colours: amber is ONLY for "notes say OK, data disagrees" (alerts after an "it's fine" note).
The warning level is orange, not amber, so amber keeps that one meaning.
"""

import pandas as pd
import plotly.graph_objects as go

from src.detect import parse_value

GREY = "#8a8984"
LINE_GREY = "#b9b8b2"
AMBER = "#f5a623"
RED = "#d03b3b"
RED_ZONE = "rgba(208, 59, 59, 0.10)"
ORANGE = "#e8590c"
NOTE = "#5b6b84"
AMBER_BAND = "rgba(245, 166, 35, 0.22)"
TWO_HOURS_MS = 2 * 3600 * 1000
NO_TRANSITION = dict(duration=0)

OTHER_ROW = "Other"
ROW_HEIGHT = 40       # px per timeline row; the HTML labels beside the chart use the same numbers
TIMELINE_TOP = 26     # px above the first row: room for the handover label
TIMELINE_BOTTOM = 30  # px below the last row: the time ticks
NOTE_LIFT = 0.3       # notes sit this far above the row line, so they never cover an alert dot
BAND_HEIGHT = 0.8


def _base_layout(fig: go.Figure, title: str, y_title: str, x_range: list, height: int,
                 legend_space: int = 90) -> go.Figure:
    """Shared look. The legend sits at the bottom of the whole figure (not the plot), with its own
    reserved space, so it never covers the time axis title even when it wraps on a phone."""
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14)),
        height=height + legend_space,
        margin=dict(l=10, r=10, t=44, b=legend_space),
        legend=dict(orientation="h", yref="container", y=0, yanchor="bottom", x=0, xanchor="left",
                    font=dict(size=11)),
        hovermode="closest",
        transition=NO_TRANSITION,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    # tick0 = shift start, so the 2-hourly ticks land on 19:00, 21:00 ... 07:00 (not on even hours).
    fig.update_xaxes(title_text="Time (HH:MM)", tickformat="%H:%M", range=x_range, dtick=TWO_HOURS_MS,
                     tick0=x_range[0], showgrid=False, zeroline=False)
    fig.update_yaxes(title_text=y_title, gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def _with_unit(value: float, unit: str) -> str:
    return f"{value:g} {unit}".strip()


def reading_chart(finding, shift) -> go.Figure | None:
    """One asset's readings over the shift, with its limits and the note times. None if no readings."""
    f = finding
    if not f.unit and f.limit is None:
        return None  # e.g. "Door held open > 60s": a number, but not a measurement worth plotting
    alerts = f.alerts.copy()
    alerts["value"] = [parse_value(m) for m in alerts["message"]]
    alerts = alerts.dropna(subset=["value"])
    if alerts.empty:
        return None

    unit = f.unit
    measurement = (f.measurement or "reading").capitalize()
    y_title = f"{measurement} ({unit})" if unit else measurement
    x0, x1 = shift.start, shift.handover

    levels = list(alerts["value"]) + [x for x in (f.limit, f.warn_limit) if x is not None]
    lo, hi = min(levels), max(levels)
    pad = (hi - lo) * 0.25 or abs(hi) * 0.1 or 1
    y_lo, y_hi = lo - pad, hi + pad

    fig = go.Figure()

    if f.limit is not None:
        edge = y_hi if f.higher_worse else y_lo
        side = "above" if f.higher_worse else "below"
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0, x0], y=[f.limit, f.limit, edge, edge, f.limit], fill="toself",
            fillcolor=RED_ZONE, line=dict(width=0), mode="lines", hoverinfo="skip",
            name=f"Out of limit ({side} {_with_unit(f.limit, unit)})"))
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[f.limit, f.limit], mode="lines", line=dict(color=RED, dash="dash", width=1.5),
            name=f"Alarm limit {_with_unit(f.limit, unit)}",
            hovertemplate=f"Alarm limit {_with_unit(f.limit, unit)}<extra></extra>"))
    if f.warn_limit is not None:
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[f.warn_limit, f.warn_limit], mode="lines", line=dict(color=ORANGE, dash="dash", width=1.5),
            name=f"Warning level {_with_unit(f.warn_limit, unit)}",
            hovertemplate=f"Warning level {_with_unit(f.warn_limit, unit)}<extra></extra>"))

    times, values = list(alerts["timestamp"]), list(alerts["value"])
    if f.readings_are_events and f.limit is not None:
        # Short separate events: a spike from the limit line to each reading, never joined up.
        xs, ys = [], []
        for t, v in zip(times, values):
            xs += [t, t, None]
            ys += [f.limit, v, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=LINE_GREY, width=2),
                                 hoverinfo="skip", name="Excursion (short separate event)"))
    elif len(times) >= 2:  # a single reading has no trend line to draw (or to list in the legend)
        fig.add_trace(go.Scatter(x=times, y=values, mode="lines", line=dict(color=LINE_GREY, width=2),
                                 hoverinfo="skip", name="Reading trend (continuous)"))

    after_ok = alerts["time"].isin(f.clash_alert_times)
    hover = f"%{{x|%H:%M:%S}} · %{{y:g}} {unit}<br>%{{customdata}}<extra></extra>"
    for mask, colour, name in [(~after_ok, GREY, "Alert reading"),
                               (after_ok, AMBER, "Alert after a note said it was fine")]:
        part = alerts[mask]
        if len(part):
            fig.add_trace(go.Scatter(
                x=part["timestamp"], y=part["value"], mode="markers", name=name,
                marker=dict(color=colour, size=10, line=dict(color="white", width=1.5)),
                customdata=part["message"], hovertemplate=hover))

    for n, (_, note) in enumerate(f.notes.iterrows()):
        text = note["text"] if len(note["text"]) <= 80 else note["text"][:77] + "..."
        fig.add_trace(go.Scatter(
            x=[note["timestamp"], note["timestamp"]], y=[y_lo, y_hi], mode="lines",
            line=dict(color=NOTE, dash="dot", width=1.2), name="Shift note", legendgroup="notes",
            showlegend=n == 0, customdata=[f"{note['time']} note: {_hover_safe(text)}"] * 2,
            hovertemplate="%{customdata}<extra></extra>"))
        fig.add_annotation(x=note["timestamp"], y=y_hi, text=f"{note['time']} note", showarrow=False,
                           yanchor="bottom", xanchor="left", font=dict(size=10, color=NOTE))

    fig.update_yaxes(range=[y_lo, y_hi])
    title = f"{f.asset_id} · {measurement.lower()} ({unit})" if unit else f"{f.asset_id} · {measurement.lower()}"
    return _base_layout(fig, title, y_title, [x0, x1], height=300, legend_space=120)


def timeline(result) -> go.Figure:
    """Home page: one row per top asset (in rank order) plus "Other", up to the handover.

    The row labels are HTML links beside the chart (ui/home.py), so this chart has no y labels,
    and it uses fixed pixel heights so those labels line up with the rows.
    """
    shift = result.shift
    top_ids = [i.asset_id for i in result.top]
    rows = top_ids + [OTHER_ROW]
    y_of = {row: n for n, row in enumerate(rows)}

    def row_of(asset) -> str:
        return asset if asset in y_of else OTHER_ROW

    alerts = result.pack.alerts.copy()
    alerts["y"] = [y_of[row_of(a)] for a in alerts["asset"]]
    alerts["after_ok"] = [
        t in result.findings[a].clash_alert_times if a in result.findings else False
        for a, t in zip(alerts["asset"], alerts["time"])
    ]
    notes = result.notes.copy()
    notes["y"] = [y_of[row_of(a)] - NOTE_LIFT for a in notes["asset_id"]]

    fig = go.Figure()

    # Bands first, so they sit behind the markers.
    for f in result.findings.values():
        if not f.clash:
            continue
        said_fine = f.notes[f.notes["time"].isin(f.clash_note_times)]["timestamp"].dropna()
        kept_alerting = f.alerts[f.alerts["time"].isin(f.clash_alert_times)]["timestamp"].dropna()
        if len(said_fine) and len(kept_alerting):
            start, end = said_fine.min(), kept_alerting.max()
            fig.add_trace(go.Bar(
                y=[y_of[row_of(f.asset_id)]], x=[(end - start).total_seconds() * 1000], base=[start],
                orientation="h", width=BAND_HEIGHT, marker=dict(color=AMBER_BAND, cornerradius=6, line=dict(width=0)),
                hoverinfo="skip", name="Said fine, kept alerting"))

    hover = "%{x|%H:%M:%S} · %{customdata[0]} · %{customdata[1]}<br>%{customdata[2]}<extra></extra>"
    for mask, colour, name in [(~alerts["after_ok"], GREY, "Alert"),
                               (alerts["after_ok"], AMBER, "Alert after a note said it was fine")]:
        part = alerts[mask]
        if len(part):
            fig.add_trace(go.Scatter(
                x=part["timestamp"], y=part["y"], mode="markers", name=name, cliponaxis=False,
                marker=dict(color=colour, size=10, line=dict(color="white", width=1)),
                customdata=part[["asset", "severity", "message"]].values, hovertemplate=hover))
    if len(notes):
        fig.add_trace(go.Scatter(
            x=notes["timestamp"], y=notes["y"], mode="markers", name="Note written", cliponaxis=False,
            marker=dict(symbol="diamond", size=8, color=NOTE),
            customdata=[[t, _hover_safe(x if len(x) <= 90 else x[:87] + "...")] for t, x in
                        zip(notes["time"], notes["text"])],
            hovertemplate="%{customdata[0]} note<br>%{customdata[1]}<extra></extra>"))

    fig.add_shape(type="line", x0=shift.handover, x1=shift.handover, y0=0, y1=1, yref="paper",
                  line=dict(color=NOTE, dash="dash", width=1.5))
    fig.add_annotation(x=shift.handover, y=1, yref="paper", yanchor="bottom", xanchor="right", showarrow=False,
                       text=f"Handover {shift.handover:%H:%M}", font=dict(size=11))

    fig.update_layout(
        height=timeline_height(rows), margin=dict(l=20, r=24, t=TIMELINE_TOP, b=TIMELINE_BOTTOM, autoexpand=False),
        showlegend=False, hovermode="closest", dragmode=False, barmode="overlay", transition=NO_TRANSITION,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    # tick0 = shift start, so the 2-hourly ticks land on 19:00, 21:00 ... 07:00 (not on even hours).
    fig.update_xaxes(type="date", tickformat="%H:%M", range=[shift.start, shift.handover], dtick=TWO_HOURS_MS,
                     tick0=shift.start, showgrid=False, zeroline=False, fixedrange=True)
    fig.update_yaxes(range=[len(rows) - 0.5, -0.5], tickvals=list(range(len(rows))), showticklabels=False,
                     gridcolor="rgba(128,128,128,0.25)", zeroline=False, fixedrange=True)
    return fig


def timeline_height(rows: list) -> int:
    return TIMELINE_TOP + ROW_HEIGHT * len(rows) + TIMELINE_BOTTOM


def _hover_safe(text: str) -> str:
    """Plotly hover text understands a little HTML; keep note text literal."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
