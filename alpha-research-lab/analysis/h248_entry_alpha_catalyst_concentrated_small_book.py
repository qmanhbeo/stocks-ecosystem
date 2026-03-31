from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.entry_alpha import build_entry_allowed_matrix
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    apply_date_gate_to_entry_allowed_matrix,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_score,
    default_entry_model_specs,
    fit_entry_model,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, assign_research_phase
from src.run_summary import write_run_summary


NEWS_ROLLING_PATH = Path("data/features/xs_news_sentiment_rolling.parquet")
EVENT_SURFACE_PATH = Path("data/features/event_surface_daily.parquet")


@dataclass(frozen=True)
class ContractSpec:
    name: str
    family: str
    top_k: int
    top_m: int
    min_selection_score: float | None = None
    min_score_gap: float | None = None
    score_column: str | None = None
    score_threshold: float | None = None
    model_name: str | None = None


DEFAULT_CONTRACT_SPECS = (
    ContractSpec(
        name="h245_top1_anchor",
        family="h245_anchor",
        top_k=1,
        top_m=5,
        min_selection_score=0.60,
        min_score_gap=None,
    ),
    ContractSpec(
        name="h245_top2_anchor",
        family="h245_anchor",
        top_k=2,
        top_m=5,
        min_selection_score=0.65,
        min_score_gap=0.03,
    ),
    ContractSpec(
        name="h247_top2_price_state_side",
        family="h247_side_result",
        top_k=2,
        top_m=5,
        score_column="entry_prob__price_state",
        score_threshold=0.55,
        model_name="price_state",
    ),
)


def _coerce_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = _coerce_numeric_columns(
        results,
        columns=[
            "top_k",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "confirmation_ir_delta",
            "validation_relative_total_return",
            "confirmation_relative_total_return",
            "gate_share_overall",
        ],
    )
    return ordered.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "gate_share_overall",
            "variant",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    )


def _print_table(contract_winners: pd.DataFrame) -> None:
    print("\n" + "=" * 228)
    print("H248: ENTRY ALPHA CATALYST-CONCENTRATED SMALL-BOOK AUDIT")
    print("=" * 228)
    print(
        f"{'rank':<5} {'contract':<30} {'gate':<24} {'val_d':>9} {'2025_d':>9} "
        f"{'gate%':>8} {'val_rel':>10} {'2025_rel':>10} {'promote':>8}"
    )
    print("-" * 228)
    for idx, row in enumerate(contract_winners.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {str(row.contract_name):<30} {str(row.gate_name):<24} "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.gate_share_overall or 0.0)*100:>7.2f}% "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{str(bool(row.promoted)):>8}"
        )


def _phase_gate_summary(gated_dates: pd.Series) -> dict[str, float | None]:
    frame = pd.DataFrame({"time": pd.to_datetime(gated_dates.index), "gate_on": gated_dates.to_numpy(dtype=bool)})
    frame = assign_research_phase(frame, date_column="time", protocol=DEFAULT_PROTOCOL)
    out: dict[str, float | None] = {
        "gate_days": int(frame["gate_on"].sum()),
        "gate_share_overall": float(frame["gate_on"].mean()) if not frame.empty else None,
    }
    for phase in PHASE_ORDER:
        phase_frame = frame.loc[frame["research_phase"] == phase].copy()
        out[f"gate_share_{phase}"] = float(phase_frame["gate_on"].mean()) if not phase_frame.empty else None
    return out


