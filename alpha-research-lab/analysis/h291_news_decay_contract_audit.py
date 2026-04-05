"""
H291 - news decay contract audit.

Question:
- Does the raw CafeF LLM news stream obey a learnable novelty half-life, where
  follow_up, new, and recycled stories matter on different forward horizons?

Design:
- use the nonzero raw cache window already observed in H290, 2015-2017
- build a ticker-day panel from raw cache novelty labels
- compare novelty counts and simple novelty spreads against 1d / 5d / 30d
  forward excess return versus VNINDEX
- report the best decay horizon per class and the best class per horizon
- keep the branch only if the novelty ordering is stable enough to look like a
  contract rather than a noise wiggle

Usage:
    conda run -n stocks python analysis/h291_news_decay_contract_audit.py
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

RAW_CACHE_DIR = data_path("llm_cache")
NOVELTY_ALLOWED = {"new", "follow_up", "recycled"}
TARGET_HORIZONS = [1, 5, 30]


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


def _load_novelty_panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    files = sorted(p for p in RAW_CACHE_DIR.glob("*.jsonl") if len(p.stem) == 10)
    for p in files:
        year = int(p.stem[:4])
        if year < 2015 or year > 2017:
            continue
        date = pd.to_datetime(p.stem)
        with p.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                novelty = str(obj.get("information_novelty", "") or "").strip().lower()
                if novelty not in NOVELTY_ALLOWED:
                    continue
                tickers = obj.get("tickers")
                if not isinstance(tickers, list):
                    continue
                for ticker in tickers:
                    ticker = str(ticker).strip().upper()
                    if not ticker:
                        continue
                    rows.append(
                        {
                            "time": date,
                            "ticker": ticker,
                            "novelty": novelty,
                        }
                    )

    if not rows:
        return pd.DataFrame(columns=["time", "ticker", "new", "follow_up", "recycled", "novelty_total"])

    frame = pd.DataFrame(rows)
    pivot = frame.pivot_table(index=["time", "ticker"], columns="novelty", aggfunc="size", fill_value=0)
    pivot = pivot.reset_index()
    pivot.columns.name = None
    for col in NOVELTY_ALLOWED:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["novelty_total"] = pivot[list(NOVELTY_ALLOWED)].sum(axis=1)
    pivot["new_minus_recycled"] = pivot["new"] - pivot["recycled"]
    pivot["follow_up_minus_recycled"] = pivot["follow_up"] - pivot["recycled"]
    pivot["follow_up_minus_new"] = pivot["follow_up"] - pivot["new"]
    pivot["time"] = pd.to_datetime(pivot["time"], errors="coerce")
    return pivot.sort_values(["time", "ticker"]).reset_index(drop=True)


def _build_panel() -> pd.DataFrame:
    novelty = _load_novelty_panel()
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[(close.index.year >= 2015) & (close.index.year <= 2017)].copy()
    benchmark_close = load_vni_close().reindex(close.index)

    panels = []
    for horizon in TARGET_HORIZONS:
        target = _future_excess_return(close, benchmark_close, periods=horizon)
        target_long = to_long(target, f"future_rel_return_{horizon}d")
        target_long["time"] = pd.to_datetime(target_long["time"], errors="coerce")
        target_long = target_long[target_long["time"].dt.year <= 2017].copy()
        merged = novelty.merge(target_long, on=["time", "ticker"], how="inner")
        merged = merged.dropna(subset=[f"future_rel_return_{horizon}d"])
        merged["horizon"] = f"{horizon}d"
        panels.append(merged)

    if not panels:
        return pd.DataFrame()
    return pd.concat(panels, ignore_index=True)


@dataclass
class FeatureResult:
    feature_name: str
    horizon: str
    mean_ic: float
    daily_hit_rate: float
    positive_years: int
    years_present: int
    daily_rows: int
    row_count: int
    nonzero_rows: int
    feature_mean: float
    target_mean: float


def _evaluate_feature(panel: pd.DataFrame, feature_col: str, horizon: str) -> FeatureResult:
    target_col = f"future_rel_return_{horizon}"
    sub = panel[["time", feature_col, target_col]].copy()
    ic_rows = _daily_ic_series(sub, feature_col, target_col)
    stats = _summary_from_series(ic_rows)
    stats["row_count"] = int(len(sub))
    stats["nonzero_rows"] = int((pd.to_numeric(sub[feature_col], errors="coerce").fillna(0.0) != 0.0).sum())
    stats["feature_mean"] = float(pd.to_numeric(sub[feature_col], errors="coerce").mean()) if len(sub) else float("nan")
    stats["target_mean"] = float(pd.to_numeric(sub[target_col], errors="coerce").mean()) if len(sub) else float("nan")
    return FeatureResult(feature_col, horizon, **stats)


def main() -> None:
    print("Building news decay contract audit panel...")
    panel = _build_panel()
    if panel.empty:
        raise ValueError("No matched LLM novelty rows for the decay audit window")

    features = [
        "new",
        "follow_up",
        "recycled",
        "new_minus_recycled",
        "follow_up_minus_recycled",
        "follow_up_minus_new",
    ]

    feature_results: list[FeatureResult] = []
    for horizon in [f"{h}d" for h in TARGET_HORIZONS]:
        for feature in features:
            feature_results.append(_evaluate_feature(panel, feature, horizon))

    feature_df = pd.DataFrame([r.__dict__ for r in feature_results])
    feature_df = feature_df.sort_values(
        by=["mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[False, False, False],
        ignore_index=True,
    )

    horizon_table = []
    per_horizon_best = []
    for horizon in [f"{h}d" for h in TARGET_HORIZONS]:
        horizon_df = feature_df[feature_df["horizon"] == horizon].copy()
        best_row = horizon_df.iloc[0].to_dict()
        per_horizon_best.append(best_row)
        horizon_table.append(
            {
                "horizon": horizon,
                "best_feature": best_row["feature_name"],
                "best_mean_ic": float(best_row["mean_ic"]),
                "best_daily_hit_rate": float(best_row["daily_hit_rate"]),
                "best_positive_years": int(best_row["positive_years"]),
                "best_years_present": int(best_row["years_present"]),
            }
        )

    class_summary = feature_df[feature_df["feature_name"].isin(["new", "follow_up", "recycled"])].copy()
    class_summary = class_summary.sort_values(["feature_name", "mean_ic"], ascending=[True, False]).reset_index(drop=True)
    class_best_rows = {
        feature: group.sort_values("mean_ic", ascending=False).iloc[0].to_dict()
        for feature, group in class_summary.groupby("feature_name", sort=False)
    }

    best_row = feature_df.iloc[0].to_dict()
    best_feature = str(best_row["feature_name"])
    best_horizon = str(best_row["horizon"])
    best_mean_ic = float(best_row["mean_ic"])
    best_hit_rate = float(best_row["daily_hit_rate"])
    best_positive_years = int(best_row["positive_years"])
    best_years_present = int(best_row["years_present"])
    best_daily_rows = int(best_row["daily_rows"])
    best_nonzero_rows = int(best_row["nonzero_rows"])
    best_feature_mean = float(best_row["feature_mean"])
    best_target_mean = float(best_row["target_mean"])

    # The contract is considered real only if the follow-up class is the
    # strongest short-horizon novelty and recycled turns weaker at the longest
    # horizon. This is intentionally conservative.
    horizon_best = {row["horizon"]: row for row in horizon_table}
    pass_condition = bool(
        horizon_best["1d"]["best_feature"] == "follow_up"
        and horizon_best["5d"]["best_feature"] == "follow_up"
        and class_best_rows["follow_up"]["mean_ic"] >= 0.01
        and class_best_rows["follow_up"]["positive_years"] >= 1
        and class_best_rows["recycled"]["mean_ic"] < class_best_rows["follow_up"]["mean_ic"]
        and class_best_rows["recycled"]["mean_ic"] < 0.01
    )
    mixed_condition = bool(
        class_best_rows["follow_up"]["mean_ic"] > class_best_rows["new"]["mean_ic"]
        and class_best_rows["follow_up"]["mean_ic"] > class_best_rows["recycled"]["mean_ic"]
    )
    verdict = "PASS" if pass_condition else "MIXED" if mixed_condition else "FAIL"

    print("\nH291 NEWS DECAY CONTRACT RESULTS")
    print("=" * 140)
    print("Feature / horizon table:")
    print(feature_df[["feature_name", "horizon", "mean_ic", "daily_hit_rate", "positive_years", "years_present", "daily_rows"]].to_string(index=False))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h291_news_decay_contract_audit_details.json"
    summary = {
        "verdict": verdict,
        "best_feature": best_feature,
        "best_horizon": best_horizon,
        "best_mean_ic": best_mean_ic,
        "best_daily_hit_rate": best_hit_rate,
        "best_positive_years": best_positive_years,
        "best_years_present": best_years_present,
        "best_daily_rows": best_daily_rows,
        "best_nonzero_rows": best_nonzero_rows,
        "best_feature_mean": best_feature_mean,
        "best_target_mean": best_target_mean,
        "feature_table": feature_df.to_dict("records"),
        "horizon_table": horizon_table,
        "class_summary": class_summary.to_dict("records"),
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "window_years": sorted(int(y) for y in panel["time"].dt.year.unique().tolist()),
        "nonzero_window_rows": int((panel[list(NOVELTY_ALLOWED)].fillna(0.0) != 0.0).any(axis=1).sum()),
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h291_news_decay_contract_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H291"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
