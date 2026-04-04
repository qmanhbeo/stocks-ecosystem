"""
H276: event-to-intraday state transition audit.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
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
    EntryModelSpec,
    assign_entry_thesis_family,
    fit_entry_model,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
)
from src.intraday_exit_research import add_intraday_shape_atoms
from src.research_protocol import ResearchProtocol
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EVENT_SURFACE_PATH = data_path("features/event_surface_daily.parquet")
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
BRANCH_CACHE_DIR = ROOT / "artifacts/entry_alpha"
H266_CANDIDATE_CACHE_PATH = BRANCH_CACHE_DIR / "h266_candidate_panel_2023_2025.parquet"
H266_LABEL_CACHE_PATH = BRANCH_CACHE_DIR / "h266_base_labels_2023_2025.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
BREAKOUT_FAMILY = "breakout_followthrough"
ANCHOR_COLUMNS = ("s1_proba", "c4_oc_asym_5d", "c12_gap_absorb_3")
MIN_REGRESSION_OBS = 20
MIN_VALIDATION_ROWS = 150
MIN_CONFIRMATION_ROWS = 100

EVENT_REGIME_SPECS = (
    ("all_rows", None, "Ungated breakout-followthrough observed subset"),
    ("report_window_any", "report_window_any", "Ticker-day is inside either report-window regime"),
    ("recent_filing_any", "recent_filing_any", "Ticker-day has any filing in the trailing 5 days"),
    (
        "event_transition_any",
        "event_transition_any",
        "Ticker-day is either inside a report window or has a recent filing",
    ),
)

MODEL_SPECS = (
    EntryModelSpec(name="fade_tension_disagreement", feature_columns=("fade_tension_disagreement",)),
    EntryModelSpec(
        name="intraday_shape_core_disagreement",
        feature_columns=("intraday_shape_core_disagreement",),
    ),
    EntryModelSpec(
        name="disagreement_combo",
        feature_columns=("fade_tension_disagreement", "intraday_shape_core_disagreement"),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H276: event-to-intraday state transition audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
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


def _daily_rank(series: pd.Series, time_index: pd.Series, *, ascending: bool = True) -> pd.Series:
    ranked = pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )
    return ranked.astype(float)


def _residualize_by_day(
    frame: pd.DataFrame,
    *,
    target_column: str,
    control_columns: tuple[str, ...],
    out_column: str,
    min_obs: int = MIN_REGRESSION_OBS,
) -> pd.DataFrame:
    work = frame.copy()
    parts: list[pd.Series] = []
    for _, group in work.groupby("time", sort=False):
        clean = group[[target_column, *control_columns]].replace([np.inf, -np.inf], np.nan).dropna()
        out = pd.Series(np.nan, index=group.index, dtype=float)
        if len(clean) >= int(min_obs):
            x = np.column_stack(
                [np.ones(len(clean), dtype=float)]
                + [clean[column].to_numpy(dtype=float) for column in control_columns]
            )
            y = clean[target_column].to_numpy(dtype=float)
            beta = np.linalg.lstsq(x, y, rcond=None)[0]
            resid = y - x @ beta
            out.loc[clean.index] = resid
        parts.append(out)
    work[out_column] = pd.concat(parts).sort_index()
    work[out_column] = _daily_rank(work[out_column], work["time"], ascending=True)
    return work


def _build_intraday_disagreement_state(
    *,
    matrix_path: Path,
    h258_summary_path: Path,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    matrix = pd.read_parquet(
        matrix_path,
        columns=["time", "ticker", "actual", *ANCHOR_COLUMNS],
    )
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(int(start_year), int(end_year))].copy()
    if matrix.empty:
        raise ValueError("No matrix rows found in requested year range")

    reduced_shape = pd.read_parquet(resolve_summary_artifact(h258_summary_path, "reduced_shape_panel"))
    reduced_shape = add_intraday_shape_atoms(reduced_shape.rename(columns={"session_date": "time"}))
    reduced_shape["time"] = pd.to_datetime(reduced_shape["time"], errors="coerce").dt.normalize()
    observed = matrix.merge(
        reduced_shape[
            [
                "time",
                "ticker",
                "first_hour_fade_proxy",
                "failed_breakout_proxy",
                "open_drive_then_fade_proxy",
            ]
        ],
        on=["time", "ticker"],
        how="inner",
        validate="one_to_one",
    )
    if observed.empty:
        raise ValueError("No observed reduced-shape rows overlap the requested matrix window")

    observed["fade_tension_rank"] = _daily_rank(
        observed["first_hour_fade_proxy"],
        observed["time"],
        ascending=True,
    )
    observed["failed_breakout_rank"] = _daily_rank(
        observed["failed_breakout_proxy"],
        observed["time"],
        ascending=True,
    )
    observed["drive_rank"] = _daily_rank(
        observed["open_drive_then_fade_proxy"],
        observed["time"],
        ascending=True,
    )
    observed["intraday_shape_core_rank"] = observed[
        ["fade_tension_rank", "failed_breakout_rank", "drive_rank"]
    ].mean(axis=1)
    observed = _residualize_by_day(
        observed,
        target_column="fade_tension_rank",
        control_columns=ANCHOR_COLUMNS,
        out_column="fade_tension_disagreement",
    )
    observed = _residualize_by_day(
        observed,
        target_column="intraday_shape_core_rank",
        control_columns=ANCHOR_COLUMNS,
        out_column="intraday_shape_core_disagreement",
    )
    return observed[
        [
            "time",
            "ticker",
            *ANCHOR_COLUMNS,
            "fade_tension_rank",
            "failed_breakout_rank",
            "intraday_shape_core_rank",
            "fade_tension_disagreement",
            "intraday_shape_core_disagreement",
        ]
    ].copy()


def _build_breakout_event_panel(
    *,
    matrix_path: Path,
    tradability_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
    event_surface_path: Path,
    start_year: int,
    end_year: int,
    strategy_name: str,
    top_m_max: int,
    top_k: int,
    rebalance_every: int,
    round_trip_cost: float,
    required_holding_age: int,
    initial_notional_vnd: float,
    candidate_cache_path: Path,
    labels_cache_path: Path,
    disagreement_state: pd.DataFrame,
) -> pd.DataFrame:
    _, candidate_panel, labels = load_or_build_entry_artifacts(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=int(start_year),
        end_year=int(end_year),
        strategy_name=str(strategy_name),
        top_m_max=int(top_m_max),
        top_k=int(top_k),
        rebalance_every=int(rebalance_every),
        round_trip_cost=float(round_trip_cost),
        required_holding_age=int(required_holding_age),
        initial_notional_vnd=float(initial_notional_vnd),
        candidate_panel_path=candidate_cache_path,
        labels_path=labels_cache_path,
    )
    panel = prepare_entry_research_panel(candidate_panel, labels, protocol=INTRADAY_RESTART_PROTOCOL)
    panel = assign_entry_thesis_family(panel)
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    breakout = panel.loc[
        (panel["entry_thesis_family"].astype(str) == BREAKOUT_FAMILY)
        & panel["can_buy_next_open"].fillna(False).astype(bool)
    ].copy()
    if breakout.empty:
        raise ValueError("No breakout-followthrough buyable rows found for H276")

    breakout = breakout.merge(
        disagreement_state,
        on=["time", "ticker"],
        how="inner",
        validate="one_to_one",
    )
    if breakout.empty:
        raise ValueError("No breakout-followthrough rows overlap the disagreement-state panel")

    event_surface = pd.read_parquet(
        event_surface_path,
        columns=[
            "time",
            "ticker",
            "in_report_w15_45",
            "in_report_w30_60",
            "recent_any_filing_5d",
            "recent_any_filing_20d",
            "event_density_20d",
            "has_any_event_history",
        ],
    )
    event_surface["time"] = pd.to_datetime(event_surface["time"], errors="coerce").dt.normalize()
    event_surface = event_surface.loc[
        event_surface["time"].dt.year.between(int(start_year), int(end_year))
    ].copy()
    breakout = breakout.merge(
        event_surface,
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    breakout["report_window_any"] = breakout[["in_report_w15_45", "in_report_w30_60"]].fillna(0).max(axis=1).astype(bool)
    breakout["recent_filing_any"] = pd.to_numeric(
        breakout["recent_any_filing_5d"],
        errors="coerce",
    ).fillna(0.0).gt(0.0)
    breakout["event_transition_any"] = breakout["report_window_any"] | breakout["recent_filing_any"]
    return breakout.reset_index(drop=True)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _phase_subset_summary(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for phase in ("dev", "validation", "confirmation"):
        scoped = frame.loc[frame["research_phase"].astype(str) == phase].copy()
        out[phase] = {
            "rows": int(len(scoped)),
            "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
            "tickers": int(scoped["ticker"].nunique()) if not scoped.empty else 0,
        }
    return out


def _candidate_decision(row: pd.Series) -> str:
    validation_rows = int(pd.to_numeric(row.get("validation_count"), errors="coerce") or 0)
    confirmation_rows = int(pd.to_numeric(row.get("confirmation_count"), errors="coerce") or 0)
    if validation_rows < MIN_VALIDATION_ROWS or confirmation_rows < MIN_CONFIRMATION_ROWS:
        return "FAILED"

    val_auc_delta = _safe_float(row.get("validation_auc_delta_vs_all_rows"))
    val_topq_delta = _safe_float(row.get("validation_top_quintile_cycle_return_net_delta_vs_all_rows"))
    conf_topq_delta = _safe_float(row.get("confirmation_top_quintile_cycle_return_net_delta_vs_all_rows"))
    conf_topq = _safe_float(row.get("confirmation_top_quintile_cycle_return_net"))
    val_topq = _safe_float(row.get("validation_top_quintile_cycle_return_net"))

    passed = bool(
        val_auc_delta is not None
        and val_topq_delta is not None
        and conf_topq_delta is not None
        and conf_topq is not None
        and val_topq is not None
        and val_auc_delta > 0.0
        and val_topq_delta > 0.0
        and conf_topq_delta > 0.0
        and conf_topq > 0.0
        and val_topq > 0.0
    )
    mixed = bool(
        not passed
        and val_topq_delta is not None
        and conf_topq_delta is not None
        and conf_topq is not None
        and val_topq is not None
        and val_topq_delta > 0.0
        and conf_topq_delta > 0.0
        and conf_topq > 0.0
        and val_topq > 0.0
    )
    return "PASSED" if passed else "MIXED" if mixed else "FAILED"


def _sort_results(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    work["_decision_rank"] = work["candidate_decision"].map({"BASELINE": 3, "PASSED": 2, "MIXED": 1, "FAILED": 0}).fillna(-1)
    for column in (
        "validation_top_quintile_cycle_return_net_delta_vs_all_rows",
        "confirmation_top_quintile_cycle_return_net_delta_vs_all_rows",
        "validation_auc_delta_vs_all_rows",
        "confirmation_auc_delta_vs_all_rows",
        "validation_top_quintile_cycle_return_net",
        "confirmation_top_quintile_cycle_return_net",
    ):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=[
            "_decision_rank",
            "validation_top_quintile_cycle_return_net_delta_vs_all_rows",
            "confirmation_top_quintile_cycle_return_net_delta_vs_all_rows",
            "validation_auc_delta_vs_all_rows",
            "confirmation_auc_delta_vs_all_rows",
            "regime_name",
            "model_name",
        ],
        ascending=[False, False, False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 214)
    print("H276: EVENT-TO-INTRADAY STATE TRANSITION")
    print("=" * 214)
    print(
        f"{'regime':<22} {'model':<34} {'decision':<8} {'share':>7} "
        f"{'v_auc_d':>9} {'v_topq_d':>10} {'25_auc_d':>10} {'25_topq_d':>11} "
        f"{'v_rows':>7} {'25_rows':>8}"
    )
    print("-" * 214)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.regime_name):<22} "
            f"{str(row.model_name):<34} "
            f"{str(row.candidate_decision):<8} "
            f"{float(pd.to_numeric(row.regime_share_overall, errors='coerce') or 0.0) * 100:>6.2f}% "
            f"{(_safe_float(row.validation_auc_delta_vs_all_rows) or 0.0):>+8.4f} "
            f"{(_safe_float(row.validation_top_quintile_cycle_return_net_delta_vs_all_rows) or 0.0):>+9.4f} "
            f"{(_safe_float(row.confirmation_auc_delta_vs_all_rows) or 0.0):>+9.4f} "
            f"{(_safe_float(row.confirmation_top_quintile_cycle_return_net_delta_vs_all_rows) or 0.0):>+10.4f} "
            f"{int(pd.to_numeric(row.validation_count, errors='coerce') or 0):>7d} "
            f"{int(pd.to_numeric(row.confirmation_count, errors='coerce') or 0):>8d}"
        )


def main() -> None:
    args = parse_args()
    h258_summary_path = Path(args.h258_summary)
    h258_summary = load_summary_payload(h258_summary_path)
    if not bool(h258_summary.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_event_to_intraday_state_transition",
            name="h276_event_to_intraday_state_transition",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape intraday contract audit",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    disagreement_state = _build_intraday_disagreement_state(
        matrix_path=Path(args.matrix),
        h258_summary_path=h258_summary_path,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    breakout_panel = _build_breakout_event_panel(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        event_surface_path=Path(args.event_surface),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        candidate_cache_path=Path(args.candidate_cache),
        labels_cache_path=Path(args.labels_cache),
        disagreement_state=disagreement_state,
    )

    regime_rows: list[dict[str, object]] = []
    baseline_lookup: dict[str, pd.Series] = {}
    regime_coverage: list[dict[str, object]] = []
    scored_frames: list[pd.DataFrame] = []

    for regime_name, flag_column, description in EVENT_REGIME_SPECS:
        if flag_column is None:
            scoped = breakout_panel.copy()
        else:
            scoped = breakout_panel.loc[breakout_panel[flag_column].fillna(False).astype(bool)].copy()
        coverage = _phase_subset_summary(scoped)
        coverage_row: dict[str, object] = {
            "regime_name": regime_name,
            "description": description,
            "share_overall": float(len(scoped) / len(breakout_panel)) if len(breakout_panel) else 0.0,
        }
        for phase in ("dev", "validation", "confirmation"):
            coverage_row[f"{phase}_rows"] = coverage[phase]["rows"]
            coverage_row[f"{phase}_dates"] = coverage[phase]["dates"]
            coverage_row[f"{phase}_tickers"] = coverage[phase]["tickers"]
        regime_coverage.append(coverage_row)
        if scoped.empty:
            continue

        for spec in MODEL_SPECS:
            try:
                fit = fit_entry_model(scoped, spec=spec, protocol=INTRADAY_RESTART_PROTOCOL)
            except ValueError:
                continue
            row = dict(fit.summary_row)
            row["regime_name"] = regime_name
            row["regime_description"] = description
            row["regime_share_overall"] = coverage_row["share_overall"]
            for phase in ("dev", "validation", "confirmation"):
                row[f"{phase}_rows"] = coverage[phase]["rows"]
                row[f"{phase}_dates"] = coverage[phase]["dates"]
                row[f"{phase}_tickers"] = coverage[phase]["tickers"]
            regime_rows.append(row)

            scored = fit.scored_dataset[
                [
                    "time",
                    "ticker",
                    "research_phase",
                    "buy_now_label",
                    "cycle_return_net",
                    "fade_tension_disagreement",
                    "intraday_shape_core_disagreement",
                ]
            ].copy()
            scored["regime_name"] = regime_name
            scored["model_name"] = spec.name
            scored[f"entry_prob__{spec.name}"] = fit.scored_dataset[f"entry_prob__{spec.name}"]
            scored_frames.append(scored)

    results = pd.DataFrame(regime_rows)
    if results.empty:
        raise ValueError("H276 produced no candidate results")

    for spec in MODEL_SPECS:
        baseline_rows = results.loc[
            (results["regime_name"].astype(str) == "all_rows")
            & (results["model_name"].astype(str) == spec.name)
        ].copy()
        if baseline_rows.empty:
            continue
        baseline = baseline_rows.iloc[0]
        baseline_lookup[spec.name] = baseline

    if not baseline_lookup:
        raise ValueError("H276 requires at least one ungated all-rows baseline result")

    decision_rows: list[dict[str, object]] = []
    for row in results.to_dict(orient="records"):
        work = dict(row)
        model_name = str(work["model_name"])
        baseline = baseline_lookup.get(model_name)
        if baseline is not None:
            for phase in ("validation", "confirmation"):
                for metric in ("auc", "top_quintile_cycle_return_net"):
                    column = f"{phase}_{metric}"
                    baseline_value = _safe_float(baseline.get(column))
                    current_value = _safe_float(work.get(column))
                    delta_column = f"{column}_delta_vs_all_rows"
                    work[delta_column] = (
                        None
                        if baseline_value is None or current_value is None
                        else float(current_value - baseline_value)
                    )
        work["candidate_decision"] = "BASELINE" if str(work["regime_name"]) == "all_rows" else _candidate_decision(pd.Series(work))
        work["promoted_event_condition"] = bool(work["candidate_decision"] == "PASSED")
        decision_rows.append(work)

    results = _sort_results(pd.DataFrame(decision_rows))
    promoted = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not promoted.empty else "MIXED" if not mixed.empty else "FAILED"
    candidate_results = results.loc[results["regime_name"].astype(str) != "all_rows"].copy()
    best_candidate = (
        candidate_results.iloc[0].to_dict()
        if not candidate_results.empty
        else {}
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h276_event_to_intraday_state_transition_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h276_event_to_intraday_state_transition_audit_panel.parquet"
    results.to_parquet(results_path, index=False)
    breakout_panel[
        [
            "time",
            "ticker",
            "research_phase",
            "buy_now_label",
            "cycle_return_net",
            "selection_score",
            "candidate_pool_rank",
            "fade_tension_disagreement",
            "intraday_shape_core_disagreement",
            "report_window_any",
            "recent_filing_any",
            "event_transition_any",
            "recent_any_filing_5d",
            "recent_any_filing_20d",
            "event_density_20d",
            "has_any_event_history",
        ]
    ].to_parquet(panel_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "breakout_rows": int(len(breakout_panel)),
        "breakout_dates": int(breakout_panel["time"].nunique()),
        "breakout_tickers": int(breakout_panel["ticker"].nunique()),
        "regime_coverage": regime_coverage,
        "all_rows_baselines": [
            results.loc[
                (results["regime_name"].astype(str) == "all_rows")
                & (results["model_name"].astype(str) == spec.name)
            ][
                [
                    "regime_name",
                    "model_name",
                    "validation_auc",
                    "validation_top_quintile_cycle_return_net",
                    "confirmation_auc",
                    "confirmation_top_quintile_cycle_return_net",
                ]
            ].iloc[0].to_dict()
            for spec in MODEL_SPECS
            if ((results["regime_name"].astype(str) == "all_rows") & (results["model_name"].astype(str) == spec.name)).any()
        ],
        "best_candidate": best_candidate,
        "promoted_candidates": promoted[
            [
                "regime_name",
                "model_name",
                "validation_auc_delta_vs_all_rows",
                "validation_top_quintile_cycle_return_net_delta_vs_all_rows",
                "confirmation_auc_delta_vs_all_rows",
                "confirmation_top_quintile_cycle_return_net_delta_vs_all_rows",
                "validation_top_quintile_cycle_return_net",
                "confirmation_top_quintile_cycle_return_net",
            ]
        ].to_dict("records"),
        "mixed_candidates": mixed[
            [
                "regime_name",
                "model_name",
                "validation_auc_delta_vs_all_rows",
                "validation_top_quintile_cycle_return_net_delta_vs_all_rows",
                "confirmation_auc_delta_vs_all_rows",
                "confirmation_top_quintile_cycle_return_net_delta_vs_all_rows",
                "validation_top_quintile_cycle_return_net",
                "confirmation_top_quintile_cycle_return_net",
            ]
        ].to_dict("records"),
        "advance_to_h277": bool(decision == "PASSED"),
        "pause_timing_model_invention": bool(decision == "FAILED"),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_event_to_intraday_state_transition",
        name="h276_event_to_intraday_state_transition",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "audit_panel": str(panel_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "branch_contract": (
                "Breakout-followthrough buyable candidate subset only, 2023-2025 only, "
                "row-level event regimes intersected with H275 disagreement states from the observed reduced-shape matrix."
            ),
            "event_surface": str(args.event_surface),
            "intraday_source": str(resolve_summary_artifact(h258_summary_path, "reduced_shape_panel")),
        },
    )
    _print_table(results)


if __name__ == "__main__":
    main()
