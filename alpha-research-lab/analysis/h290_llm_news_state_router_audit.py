"""
H290 - LLM news state router audit.

Question:
- Does the LLM news surface become useful only in certain news states, rather
  than as one pooled sentiment factor?

Design:
- use the nonzero news window in the current cache, 2015-2017
- build a 5d relative excess-return target vs VNINDEX
- compare a small sentiment feature basket against the target overall and inside
  four state views:
  - expectation alignment: beat / miss / flat
  - information novelty: new / follow / flat
  - source authority: official / rumor / flat
  - alignment x novelty combo
- summarize each bucket with daily IC, daily hit rate, and positive-year rate
- if the best state bucket meaningfully improves over the pooled baseline and
  flips the sign relative to the opposite state, the next step is a routed news
  factor; otherwise the branch is parked

Usage:
    conda run -n stocks python analysis/h290_llm_news_state_router_audit.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long

LLM_PATH = data_path("features/xs_llm_news_ticker_day.parquet")
LLM_FEATURES = [
    "llm_sentiment_conf_weighted",
    "llm_sentiment_5d",
    "llm_sentiment_30d",
]


def _future_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, *, periods: int) -> pd.DataFrame:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 3 or gg[feature_col].nunique() < 2 or gg[target_col].nunique() < 2:
            continue
        rho, p = spearmanr(gg[feature_col], gg[target_col])
        if np.isfinite(rho):
            rows.append({"time": pd.to_datetime(time), "ic": float(rho), "p_value": float(p), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _summary_from_series(series: pd.DataFrame) -> dict[str, object]:
    if series.empty:
        return {
            "mean_ic": float("nan"),
            "daily_hit_rate": float("nan"),
            "positive_years": 0,
            "years_present": 0,
            "daily_rows": 0,
        }
    yearly = series.assign(year=series["time"].dt.year).groupby("year")["ic"].mean()
    return {
        "mean_ic": float(series["ic"].mean()),
        "daily_hit_rate": float((series["ic"] > 0.0).mean()),
        "positive_years": int((yearly > 0.0).sum()),
        "years_present": int(yearly.shape[0]),
        "daily_rows": int(len(series)),
    }


def _bucket_frame(frame: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    work = frame[[bucket_col]].copy()
    return work


def _bucket_labeler(frame: pd.DataFrame, kind: str) -> pd.Series:
    if kind == "alignment":
        return pd.Series(
            np.where(
                frame["llm_expectation_beats_5d"] > frame["llm_expectation_misses_5d"],
                "beat",
                np.where(frame["llm_expectation_beats_5d"] < frame["llm_expectation_misses_5d"], "miss", "flat"),
            ),
            index=frame.index,
        )
    if kind == "novelty":
        return pd.Series(
            np.where(
                frame["llm_new_info_5d"] > frame["llm_followup_info_5d"],
                "new",
                np.where(frame["llm_new_info_5d"] < frame["llm_followup_info_5d"], "follow", "flat"),
            ),
            index=frame.index,
        )
    if kind == "authority":
        return pd.Series(
            np.where(
                frame["llm_official_source_5d"] > frame["llm_rumor_source_5d"],
                "official",
                np.where(frame["llm_official_source_5d"] < frame["llm_rumor_source_5d"], "rumor", "flat"),
            ),
            index=frame.index,
        )
    if kind == "align_novel":
        align = _bucket_labeler(frame, "alignment")
        novel = _bucket_labeler(frame, "novelty")
        return align.astype(str) + "__" + novel.astype(str)
    raise ValueError(f"Unknown bucket kind: {kind}")


@dataclass
class BucketResult:
    feature_name: str
    state_kind: str
    bucket_name: str
    stats: dict[str, object]
    daily_ic_rows: pd.DataFrame


def _bucket_stats(frame: pd.DataFrame, feature_col: str, target_col: str, state_kind: str, bucket_name: str) -> BucketResult:
    bucket_mask = frame["bucket"] == bucket_name
    bucket_frame = frame.loc[bucket_mask, ["time", feature_col, target_col]].copy()
    ic_rows = _daily_ic_series(bucket_frame, feature_col, target_col)
    stats = _summary_from_series(ic_rows)
    stats["row_count"] = int(len(bucket_frame))
    stats["nonzero_feature_rows"] = int((bucket_frame[feature_col].fillna(0.0) != 0.0).sum())
    stats["feature_mean"] = float(pd.to_numeric(bucket_frame[feature_col], errors="coerce").mean()) if len(bucket_frame) else float("nan")
    stats["target_mean"] = float(pd.to_numeric(bucket_frame[target_col], errors="coerce").mean()) if len(bucket_frame) else float("nan")
    return BucketResult(
        feature_name=feature_col,
        state_kind=state_kind,
        bucket_name=bucket_name,
        stats=stats,
        daily_ic_rows=ic_rows,
    )


def main() -> None:
    print("Building LLM news state router audit panel...")

    llm = pd.read_parquet(LLM_PATH, columns=["time", "ticker", *LLM_FEATURES,
                                             "llm_expectation_beats_5d", "llm_expectation_misses_5d",
                                             "llm_new_info_5d", "llm_followup_info_5d",
                                             "llm_official_source_5d", "llm_rumor_source_5d"]).copy()
    llm["time"] = pd.to_datetime(llm["time"], errors="coerce")
    llm = llm[(llm["time"].dt.year >= 2015) & (llm["time"].dt.year <= 2017)].copy()

    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[close.index.year <= 2017].copy()
    benchmark_close = load_vni_close().reindex(close.index)
    future5 = _future_excess_return(close, benchmark_close, periods=5)
    future5_df = to_long(future5, "future_rel_return_5d")
    future5_df["time"] = pd.to_datetime(future5_df["time"], errors="coerce")
    future5_df = future5_df[future5_df["time"].dt.year <= 2017].copy()

    panel = llm.merge(future5_df, on=["time", "ticker"], how="inner")
    panel = panel.dropna(subset=["future_rel_return_5d"])
    if panel.empty:
        raise ValueError("No matched LLM news rows for the 5d target window")

    feature_summaries = []
    bucket_rows = []
    all_bucket_results: list[BucketResult] = []
    for feature in LLM_FEATURES:
        overall_ic = _daily_ic_series(panel[["time", feature, "future_rel_return_5d"]].copy(), feature, "future_rel_return_5d")
        overall_stats = _summary_from_series(overall_ic)
        feature_summaries.append(
            {
                "feature_name": feature,
                **overall_stats,
            }
        )

        for state_kind in ["alignment", "novelty", "authority", "align_novel"]:
            frame = panel.copy()
            frame["bucket"] = _bucket_labeler(frame, state_kind)
            bucket_names = sorted(frame["bucket"].dropna().unique().tolist())
            for bucket_name in bucket_names:
                result = _bucket_stats(frame, feature, "future_rel_return_5d", state_kind, bucket_name)
                all_bucket_results.append(result)
                bucket_rows.append(
                    {
                        "feature_name": feature,
                        "state_kind": state_kind,
                        "bucket_name": bucket_name,
                        **result.stats,
                    }
                )

    feature_df = pd.DataFrame(feature_summaries).sort_values(
        by=["mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[False, False, False],
        ignore_index=True,
    )
    bucket_df = pd.DataFrame(bucket_rows).sort_values(
        by=["mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[False, False, False],
        ignore_index=True,
    )

    best_row = bucket_df.iloc[0].to_dict()
    best_feature = str(best_row["feature_name"])
    best_state_kind = str(best_row["state_kind"])
    best_bucket = str(best_row["bucket_name"])

    opposite_map = {
        "beat": "miss",
        "miss": "beat",
        "new": "follow",
        "follow": "new",
        "official": "rumor",
        "rumor": "official",
    }
    opposite_bucket = opposite_map.get(best_bucket.split("__")[0], None)
    if "__" in best_bucket:
        left, right = best_bucket.split("__", 1)
        opposite_bucket = f"{opposite_map.get(left, left)}__{opposite_map.get(right, right)}"

    comparable = bucket_df[
        (bucket_df["feature_name"] == best_feature)
        & (bucket_df["state_kind"] == best_state_kind)
    ].copy()
    opposite_stats = {}
    if opposite_bucket is not None and not comparable.empty and (comparable["bucket_name"] == opposite_bucket).any():
        opposite_row = comparable.loc[comparable["bucket_name"] == opposite_bucket].iloc[0].to_dict()
        opposite_stats = {
            "opposite_bucket": opposite_bucket,
            "opposite_mean_ic": float(opposite_row["mean_ic"]),
            "opposite_daily_hit_rate": float(opposite_row["daily_hit_rate"]),
            "opposite_positive_years": int(opposite_row["positive_years"]),
        }

    best_mean_ic = float(best_row["mean_ic"])
    best_hit_rate = float(best_row["daily_hit_rate"])
    best_positive_years = int(best_row["positive_years"])
    best_years_present = int(best_row["years_present"])
    best_daily_rows = int(best_row["daily_rows"])
    best_target_mean = float(best_row["target_mean"])
    best_nonzero_rows = int(best_row["nonzero_feature_rows"])
    overall_feature = feature_df.iloc[0].to_dict()
    sign_flip = bool(best_mean_ic > 0.0 and best_row.get("bucket_name") != "flat" and (best_state_kind != "authority" or best_bucket != "flat"))

    pass_condition = bool(best_mean_ic >= 0.05 and best_hit_rate >= 0.50 and best_positive_years == best_years_present and sign_flip)
    mixed_condition = bool(best_mean_ic >= 0.01 or sign_flip)
    verdict = "PASS" if pass_condition else "MIXED" if mixed_condition else "FAIL"

    print("\nH290 LLM NEWS STATE ROUTER RESULTS")
    print("=" * 140)
    print("Overall feature basket:")
    print(feature_df[["feature_name", "mean_ic", "daily_hit_rate", "positive_years", "years_present", "daily_rows"]].to_string(index=False))
    print("\nBest state buckets:")
    print(bucket_df.head(10)[["feature_name", "state_kind", "bucket_name", "mean_ic", "daily_hit_rate", "positive_years", "years_present", "daily_rows"]].to_string(index=False))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h290_llm_news_state_router_audit_details.json"
    summary = {
        "verdict": verdict,
        "best_feature": best_feature,
        "best_state_kind": best_state_kind,
        "best_bucket": best_bucket,
        "best_mean_ic": best_mean_ic,
        "best_daily_hit_rate": best_hit_rate,
        "best_positive_years": best_positive_years,
        "best_years_present": best_years_present,
        "best_daily_rows": best_daily_rows,
        "best_nonzero_rows": best_nonzero_rows,
        "best_target_mean": best_target_mean,
        "overall_feature_basket": feature_df.to_dict("records"),
        "bucket_table": bucket_df.to_dict("records"),
        "opposite_stats": opposite_stats,
        "sign_flip": sign_flip,
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "window_years": sorted(int(y) for y in panel["time"].dt.year.unique().tolist()),
        "nonzero_window_rows": int((panel[LLM_FEATURES].fillna(0.0) != 0.0).any(axis=1).sum()),
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h290_llm_news_state_router_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H290"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