def _load_catalyst_daily(
    candidate_panel: pd.DataFrame,
    *,
    top_m: int,
    news_rolling_path: Path,
    event_surface_path: Path,
) -> pd.DataFrame:
    base = candidate_panel.loc[pd.to_numeric(candidate_panel["candidate_pool_rank"], errors="coerce") <= int(top_m)].copy()
    base["time"] = pd.to_datetime(base["time"])
    base = base[["time", "ticker", "candidate_pool_rank", "c5_ins_relative_size_5d"]].copy()

    news = pd.read_parquet(news_rolling_path, columns=["time", "ticker", "has_news_5d"])
    news["time"] = pd.to_datetime(news["time"])
    news["has_news_5d"] = pd.to_numeric(news["has_news_5d"], errors="coerce").fillna(0.0)

    event_surface = pd.read_parquet(
        event_surface_path,
        columns=[
            "time",
            "ticker",
            "recent_any_filing_5d",
            "dividend_window_pre_20d",
            "issuance_window_pre_20d",
        ],
    )
    event_surface["time"] = pd.to_datetime(event_surface["time"])
    for column in ["recent_any_filing_5d", "dividend_window_pre_20d", "issuance_window_pre_20d"]:
        event_surface[column] = pd.to_numeric(event_surface[column], errors="coerce").fillna(0.0)

    merged = base.merge(news, on=["time", "ticker"], how="left").merge(event_surface, on=["time", "ticker"], how="left")
    merged["has_news_catalyst"] = pd.to_numeric(merged["has_news_5d"], errors="coerce").fillna(0.0) > 0.0
    merged["has_insider_catalyst"] = pd.to_numeric(merged["c5_ins_relative_size_5d"], errors="coerce").fillna(0.0) > 0.0
    merged["has_filing_catalyst"] = pd.to_numeric(merged["recent_any_filing_5d"], errors="coerce").fillna(0.0) > 0.0
    merged["has_corp_action_catalyst"] = (
        (pd.to_numeric(merged["dividend_window_pre_20d"], errors="coerce").fillna(0.0) > 0.0)
        | (pd.to_numeric(merged["issuance_window_pre_20d"], errors="coerce").fillna(0.0) > 0.0)
    )
    family_columns = [
        "has_news_catalyst",
        "has_insider_catalyst",
        "has_filing_catalyst",
        "has_corp_action_catalyst",
    ]
    merged["catalyst_family_count"] = merged[family_columns].astype(int).sum(axis=1)
    merged["has_any_catalyst"] = merged["catalyst_family_count"] >= 1
    merged["has_high_conviction_catalyst"] = (
        merged["has_insider_catalyst"] | merged["has_filing_catalyst"] | merged["has_corp_action_catalyst"]
    )
    merged["has_multi_source_catalyst"] = merged["catalyst_family_count"] >= 2
    merged["has_news_or_insider_catalyst"] = merged["has_news_catalyst"] | merged["has_insider_catalyst"]

    daily = (
        merged.groupby("time", sort=True)
        .agg(
            top_m_candidates=("ticker", "size"),
            any_catalyst_count=("has_any_catalyst", "sum"),
            high_conviction_count=("has_high_conviction_catalyst", "sum"),
            multi_source_count=("has_multi_source_catalyst", "sum"),
            news_or_insider_count=("has_news_or_insider_catalyst", "sum"),
            news_count=("has_news_catalyst", "sum"),
            insider_count=("has_insider_catalyst", "sum"),
            filing_count=("has_filing_catalyst", "sum"),
            corp_action_count=("has_corp_action_catalyst", "sum"),
        )
        .reset_index()
    )
    daily["any_catalyst_share"] = (
        pd.to_numeric(daily["any_catalyst_count"], errors="coerce")
        / pd.to_numeric(daily["top_m_candidates"], errors="coerce").replace(0, np.nan)
    ).fillna(0.0)
    daily["highconv_ge1"] = pd.to_numeric(daily["high_conviction_count"], errors="coerce") >= 1.0
    daily["highconv_ge2"] = pd.to_numeric(daily["high_conviction_count"], errors="coerce") >= 2.0
    daily["multisource_ge1"] = pd.to_numeric(daily["multi_source_count"], errors="coerce") >= 1.0
    daily["news_or_insider_ge1"] = pd.to_numeric(daily["news_or_insider_count"], errors="coerce") >= 1.0
    return daily.sort_values("time").reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H248: catalyst-concentrated small-book audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--news-rolling", type=str, default=str(NEWS_ROLLING_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=10)
    parser.add_argument("--gate-top-m", type=int, default=5)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--candidate-panel-cache", type=str, default="")
    parser.add_argument("--base-labels-cache", type=str, default="")
    parser.add_argument("--top-results", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    candidate_panel_cache = (
        Path(args.candidate_panel_cache)
        if str(args.candidate_panel_cache).strip()
        else ENTRY_ALPHA_OUT_DIR / f"h248_candidate_panel_{int(args.start_year)}_{int(args.end_year)}.parquet"
    )
    base_labels_cache = (
        Path(args.base_labels_cache)
        if str(args.base_labels_cache).strip()
        else ENTRY_ALPHA_OUT_DIR / f"h248_base_labels_{int(args.start_year)}_{int(args.end_year)}.parquet"
    )

    inputs, candidate_panel, labels = load_or_build_entry_artifacts(
        candidate_panel_path=candidate_panel_cache,
        labels_path=base_labels_cache,
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
        top_k=5,
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    candidate_panel = candidate_panel.copy()
    candidate_panel["time"] = pd.to_datetime(candidate_panel["time"])
    candidate_panel = candidate_panel[
        (candidate_panel["time"].dt.year >= int(args.start_year))
        & (candidate_panel["time"].dt.year <= int(args.end_year))
    ].copy()
    labels = labels.copy()
    labels["time"] = pd.to_datetime(labels["time"])
    labels = labels[
        (labels["time"].dt.year >= int(args.start_year))
        & (labels["time"].dt.year <= int(args.end_year))
    ].copy()
    panel = prepare_entry_research_panel(candidate_panel, labels)

    model_specs = {spec.name: spec for spec in default_entry_model_specs(panel)}
    if "price_state" not in model_specs:
        raise ValueError("H248 requires the price_state compact model spec")
    price_state_fit = fit_entry_model(panel, spec=model_specs["price_state"])

    catalyst_daily = _load_catalyst_daily(
        candidate_panel,
        top_m=int(args.gate_top_m),
        news_rolling_path=Path(args.news_rolling),
        event_surface_path=Path(args.event_surface),
    )
    gate_columns = [
        "highconv_ge1",
        "highconv_ge2",
        "multisource_ge1",
        "news_or_insider_ge1",
    ]
    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)

    all_results: list[pd.DataFrame] = []
    winner_rows: list[dict[str, object]] = []
    winner_daily_outputs: list[pd.DataFrame] = []

    for contract in DEFAULT_CONTRACT_SPECS:
        if contract.score_column is None:
            base_entry_allowed = build_entry_allowed_matrix(
                candidate_panel,
                dates=market_dates,
                tickers=market_tickers,
                top_m=int(contract.top_m),
                min_selection_score=contract.min_selection_score,
                min_score_gap=contract.min_score_gap,
                require_buyable=True,
            )
        else:
            base_entry_allowed = build_entry_allowed_matrix_from_score(
                price_state_fit.scored_dataset,
                dates=market_dates,
                tickers=market_tickers,
                score_column=str(contract.score_column),
                top_m=int(contract.top_m),
                min_score=float(contract.score_threshold),
                require_buyable=True,
            )

        baseline_variant = f"{contract.name}__always_on"
        baseline_result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=base_entry_allowed,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(contract.top_k),
            rebalance_every=int(args.rebalance_every),
        )
        rows = [
            backtest_row_from_result(
                variant=baseline_variant,
                family=contract.family,
                result=baseline_result,
                extra={
                    "contract_name": contract.name,
                    "gate_name": "always_on",
                    "top_k": int(contract.top_k),
                    "top_m": int(contract.top_m),
                    "min_selection_score": contract.min_selection_score,
                    "min_score_gap": contract.min_score_gap,
                    "model_name": contract.model_name,
                    "score_threshold": contract.score_threshold,
                    "gate_days": None,
                    "gate_share_overall": None,
                    "gate_share_dev": None,
                    "gate_share_validation": None,
                    "gate_share_confirmation": None,
                    "gate_share_forward": None,
                },
            )
        ]
        daily_outputs: dict[str, pd.DataFrame] = {baseline_variant: baseline_result.daily.copy()}

        for gate_name in gate_columns:
            gate_by_date = {
                pd.Timestamp(time): bool(flag)
                for time, flag in zip(catalyst_daily["time"], catalyst_daily[gate_name].astype(bool))
            }
            gated_entry_allowed = apply_date_gate_to_entry_allowed_matrix(
                base_entry_allowed,
                dates=market_dates,
                allowed_by_date=gate_by_date,
            )
            gated_result = run_entry_backtest(
                inputs,
                entry_allowed_matrix=gated_entry_allowed,
                round_trip_cost=float(args.round_trip_cost),
                required_holding_age=int(args.required_holding_age),
                initial_notional_vnd=float(args.initial_notional_vnd),
                top_k=int(contract.top_k),
                rebalance_every=int(args.rebalance_every),
            )
            gate_series = catalyst_daily.set_index("time")[gate_name].astype(bool)
            rows.append(
                backtest_row_from_result(
                    variant=f"{contract.name}__{gate_name}",
                    family=contract.family,
                    result=gated_result,
                    extra={
                        "contract_name": contract.name,
                        "gate_name": gate_name,
                        "top_k": int(contract.top_k),
                        "top_m": int(contract.top_m),
                        "min_selection_score": contract.min_selection_score,
                        "min_score_gap": contract.min_score_gap,
                        "model_name": contract.model_name,
                        "score_threshold": contract.score_threshold,
                        **_phase_gate_summary(gate_series),
                    },
                )
            )
            daily_outputs[f"{contract.name}__{gate_name}"] = gated_result.daily.copy()

        results = _sort_results(add_baseline_deltas(pd.DataFrame(rows), baseline_variant=baseline_variant))
        contract_rows = results.loc[results["variant"] != baseline_variant].copy().reset_index(drop=True)
        winner_row = contract_rows.iloc[0].to_dict()
        winner_row["baseline_variant"] = baseline_variant
        all_results.append(results)
        winner_rows.append(winner_row)
        winner_daily_outputs.append(
            daily_outputs[str(winner_row["variant"])].copy().assign(
                contract_name=contract.name,
                variant=str(winner_row["variant"]),
            )
        )

    results = pd.concat([frame for frame in all_results if not frame.empty], ignore_index=True)
    contract_winners = _sort_results(pd.DataFrame(winner_rows))
    _print_table(contract_winners.head(max(int(args.top_results), 1)))

    promoted_mask = pd.Series(results["promoted"], dtype="boolean").fillna(False).to_numpy(dtype=bool)
    promoted_candidates = results.loc[promoted_mask].copy()
    promoted_candidates = promoted_candidates.loc[promoted_candidates["gate_name"] != "always_on"].copy()
    best_nonbaseline = _sort_results(results.loc[results["gate_name"] != "always_on"].copy())

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h248_entry_alpha_catalyst_concentrated_small_book_results.parquet"
    winners_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h248_entry_alpha_catalyst_concentrated_small_book_contract_winners.parquet"
    catalyst_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h248_entry_alpha_catalyst_concentrated_small_book_catalyst_daily.parquet"
    selected_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h248_entry_alpha_catalyst_concentrated_small_book_selected_daily.parquet"
    results.to_parquet(results_path, index=False)
    contract_winners.to_parquet(winners_path, index=False)
    catalyst_daily.to_parquet(catalyst_daily_path, index=False)
    pd.concat(winner_daily_outputs, ignore_index=True).to_parquet(selected_daily_path, index=False)

    summary = {
        "protocol": DEFAULT_PROTOCOL.describe(),
        "contract_winners": contract_winners.to_dict("records"),
        "best_nonbaseline_candidate": best_nonbaseline.iloc[0].to_dict() if not best_nonbaseline.empty else None,
        "promoted_candidates": promoted_candidates[
            [
                "variant",
                "contract_name",
                "gate_name",
                "validation_relative_delta",
                "confirmation_relative_delta",
                "gate_share_overall",
            ]
        ].to_dict("records"),
        "gate_coverage": catalyst_daily[
            [
                "time",
                "highconv_ge1",
                "highconv_ge2",
                "multisource_ge1",
                "news_or_insider_ge1",
            ]
        ].copy().assign(time=lambda frame: frame["time"].astype(str)).to_dict("records")[:10],
        "gate_rates": {
            gate_name: float(pd.to_numeric(catalyst_daily[gate_name], errors="coerce").mean())
            for gate_name in gate_columns
        },
        "verdict_hint": {
            "promoted_count": int(len(promoted_candidates)),
            "any_promoted": bool(not promoted_candidates.empty),
        },
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_catalyst_concentrated_small_book",
        name="h248_entry_alpha_catalyst_concentrated_small_book",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "contract_winners": str(winners_path),
            "catalyst_daily": str(catalyst_daily_path),
            "selected_daily": str(selected_daily_path),
            "candidate_panel_cache": str(candidate_panel_cache),
            "base_labels_cache": str(base_labels_cache),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "news_rolling": str(args.news_rolling),
            "event_surface": str(args.event_surface),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "gate_top_m": int(args.gate_top_m),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "contracts": [contract.name for contract in DEFAULT_CONTRACT_SPECS],
            "gates": gate_columns,
        },
    )


if __name__ == "__main__":
    main()
