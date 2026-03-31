from __future__ import annotations

import pandas as pd


EVENT_TRUST_REGIME_SPECS: dict[str, tuple[str, int]] = {
    "top5_any_event_ge1": ("topk_any_event_count", 1),
    "top5_recent_filing_ge1": ("topk_recent_filing_count", 1),
    "top5_report_window_ge2": ("topk_report_window_count", 2),
    "top5_corp_action_ge1": ("topk_corp_action_count", 1),
}

EVENT_SURFACE_TRUST_COLUMNS = (
    "recent_any_filing_5d",
    "in_report_w15_45",
    "in_report_w30_60",
    "dividend_window_pre_20d",
    "issuance_window_pre_20d",
    "event_density_20d",
)


def build_topk_event_regime_frame(
    scored_frame: pd.DataFrame,
    *,
    strategy_names: list[str],
    event_surface: pd.DataFrame,
    top_k: int = 5,
) -> pd.DataFrame:
    required = {"time", "ticker", "actual"} | {f"score__{name}" for name in strategy_names}
    missing = sorted(required - set(scored_frame.columns))
    if missing:
        raise ValueError(f"Missing score columns for event trust decomposition: {missing}")

    event_missing = sorted(set(EVENT_SURFACE_TRUST_COLUMNS) - set(event_surface.columns))
    if event_missing:
        raise ValueError(f"Missing event-surface columns for trust decomposition: {event_missing}")

    work = scored_frame[["time", "ticker", "actual"] + [f"score__{name}" for name in strategy_names]].copy()
    work["time"] = pd.to_datetime(work["time"])
    events = event_surface[["time", "ticker"] + list(EVENT_SURFACE_TRUST_COLUMNS)].copy()
    events["time"] = pd.to_datetime(events["time"])
    merged = work.merge(events, on=["time", "ticker"], how="left", validate="one_to_one")

    merged["has_any_event_flag"] = pd.to_numeric(merged["event_density_20d"], errors="coerce").fillna(0.0) > 0.0
    merged["has_recent_filing_flag"] = pd.to_numeric(merged["recent_any_filing_5d"], errors="coerce").fillna(0.0) > 0.0
    merged["in_report_window_flag"] = (
        (pd.to_numeric(merged["in_report_w15_45"], errors="coerce").fillna(0.0) > 0.0)
        | (pd.to_numeric(merged["in_report_w30_60"], errors="coerce").fillna(0.0) > 0.0)
    )
    merged["has_corp_action_flag"] = (
        (pd.to_numeric(merged["dividend_window_pre_20d"], errors="coerce").fillna(0.0) > 0.0)
        | (pd.to_numeric(merged["issuance_window_pre_20d"], errors="coerce").fillna(0.0) > 0.0)
    )

    universe_actual = (
        merged.groupby("time", sort=True)["actual"].mean().rename("universe_mean_actual").reset_index()
    )
    rows: list[pd.DataFrame] = []
    for strategy_name in strategy_names:
        score_column = f"score__{strategy_name}"
        ranked = merged.sort_values(
            by=["time", score_column, "ticker"],
            ascending=[True, False, True],
            ignore_index=True,
        )
        topk = ranked.groupby("time", sort=True).head(int(top_k)).copy()
        summary = (
            topk.groupby("time", sort=True)
            .agg(
                selected_count=("ticker", "size"),
                topk_mean_score=(score_column, "mean"),
                topk_mean_actual=("actual", "mean"),
                topk_any_event_count=("has_any_event_flag", "sum"),
                topk_recent_filing_count=("has_recent_filing_flag", "sum"),
                topk_report_window_count=("in_report_window_flag", "sum"),
                topk_corp_action_count=("has_corp_action_flag", "sum"),
            )
            .reset_index()
        )
        summary["strategy_name"] = strategy_name
        summary = summary.merge(universe_actual, on="time", how="left", validate="one_to_one")
        denom = pd.to_numeric(summary["selected_count"], errors="coerce").replace(0, pd.NA)
        summary["topk_edge_actual"] = (
            pd.to_numeric(summary["topk_mean_actual"], errors="coerce")
            - pd.to_numeric(summary["universe_mean_actual"], errors="coerce")
        )
        summary["topk_any_event_share"] = (
            pd.to_numeric(summary["topk_any_event_count"], errors="coerce") / denom
        ).fillna(0.0)
        summary["topk_recent_filing_share"] = (
            pd.to_numeric(summary["topk_recent_filing_count"], errors="coerce") / denom
        ).fillna(0.0)
        summary["topk_report_window_share"] = (
            pd.to_numeric(summary["topk_report_window_count"], errors="coerce") / denom
        ).fillna(0.0)
        summary["topk_corp_action_share"] = (
            pd.to_numeric(summary["topk_corp_action_count"], errors="coerce") / denom
        ).fillna(0.0)
        rows.append(summary)
    return pd.concat(rows, ignore_index=True).sort_values(["strategy_name", "time"]).reset_index(drop=True)


def build_event_regime_activation_scale(
    topk_frame: pd.DataFrame,
    *,
    strategy_name: str,
    regime_name: str,
    on_scale: float = 1.0,
    off_scale: float = 0.0,
    all_dates: pd.Series | pd.Index | list | None = None,
) -> pd.Series:
    if regime_name not in EVENT_TRUST_REGIME_SPECS:
        raise ValueError(f"Unknown event trust regime {regime_name!r}")
    on_scale = float(on_scale)
    off_scale = float(off_scale)
    if on_scale < 0.0 or on_scale > 1.0 or off_scale < 0.0 or off_scale > 1.0:
        raise ValueError("on_scale and off_scale must lie in [0, 1]")

    count_column, threshold = EVENT_TRUST_REGIME_SPECS[regime_name]
    required = {"time", "strategy_name", count_column}
    missing = sorted(required - set(topk_frame.columns))
    if missing:
        raise ValueError(f"Missing columns for event regime activation scale: {missing}")

    strategy_frame = topk_frame.loc[topk_frame["strategy_name"] == str(strategy_name), ["time", count_column]].copy()
    strategy_frame["time"] = pd.to_datetime(strategy_frame["time"])
    strategy_frame = strategy_frame.drop_duplicates("time").sort_values("time").reset_index(drop=True)

    if all_dates is None:
        date_index = pd.Index(strategy_frame["time"].drop_duplicates().sort_values(), name="time")
    else:
        date_index = pd.Index(pd.to_datetime(pd.Series(all_dates)).drop_duplicates().sort_values(), name="time")
    scale = pd.Series(float(off_scale), index=date_index, dtype=float)
    regime_dates = strategy_frame.loc[
        pd.to_numeric(strategy_frame[count_column], errors="coerce") >= float(threshold),
        "time",
    ].drop_duplicates()
    scale.loc[scale.index.intersection(pd.Index(regime_dates))] = float(on_scale)
    return scale
