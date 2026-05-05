from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    S1_DEFAULT_PATH,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    load_s1_decision_panel,
    normalize_time_ticker,
    safe_spearman,
    summarize_ic_rows,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402


BRANCH_NAME = "h399_crowd_count_ignition"
MODE = "research_branch_crowd_count_ignition"

C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
H394_PREDICTIONS_PATH = (
    ROOT
    / "artifacts/h394_oracle_shadow_regime_distiller/"
    "20260505_170942_h394_oracle_shadow_regime_distiller_date_predictions.parquet"
)

C16_SCORE_COL = "order_volume_ratio_rank"
C8_SCORE_COL = "c8_vol_zscore_5d"
BUY_COUNT_COL = "buy_count_rank"
BUY_PRESSURE_COL = "buy_volume_pressure_rank"
AVG_BUY_SIZE_COL = "avg_buy_size_rank"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "High buy-order count is modest alone because it mixes retail swarm "
        "and real breadth; it should improve C16 quality only when average "
        "buy size, buy-volume pressure, or prior H394 weather creates a "
        "favorable ignition state."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=300,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        C16_SCORE_COL: "decision-time C16 order-pressure rank",
        BUY_COUNT_COL: "decision-time same-day buy-order-count rank",
        BUY_PRESSURE_COL: "decision-time same-day buy-volume-pressure rank",
        AVG_BUY_SIZE_COL: "decision-time same-day average-buy-order-size rank",
        C8_SCORE_COL: "decision-time C8 volume-z rank from RL matrix",
    },
)


@dataclass(frozen=True)
class StateSpec:
    name: str
    baseline_col: str
    primary: bool = False
    note: str = ""


STATE_SPECS = [
    StateSpec("all_rows", "all_rows", note="raw C16 baseline"),
    StateSpec("high_buy_count", "all_rows", note="high buy-order count alone"),
    StateSpec("volume_z_high80", "all_rows", note="C8 high volume-z alone"),
    StateSpec("high_count_volume_z_high80", "high_buy_count", note="count plus volume-z"),
    StateSpec("count_high_avg_buy_size", "high_buy_count", primary=True, note="many buyers and large average buy tickets"),
    StateSpec("count_low_avg_buy_size", "high_buy_count", primary=True, note="many buyers but small average buy tickets"),
    StateSpec("count_high_buy_pressure", "high_buy_count", primary=True, note="many buyers plus high buy-volume pressure"),
    StateSpec(
        "count_high_size_high_pressure",
        "high_buy_count",
        primary=True,
        note="many buyers, large tickets, and high buy-volume pressure",
    ),
    StateSpec(
        "count_low_size_high_pressure",
        "high_buy_count",
        primary=True,
        note="many buyers, small tickets, and high buy-volume pressure",
    ),
    StateSpec("count_weather_low20", "high_buy_count", primary=True, note="many buyers in H394 low predicted weather"),
    StateSpec("count_weather_high80", "high_buy_count", primary=True, note="many buyers in H394 high predicted weather"),
    StateSpec(
        "count_high_size_weather_low20",
        "high_buy_count",
        primary=True,
        note="many buyers plus large tickets in H394 low predicted weather",
    ),
    StateSpec(
        "count_high_pressure_weather_low20",
        "high_buy_count",
        primary=True,
        note="many buyers plus buy pressure in H394 low predicted weather",
    ),
]

SCORE_SPECS = [
    C16_SCORE_COL,
    BUY_COUNT_COL,
    BUY_PRESSURE_COL,
    AVG_BUY_SIZE_COL,
    C8_SCORE_COL,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H399: fixed crowd-count ignition state audit.")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--order-stats-path", type=str, default=str(ORDER_STATS_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--h394-predictions-path", type=str, default=str(H394_PREDICTIONS_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--high-quantile", type=float, default=0.80)
    parser.add_argument("--low-quantile", type=float, default=0.20)
    return parser.parse_args()


def _ticker(value: object) -> str:
    return str(value).strip().upper()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).astype(float)


