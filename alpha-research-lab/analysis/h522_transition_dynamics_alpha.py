"""
H522: Transition Dynamics as Alpha

Hypothesis: Transition events (time-in-state, transition_to_X flags) capture
information that static state labels lose.

Context from H507: coherent transition flow (onset/amplified/router -> carry -> quiet)
with self-transition probability 0.8692. The question is whether the transition
events themselves are the alpha, not just the static states.

This branch tests:
- days_in_state: cumulative days spent in current latent state
- just_transitioned: binary flag indicating state change from previous day
- transition_to_X: specific flags for entering each state
- prior_state encoding: categorical prior state as feature

Decision ladder:
- PASS: transition features beat static states by >+0.01 IC lift
- MIXED: transition features show positive but <+0.01 lift, or some types work
- FAIL: transition features do not beat static states
"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "transition_dynamics_alpha"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Transition events (time-in-state, transition_to_X flags) capture info "
        "that static state labels lose. H507 found coherent flow; test if "
        "transitions themselves are the alpha."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H522 transition dynamics alpha test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--c16-path",
        type=str,
        default=str(data_path("features/xs_order_pressure_daily.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def _extract_pct(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    text = str(value).replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    return np.nan


def _compute_amihud(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["daily_return"] = frame.groupby("ticker")["close"].pct_change()
    frame["daily_return_abs"] = frame["daily_return"].abs()
    frame["turnover"] = frame["close"] * frame["volume"]
    frame["amihud"] = frame["daily_return_abs"] / (frame["turnover"] + 1e-9)
    return frame


def _load_ohlcv_amihud() -> pd.DataFrame:
    stock_dir = data_path("stock")
    parts: list[pd.DataFrame] = []
    for file in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            part = pd.read_parquet(file, columns=["time", "close", "volume"])
            part["ticker"] = file.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
            parts.append(part)
        except Exception:
            continue
    if not parts:
        return pd.DataFrame(columns=["time", "ticker", "amihud"])
    merged = pd.concat(parts, ignore_index=True)
    merged["time"] = pd.to_datetime(merged["time"], errors="coerce").dt.normalize()
    merged = merged.dropna(subset=["time", "ticker", "close", "volume"])
    merged = _compute_amihud(merged)
    return merged[["time", "ticker", "amihud"]]


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    """Load S1 panel with latent state labels and compute transition features."""
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16 = pd.read_parquet(args.c16_path, columns=["time", "ticker", "order_volume_ratio_rank"])
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()
    panel = panel.merge(c16, on=["time", "ticker"], how="left")

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats["time"] = pd.to_datetime(order_stats["date"], errors="coerce").dt.normalize()
    order_stats["ticker"] = order_stats["ticker"].astype(str).str.upper()
    order_stats["volume_daily"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["vol_change"] = order_stats.groupby("ticker")["volume_daily"].pct_change()
    order_stats["vol_expansion"] = order_stats.groupby("time")["vol_change"].transform(
        lambda x: (x >= x.quantile(0.8)).astype(int)
    )
    order_stats["order_volume_ratio"] = order_stats["buy_order_volume"] / (
        order_stats["sell_order_volume"] + 1e-9
    )
    order_stats["buy_heavy"] = (order_stats["order_volume_ratio"] > 1.0).astype(int)
    order_stats["price_change_pct"] = order_stats["price_change_raw"].map(_extract_pct)
    order_stats["at_ceiling"] = (order_stats["price_change_pct"] >= 6.5).astype(int)
    order_stats["ceiling_2of3"] = (
        order_stats.groupby("ticker")["at_ceiling"].rolling(3, min_periods=3).sum().reset_index(level=0, drop=True) >= 2
    ).astype(int)
    panel = panel.merge(
        order_stats[
            ["time", "ticker", "vol_expansion", "buy_heavy", "ceiling_2of3"]
        ],
        on=["time", "ticker"],
        how="left",
    )

    amihud = _load_ohlcv_amihud()
    panel = panel.merge(amihud, on=["time", "ticker"], how="left")

    amihud_p80 = panel["amihud"].quantile(0.8)
    panel["high_illiq"] = (panel["amihud"] >= amihud_p80).astype(int)
    panel["c23"] = ((panel["high_illiq"] == 1) & (panel["vol_expansion"] == 1)).astype(int)
    panel["c24"] = (panel["ceiling_2of3"] == 1).astype(int)
    panel["c26"] = ((panel["buy_heavy"] == 1) & (panel["high_illiq"] == 1) & (panel["vol_expansion"] == 1)).astype(int)
    panel["cofire_count"] = panel[["c23", "c24", "c26"]].sum(axis=1)
    panel["cofire_2"] = (panel["cofire_count"] >= 2).astype(int)
    panel["c16_low"] = (panel["order_volume_ratio_rank"] <= 0.2).astype(int)
    panel["c16_low_c23"] = ((panel["c16_low"] == 1) & (panel["c23"] == 1)).astype(int)

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel["c23_prev"] = panel.groupby("ticker")["c23"].shift(1).fillna(0).astype(int)
    panel["c23_fresh"] = ((panel["c23"] == 1) & (panel["c23_prev"] == 0)).astype(int)
    panel["c23_carry"] = ((panel["c23"] == 0) & (panel["c23_prev"] == 1)).astype(int)

    panel["state_quiet"] = (panel["cofire_count"] == 0).astype(int)
    panel["state_onset"] = panel["c23_fresh"]
    panel["state_amplified"] = panel["cofire_2"]
    panel["state_router"] = panel["c16_low_c23"]
    panel["state_carry"] = panel["c23_carry"]

    labels = np.select(
        [
            panel["state_router"] == 1,
            panel["state_amplified"] == 1,
            panel["state_onset"] == 1,
            panel["state_carry"] == 1,
            panel["state_quiet"] == 1,
        ],
        ["router", "amplified", "onset", "carry", "quiet"],
        default="other",
    )
    panel["latent_label"] = labels

    panel = panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL])

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["prev_latent_label"] = panel.groupby("ticker")["latent_label"].shift(1)

    panel["just_transitioned"] = (
        (panel["latent_label"] != panel["prev_latent_label"]) & 
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["transition_to_onset"] = (
        (panel["latent_label"] == "onset") & 
        (panel["prev_latent_label"] != "onset") &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["transition_to_amplified"] = (
        (panel["latent_label"] == "amplified") & 
        (panel["prev_latent_label"] != "amplified") &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["transition_to_carry"] = (
        (panel["latent_label"] == "carry") & 
        (panel["prev_latent_label"] != "carry") &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["transition_to_router"] = (
        (panel["latent_label"] == "router") & 
        (panel["prev_latent_label"] != "router") &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["enter_active"] = (
        (panel["latent_label"].isin(["onset", "amplified", "router", "carry"])) &
        (panel["prev_latent_label"] == "quiet") &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["return_to_quiet"] = (
        (panel["latent_label"] == "quiet") &
        (panel["prev_latent_label"].isin(["onset", "amplified", "router", "carry"])) &
        (panel["prev_latent_label"].notna())
    ).astype(int)

    panel["days_in_state"] = panel.groupby(["ticker", "latent_label"]).cumcount() + 1

    panel["days_in_state_q4"] = (panel["days_in_state"] >= panel["days_in_state"].quantile(0.8)).astype(int)
    panel["days_in_state_q1"] = (panel["days_in_state"] <= panel["days_in_state"].quantile(0.2)).astype(int)

    prior_state_map = {
        "quiet": 0,
        "onset": 1,
        "amplified": 2,
        "router": 3,
        "carry": 4,
    }
    panel["prior_state_encoded"] = panel["prev_latent_label"].map(prior_state_map)

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("state_quiet", "Static: no C23-family signal active", family="static"),
    StateSpec("state_onset", "Static: fresh C23 onset state", family="static"),
    StateSpec("state_amplified", "Static: C23-family cofire amplification", family="static"),
    StateSpec("state_router", "Static: low-C16 router sub-state", family="static"),
    StateSpec("state_carry", "Static: post-C23 carry state", family="static"),
    StateSpec("just_transitioned", "Transition: any state change", family="transition", primary=True),
    StateSpec("transition_to_onset", "Transition: entered onset from another state", family="transition", primary=True),
    StateSpec("transition_to_amplified", "Transition: entered amplified from another state", family="transition", primary=True),
    StateSpec("transition_to_carry", "Transition: entered carry from another state", family="transition", primary=True),
    StateSpec("transition_to_router", "Transition: entered router from another state", family="transition"),
    StateSpec("enter_active", "Transition: quiet -> active (any)", family="transition", primary=True),
    StateSpec("return_to_quiet", "Transition: active -> quiet", family="transition"),
    StateSpec("days_in_state_q4", "Duration: long duration in current state (top 20%)", family="duration", primary=True),
    StateSpec("days_in_state_q1", "Duration: short duration in current state (bottom 20%)", family="duration"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_row = results[results["name"] == "all_rows"].iloc[0]
    baseline_ic = baseline_row["avg_ic"]

    static_states = ["state_onset", "state_amplified", "state_router", "state_carry"]
    static_best = results[results["name"].isin(static_states)].nlargest(1, "avg_ic")
    static_best_ic = static_best.iloc[0]["avg_ic"] if not static_best.empty else baseline_ic

    transition_states = ["just_transitioned", "transition_to_onset", "transition_to_amplified", 
                         "transition_to_carry", "transition_to_router", "enter_active", "return_to_quiet"]
    transition_best = results[results["name"].isin(transition_states)].nlargest(1, "avg_ic")
    transition_best_ic = transition_best.iloc[0]["avg_ic"] if not transition_best.empty else baseline_ic

    duration_states = ["days_in_state_q4", "days_in_state_q1"]
    duration_best = results[results["name"].isin(duration_states)].nlargest(1, "avg_ic")
    duration_best_ic = duration_best.iloc[0]["avg_ic"] if not duration_best.empty else baseline_ic

    transition_vs_static_lift = transition_best_ic - static_best_ic if static_best_ic > baseline_ic else 0

    if transition_vs_static_lift > 0.01:
        decision = "PASSED"
    elif transition_vs_static_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "static_best_ic": float(static_best_ic),
            "transition_best_ic": float(transition_best_ic),
            "duration_best_ic": float(duration_best_ic),
            "transition_vs_static_lift": float(transition_vs_static_lift),
            "best_transition_state": transition_best.iloc[0]["name"] if not transition_best.empty else None,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "Transition events capture info static states lose",
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nBaseline IC: {baseline_ic:.4f}")
    print(f"Static best IC: {static_best_ic:.4f}")
    print(f"Transition best IC: {transition_best_ic:.4f}")
    print(f"Duration best IC: {duration_best_ic:.4f}")
    print(f"Transition vs Static lift: {transition_vs_static_lift:.4f}")
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()