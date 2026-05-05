from __future__ import annotations

import argparse
import glob
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    MAX_RESEARCH_YEAR,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    safe_spearman,
    summarize_ic_rows,
    write_dataframe_artifact,
)
from src.repo_paths import artifact_path, data_path  # noqa: E402


BRANCH_NAME = "h396_parent_echo_residual_harvester"
MODE = "research_branch_parent_echo_residual_harvester"

MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
H395_ARTIFACT_GLOB = str(
    artifact_path("h395_weak_signal_quorum_sleeve") / "*_h395_weak_signal_quorum_sleeve_test_scores.parquet"
)
C16_SCORE_COL = "order_volume_ratio_rank"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "High-IC composite or filter signals may be parent echoes; after "
        "same-date residualization against their parent signals, only residuals "
        "with stable IC > 0.01 should be treated as independent evidence."
    ),
    start_year=2019,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        C16_SCORE_COL: "decision-time C16 order-pressure rank",
        "weak_quorum_score": "H395 train-selected weak-vote quorum score",
    },
)

MATRIX_COMPONENTS = {
    "vote_c4_oc_asym": "c4_oc_asym_5d",
    "vote_c5_positive_size": "c5_positive_size",
    "vote_c6_sector_laggard": "c6_contrarian_intra_5d",
    "vote_c7_ceiling_count": "c7_ceiling_count_5d",
    "vote_c8_volume_z": "c8_vol_zscore_5d",
    "vote_c9_reversal": "c9_reversal_1d",
    "vote_c10_illiq": "c10_illiq_level_rank",
    "vote_c11_ret_lag": "c11_ret_60d_lag_rank",
    "vote_c12_gap_absorb": "c12_gap_absorb_3",
    "vote_c13_compression": "c13_compress_blowoff_2",
    "vote_c14_clv_volconf": "c14_clv_volconf_resid_rank",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H396: parent-echo residual audit for H395 and its C-library "
            "ingredients."
        )
    )
    parser.add_argument("--h395-test-scores", type=str, default="")
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    return parser.parse_args()


