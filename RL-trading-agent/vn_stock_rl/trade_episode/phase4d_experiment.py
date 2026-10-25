"""Run the preregistered, bounded Phase 4D supervised exit experiment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["MPLBACKEND"] = "Agg"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _thread_variable in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def run_experiment(
    config_path: Path | None = None, *, data_root: Path | None = None
) -> dict[str, Any]:
    from vn_stock_rl.trade_episode.data import load_daily_stock_bars, stock_bars_path
    from vn_stock_rl.trade_episode.phase4a_data import (
        DATA_CUTOFF,
        PHASE4A_TICKERS,
        prepare_stock,
    )
    from vn_stock_rl.trade_episode.phase4b_provenance import verify_checkpoint_manifest
    from vn_stock_rl.trade_episode.phase4b_regimes import build_causal_vnindex_regimes
    from vn_stock_rl.trade_episode.phase4d_experiment_support import (
        _file_stat,
        _git,
        _json_default,
        _mean,
        _prediction_rows,
        _prepared_fingerprint,
        _regime_map_for_stocks,
        _sha256_file,
        _write_csv,
    )
    from vn_stock_rl.trade_episode.phase4d_policy import (
        make_entry_schedule,
        simulate_fixed_entry_policy,
    )
    from vn_stock_rl.trade_episode.phase4d_supervised import (
        fit_exit_models,
        generate_exit_examples,
    )
    from vn_stock_rl.trade_episode.signals import C16_ARTIFACT, S1_ARTIFACT

    root = Path(__file__).resolve().parents[3]
    config_path = config_path or (
        root / "RL-trading-agent/configs/trade_episode/phase4d_supervised_exit.json"
    )
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text())
    protocol_path = root / config["protocol_path"]
    manifest_path = root / config["ppo_reference"]["checkpoint_manifest"]
    phase4b_metrics_path = root / config["ppo_reference"]["phase4b_metrics"]
    phase4b_regime_path = root / config["ppo_reference"]["phase4b_regime_metrics"]
    checkpoint_manifest = json.loads(manifest_path.read_text())
    if data_root is None:
        raw_data_root = os.environ.get(config["data_root_env"])
        if not raw_data_root:
            raise RuntimeError(
                "Set STOCKS_DATA_ROOT or pass --data-root to the shared read-only data root"
            )
        data_root = Path(raw_data_root)
    data_root = data_root.expanduser().resolve(strict=True)
    if not data_root.is_dir():
        raise NotADirectoryError(data_root)

    output_dir = root / config["results_dir"]
    model_dir = root / config["isolated_model_dir"]
    for path in (output_dir, model_dir):
        if path.exists() and any(path.iterdir()):
            raise FileExistsError(f"Refusing to overwrite non-empty isolated output: {path}")

    branch = _git(root, "branch", "--show-current")
    if branch != "exp/stock-rl-trade-episode":
        raise RuntimeError(f"Phase 4D must run on its isolated branch, got {branch}")
    if _git(root, "status", "--porcelain"):
        raise RuntimeError(
            "Phase 4D fitting requires committed source and a clean starting worktree"
        )
    run_commit = _git(root, "rev-parse", "HEAD")
    start_time = time.monotonic()
    execution_time = datetime.now(timezone.utc).isoformat()

    checkpoint_hashes_before = verify_checkpoint_manifest(checkpoint_manifest["checkpoints"])
    phase4b_hash_before = _sha256_file(phase4b_metrics_path)
    phase4b_regime_hash_before = _sha256_file(phase4b_regime_path)
    phase4a_trade_path = Path(
        config["ppo_reference"]["entry_conditioned_diagnostic"]["phase4a_trade_log"]
    )
    phase4a_trade_hash = _sha256_file(phase4a_trade_path)
    expected_trade_hash = checkpoint_manifest["files"].get("phase4a_trades.csv")
    if expected_trade_hash and phase4a_trade_hash != expected_trade_hash:
        raise RuntimeError("Saved Phase 4A trade log hash does not match the Phase 4B manifest")

    input_paths = {
        "daily_ohlcv": [stock_bars_path(ticker, data_root=data_root) for ticker in PHASE4A_TICKERS],
        "s1": [data_root / S1_ARTIFACT],
        "c16": [data_root / C16_ARTIFACT],
        "tradability": [data_root / "features/execution/tradability_daily.parquet"],
        "market_index": [stock_bars_path("VNINDEX", data_root=data_root)],
    }
    flat_input_paths = sorted(
        {path.resolve(strict=True) for paths in input_paths.values() for path in paths}
    )
    input_file_stats_before = {str(path): _file_stat(path) for path in flat_input_paths}

    stocks = {ticker: prepare_stock(ticker, data_root=data_root) for ticker in PHASE4A_TICKERS}
    for ticker, stock in stocks.items():
        if stock.dates.max() > DATA_CUTOFF:
            raise RuntimeError(f"{ticker}: prepared rows exceed the preregistered 2025 cutoff")
        if (
            not np.isfinite(stock.market_features).all()
            or not np.isfinite(stock.alpha_features).all()
        ):
            raise RuntimeError(f"{ticker}: non-finite input features")

    index_bars = load_daily_stock_bars("VNINDEX", data_root=data_root, end_date=DATA_CUTOFF)
    if pd.Timestamp(index_bars["time"].max()).normalize() > DATA_CUTOFF:
        raise RuntimeError("VNINDEX regime input exceeded the allowed date cutoff")
    regime_frame = build_causal_vnindex_regimes(index_bars, cutoff=DATA_CUTOFF)
    regime_by_date = _regime_map_for_stocks(regime_frame, stocks)

    effective_config = json.loads(
        (
            root / "RL-trading-agent/research/trade_episode/phase4b/phase4a_effective_config.json"
        ).read_text()
    )
    state_config = effective_config["environment"]
    target_cfg = config["target"]
    ages = tuple(int(age) for age in target_cfg["eligible_current_holding_ages"])
    sample_stride = int(config["training_examples"]["sample_stride_trading_rows"])
    train_examples = generate_exit_examples(
        stocks,
        tickers=tuple(config["training_tickers"]),
        split="train",
        ages=ages,
        stride=sample_stride,
        phase4a_state_config=state_config,
    )
    models = fit_exit_models(train_examples, config=config)

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory changed while preparing: {output_dir}")
    if model_dir.exists() and any(model_dir.iterdir()):
        raise FileExistsError(f"Model directory changed while preparing: {model_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_artifacts: dict[str, dict[str, str]] = {}
    for model_id, model in models.items():
        model_path = model_dir / f"{model_id}.joblib"
        joblib.dump(model, model_path, compress=3)
        model_artifacts[model_id] = {
            "path": str(model_path.relative_to(root)),
            "sha256": _sha256_file(model_path),
        }

    prediction_rows: list[dict[str, Any]] = []
    evaluation_examples: dict[str, Any] = {}
    for split, tickers in (
        ("validation", tuple(config["threshold_selection_tickers"])),
        ("exploratory", tuple(PHASE4A_TICKERS)),
    ):
        examples = generate_exit_examples(
            stocks,
            tickers=tickers,
            split=split,
            ages=ages,
            stride=sample_stride,
            phase4a_state_config=state_config,
        )
        evaluation_examples[split] = examples
        prediction_rows.extend(_prediction_rows(examples, models))

    policy_config = config["policy"]
    max_holding = int(policy_config["maximum_holding_intervals"])
    max_model_age = int(policy_config["model_last_decision_holding_age"])
    entry_stride = int(policy_config["entry_schedule_stride_trading_rows"])
    threshold_grid = [float(value) for value in policy_config["threshold_grid_delta_reward"]]
    main_model_ids = [
        "ridge_market",
        "ridge_market_alpha",
        "extra_trees_market",
        "extra_trees_market_alpha",
    ]

    threshold_results: dict[str, Any] = {}
    thresholds: dict[str, float] = {}
    validation_duration_pools: dict[str, tuple[int, ...]] = {}
    for model_id in main_model_ids:
        candidates: list[dict[str, Any]] = []
        for threshold_index, threshold in enumerate(threshold_grid):
            results = []
            for ticker in config["threshold_selection_tickers"]:
                stock = stocks[ticker]
                schedule = make_entry_schedule(
                    stock,
                    split="validation",
                    stride=entry_stride,
                    maximum_holding_intervals=max_holding,
                )
                result = simulate_fixed_entry_policy(
                    stock,
                    split="validation",
                    entry_decision_indices=schedule["decision_indices"],
                    policy_id=f"validation:{model_id}:{threshold}",
                    policy_kind="supervised",
                    phase4a_state_config=state_config,
                    maximum_holding_intervals=max_holding,
                    model_last_decision_age=max_model_age,
                    regime_by_date=regime_by_date,
                    model=models[model_id],
                    threshold=threshold,
                )
                results.append(result)
            mean_cagr = _mean(result["chronological_portfolio_cagr"] for result in results)
            mean_trades = _mean(result["number_of_trades"] for result in results)
            candidates.append(
                {
                    "threshold": threshold,
                    "threshold_index": threshold_index,
                    "equal_ticker_mean_cagr": mean_cagr,
                    "mean_trades_per_ticker": mean_trades,
                    "results": results,
                }
            )
        selected = max(
            candidates,
            key=lambda row: (
                row["equal_ticker_mean_cagr"],
                -row["mean_trades_per_ticker"],
                -row["threshold_index"],
            ),
        )
        thresholds[model_id] = float(selected["threshold"])
        threshold_results[model_id] = [
            {key: value for key, value in row.items() if key not in {"results", "threshold_index"}}
            for row in candidates
        ]
        durations = [
            int(trade["holding_duration"])
            for result in selected["results"]
            for trade in result["trades"]
            if not trade["incomplete"]
        ]
        if not durations:
            raise RuntimeError(
                f"{model_id}: validation policy produced no exit durations for matching"
            )
        validation_duration_pools[model_id] = tuple(durations)

    from vn_stock_rl.trade_episode.phase4d_evaluation import run_evaluation

    evaluation = run_evaluation(
        config=config,
        stocks=stocks,
        models=models,
        thresholds=thresholds,
        validation_duration_pools=validation_duration_pools,
        state_config=state_config,
        regime_by_date=regime_by_date,
        phase4b_metrics_path=phase4b_metrics_path,
        phase4b_regime_path=phase4b_regime_path,
        phase4a_trade_path=phase4a_trade_path,
    )
    policy_rows = evaluation["policy_rows"]
    trade_rows = evaluation["trade_rows"]
    year_regime_rows = evaluation["year_regime_rows"]
    random_rows = evaluation["random_rows"]
    ppo_entry_diagnostic_rows = evaluation["ppo_entry_diagnostic_rows"]
    all_metric_summaries = evaluation["all_metric_summaries"]
    overlap_summary = evaluation["overlap_summary"]
    match_summary = evaluation["match_summary"]
    bootstrap_rows = evaluation["bootstrap_rows"]
    support_checks = evaluation["support_checks"]
    h6_verdict = evaluation["h6_verdict"]
    h6_supported = evaluation["h6_supported"]
    h6_contradicted = evaluation["h6_contradicted"]
    adequate_comparison = evaluation["adequate_comparison"]

    # Dataset, checkpoint, and reference immutability check after all evaluations.
    input_file_stats_after = {str(path): _file_stat(path) for path in flat_input_paths}
    if input_file_stats_before != input_file_stats_after:
        raise RuntimeError("A shared input data file changed during Phase 4D")
    checkpoint_hashes_after = verify_checkpoint_manifest(checkpoint_manifest["checkpoints"])
    if checkpoint_hashes_before != checkpoint_hashes_after:
        raise RuntimeError("A frozen Phase 4A PPO checkpoint changed during Phase 4D")
    if _sha256_file(phase4b_metrics_path) != phase4b_hash_before:
        raise RuntimeError("The saved Phase 4B full-policy reference changed during Phase 4D")
    if _sha256_file(phase4b_regime_path) != phase4b_regime_hash_before:
        raise RuntimeError("The saved Phase 4B regime reference changed during Phase 4D")
    if _sha256_file(phase4a_trade_path) != phase4a_trade_hash:
        raise RuntimeError("The saved Phase 4A trade log changed during Phase 4D")

    prediction_summary = {}
    for split in ("validation", "exploratory"):
        frame = pd.DataFrame(
            [row for row in prediction_rows if row["split"] == split and "ticker" not in row]
        )
        prediction_summary[split] = frame.to_dict(orient="records")

    summary = {
        "experiment_id": config["experiment_id"],
        "execution_date_utc": execution_time,
        "run_code_commit_sha": run_commit,
        "branch": branch,
        "protocol_sha256": _sha256_file(protocol_path),
        "config_sha256": _sha256_file(config_path),
        "config": config,
        "python_version": sys.version,
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scikit-learn", "joblib", "pyarrow")
        },
        "training_sample_count": int(len(train_examples.target)),
        "training_ticker_count": int(len(config["training_tickers"])),
        "training_ticker_year_age_strata": int(
            train_examples.metadata.groupby(["ticker", "year", "current_holding_age"]).ngroups
        ),
        "thresholds_selected_on_validation_training_tickers": thresholds,
        "threshold_selection_results": threshold_results,
        "models": model_artifacts,
        "input_data_root": str(data_root),
        "input_file_metadata_fingerprints": input_file_stats_before,
        "prepared_stock_sha256": {
            ticker: _prepared_fingerprint(stock) for ticker, stock in stocks.items()
        },
        "stock_coverage": {ticker: stock.metadata for ticker, stock in stocks.items()},
        "regime_definition": {
            "index": "VNINDEX",
            "trailing_sessions": 126,
            "rising_if_return_at_least": 0.10,
            "falling_if_return_at_most": -0.10,
            "cutoff": str(DATA_CUTOFF.date()),
            "coverage_counts": regime_frame["regime"].value_counts().to_dict(),
        },
        "prediction_overview": prediction_summary,
        "policy_group_summaries": all_metric_summaries,
        "random_control_matching": {
            "entry_overlap": overlap_summary,
            "duration_and_exposure": match_summary,
        },
        "paired_uncertainty": bootstrap_rows,
        "h6_support_checks": support_checks,
        "h6_verdict": h6_verdict,
        "h6_supported": bool(h6_supported),
        "h6_contradicted_under_preregistered_rule": bool(h6_contradicted),
        "adequate_comparison_coverage_and_matching": bool(adequate_comparison),
        "ppo_full_policy_reference": {
            "source": config["ppo_reference"]["phase4b_metrics"],
            "sha256": phase4b_hash_before,
            "regime_source": config["ppo_reference"]["phase4b_regime_metrics"],
            "regime_sha256": phase4b_regime_hash_before,
            "interpretation": "separate entry policy; descriptive context only",
        },
        "phase4a_entry_diagnostic": {
            "source": str(phase4a_trade_path),
            "sha256": phase4a_trade_hash,
            "records": len(ppo_entry_diagnostic_rows),
            "interpretation": "overlapping per-trade counterfactuals; not a portfolio",
        },
        "checkpoint_hashes_before": checkpoint_hashes_before,
        "checkpoint_hashes_after": checkpoint_hashes_after,
        "runtime_seconds": time.monotonic() - start_time,
        "date_cutoff_assertion": (
            "all prepared stock/index rows and evaluated outcomes <= 2025-12-31"
        ),
        "shared_data_modified": False,
        "ppo_retrained": False,
    }

    (output_dir / "phase4d_config_snapshot.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    _write_csv(output_dir / "phase4d_prediction_metrics.csv", prediction_rows)
    _write_csv(output_dir / "phase4d_policy_metrics.csv", policy_rows)
    _write_csv(output_dir / "phase4d_trades.csv", trade_rows)
    _write_csv(output_dir / "phase4d_year_regime_metrics.csv", year_regime_rows)
    _write_csv(output_dir / "phase4d_random_controls.csv", random_rows)
    _write_csv(output_dir / "phase4d_ppo_entry_diagnostic.csv", ppo_entry_diagnostic_rows)
    _write_csv(output_dir / "phase4d_bootstrap_comparisons.csv", bootstrap_rows)
    (output_dir / "phase4d_metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=_json_default, allow_nan=False) + "\n"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    result = run_experiment(args.config, data_root=args.data_root)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "run_code_commit_sha": result["run_code_commit_sha"],
                "h6_verdict": result["h6_verdict"],
                "runtime_seconds": round(result["runtime_seconds"], 2),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
