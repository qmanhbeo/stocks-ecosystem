"""
H274: top-k intraday stress router audit on the frozen sticky branch.
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
from src.champion_activation_utils import current_live_variant, load_champion_setup, run_champion_variant
from src.intraday_exit_research import build_intraday_router_feature_frame
from src.research_protocol import ResearchProtocol
from src.run_summary import write_run_summary


STOCK_DIR = data_path("stock")
RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
CURRENT_LIVE_VARIANT = current_live_variant()
HIT_CORR_FLOOR = 0.10
HIGH_STRESS_QUANTILE = 0.80
BASELINE_VARIANT = "slow_blocked5_proxy"
BASELINE_SCORE_COLUMN = "full_recent_blocked_buy_ewm5"
INTRADAY_SCORE_SPECS = (
    ("stress_fade", "topk_first_hour_fade_mean"),
    ("stress_failed_breakout", "topk_failed_breakout_mean"),
    ("stress_weak_close_repair", "topk_weak_close_repair_mean"),
    ("stress_composite_mean", "topk_intraday_stress_mean"),
    ("stress_name_share_q70", "topk_intraday_stress_name_share_q70"),
)
ENDPOINT_SPECS = (
    ("blocked_buy_count", "blocked_buy_count", 1.0),
    ("cash_weight", "cash_weight", 1.0),
    ("full_top5_prev_overlap_ratio", "replacement_overlap", -1.0),
    ("full_top5_buyable_count", "top5_buyable_count", -1.0),
    ("next_cycle_relative_return", "next_cycle_relative_return", -1.0),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H274: top-k intraday stress router audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--history-start-year", type=int, default=2019)
    parser.add_argument("--eval-start-year", type=int, default=2023)
    parser.add_argument("--eval-end-year", type=int, default=2025)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    return parser.parse_args()


def _safe_corr(frame: pd.DataFrame, x_column: str, y_column: str) -> float | None:
    work = frame[[x_column, y_column]].copy()
    work[x_column] = pd.to_numeric(work[x_column], errors="coerce")
    work[y_column] = pd.to_numeric(work[y_column], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    if len(work) < 5:
        return None
    if work[x_column].nunique(dropna=True) < 2 or work[y_column].nunique(dropna=True) < 2:
        return None
    corr = work[x_column].corr(work[y_column], method="spearman")
    return None if pd.isna(corr) else float(corr)


def _safe_mean(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def _quantile(series: pd.Series, quantile: float) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return None
    return float(numeric.quantile(float(quantile)))


def _add_daily_stress_ranks(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()

    stress_specs = (
        ("first_hour_fade_proxy", "stress_fade", False),
        ("failed_breakout_proxy", "stress_failed_breakout", False),
        ("weak_open_strong_close_proxy", "stress_weak_close_repair", True),
    )
    for source_column, out_column, invert in stress_specs:
        values = pd.to_numeric(work[source_column], errors="coerce")
        ranks = values.groupby(work["time"], sort=False).rank(method="average", pct=True)
        work[out_column] = (1.0 - ranks) if invert else ranks

    work["stress_composite_mean"] = work[
        ["stress_fade", "stress_failed_breakout", "stress_weak_close_repair"]
    ].mean(axis=1)
    work["stress_name_share_q70_flag"] = pd.to_numeric(
        work["stress_composite_mean"],
        errors="coerce",
    ) >= 0.70
    return work


def _cycle_relative_return(
    frame: pd.DataFrame,
    *,
    portfolio_value_column: str = "portfolio_value_vnd",
    benchmark_value_column: str = "benchmark_value_vnd",
) -> pd.Series:
    work = frame.copy()
    next_portfolio = pd.to_numeric(work[portfolio_value_column], errors="coerce").shift(-1)
    next_benchmark = pd.to_numeric(work[benchmark_value_column], errors="coerce").shift(-1)
    current_portfolio = pd.to_numeric(work[portfolio_value_column], errors="coerce")
    current_benchmark = pd.to_numeric(work[benchmark_value_column], errors="coerce")
    return (next_portfolio / current_portfolio - 1.0) - (next_benchmark / current_benchmark - 1.0)


def _build_overlap_ratio(requested_tickers: pd.Series) -> pd.Series:
    prev: set[str] | None = None
    values: list[float | None] = []
    for raw in requested_tickers.tolist():
        current = {str(value) for value in list(raw or [])}
        if prev is None:
            values.append(None)
        else:
            values.append(float(len(current & prev) / max(len(current | prev), 1)))
        prev = current
    return pd.Series(values, index=requested_tickers.index, dtype=float)


def _topk_intraday_summary(router_frame: pd.DataFrame, rebalance_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in rebalance_frame.itertuples(index=False):
        signal_date = pd.Timestamp(row.signal_date).normalize()
        requested_tickers = [str(value) for value in list(row.requested_tickers or [])]
        subset = router_frame.loc[
            (router_frame["time"] == signal_date) & router_frame["ticker"].isin(requested_tickers)
        ].copy()
        rows.append(
            {
                "signal_date": signal_date,
                "requested_count": int(len(requested_tickers)),
                "observed_count": int(len(subset)),
                "observed_share": float(len(subset) / max(len(requested_tickers), 1)) if requested_tickers else None,
                "topk_first_hour_fade_mean": _safe_mean(subset["stress_fade"]),
                "topk_failed_breakout_mean": _safe_mean(subset["stress_failed_breakout"]),
                "topk_weak_close_repair_mean": _safe_mean(subset["stress_weak_close_repair"]),
                "topk_intraday_stress_mean": _safe_mean(subset["stress_composite_mean"]),
                "topk_intraday_stress_name_share_q70": _safe_mean(subset["stress_name_share_q70_flag"]),
            }
        )
    return pd.DataFrame(rows)


def _gate_cycle_stats(frame: pd.DataFrame, score_column: str, threshold: float | None) -> dict[str, float | None]:
    if threshold is None:
        return {
            "high_stress_share": None,
            "high_stress_cycle_mean": None,
            "low_stress_cycle_mean": None,
            "high_minus_low_cycle_delta": None,
        }

    work = frame[[score_column, "next_cycle_relative_return"]].copy()
    work[score_column] = pd.to_numeric(work[score_column], errors="coerce")
    work["next_cycle_relative_return"] = pd.to_numeric(work["next_cycle_relative_return"], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    if work.empty:
        return {
            "high_stress_share": None,
            "high_stress_cycle_mean": None,
            "low_stress_cycle_mean": None,
            "high_minus_low_cycle_delta": None,
        }

    high = work.loc[work[score_column] >= float(threshold)].copy()
    low = work.loc[work[score_column] < float(threshold)].copy()
    high_mean = _safe_mean(high["next_cycle_relative_return"])
    low_mean = _safe_mean(low["next_cycle_relative_return"])
    delta = None
    if high_mean is not None and low_mean is not None:
        delta = float(high_mean - low_mean)
    return {
        "high_stress_share": float(len(high) / len(work)) if len(work) else None,
        "high_stress_cycle_mean": high_mean,
        "low_stress_cycle_mean": low_mean,
        "high_minus_low_cycle_delta": delta,
    }


def _evaluate_score_variants(audit_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    dev_frame = audit_frame.loc[audit_frame["research_phase"] == "dev"].copy()

    all_specs = list(INTRADAY_SCORE_SPECS) + [(BASELINE_VARIANT, BASELINE_SCORE_COLUMN)]
    for variant, score_column in all_specs:
        threshold = _quantile(dev_frame[score_column], HIGH_STRESS_QUANTILE)
        row: dict[str, object] = {
            "variant": variant,
            "score_column": score_column,
            "dev_q80_threshold": threshold,
        }
        for phase in ("validation", "confirmation"):
            phase_frame = audit_frame.loc[audit_frame["research_phase"] == phase].copy()
            hits = 0
            for endpoint_column, metric_name, expected_sign in ENDPOINT_SPECS:
                corr = _safe_corr(phase_frame, score_column, endpoint_column)
                row[f"{phase}_{metric_name}_spearman"] = corr
                if corr is not None:
                    if expected_sign > 0.0 and corr >= HIT_CORR_FLOOR:
                        hits += 1
                    if expected_sign < 0.0 and corr <= -HIT_CORR_FLOOR:
                        hits += 1
            row[f"{phase}_directional_hits"] = int(hits)
            row[f"{phase}_row_count"] = int(len(phase_frame))

            gate_stats = _gate_cycle_stats(phase_frame, score_column, threshold)
            row[f"{phase}_high_stress_share"] = gate_stats["high_stress_share"]
            row[f"{phase}_high_stress_cycle_mean"] = gate_stats["high_stress_cycle_mean"]
            row[f"{phase}_low_stress_cycle_mean"] = gate_stats["low_stress_cycle_mean"]
            row[f"{phase}_high_minus_low_cycle_delta"] = gate_stats["high_minus_low_cycle_delta"]

        if variant == BASELINE_VARIANT:
            row["candidate_decision"] = "BASELINE"
        else:
            validation_hits = int(row["validation_directional_hits"])
            confirmation_hits = int(row["confirmation_directional_hits"])
            validation_cycle_delta = pd.to_numeric(
                row.get("validation_high_minus_low_cycle_delta"),
                errors="coerce",
            )
            confirmation_cycle_delta = pd.to_numeric(
                row.get("confirmation_high_minus_low_cycle_delta"),
                errors="coerce",
            )
            passes = bool(
                validation_hits >= 3
                and confirmation_hits >= 3
                and pd.notna(validation_cycle_delta)
                and pd.notna(confirmation_cycle_delta)
                and float(validation_cycle_delta) < 0.0
                and float(confirmation_cycle_delta) < 0.0
            )
            mixed = bool(
                not passes
                and validation_hits >= 2
                and confirmation_hits >= 2
                and (
                    (pd.notna(validation_cycle_delta) and float(validation_cycle_delta) < 0.0)
                    or (pd.notna(confirmation_cycle_delta) and float(confirmation_cycle_delta) < 0.0)
                )
            )
            row["candidate_decision"] = "PASSED" if passes else "MIXED" if mixed else "FAILED"
        rows.append(row)

    return pd.DataFrame(rows)


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()

    work = results.copy()
    decision_rank = work["candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2, "BASELINE": -1}).fillna(-1)
    work["_decision_rank"] = decision_rank
    for column in (
        "validation_directional_hits",
        "confirmation_directional_hits",
        "validation_high_minus_low_cycle_delta",
        "confirmation_high_minus_low_cycle_delta",
    ):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    intraday = work.loc[work["variant"] != BASELINE_VARIANT].sort_values(
        by=[
            "_decision_rank",
            "confirmation_directional_hits",
            "validation_directional_hits",
            "confirmation_high_minus_low_cycle_delta",
            "validation_high_minus_low_cycle_delta",
            "variant",
        ],
        ascending=[False, False, False, True, True, True],
        ignore_index=True,
    )
    baseline = work.loc[work["variant"] == BASELINE_VARIANT].copy()
    return pd.concat([intraday, baseline], ignore_index=True).drop(columns="_decision_rank")


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 210)
    print("H274: TOP-K INTRADAY STRESS ROUTER AUDIT")
    print("=" * 210)
    print(
        f"{'variant':<32} {'decision':<10} {'val_hit':>7} {'conf_hit':>8} "
        f"{'val_dcyc':>10} {'conf_dcyc':>10} {'val_blk':>9} {'conf_blk':>9} "
        f"{'val_nxt':>9} {'conf_nxt':>9}"
    )
    print("-" * 210)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.variant):<32} "
            f"{str(row.candidate_decision):<10} "
            f"{int(pd.to_numeric(row.validation_directional_hits, errors='coerce') or 0):>7d} "
            f"{int(pd.to_numeric(row.confirmation_directional_hits, errors='coerce') or 0):>8d} "
            f"{(pd.to_numeric(row.validation_high_minus_low_cycle_delta, errors='coerce') or 0.0):>+9.4f} "
            f"{(pd.to_numeric(row.confirmation_high_minus_low_cycle_delta, errors='coerce') or 0.0):>+9.4f} "
            f"{(pd.to_numeric(row.validation_blocked_buy_count_spearman, errors='coerce') or 0.0):>+8.3f} "
            f"{(pd.to_numeric(row.confirmation_blocked_buy_count_spearman, errors='coerce') or 0.0):>+8.3f} "
            f"{(pd.to_numeric(row.validation_next_cycle_relative_return_spearman, errors='coerce') or 0.0):>+8.3f} "
            f"{(pd.to_numeric(row.confirmation_next_cycle_relative_return_spearman, errors='coerce') or 0.0):>+8.3f}"
        )


def main() -> None:
    args = parse_args()
    h258_summary_path = Path(args.h258_summary)
    h258_summary = load_summary_payload(h258_summary_path)
    if not bool(h258_summary.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_activation_topk_intraday_stress_router_audit",
            name="h274_topk_intraday_stress_router_audit",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape intraday contract audit",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    reduced_shape_path = resolve_summary_artifact(h258_summary_path, "reduced_shape_panel")
    reduced_shape_panel = pd.read_parquet(reduced_shape_path)
    router_frame = build_intraday_router_feature_frame(reduced_shape_panel)
    router_frame = _add_daily_stress_ranks(router_frame)

    setup = load_champion_setup(
        start_year=int(args.history_start_year),
        end_year=int(args.eval_end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
    )
    run = run_champion_variant(setup, spec=CURRENT_LIVE_VARIANT, capture_blotter=False)
    sticky_daily = run.result.daily.copy()
    sticky_daily["signal_date"] = pd.to_datetime(sticky_daily["signal_date"], errors="coerce").dt.normalize()
    sticky_daily["execution_date"] = pd.to_datetime(sticky_daily["execution_date"], errors="coerce").dt.normalize()
    sticky_daily = sticky_daily.loc[
        sticky_daily["execution_date"].dt.year.between(int(args.eval_start_year), int(args.eval_end_year))
    ].copy()
    rebalance_frame = sticky_daily.loc[
        sticky_daily["rebalance_triggered"].fillna(False).astype(bool)
        & sticky_daily["activation_on"].fillna(False).astype(bool)
    ].copy()
    rebalance_frame = rebalance_frame.sort_values("signal_date").reset_index(drop=True)
    rebalance_frame["next_cycle_relative_return"] = _cycle_relative_return(rebalance_frame)
    rebalance_frame["requested_prev_overlap_ratio"] = _build_overlap_ratio(rebalance_frame["requested_tickers"])

    summary_frame = _topk_intraday_summary(router_frame, rebalance_frame)
    meta_state = setup.meta_state.copy()
    meta_state["time"] = pd.to_datetime(meta_state["time"], errors="coerce").dt.normalize()
    audit_frame = rebalance_frame[
        [
            "signal_date",
            "execution_date",
            "blocked_buy_count",
            "cash_weight",
            "selected_count",
            "requested_tickers",
            "held_tickers",
            "requested_prev_overlap_ratio",
            "next_cycle_relative_return",
        ]
    ].copy()
    audit_frame = audit_frame.merge(summary_frame, on="signal_date", how="left", validate="one_to_one")
    audit_frame = audit_frame.merge(
        meta_state[
            [
                "time",
                "full_recent_blocked_buy_ewm5",
                "full_top5_prev_overlap_ratio",
                "full_top5_buyable_count",
                "buyable_breadth_all",
            ]
        ],
        left_on="signal_date",
        right_on="time",
        how="left",
        validate="one_to_one",
    ).drop(columns="time")
    audit_frame["research_phase"] = audit_frame["signal_date"].dt.year.map(INTRADAY_RESTART_PROTOCOL.phase_for_year)

    results = _sort_results(_evaluate_score_variants(audit_frame))
    if results.empty:
        raise ValueError("H274 produced no score variants to evaluate")

    best_intraday = results.loc[results["variant"] != BASELINE_VARIANT].iloc[0].to_dict()
    baseline = results.loc[results["variant"] == BASELINE_VARIANT].iloc[0].to_dict()
    decision = str(best_intraday.get("candidate_decision", "FAILED"))

    overall_observed_share = _safe_mean(audit_frame["observed_share"])
    validation_observed_share = _safe_mean(
        audit_frame.loc[audit_frame["research_phase"] == "validation", "observed_share"]
    )
    confirmation_observed_share = _safe_mean(
        audit_frame.loc[audit_frame["research_phase"] == "confirmation", "observed_share"]
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h274_topk_intraday_stress_router_audit_results.parquet"
    audit_path = OUT_DIR / f"{ts}_h274_topk_intraday_stress_router_audit_frame.parquet"
    sticky_daily_path = OUT_DIR / f"{ts}_h274_topk_intraday_stress_router_audit_sticky_daily.parquet"
    results.to_parquet(results_path, index=False)
    audit_frame.to_parquet(audit_path, index=False)
    rebalance_frame.to_parquet(sticky_daily_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "history_start_year": int(args.history_start_year),
        "evaluation_years": [int(args.eval_start_year), int(args.eval_end_year)],
        "live_variant": CURRENT_LIVE_VARIANT.name,
        "rebalance_row_count": int(len(audit_frame)),
        "validation_rebalance_row_count": int((audit_frame["research_phase"] == "validation").sum()),
        "confirmation_rebalance_row_count": int((audit_frame["research_phase"] == "confirmation").sum()),
        "overall_observed_share": overall_observed_share,
        "validation_observed_share": validation_observed_share,
        "confirmation_observed_share": confirmation_observed_share,
        "best_intraday_candidate": best_intraday,
        "slow_proxy_baseline": baseline,
        "advance_to_h275": bool(decision == "PASSED"),
        "advance_to_library_grade_intraday_shape_atoms": bool(decision != "PASSED"),
        "close_topk_intraday_stress_router_branch": bool(decision == "FAILED"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_topk_intraday_stress_router_audit",
        name="h274_topk_intraday_stress_router_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "audit_frame": str(audit_path),
            "sticky_rebalance_daily": str(sticky_daily_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "branch_contract": "Frozen sticky branch path 2019-2025, evaluated on 2023-2025 activated rebalance dates only",
            "intraday_source": str(reduced_shape_path),
        },
    )
    _print_table(results)


if __name__ == "__main__":
    main()
