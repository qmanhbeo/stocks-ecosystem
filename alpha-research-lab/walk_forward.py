"""
walk_forward.py -- Year-by-year walk-forward validation.

Trains on all data before a test year, evaluates on that year.
Escapes the val/test regime bias problem: gives signal consistency across market regimes.

Usage:
    python walk_forward.py --config configs/A1_lags_only.json
    python walk_forward.py --config configs/A1_lags_only.json --min-train-years 3

Output:
    - Per-year results printed to stdout
    - Summary appended to wf_results.jsonl
    - Compact per-run summary written to artifacts/run_summaries/
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model
from src.evaluator import evaluate_model
from src.run_summary import write_run_summary


def run_walk_forward(config_path: str, min_train_years: int = 3):
    with open(config_path) as f:
        config = json.load(f)

    exp_name = config.get("experiment_name", "unnamed")
    data_cfg = config.get("data", {})
    file_path = data_cfg.get("file_path", "gia_lich_su_FPT_1D.parquet")
    start_date = data_cfg.get("start_date", "2016-01-01")
    target_col = data_cfg.get("target_col", "future_return_5d")

    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION: {exp_name}")
    print(f"Config: {config_path}  |  Target: {target_col}  |  Min train: {min_train_years}y")
    print(f"{'='*70}")

    df = load_data(file_path, start_date)
    df = generate_features(df, config)
    feature_cols = get_feature_columns(df, config)
    df["_year"] = pd.to_datetime(df["time"]).dt.year

    start_year = int(df["_year"].min()) + min_train_years
    end_year   = int(df["_year"].max())  # last full year (2026 is partial — skip)
    if end_year == datetime.now().year:
        end_year -= 1   # current year is incomplete

    per_year = []

    print(f"\n  {'year':>5}  {'n_test':>7}  {'dir_acc':>8}  {'naive':>7}  {'edge':>7}  {'pval_naive':>11}")
    print("  " + "-" * 60)

    for test_year in range(start_year, end_year + 1):
        train_mask = df["_year"] < test_year
        test_mask  = df["_year"] == test_year

        train_df = df[train_mask].copy()
        test_df  = df[test_mask].copy()

        if len(train_df) < 200 or len(test_df) < 20:
            print(f"  [SKIP] {test_year}: train={len(train_df)}, test={len(test_df)}")
            continue

        X_train = train_df[feature_cols]
        y_train = train_df[target_col]
        X_test  = test_df[feature_cols]
        y_test  = test_df[target_col]

        model = get_model(config)
        fit_params = {}
        model_type = config.get("model", {}).get("type", "")
        if model_type in ("xgboost", "xgboost_classifier"):
            # Use last 15% of train as internal val for early stopping
            n_val = max(30, int(len(X_train) * 0.15))
            X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
            X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]
            fit_params["eval_set"] = [(X_v, y_v)]
            fit_params["verbose"] = False
        elif model_type == "lightgbm_classifier":
            # LightGBM uses callbacks for early stopping; pass eval_set the same way
            n_val = max(30, int(len(X_train) * 0.15))
            X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
            X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]
            fit_params["eval_set"] = [(X_v, y_v)]
            fit_params["callbacks"] = []
            try:
                from lightgbm import early_stopping, log_evaluation
                early_rounds = config.get("model", {}).get("params", {}).get("early_stopping_rounds", 30)
                fit_params["callbacks"] = [early_stopping(early_rounds, verbose=False),
                                           log_evaluation(period=-1)]
            except ImportError:
                pass
        else:
            X_tr, y_tr = X_train, y_train

        model.fit(X_tr, y_tr, **fit_params)

        preds = model.predict(X_test)
        m = evaluate_model(y_test, preds)

        edge = m["edge_over_naive"]
        edge_str = f"{edge*100:+.2f}%"
        sig = "*" if m["dir_pvalue_vs_naive"] < 0.05 else " "
        print(f"  {test_year:>5}  {len(test_df):>7}  {m['direction_accuracy']*100:>7.2f}%"
              f"  {m['naive_dir_acc']*100:>6.1f}%  {edge_str:>7}  {m['dir_pvalue_vs_naive']:>9.4f}{sig}")

        per_year.append({
            "year": test_year,
            "n": len(test_df),
            "dir": round(m["direction_accuracy"], 4),
            "naive": round(m["naive_dir_acc"], 4),
            "edge": round(edge, 4),
            "pval_naive": round(m["dir_pvalue_vs_naive"], 4),
            "mae": round(m["mae"], 5),
        })

    if not per_year:
        print("  Not enough data for walk-forward validation.")
        return

    # Summary
    edges = [r["edge"] for r in per_year]
    dirs  = [r["dir"]  for r in per_year]
    pvs   = [r["pval_naive"] for r in per_year]
    n_sig = sum(1 for p in pvs if p < 0.05)

    print(f"\n  {'SUMMARY':>5}")
    print(f"  Avg dir_acc  : {np.mean(dirs)*100:.2f}%")
    print(f"  Avg edge     : {np.mean(edges)*100:+.2f}%  (std: {np.std(edges)*100:.2f}%)")
    print(f"  Sig years    : {n_sig}/{len(per_year)} (p<0.05 vs drift)")
    print(f"  Best year    : {per_year[np.argmax(edges)]['year']} ({max(edges)*100:+.2f}% edge)")
    print(f"  Worst year   : {per_year[np.argmin(edges)]['year']} ({min(edges)*100:+.2f}% edge)")

    # Save to wf_results.jsonl
    record = {
        "ts": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "name": exp_name,
        "model": config.get("model", {}).get("type"),
        "target": target_col,
        "n_features": len(feature_cols),
        "cfg": config_path,
        "avg_dir": round(np.mean(dirs), 4),
        "avg_edge": round(np.mean(edges), 4),
        "std_edge": round(np.std(edges), 4),
        "n_sig_years": n_sig,
        "total_years": len(per_year),
        "per_year": per_year,
    }
    with open("wf_results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    summary_path = write_run_summary(
        ts=record["ts"],
        mode="walk_forward",
        name=exp_name,
        summary={
            "avg_dir_acc": round(np.mean(dirs), 4),
            "avg_edge": round(np.mean(edges), 4),
            "std_edge": round(np.std(edges), 4),
            "n_sig_years": n_sig,
            "total_years": len(per_year),
            "best_year": per_year[np.argmax(edges)]["year"],
            "worst_year": per_year[np.argmin(edges)]["year"],
        },
        artifacts={
            "config": config_path,
            "wf_log": "wf_results.jsonl",
        },
        metadata={
            "target": target_col,
            "model": config.get("model", {}).get("type"),
            "n_features": len(feature_cols),
        },
    )

    print(f"\n  Results appended to wf_results.jsonl")
    print(f"  Run summary saved to {summary_path}\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--min-train-years", type=int, default=3,
                        help="Minimum years of training data before first test year")
    args = parser.parse_args()
    run_walk_forward(args.config, args.min_train_years)
