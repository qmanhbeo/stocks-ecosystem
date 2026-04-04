"""
H279: intraday disagreement + breadth gap router audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SHARED_MARKET_RULES_ROOT = REPO_ROOT.parent / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.intraday_exit_research import add_intraday_shape_atoms
from src.run_summary import write_run_summary
from src.standalone_signal_utils import (
    load_ohlcv_wide,
    load_vni_close,
    spearman_stat,
    to_long,
)

H258_SUMMARY_PATH = REPO_ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
SECTOR_ROTATION_PATH = Path("data/features/xs_sector_rotation_daily.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H279: intraday disagreement + breadth gap router audit")
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--future-horizon", type=int, default=5)
    parser.add_argument("--shape-quantile", type=float, default=0.90)
    parser.add_argument("--breadth-gap-min", type=float, default=0.0)
    return parser.parse_args()


def _future_hold_advantage(
    close: pd.DataFrame, benchmark_close: pd.Series, periods: int
) -> pd.DataFrame:
    future_stock = close.shift(-periods).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-periods).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _summary_stats(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {"count": 0.0, "mean_adv": 0.0, "positive_rate": 0.0}
    adv = df["future_hold_advantage"].dropna()
    return {
        "count": float(len(adv)),
        "mean_adv": float(adv.mean()),
        "positive_rate": float((adv > 0.0).mean()),
    }


def main() -> None:
    args = parse_args()

    summary_payload = load_summary_payload(H258_SUMMARY_PATH)
    panel_path = resolve_summary_artifact(H258_SUMMARY_PATH, "reduced_shape_panel")
    panel = pd.read_parquet(panel_path)
    panel["time"] = pd.to_datetime(panel["session_date"], errors="coerce").dt.normalize()
    panel = add_intraday_shape_atoms(panel)
    panel = panel.loc[
        panel["time"].dt.year.between(int(args.start_year), int(args.end_year))
        & panel["intraday_observed"].fillna(0).astype(bool)
    ].copy()
    score_components = [
        panel["first_hour_fade_proxy"].fillna(0.0),
        panel["weak_open_strong_close_proxy"].fillna(0.0),
        panel["failed_breakout_proxy"].fillna(0.0),
    ]
    panel["shape_score"] = sum(score_components) / float(len(score_components))

    sector = pd.read_parquet(SECTOR_ROTATION_PATH)
    sector["time"] = pd.to_datetime(sector["time"], errors="coerce").dt.normalize()
    sector = sector.sort_values(["ticker", "time"])
    sector["breadth_prev"] = sector.groupby("ticker")["xs_sector_breadth_5d"].shift(5)
    sector["breadth_gap"] = sector["breadth_prev"] - sector["xs_sector_breadth_5d"]
    sector = sector.dropna(subset=["breadth_gap"])

    merged = panel.merge(
        sector[["time", "ticker", "xs_sector_breadth_5d", "breadth_gap"]],
        on=["time", "ticker"],
        how="inner",
    )
    if merged.empty:
        raise ValueError("No matched intraday + sector rows in the requested window")

    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    idx_year = close.index.year
    close = close.loc[
        (idx_year >= int(args.start_year)) & (idx_year <= int(args.end_year))
    ]
    future_adv = _future_hold_advantage(close, load_vni_close().reindex(close.index), int(args.future_horizon))
    future_long = to_long(future_adv, f"hold_adv_{int(args.future_horizon)}d")
    future_long["time"] = pd.to_datetime(future_long["time"], errors="coerce").dt.normalize()

    merged = merged.merge(
        future_long.rename(columns={f"hold_adv_{int(args.future_horizon)}d": "future_hold_advantage"}),
        on=["time", "ticker"],
        how="inner",
    )
    merged = merged.dropna(subset=["future_hold_advantage"])

    shape_thresh = merged["shape_score"].quantile(float(args.shape_quantile))
    merged["shape_gate"] = merged["shape_score"] >= float(shape_thresh)
    merged["breadth_gate"] = merged["breadth_gap"] >= float(args.breadth_gap_min)
    merged["router_gate"] = merged["shape_gate"] & merged["breadth_gate"]

    router_stats = _summary_stats(merged.loc[merged["router_gate"]])
    baseline_stats = _summary_stats(merged)
    chis = merged.loc[merged["shape_gate"]]
    shape_stats = _summary_stats(chis)

    results = pd.DataFrame(
        [
            {"group": "router_gate", **router_stats},
            {"group": "shape_only", **shape_stats},
            {"group": "all_rows", **baseline_stats},
        ]
    )

    best_feature = merged.sort_values("shape_score", ascending=False).iloc[0].to_dict()
    stats = {
        "shape_threshold": float(shape_thresh),
        "breadth_gap_min": float(args.breadth_gap_min),
        "router_count": router_stats["count"],
        "router_mean_adv": router_stats["mean_adv"],
        "router_positive_rate": router_stats["positive_rate"],
        "shape_only_mean_adv": shape_stats["mean_adv"],
        "shape_only_positive_rate": shape_stats["positive_rate"],
        "baseline_mean_adv": baseline_stats["mean_adv"],
        "router_vs_shape_delta": router_stats["mean_adv"] - shape_stats["mean_adv"],
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{ts}_h279_shape_breadth_router_results.parquet"
    panel_path_out = out_dir / f"{ts}_h279_shape_breadth_router_panel.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h279_shape_breadth_router_summary.json"
    results.to_parquet(results_path, index=False)
    merged[["time", "ticker", "shape_score", "breadth_gap", "future_hold_advantage", "router_gate"]].to_parquet(
        panel_path_out, index=False
    )

    summary = {
        "verdict": "MIXED" if router_stats["mean_adv"] > baseline_stats["mean_adv"] else "FAIL",
        "stats": stats,
        "group_columns": results_path.name,
        "best_feature": {
            "shape_score": best_feature.get("shape_score"),
            "breadth_gap": best_feature.get("breadth_gap"),
            "future_hold_advantage": best_feature.get("future_hold_advantage"),
        },
        "start_year": int(args.start_year),
        "end_year": int(args.end_year),
        "future_horizon": int(args.future_horizon),
        "shape_quantile": float(args.shape_quantile),
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="portfolio_router_shape_breadth",
        name="h279_shape_breadth_disagreement_router",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "panel": str(panel_path_out),
            "details": str(details_path),
        },
        metadata={
            "session": 108,
            "shape_quantile": float(args.shape_quantile),
            "future_horizon": int(args.future_horizon),
        },
    )

    print("H279 router stats")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
