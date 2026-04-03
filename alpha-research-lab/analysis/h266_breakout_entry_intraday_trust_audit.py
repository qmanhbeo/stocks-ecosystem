"""
H266: breakout-entry reduced-shape intraday trust audit.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    EntryModelSpec,
    assign_entry_thesis_family,
    build_entry_score_panel,
    fit_entry_model,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
)
from src.intraday_exit_research import (
    INTRADAY_SHAPE_ATOM_COLUMNS,
    REDUCED_SHAPE_FEATURE_COLUMNS,
    add_intraday_shape_atoms,
    merge_reduced_shape_panel,
)
from src.repo_paths import artifact_path
from src.research_protocol import ResearchProtocol
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
BRANCH_CACHE_DIR = artifact_path("entry_alpha")
H266_CANDIDATE_CACHE_PATH = BRANCH_CACHE_DIR / "h266_candidate_panel_2023_2025.parquet"
H266_LABEL_CACHE_PATH = BRANCH_CACHE_DIR / "h266_base_labels_2023_2025.parquet"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
BREAKOUT_FAMILY = "breakout_followthrough"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H266: breakout-entry reduced-shape intraday trust audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--candidate-cache", type=str, default=str(H266_CANDIDATE_CACHE_PATH))
    parser.add_argument("--labels-cache", type=str, default=str(H266_LABEL_CACHE_PATH))
    return parser.parse_args()


def _breakout_model_specs(panel: pd.DataFrame) -> list[EntryModelSpec]:
    breakout_path_columns = (
        "selection_score",
        "candidate_pool_rank",
        "breakout_20d",
        "gap_to_prev_close",
        "ret_1d",
        "c8_vol_zscore_5d",
        "c12_gap_absorb_3",
        "c13_compress_blowoff_2",
        "c14_clv_volconf_resid_rank",
    )
    specs = [
        EntryModelSpec(
            name="selection_baseline",
            feature_columns=tuple(column for column in ("selection_score", "candidate_pool_rank") if column in panel.columns),
        ),
        EntryModelSpec(
            name="breakout_path_core",
            feature_columns=tuple(column for column in breakout_path_columns if column in panel.columns),
        ),
        EntryModelSpec(
            name="intraday_shape_core",
            feature_columns=tuple(column for column in REDUCED_SHAPE_FEATURE_COLUMNS if column in panel.columns),
        ),
        EntryModelSpec(
            name="intraday_shape_atoms",
            feature_columns=tuple(column for column in INTRADAY_SHAPE_ATOM_COLUMNS if column in panel.columns),
        ),
        EntryModelSpec(
            name="intraday_atoms_plus_breakout_path",
            feature_columns=tuple(
                column for column in list(breakout_path_columns) + list(INTRADAY_SHAPE_ATOM_COLUMNS) if column in panel.columns
            ),
        ),
    ]
    return [spec for spec in specs if len(spec.feature_columns) >= 2]


def _sort_results(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return frame.sort_values(
        by=[
            "validation_auc",
            "validation_top_quintile_cycle_return_net",
            "confirmation_auc",
            "confirmation_top_quintile_cycle_return_net",
            "model_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )


def _to_float(row: pd.Series | dict[str, object], column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def main() -> None:
    args = parse_args()
    h258_summary_path = Path(args.h258_summary)
    h258_payload = load_summary_payload(h258_summary_path)
    if not bool(h258_payload.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_breakout_intraday_trust_audit",
            name="h266_breakout_entry_intraday_trust_audit",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape intraday contract gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    _, candidate_panel, labels = load_or_build_entry_artifacts(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        candidate_panel_path=Path(args.candidate_cache),
        labels_path=Path(args.labels_cache),
    )
    panel = prepare_entry_research_panel(candidate_panel, labels, protocol=INTRADAY_RESTART_PROTOCOL)
    panel = assign_entry_thesis_family(panel)

    reduced_shape_panel = pd.read_parquet(resolve_summary_artifact(h258_summary_path, "reduced_shape_panel"))
    coverage_frame = pd.read_parquet(resolve_summary_artifact(h258_summary_path, "coverage_frame"))
    merged = merge_reduced_shape_panel(
        panel,
        feature_panel=reduced_shape_panel,
        coverage_frame=coverage_frame,
    )
    merged = add_intraday_shape_atoms(merged)

    breakout_buyable = merged.loc[
        (merged["entry_thesis_family"].astype(str) == BREAKOUT_FAMILY)
        & merged["can_buy_next_open"].fillna(False).astype(bool)
    ].copy()
    observed = breakout_buyable.loc[breakout_buyable["intraday_observed"].fillna(False).astype(bool)].copy()
    if observed.empty:
        raise ValueError("No breakout-followthrough buyable candidate rows overlap the reduced-shape intraday panel")

    model_specs = _breakout_model_specs(observed)
    fits = [fit_entry_model(observed, spec=spec, protocol=INTRADAY_RESTART_PROTOCOL) for spec in model_specs]

    results_rows: list[dict[str, object]] = []
    control_models = {"selection_baseline", "breakout_path_core"}
    for fit in fits:
        row = dict(fit.summary_row)
        row["model_group"] = "control" if fit.spec.name in control_models else "intraday"
        results_rows.append(row)
    results = pd.DataFrame(results_rows)
    controls = _sort_results(results.loc[results["model_group"] == "control"].copy())
    intraday = _sort_results(results.loc[results["model_group"] == "intraday"].copy())
    if controls.empty or intraday.empty:
        raise ValueError("H266 requires both control and intraday model groups")

    best_path = controls.iloc[0]
    best_intraday = intraday.iloc[0]

    breakout_phase_means = {
        phase: float(pd.to_numeric(observed.loc[observed["research_phase"] == phase, "cycle_return_net"], errors="coerce").dropna().mean())
        for phase in ("dev", "validation", "confirmation")
    }
    results["validation_top_quintile_delta_vs_breakout_mean"] = pd.to_numeric(
        results["validation_top_quintile_cycle_return_net"],
        errors="coerce",
    ) - breakout_phase_means["validation"]
    results["confirmation_top_quintile_delta_vs_breakout_mean"] = pd.to_numeric(
        results["confirmation_top_quintile_cycle_return_net"],
        errors="coerce",
    ) - breakout_phase_means["confirmation"]
    results["validation_auc_delta_vs_best_path"] = pd.to_numeric(results["validation_auc"], errors="coerce") - float(
        pd.to_numeric(best_path.get("validation_auc"), errors="coerce")
    )
    results["validation_top_quintile_delta_vs_best_path"] = pd.to_numeric(
        results["validation_top_quintile_cycle_return_net"],
        errors="coerce",
    ) - float(pd.to_numeric(best_path.get("validation_top_quintile_cycle_return_net"), errors="coerce"))
    results["confirmation_top_quintile_delta_vs_best_path"] = pd.to_numeric(
        results["confirmation_top_quintile_cycle_return_net"],
        errors="coerce",
    ) - float(pd.to_numeric(best_path.get("confirmation_top_quintile_cycle_return_net"), errors="coerce"))

    best_intraday_validation_auc = _to_float(best_intraday, "validation_auc")
    best_path_validation_auc = _to_float(best_path, "validation_auc")
    best_intraday_validation_top_quintile = _to_float(best_intraday, "validation_top_quintile_cycle_return_net")
    best_intraday_confirmation_top_quintile = _to_float(best_intraday, "confirmation_top_quintile_cycle_return_net")
    passed = bool(
        best_intraday_validation_auc is not None
        and best_path_validation_auc is not None
        and best_intraday_validation_top_quintile is not None
        and best_intraday_confirmation_top_quintile is not None
        and float(best_intraday_validation_auc) > float(best_path_validation_auc)
        and float(best_intraday_validation_top_quintile) > float(breakout_phase_means["validation"])
        and float(best_intraday_confirmation_top_quintile) > 0.0
        and float(best_intraday_confirmation_top_quintile) > float(breakout_phase_means["confirmation"])
    )
    mixed = bool(
        not passed
        and best_intraday_validation_top_quintile is not None
        and best_intraday_confirmation_top_quintile is not None
        and float(best_intraday_validation_top_quintile) > float(breakout_phase_means["validation"])
        and float(best_intraday_confirmation_top_quintile) > 0.0
    )
    verdict = "PASSED" if passed else "MIXED" if mixed else "FAILED"

    results["decision"] = results["model_name"].astype(str).map(
        lambda name: verdict if name == str(best_intraday["model_name"]) else "CONTROL" if name in control_models else "CANDIDATE"
    )
    results = _sort_results(results)
    score_panel = build_entry_score_panel(fits)
    score_columns = [column for column in score_panel.columns if str(column).startswith("entry_prob__")]
    scored_panel = observed.merge(
        score_panel[["time", "ticker"] + score_columns].copy(),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h266_breakout_entry_intraday_trust_audit_results.parquet"
    scored_panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h266_breakout_entry_intraday_trust_audit_scored_panel.parquet"
    subset_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h266_breakout_entry_intraday_trust_audit_subset_panel.parquet"
    results.to_parquet(results_path, index=False)
    scored_panel.to_parquet(scored_panel_path, index=False)
    observed.to_parquet(subset_path, index=False)

    write_run_summary(
        ts=ts,
        mode="entry_alpha_breakout_intraday_trust_audit",
        name="h266_breakout_entry_intraday_trust_audit",
        summary={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "decision": verdict,
            "advance_to_h267": verdict == "PASSED",
            "breakout_family": BREAKOUT_FAMILY,
            "breakout_buyable_row_count": int(len(breakout_buyable)),
            "observed_breakout_row_count": int(len(observed)),
            "observed_breakout_share": float(len(observed) / len(breakout_buyable)) if len(breakout_buyable) else 0.0,
            "phase_breakout_mean_cycle_return_net": breakout_phase_means,
            "best_path_model": best_path.to_dict(),
            "best_intraday_model": best_intraday.to_dict(),
        },
        artifacts={
            "results": str(results_path),
            "scored_panel": str(scored_panel_path),
            "subset_panel": str(subset_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "branch_contract": "Breakout-followthrough-like entry rows only, 2023-2025 only, reduced-shape observed subset only",
            "candidate_cache": str(args.candidate_cache),
            "labels_cache": str(args.labels_cache),
            "h258_summary": str(h258_summary_path),
        },
    )


if __name__ == "__main__":
    main()
