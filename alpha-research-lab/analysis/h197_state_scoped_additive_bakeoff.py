"""
H197: State-scoped additive bakeoff for promoted H196 atoms.

Purpose:
- test whether additive atoms only help inside tradable / liquidity-opening states
- keep the selector backbone fixed outside the state
- only run if H196 produced promoted atoms

Usage:
    conda run -n stocks python analysis/h197_state_scoped_additive_bakeoff.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.additive_selector_research import (
    additive_candidate_deltas,
    additive_candidate_passes,
    blend_state_scoped_scores,
    resolve_summary_artifact,
)
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    build_candidate_signal_frame,
    compute_phase_portfolio_summary,
    evaluate_signal_ic_by_phase,
    load_research_bundle,
    run_selector_candidate,
)


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H196_SUMMARY_PATH = Path("artifacts/run_summaries/latest_portfolio_additive_atom_bakeoff.json")
OUT_DIR = Path("artifacts/portfolio_baselines")
ATOM_WEIGHTS = (0.10, 0.20, 0.30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h196-summary", type=str, default=str(H196_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 196)
    print("H197: STATE-SCOPED ADDITIVE BAKEOFF")
    print("=" * 196)
    print(
        f"{'strategy':<54} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'cash_val':>9} {'turn_val':>9} {'promote':>8}"
    )
    print("-" * 196)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<54} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_avg_cash_weight if row.validation_avg_cash_weight is not None else float('nan'):>9.4f} "
            f"{row.validation_avg_daily_turnover if row.validation_avg_daily_turnover is not None else float('nan'):>9.4f} "
            f"{str(bool(row.promoted)):>8}"
        )


def _load_h196_promoted(summary_path: Path) -> tuple[pd.DataFrame, list[str]]:
    results_path = resolve_summary_artifact(summary_path, "results")
    results = pd.read_parquet(results_path)
    promoted_rows = results.loc[results["promoted"]].copy()
    atoms = []
    for strategy_name in promoted_rows["strategy_name"].tolist():
        if "full_library_plus__" in str(strategy_name):
            atoms.append(str(strategy_name).split("full_library_plus__", 1)[1])
    return results, atoms


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    h196_results, promoted_atoms = _load_h196_promoted(Path(args.h196_summary))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if not promoted_atoms:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H196 produced no promoted atoms",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_state_scoped_additive_bakeoff",
            name="h197_state_scoped_additive_bakeoff",
            summary=summary,
            artifacts={},
            metadata={"protocol": protocol.describe(), "h196_summary": str(args.h196_summary)},
        )
        print("H197 skipped: H196 produced no promoted atoms.")
        return

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    missing_atoms = sorted(set(promoted_atoms) - set(candidate_frame.columns))
    if missing_atoms:
        raise ValueError(f"Missing promoted H196 atoms for H197: {missing_atoms}")

    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", "s1_proba", "tv_to_adv20", "clv", "can_buy_next_open"] + promoted_atoms],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    scored = compute_strategy_scores(
        merged,
        {"full_library_baseline": list(full_library_columns), **{atom: [atom] for atom in promoted_atoms}},
    )
    strategy_frame = scored[["time", "ticker", "actual", "score__full_library_baseline"]].copy()
    base_score = pd.to_numeric(scored["score__full_library_baseline"], errors="coerce")
    for atom in promoted_atoms:
        atom_score = pd.to_numeric(scored[f"score__{atom}"], errors="coerce")
        for atom_weight in ATOM_WEIGHTS:
            name = f"state_blend__{atom}__{int(round(atom_weight * 100.0)):02d}"
            strategy_frame[f"score__{name}"] = blend_state_scoped_scores(
                base_score,
                atom_score,
                liq_open_basic,
                atom_weight=float(atom_weight),
            )

    scored_with_states = strategy_frame.merge(
        merged[["time", "ticker", "s1_proba", "tv_to_adv20", "clv", "can_buy_next_open"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    strategy_names = ["full_library_baseline"] + [column.split("score__", 1)[1] for column in strategy_frame.columns if column.startswith("score__state_blend__")]
    for strategy_name in strategy_names:
        signal_columns = list(full_library_columns) if strategy_name == "full_library_baseline" else [strategy_name]
        result = run_selector_candidate(
            scored_frame=strategy_frame,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=signal_columns,
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        ic_basic = evaluate_signal_ic_by_phase(
            scored_with_states,
            signal_column=f"score__{strategy_name}",
            state_mask=liq_open_basic,
            protocol=protocol,
        )
        row = {
            "strategy_name": strategy_name,
            "overall_relative_total_return": float(result.summary["relative_total_return"]),
            "overall_information_ratio_annualized": result.summary["information_ratio_annualized"],
        }
        for phase in ("dev", "validation", "confirmation"):
            row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
            row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
            row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
            row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
            row[f"liq_open_basic_{phase}_avg_ic"] = ic_basic[phase]["avg_ic"]
            row[f"liq_open_basic_{phase}_corr_with_s1"] = ic_basic[phase]["corr_with_s1"]
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = (
            False if row["strategy_name"] == "full_library_baseline" else additive_candidate_passes(row, baseline)
        )

    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "validation_avg_cash_weight",
            "validation_avg_daily_turnover",
            "strategy_name",
        ],
        ascending=[False, False, False, False, True, True, True],
        ignore_index=True,
    )

    _print_table(results)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h197_state_scoped_additive_bakeoff_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h197_state_scoped_additive_bakeoff_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["strategy_name"])].to_parquet(best_daily_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    summary = {
        "protocol": protocol.describe(),
        "h196_promoted_atoms": promoted_atoms,
        "baseline": baseline.to_dict(),
        "winner": results.iloc[0].to_dict(),
        "promoted_candidates": promoted[
            [
                "strategy_name",
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "confirmation_ir_delta",
            ]
        ].to_dict("records"),
        "tested_candidates": results[
            [
                "strategy_name",
                "validation_relative_total_return",
                "validation_relative_delta",
                "validation_information_ratio_annualized",
                "validation_ir_delta",
                "confirmation_relative_total_return",
                "confirmation_relative_delta",
                "promoted",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_state_scoped_additive_bakeoff",
        name="h197_state_scoped_additive_bakeoff",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={
            "protocol": protocol.describe(),
            "h196_summary": str(args.h196_summary),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )


if __name__ == "__main__":
    main()
