"""Dash layout for the labeling UI."""

from __future__ import annotations

from dash import dcc, html

from .chart_utils import build_chunk_figure, format_ranges_text
from .state import progress_state


def build_layout(initial_chunk_payload, session_id: str):
    initial_progress = progress_state()
    return html.Div(
        [
            html.H2("Supervised Label UI"),
            html.Div(id="session-info", children=f"Session: {session_id}"),
            html.Div(id="chunk-info"),
            html.Div(id="progress-info", children="Viewed: 0 | Saved: 0 | Skipped: 0"),
            html.Div(
                [
                    html.Button("Save", id="save-btn", n_clicks=0),
                    html.Button("Skip", id="skip-btn", n_clicks=0),
                    html.Button("Clear", id="clear-btn", n_clicks=0),
                    html.Button("Undo last range", id="undo-btn", n_clicks=0),
                    html.Button("Next chunk", id="next-btn", n_clicks=0),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "12px", "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Confidence"),
                            dcc.Dropdown(
                                id="confidence-dropdown",
                                options=[
                                    {"label": "Low", "value": "low"},
                                    {"label": "Medium", "value": "medium"},
                                    {"label": "High", "value": "high"},
                                ],
                                value="medium",
                                clearable=False,
                            ),
                        ],
                        style={"minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Options"),
                            dcc.Checklist(
                                id="ui-options",
                                options=[{"label": "Skip already labeled chunks", "value": "skip_labeled"}],
                                value=[],
                            ),
                        ],
                        style={"minWidth": "260px"},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "marginBottom": "12px", "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Label("Notes"),
                    dcc.Textarea(
                        id="notes-input",
                        value="",
                        style={"width": "100%", "height": "80px"},
                        placeholder="Optional notes about the labeled region",
                    ),
                ],
                style={"marginBottom": "12px"},
            ),
            dcc.Graph(
                id="price-graph",
                figure=build_chunk_figure(initial_chunk_payload, []),
                config={"modeBarButtonsToAdd": ["drawrect", "eraseshape"], "displaylogo": False},
            ),
            html.H4("Selected ranges"),
            html.Pre(id="selected-ranges-view", children=format_ranges_text([])),
            html.Div(id="status-message"),
            dcc.Store(id="current-chunk-store", data=initial_chunk_payload),
            dcc.Store(id="selected-ranges-store", data=[]),
            dcc.Store(id="progress-store", data=initial_progress),
        ],
        style={"maxWidth": "1200px", "margin": "0 auto", "padding": "20px"},
    )
