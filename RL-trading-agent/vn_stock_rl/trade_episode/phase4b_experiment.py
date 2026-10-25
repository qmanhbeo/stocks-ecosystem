"""Run the frozen-policy Phase 4B falsification experiments headlessly."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["MPLBACKEND"] = "Agg"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _name in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

ACTIVE_JOB: Any | None = None


def run_experiment(config_path: Path | None = None) -> dict[str, Any]:
    global ACTIVE_JOB
    import importlib.metadata

    import numpy as np
    import torch
    from sb3_contrib import MaskablePPO

    from vn_stock_rl.trade_episode.data import load_daily_stock_bars
    from vn_stock_rl.trade_episode.evaluation import evaluate_chronological_policy
    from vn_stock_rl.trade_episode.phase4a_data import (
        DATA_CUTOFF,
        HISTORICAL_LOOKBACK_START,
        PHASE4A_TICKERS,
        make_stock_env,
        prepare_stock,
    )
    from vn_stock_rl.trade_episode.phase4b_controls import (
        BuyAndHoldPolicy,
        MechanicalThreeDayPolicy,
        ValidationScheduleRandomPolicy,
        derive_control_seed,
    )
    from vn_stock_rl.trade_episode.phase4b_experiment_support import (
        EXPERIMENT_ID,
        METRICS,
        POLICY_SEEDS,
        REPRODUCTION_METRICS,
        SPLIT_LABELS,
        SPLITS,
        TRADE_FIELDS,
        VARIANTS,
        Phase4BJobMonitor,
        _file_stats,
        _group_mean,
        _h1_summary,
        _input_paths,
        _json_default,
        _match_groups,
        _metric_row,
        _read_csv,
        _read_duration_pairs,
        _read_json,
        _trade_rows,
        _write_csv,
        summarize_h5_regimes,
    )
    from vn_stock_rl.trade_episode.phase4b_provenance import (
        prepared_stock_fingerprint,
        sha256_file,
        verify_checkpoint_manifest,
    )
    from vn_stock_rl.trade_episode.phase4b_regimes import (
        build_causal_vnindex_regimes,
        summarize_calendar_year_path,
        summarize_regime_year_blocks,
    )

    worktree_root = Path(__file__).resolve().parents[3]
    config_path = config_path or (
        worktree_root
        / "RL-trading-agent"
        / "configs"
        / "trade_episode"
        / "phase4b_falsification.json"
    )
    config_path = config_path.resolve()
    config = _read_json(config_path)
    phase4a_dir = Path("/tmp/stock-rl-trade-episode-phase4a-20261025")
    protocol_dir = worktree_root / "RL-trading-agent" / "research" / "trade_episode" / "phase4b"
    manifest_path = protocol_dir / "checkpoint_manifest.json"
    reference_config_path = protocol_dir / "phase4a_effective_config.json"
    reference_metrics_path = protocol_dir / "phase4a_reference_metrics.csv"
    duration_pairs_path = protocol_dir / "phase4a_validation_duration_pairs.csv"

    effective_config = _read_json(reference_config_path)
    checkpoint_manifest = _read_json(manifest_path)
    phase4a_config_path = phase4a_dir / "phase4a_config.json"
    output_root = worktree_root / config["outputs"]["root"]
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 4B output directory: {output_root}")

    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError("Phase 4B run requires a clean worktree so its source SHA is exact")
    run_commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=worktree_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    run_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=worktree_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if run_branch != "exp/stock-rl-trade-episode":
        raise RuntimeError(f"Unexpected experiment branch: {run_branch}")

    monitor = Phase4BJobMonitor(worktree_root, run_commit_sha)
    ACTIVE_JOB = monitor
    monitor.phase("preflight", total=1)

    verify_checkpoint_manifest(checkpoint_manifest["checkpoints"])
    for expected_file in checkpoint_manifest["files"]:
        source_path = phase4a_dir / expected_file
        if sha256_file(source_path) != checkpoint_manifest["files"][expected_file]:
            raise ValueError(f"Phase 4A reference artifact changed: {source_path}")
    phase4a_config = _read_json(phase4a_config_path)
    if phase4a_config != effective_config:
        raise ValueError("Committed Phase 4A effective config differs from its source snapshot")
    if (
        sha256_file(reference_config_path)
        != checkpoint_manifest["phase4a_reference_artifacts"]["effective_config"]["sha256"]
    ):
        raise ValueError("Phase 4A effective config reference hash mismatch")
    if (
        sha256_file(reference_metrics_path)
        != checkpoint_manifest["phase4a_reference_artifacts"]["reference_metrics"]["sha256"]
    ):
        raise ValueError("Phase 4A reference metrics hash mismatch")
    if (
        sha256_file(duration_pairs_path)
        != checkpoint_manifest["validation_duration_pairs"]["sha256"]
    ):
        raise ValueError("Validation duration-pair calibration file hash mismatch")

    data_root = Path(config["data_root"]).expanduser().resolve()
    expected_tickers = tuple(config["train_tickers"] + config["unseen_tickers"])
    if set(expected_tickers) != set(PHASE4A_TICKERS):
        raise ValueError("Phase 4B ticker universe differs from the frozen Phase 4A universe")
    input_paths = _input_paths(data_root, tuple(sorted(expected_tickers)))
    input_stats_before = _file_stats(input_paths)
    if input_stats_before != phase4a_config["input_file_stats_before"]:
        raise RuntimeError(
            "Shared input metadata differs from the Phase 4A run; refusing comparison"
        )

    stocks = {}
    for ticker in expected_tickers:
        stocks[ticker] = prepare_stock(ticker, data_root=data_root)
    if any(stock.dates.max() > DATA_CUTOFF for stock in stocks.values()):
        raise RuntimeError("Post-cutoff rows entered prepared Phase 4B observations")
    fingerprints = {ticker: prepared_stock_fingerprint(stock) for ticker, stock in stocks.items()}
    index_bars = load_daily_stock_bars(
        "VNINDEX",
        data_root=data_root,
        start_date=HISTORICAL_LOOKBACK_START,
        end_date=DATA_CUTOFF,
    )
    regime_frame = build_causal_vnindex_regimes(
        index_bars,
        lookback_sessions=int(config["market_regimes"]["lookback_sessions"]),
        rising_threshold=float(config["market_regimes"]["rising_minimum_simple_return"]),
        falling_threshold=float(config["market_regimes"]["falling_maximum_simple_return"]),
        cutoff=DATA_CUTOFF,
    )
    if regime_frame["time"].max() > DATA_CUTOFF:
        raise RuntimeError("Post-cutoff index rows entered regime assignment")

    env_cfg = dict(phase4a_config["environment"])
    env_cfg.update({"annualization_intervals": 252, "annual_benchmark": 0.07})
    duration_pairs = _read_duration_pairs(duration_pairs_path)
    for variant in VARIANTS:
        for ticker in expected_tickers:
            if not duration_pairs.get((variant, ticker)):
                raise ValueError(f"No validation duration pairs for {variant} {ticker}")
    reference_metrics = {}
    for row in _read_csv(reference_metrics_path):
        key = (row["variant"], int(row["seed"]), row["ticker"], row["split"])
        reference_metrics[key] = row
    if len(reference_metrics) != 180:
        raise ValueError(
            f"Expected 180 Phase 4A reference metric rows, got {len(reference_metrics)}"
        )

    checkpoint_hashes_before = verify_checkpoint_manifest(checkpoint_manifest["checkpoints"])
    models = {}
    for record in checkpoint_manifest["checkpoints"]:
        models[(record["variant"], int(record["seed"]))] = MaskablePPO.load(
            record["path"], device="cpu"
        )
    torch.set_num_threads(1)
    monitor.record(
        "preflight_verified",
        {
            "ticker_count": len(stocks),
            "max_observation_date": max(stock.dates.max() for stock in stocks.values()).strftime(
                "%Y-%m-%d"
            ),
            "checkpoint_count": len(models),
            "post_cutoff_observations_used": False,
        },
    )

    run_started = time.perf_counter()
    stock_period_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    ppo_trade_rows: list[dict[str, Any]] = []
    control_simulation_rows: list[dict[str, Any]] = []
    ppo_periods: list[dict[str, Any]] = []
    control_rows_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    ppo_durations: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(
        lambda: {"holding": [], "waiting": []}
    )
    control_durations: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(
        lambda: {"holding": [], "waiting": []}
    )
    ppo_year_values: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    control_year_values: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    ppo_regime_values: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    control_regime_values: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    benchmark_regime_values: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    ppo_totals: dict[tuple[str, str], list[float]] = defaultdict(list)
    control_totals: dict[tuple[str, str], list[float]] = defaultdict(list)
    reproduction_diffs: list[dict[str, Any]] = []
    regime_coverage = []

    training_groups = set(config["train_tickers"])
    for split in SPLITS:
        start, end = (
            phase4a_config["splits"][split]["start"],
            phase4a_config["splits"][split]["end_max"],
        )
        years = range(int(start[:4]), int(end[:4]) + 1)
        for year in years:
            selected = regime_frame.loc[
                regime_frame["time"].dt.year.eq(year) & regime_frame["regime"].ne("warmup"),
                "regime",
            ]
            for label, count in selected.value_counts().items():
                regime_coverage.append(
                    {
                        "split": split,
                        "year": year,
                        "regime": str(label),
                        "index_sessions": int(count),
                    }
                )

    # Reproduce all Phase 4A train/validation/test paths from the frozen models.
    monitor.phase(
        "frozen_policy_replay",
        total=len(stocks) * len(SPLITS) * len(VARIANTS) * len(POLICY_SEEDS),
    )
    for ticker, stock in stocks.items():
        ticker_group = "training_universe" if ticker in training_groups else "unseen_ticker"
        for split in SPLITS:
            for variant in VARIANTS:
                include_alpha = variant == "market_plus_s1_c16"
                for seed in POLICY_SEEDS:
                    env = make_stock_env(
                        stock,
                        stock.split_masks[split],
                        env_cfg=env_cfg,
                        include_alpha=include_alpha,
                    )
                    result = evaluate_chronological_policy(
                        models[(variant, seed)], env, seed=seed, deterministic=True
                    )
                    if any(trade["holding_duration"] < 3 for trade in result["trades"]):
                        raise RuntimeError(f"{ticker}: frozen PPO produced a sub-minimum trade")
                    row = _metric_row(
                        result,
                        policy="MaskablePPO",
                        variant=variant,
                        seed=seed,
                        split=split,
                        ticker=ticker,
                        ticker_group=ticker_group,
                    )
                    stock_period_rows.append(row)
                    ppo_periods.append(row)
                    monitor.record("ppo_path", row, details={"trades": result["trades"]})
                    key = (variant, ticker, split)
                    for trade in result["trades"]:
                        ppo_durations[key]["holding"].append(int(trade["holding_duration"]))
                        ppo_durations[key]["waiting"].append(int(trade["waiting_duration"]))
                    ppo_trade_rows.extend(
                        _trade_rows(
                            result["trades"],
                            variant=variant,
                            seed=seed,
                            split=split,
                            ticker=ticker,
                            ticker_group=ticker_group,
                            stock_dates=stock.dates,
                            regime_frame=regime_frame,
                        )
                    )
                    for block in summarize_calendar_year_path(result["daily_path"]):
                        ppo_year_values[(variant, ticker, block["year"])].append(
                            float(block["calendar_return"])
                        )
                    for block in summarize_regime_year_blocks(result["daily_path"], regime_frame):
                        regime_rows.append(
                            {
                                "policy": "MaskablePPO",
                                "variant": variant,
                                "seed": seed,
                                "ticker": ticker,
                                "ticker_group": ticker_group,
                                "split": split,
                                **block,
                            }
                        )
                        if block["interval_count"] >= 30:
                            ppo_regime_values[
                                (variant, ticker, block["year"], block["regime"])
                            ].append(float(block["conditional_compounded_return"]))
                    if split in ("validation", "test"):
                        reference = reference_metrics[(variant, seed, ticker, split)]
                        for field in REPRODUCTION_METRICS:
                            expected = reference.get(field)
                            actual = result.get(field)
                            if expected in (None, "") and actual is None:
                                continue
                            difference = abs(float(expected) - float(actual))
                            reproduction_diffs.append(
                                {
                                    "ticker": ticker,
                                    "variant": variant,
                                    "seed": seed,
                                    "split": split,
                                    "metric": field,
                                    "absolute_difference": difference,
                                }
                            )
                            if not np.isclose(float(expected), float(actual), rtol=1e-8, atol=1e-8):
                                raise RuntimeError(
                                    f"Frozen checkpoint reproduction mismatch: {ticker} {variant} "
                                    f"seed={seed} split={split} metric={field} "
                                    f"reference={expected} actual={actual}"
                                )
                    for total in (float(result["total_calendar_return"]),):
                        if split == "test":
                            ppo_totals[(variant, ticker)].append(total)
                    env.close()

    # Baselines use the same ticker/date slices, initial capital, and next-open fills.
    monitor.phase("benchmark_replay", total=len(stocks) * len(SPLITS) * 2)
    for ticker, stock in stocks.items():
        ticker_group = "training_universe" if ticker in training_groups else "unseen_ticker"
        for split in SPLITS:
            for policy_name, policy in (
                ("mechanical_immediate_entry_3day_exit", MechanicalThreeDayPolicy()),
                ("buy_and_hold", BuyAndHoldPolicy()),
            ):
                env = make_stock_env(
                    stock, stock.split_masks[split], env_cfg=env_cfg, include_alpha=False
                )
                result = evaluate_chronological_policy(policy, env, seed=1208, deterministic=True)
                row = _metric_row(
                    result,
                    policy=policy_name,
                    variant="benchmark",
                    seed=None,
                    split=split,
                    ticker=ticker,
                    ticker_group=ticker_group,
                )
                stock_period_rows.append(row)
                monitor.record("benchmark_path", row)
                for block in summarize_regime_year_blocks(result["daily_path"], regime_frame):
                    regime_rows.append(
                        {
                            "policy": policy_name,
                            "variant": "benchmark",
                            "seed": None,
                            "ticker": ticker,
                            "ticker_group": ticker_group,
                            "split": split,
                            **block,
                        }
                    )
                    if block["interval_count"] >= 30:
                        benchmark_regime_values[
                            (policy_name, ticker, block["year"], block["regime"])
                        ].append(float(block["conditional_compounded_return"]))
                env.close()

    # Validation schedules are sampled independently for each Monte Carlo path.
    random_seed_start = int(config["controls"]["master_seed_start"])
    random_replicates = int(config["controls"]["replicates_per_ticker_variant_partition"])
    monitor.phase(
        "randomized_control_replay",
        total=len(stocks) * len(VARIANTS) * len(SPLITS) * random_replicates,
    )
    env_horizons = {
        "max_wait_steps": int(env_cfg["max_wait_steps"]),
        "max_holding_intervals": int(env_cfg["max_holding_intervals"]),
        "max_episode_steps": int(env_cfg["max_episode_steps"]),
    }
    for ticker, stock in stocks.items():
        ticker_group = "training_universe" if ticker in training_groups else "unseen_ticker"
        for variant in VARIANTS:
            pairs = duration_pairs[(variant, ticker)]
            for split in SPLITS:
                key = (variant, ticker, split)
                for replicate in range(random_replicates):
                    master_seed = random_seed_start + replicate
                    mc_seed = derive_control_seed(master_seed, ticker, variant, split)
                    env = make_stock_env(
                        stock,
                        stock.split_masks[split],
                        env_cfg=env_cfg,
                        include_alpha=(variant == "market_plus_s1_c16"),
                    )
                    policy = ValidationScheduleRandomPolicy(
                        pairs,
                        seed=mc_seed,
                        **env_horizons,
                    )
                    result = evaluate_chronological_policy(
                        policy, env, seed=mc_seed, deterministic=True
                    )
                    if any(trade["holding_duration"] < 3 for trade in result["trades"]):
                        raise RuntimeError(f"{ticker}: randomized control broke the minimum hold")
                    row = _metric_row(
                        result,
                        policy="validation_schedule_random_control",
                        variant=variant,
                        seed=mc_seed,
                        split=split,
                        ticker=ticker,
                        ticker_group=ticker_group,
                    )
                    row["master_seed"] = master_seed
                    year_blocks = summarize_calendar_year_path(result["daily_path"])
                    regime_blocks = summarize_regime_year_blocks(result["daily_path"], regime_frame)
                    row["calendar_year_blocks_json"] = json.dumps(
                        year_blocks, separators=(",", ":"), allow_nan=False
                    )
                    row["causal_regime_blocks_json"] = json.dumps(
                        regime_blocks, separators=(",", ":"), allow_nan=False
                    )
                    control_simulation_rows.append(row)
                    monitor.record("randomized_control_path", row)
                    control_rows_by_key[key].append(row)
                    for trade in result["trades"]:
                        control_durations[key]["holding"].append(int(trade["holding_duration"]))
                        control_durations[key]["waiting"].append(int(trade["waiting_duration"]))
                    for block in year_blocks:
                        control_year_values[(variant, ticker, block["year"])].append(
                            float(block["calendar_return"])
                        )
                    for block in regime_blocks:
                        if block["interval_count"] >= 30:
                            control_regime_values[
                                (variant, ticker, block["year"], block["regime"])
                            ].append(float(block["conditional_compounded_return"]))
                    if split == "test":
                        control_totals[(variant, ticker)].append(
                            float(result["total_calendar_return"])
                        )
                    env.close()

    thresholds = config["controls"]["match_thresholds"]
    control_summaries = []
    for (variant, ticker, split), rows in sorted(control_rows_by_key.items()):
        summary = {
            "policy": "validation_schedule_random_control_mean",
            "variant": variant,
            "seed": None,
            "split": split,
            "ticker": ticker,
            "ticker_group": "training_universe" if ticker in training_groups else "unseen_ticker",
            "simulation_count": len(rows),
        }
        for field in METRICS:
            summary[field] = _group_mean(rows, field)
        for field in (
            "chronological_portfolio_cagr",
            "total_calendar_return",
            "exposure_percentage",
            "average_holding_duration",
            "average_waiting_duration",
        ):
            values = [float(row[field]) for row in rows if row.get(field) is not None]
            q10, q50, q90 = np.quantile(values, [0.1, 0.5, 0.9])
            summary[f"{field}_p10"] = float(q10)
            summary[f"{field}_p50"] = float(q50)
            summary[f"{field}_p90"] = float(q90)
        stock_period_rows.append(summary)
        control_summaries.append(summary)

    match_group_rows, match_by_key = _match_groups(
        ppo_periods,
        control_summaries,
        ppo_durations,
        control_durations,
        thresholds=thresholds,
    )
    match_rows = [
        {
            "variant": variant,
            "ticker": ticker,
            "split": split,
            "ticker_group": "training_universe" if ticker in training_groups else "unseen_ticker",
            **quality,
        }
        for (variant, ticker, split), quality in sorted(match_by_key.items())
    ]
    group_metrics = []
    for group in ("training_universe", "unseen_ticker"):
        for variant in VARIANTS:
            for split in SPLITS:
                ppo_selected = [
                    row
                    for row in ppo_periods
                    if row["ticker_group"] == group
                    and row["variant"] == variant
                    and row["split"] == split
                ]
                controls_selected = [
                    row
                    for row in control_summaries
                    if row["ticker_group"] == group
                    and row["variant"] == variant
                    and row["split"] == split
                ]
                if not ppo_selected:
                    continue
                summary = {
                    "ticker_group": group,
                    "variant": variant,
                    "split": split,
                    "aggregation": "unweighted independent stock backtests; not a portfolio",
                    "ppo_path_count": len(ppo_selected),
                    "stock_count": len({row["ticker"] for row in ppo_selected}),
                    "control_stock_count": len(controls_selected),
                }
                for field in METRICS:
                    summary[f"ppo_{field}_mean"] = _group_mean(ppo_selected, field)
                    summary[f"control_{field}_mean"] = _group_mean(controls_selected, field)
                group_metrics.append(summary)

    h1 = _h1_summary(
        ppo_year_values=ppo_year_values,
        control_year_values=control_year_values,
        ppo_totals=ppo_totals,
        control_totals=control_totals,
        match_groups=match_group_rows,
        bootstrap_replicates=int(config["uncertainty"]["replicates"]),
        bootstrap_seed=int(config["uncertainty"]["seed"]),
    )

    h5_details, h5_combined = summarize_h5_regimes(
        ppo_regime_values=ppo_regime_values,
        control_regime_values=control_regime_values,
        benchmark_regime_values=benchmark_regime_values,
        match_group_rows=match_group_rows,
        config=config,
    )

    # Aggregate per-simulation causal regime blocks without losing Monte Carlo variation.
    control_regime_index: dict[tuple[str, str, str, int, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for simulation in control_simulation_rows:
        for block in json.loads(simulation["causal_regime_blocks_json"]):
            if block["interval_count"] < 30:
                continue
            key = (
                simulation["variant"],
                simulation["ticker"],
                simulation["split"],
                int(block["year"]),
                block["regime"],
            )
            control_regime_index[key].append(block)
    for key, rows in sorted(control_regime_index.items()):
        variant, ticker, split, year, regime = key
        returns = [float(row["conditional_compounded_return"]) for row in rows]
        exposures = [float(row["exposure_percentage"]) for row in rows]
        q10, q50, q90 = np.quantile(returns, [0.1, 0.5, 0.9])
        regime_rows.append(
            {
                "policy": "validation_schedule_random_control_mean",
                "variant": variant,
                "seed": None,
                "ticker": ticker,
                "ticker_group": "training_universe"
                if ticker in training_groups
                else "unseen_ticker",
                "split": split,
                "year": year,
                "regime": regime,
                "interval_count": int(np.mean([row["interval_count"] for row in rows])),
                "simulation_count": len(rows),
                "conditional_compounded_return_mean": float(np.mean(returns)),
                "conditional_compounded_return_p10": float(q10),
                "conditional_compounded_return_p50": float(q50),
                "conditional_compounded_return_p90": float(q90),
                "exposure_percentage_mean": float(np.mean(exposures)),
            }
        )

    checkpoint_hashes_after = verify_checkpoint_manifest(checkpoint_manifest["checkpoints"])
    input_stats_after = _file_stats(input_paths)
    if checkpoint_hashes_before != checkpoint_hashes_after:
        raise RuntimeError("A frozen Phase 4A checkpoint changed during evaluation")
    if input_stats_before != input_stats_after:
        raise RuntimeError("A shared dataset file changed during the experiment")
    runtime = time.perf_counter() - run_started
    regime_counts = {
        split: {
            label: sum(
                row["index_sessions"]
                for row in regime_coverage
                if row["split"] == split and row["regime"] == label
            )
            for label in ("rising", "falling", "sideways")
        }
        for split in SPLITS
    }

    metrics_payload = {
        "experiment_id": EXPERIMENT_ID,
        "execution_date_utc": datetime.now(timezone.utc).isoformat(),
        "run_code_commit_sha": run_commit_sha,
        "run_code_branch": run_branch,
        "phase4a_training_git_sha": checkpoint_manifest["phase4a_generating_git_sha"],
        "phase4a_provenance_note": checkpoint_manifest["phase4a_sha_note"],
        "config_sha256": sha256_file(config_path),
        "protocol_sha256": sha256_file(protocol_dir / "protocol.md"),
        "checkpoint_manifest_sha256": sha256_file(manifest_path),
        "job_status_path": str(monitor.status_path),
        "incremental_progress_trace_path": str(monitor.trace_path),
        "python": __import__("sys").version,
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in (
                "numpy",
                "pandas",
                "torch",
                "stable-baselines3",
                "sb3-contrib",
                "gymnasium",
            )
        },
        "runtime_seconds": runtime,
        "retraining_performed": False,
        "training_timesteps": 0,
        "policy_eval_path_count": len(ppo_periods),
        "randomized_control_path_count": len(control_simulation_rows),
        "benchmark_path_count": len(stock_period_rows) - len(ppo_periods) - len(control_summaries),
        "split_names": SPLIT_LABELS,
        "checkpoint_hashes_before": checkpoint_hashes_before,
        "checkpoint_hashes_after": checkpoint_hashes_after,
        "shared_data_file_stats_before": input_stats_before,
        "shared_data_file_stats_after": input_stats_after,
        "shared_data_unchanged": input_stats_before == input_stats_after,
        "prepared_stock_input_sha256": fingerprints,
        "max_observation_date_used": max(stock.dates.max() for stock in stocks.values()).strftime(
            "%Y-%m-%d"
        ),
        "cutoff": str(DATA_CUTOFF.date()),
        "post_cutoff_rows_used": False,
        "ticker_observation_encoding": False,
        "price_adjustment_basis": "user-confirmed dividend-adjusted assumption",
        "phase4a_reproduction": {
            "reference_path_count": len(reference_metrics),
            "metric_comparisons": len(reproduction_diffs),
            "metric_comparisons_skipped_as_null": (
                len(reference_metrics) * len(REPRODUCTION_METRICS) - len(reproduction_diffs)
            ),
            "max_absolute_metric_difference": max(
                (row["absolute_difference"] for row in reproduction_diffs), default=0.0
            ),
            "matched_reference": True,
        },
        "market_regime_rule": {
            "index": "VNINDEX",
            "trailing_sessions": 126,
            "rising": ">=+10% simple return",
            "falling": "<=-10% simple return",
            "otherwise": "sideways",
            "labels_available_through": "decision close; assigned to next interval",
            "classified_index_sessions_by_split": regime_counts,
            "classified_index_sessions_by_year": regime_coverage,
        },
        "control_match_thresholds": thresholds,
        "control_match_quality": match_rows,
        "control_match_group_quality": match_group_rows,
        "main_period_group_metrics": group_metrics,
        "H1_exposure_shortcut": h1,
        "H5_bull_market_dependence": {
            "by_variant": h5_details,
            "combined_classification": h5_combined,
            "primary_years": "2020-2025; training years are descriptive only",
        },
        "limitations": [
            (
                "The Phase 4A checkpoint-generation Git SHA is unavailable because it predates the "
                "first commit; checkpoint hashes and effective config are preserved."
            ),
            (
                "2020-2022 was previously used validation and also calibrates randomized "
                "duration pairs."
            ),
            "2023-2025 is exploratory and contaminated by Alpha feature selection.",
            "Per-stock averages are not a multi-stock portfolio; no allocation rule is evaluated.",
            (
                "Randomized controls match completed-trade validation wait/hold pairs, not "
                "PPO's no-trade episode behavior."
            ),
        ],
    }

    monitor.phase("finalize_outputs", total=1)
    output_root.mkdir(parents=True, exist_ok=False)
    _write_csv(output_root / "phase4b_stock_period_metrics.csv", stock_period_rows)
    _write_csv(output_root / "phase4b_regime_metrics.csv", regime_rows)
    _write_csv(output_root / "phase4b_control_simulations.csv", control_simulation_rows)
    _write_csv(
        output_root / "phase4b_trades.csv",
        ppo_trade_rows,
        fieldnames=TRADE_FIELDS,
    )
    (output_root / "phase4b_metrics.json").write_text(
        json.dumps(metrics_payload, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    final_outputs = [
        str(output_root / name)
        for name in (
            "phase4b_stock_period_metrics.csv",
            "phase4b_regime_metrics.csv",
            "phase4b_control_simulations.csv",
            "phase4b_trades.csv",
            "phase4b_metrics.json",
        )
    ]
    monitor.record("final_outputs_written", {"paths": final_outputs})
    monitor.complete(final_outputs)
    return metrics_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    try:
        result = run_experiment(args.config)
    except BaseException as error:
        if ACTIVE_JOB is not None:
            ACTIVE_JOB.fail(error)
        raise
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "run_code_commit_sha": result["run_code_commit_sha"],
                "runtime_seconds": result["runtime_seconds"],
                "ppo_paths": result["policy_eval_path_count"],
                "random_control_paths": result["randomized_control_path_count"],
                "H1": result["H1_exposure_shortcut"]["combined_classification"],
                "H5": result["H5_bull_market_dependence"]["combined_classification"],
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