def _latest_h395_test_scores() -> Path:
    paths = sorted(glob.glob(H395_ARTIFACT_GLOB))
    if not paths:
        raise FileNotFoundError(f"No H395 test-score artifact matched {H395_ARTIFACT_GLOB}")
    return Path(paths[-1])


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _clip_years(frame: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    if int(end_year) > MAX_RESEARCH_YEAR:
        raise ValueError(f"H396 blocks 2026+; got end_year={end_year}")
    years = pd.to_datetime(frame["time"], errors="coerce").dt.year
    return frame.loc[years.between(int(start_year), int(end_year))].copy()


def _daily_rank(frame: pd.DataFrame, raw_col: str) -> pd.Series:
    raw = _safe_numeric(frame, raw_col, np.nan)
    ranked = raw.groupby(frame["time"], sort=False).rank(method="average", pct=True)
    return ranked.fillna(0.5).astype(float)


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    h395_path = Path(args.h395_test_scores) if args.h395_test_scores else _latest_h395_test_scores()
    h395 = pd.read_parquet(h395_path).copy()
    h395["time"] = pd.to_datetime(h395["time"], errors="coerce").dt.normalize()
    h395["ticker"] = h395["ticker"].astype(str).str.upper()
    h395 = _clip_years(h395, spec.start_year, spec.end_year)

    matrix_cols = ["time", "ticker", *[col for col in MATRIX_COMPONENTS.values() if col != "c5_positive_size"]]
    matrix = pd.read_parquet(args.matrix_path, columns=matrix_cols).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix = _clip_years(matrix, spec.start_year, spec.end_year)
    matrix["c5_positive_size"] = _safe_numeric(matrix, "c5_ins_relative_size_5d", 0.0).clip(lower=0.0)

    panel = h395.merge(matrix, on=["time", "ticker"], how="inner", validate="one_to_one")
    for vote_col, raw_col in MATRIX_COMPONENTS.items():
        panel[vote_col] = _daily_rank(panel, raw_col)
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.dropna(subset=[S1_TARGET_COL, S1_SCORE_COL, C16_SCORE_COL, "weak_quorum_score"])


def _residualize_by_date(frame: pd.DataFrame, target_col: str, parent_cols: list[str]) -> pd.Series:
    residual = pd.Series(np.nan, index=frame.index, dtype=float)
    required = [target_col, *parent_cols]
    for _, group in frame.groupby("time", sort=False):
        clean = group[required].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < max(20, len(parent_cols) + 5):
            continue
        y = clean[target_col].to_numpy(dtype=float)
        x = np.ones((len(clean), 1), dtype=float)
        for parent in parent_cols:
            x = np.column_stack([x, clean[parent].to_numpy(dtype=float)])
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residual.loc[clean.index] = y - x @ beta
    return residual


def _yearly_summary(frame: pd.DataFrame, score_col: str, min_year_rows: int) -> tuple[dict[str, object], pd.DataFrame]:
    yearly_rows = []
    pooled = safe_spearman(frame, score_col, S1_TARGET_COL, min_rows=int(min_year_rows))
    for year, group in frame.groupby("year", sort=True):
        stat = safe_spearman(group, score_col, S1_TARGET_COL, min_rows=int(min_year_rows))
        yearly_rows.append({"year": int(year), **stat})
    summary = {
        "pooled_rows": pooled["rows"],
        "pooled_ic": pooled["ic"],
        "pooled_p_value": pooled["p_value"],
        **summarize_ic_rows(yearly_rows),
    }
    return summary, pd.DataFrame(yearly_rows)


def run_audit(panel: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidate_cols = ["weak_quorum_score", *MATRIX_COMPONENTS.keys()]
    c_parent_cols = list(MATRIX_COMPONENTS.keys())
    result_rows = []
    yearly_frames = []
    residual_frame = panel[["time", "ticker", "year", S1_TARGET_COL, S1_SCORE_COL, C16_SCORE_COL]].copy()

    for score_col in candidate_cols:
        raw_summary, raw_yearly = _yearly_summary(panel, score_col, int(args.min_year_rows))
        result_rows.append({"candidate": score_col, "variant": "raw", **raw_summary})
        raw_yearly["candidate"] = score_col
        raw_yearly["variant"] = "raw"
        yearly_frames.append(raw_yearly)

        parent_resid_col = f"{score_col}__resid_s1_c16"
        residual_frame[parent_resid_col] = _residualize_by_date(panel, score_col, [S1_SCORE_COL, C16_SCORE_COL])
        parent_summary, parent_yearly = _yearly_summary(residual_frame, parent_resid_col, int(args.min_year_rows))
        result_rows.append({"candidate": score_col, "variant": "resid_s1_c16", **parent_summary})
        parent_yearly["candidate"] = score_col
        parent_yearly["variant"] = "resid_s1_c16"
        yearly_frames.append(parent_yearly)

        if score_col == "weak_quorum_score":
            component_resid_col = f"{score_col}__resid_c_votes"
            residual_frame[component_resid_col] = _residualize_by_date(panel, score_col, c_parent_cols)
            component_summary, component_yearly = _yearly_summary(
                residual_frame,
                component_resid_col,
                int(args.min_year_rows),
            )
            result_rows.append({"candidate": score_col, "variant": "resid_c_votes", **component_summary})
            component_yearly["candidate"] = score_col
            component_yearly["variant"] = "resid_c_votes"
            yearly_frames.append(component_yearly)

    results = pd.DataFrame(result_rows)
    results["survives_residual_gate"] = (
        (pd.to_numeric(results["avg_ic"], errors="coerce") > 0.01)
        & (pd.to_numeric(results["pct_positive_years"], errors="coerce") >= 0.60)
    )
    yearly = pd.concat(yearly_frames, ignore_index=True)
    return (
        results.sort_values(["variant", "avg_ic"], ascending=[True, False], na_position="last"),
        yearly,
        residual_frame,
    )


def choose_decision(results: pd.DataFrame) -> tuple[str, dict[str, object]]:
    q1_market = results.loc[
        results["candidate"].eq("weak_quorum_score") & results["variant"].eq("resid_s1_c16")
    ]
    q1_components = results.loc[
        results["candidate"].eq("weak_quorum_score") & results["variant"].eq("resid_c_votes")
    ]
    surviving = results.loc[results["variant"].eq("resid_s1_c16") & results["survives_residual_gate"]]
    q1_market_row = q1_market.iloc[0].to_dict() if not q1_market.empty else {}
    q1_component_row = q1_components.iloc[0].to_dict() if not q1_components.empty else {}
    q1_market_pass = bool(q1_market_row.get("survives_residual_gate", False))
    q1_component_pass = bool(q1_component_row.get("survives_residual_gate", False))
    if q1_market_pass and not q1_component_pass:
        decision = "PASSED"
    elif q1_market_pass:
        decision = "MIXED"
    elif not surviving.empty:
        decision = "MIXED"
    else:
        decision = "FAILED"
    return decision, {
        "q1_resid_s1_c16_avg_ic": q1_market_row.get("avg_ic"),
        "q1_resid_s1_c16_positive_years": q1_market_row.get("positive_years"),
        "q1_resid_s1_c16_years": q1_market_row.get("years"),
        "q1_resid_c_votes_avg_ic": q1_component_row.get("avg_ic"),
        "q1_resid_c_votes_positive_years": q1_component_row.get("positive_years"),
        "q1_resid_c_votes_years": q1_component_row.get("years"),
        "q1_independent_of_s1_c16": q1_market_pass,
        "q1_independent_of_c_votes": q1_component_pass,
        "s1_c16_residual_survivor_count": int(len(surviving)),
        "s1_c16_residual_survivors": surviving[["candidate", "avg_ic", "positive_years", "years"]].to_dict(
            orient="records"
        ),
    }


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
    )
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)
    panel = load_panel(args, spec)
    results, yearly, residuals = run_audit(panel, args)
    decision, detail = choose_decision(results)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    residuals_path = write_dataframe_artifact(residuals, context, f"{BRANCH_NAME}_residual_scores")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_years": sorted(int(year) for year in panel["year"].unique()),
            "top_results": results.head(30).to_dict(orient="records"),
            "protocol_note": (
                "resid_s1_c16 tests market-parent independence; resid_c_votes "
                "tests whether H395 is new beyond its C-library ingredients."
            ),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "residual_scores": residuals_path,
        },
        metadata={
            "no_2026_rows": True,
            "parent_columns_market": [S1_SCORE_COL, C16_SCORE_COL],
            "parent_columns_c_votes": list(MATRIX_COMPONENTS.keys()),
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 220)
    print(results.to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