def _rank_by_date(frame: pd.DataFrame, column: str, out_col: str) -> None:
    frame[out_col] = _safe_numeric(frame, column).groupby(frame["time"], sort=False).rank(method="average", pct=True)


def _clip_years(frame: pd.DataFrame, start_year: int, end_year: int, time_col: str = "time") -> pd.DataFrame:
    years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
    return frame.loc[years.between(int(start_year), int(end_year))].copy()


def _load_order_features(path: str | Path, start_year: int, end_year: int) -> pd.DataFrame:
    order = pd.read_parquet(
        path,
        columns=[
            "date",
            "ticker",
            "buy_order_count",
            "buy_order_volume",
            "avg_buy_order_volume",
            "sell_order_count",
            "sell_order_volume",
            "avg_sell_order_volume",
            "buy_sell_volume_imbalance",
        ],
    )
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].map(_ticker)
    order = order.dropna(subset=["time", "ticker"])
    order = _clip_years(order, start_year, end_year)
    for column in [
        "buy_order_count",
        "buy_order_volume",
        "avg_buy_order_volume",
        "sell_order_count",
        "sell_order_volume",
        "avg_sell_order_volume",
        "buy_sell_volume_imbalance",
    ]:
        order[column] = _safe_numeric(order, column)
    denom = (order["buy_order_volume"] + order["sell_order_volume"]).replace(0, np.nan)
    fallback_pressure = (order["buy_order_volume"] - order["sell_order_volume"]).div(denom)
    order["buy_volume_pressure"] = order["buy_sell_volume_imbalance"].where(
        order["buy_sell_volume_imbalance"].notna(),
        fallback_pressure,
    )
    _rank_by_date(order, "buy_order_count", BUY_COUNT_COL)
    _rank_by_date(order, "avg_buy_order_volume", AVG_BUY_SIZE_COL)
    _rank_by_date(order, "avg_sell_order_volume", "avg_sell_size_rank")
    _rank_by_date(order, "buy_volume_pressure", BUY_PRESSURE_COL)
    return order[
        [
            "time",
            "ticker",
            BUY_COUNT_COL,
            AVG_BUY_SIZE_COL,
            "avg_sell_size_rank",
            BUY_PRESSURE_COL,
            "buy_volume_pressure",
        ]
    ].drop_duplicates(["time", "ticker"])


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(args.s1_path, start_year=spec.start_year, end_year=spec.end_year)
    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", C16_SCORE_COL, "order_pressure_available"],
    )
    c16 = normalize_time_ticker(c16, source="C16 order-pressure surface")
    c16 = _clip_years(c16, spec.start_year, spec.end_year)
    c16[C16_SCORE_COL] = _safe_numeric(c16, C16_SCORE_COL)
    c16["order_pressure_available"] = c16["order_pressure_available"].eq(True)

    matrix = pd.read_parquet(args.matrix_path, columns=["time", "ticker", C8_SCORE_COL])
    matrix = normalize_time_ticker(matrix, source="RL signal matrix C8")
    matrix = _clip_years(matrix, spec.start_year, spec.end_year)
    matrix[C8_SCORE_COL] = _safe_numeric(matrix, C8_SCORE_COL)

    weather = pd.read_parquet(
        args.h394_predictions_path,
        columns=["time", "ridge_pred_low20", "ridge_pred_high80", "observed_vni_down_2d"],
    )
    weather["time"] = pd.to_datetime(weather["time"], errors="coerce").dt.normalize()
    weather = weather.dropna(subset=["time"])
    weather = _clip_years(weather, spec.start_year, spec.end_year)
    for column in ["ridge_pred_low20", "ridge_pred_high80", "observed_vni_down_2d"]:
        weather[column] = weather[column].eq(True)

    order = _load_order_features(args.order_stats_path, spec.start_year, spec.end_year)

    panel = panel.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["order_pressure_available"]].copy()
    panel = panel.merge(matrix, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(order, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(weather, on="time", how="left", validate="many_to_one")
    panel["year"] = panel["time"].dt.year.astype(int)

    high = float(args.high_quantile)
    low = float(args.low_quantile)
    panel["all_rows"] = True
    panel["high_buy_count"] = panel[BUY_COUNT_COL] >= high
    panel["volume_z_high80"] = panel[C8_SCORE_COL] >= high
    panel["high_count_volume_z_high80"] = panel["high_buy_count"] & panel["volume_z_high80"]
    panel["count_high_avg_buy_size"] = panel["high_buy_count"] & (panel[AVG_BUY_SIZE_COL] >= high)
    panel["count_low_avg_buy_size"] = panel["high_buy_count"] & (panel[AVG_BUY_SIZE_COL] <= low)
    panel["count_high_buy_pressure"] = panel["high_buy_count"] & (panel[BUY_PRESSURE_COL] >= high)
    panel["count_high_size_high_pressure"] = panel["count_high_avg_buy_size"] & (panel[BUY_PRESSURE_COL] >= high)
    panel["count_low_size_high_pressure"] = panel["count_low_avg_buy_size"] & (panel[BUY_PRESSURE_COL] >= high)
    panel["count_weather_low20"] = panel["high_buy_count"] & panel["ridge_pred_low20"].eq(True)
    panel["count_weather_high80"] = panel["high_buy_count"] & panel["ridge_pred_high80"].eq(True)
    panel["count_high_size_weather_low20"] = panel["count_high_avg_buy_size"] & panel["ridge_pred_low20"].eq(True)
    panel["count_high_pressure_weather_low20"] = panel["count_high_buy_pressure"] & panel["ridge_pred_low20"].eq(True)
    return panel.dropna(subset=[C16_SCORE_COL, S1_TARGET_COL])


def _mask(panel: pd.DataFrame, column: str) -> pd.Series:
    if column == "all_rows":
        return pd.Series(True, index=panel.index, dtype=bool)
    return panel[column].eq(True)


def _evaluate_score(panel: pd.DataFrame, score_col: str, spec: ExperimentSpec) -> tuple[dict[str, object], pd.DataFrame]:
    yearly_rows = []
    for year, group in panel.groupby("year", sort=True):
        stat = safe_spearman(group, score_col, S1_TARGET_COL, min_rows=int(spec.min_year_rows))
        yearly_rows.append({"year": int(year), "score": score_col, **stat})
    pooled = safe_spearman(panel, score_col, S1_TARGET_COL, min_rows=int(spec.min_phase_rows))
    summary = summarize_ic_rows(yearly_rows)
    out = {
        "score": score_col,
        "rows": int(pooled["rows"]),
        "pooled_ic": pooled["ic"],
        "pooled_p_value": pooled["p_value"],
        **summary,
    }
    return out, pd.DataFrame(yearly_rows)


def _evaluate_state(panel: pd.DataFrame, state: StateSpec, spec: ExperimentSpec) -> tuple[dict[str, object], pd.DataFrame]:
    subset = panel.loc[_mask(panel, state.name)].copy()
    baseline = panel.loc[_mask(panel, state.baseline_col)].copy()
    yearly_rows = []
    baseline_by_year = {}
    for year, group in baseline.groupby("year", sort=True):
        stat = safe_spearman(group, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(spec.min_year_rows))
        baseline_by_year[int(year)] = stat
    for year, group in subset.groupby("year", sort=True):
        stat = safe_spearman(group, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(spec.min_year_rows))
        base = baseline_by_year.get(int(year), {})
        lift = (
            float(stat["ic"] - base["ic"])
            if stat.get("ic") is not None and base.get("ic") is not None
            else None
        )
        target = _safe_numeric(group, S1_TARGET_COL).dropna()
        base_target = _safe_numeric(baseline.loc[baseline["year"].eq(int(year))], S1_TARGET_COL).dropna()
        yearly_rows.append(
            {
                "year": int(year),
                "state": state.name,
                "rows": stat["rows"],
                "ic": stat["ic"],
                "p_value": stat["p_value"],
                "baseline_ic": base.get("ic"),
                "lift_vs_baseline_ic": lift,
                "hit_rate": float(target.mean()) if len(target) >= int(spec.min_year_rows) else None,
                "baseline_hit_rate": (
                    float(base_target.mean()) if len(base_target) >= int(spec.min_year_rows) else None
                ),
            }
        )
    pooled = safe_spearman(subset, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(spec.min_phase_rows))
    base_pooled = safe_spearman(baseline, C16_SCORE_COL, S1_TARGET_COL, min_rows=int(spec.min_phase_rows))
    summary = summarize_ic_rows(yearly_rows)
    lift_values = [
        float(row["lift_vs_baseline_ic"])
        for row in yearly_rows
        if row.get("lift_vs_baseline_ic") is not None and np.isfinite(float(row["lift_vs_baseline_ic"]))
    ]
    hit_rate = _safe_numeric(subset, S1_TARGET_COL).dropna()
    baseline_hit_rate = _safe_numeric(baseline, S1_TARGET_COL).dropna()
    out = {
        "state": state.name,
        "baseline_col": state.baseline_col,
        "primary": bool(state.primary),
        "note": state.note,
        "rows": int(pooled["rows"]),
        "dates": int(subset["time"].nunique()) if not subset.empty else 0,
        "tickers": int(subset["ticker"].nunique()) if not subset.empty else 0,
        "pooled_ic": pooled["ic"],
        "baseline_pooled_ic": base_pooled["ic"],
        "pooled_lift_vs_baseline_ic": (
            float(pooled["ic"] - base_pooled["ic"])
            if pooled.get("ic") is not None and base_pooled.get("ic") is not None
            else None
        ),
        "hit_rate": float(hit_rate.mean()) if len(hit_rate) else None,
        "baseline_hit_rate": float(baseline_hit_rate.mean()) if len(baseline_hit_rate) else None,
        "hit_rate_lift": (
            float(hit_rate.mean() - baseline_hit_rate.mean()) if len(hit_rate) and len(baseline_hit_rate) else None
        ),
        "avg_yearly_lift_vs_baseline_ic": float(np.mean(lift_values)) if lift_values else None,
        "positive_lift_years": int(sum(1 for value in lift_values if value > 0)),
        "lift_years": int(len(lift_values)),
        **summary,
    }
    return out, pd.DataFrame(yearly_rows)


def run_audit(panel: pd.DataFrame, spec: ExperimentSpec) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)
    score_rows = []
    score_yearly_rows = []
    for score_col in SCORE_SPECS:
        result, yearly = _evaluate_score(panel.dropna(subset=[score_col]), score_col, spec)
        score_rows.append(result)
        score_yearly_rows.extend(yearly.to_dict(orient="records"))
    state_rows = []
    state_yearly_rows = []
    for state in STATE_SPECS:
        result, yearly = _evaluate_state(panel, state, spec)
        state_rows.append(result)
        state_yearly_rows.extend(yearly.to_dict(orient="records"))
    return (
        pd.DataFrame(state_rows),
        pd.DataFrame(state_yearly_rows),
        pd.DataFrame(score_rows),
        pd.DataFrame(score_yearly_rows),
    )


def choose_decision(state_results: pd.DataFrame, score_results: pd.DataFrame) -> tuple[str, dict[str, object]]:
    primary = state_results.loc[state_results["primary"].eq(True)].copy()
    primary = primary.sort_values(
        ["avg_yearly_lift_vs_baseline_ic", "avg_ic"],
        ascending=[False, False],
        na_position="last",
    )
    best = primary.iloc[0].to_dict() if not primary.empty else {}
    high_count = state_results.loc[state_results["state"].eq("high_buy_count")]
    high_count_row = high_count.iloc[0].to_dict() if not high_count.empty else {}
    c16_score = score_results.loc[score_results["score"].eq(C16_SCORE_COL)]
    buy_count_score = score_results.loc[score_results["score"].eq(BUY_COUNT_COL)]
    c16_score_row = c16_score.iloc[0].to_dict() if not c16_score.empty else {}
    buy_count_score_row = buy_count_score.iloc[0].to_dict() if not buy_count_score.empty else {}
    best_lift = best.get("avg_yearly_lift_vs_baseline_ic")
    best_ic = best.get("avg_ic")
    positive_lift_years = int(best.get("positive_lift_years", 0) or 0)
    lift_years = int(best.get("lift_years", 0) or 0)
    pass_gate = (
        best_lift is not None
        and float(best_lift) >= 0.015
        and positive_lift_years >= 6
        and lift_years >= 8
        and best_ic is not None
        and float(best_ic) >= 0.095
    )
    mixed_gate = (
        best_lift is not None
        and float(best_lift) >= 0.007
        and positive_lift_years >= 5
        and best_ic is not None
        and float(best_ic) >= 0.085
    )
    decision = "PASSED" if pass_gate else "MIXED" if mixed_gate else "FAILED"
    return decision, {
        "best_primary_state": best.get("state"),
        "best_primary_avg_ic": best_ic,
        "best_primary_avg_yearly_lift": best_lift,
        "best_primary_positive_lift_years": positive_lift_years,
        "best_primary_lift_years": lift_years,
        "high_buy_count_avg_ic": high_count_row.get("avg_ic"),
        "high_buy_count_hit_rate_lift_vs_all": high_count_row.get("hit_rate_lift"),
        "c16_standalone_avg_ic": c16_score_row.get("avg_ic"),
        "buy_count_standalone_avg_ic": buy_count_score_row.get("avg_ic"),
        "pass_gate": pass_gate,
        "mixed_gate": mixed_gate,
    }


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)
    panel = load_panel(args, spec)
    state_results, state_yearly, score_results, score_yearly = run_audit(panel, spec)
    decision, detail = choose_decision(state_results, score_results)

    state_results_path = write_dataframe_artifact(state_results, context, f"{BRANCH_NAME}_state_results")
    state_yearly_path = write_dataframe_artifact(state_yearly, context, f"{BRANCH_NAME}_state_yearly")
    score_results_path = write_dataframe_artifact(score_results, context, f"{BRANCH_NAME}_score_results")
    score_yearly_path = write_dataframe_artifact(score_yearly, context, f"{BRANCH_NAME}_score_yearly")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_years": sorted(int(year) for year in panel["year"].unique()),
            "state_rows": state_results.to_dict(orient="records"),
            "score_rows": score_results.to_dict(orient="records"),
            "decision_rule": (
                "PASSED requires a primary high-count intersection to beat "
                "high_buy_count alone by >= +0.015 avg yearly C16-IC lift, "
                "with >= 6/8 positive lift years and avg IC >= +0.095. MIXED "
                "requires >= +0.007 lift, >= 5 positive lift years, and avg IC >= +0.085."
            ),
        },
        artifacts={
            "state_results": state_results_path,
            "state_yearly": state_yearly_path,
            "score_results": score_results_path,
            "score_yearly": score_yearly_path,
        },
        metadata={
            "no_2026_rows": True,
            "state_specs": [state.__dict__ for state in STATE_SPECS],
            "h394_predictions_source": str(args.h394_predictions_path),
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 240)
    print("\nScore diagnostics:")
    print(score_results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print("\nState C16-quality results:")
    print(
        state_results.sort_values(
            ["primary", "avg_yearly_lift_vs_baseline_ic", "avg_ic"],
            ascending=[False, False, False],
            na_position="last",
        ).to_string(index=False)
    )
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
