"""
H198: Activation compatibility test for the promoted additive selector winner.

Purpose:
- test whether the best H197 selector also works under the frozen sticky activation overlay
- keep activation fixed at h175__rel2_gt0 + sticky_bonus_0p015
- only run if H197 produced a promoted winner

Usage:
    conda run -n stocks python analysis/h198_selector_activation_compatibility.py
"""

from __future__ import annotations

import argparse
import json
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes, resolve_summary_artifact
from src.champion_activation_utils import align_series_to_market_dates, load_champion_setup
from src.deterministic_portfolio import build_market_inputs, load_benchmark_open, load_or_build_tradability_panel, load_price_panel, simulate_strategy
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H197_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_state_scoped_additive_bakeoff.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h197-summary", type=str, default=str(H197_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.015)
    return parser.parse_args()


def _load_h197_winner(summary_path: Path) -> tuple[pd.DataFrame, str | None]:
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if payload.get("summary", {}).get("skipped"):
        return pd.DataFrame(), None
    results_path = resolve_summary_artifact(summary_path, "results")
    results = pd.read_parquet(results_path)
    promoted = results.loc[results["promoted"]].copy()
    if promoted.empty:
        return results, None
    winner = str(promoted.sort_values(
        by=[
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "validation_avg_cash_weight",
            "validation_avg_daily_turnover",
            "strategy_name",
        ],
        ascending=[False, False, False, True, True, True],
    ).iloc[0]["strategy_name"])
    return results, winner


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 180)
    print("H198: SELECTOR / STICKY ACTIVATION COMPATIBILITY")
    print("=" * 180)
    print(
        f"{'variant':<38} {'val_rel':>10} {'d_rel':>9} {'val_IR':>8} {'d_IR':>8} "
        f"{'2025_rel':>10} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 180)
    for row in results.itertuples(index=False):
        print(
            f"{row.variant:<38} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>8.2f} "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{str(bool(row.promoted)):>8}"
        )


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    h197_results, winner_name = _load_h197_winner(Path(args.h197_summary))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if winner_name is None:
        summary = {
            "protocol": protocol.describe(),
            "skipped": True,
            "reason": "H197 produced no promoted winner",
        }
        write_run_summary(
            ts=ts,
            mode="portfolio_selector_activation_compatibility",
            name="h198_selector_activation_compatibility",
            summary=summary,
            artifacts={},
            metadata={"protocol": protocol.describe(), "h197_summary": str(args.h197_summary)},
        )
        print("H198 skipped: H197 produced no promoted winner.")
        return

    winner_row = h197_results.loc[h197_results["strategy_name"] == winner_name].iloc[0]
    candidate_results_path = resolve_summary_artifact(Path(args.h197_summary), "results")
    candidate_daily_path = resolve_summary_artifact(Path(args.h197_summary), "best_daily")
    del candidate_results_path, candidate_daily_path  # explicit resolution sanity only

    matrix = pd.read_parquet(Path(args.matrix))
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= int(args.start_year)) & (matrix["time"].dt.year <= int(args.end_year))].copy()
    if f"score__{winner_name}" not in h197_results.columns:
        pass

    h197_results_full = pd.read_parquet(resolve_summary_artifact(Path(args.h197_summary), "results"))
    best_daily_source = pd.read_parquet(resolve_summary_artifact(Path(args.h197_summary), "best_daily"))
    del best_daily_source  # artifact existence check; selector score is rebuilt from latest matrix below

    scored = pd.read_parquet(resolve_summary_artifact(Path(args.h197_summary), "results"))
    del scored  # avoid accidental use of summary table as score frame

    # Rebuild the H197 winner score frame from the strategy parquet stored in the experiment artifacts.
    h197_results_table = h197_results_full.copy()
    if winner_name not in h197_results_table["strategy_name"].tolist():
        raise ValueError(f"Winner {winner_name!r} not present in H197 results")

    from src.tradability_conditioned_research import build_candidate_signal_frame, load_research_bundle
    from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
    from src.additive_selector_research import blend_state_scoped_scores

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )
    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    atom = winner_name.split("__")[1]
    atom_weight = float(winner_name.split("__")[-1]) / 100.0
    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", atom]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    base_scored = compute_strategy_scores(
        merged,
        {"full_library": list(full_library_columns), atom: [atom]},
    )
    selector_scored = base_scored[["time", "ticker", "actual", "score__full_library"]].copy()
    selector_scored[f"score__{winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(base_scored["score__full_library"], errors="coerce"),
        pd.to_numeric(base_scored[f"score__{atom}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(atom_weight),
    )

    price_panel = load_price_panel(selector_scored["ticker"].unique().tolist(), Path(args.stock_dir))
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, Path(args.tradability))
    benchmark_open = load_benchmark_open(Path(args.benchmark))
    market_inputs = build_market_inputs(
        selector_scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=["full_library", winner_name],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )

    champion_setup = load_champion_setup(
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
    )
    activation_scale = align_series_to_market_dates((champion_setup.rel2 > 0.0).astype(float), market_inputs.dates, fill_value=0.0)
    fee_leg = float(args.round_trip_cost) / 2.0
    holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    variants = [
        {
            "variant": "winner_always_on",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": None,
            "incumbent_score_bonus": 0.0,
        },
        {
            "variant": "winner_plus_sticky",
            "strategy_name": winner_name,
            "signal_columns": [winner_name],
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
        {
            "variant": "full_library_plus_sticky",
            "strategy_name": "full_library",
            "signal_columns": list(full_library_columns),
            "activation_scale": activation_scale,
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
        },
    ]

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for spec in variants:
        result = simulate_strategy(
            strategy_name=str(spec["strategy_name"]),
            signal_columns=list(spec["signal_columns"]),
            market_inputs=market_inputs,
            top_k=5,
            rebalance_every=5,
            weighting="equal",
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=0.0,
            required_holding_age=int(holding_age),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            capital_gains_tax_rate=0.0,
            activation_scale=spec["activation_scale"],
            incumbent_score_bonus=float(spec["incumbent_score_bonus"]),
        )
        phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
        row = {"variant": str(spec["variant"]), "strategy_name": str(spec["strategy_name"])}
        for phase in ("dev", "validation", "confirmation"):
            row[f"{phase}_relative_total_return"] = phase_summary[phase]["relative_total_return"]
            row[f"{phase}_information_ratio_annualized"] = phase_summary[phase]["information_ratio_annualized"]
            row[f"{phase}_avg_cash_weight"] = phase_summary[phase]["avg_cash_weight"]
            row[f"{phase}_avg_daily_turnover"] = phase_summary[phase]["avg_daily_turnover"]
        rows.append(row)
        daily_outputs[str(spec["variant"])] = result.daily.copy()

    results = pd.DataFrame(rows)
    incumbent = results.loc[results["variant"] == "full_library_plus_sticky"].iloc[0]
    for idx, row in results.iterrows():
        deltas = additive_candidate_deltas(row, incumbent)
        for key, value in deltas.items():
            results.loc[idx, key] = value
        results.loc[idx, "promoted"] = (
            False
            if row["variant"] != "winner_plus_sticky"
            else additive_candidate_passes(row, incumbent)
        )

    results = results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    _print_table(results)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h198_selector_activation_compatibility_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h198_selector_activation_compatibility_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(results.iloc[0]["variant"])].to_parquet(best_daily_path, index=False)

    summary = {
        "protocol": protocol.describe(),
        "h197_winner": winner_row.to_dict(),
        "incumbent": incumbent.to_dict(),
        "winner_selector_always_on": results.loc[results["variant"] == "winner_always_on"].iloc[0].to_dict(),
        "winner_selector_plus_sticky": results.loc[results["variant"] == "winner_plus_sticky"].iloc[0].to_dict(),
        "promoted": bool(results.loc[results["variant"] == "winner_plus_sticky", "promoted"].iloc[0]),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_selector_activation_compatibility",
        name="h198_selector_activation_compatibility",
        summary=summary,
        artifacts={"results": str(results_path), "best_daily": str(best_daily_path)},
        metadata={
            "protocol": protocol.describe(),
            "h197_summary": str(args.h197_summary),
            "incumbent_score_bonus": float(args.incumbent_score_bonus),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )


if __name__ == "__main__":
    main()
