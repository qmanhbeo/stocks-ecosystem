"""Finalize Phase 4D provenance from saved CSVs without rerunning evaluation."""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _mean(values) -> float | None:
    valid = [float(value) for value in values if pd.notna(value) and np.isfinite(value)]
    return None if not valid else float(np.mean(valid))


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_stat(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _entry_indices(value) -> set[int]:
    if not isinstance(value, str) or not value.strip():
        return set()
    try:
        return {int(item) for item in ast.literal_eval(value)}
    except (ValueError, SyntaxError, TypeError):
        return set()


def _summary_rows(policy_frame: pd.DataFrame) -> list[dict[str, Any]]:
    fields = (
        "chronological_portfolio_cagr",
        "total_calendar_return",
        "maximum_drawdown",
        "exposure_percentage",
        "number_of_trades",
        "win_rate",
        "mean_terminal_rl_reward",
        "mean_holding_duration",
        "mean_waiting_duration",
        "incomplete_open_positions",
    )
    frame = policy_frame.copy()
    frame["variant_key"] = frame["variant"].fillna("")
    groups = frame.groupby(["policy", "variant_key", "ticker_group"], dropna=False, sort=True)
    result = []
    for (policy, variant, ticker_group), group in groups:
        row: dict[str, Any] = {
            "policy": policy,
            "variant": variant or None,
            "ticker_group": ticker_group,
            "ticker_count": int(group["ticker"].nunique()),
            "aggregation": "equal-weight mean of separate stock paths; not a portfolio",
        }
        for field in fields:
            source = field
            if source not in group and field == "mean_holding_duration":
                source = "average_holding_duration"
            if source not in group and field == "mean_waiting_duration":
                source = "average_waiting_duration"
            if source in group:
                row[field] = _mean(group[source])
        result.append(row)
    return result


def _matching_summary(
    policies: pd.DataFrame, random_paths: pd.DataFrame, config: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    models = (
        "ridge_market",
        "ridge_market_alpha",
        "extra_trees_market",
        "extra_trees_market_alpha",
    )
    groups = ("training_universe", "unseen_ticker")
    fixed = ("mechanical_3", "mechanical_10", "mechanical_20")
    coverage_min = float(config["policy"]["common_entry_coverage_minimum"] * 100.0)
    hold_tolerance = float(config["randomized_exit_control"]["duration_match_tolerance_sessions"])
    exposure_tolerance = float(
        config["randomized_exit_control"]["exposure_match_tolerance_percentage_points"]
    )
    summary: dict[str, Any] = {}
    overall_adequate = True
    for model_id in models:
        candidate_id = f"supervised:{model_id}"
        summary[model_id] = {}
        for ticker_group in groups:
            ticker_rows = policies.loc[
                (policies["policy"] == candidate_id) & (policies["ticker_group"] == ticker_group)
            ]
            candidate_by_ticker = {
                str(row.ticker): row for row in ticker_rows.itertuples(index=False)
            }
            overlaps: list[float] = []
            hold_diffs: list[float] = []
            exposure_diffs: list[float] = []
            for ticker, candidate in candidate_by_ticker.items():
                candidate_indices = _entry_indices(
                    getattr(candidate, "executed_entry_decision_indices", "")
                )
                scheduled = int(getattr(candidate, "scheduled_entry_slots", 0) or 0)
                for policy in fixed:
                    control_rows = policies.loc[
                        (policies["policy"] == policy) & (policies["ticker"] == ticker)
                    ]
                    if control_rows.empty:
                        continue
                    control_indices = _entry_indices(
                        control_rows.iloc[0]["executed_entry_decision_indices"]
                    )
                    overlaps.append(
                        100.0 * len(candidate_indices & control_indices) / scheduled
                        if scheduled
                        else 100.0
                    )

                random_ticker = random_paths.loc[
                    (random_paths["model_id"] == model_id) & (random_paths["ticker"] == ticker)
                ]
                if not random_ticker.empty:
                    overlaps.extend(
                        float(value)
                        for value in random_ticker["entry_overlap_percentage"]
                        if pd.notna(value)
                    )
                    random_hold = _mean(random_ticker["mean_holding_duration"])
                    random_exposure = _mean(random_ticker["exposure_percentage"])
                    if random_hold is not None and pd.notna(candidate.mean_holding_duration):
                        hold_diffs.append(random_hold - float(candidate.mean_holding_duration))
                    if random_exposure is not None and pd.notna(candidate.exposure_percentage):
                        exposure_diffs.append(
                            random_exposure - float(candidate.exposure_percentage)
                        )

            mean_overlap = _mean(overlaps)
            mean_hold_diff = _mean(hold_diffs)
            mean_exposure_diff = _mean(exposure_diffs)
            adequate = bool(
                mean_overlap is not None
                and mean_overlap >= coverage_min
                and mean_hold_diff is not None
                and abs(mean_hold_diff) <= hold_tolerance
                and mean_exposure_diff is not None
                and abs(mean_exposure_diff) <= exposure_tolerance
            )
            overall_adequate = overall_adequate and adequate
            summary[model_id][ticker_group] = {
                "mean_common_entry_overlap_percentage": mean_overlap,
                "minimum_pairwise_entry_overlap_percentage": (
                    None if not overlaps else float(np.min(overlaps))
                ),
                "minimum_required_overlap_percentage": coverage_min,
                "mean_random_minus_supervised_holding_intervals": mean_hold_diff,
                "holding_match_tolerance_intervals": hold_tolerance,
                "mean_random_minus_supervised_exposure_percentage_points": mean_exposure_diff,
                "exposure_match_tolerance_percentage_points": exposure_tolerance,
                "adequate_mean_match": adequate,
            }
    return summary, overall_adequate


def _h6_verdict(bootstrap: pd.DataFrame, adequate: bool) -> dict[str, Any]:
    models = (
        "ridge_market",
        "ridge_market_alpha",
        "extra_trees_market",
        "extra_trees_market_alpha",
    )
    groups = ("training_universe", "unseen_ticker")
    controls = ("mechanical_3", "mechanical_10", "mechanical_20")
    checks = {}
    for model_id in models:
        candidate = f"supervised:{model_id}"
        model_rows = bootstrap.loc[bootstrap["candidate"] == candidate]
        comparisons = {}
        for row in model_rows.itertuples(index=False):
            control = (
                "matched_random"
                if str(row.comparator).startswith("matched_random_mean:")
                else str(row.comparator)
            )
            comparisons[f"{row.ticker_group}:{control}"] = {
                "equal_ticker_mean_cagr_difference": float(row.equal_ticker_mean_cagr_difference),
                "ci_low": float(row.bootstrap_ci_95_low),
                "ci_high": float(row.bootstrap_ci_95_high),
                "paired_tickers": int(row.paired_tickers),
                "paired_ticker_years": int(row.paired_ticker_years),
            }
        supported = all(
            comparisons.get(f"{group}:{control}", {}).get(
                "equal_ticker_mean_cagr_difference", -np.inf
            )
            >= 0.02
            and comparisons.get(f"{group}:{control}", {}).get("ci_low", -np.inf) > 0.0
            for group in groups
            for control in (*controls, "matched_random")
        )
        contradicted = all(
            any(
                comparisons.get(f"{group}:{control}", {}).get("ci_high", np.inf) < 0.02
                for control in (*controls, "matched_random")
            )
            for group in groups
        )
        checks[model_id] = {
            "beats_each_control_by_two_cagr_points_with_positive_95pct_lower_bound": supported,
            "excludes_two_point_advantage_over_at_least_one_control_in_both_groups": contradicted,
            "comparisons": comparisons,
        }
    supported = adequate and any(
        check["beats_each_control_by_two_cagr_points_with_positive_95pct_lower_bound"]
        for check in checks.values()
    )
    contradicted = adequate and all(
        check["excludes_two_point_advantage_over_at_least_one_control_in_both_groups"]
        for check in checks.values()
    )
    verdict = "supported" if supported else "contradicted" if contradicted else "inconclusive"
    return {
        "verdict": verdict,
        "supported": supported,
        "contradicted_under_preregistered_rule": contradicted,
        "adequate_coverage_and_matching": adequate,
        "model_checks": checks,
    }


def _random_percentiles(
    policy_frame: pd.DataFrame, random_frame: pd.DataFrame
) -> list[dict[str, Any]]:
    rows = []
    for model_id in random_frame["model_id"].dropna().unique():
        candidate_policy = f"supervised:{model_id}"
        for ticker_group in ("training_universe", "unseen_ticker"):
            candidate_rows = policy_frame.loc[
                (policy_frame["policy"] == candidate_policy)
                & (policy_frame["ticker_group"] == ticker_group)
            ]
            null_paths = random_frame.loc[
                (random_frame["model_id"] == model_id)
                & (random_frame["ticker_group"] == ticker_group)
            ]
            candidate = _mean(candidate_rows["chronological_portfolio_cagr"])
            by_seed = null_paths.groupby("random_seed")["chronological_portfolio_cagr"].mean()
            if candidate is None or by_seed.empty:
                continue
            rows.append(
                {
                    "model_id": model_id,
                    "ticker_group": ticker_group,
                    "candidate_equal_ticker_mean_cagr": candidate,
                    "random_control_mean_cagr": float(by_seed.mean()),
                    "random_control_cagr_p10": float(by_seed.quantile(0.10)),
                    "random_control_cagr_median": float(by_seed.median()),
                    "random_control_cagr_p90": float(by_seed.quantile(0.90)),
                    "candidate_percentile_in_random_null": float(
                        (by_seed <= candidate).mean() * 100.0
                    ),
                    "random_replicates": int(by_seed.size),
                }
            )
    return rows


def finalize_results(
    *, data_root: Path, run_code_sha: str, worktree_root: Path | None = None
) -> dict[str, Any]:
    from vn_stock_rl.trade_episode.data import load_daily_stock_bars, stock_bars_path
    from vn_stock_rl.trade_episode.phase4a_data import (
        DATA_CUTOFF,
        PHASE4A_TICKERS,
        TRAIN_TICKERS,
        prepare_stock,
    )
    from vn_stock_rl.trade_episode.phase4b_provenance import verify_checkpoint_manifest
    from vn_stock_rl.trade_episode.phase4b_regimes import build_causal_vnindex_regimes
    from vn_stock_rl.trade_episode.phase4d_experiment_support import (
        _json_safe,
        _prepared_fingerprint,
    )
    from vn_stock_rl.trade_episode.phase4d_supervised import generate_exit_examples
    from vn_stock_rl.trade_episode.signals import C16_ARTIFACT, S1_ARTIFACT

    root = (worktree_root or Path(__file__).resolve().parents[3]).resolve()
    data_root = data_root.expanduser().resolve(strict=True)
    config_path = root / "RL-trading-agent/configs/trade_episode/phase4d_supervised_exit.json"
    config = json.loads(config_path.read_text())
    output_dir = root / config["results_dir"]
    metrics_path = output_dir / "phase4d_metrics.json"
    if metrics_path.exists():
        raise FileExistsError(f"Refusing to overwrite finalized metrics: {metrics_path}")

    def read_csv(name):
        return pd.read_csv(output_dir / name)

    policy = read_csv("phase4d_policy_metrics.csv")
    predictions = read_csv("phase4d_prediction_metrics.csv")
    random_paths = read_csv("phase4d_random_controls.csv")
    bootstrap = read_csv("phase4d_bootstrap_comparisons.csv")
    ppo_diagnostic = read_csv("phase4d_ppo_entry_diagnostic.csv")
    model_dir = root / config["isolated_model_dir"]
    model_hashes = {
        path.stem: {"path": str(path.relative_to(root)), "sha256": _sha256(path)}
        for path in sorted(model_dir.glob("*.joblib"))
    }
    expected_model_ids = {
        "ridge_market",
        "ridge_market_alpha",
        "extra_trees_market",
        "extra_trees_market_alpha",
        "age_only_ridge",
        "constant_mean",
    }
    if set(model_hashes) != expected_model_ids:
        raise RuntimeError("Phase 4D model artifact set is incomplete")

    manifest_path = root / config["ppo_reference"]["checkpoint_manifest"]
    manifest = json.loads(manifest_path.read_text())
    checkpoint_hashes = verify_checkpoint_manifest(manifest["checkpoints"])
    phase4a_trade_path = Path(
        config["ppo_reference"]["entry_conditioned_diagnostic"]["phase4a_trade_log"]
    )
    phase4a_trade_hash = _sha256(phase4a_trade_path)
    phase4b_metrics_path = root / config["ppo_reference"]["phase4b_metrics"]
    phase4b_regime_path = root / config["ppo_reference"]["phase4b_regime_metrics"]

    input_paths = [
        *(stock_bars_path(ticker, data_root=data_root) for ticker in PHASE4A_TICKERS),
        data_root / S1_ARTIFACT,
        data_root / C16_ARTIFACT,
        data_root / "features/execution/tradability_daily.parquet",
        stock_bars_path("VNINDEX", data_root=data_root),
    ]
    flat_input_paths = sorted({path.resolve(strict=True) for path in input_paths})
    input_stat_before = {str(path): _file_stat(path) for path in flat_input_paths}
    stocks = {ticker: prepare_stock(ticker, data_root=data_root) for ticker in PHASE4A_TICKERS}
    if any(stock.dates.max() > DATA_CUTOFF for stock in stocks.values()):
        raise RuntimeError("Post-2025 rows were found in prepared feature inputs")
    state_config = json.loads(
        (
            root / "RL-trading-agent/research/trade_episode/phase4b/phase4a_effective_config.json"
        ).read_text()
    )["environment"]
    train_examples = generate_exit_examples(
        stocks,
        tickers=tuple(config["training_tickers"]),
        split="train",
        ages=tuple(config["target"]["eligible_current_holding_ages"]),
        stride=int(config["training_examples"]["sample_stride_trading_rows"]),
        phase4a_state_config=state_config,
    )
    index_bars = load_daily_stock_bars("VNINDEX", data_root=data_root, end_date=DATA_CUTOFF)
    regimes = build_causal_vnindex_regimes(index_bars, cutoff=DATA_CUTOFF)
    input_stat_after = {str(path): _file_stat(path) for path in flat_input_paths}
    if input_stat_before != input_stat_after:
        raise RuntimeError("A shared input file changed while finalizing provenance")

    matching, adequate = _matching_summary(policy, random_paths, config)
    h6 = _h6_verdict(bootstrap, adequate)
    ppo_reference = policy.loc[policy["policy"] == "frozen_PPO_full_policy"]
    ppo_diagnostic_summary = (
        ppo_diagnostic.groupby(["exit_controller", "ppo_variant", "ticker_group"], dropna=False)
        .agg(
            records=("terminal_rl_reward", "count"),
            mean_terminal_reward=("terminal_rl_reward", "mean"),
            median_terminal_reward=("terminal_rl_reward", "median"),
            mean_raw_trade_return=("raw_trade_return", "mean"),
            mean_holding_duration=("new_holding_duration", "mean"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    overview = predictions.loc[
        predictions["ticker"].isna() & predictions["ticker_group"].isna()
    ].to_dict(orient="records")
    current_head = _git(root, "rev-parse", "HEAD")
    executed_rows = policy.loc[policy["policy"].astype(str).str.startswith("supervised:")]
    thresholds = executed_rows.groupby("model_id")["threshold"].first().dropna().to_dict()
    reference_hashes = {
        "phase4b_stock_period_metrics": _sha256(phase4b_metrics_path),
        "phase4b_regime_metrics": _sha256(phase4b_regime_path),
        "phase4a_trade_log": phase4a_trade_hash,
    }
    summary = {
        "experiment_id": config["experiment_id"],
        "run_attempt": config.get("run_attempt", 1),
        "execution_date_utc": datetime.fromtimestamp(
            (output_dir / "phase4d_config_snapshot.json").stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "run_code_commit_sha": run_code_sha,
        "finalization_code_commit_sha": current_head,
        "branch": _git(root, "branch", "--show-current"),
        "config_sha256": _sha256(config_path),
        "protocol_sha256": _sha256(root / config["protocol_path"]),
        "config": config,
        "postprocessing_note": (
            "Training and all evaluations completed and saved CSVs; only final JSON serialization "
            "failed on NaN in a reused PPO metric. This step sanitized null metrics and rebuilt "
            "provenance from saved results; no model fit or backtest was rerun."
        ),
        "python_version": os.sys.version,
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scikit-learn", "joblib", "pyarrow")
        },
        "training_sample_count": int(len(train_examples.target)),
        "training_ticker_count": len(TRAIN_TICKERS),
        "training_ticker_year_age_strata": int(
            train_examples.metadata.groupby(["ticker", "year", "current_holding_age"]).ngroups
        ),
        "thresholds_selected_on_validation_training_tickers": thresholds,
        "models": model_hashes,
        "input_data_root": str(data_root),
        "input_file_metadata_fingerprints_recaptured": input_stat_before,
        "in_run_input_file_immutability_assertion": "passed before CSV outputs were written",
        "prepared_stock_sha256": {
            ticker: _prepared_fingerprint(stock) for ticker, stock in stocks.items()
        },
        "stock_coverage": {ticker: stock.metadata for ticker, stock in stocks.items()},
        "date_cutoff": "2025-12-31; prepared stock and VNINDEX rows are cutoff-filtered",
        "vnindex_regime_coverage": regimes["regime"].value_counts().to_dict(),
        "prediction_overview": overview,
        "policy_group_summaries": _summary_rows(policy),
        "random_control_percentiles": _random_percentiles(policy, random_paths),
        "random_control_matching": matching,
        "paired_uncertainty": bootstrap.to_dict(orient="records"),
        "h6": h6,
        "ppo_full_policy_reference": {
            "source": config["ppo_reference"]["phase4b_metrics"],
            "reference_file_sha256": reference_hashes["phase4b_stock_period_metrics"],
            "regime_source": config["ppo_reference"]["phase4b_regime_metrics"],
            "regime_file_sha256": reference_hashes["phase4b_regime_metrics"],
            "ticker_rows": int(len(ppo_reference)),
            "interpretation": "separate PPO-selected entries; descriptive only",
        },
        "phase4a_entry_diagnostic": {
            "source": str(phase4a_trade_path),
            "sha256": phase4a_trade_hash,
            "rows": int(len(ppo_diagnostic)),
            "summary": ppo_diagnostic_summary,
            "interpretation": "overlapping per-entry counterfactuals; not a portfolio",
        },
        "checkpoint_hashes_before_and_after": checkpoint_hashes,
        "checkpoint_integrity_check": "manifest hashes matched before and after evaluation",
        "reference_file_hashes": reference_hashes,
        "shared_data_modified": False,
        "ppo_retrained": False,
        "failed_attempts": [
            {
                "attempt": 1,
                "run_code_commit_sha": "0e60618b4e769da7883aea407e1cdb6c803d8a23",
                "cause": "constant prediction baseline requested an absent feature matrix",
                "result_files_written": False,
            },
            {
                "attempt": 2,
                "run_code_commit_sha": run_code_sha,
                "cause": (
                    "NaN from reused PPO reference blocked final JSON serialization after "
                    "CSV files were saved"
                ),
                "models_and_csvs_saved": True,
                "refit_or_reevaluation_during_finalization": False,
            },
        ],
    }
    (output_dir / "phase4d_metrics.json").write_text(
        json.dumps(_json_safe(summary), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument(
        "--run-code-sha",
        default="501f6c2cf41434a08083c8567cd6bb9d2f9b33a6",
        help="Commit SHA that performed training and evaluation.",
    )
    args = parser.parse_args()
    data_root = args.data_root or os.environ.get("STOCKS_DATA_ROOT")
    if not data_root:
        parser.error("Pass --data-root or set STOCKS_DATA_ROOT")
    summary = finalize_results(data_root=Path(data_root), run_code_sha=args.run_code_sha)
    print(
        json.dumps(
            {
                "experiment_id": summary["experiment_id"],
                "run_code_commit_sha": summary["run_code_commit_sha"],
                "finalization_code_commit_sha": summary["finalization_code_commit_sha"],
                "h6_verdict": summary["h6"]["verdict"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
