"""
H270: breakout survivor label rewrite audit.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
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
from src.entry_alpha import build_entry_labels
from src.entry_alpha_research import (
    EntryModelSpec,
    assign_entry_thesis_family,
    build_entry_score_panel,
    build_survivor_label_series,
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
H266_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_entry_alpha_breakout_intraday_trust_audit.json"
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


@dataclass(frozen=True)
class SurvivorContractSpec:
    name: str
    immediate_return_floor: float
    extended_return_floor: float
    description: str


SURVIVOR_CONTRACTS: tuple[SurvivorContractSpec, ...] = (
    SurvivorContractSpec(
        name="net_relaxed_survivor",
        immediate_return_floor=-0.02,
        extended_return_floor=0.00,
        description="5d cycle avoids immediate failure and 10d net follow-through stays positive",
    ),
    SurvivorContractSpec(
        name="net_soft_survivor",
        immediate_return_floor=-0.01,
        extended_return_floor=0.00,
        description="5d cycle stays above a mild loss floor and 10d net follow-through stays positive",
    ),
    SurvivorContractSpec(
        name="net_strict_survivor",
        immediate_return_floor=0.00,
        extended_return_floor=0.00,
        description="5d cycle stays positive and 10d net follow-through stays positive",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H270: breakout survivor label rewrite audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--h266-summary", type=str, default=str(H266_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--survivor-horizon-cycles", type=int, default=2)
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
    work = frame.copy()
    sort_columns = [
        "validation_auc",
        "validation_top_quintile_cycle_return_net",
        "confirmation_auc",
        "confirmation_top_quintile_cycle_return_net",
        "validation_auc_delta_vs_best_path",
        "validation_top_quintile_delta_vs_best_path",
        "confirmation_top_quintile_delta_vs_best_path",
        "model_name",
    ]
    for column in sort_columns:
        if column in work.columns and column != "model_name":
            work[column] = pd.to_numeric(work[column], errors="coerce")
    available_sort_columns = [column for column in sort_columns if column in work.columns]
    ascending = [False if column != "model_name" else True for column in available_sort_columns]
    return work.sort_values(by=available_sort_columns, ascending=ascending, ignore_index=True)


def _to_float(row: pd.Series | dict[str, object], column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def _positive_rate(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def _print_table(contract_winners: pd.DataFrame) -> None:
    top = contract_winners.head(max(len(contract_winners), 1))
    print("\n" + "=" * 238)
    print("H270: BREAKOUT SURVIVOR LABEL REWRITE AUDIT")
    print("=" * 238)
    print(
        f"{'rank':<5} {'contract':<24} {'winner':<28} {'val_auc_d':>10} {'2025_auc':>10} "
        f"{'val_10d':>10} {'2025_10d':>10} {'val_d':>10} {'2025_d':>10} {'decision':>10}"
    )
    print("-" * 238)
    for idx, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {str(row.contract_name):<24} {str(row.best_intraday_model_name):<28} "
            f"{(row.validation_auc_delta_vs_best_path or 0.0):>+9.3f} "
            f"{(row.best_intraday_confirmation_auc if row.best_intraday_confirmation_auc is not None else float('nan')):>9.3f} "
            f"{(row.best_intraday_validation_top_quintile_cycle_return_net or 0.0)*100:>+9.2f}% "
            f"{(row.best_intraday_confirmation_top_quintile_cycle_return_net or 0.0)*100:>+9.2f}% "
            f"{(row.validation_top_quintile_delta_vs_best_path or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_top_quintile_delta_vs_best_path or 0.0)*100:>+9.2f}% "
            f"{str(row.contract_decision):>10}"
        )


def main() -> None:
    args = parse_args()
    h266_summary_path = Path(args.h266_summary)
    h266_payload = load_summary_payload(h266_summary_path)
    if not bool(h266_payload.get("summary", {}).get("advance_to_h267", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_breakout_survivor_label_rewrite_audit",
            name="h270_breakout_survivor_label_rewrite_audit",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H266 did not clear the breakout-entry intraday trust gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    inputs, candidate_panel, labels = load_or_build_entry_artifacts(
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

    signal_dates = sorted(pd.to_datetime(inputs.matrix["time"]).drop_duplicates())
    survivor_horizon_signal_steps = int(args.rebalance_every) * int(args.survivor_horizon_cycles)
    labels_survivor = build_entry_labels(
        candidate_panel,
        price_panel=inputs.price_panel,
        benchmark_open=inputs.benchmark_open,
        horizon_signal_steps=survivor_horizon_signal_steps,
        signal_dates=signal_dates,
        round_trip_cost=float(args.round_trip_cost),
        label_edge_buffer=0.0,
    )
    labels_survivor["time"] = pd.to_datetime(labels_survivor["time"])
    panel = panel.merge(
        labels_survivor[
            [
                "time",
                "ticker",
                "cycle_exit_date",
                "cycle_return_net",
                "cycle_relative_return_vs_vnindex",
            ]
        ].rename(
            columns={
                "cycle_exit_date": "cycle10_exit_date",
                "cycle_return_net": "cycle10_return_net",
                "cycle_relative_return_vs_vnindex": "cycle10_relative_return_vs_vnindex",
            }
        ),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    h258_summary_path = Path(args.h258_summary)
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
    label_stats_rows: list[dict[str, object]] = []
    all_results_rows: list[dict[str, object]] = []
    contract_winner_rows: list[dict[str, object]] = []
    scored_panel_by_contract: dict[str, pd.DataFrame] = {}
    subset_panel_by_contract: dict[str, pd.DataFrame] = {}
    phase_mean_survivor_return_net: dict[str, float] = {}

    for contract in SURVIVOR_CONTRACTS:
        contract_panel = observed.copy()
        contract_panel["cycle5_return_net"] = pd.to_numeric(contract_panel["cycle_return_net"], errors="coerce")
        contract_panel["cycle5_relative_return_vs_vnindex"] = pd.to_numeric(
            contract_panel["cycle_relative_return_vs_vnindex"],
            errors="coerce",
        )
        contract_panel["cycle_return_net"] = pd.to_numeric(contract_panel["cycle10_return_net"], errors="coerce")
        contract_panel["cycle_relative_return_vs_vnindex"] = pd.to_numeric(
            contract_panel["cycle10_relative_return_vs_vnindex"],
            errors="coerce",
        )
        contract_panel["buy_now_label"] = build_survivor_label_series(
            contract_panel,
            immediate_return_floor=float(contract.immediate_return_floor),
            extended_floor=float(contract.extended_return_floor),
            immediate_return_column="cycle5_return_net",
            extended_column="cycle10_return_net",
        )
        contract_panel["survivor_contract"] = contract.name
        contract_panel["survivor_immediate_return_floor"] = float(contract.immediate_return_floor)
        contract_panel["survivor_extended_return_floor"] = float(contract.extended_return_floor)
        contract_panel["survivor_description"] = contract.description

        label_stats_rows.append(
            {
                "contract_name": contract.name,
                "description": contract.description,
                "immediate_return_floor": float(contract.immediate_return_floor),
                "extended_return_floor": float(contract.extended_return_floor),
                "overall_positive_rate": _positive_rate(contract_panel["buy_now_label"]),
                "dev_positive_rate": _positive_rate(contract_panel.loc[contract_panel["research_phase"] == "dev", "buy_now_label"]),
                "validation_positive_rate": _positive_rate(
                    contract_panel.loc[contract_panel["research_phase"] == "validation", "buy_now_label"]
                ),
                "confirmation_positive_rate": _positive_rate(
                    contract_panel.loc[contract_panel["research_phase"] == "confirmation", "buy_now_label"]
                ),
            }
        )
        phase_mean_survivor_return_net = {
            phase: float(
                pd.to_numeric(
                    contract_panel.loc[contract_panel["research_phase"] == phase, "cycle_return_net"],
                    errors="coerce",
                ).dropna().mean()
            )
            for phase in ("dev", "validation", "confirmation")
        }

        fits = [fit_entry_model(contract_panel, spec=spec, protocol=INTRADAY_RESTART_PROTOCOL) for spec in model_specs]
        results_rows: list[dict[str, object]] = []
        control_models = {"selection_baseline", "breakout_path_core"}
        for fit in fits:
            row = dict(fit.summary_row)
            row["contract_name"] = contract.name
            row["description"] = contract.description
            row["immediate_return_floor"] = float(contract.immediate_return_floor)
            row["extended_return_floor"] = float(contract.extended_return_floor)
            row["model_group"] = "control" if fit.spec.name in control_models else "intraday"
            results_rows.append(row)
        contract_results = pd.DataFrame(results_rows)
        controls = _sort_results(contract_results.loc[contract_results["model_group"] == "control"].copy())
        intraday = _sort_results(contract_results.loc[contract_results["model_group"] == "intraday"].copy())
        if controls.empty or intraday.empty:
            raise ValueError(f"H270 requires both control and intraday model groups for contract {contract.name}")

        best_path = controls.iloc[0]
        best_intraday = intraday.iloc[0]
        contract_results["validation_auc_delta_vs_best_path"] = pd.to_numeric(
            contract_results["validation_auc"],
            errors="coerce",
        ) - float(pd.to_numeric(best_path.get("validation_auc"), errors="coerce"))
        contract_results["validation_top_quintile_delta_vs_best_path"] = pd.to_numeric(
            contract_results["validation_top_quintile_cycle_return_net"],
            errors="coerce",
        ) - float(pd.to_numeric(best_path.get("validation_top_quintile_cycle_return_net"), errors="coerce"))
        contract_results["confirmation_top_quintile_delta_vs_best_path"] = pd.to_numeric(
            contract_results["confirmation_top_quintile_cycle_return_net"],
            errors="coerce",
        ) - float(pd.to_numeric(best_path.get("confirmation_top_quintile_cycle_return_net"), errors="coerce"))
        all_results_rows.extend(contract_results.to_dict(orient="records"))

        best_intraday_validation_auc = _to_float(best_intraday, "validation_auc")
        best_path_validation_auc = _to_float(best_path, "validation_auc")
        best_intraday_validation_top_quintile = _to_float(best_intraday, "validation_top_quintile_cycle_return_net")
        best_intraday_confirmation_top_quintile = _to_float(best_intraday, "confirmation_top_quintile_cycle_return_net")
        best_intraday_confirmation_auc = _to_float(best_intraday, "confirmation_auc")

        passed = bool(
            best_intraday_validation_auc is not None
            and best_path_validation_auc is not None
            and best_intraday_validation_top_quintile is not None
            and best_intraday_confirmation_top_quintile is not None
            and best_intraday_confirmation_auc is not None
            and float(best_intraday_validation_auc) > float(best_path_validation_auc)
            and float(best_intraday_validation_top_quintile) > float(phase_mean_survivor_return_net["validation"])
            and float(best_intraday_confirmation_top_quintile) > 0.0
            and float(best_intraday_confirmation_top_quintile) > float(phase_mean_survivor_return_net["confirmation"])
            and float(best_intraday_confirmation_auc) >= 0.52
        )
        mixed = bool(
            not passed
            and best_intraday_validation_auc is not None
            and best_path_validation_auc is not None
            and best_intraday_validation_top_quintile is not None
            and best_intraday_confirmation_top_quintile is not None
            and float(best_intraday_validation_auc) > float(best_path_validation_auc)
            and float(best_intraday_validation_top_quintile) > float(phase_mean_survivor_return_net["validation"])
            and float(best_intraday_confirmation_top_quintile) > 0.0
        )
        contract_decision = "PASSED" if passed else "MIXED" if mixed else "FAILED"

        contract_winner_rows.append(
            {
                "contract_name": contract.name,
                "description": contract.description,
                "immediate_return_floor": float(contract.immediate_return_floor),
                "extended_return_floor": float(contract.extended_return_floor),
                "contract_decision": contract_decision,
                "best_intraday_model_name": str(best_intraday.get("model_name", "")),
                "best_path_model_name": str(best_path.get("model_name", "")),
                "best_intraday_validation_auc": best_intraday_validation_auc,
                "best_path_validation_auc": best_path_validation_auc,
                "validation_auc_delta_vs_best_path": None
                if best_intraday_validation_auc is None or best_path_validation_auc is None
                else float(best_intraday_validation_auc) - float(best_path_validation_auc),
                "best_intraday_confirmation_auc": best_intraday_confirmation_auc,
                "best_intraday_validation_top_quintile_cycle_return_net": best_intraday_validation_top_quintile,
                "best_intraday_confirmation_top_quintile_cycle_return_net": best_intraday_confirmation_top_quintile,
                "best_path_validation_top_quintile_cycle_return_net": _to_float(
                    best_path,
                    "validation_top_quintile_cycle_return_net",
                ),
                "best_path_confirmation_top_quintile_cycle_return_net": _to_float(
                    best_path,
                    "confirmation_top_quintile_cycle_return_net",
                ),
                "validation_top_quintile_delta_vs_best_path": None
                if best_intraday_validation_top_quintile is None
                else float(best_intraday_validation_top_quintile)
                - float(pd.to_numeric(best_path.get("validation_top_quintile_cycle_return_net"), errors="coerce")),
                "confirmation_top_quintile_delta_vs_best_path": None
                if best_intraday_confirmation_top_quintile is None
                else float(best_intraday_confirmation_top_quintile)
                - float(pd.to_numeric(best_path.get("confirmation_top_quintile_cycle_return_net"), errors="coerce")),
                "phase_validation_mean_survivor_return_net": float(phase_mean_survivor_return_net["validation"]),
                "phase_confirmation_mean_survivor_return_net": float(phase_mean_survivor_return_net["confirmation"]),
                "dev_positive_rate": _positive_rate(contract_panel.loc[contract_panel["research_phase"] == "dev", "buy_now_label"]),
                "validation_positive_rate": _positive_rate(
                    contract_panel.loc[contract_panel["research_phase"] == "validation", "buy_now_label"]
                ),
                "confirmation_positive_rate": _positive_rate(
                    contract_panel.loc[contract_panel["research_phase"] == "confirmation", "buy_now_label"]
                ),
            }
        )
        scored_panel_by_contract[contract.name] = build_entry_score_panel(fits)
        subset_panel_by_contract[contract.name] = contract_panel[
            [
                "time",
                "ticker",
                "research_phase",
                "entry_thesis_family",
                "selection_score",
                "candidate_pool_rank",
                "cycle5_return_net",
                "cycle10_return_net",
                "cycle10_relative_return_vs_vnindex",
                "buy_now_label",
                "survivor_contract",
                "survivor_immediate_return_floor",
                "survivor_extended_return_floor",
                "intraday_observed",
            ]
        ].copy()

    results = _sort_results(pd.DataFrame(all_results_rows))
    contract_winners = pd.DataFrame(contract_winner_rows)
    contract_winners["decision_rank"] = contract_winners["contract_decision"].map({"PASSED": 0, "MIXED": 1, "FAILED": 2}).fillna(3)
    contract_winners = contract_winners.sort_values(
        by=[
            "decision_rank",
            "validation_auc_delta_vs_best_path",
            "best_intraday_validation_top_quintile_cycle_return_net",
            "best_intraday_confirmation_top_quintile_cycle_return_net",
            "contract_name",
        ],
        ascending=[True, False, False, False, True],
        ignore_index=True,
    )
    contract_winners = contract_winners.drop(columns=["decision_rank"])
    _print_table(contract_winners)

    passed_contracts = contract_winners.loc[contract_winners["contract_decision"] == "PASSED"].copy()
    mixed_contracts = contract_winners.loc[contract_winners["contract_decision"] == "MIXED"].copy()
    if not passed_contracts.empty:
        decision = "PASSED"
        winner_row = passed_contracts.iloc[0]
    elif not mixed_contracts.empty:
        decision = "MIXED"
        winner_row = mixed_contracts.iloc[0]
    else:
        decision = "FAILED"
        winner_row = contract_winners.iloc[0]

    winner_contract = str(winner_row["contract_name"])
    winner_results = _sort_results(results.loc[results["contract_name"] == winner_contract].copy())
    winner_intraday = winner_results.loc[winner_results["model_group"] == "intraday"].copy().iloc[0].to_dict()
    winner_path = winner_results.loc[winner_results["model_group"] == "control"].copy().iloc[0].to_dict()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path = BRANCH_CACHE_DIR / f"{ts}_h270_breakout_survivor_label_rewrite_results.parquet"
    contract_winners_path = BRANCH_CACHE_DIR / f"{ts}_h270_breakout_survivor_label_rewrite_contract_winners.parquet"
    label_stats_path = BRANCH_CACHE_DIR / f"{ts}_h270_breakout_survivor_label_rewrite_label_stats.parquet"
    winner_scored_panel_path = BRANCH_CACHE_DIR / f"{ts}_h270_breakout_survivor_label_rewrite_scored_panel.parquet"
    winner_subset_panel_path = BRANCH_CACHE_DIR / f"{ts}_h270_breakout_survivor_label_rewrite_subset_panel.parquet"
    results.to_parquet(results_path, index=False)
    contract_winners.to_parquet(contract_winners_path, index=False)
    pd.DataFrame(label_stats_rows).to_parquet(label_stats_path, index=False)
    scored_panel_by_contract[winner_contract].to_parquet(winner_scored_panel_path, index=False)
    subset_panel_by_contract[winner_contract].to_parquet(winner_subset_panel_path, index=False)

    write_run_summary(
        ts=ts,
        mode="entry_alpha_breakout_survivor_label_rewrite_audit",
        name="h270_breakout_survivor_label_rewrite_audit",
        summary={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "decision": decision,
            "advance_to_h271": bool(decision == "PASSED"),
            "breakout_family": BREAKOUT_FAMILY,
            "breakout_buyable_row_count": int(len(breakout_buyable)),
            "observed_breakout_row_count": int(len(observed)),
            "observed_breakout_share": float(len(observed) / len(breakout_buyable)) if len(breakout_buyable) else None,
            "survivor_horizon_signal_steps": int(survivor_horizon_signal_steps),
            "survivor_contracts": [
                {
                    "contract_name": contract.name,
                    "immediate_return_floor": float(contract.immediate_return_floor),
                    "extended_return_floor": float(contract.extended_return_floor),
                    "description": contract.description,
                }
                for contract in SURVIVOR_CONTRACTS
            ],
            "winning_contract": winner_row.to_dict(),
            "best_intraday_model": winner_intraday,
            "best_path_model": winner_path,
            "contract_outcomes": contract_winners.to_dict(orient="records"),
        },
        artifacts={
            "results": str(results_path.relative_to(ROOT)),
            "contract_winners": str(contract_winners_path.relative_to(ROOT)),
            "label_stats": str(label_stats_path.relative_to(ROOT)),
            "scored_panel": str(winner_scored_panel_path.relative_to(ROOT)),
            "subset_panel": str(winner_subset_panel_path.relative_to(ROOT)),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "h258_summary": str(h258_summary_path),
            "h266_summary": str(h266_summary_path),
            "survivor_horizon_cycles": int(args.survivor_horizon_cycles),
        },
    )


if __name__ == "__main__":
    main()
