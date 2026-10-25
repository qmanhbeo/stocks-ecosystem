"""Fixed-entry policy replay, PPO references, and preregistered H6 inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def run_evaluation(
    *,
    config: dict[str, Any],
    stocks: dict[str, Any],
    models: dict[str, Any],
    thresholds: dict[str, float],
    validation_duration_pools: dict[str, tuple[int, ...]],
    state_config: dict[str, Any],
    regime_by_date: dict[str, str],
    phase4b_metrics_path: Path,
    phase4b_regime_path: Path,
    phase4a_trade_path: Path,
) -> dict[str, Any]:
    from vn_stock_rl.trade_episode.phase4a_data import (
        PHASE4A_TICKERS,
        UNSEEN_TICKERS,
    )
    from vn_stock_rl.trade_episode.phase4d_experiment_support import (
        _copy_trade_rows,
        _group_mean_policy,
        _group_random_rows,
        _mean,
        _policy_metric_row,
        _year_regime_rows,
    )
    from vn_stock_rl.trade_episode.phase4d_policy import (
        make_entry_schedule,
        simulate_fixed_entry_policy,
    )
    from vn_stock_rl.trade_episode.phase4d_statistics import (
        annualized_year_blocks,
        hierarchical_paired_bootstrap,
        policy_group_summary,
    )

    policy_config = config["policy"]
    max_holding = int(policy_config["maximum_holding_intervals"])
    max_model_age = int(policy_config["model_last_decision_holding_age"])
    entry_stride = int(policy_config["entry_schedule_stride_trading_rows"])
    main_model_ids = [
        "ridge_market",
        "ridge_market_alpha",
        "extra_trees_market",
        "extra_trees_market_alpha",
    ]
    policy_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    year_regime_rows: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    block_returns: dict[tuple[str, str, int], float] = {}
    entry_indices_by_policy_ticker: dict[tuple[str, str], set[int]] = {}
    test_entry_schedules: dict[str, list[int]] = {}

    def record_result(result, policy, *, model_id=None, threshold=None):
        group = "unseen_ticker" if result["ticker"] in UNSEEN_TICKERS else "training_universe"
        result["policy"] = policy
        policy_rows.append(
            _policy_metric_row(
                result,
                policy=policy,
                ticker_group=group,
                model_id=model_id,
                threshold=threshold,
            )
        )
        trade_rows.extend(_copy_trade_rows(result["trades"], ticker_group=group, model_id=model_id))
        year_regime_rows.extend(_year_regime_rows(result, ticker_group=group, model_id=model_id))
        for year, value in annualized_year_blocks(result).items():
            block_returns[(policy, result["ticker"], year)] = value
        entry_indices_by_policy_ticker[(policy, result["ticker"])] = set(
            result["executed_entry_decision_indices"]
        )

    # Primary fixed-entry test: all exit strategies receive the same prespecified slots.
    for ticker, stock in stocks.items():
        schedule = make_entry_schedule(
            stock,
            split="exploratory",
            stride=entry_stride,
            maximum_holding_intervals=max_holding,
        )
        test_entry_schedules[ticker] = list(schedule["decision_indices"])
        for fixed_duration in (3, 10, 20):
            policy = f"mechanical_{fixed_duration}"
            result = simulate_fixed_entry_policy(
                stock,
                split="exploratory",
                entry_decision_indices=schedule["decision_indices"],
                policy_id=policy,
                policy_kind="fixed",
                phase4a_state_config=state_config,
                maximum_holding_intervals=max_holding,
                model_last_decision_age=max_model_age,
                regime_by_date=regime_by_date,
                fixed_duration=fixed_duration,
            )
            record_result(result, policy)
        for model_id in main_model_ids:
            policy = f"supervised:{model_id}"
            result = simulate_fixed_entry_policy(
                stock,
                split="exploratory",
                entry_decision_indices=schedule["decision_indices"],
                policy_id=policy,
                policy_kind="supervised",
                phase4a_state_config=state_config,
                maximum_holding_intervals=max_holding,
                model_last_decision_age=max_model_age,
                regime_by_date=regime_by_date,
                model=models[model_id],
                threshold=thresholds[model_id],
            )
            record_result(result, policy, model_id=model_id, threshold=thresholds[model_id])

    control_cfg = config["randomized_exit_control"]
    random_seed_start = int(control_cfg["seed_start"])
    random_replicates = int(control_cfg["replicates"])
    for ticker, stock in stocks.items():
        schedule = test_entry_schedules[ticker]
        group = "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"
        for model_id in main_model_ids:
            candidate_policy = f"supervised:{model_id}"
            candidate_entries = entry_indices_by_policy_ticker[(candidate_policy, ticker)]
            for replicate in range(random_replicates):
                seed = random_seed_start + replicate
                policy = f"random:{model_id}:{seed}"
                result = simulate_fixed_entry_policy(
                    stock,
                    split="exploratory",
                    entry_decision_indices=schedule,
                    policy_id=policy,
                    policy_kind="random",
                    phase4a_state_config=state_config,
                    maximum_holding_intervals=max_holding,
                    model_last_decision_age=max_model_age,
                    regime_by_date=regime_by_date,
                    duration_pool=validation_duration_pools[model_id],
                    random_seed=seed,
                )
                row = _policy_metric_row(
                    result, policy=policy, ticker_group=group, model_id=model_id
                )
                overlap = len(candidate_entries & set(result["executed_entry_decision_indices"]))
                row["random_seed"] = seed
                row["entry_overlap_percentage"] = (
                    100.0 * overlap / len(schedule) if schedule else None
                )
                row["mean_validation_duration_pool"] = float(
                    np.mean(validation_duration_pools[model_id])
                )
                random_rows.append(row)
                trade_rows.extend(
                    _copy_trade_rows(result["trades"], ticker_group=group, model_id=model_id)
                )
                year_regime_rows.extend(
                    _year_regime_rows(result, ticker_group=group, model_id=model_id)
                )
                for year, value in annualized_year_blocks(result).items():
                    block_returns[(policy, ticker, year)] = value

    # Collapse Monte Carlo paths to one per-stock mean for table summaries.
    policy_rows.extend(
        row
        for model_id in main_model_ids
        for group in ("training_universe", "unseen_ticker")
        for row in _group_random_rows(random_rows, model_id, group)
    )

    # Preserve the historical full-policy PPO reference separately: it has different entries.
    ppo_source = pd.read_csv(phase4b_metrics_path)
    ppo_source = ppo_source.loc[
        (ppo_source["policy"] == "MaskablePPO") & (ppo_source["split"] == "test")
    ].copy()
    ppo_reference_rows = []
    for (variant, ticker, ticker_group), group in ppo_source.groupby(
        ["variant", "ticker", "ticker_group"], sort=True
    ):
        item = {
            "policy": "frozen_PPO_full_policy",
            "variant": variant,
            "model_id": None,
            "ticker": ticker,
            "ticker_group": ticker_group,
            "split": "exploratory",
            "source": str(config["ppo_reference"]["phase4b_metrics"]),
            "entry_comparison": "different PPO-selected entries; descriptive only",
        }
        for field in (
            "chronological_portfolio_cagr",
            "total_calendar_return",
            "maximum_drawdown",
            "exposure_percentage",
            "number_of_trades",
            "win_rate",
            "mean_terminal_rl_reward",
            "average_holding_duration",
            "average_waiting_duration",
        ):
            source_field = field
            if field == "average_holding_duration":
                source_field = "average_holding_duration"
            if source_field in group:
                item[field] = float(group[source_field].mean())
        item["seed_count"] = int(group["seed"].nunique())
        ppo_reference_rows.append(item)
    policy_rows.extend(ppo_reference_rows)
    ppo_regime_source = pd.read_csv(phase4b_regime_path)
    ppo_regime_source = ppo_regime_source.loc[
        (ppo_regime_source["policy"] == "MaskablePPO") & (ppo_regime_source["split"] == "test")
    ].copy()
    if int(ppo_regime_source["year"].max()) > 2025:
        raise RuntimeError("Saved PPO regime reference contains a year beyond the permitted cutoff")
    for (variant, ticker, ticker_group, year, regime), group in ppo_regime_source.groupby(
        ["variant", "ticker", "ticker_group", "year", "regime"], sort=True
    ):
        year_regime_rows.append(
            {
                "policy": "frozen_PPO_full_policy",
                "model_id": None,
                "variant": variant,
                "ticker": ticker,
                "ticker_group": ticker_group,
                "split": "exploratory",
                "year": int(year),
                "regime": regime,
                "trading_intervals": int(group["interval_count"].mean()),
                "compounded_return": float(group["conditional_compounded_return"].mean()),
                "exposure_percentage": float(group["exposure_percentage"].mean()),
                "source": config["ppo_reference"]["phase4b_regime_metrics"],
                "entry_comparison": "different PPO-selected entries; descriptive only",
            }
        )

    # Secondary counterfactual diagnostic: identical saved PPO entries, per trade only.
    diagnostic_cfg = config["ppo_reference"]["entry_conditioned_diagnostic"]
    phase4a_trades = pd.read_csv(diagnostic_cfg["phase4a_trade_log"])
    phase4a_trades = phase4a_trades.loc[
        (phase4a_trades["policy"] == "MaskablePPO")
        & (phase4a_trades["seed"] == int(diagnostic_cfg["seed"]))
        & (phase4a_trades["split"] == "test")
    ].copy()
    ppo_entry_diagnostic_rows: list[dict[str, Any]] = []
    for row in phase4a_trades.itertuples(index=False):
        stock = stocks.get(str(row.ticker))
        if stock is None:
            continue
        fill_date = pd.Timestamp(row.entry_date).normalize()
        fill_match = int(stock.dates.searchsorted(fill_date))
        if (
            fill_match >= len(stock.dates)
            or pd.Timestamp(stock.dates[fill_match]).normalize() != fill_date
        ):
            continue
        decision = fill_match - 1
        selected = np.flatnonzero(stock.split_masks["test"])
        if (
            not len(selected)
            or decision < int(selected[0])
            or decision + 1 + max_holding > int(selected[-1])
        ):
            continue
        if not stock.can_buy[decision]:
            continue
        variant = str(row.variant)
        for model_id in main_model_ids:
            if ("alpha" in model_id) != (variant == "market_plus_s1_c16"):
                continue
            policy = f"ppo_entry_diag_supervised:{model_id}"
            result = simulate_fixed_entry_policy(
                stock,
                split="exploratory",
                entry_decision_indices=[decision],
                policy_id=policy,
                policy_kind="supervised",
                phase4a_state_config=state_config,
                maximum_holding_intervals=max_holding,
                model_last_decision_age=max_model_age,
                regime_by_date=regime_by_date,
                model=models[model_id],
                threshold=thresholds[model_id],
            )
            if result["executed_entry_decision_indices"] != [decision]:
                raise RuntimeError("PPO-entry diagnostic changed the prespecified entry date")
            trade = next((item for item in result["trades"] if not item["incomplete"]), None)
            if trade is None:
                continue
            ppo_entry_diagnostic_rows.append(
                {
                    "ppo_variant": variant,
                    "ppo_seed": int(row.seed),
                    "ticker": str(row.ticker),
                    "ticker_group": str(row.ticker_group),
                    "ppo_entry_fill_date": str(fill_date.date()),
                    "ppo_original_exit_date": str(pd.Timestamp(row.exit_date).date())
                    if pd.notna(row.exit_date)
                    else None,
                    "ppo_original_holding_duration": int(row.holding_duration),
                    "exit_controller": policy,
                    "threshold": thresholds[model_id],
                    "new_exit_date": trade["exit_date"],
                    "new_holding_duration": trade["holding_duration"],
                    "raw_trade_return": trade["raw_trade_return"],
                    "terminal_rl_reward": trade["terminal_rl_reward"],
                    "overlapping_counterfactual": True,
                    "portfolio_compounding": False,
                }
            )
        for duration in (3, 10, 20):
            policy = f"ppo_entry_diag_mechanical_{duration}"
            result = simulate_fixed_entry_policy(
                stock,
                split="exploratory",
                entry_decision_indices=[decision],
                policy_id=policy,
                policy_kind="fixed",
                phase4a_state_config=state_config,
                maximum_holding_intervals=max_holding,
                model_last_decision_age=max_model_age,
                regime_by_date=regime_by_date,
                fixed_duration=duration,
            )
            trade = next((item for item in result["trades"] if not item["incomplete"]), None)
            if trade is not None:
                ppo_entry_diagnostic_rows.append(
                    {
                        "ppo_variant": variant,
                        "ppo_seed": int(row.seed),
                        "ticker": str(row.ticker),
                        "ticker_group": str(row.ticker_group),
                        "ppo_entry_fill_date": str(fill_date.date()),
                        "ppo_original_exit_date": str(pd.Timestamp(row.exit_date).date())
                        if pd.notna(row.exit_date)
                        else None,
                        "ppo_original_holding_duration": int(row.holding_duration),
                        "exit_controller": policy,
                        "threshold": None,
                        "new_exit_date": trade["exit_date"],
                        "new_holding_duration": trade["holding_duration"],
                        "raw_trade_return": trade["raw_trade_return"],
                        "terminal_rl_reward": trade["terminal_rl_reward"],
                        "overlapping_counterfactual": True,
                        "portfolio_compounding": False,
                    }
                )

    # Threshold, matching, block uncertainty, and preregistered H6 decision.
    all_metric_summaries: list[dict[str, Any]] = []
    group_names = ("training_universe", "unseen_ticker")
    for row in policy_rows:
        if row.get("policy") == "frozen_PPO_full_policy":
            all_metric_summaries.append(row)
    for policy in ["mechanical_3", "mechanical_10", "mechanical_20"] + [
        f"supervised:{model_id}" for model_id in main_model_ids
    ]:
        for group in group_names:
            all_metric_summaries.append(
                policy_group_summary(policy_rows, policy=policy, ticker_group=group)
            )

    random_group_summaries = {
        model_id: {
            group: _group_mean_policy(
                _group_random_rows(random_rows, model_id, group),
                f"random_mean:{model_id}",
                group,
            )
            for group in group_names
        }
        for model_id in main_model_ids
    }
    for model_id in main_model_ids:
        for group in group_names:
            all_metric_summaries.append(random_group_summaries[model_id][group])

    overlap_summary: dict[str, dict[str, Any]] = {}
    match_summary: dict[str, dict[str, Any]] = {}
    bootstrap_rows: list[dict[str, Any]] = []
    support_checks: dict[str, Any] = {}
    control_ids = ["mechanical_3", "mechanical_10", "mechanical_20"]
    for model_id in main_model_ids:
        candidate_policy = f"supervised:{model_id}"
        comparisons = {}
        overlap_summary[model_id] = {}
        match_summary[model_id] = {}
        for group in group_names:
            selected_tickers = [
                ticker
                for ticker in PHASE4A_TICKERS
                if ("unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe") == group
            ]
            overlap_values: list[float] = []
            duration_differences: list[float] = []
            exposure_differences: list[float] = []
            for ticker in selected_tickers:
                expected = set(test_entry_schedules[ticker])
                candidate_entries = entry_indices_by_policy_ticker[(candidate_policy, ticker)]
                for control in control_ids:
                    control_entries = entry_indices_by_policy_ticker[(control, ticker)]
                    overlap_values.append(
                        100.0 * len(candidate_entries & control_entries) / len(expected)
                        if expected
                        else 100.0
                    )
                ticker_random = [
                    row
                    for row in random_rows
                    if row["model_id"] == model_id and row["ticker"] == ticker
                ]
                overlap_values.extend(
                    float(row["entry_overlap_percentage"])
                    for row in ticker_random
                    if row.get("entry_overlap_percentage") is not None
                )
                candidate_metric = next(
                    row
                    for row in policy_rows
                    if row.get("policy") == candidate_policy and row.get("ticker") == ticker
                )
                random_by_ticker = _mean(
                    row.get("chronological_portfolio_cagr") for row in ticker_random
                )
                random_holding = _mean(row.get("mean_holding_duration") for row in ticker_random)
                random_exposure = _mean(row.get("exposure_percentage") for row in ticker_random)
                if (
                    candidate_metric.get("mean_holding_duration") is not None
                    and random_holding is not None
                ):
                    duration_differences.append(
                        float(random_holding - candidate_metric["mean_holding_duration"])
                    )
                if (
                    candidate_metric.get("exposure_percentage") is not None
                    and random_exposure is not None
                ):
                    exposure_differences.append(
                        float(random_exposure - candidate_metric["exposure_percentage"])
                    )
                if random_by_ticker is None:
                    continue
            group_overlap = _mean(overlap_values)
            mean_holding_diff = _mean(duration_differences)
            mean_exposure_diff = _mean(exposure_differences)
            overlap_summary[model_id][group] = {
                "mean_common_entry_overlap_percentage": group_overlap,
                "minimum_required_percentage": float(
                    policy_config["common_entry_coverage_minimum"] * 100.0
                ),
            }
            match_summary[model_id][group] = {
                "mean_random_minus_supervised_holding_intervals": mean_holding_diff,
                "mean_random_minus_supervised_exposure_percentage_points": mean_exposure_diff,
                "holding_match_tolerance_intervals": int(
                    control_cfg["duration_match_tolerance_sessions"]
                ),
                "exposure_match_tolerance_percentage_points": float(
                    control_cfg["exposure_match_tolerance_percentage_points"]
                ),
                "adequate_mean_match": bool(
                    mean_holding_diff is not None
                    and mean_exposure_diff is not None
                    and abs(mean_holding_diff) <= control_cfg["duration_match_tolerance_sessions"]
                    and abs(mean_exposure_diff)
                    <= control_cfg["exposure_match_tolerance_percentage_points"]
                ),
            }
            for control in control_ids:
                comparator = _group_mean_policy(policy_rows, control, group)
                candidate = _group_mean_policy(policy_rows, candidate_policy, group)
                point_diff = (
                    None
                    if candidate["chronological_portfolio_cagr"] is None
                    or comparator["chronological_portfolio_cagr"] is None
                    else candidate["chronological_portfolio_cagr"]
                    - comparator["chronological_portfolio_cagr"]
                )
                bootstrap = hierarchical_paired_bootstrap(
                    candidate_policy=candidate_policy,
                    comparator_policy=control,
                    ticker_group=group,
                    block_returns=block_returns,
                    ticker_groups={
                        ticker: "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"
                        for ticker in PHASE4A_TICKERS
                    },
                )
                comparison = {
                    "candidate": candidate_policy,
                    "comparator": control,
                    "ticker_group": group,
                    "equal_ticker_mean_cagr_difference": point_diff,
                    **bootstrap,
                }
                bootstrap_rows.append(comparison)
                comparisons[f"{group}:{control}"] = comparison
            random_policy_prefix = f"random:{model_id}:"
            random_comparator = random_group_summaries[model_id][group]
            candidate = _group_mean_policy(policy_rows, candidate_policy, group)
            point_diff = (
                None
                if candidate["chronological_portfolio_cagr"] is None
                or random_comparator["chronological_portfolio_cagr"] is None
                else candidate["chronological_portfolio_cagr"]
                - random_comparator["chronological_portfolio_cagr"]
            )
            bootstrap = hierarchical_paired_bootstrap(
                candidate_policy=candidate_policy,
                comparator_policy="",
                ticker_group=group,
                block_returns=block_returns,
                ticker_groups={
                    ticker: "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"
                    for ticker in PHASE4A_TICKERS
                },
                random_comparator_prefix=random_policy_prefix,
            )
            comparison = {
                "candidate": candidate_policy,
                "comparator": f"matched_random_mean:{model_id}",
                "ticker_group": group,
                "equal_ticker_mean_cagr_difference": point_diff,
                **bootstrap,
            }
            bootstrap_rows.append(comparison)
            comparisons[f"{group}:matched_random"] = comparison
        comparisons_ok = all(
            comparisons[f"{group}:{control}"].get("equal_ticker_mean_cagr_difference") is not None
            and comparisons[f"{group}:{control}"].get("equal_ticker_mean_cagr_difference") >= 0.02
            and comparisons[f"{group}:{control}"].get("bootstrap_ci_95_low") is not None
            and comparisons[f"{group}:{control}"]["bootstrap_ci_95_low"] > 0.0
            for group in group_names
            for control in [*control_ids, "matched_random"]
        )
        support_checks[model_id] = {
            "beats_each_control_by_two_cagr_points_with_positive_95pct_lower_bound": comparisons_ok,
            "comparisons": comparisons,
        }

    adequate_comparison = all(
        overlap_summary[model_id][group]["mean_common_entry_overlap_percentage"] is not None
        and overlap_summary[model_id][group]["mean_common_entry_overlap_percentage"]
        >= policy_config["common_entry_coverage_minimum"] * 100.0
        and match_summary[model_id][group]["adequate_mean_match"]
        for model_id in main_model_ids
        for group in group_names
    )
    h6_supported = adequate_comparison and any(
        item["beats_each_control_by_two_cagr_points_with_positive_95pct_lower_bound"]
        for item in support_checks.values()
    )
    h6_contradicted = adequate_comparison and all(
        all(
            any(
                support_checks[model_id]["comparisons"][f"{group}:{control}"].get(
                    "bootstrap_ci_95_high"
                )
                is not None
                and support_checks[model_id]["comparisons"][f"{group}:{control}"][
                    "bootstrap_ci_95_high"
                ]
                < 0.02
                for control in [*control_ids, "matched_random"]
            )
            for group in group_names
        )
        for model_id in main_model_ids
    )
    h6_verdict = (
        "supported" if h6_supported else "contradicted" if h6_contradicted else "inconclusive"
    )

    return {
        "policy_rows": policy_rows,
        "trade_rows": trade_rows,
        "year_regime_rows": year_regime_rows,
        "random_rows": random_rows,
        "ppo_entry_diagnostic_rows": ppo_entry_diagnostic_rows,
        "all_metric_summaries": all_metric_summaries,
        "overlap_summary": overlap_summary,
        "match_summary": match_summary,
        "bootstrap_rows": bootstrap_rows,
        "support_checks": support_checks,
        "h6_verdict": h6_verdict,
        "h6_supported": bool(h6_supported),
        "h6_contradicted": bool(h6_contradicted),
        "adequate_comparison": bool(adequate_comparison),
    }
