"""
H251: Event-surface trust-modulator decomposition.

Purpose:
- test whether event surface v1 is useful as a selector trust variable even
  though it failed as an exit-side predictive branch
- keep the pass pre-integration: conditional IC and top-k edge decomposition
  only, with no deterministic gate added yet
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import blend_state_scoped_scores, resolve_summary_artifact, summary_is_skipped
from src.contradiction_state_router import add_h250_router_signals
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.event_surface_trust_research import build_topk_event_regime_frame
from src.repo_paths import artifact_path
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, assign_research_phase
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import (
    build_candidate_signal_frame,
    load_research_bundle,
)


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EVENT_SURFACE_PATH = data_path("features/event_surface_daily.parquet")
H201_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json")
H250_SUMMARY_PATH = artifact_path("run_summaries/latest_portfolio_contradiction_state_router.json")
OUT_DIR = artifact_path("portfolio_baselines")

REGIME_SPECS = (
    ("top5_any_event_ge1", "topk_any_event_count", 1),
    ("top5_recent_filing_ge1", "topk_recent_filing_count", 1),
    ("top5_report_window_ge2", "topk_report_window_count", 2),
    ("top5_corp_action_ge1", "topk_corp_action_count", 1),
)
MIN_VALIDATION_DATES = 20
MIN_CONFIRMATION_DATES = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H251: event-surface trust-modulator decomposition")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--h201-summary", type=str, default=str(H201_SUMMARY_PATH))
    parser.add_argument("--h250-summary", type=str, default=str(H250_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


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


def _load_h250_winner(summary_path: Path) -> str | None:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    winner = payload.get("summary", {}).get("winner", {})
    signal_name = winner.get("signal_name") if isinstance(winner, dict) else None
    return None if not signal_name else str(signal_name)


def _parse_state_blend_name(strategy_name: str) -> tuple[str, float]:
    parts = str(strategy_name).split("__")
    if len(parts) != 3 or parts[0] != "state_blend":
        raise ValueError(f"Expected state blend strategy name, got {strategy_name!r}")
    return parts[1], float(parts[2]) / 100.0


def _phase_avg(values_frame: pd.DataFrame, value_column: str) -> dict[str, dict[str, float | int | None]]:
    assigned = assign_research_phase(values_frame, date_column="time", protocol=DEFAULT_PROTOCOL)
    out: dict[str, dict[str, float | int | None]] = {}
    for phase in ("validation", "confirmation"):
        phase_frame = assigned.loc[assigned["research_phase"] == phase].copy()
        series = pd.to_numeric(phase_frame[value_column], errors="coerce")
        out[phase] = {
            "dates": int(len(phase_frame)),
            "avg": None if phase_frame.empty else float(series.mean()),
        }
    return out


def _yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for year, group in df.groupby(df["time"].dt.year):
        clean = group[[score_col, target_col]].replace([float("inf"), float("-inf")], pd.NA).dropna()
        if len(clean) < 500:
            continue
        rho = clean[score_col].corr(clean[target_col], method="spearman")
        rows.append({"year": int(year), "ic": float(rho), "n": int(len(clean))})
    return rows


def _phase_ic(frame: pd.DataFrame, *, score_column: str) -> dict[str, dict[str, float | int | None]]:
    assigned = assign_research_phase(frame, date_column="time", protocol=DEFAULT_PROTOCOL)
    out: dict[str, dict[str, float | int | None]] = {}
    for phase in ("validation", "confirmation"):
        phase_frame = assigned.loc[assigned["research_phase"] == phase].copy()
        yearly = _yearly_ic(phase_frame, score_col=score_column)
        ics = [row["ic"] for row in yearly]
        out[phase] = {
            "dates": int(phase_frame["time"].nunique()),
            "avg_ic": None if not ics else float(sum(ics) / len(ics)),
        }
    return out


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 244)
    print("H251: EVENT-SURFACE TRUST-MODULATOR DECOMPOSITION")
    print("=" * 244)
    print(
        f"{'strategy':<42} {'regime':<28} {'share':>7} {'v_ic_d':>8} {'25_ic_d':>9} "
        f"{'v_edge_d':>10} {'25_edge_d':>11} {'promote':>8}"
    )
    print("-" * 244)
    for row in results.itertuples(index=False):
        print(
            f"{row.strategy_name:<42} {row.regime_name:<28} "
            f"{(row.gate_share_overall or 0.0)*100:>6.2f}% "
            f"{(row.validation_ic_delta if row.validation_ic_delta is not None else float('nan')):>+7.4f} "
            f"{(row.confirmation_ic_delta if row.confirmation_ic_delta is not None else float('nan')):>+8.4f} "
            f"{(row.validation_edge_delta or 0.0):>+9.4f} "
            f"{(row.confirmation_edge_delta or 0.0):>+10.4f} "
            f"{str(bool(row.promoted_to_trust_audit)):>8}"
        )


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    h201_results, h201_winner_name = _load_h201_winner(Path(args.h201_summary))
    if h201_winner_name is None:
        raise ValueError("H251 requires an H201 winner")

    h250_signal_name = _load_h250_winner(Path(args.h250_summary))
    if h250_signal_name is None:
        raise ValueError("H251 requires an H250 promoted router winner")

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    candidate_frame = build_candidate_signal_frame(bundle, start_year=int(args.start_year), end_year=int(args.end_year))
    candidate_frame = candidate_frame.merge(
        bundle.matrix[["time", "ticker", "c9_reversal_1d", "c14_clv_volconf_resid_rank"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    candidate_frame = add_h250_router_signals(candidate_frame)
    candidate_frame["time"] = pd.to_datetime(candidate_frame["time"])

    event_surface = pd.read_parquet(Path(args.event_surface))
    event_surface["time"] = pd.to_datetime(event_surface["time"])
    event_surface = event_surface[
        (event_surface["time"].dt.year >= int(args.start_year))
        & (event_surface["time"].dt.year <= int(args.end_year))
    ].copy()

    full_library_columns = resolve_strategy_columns(bundle.matrix.columns.tolist(), "full_library")
    h201_atom, h201_weight = _parse_state_blend_name(h201_winner_name)
    h250_strategy_name = f"full_library_plus__{h250_signal_name}"

    merged = bundle.matrix.merge(
        candidate_frame[["time", "ticker", h201_atom, h250_signal_name]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    base_scored = compute_strategy_scores(
        merged,
        {
            "full_library_baseline": list(full_library_columns),
            h250_strategy_name: list(full_library_columns) + [h250_signal_name],
            h201_atom: [h201_atom],
        },
    )
    liq_open_basic = (
        (pd.to_numeric(candidate_frame["tv_to_adv20"], errors="coerce") >= 1.10)
        & (pd.to_numeric(candidate_frame["clv"], errors="coerce") >= 0.45)
        & candidate_frame["can_buy_next_open"].fillna(False).astype(bool)
    )

    scored = base_scored[
        [
            "time",
            "ticker",
            "actual",
            "score__full_library_baseline",
            f"score__{h250_strategy_name}",
        ]
    ].copy()
    scored[f"score__{h201_winner_name}"] = blend_state_scoped_scores(
        pd.to_numeric(base_scored["score__full_library_baseline"], errors="coerce"),
        pd.to_numeric(base_scored[f"score__{h201_atom}"], errors="coerce"),
        liq_open_basic,
        atom_weight=float(h201_weight),
    )

    strategy_names = ["full_library_baseline", h201_winner_name, h250_strategy_name]
    topk_frame = build_topk_event_regime_frame(
        scored,
        strategy_names=strategy_names,
        event_surface=event_surface,
        top_k=int(args.top_k),
    )

    rows: list[dict[str, object]] = []
    for strategy_name in strategy_names:
        score_column = f"score__{strategy_name}"
        strategy_frame = scored[["time", "ticker", "actual", score_column]].copy()
        state_mask = liq_open_basic.loc[strategy_frame.index]
        topk_strategy = topk_frame.loc[topk_frame["strategy_name"] == strategy_name].copy()
        topk_strategy["time"] = pd.to_datetime(topk_strategy["time"])

        for regime_name, count_column, threshold in REGIME_SPECS:
            regime_dates = topk_strategy.loc[
                pd.to_numeric(topk_strategy[count_column], errors="coerce") >= float(threshold),
                "time",
            ].drop_duplicates()
            on_mask = strategy_frame["time"].isin(regime_dates)
            off_mask = ~on_mask

            on_ic = _phase_ic(strategy_frame.loc[on_mask & state_mask].copy(), score_column=score_column)
            off_ic = _phase_ic(strategy_frame.loc[off_mask & state_mask].copy(), score_column=score_column)
            on_edge = _phase_avg(topk_strategy.loc[topk_strategy["time"].isin(regime_dates)].copy(), "topk_edge_actual")
            off_edge = _phase_avg(topk_strategy.loc[~topk_strategy["time"].isin(regime_dates)].copy(), "topk_edge_actual")

            validation_ic_delta = None
            if on_ic["validation"]["avg_ic"] is not None and off_ic["validation"]["avg_ic"] is not None:
                validation_ic_delta = float(on_ic["validation"]["avg_ic"] - off_ic["validation"]["avg_ic"])
            confirmation_ic_delta = None
            if on_ic["confirmation"]["avg_ic"] is not None and off_ic["confirmation"]["avg_ic"] is not None:
                confirmation_ic_delta = float(on_ic["confirmation"]["avg_ic"] - off_ic["confirmation"]["avg_ic"])
            validation_edge_delta = None
            if on_edge["validation"]["avg"] is not None and off_edge["validation"]["avg"] is not None:
                validation_edge_delta = float(on_edge["validation"]["avg"] - off_edge["validation"]["avg"])
            confirmation_edge_delta = None
            if on_edge["confirmation"]["avg"] is not None and off_edge["confirmation"]["avg"] is not None:
                confirmation_edge_delta = float(on_edge["confirmation"]["avg"] - off_edge["confirmation"]["avg"])

            support_ok = (
                on_edge["validation"]["dates"] >= MIN_VALIDATION_DATES
                and off_edge["validation"]["dates"] >= MIN_VALIDATION_DATES
                and on_edge["confirmation"]["dates"] >= MIN_CONFIRMATION_DATES
                and off_edge["confirmation"]["dates"] >= MIN_CONFIRMATION_DATES
            )
            ic_improves = (
                validation_ic_delta is not None
                and confirmation_ic_delta is not None
                and validation_ic_delta > 0.0
                and confirmation_ic_delta > 0.0
            )
            edge_improves = (
                validation_edge_delta is not None
                and confirmation_edge_delta is not None
                and validation_edge_delta > 0.0
                and confirmation_edge_delta > 0.0
            )
            mixed_signal = support_ok and ((ic_improves and not edge_improves) or (edge_improves and not ic_improves))

            rows.append(
                {
                    "strategy_name": strategy_name,
                    "regime_name": regime_name,
                    "gate_share_overall": float(on_mask.mean()),
                    "gate_share_validation": float(on_edge["validation"]["dates"] / max(on_edge["validation"]["dates"] + off_edge["validation"]["dates"], 1)),
                    "gate_share_confirmation": float(on_edge["confirmation"]["dates"] / max(on_edge["confirmation"]["dates"] + off_edge["confirmation"]["dates"], 1)),
                    "validation_on_dates": on_edge["validation"]["dates"],
                    "validation_off_dates": off_edge["validation"]["dates"],
                    "confirmation_on_dates": on_edge["confirmation"]["dates"],
                    "confirmation_off_dates": off_edge["confirmation"]["dates"],
                    "validation_ic_on": on_ic["validation"]["avg_ic"],
                    "validation_ic_off": off_ic["validation"]["avg_ic"],
                    "validation_ic_delta": validation_ic_delta,
                    "confirmation_ic_on": on_ic["confirmation"]["avg_ic"],
                    "confirmation_ic_off": off_ic["confirmation"]["avg_ic"],
                    "confirmation_ic_delta": confirmation_ic_delta,
                    "validation_edge_on": on_edge["validation"]["avg"],
                    "validation_edge_off": off_edge["validation"]["avg"],
                    "validation_edge_delta": validation_edge_delta,
                    "confirmation_edge_on": on_edge["confirmation"]["avg"],
                    "confirmation_edge_off": off_edge["confirmation"]["avg"],
                    "confirmation_edge_delta": confirmation_edge_delta,
                    "support_ok": support_ok,
                    "mixed_signal": mixed_signal,
                    "promoted_to_trust_audit": support_ok and ic_improves and edge_improves,
                }
            )

    results = pd.DataFrame(rows).sort_values(
        by=[
            "promoted_to_trust_audit",
            "mixed_signal",
            "confirmation_edge_delta",
            "validation_edge_delta",
            "confirmation_ic_delta",
            "validation_ic_delta",
            "strategy_name",
            "regime_name",
        ],
        ascending=[False, False, False, False, False, False, True, True],
        ignore_index=True,
    )
    _print_table(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h251_event_surface_trust_modulator_results.parquet"
    topk_frame_path = OUT_DIR / f"{ts}_h251_event_surface_trust_modulator_topk_frame.parquet"
    results.to_parquet(results_path, index=False)
    topk_frame.to_parquet(topk_frame_path, index=False)

    promoted = results.loc[results["promoted_to_trust_audit"]].copy()
    mixed = results.loc[results["mixed_signal"]].copy()
    verdict = "PASS" if not promoted.empty else "MIXED" if not mixed.empty else "FAIL"
    summary = {
        "protocol": protocol.describe(),
        "h201_winner": h201_results.loc[h201_results["strategy_name"] == h201_winner_name].iloc[0].to_dict(),
        "h250_signal_name": h250_signal_name,
        "verdict": verdict,
        "best_candidate": results.iloc[0].to_dict() if not results.empty else {},
        "promoted_candidates": promoted[
            [
                "strategy_name",
                "regime_name",
                "validation_ic_delta",
                "confirmation_ic_delta",
                "validation_edge_delta",
                "confirmation_edge_delta",
            ]
        ].to_dict("records"),
        "mixed_candidates": mixed[
            [
                "strategy_name",
                "regime_name",
                "validation_ic_delta",
                "confirmation_ic_delta",
                "validation_edge_delta",
                "confirmation_edge_delta",
            ]
        ].to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_event_surface_trust_modulator",
        name="h251_event_surface_trust_modulator",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "topk_frame": str(topk_frame_path),
        },
        metadata={
            "protocol": protocol.describe(),
            "h201_summary": str(args.h201_summary),
            "h250_summary": str(args.h250_summary),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
        },
    )


if __name__ == "__main__":
    main()
