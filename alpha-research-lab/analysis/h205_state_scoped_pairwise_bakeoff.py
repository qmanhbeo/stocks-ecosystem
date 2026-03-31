"""
H205: State-scoped pairwise additive blend for promoted H203 pair candidate(s).

Purpose:
- test whether the promoted H203 pair only helps inside liq_open_basic
- compare pairwise state blends against the current offline lead selector
- only run if H203 promotes at least one true pair candidate

Usage:
    conda run -n stocks python analysis/h205_state_scoped_pairwise_bakeoff.py
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
    summary_is_skipped,
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
H201_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json"
H203_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_pairwise_additive_bakeoff.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"
PAIR_WEIGHTS = (0.10, 0.20, 0.30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--h203-summary", type=str, default=str(H203_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 210)
    print("H205: STATE-SCOPED PAIRWISE BAKEOFF")
    print("=" * 210)
    print(
        f"{'strategy':<72} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'cash_val':>9} {'turn_val':>9} {'promote':>8}"
    )
    print("-" * 210)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<72} "
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


def _load_h201_winner(summary_path: Path) -> tuple[pd.DataFrame, str | None]:
    if summary_is_skipped(summary_path):
        return pd.DataFrame(), None
    results_path = resolve_summary_artifact(summary_path, "results")
    results = pd.read_parquet(results_path)
    promoted = results.loc[results["promoted"]].copy()
    if promoted.empty:
        return results, None
    winner = str(
        promoted.sort_values(
            by=[
                "validation_relative_delta",
                "validation_ir_delta",
                "confirmation_relative_delta",
                "validation_avg_cash_weight",
                "validation_avg_daily_turnover",
                "strategy_name",
            ],
            ascending=[False, False, False, True, True, True],
        ).iloc[0]["strategy_name"]
    )
    return results, winner


def _load_h203_promoted_pairs(summary_path: Path) -> tuple[pd.DataFrame, list[str], bool]:
    if summary_is_skipped(summary_path):
        return pd.DataFrame(), [], True
    results_path = resolve_summary_artifact(summary_path, "results")
    results = pd.read_parquet(results_path)
    promoted = results.loc[results["promoted"]].copy()
    pair_names = [
        str(name)
        for name in promoted["strategy_name"].tolist()
        if str(name).startswith("full_library_pair__")
    ]
    return results, pair_names, False


def _parse_state_blend_name(strategy_name: str) -> tuple[str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "state_blend":
        raise ValueError(f"Expected state blend strategy name, got {strategy_name!r}")
    atom = parts[1]
    atom_weight = float(parts[2]) / 100.0
    return atom, atom_weight


def _parse_pair_name(strategy_name: str) -> tuple[str, str]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "full_library_pair":
        raise ValueError(f"Expected H203 pair strategy name, got {strategy_name!r}")
    return parts[1], parts[2]


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    _, h201_winner = _load_h201_winner(Path(args.h201_summary))
    h203_results, promoted_pairs, upstream_skipped = _load_h203_promoted_pairs(Path(args.h203_summary))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if h201_winner is None:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H201 produced no promoted winner",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_state_scoped_pairwise_bakeoff",
            name="h205_state_scoped_pairwise_bakeoff",
            summary=summary,
            artifacts={},
            metadata={"protocol": protocol.describe(), "h201_summary": str(args.h201_summary)},
        )
        print("H205 skipped: H201 produced no promoted winner.")
        return
    if upstream_skipped or not promoted_pairs:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H203 produced no promoted pair candidate",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_state_scoped_pairwise_bakeoff",
            name="h205_state_scoped_pairwise_bakeoff",
            summary=summary,
            artifacts={},
            metadata={
                "protocol": protocol.describe(),
                "h201_summary": str(args.h201_summary),
                "h203_summary": str(args.h203_summary),
            },
        )
        print("H205 skipped: H203 produced no promoted pair candidate.")
        return

    lead_atom, lead_weight = _parse_state_blend_name(h201_winner)
    pair_atoms = [_parse_pair_name(name) for name in promoted_pairs]
    required_atoms = sorted({lead_atom, *[atom for pair in pair_atoms for atom in pair]})

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    missing_atoms = sorted(set(required_atoms) - set(candidate_frame.columns))
    if missing_atoms:
        raise ValueError(f"Missing H205 atom columns: {missing_atoms}")

    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", "tv_to_adv20", "clv", "can_buy_next_open"] + required_atoms],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    score_strategies = {"full_library_baseline": list(full_library_columns), lead_atom: [lead_atom]}
    for atom_a, atom_b in pair_atoms:
        pair_name = f"full_library_pair__{atom_a}__{atom_b}"
        score_strategies[pair_name] = list(full_library_columns) + [atom_a, atom_b]
    scored = compute_strategy_scores(merged, score_strategies)

    strategy_frame = scored[["time", "ticker", "actual", "score__full_library_baseline"]].copy()
    baseline_score = pd.to_numeric(scored["score__full_library_baseline"], errors="coerce")
    lead_score = pd.to_numeric(scored[f"score__{lead_atom}"], errors="coerce")
    strategy_frame[f"score__{h201_winner}"] = blend_state_scoped_scores(
        baseline_score,
        lead_score,
        liq_open_basic,
        atom_weight=float(lead_weight),
    )
    for atom_a, atom_b in pair_atoms:
        pair_name = f"full_library_pair__{atom_a}__{atom_b}"
        pair_score = pd.to_numeric(scored[f"score__{pair_name}"], errors="coerce")
        for pair_weight in PAIR_WEIGHTS:
            strategy_name = f"state_pair_blend__{atom_a}__{atom_b}__{int(round(pair_weight * 100.0)):02d}"
            strategy_frame[f"score__{strategy_name}"] = blend_state_scoped_scores(
                baseline_score,
                pair_score,
                liq_open_basic,
                atom_weight=float(pair_weight),
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
    strategy_names = [h201_winner] + [
        column.split("score__", 1)[1]
        for column in strategy_frame.columns
        if column.startswith("score__state_pair_blend__")
    ]
    for strategy_name in strategy_names:
        signal_columns = [h201_winner] if strategy_name == h201_winner else [strategy_name]
        result = run_selector_candidate(
            scored_frame=strategy_frame,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=list(signal_columns),
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
    baseline = results.loc[results["strategy_name"] == h201_winner].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = False if row["strategy_name"] == h201_winner else additive_candidate_passes(row, baseline)

    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "strategy_name",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    _print_table(results)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h205_state_scoped_pairwise_bakeoff_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h205_state_scoped_pairwise_bakeoff_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["strategy_name"])].to_parquet(best_daily_path, index=False)

    promoted = results.loc[results["promoted"]].copy()
    summary = {
        "protocol": protocol.describe(),
        "baseline_strategy": h201_winner,
        "promoted_pairs_from_h203": promoted_pairs,
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
        mode="portfolio_state_scoped_pairwise_bakeoff",
        name="h205_state_scoped_pairwise_bakeoff",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={
            "protocol": protocol.describe(),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "h201_summary": str(args.h201_summary),
            "h203_summary": str(args.h203_summary),
        },
    )


if __name__ == "__main__":
    main()
