"""Dash callbacks for the labeling UI."""

from __future__ import annotations

from typing import Dict, List, Optional

from dash import Input, Output, State, callback_context, no_update

from manual_label_factory.config import SupervisedLabelConfig
from manual_label_factory.core.chunk_sampler import ChunkSampler
from manual_label_factory.core.label_storage import append_label_record, build_label_record, list_labeled_chunk_ids

from .chart_utils import build_chunk_figure, extract_range_from_relayout, format_ranges_text
from .state import chunk_sample_to_store, normalize_ranges, progress_state, store_to_chunk_sample


def _sample_next_chunk_payload(
    sampler: ChunkSampler,
    config: SupervisedLabelConfig,
    ui_options: Optional[List[str]],
):
    skip_ids = list_labeled_chunk_ids(config=config) if ui_options and "skip_labeled" in ui_options else set()
    chunk = sampler.sample_chunk(skip_labeled_chunk_ids=skip_ids)
    return chunk_sample_to_store(chunk)


def _chunk_info_text(chunk_payload: Dict[str, object]) -> str:
    return (
        f"Ticker: {chunk_payload['ticker']} | "
        f"Chunk: {chunk_payload['chunk_id']} | "
        f"Range: {chunk_payload['chunk_start']} -> {chunk_payload['chunk_end']} | "
        f"Bars: {chunk_payload['chunk_length']}"
    )


def _progress_text(progress: Dict[str, int]) -> str:
    return (
        f"Viewed: {progress.get('viewed', 0)} | "
        f"Saved: {progress.get('saved', 0)} | "
        f"Skipped: {progress.get('skipped', 0)}"
    )


def register_callbacks(app, sampler: ChunkSampler, session_id: str, config: SupervisedLabelConfig) -> None:
    @app.callback(
        Output("selected-ranges-store", "data"),
        Input("price-graph", "relayoutData"),
        Input("clear-btn", "n_clicks"),
        Input("undo-btn", "n_clicks"),
        Input("current-chunk-store", "data"),
        State("selected-ranges-store", "data"),
    )
    def sync_selected_ranges(relayout_data, clear_clicks, undo_clicks, current_chunk, existing_ranges):
        del clear_clicks, undo_clicks
        trigger = callback_context.triggered_id
        ranges = normalize_ranges(existing_ranges)
        if trigger == "current-chunk-store":
            return []
        if trigger == "clear-btn":
            return []
        if trigger == "undo-btn":
            return ranges[:-1]
        if trigger == "price-graph" and current_chunk:
            new_range = extract_range_from_relayout(relayout_data, current_chunk)
            if new_range is None:
                return ranges
            ranges.append(new_range)
            return normalize_ranges(ranges)
        return ranges

    @app.callback(
        Output("price-graph", "figure"),
        Output("selected-ranges-view", "children"),
        Output("chunk-info", "children"),
        Output("progress-info", "children"),
        Input("current-chunk-store", "data"),
        Input("selected-ranges-store", "data"),
        Input("progress-store", "data"),
    )
    def refresh_chunk_view(current_chunk, selected_ranges, progress):
        figure = build_chunk_figure(current_chunk, selected_ranges)
        return (
            figure,
            format_ranges_text(selected_ranges),
            _chunk_info_text(current_chunk),
            _progress_text(progress or progress_state()),
        )

    @app.callback(
        Output("current-chunk-store", "data"),
        Output("progress-store", "data"),
        Output("notes-input", "value"),
        Output("status-message", "children"),
        Input("save-btn", "n_clicks"),
        Input("skip-btn", "n_clicks"),
        Input("next-btn", "n_clicks"),
        State("current-chunk-store", "data"),
        State("selected-ranges-store", "data"),
        State("confidence-dropdown", "value"),
        State("notes-input", "value"),
        State("progress-store", "data"),
        State("ui-options", "value"),
        prevent_initial_call=True,
    )
    def handle_chunk_actions(
        save_clicks,
        skip_clicks,
        next_clicks,
        current_chunk,
        selected_ranges,
        confidence,
        notes,
        progress,
        ui_options,
    ):
        del save_clicks, skip_clicks, next_clicks
        trigger = callback_context.triggered_id
        progress = progress or progress_state()
        try:
            if trigger == "save-btn":
                normalized_ranges = normalize_ranges(selected_ranges)
                if not normalized_ranges:
                    return no_update, no_update, no_update, "Select at least one range before saving."
                chunk_sample = store_to_chunk_sample(current_chunk)
                record = build_label_record(
                    chunk_sample=chunk_sample,
                    session_id=session_id,
                    selected_ranges=normalized_ranges,
                    confidence=str(confidence or "medium"),
                    notes=str(notes or ""),
                    config=config,
                )
                saved = append_label_record(record, config=config)
                progress = {
                    "saved": int(progress.get("saved", 0)) + 1,
                    "skipped": int(progress.get("skipped", 0)),
                    "viewed": int(progress.get("viewed", 0)) + 1,
                }
                next_chunk = _sample_next_chunk_payload(sampler=sampler, config=config, ui_options=ui_options)
                message = (
                    f"Saved {saved['label_id']} for {saved['ticker']} "
                    f"({len(saved['selected_ranges'])} range(s), confidence={saved['confidence']})."
                )
                return next_chunk, progress, "", message

            if trigger == "skip-btn":
                progress = {
                    "saved": int(progress.get("saved", 0)),
                    "skipped": int(progress.get("skipped", 0)) + 1,
                    "viewed": int(progress.get("viewed", 0)) + 1,
                }
                next_chunk = _sample_next_chunk_payload(sampler=sampler, config=config, ui_options=ui_options)
                return next_chunk, progress, "", "Skipped current chunk."

            if trigger == "next-btn":
                progress = {
                    "saved": int(progress.get("saved", 0)),
                    "skipped": int(progress.get("skipped", 0)),
                    "viewed": int(progress.get("viewed", 0)) + 1,
                }
                next_chunk = _sample_next_chunk_payload(sampler=sampler, config=config, ui_options=ui_options)
                return next_chunk, progress, "", "Loaded next chunk without saving."
        except Exception as exc:
            return no_update, no_update, no_update, f"Error: {exc}"

        return no_update, no_update, no_update, no_update
