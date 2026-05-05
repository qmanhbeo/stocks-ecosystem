from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
    MAX_RESEARCH_YEAR,
    ExperimentSpec,
    build_experiment_context,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402


BRANCH_NAME = "h401_anti_signal_annihilation_veto"
MODE = "research_branch_anti_signal_annihilation_veto"

CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_DAILY_PATH = data_path("features/news/datasets/news_daily_features.parquet")

K = 5
MIN_VETO_DAYS_PER_YEAR = 20

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "High-ranked long candidates should be vetoed when side-channel "
        "evidence from C16, insider, news, tradability, and sector context "
        "disagrees with the candidate score."
    ),
    start_year=2019,
    end_year=2025,
    min_year_rows=20,
    min_phase_rows=20,
    target_columns={"cycle_relative_return_vs_vnindex": "future cycle relative return; target only"},
    score_columns={"selection_score": "decision-time candidate score"},
)


@dataclass(frozen=True)
class VetoSpec:
    name: str
    note: str
    primary: bool = True


VETO_SPECS = [
    VetoSpec("support_count_le1", "At most one support vote across C16/insider/news/tradability/sector"),
    VetoSpec("support_count_zero", "No explicit support vote across the side channels"),
    VetoSpec("weak_flow_weak_sector", "Weak C16, no insider, and weak sector support"),
    VetoSpec("pretty_price_weak_flow", "High S1/candidate row but weak C16, weak volume, and no insider"),
    VetoSpec("news_hype_weak_flow", "Positive/forward news but weak C16 and no insider support"),
    VetoSpec("tradability_fragile_weak_flow", "Weak tradability plus weak C16 and no insider support"),
]

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_article_count_1d",
    "phobert_sentiment_score_sum",
    "phobert_forward_looking_article_count_1d",
    "phobert_forward_looking_prob_mean",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H401: anti-signal long-only veto audit.")
    parser.add_argument("--candidate-panel", type=str, default=str(CANDIDATE_PANEL_PATH))
    parser.add_argument("--labels", type=str, default=str(LABELS_PATH))
    parser.add_argument("--c16", type=str, default=str(C16_PATH))
    parser.add_argument("--news", type=str, default=str(NEWS_DAILY_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--top-k", type=int, default=K)
    parser.add_argument("--random-trials", type=int, default=300)
    parser.add_argument("--seed", type=int, default=401)
    return parser.parse_args()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _safe_bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    return frame[column].eq(True)


def _load_news(path: Path, start_year: int, end_year: int) -> pd.DataFrame:
    news = pd.read_parquet(path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    news = news.loc[news["time"].dt.year.between(int(start_year), int(end_year))].copy()
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            news[column] = _safe_numeric(news, column, 0.0)
    news["news_active"] = news["phobert_article_count_1d"] > 0.0
    news["news_positive_or_forward"] = (
        (news["phobert_sentiment_score_sum"] > 0.0)
        | (
            (news["phobert_forward_looking_article_count_1d"] > 0.0)
            & (news["phobert_forward_looking_prob_mean"] >= 0.50)
        )
        | (
            (news["phobert_source_type_article_count_1d"] > 0.0)
            & (news["phobert_source_type_official_or_regulatory_prob_mean"] >= 0.50)
        )
    )
    news["news_negative"] = news["news_active"] & (news["phobert_sentiment_score_sum"] < 0.0)
    return news[["time", "ticker", "news_active", "news_positive_or_forward", "news_negative"]].drop_duplicates(
        ["time", "ticker"]
    )


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) > MAX_RESEARCH_YEAR:
        raise ValueError("H401 blocks 2026+; set --end-year <= 2025")
    candidate = pd.read_parquet(args.candidate_panel).copy()
    labels = pd.read_parquet(args.labels).copy()
    c16 = pd.read_parquet(
        args.c16,
        columns=["time", "ticker", "order_volume_ratio_rank", "order_pressure_available"],
    ).copy()
    news = _load_news(Path(args.news), int(args.start_year), int(args.end_year))

    for frame in [candidate, labels, c16]:
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()

    required_candidate = [
        "time",
        "ticker",
        "candidate_pool_rank",
        "selection_score",
        "can_buy_next_open",
        "s1_proba",
        "c5_ins_relative_size_5d",
        "c5_signal_present",
        "c8_vol_zscore_5d",
        "xs_tradability_rank",
        "xs_sector_mom_5d_rank",
        "xs_sector_breadth_5d",
    ]
    required_labels = ["cycle_return_net", "cycle_relative_return_vs_vnindex"]
    missing_candidate = [column for column in required_candidate if column not in candidate.columns]
    missing_labels = [column for column in required_labels if column not in labels.columns]
    if missing_candidate:
        raise ValueError(f"Candidate panel missing required columns: {missing_candidate}")
    if missing_labels:
        raise ValueError(f"Labels missing required columns: {missing_labels}")

    panel = candidate[required_candidate].merge(
        labels[["time", "ticker", *required_labels]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )
    panel = panel.merge(c16, on=["time", "ticker"], how="left", validate="many_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="many_to_one")
    panel["year"] = panel["time"].dt.year.astype(int)
    panel = panel.loc[
        panel["year"].between(int(args.start_year), int(args.end_year))
        & (_safe_numeric(panel, "candidate_pool_rank") <= float(args.top_k))
        & _safe_bool(panel, "can_buy_next_open")
    ].copy()
    for column in [
        "candidate_pool_rank",
        "selection_score",
        "s1_proba",
        "c5_ins_relative_size_5d",
        "c5_signal_present",
        "c8_vol_zscore_5d",
        "xs_tradability_rank",
        "xs_sector_mom_5d_rank",
        "xs_sector_breadth_5d",
        "order_volume_ratio_rank",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
    ]:
        panel[column] = _safe_numeric(panel, column)
    for column in ["news_active", "news_positive_or_forward", "news_negative", "order_pressure_available"]:
        panel[column] = _safe_bool(panel, column)
    panel = panel.dropna(
        subset=[
            "candidate_pool_rank",
            "selection_score",
            "cycle_return_net",
            "cycle_relative_return_vs_vnindex",
        ]
    )
    panel["c16_support"] = panel["order_pressure_available"] & (panel["order_volume_ratio_rank"] >= 0.60)
    panel["c16_weak"] = (~panel["order_pressure_available"]) | (panel["order_volume_ratio_rank"] <= 0.40)
    panel["insider_support"] = (panel["c5_signal_present"] > 0.0) & (panel["c5_ins_relative_size_5d"] > 0.0)
    panel["news_support"] = panel["news_positive_or_forward"] & ~panel["news_negative"]
    panel["tradability_support"] = panel["xs_tradability_rank"] >= 0.50
    panel["tradability_weak"] = panel["xs_tradability_rank"] <= 0.30
    panel["sector_support"] = (panel["xs_sector_mom_5d_rank"] >= 0.50) | (panel["xs_sector_breadth_5d"] >= 0.50)
    panel["sector_weak"] = (panel["xs_sector_mom_5d_rank"] <= 0.35) & (panel["xs_sector_breadth_5d"] <= 0.50)
    support_cols = ["c16_support", "insider_support", "news_support", "tradability_support", "sector_support"]
    panel["support_count"] = panel[support_cols].sum(axis=1)
    panel["support_count_le1"] = panel["support_count"] <= 1
    panel["support_count_zero"] = panel["support_count"] <= 0
    panel["weak_flow_weak_sector"] = panel["c16_weak"] & ~panel["insider_support"] & panel["sector_weak"]
    panel["pretty_price_weak_flow"] = (
        (panel["s1_proba"] >= 0.55)
        & panel["c16_weak"]
        & (panel["c8_vol_zscore_5d"] <= 0.50)
        & ~panel["insider_support"]
    )
    panel["news_hype_weak_flow"] = panel["news_positive_or_forward"] & panel["c16_weak"] & ~panel["insider_support"]
    panel["tradability_fragile_weak_flow"] = panel["tradability_weak"] & panel["c16_weak"] & ~panel["insider_support"]
    return panel.sort_values(["time", "candidate_pool_rank", "ticker"]).reset_index(drop=True)


def _daily_veto_return(group: pd.DataFrame, state_col: str, top_k: int) -> dict[str, object]:
    selected = group.sort_values(["candidate_pool_rank", "ticker"]).head(int(top_k)).copy()
    veto_mask = selected[state_col].eq(True).to_numpy(dtype=bool)
    rel = selected["cycle_relative_return_vs_vnindex"].to_numpy(dtype=float)
    abs_ret = selected["cycle_return_net"].to_numpy(dtype=float)
    no_veto_rel = float(np.nansum(rel) / float(top_k))
    no_veto_abs = float(np.nansum(abs_ret) / float(top_k))
    keep = ~veto_mask
    veto_rel = float(np.nansum(rel[keep]) / float(top_k))
    veto_abs = float(np.nansum(abs_ret[keep]) / float(top_k))
    return {
        "time": selected["time"].iloc[0],
        "year": int(selected["year"].iloc[0]),
        "state": state_col,
        "top_rows": int(len(selected)),
        "veto_count": int(veto_mask.sum()),
        "no_veto_relative_return": no_veto_rel,
        "veto_relative_return": veto_rel,
        "no_veto_abs_return": no_veto_abs,
        "veto_abs_return": veto_abs,
    }


def _random_veto_year_controls(
    daily: pd.DataFrame,
    panel: pd.DataFrame,
    state_col: str,
    *,
    top_k: int,
    random_trials: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(seed))
    rows = []
    grouped_returns = {
        time: group.sort_values(["candidate_pool_rank", "ticker"])["cycle_relative_return_vs_vnindex"].to_numpy(dtype=float)[: int(top_k)]
        for time, group in panel.groupby("time", sort=True)
    }
    for year, year_daily in daily.groupby("year", sort=True):
        trial_means = []
        for _ in range(int(random_trials)):
            values = []
            for row in year_daily.itertuples(index=False):
                returns = grouped_returns.get(row.time)
                if returns is None or len(returns) == 0:
                    values.append(0.0)
                    continue
                veto_count = min(int(row.veto_count), len(returns))
                if veto_count <= 0:
                    values.append(float(np.nansum(returns) / float(top_k)))
                    continue
                drop_idx = rng.choice(len(returns), size=veto_count, replace=False)
                keep_mask = np.ones(len(returns), dtype=bool)
                keep_mask[drop_idx] = False
                values.append(float(np.nansum(returns[keep_mask]) / float(top_k)))
            if values:
                trial_means.append(float(np.mean(values)))
        if trial_means:
            rows.append(
                {
                    "state": state_col,
                    "year": int(year),
                    "random_mean_relative_return": float(np.mean(trial_means)),
                    "random_p95_relative_return": float(np.quantile(trial_means, 0.95)),
                }
            )
    return pd.DataFrame(rows)


def evaluate_state(panel: pd.DataFrame, spec: VetoSpec, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_rows = [
        _daily_veto_return(group, spec.name, int(args.top_k))
        for _, group in panel.groupby("time", sort=True)
    ]
    daily = pd.DataFrame(daily_rows)
    random_yearly = _random_veto_year_controls(
        daily,
        panel,
        spec.name,
        top_k=int(args.top_k),
        random_trials=int(args.random_trials),
        seed=int(args.seed) + sum(ord(ch) for ch in spec.name),
    )
    yearly = (
        daily.groupby(["state", "year"], as_index=False)
        .agg(
            dates=("time", "nunique"),
            veto_dates=("veto_count", lambda series: int((series > 0).sum())),
            vetoed_slots=("veto_count", "sum"),
            no_veto_relative_return=("no_veto_relative_return", "mean"),
            veto_relative_return=("veto_relative_return", "mean"),
            no_veto_abs_return=("no_veto_abs_return", "mean"),
            veto_abs_return=("veto_abs_return", "mean"),
        )
        .merge(random_yearly, on=["state", "year"], how="left", validate="one_to_one")
    )
    yearly["delta_vs_no_veto"] = yearly["veto_relative_return"] - yearly["no_veto_relative_return"]
    yearly["delta_vs_random_mean"] = yearly["veto_relative_return"] - yearly["random_mean_relative_return"]
    yearly["delta_vs_random_p95"] = yearly["veto_relative_return"] - yearly["random_p95_relative_return"]
    yearly["primary"] = bool(spec.primary)
    yearly["note"] = spec.note
    return daily, yearly


def summarize_yearly(yearly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state, group in yearly.groupby("state", sort=True):
        valid = group.loc[group["veto_dates"] >= MIN_VETO_DAYS_PER_YEAR].copy()
        rows.append(
            {
                "state": state,
                "primary": bool(group["primary"].iloc[0]),
                "note": str(group["note"].iloc[0]),
                "years": int(len(valid)),
                "avg_delta_vs_no_veto": float(valid["delta_vs_no_veto"].mean()) if not valid.empty else None,
                "avg_delta_vs_random_mean": float(valid["delta_vs_random_mean"].mean()) if not valid.empty else None,
                "avg_delta_vs_random_p95": float(valid["delta_vs_random_p95"].mean()) if not valid.empty else None,
                "positive_no_veto_years": int((valid["delta_vs_no_veto"] > 0.0).sum()),
                "positive_random_mean_years": int((valid["delta_vs_random_mean"] > 0.0).sum()),
                "positive_random_p95_years": int((valid["delta_vs_random_p95"] > 0.0).sum()),
                "avg_veto_dates": float(valid["veto_dates"].mean()) if not valid.empty else None,
                "avg_vetoed_slots": float(valid["vetoed_slots"].mean()) if not valid.empty else None,
                "mean_veto_relative_return": float(valid["veto_relative_return"].mean()) if not valid.empty else None,
                "mean_no_veto_relative_return": float(valid["no_veto_relative_return"].mean()) if not valid.empty else None,
            }
        )
    return pd.DataFrame(rows).sort_values("avg_delta_vs_random_mean", ascending=False, na_position="last")


def choose_decision(summary: pd.DataFrame) -> tuple[str, dict[str, object]]:
    primary = summary.loc[summary["primary"].eq(True)].copy()
    primary = primary.sort_values(
        ["avg_delta_vs_no_veto", "avg_delta_vs_random_mean"],
        ascending=[False, False],
        na_position="last",
    )
    best = primary.iloc[0].to_dict() if not primary.empty else {}
    years = int(best.get("years", 0) or 0)
    pass_gate = (
        years >= 5
        and best.get("avg_delta_vs_no_veto") is not None
        and float(best["avg_delta_vs_no_veto"]) >= 0.0015
        and best.get("avg_delta_vs_random_mean") is not None
        and float(best["avg_delta_vs_random_mean"]) >= 0.0010
        and int(best.get("positive_no_veto_years", 0) or 0) >= 5
        and int(best.get("positive_random_mean_years", 0) or 0) >= 5
    )
    mixed_gate = (
        years >= 5
        and best.get("avg_delta_vs_no_veto") is not None
        and float(best["avg_delta_vs_no_veto"]) > 0.0
        and int(best.get("positive_no_veto_years", 0) or 0) >= 4
    )
    decision = "PASSED" if pass_gate else "MIXED" if mixed_gate else "FAILED"
    return decision, {
        "best_state": best.get("state"),
        "best_avg_delta_vs_no_veto": best.get("avg_delta_vs_no_veto"),
        "best_avg_delta_vs_random_mean": best.get("avg_delta_vs_random_mean"),
        "best_avg_delta_vs_random_p95": best.get("avg_delta_vs_random_p95"),
        "best_positive_no_veto_years": best.get("positive_no_veto_years"),
        "best_positive_random_mean_years": best.get("positive_random_mean_years"),
        "best_years": years,
        "pass_gate": pass_gate,
        "mixed_gate": mixed_gate,
    }


def run_branch(args: argparse.Namespace) -> str:
    spec = SPEC
    context = build_experiment_context(spec, artifact_subdir=BRANCH_NAME)
    panel = load_panel(args)
    daily_frames = []
    yearly_frames = []
    for veto in VETO_SPECS:
        daily, yearly = evaluate_state(panel, veto, args)
        daily_frames.append(daily)
        yearly_frames.append(yearly)
    daily_all = pd.concat(daily_frames, ignore_index=True)
    yearly_all = pd.concat(yearly_frames, ignore_index=True)
    summary = summarize_yearly(yearly_all)
    decision, detail = choose_decision(summary)

    daily_path = write_dataframe_artifact(daily_all, context, f"{BRANCH_NAME}_daily")
    yearly_path = write_dataframe_artifact(yearly_all, context, f"{BRANCH_NAME}_yearly")
    summary_path_artifact = write_dataframe_artifact(summary, context, f"{BRANCH_NAME}_summary")
    run_summary_path = context.write_summary(
        summary={
            "decision": decision,
            "decision_detail": detail,
            "panel_rows": int(len(panel)),
            "test_years": sorted(int(year) for year in panel["year"].unique()),
            "state_summary": summary.to_dict(orient="records"),
            "decision_rule": (
                "PASSED requires the best fixed primary veto to improve "
                "top-5 cycle relative return by >= +0.0015 versus no-veto and "
                ">= +0.0010 versus random same-breadth vetoes, with >= 5 "
                "positive years on both comparisons. MIXED requires positive "
                "mean lift versus no-veto with >= 4 positive no-veto years."
            ),
        },
        artifacts={
            "daily": daily_path,
            "yearly": yearly_path,
            "state_summary": summary_path_artifact,
        },
        metadata={
            "no_2026_rows": True,
            "top_k": int(args.top_k),
            "random_trials": int(args.random_trials),
            "veto_specs": [veto.__dict__ for veto in VETO_SPECS],
        },
    )

    pd.set_option("display.max_rows", 80)
    pd.set_option("display.width", 240)
    print(summary.to_string(index=False))
    print(f"\ndecision: {decision}")
    print(f"summary: {run_summary_path}")
    return run_summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
