"""
H508: router_equivalence_ablation

Theory-first branch: test whether surviving C23 routers are genuinely distinct
mechanisms or mostly overlapping projections of one latent regime.
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
    safe_spearman,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "router_equivalence_ablation"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Low-C16 routing, freshness routing, and cofire routing may be "
        "equivalent slices of one underlying C23 latent regime rather than "
        "distinct alpha families."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H508 router equivalence ablation")
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
    chunks: list[pd.DataFrame] = []
    for file in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            part = pd.read_parquet(file, columns=["time", "close", "volume"])
            part["ticker"] = file.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
            chunks.append(part)
        except Exception:
            continue
    if not chunks:
        return pd.DataFrame(columns=["time", "ticker", "amihud"])
    frame = pd.concat(chunks, ignore_index=True)
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["time", "ticker", "close", "volume"])
    frame = _compute_amihud(frame)
    return frame[["time", "ticker", "amihud"]]


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
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
        order_stats[["time", "ticker", "vol_expansion", "buy_heavy", "ceiling_2of3"]],
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
    panel["c23_not_lowc16"] = ((panel["c23"] == 1) & (panel["c16_low"] == 0)).astype(int)

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel["c23_prev"] = panel.groupby("ticker")["c23"].shift(1).fillna(0).astype(int)
    panel["c23_fresh_not_yesterday"] = ((panel["c23"] == 1) & (panel["c23_prev"] == 0)).astype(int)
    panel["c23_yesterday_carry"] = ((panel["c23"] == 0) & (panel["c23_prev"] == 1)).astype(int)

    panel["router_overlap_core"] = (
        (panel["c16_low_c23"] == 1) & (panel["c23_fresh_not_yesterday"] == 1)
    ).astype(int)

    return panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL])


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("c23", "C23 base state", family="primitive", primary=True),
    StateSpec("c24", "C24 base state (ceiling 2-of-3)", family="primitive", primary=True),
    StateSpec("c16_low_c23", "Router: low-C16 within C23", family="router", primary=True),
    StateSpec("c23_not_lowc16", "C23 outside low-C16 router", family="router"),
    StateSpec("c23_fresh_not_yesterday", "Router: fresh C23 onset", family="timing_router", primary=True),
    StateSpec("c23_yesterday_carry", "Carry state after C23", family="timing_router"),
    StateSpec("cofire_2", "Amplification router (2+ family fires)", family="router", primary=True),
    StateSpec("router_overlap_core", "Intersection of low-C16 and freshness routers", family="router_overlap"),
]


def _jaccard(mask_a: pd.Series, mask_b: pd.Series) -> float:
    a = mask_a.fillna(False).astype(bool)
    b = mask_b.fillna(False).astype(bool)
    inter = (a & b).sum()
    union = (a | b).sum()
    if union == 0:
        return np.nan
    return float(inter / union)


def _containment(mask_a: pd.Series, mask_b: pd.Series) -> float:
    """
    Fraction of A contained in B: P(B=1 | A=1).
    """
    a = mask_a.fillna(False).astype(bool)
    b = mask_b.fillna(False).astype(bool)
    denom = a.sum()
    if denom == 0:
        return np.nan
    return float((a & b).sum() / denom)


def build_overlap_matrix(panel: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for left in names:
        for right in names:
            left_mask = panel[left]
            right_mask = panel[right]
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "jaccard": _jaccard(left_mask, right_mask),
                    "contain_left_in_right": _containment(left_mask, right_mask),
                    "contain_right_in_left": _containment(right_mask, left_mask),
                    "left_share": float(left_mask.fillna(False).astype(bool).mean()),
                    "right_share": float(right_mask.fillna(False).astype(bool).mean()),
                }
            )
    return pd.DataFrame(rows)


def build_residual_table(panel: pd.DataFrame) -> pd.DataFrame:
    # Residual masks requested by the structural protocol.
    panel = panel.copy()
    panel["c23_resid_not_fresh"] = ((panel["c23"] == 1) & (panel["c23_fresh_not_yesterday"] == 0)).astype(int)
    panel["fresh_resid_not_c23"] = ((panel["c23_fresh_not_yesterday"] == 1) & (panel["c23"] == 0)).astype(int)
    panel["cofire_resid_not_c23"] = ((panel["cofire_2"] == 1) & (panel["c23"] == 0)).astype(int)
    panel["lowc16_resid_not_c23"] = ((panel["c16_low_c23"] == 1) & (panel["c23"] == 0)).astype(int)
    panel["c24_resid_not_c23"] = ((panel["c24"] == 1) & (panel["c23"] == 0)).astype(int)
    panel["carry_resid_not_onset"] = (
        (panel["c23_yesterday_carry"] == 1) & (panel["c23_fresh_not_yesterday"] == 0)
    ).astype(int)

    tests = [
        ("c23_resid_not_fresh", "C23 residual after removing freshness"),
        ("fresh_resid_not_c23", "Freshness residual after removing C23"),
        ("cofire_resid_not_c23", "Cofire residual after removing C23"),
        ("lowc16_resid_not_c23", "Low-C16 residual after removing C23"),
        ("c24_resid_not_c23", "C24 residual after removing C23"),
        ("carry_resid_not_onset", "Carry residual after removing onset"),
    ]

    rows: list[dict[str, object]] = []
    for col, label in tests:
        mask = panel[col].fillna(False).astype(bool)
        subset = panel.loc[mask]
        stat = safe_spearman(subset, S1_SCORE_COL, S1_TARGET_COL, min_rows=500)
        rows.append(
            {
                "name": col,
                "label": label,
                "rows": int(mask.sum()),
                "share": float(mask.mean()),
                "ic": stat["ic"],
                "p_value": stat["p_value"],
            }
        )
    return pd.DataFrame(rows)


def build_conditional_ic_table(panel: pd.DataFrame) -> pd.DataFrame:
    tests = [
        ("c23_not_fresh", (panel["c23"] == 1) & (panel["c23_fresh_not_yesterday"] == 0), "IC(C23 | not freshness)"),
        ("fresh_given_c23", panel["c23_fresh_not_yesterday"] == 1, "IC(freshness | C23)"),
        ("cofire_given_c23", panel["cofire_2"] == 1, "IC(cofire | C23)"),
        ("lowc16_given_c23", panel["c16_low_c23"] == 1, "IC(low-C16×C23 | C23)"),
        ("c24_given_not_c23", (panel["c24"] == 1) & (panel["c23"] == 0), "IC(C24 | not C23)"),
        ("c23_not_lowc16", panel["c23_not_lowc16"] == 1, "IC(C23 | not low-C16)"),
        ("c23_not_cofire", (panel["c23"] == 1) & (panel["cofire_2"] == 0), "IC(C23 | not cofire)"),
    ]

    rows: list[dict[str, object]] = []
    for key, mask_expr, label in tests:
        mask = mask_expr.fillna(False).astype(bool)
        subset = panel.loc[mask]
        stat = safe_spearman(subset, S1_SCORE_COL, S1_TARGET_COL, min_rows=500)
        rows.append(
            {
                "name": key,
                "label": label,
                "rows": int(mask.sum()),
                "share": float(mask.mean()),
                "ic": stat["ic"],
                "p_value": stat["p_value"],
            }
        )
    return pd.DataFrame(rows)


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
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
    router_names = [
        "c23",
        "c24",
        "c16_low_c23",
        "c23_not_lowc16",
        "c23_fresh_not_yesterday",
        "c23_yesterday_carry",
        "cofire_2",
        "router_overlap_core",
    ]
    overlap = build_overlap_matrix(panel, router_names)
    residual = build_residual_table(panel)
    conditional = build_conditional_ic_table(panel)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    overlap_path = write_dataframe_artifact(overlap, context, f"{BRANCH_NAME}_overlap")
    residual_path = write_dataframe_artifact(residual, context, f"{BRANCH_NAME}_residual")
    conditional_path = write_dataframe_artifact(conditional, context, f"{BRANCH_NAME}_conditional_ic")

    c23_ic = results.loc[results["name"] == "c23", "avg_ic"]
    c24_ic = results.loc[results["name"] == "c24", "avg_ic"]
    lowc16_ic = results.loc[results["name"] == "c16_low_c23", "avg_ic"]
    fresh_ic = results.loc[results["name"] == "c23_fresh_not_yesterday", "avg_ic"]
    cofire_ic = results.loc[results["name"] == "cofire_2", "avg_ic"]

    summary_path = context.write_summary(
        summary={
            "decision": "STRUCTURE_PASS",
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "c23_ic": float(c23_ic.iloc[0]) if len(c23_ic) else None,
            "c24_ic": float(c24_ic.iloc[0]) if len(c24_ic) else None,
            "c16_low_c23_ic": float(lowc16_ic.iloc[0]) if len(lowc16_ic) else None,
            "c23_fresh_ic": float(fresh_ic.iloc[0]) if len(fresh_ic) else None,
            "cofire_2_ic": float(cofire_ic.iloc[0]) if len(cofire_ic) else None,
            "zero_row_residual_tests": int((residual["rows"] == 0).sum()) if not residual.empty else None,
            "max_jaccard_non_identical": float(
                overlap.loc[overlap["left"] != overlap["right"], "jaccard"].max()
            )
            if not overlap.empty
            else None,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "overlap": overlap_path,
            "residual": residual_path,
            "conditional_ic": conditional_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "structure_note": "Ablation/overlap map for router equivalence, not a return optimization branch.",
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(overlap.sort_values("jaccard", ascending=False).head(20).to_string(index=False))
    print(residual.to_string(index=False))
    print(conditional.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
