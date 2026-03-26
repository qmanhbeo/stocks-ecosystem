import argparse
import json
import os
import pandas as pd
import joblib
from datetime import datetime
from src.data_loader import load_data, split_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model
from src.evaluator import evaluate_model
from src.run_summary import write_run_summary


def update_status(n_recent=5):
    """Regenerate STATUS.md from results_summary.jsonl. Called after every experiment."""
    summary_file = "results_summary.jsonl"
    results = []
    try:
        with open(summary_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    except FileNotFoundError:
        return
    if not results:
        return

    recent = results[-n_recent:]
    last_ts = results[-1]["ts"]
    total = len(results)

    # Best by edge over naive (the real signal metric; test is sacred so use val)
    has_edge = [r for r in results if "edge" in r.get("val", {})]
    best_val = max(has_edge if has_edge else results, key=lambda r: r["val"].get("edge", r["val"]["dir"]))
    # Best by test metrics (only from entries that have test metrics)
    tested = [r for r in results if r.get("test")]
    best_test_str = ""
    if tested:
        best_test = max(tested, key=lambda r: r["test"].get("edge", r["test"]["dir"]))
        best_test_str = "| test_edge_over_naive (final) | {:.2f}% | {} ({}) |".format(
            best_test["test"].get("edge", 0) * 100, best_test["name"], best_test["ts"]
        )

    # Recent experiments table
    rows = []
    for r in recent:
        edge = r["val"].get("edge", float("nan"))
        edge_str = "{:+.2f}%".format(edge * 100) if edge == edge else "  n/a"
        pval_n = r["val"].get("pval_naive", float("nan"))
        pval_str = "{:.3f}".format(pval_n) if pval_n == pval_n else " n/a"
        test_edge = "{:+.2f}%".format(r["test"].get("edge", 0) * 100) if r.get("test") else "SACRED"
        rows.append(
            "| {} | {} | {} | {:.1f}% | {} | {} | {} |".format(
                r["ts"], r["name"], r["model"],
                r["val"]["dir"] * 100, edge_str, pval_str, test_edge,
            )
        )
    table = "\n".join(rows)

    status = (
        "# PROJECT STATUS\n"
        "_Auto-updated after each experiment. Last run: {last_ts}. Total experiments: {total}._\n"
        "\n"
        "## Mission\n"
        "Self-improving FPT stock signal prediction. Find real market signals through iterative experiments.\n"
        "**KEY INSIGHT: FPT has ~60% upward drift. Raw dir_acc is misleading.**\n"
        "**Real metric: edge_over_naive = dir_acc - naive_always_up_acc** (>2% edge + pval_naive<0.05 = real signal)\n"
        "\n"
        "## Best Edge Over Naive So Far\n"
        "| metric | value | experiment |\n"
        "|--------|-------|------------|\n"
        "| val_edge_over_naive | {best_edge:.2f}% | {best_val_name} ({best_val_ts}) |\n"
        "{best_test_str}\n"
        "\n"
        "## Recent Experiments (last {n_shown} of {total})\n"
        "| ts | name | model | val_dir | edge_naive | pval_naive | test_edge |\n"
        "|---|---|---|---|---|---|---|\n"
        "{table}\n"
        "\n"
        "## Agent Quick-Start\n"
        "1. Read **AGENT_WORKFLOW.md** for the current agent protocol.\n"
        "2. One-shot runs write compact summaries to **artifacts/run_summaries/**.\n"
        "3. Run: python view_recent.py --best\n"
        "4. Create a config in configs/, then: python run_experiment.py --config configs/your_config.json\n"
        "5. To evaluate on test (FINAL only): python run_experiment.py --config configs/X.json --eval-test\n"
    ).format(
        last_ts=last_ts, total=total,
        best_edge=best_val["val"].get("edge", 0) * 100,
        best_val_name=best_val["name"], best_val_ts=best_val["ts"],
        best_test_str=best_test_str if best_test_str else "_No test evaluations yet (test set is sacred)._",
        n_shown=len(recent), table=table,
    )

    with open("STATUS.md", "w", encoding="utf-8") as f:
        f.write(status)


def run_experiment(config_path: str, eval_test: bool = False):
    # 1. Load Config
    with open(config_path, "r") as f:
        config = json.load(f)

    # 2. Setup Experiment Directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_name = config.get("experiment_name", "unnamed")
    exp_dir = os.path.join("experiments", f"{timestamp}_{exp_name}")
    os.makedirs(exp_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Experiment : {exp_name}")
    print(f"Output dir : {exp_dir}")
    print(f"Test eval  : {'YES (--eval-test)' if eval_test else 'NO (sacred)'}")
    print(f"{'='*60}")

    # 3. Load Data
    data_cfg = config.get("data", {})
    file_path = data_cfg.get("file_path", "gia_lich_su_FPT_1D.parquet")
    start_date = data_cfg.get("start_date", "2016-01-01")
    df = load_data(file_path, start_date)

    # 4. Feature Engineering
    df = generate_features(df, config)
    feature_cols = get_feature_columns(df, config)
    target_col = data_cfg.get("target_col", "future_return_5d")

    print(f"Features ({len(feature_cols)}): {feature_cols}")
    print(f"Target: {target_col}  |  Rows after dropna: {len(df)}")

    # 5. Split Data
    test_size = data_cfg.get("test_size", 0.15)
    val_size = data_cfg.get("val_size", 0.15)
    train_df, val_df, test_df = split_data(df, test_size, val_size)

    X_train, y_train = train_df[feature_cols], train_df[target_col]
    X_val,   y_val   = val_df[feature_cols],   val_df[target_col]
    X_test,  y_test  = test_df[feature_cols],  test_df[target_col]

    print(f"Split sizes -> train: {len(X_train)}, val: {len(X_val)}, test: {len(X_test)}")

    # 6. Train
    print("Training...")
    model_type = config.get("model", {}).get("type")
    model = get_model(config)
    fit_params = {}
    if model_type in ("xgboost", "xgboost_classifier"):
        fit_params["eval_set"] = [(X_val, y_val)]
        fit_params["verbose"] = False
    model.fit(X_train, y_train, **fit_params)

    # 7. Evaluate on VAL (always) and TEST (only if --eval-test)
    val_pred = model.predict(X_val)
    val_prob = model.predict_proba(X_val)[:, 1] if model_type == "xgboost_classifier" else None
    val_metrics = evaluate_model(y_val, val_pred, val_prob)

    test_metrics = None
    if eval_test:
        test_pred = model.predict(X_test)
        test_prob = model.predict_proba(X_test)[:, 1] if model_type == "xgboost_classifier" else None
        test_metrics = evaluate_model(y_test, test_pred, test_prob)

    def _print_metrics(label, m):
        edge = m["edge_over_naive"]
        edge_str = f"+{edge*100:.2f}%" if edge >= 0 else f"{edge*100:.2f}%"
        sig_naive = "*** BEATS DRIFT" if m["dir_pvalue_vs_naive"] < 0.05 else "(no edge over drift)"
        auc = m.get("auc", float("nan"))
        auc_str = f"  |  AUC: {auc:.4f}" if auc == auc else ""
        print(f"\n{label}:")
        print(f"  dir_acc      : {m['direction_accuracy']*100:.2f}%  |  naive_up: {m['naive_dir_acc']*100:.2f}%  |  edge: {edge_str}{auc_str}")
        print(f"  p-val vs 50% : {m['dir_pvalue']:.4f}  {'*** sig' if m['dir_pvalue'] < 0.05 else '(n.s.)'}"
              f"  |  p-val vs drift: {m['dir_pvalue_vs_naive']:.4f}  {sig_naive}")
        print(f"  MAE: {m['mae']:.5f}  |  RMSE: {m['rmse']:.5f}  |  R2: {m['r2']:.4f}")

    _print_metrics("Validation Metrics", val_metrics)
    if test_metrics:
        _print_metrics("Test Metrics (FINAL)", test_metrics)

    # 8. Save Results
    with open(os.path.join(exp_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=4)

    metrics_out = {"val": val_metrics, "test": test_metrics}
    with open(os.path.join(exp_dir, "metrics.json"), "w") as f:
        json.dump(metrics_out, f, indent=4)

    joblib.dump(model, os.path.join(exp_dir, "model.pkl"))

    # 9. Update results_summary.jsonl
    summary_file = "results_summary.jsonl"
    summary_data = {
        "ts": timestamp,
        "name": exp_name,
        "model": config.get("model", {}).get("type"),
        "n_features": len(feature_cols),
        "val": {
            "mae": round(val_metrics["mae"], 5),
            "rmse": round(val_metrics["rmse"], 5),
            "dir": round(val_metrics["direction_accuracy"], 4),
            "naive_dir": round(val_metrics["naive_dir_acc"], 4),
            "edge": round(val_metrics["edge_over_naive"], 4),
            "pval_50": round(val_metrics["dir_pvalue"], 4),
            "pval_naive": round(val_metrics["dir_pvalue_vs_naive"], 4),
        },
        "test": {
            "mae": round(test_metrics["mae"], 5),
            "rmse": round(test_metrics["rmse"], 5),
            "dir": round(test_metrics["direction_accuracy"], 4),
            "naive_dir": round(test_metrics["naive_dir_acc"], 4),
            "edge": round(test_metrics["edge_over_naive"], 4),
            "pval_50": round(test_metrics["dir_pvalue"], 4),
            "pval_naive": round(test_metrics["dir_pvalue_vs_naive"], 4),
        } if test_metrics else None,
        "cfg": os.path.join(exp_dir, "config.json"),
    }
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary_data) + "\n")

    summary_path = write_run_summary(
        ts=timestamp,
        mode="one_shot",
        name=exp_name,
        summary={
            "val_dir_acc": round(val_metrics["direction_accuracy"], 4),
            "val_edge": round(val_metrics["edge_over_naive"], 4),
            "val_pval_naive": round(val_metrics["dir_pvalue_vs_naive"], 4),
            "test_dir_acc": round(test_metrics["direction_accuracy"], 4) if test_metrics else None,
            "test_edge": round(test_metrics["edge_over_naive"], 4) if test_metrics else None,
            "test_pval_naive": round(test_metrics["dir_pvalue_vs_naive"], 4) if test_metrics else None,
        },
        artifacts={
            "experiment_dir": exp_dir,
            "config": os.path.join(exp_dir, "config.json"),
            "metrics": os.path.join(exp_dir, "metrics.json"),
            "summary_log": summary_file,
        },
        metadata={
            "model": config.get("model", {}).get("type"),
            "target": target_col,
            "n_features": len(feature_cols),
            "eval_test": eval_test,
        },
    )

    # 10. Regenerate STATUS.md
    update_status()

    print(f"\nDone. Results in: {exp_dir}")
    print(f"Run summary: {summary_path}")
    print(f"STATUS.md updated.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FPT Stock Prediction Experiment")
    parser.add_argument("--config", type=str, default="configs/default.json")
    parser.add_argument(
        "--eval-test", action="store_true",
        help="Also evaluate on the held-out test set. Use sparingly — test set is sacred."
    )
    args = parser.parse_args()
    run_experiment(args.config, eval_test=args.eval_test)
