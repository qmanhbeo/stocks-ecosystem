"""I/O, provenance, matching, and inference helpers for Phase 4B."""

from __future__ import annotations

import csv
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

EXPERIMENT_ID = "rl-trade-episode-phase4b-20261025"
POLICY_SEEDS = (1208, 1209, 1210)
SPLITS = ("train", "validation", "test")
SPLIT_LABELS = {
    "train": "training_insample",
    "validation": "validation_previously_examined",
    "test": "exploratory_alpha_selection_contaminated",
}
VARIANTS = ("market_only", "market_plus_s1_c16")
METRICS = (
    "mean_terminal_rl_reward",
    "median_terminal_rl_reward",
    "number_of_trades",
    "win_rate",
    "average_holding_duration",
    "median_holding_duration",
    "average_waiting_duration",
    "median_waiting_duration",
    "exposure_percentage",
    "total_calendar_return",
    "chronological_portfolio_cagr",
    "maximum_drawdown",
    "no_trade_episode_count",
    "no_trade_episode_frequency",
    "truncated_episode_count",
    "truncated_episode_frequency",
    "incomplete_episode_count",
    "episode_count",
    "first_action_buy_frequency",
    "immediate_buy_trade_frequency",
    "minimum_hold_exit_frequency",
    "open_position_truncated_episode_count",
    "final_mark_to_market_value",
    "evaluated_trading_intervals",
    "mean_annualized_log_trade_return",
)
REPRODUCTION_METRICS = (
    "mean_terminal_rl_reward",
    "median_terminal_rl_reward",
    "number_of_trades",
    "win_rate",
    "average_holding_duration",
    "average_waiting_duration",
    "exposure_percentage",
    "total_calendar_return",
    "chronological_portfolio_cagr",
    "maximum_drawdown",
)
TRADE_FIELDS = (
    "policy",
    "variant",
    "seed",
    "split",
    "ticker",
    "ticker_group",
    "entry_decision_date",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "waiting_duration",
    "holding_duration",
    "raw_trade_return",
    "annualized_log_trade_return",
    "terminal_rl_reward",
    "entry_regime",
)


def _json_default(value: Any):
    import numpy as np

    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    fieldnames: tuple[str, ...] | None = None,
) -> None:
    if not rows and fieldnames is None:
        raise ValueError(f"Refusing to write an empty research CSV without a schema: {path}")
    fields = list(fieldnames or dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _input_paths(data_root: Path, tickers: tuple[str, ...]) -> dict[str, Path]:
    from vn_stock_rl.trade_episode.data import stock_bars_path
    from vn_stock_rl.trade_episode.signals import C16_ARTIFACT, S1_ARTIFACT

    paths = {f"ohlcv_{ticker}": stock_bars_path(ticker, data_root=data_root) for ticker in tickers}
    paths["vnindex"] = stock_bars_path("VNINDEX", data_root=data_root)
    paths["tradability"] = data_root / "features" / "execution" / "tradability_daily.parquet"
    paths["s1"] = data_root / S1_ARTIFACT
    paths["c16"] = data_root / C16_ARTIFACT
    return paths


def _file_stats(paths: dict[str, Path]) -> dict[str, dict[str, int]]:
    return {
        name: {"size_bytes": int(path.stat().st_size), "mtime_ns": int(path.stat().st_mtime_ns)}
        for name, path in paths.items()
    }


def _read_duration_pairs(path: Path) -> dict[tuple[str, str], list[tuple[int, int]]]:
    grouped: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for row in _read_csv(path):
        if int(row["holding_duration"]) < 3 or int(row["waiting_duration"]) < 0:
            raise ValueError("Validation duration-pair source contains invalid durations")
        grouped[(row["variant"], row["ticker"])].append(
            (int(row["waiting_duration"]), int(row["holding_duration"]))
        )
    return dict(grouped)


def _metric_row(
    result: dict[str, Any],
    *,
    policy: str,
    variant: str,
    seed: int | None,
    split: str,
    ticker: str,
    ticker_group: str,
) -> dict[str, Any]:
    row = {
        "policy": policy,
        "variant": variant,
        "seed": seed,
        "split": split,
        "ticker": ticker,
        "ticker_group": ticker_group,
        **{field: result.get(field) for field in METRICS},
        "action_counts": json.dumps(result.get("action_counts", {}), separators=(",", ":")),
    }
    return row


def _trade_rows(
    trades: list[dict[str, Any]],
    *,
    variant: str,
    seed: int,
    split: str,
    ticker: str,
    ticker_group: str,
    stock_dates,
    regime_frame,
) -> list[dict[str, Any]]:
    from vn_stock_rl.trade_episode.phase4b_regimes import regime_asof

    result = []
    dates = stock_dates.normalize()
    for trade in trades:
        entry_fill = __import__("pandas").Timestamp(trade["entry_date"]).normalize()
        index = int(dates.searchsorted(entry_fill, side="left"))
        decision_date = dates[max(0, index - 1)]
        result.append(
            {
                "policy": "MaskablePPO",
                "variant": variant,
                "seed": seed,
                "split": split,
                "ticker": ticker,
                "ticker_group": ticker_group,
                "entry_decision_date": str(decision_date.date()),
                **trade,
                "entry_regime": regime_asof(regime_frame, decision_date),
            }
        )
    return result


def _group_mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return None if not values else float(sum(values) / len(values))


def _quantiles(values: list[float]) -> dict[str, float | None]:
    import numpy as np

    if not values:
        return {"p10": None, "p50": None, "p90": None}
    q10, q50, q90 = np.quantile(np.asarray(values, dtype=np.float64), [0.1, 0.5, 0.9])
    return {"p10": float(q10), "p50": float(q50), "p90": float(q90)}


def _match_quality(
    ppo_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    *,
    ppo_holdings: list[int],
    ppo_waits: list[int],
    control_holdings: list[int],
    control_waits: list[int],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    from vn_stock_rl.trade_episode.phase4b_controls import summarize_duration_matching

    target = {
        key: _group_mean(ppo_rows, key)
        for key in (
            "exposure_percentage",
            "average_holding_duration",
            "average_waiting_duration",
        )
    }
    observed = {key: _group_mean(control_rows, key) for key in target}
    if any(value is None for value in (*target.values(), *observed.values())):
        return {"adequate_match": False, "reason": "missing completed trades or exposure metrics"}
    gaps = summarize_duration_matching(target, observed)
    ppo_hold_q = _quantiles(ppo_holdings)
    ctl_hold_q = _quantiles(control_holdings)
    ppo_wait_q = _quantiles(ppo_waits)
    ctl_wait_q = _quantiles(control_waits)
    ppo_exposure_q = _quantiles([float(row["exposure_percentage"]) for row in ppo_rows])
    control_exposure_q = {
        quantile: control_rows[0].get(f"exposure_percentage_{quantile}")
        for quantile in ("p10", "p50", "p90")
    }
    quality = {
        **gaps,
        "absolute_exposure_error_percentage_points": abs(gaps["exposure_error_percentage_points"]),
        "absolute_holding_duration_relative_error": abs(gaps["holding_duration_relative_error"]),
        "absolute_waiting_duration_error_days": abs(gaps["waiting_duration_error_days"]),
        "target_mean_exposure_percentage": target["exposure_percentage"],
        "observed_mean_exposure_percentage": observed["exposure_percentage"],
        "target_mean_holding_duration": target["average_holding_duration"],
        "observed_mean_holding_duration": observed["average_holding_duration"],
        "target_mean_waiting_duration": target["average_waiting_duration"],
        "observed_mean_waiting_duration": observed["average_waiting_duration"],
        "ppo_holding_duration_quantiles": ppo_hold_q,
        "control_holding_duration_quantiles": ctl_hold_q,
        "ppo_waiting_duration_quantiles": ppo_wait_q,
        "control_waiting_duration_quantiles": ctl_wait_q,
        "ppo_exposure_percentage_quantiles": ppo_exposure_q,
        "control_exposure_percentage_quantiles": control_exposure_q,
    }
    quality["adequate_match"] = bool(
        quality["absolute_exposure_error_percentage_points"]
        <= thresholds["mean_absolute_exposure_error_percentage_points"]
        and quality["absolute_holding_duration_relative_error"]
        <= thresholds["relative_mean_holding_duration_error"]
        and quality["absolute_waiting_duration_error_days"]
        <= thresholds["mean_waiting_duration_error_days"]
    )
    return quality


def _match_groups(
    ppo_periods: list[dict[str, Any]],
    control_summaries: list[dict[str, Any]],
    ppo_durations: dict[tuple[str, str, str], dict[str, list[int]]],
    control_durations: dict[tuple[str, str, str], dict[str, list[int]]],
    *,
    thresholds: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    ppo_keys = {
        (row["variant"], row["ticker"], row["split"])
        for row in ppo_periods
        if row["policy"] == "MaskablePPO"
    }
    control_index = {
        (row["variant"], row["ticker"], row["split"]): row for row in control_summaries
    }
    match_by_key = {}
    rows = []
    for key in sorted(ppo_keys):
        variant, ticker, split = key
        ppo_rows = [
            row
            for row in ppo_periods
            if row["policy"] == "MaskablePPO"
            and (row["variant"], row["ticker"], row["split"]) == key
        ]
        control_summary = control_index.get(key)
        if control_summary is None:
            continue
        ppo_dur = ppo_durations.get(key, {"holding": [], "waiting": []})
        ctl_dur = control_durations.get(key, {"holding": [], "waiting": []})
        quality = _match_quality(
            ppo_rows,
            [control_summary],
            ppo_holdings=ppo_dur["holding"],
            ppo_waits=ppo_dur["waiting"],
            control_holdings=ctl_dur["holding"],
            control_waits=ctl_dur["waiting"],
            thresholds=thresholds,
        )
        row = {
            "variant": variant,
            "ticker": ticker,
            "ticker_group": ppo_rows[0]["ticker_group"],
            "split": split,
            **quality,
        }
        rows.append(row)
        match_by_key[key] = quality

    group_rows = []
    for variant in VARIANTS:
        for split in SPLITS:
            for ticker_group in ("training_universe", "unseen_ticker"):
                selected = [
                    row
                    for row in rows
                    if row["variant"] == variant
                    and row["split"] == split
                    and row["ticker_group"] == ticker_group
                ]
                if not selected:
                    continue
                exposure_gap = float(
                    sum(row["absolute_exposure_error_percentage_points"] for row in selected)
                    / len(selected)
                )
                holding_gap = float(
                    sum(row["absolute_holding_duration_relative_error"] for row in selected)
                    / len(selected)
                )
                waiting_gap = float(
                    sum(row["absolute_waiting_duration_error_days"] for row in selected)
                    / len(selected)
                )
                group_rows.append(
                    {
                        "variant": variant,
                        "split": split,
                        "ticker_group": ticker_group,
                        "ticker_count": len(selected),
                        "mean_absolute_exposure_error_percentage_points": exposure_gap,
                        "mean_absolute_holding_duration_relative_error": holding_gap,
                        "mean_absolute_waiting_duration_error_days": waiting_gap,
                        "adequate_match": bool(
                            exposure_gap
                            <= thresholds["mean_absolute_exposure_error_percentage_points"]
                            and holding_gap <= thresholds["relative_mean_holding_duration_error"]
                            and waiting_gap <= thresholds["mean_waiting_duration_error_days"]
                        ),
                    }
                )
    return group_rows, match_by_key


def _h1_summary(
    *,
    ppo_year_values,
    control_year_values,
    ppo_totals,
    control_totals,
    match_groups,
    bootstrap_replicates: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    from vn_stock_rl.trade_episode.phase4b_statistics import (
        bootstrap_paired_blocks,
        empirical_percentile,
    )

    by_variant = {}
    for variant_index, variant in enumerate(VARIANTS):
        per_group = {}
        for group in ("training_universe", "unseen_ticker"):
            tickers = sorted(
                ticker
                for candidate, ticker in ppo_totals
                if candidate == variant and (ticker_group_for(ticker) == group)
            )
            ppo_cells = {}
            control_cells = {}
            for (candidate, ticker, year), values in ppo_year_values.items():
                if candidate == variant and ticker_group_for(ticker) == group and year >= 2023:
                    ppo_cells[(ticker, year)] = values
            for (candidate, ticker, year), values in control_year_values.items():
                if candidate == variant and ticker_group_for(ticker) == group and year >= 2023:
                    control_cells[(ticker, year)] = values
            paired = bootstrap_paired_blocks(
                ppo_cells,
                control_cells,
                replicates=bootstrap_replicates,
                seed=bootstrap_seed
                + variant_index * 101
                + (0 if group == "training_universe" else 17),
            )
            ticker_percentiles = []
            ticker_percentile_map = {}
            tickers_above_median = 0
            for ticker in tickers:
                ppo_values = ppo_totals.get((variant, ticker), [])
                null_values = control_totals.get((variant, ticker), [])
                if not ppo_values or not null_values:
                    continue
                ppo_value = float(np.mean(ppo_values))
                percentile = empirical_percentile(ppo_value, null_values)
                if percentile is not None:
                    ticker_percentiles.append(percentile)
                    ticker_percentile_map[ticker] = percentile
                    tickers_above_median += int(ppo_value > float(np.median(null_values)))
            match = next(
                (
                    row
                    for row in match_groups
                    if row["variant"] == variant
                    and row["split"] == "test"
                    and row["ticker_group"] == group
                ),
                None,
            )
            per_group[group] = {
                **paired,
                "adequate_match": bool(match and match["adequate_match"]),
                "median_ticker_null_percentile": (
                    None if not ticker_percentiles else float(np.median(ticker_percentiles))
                ),
                "tickers_above_control_median": tickers_above_median,
                "eligible_ticker_count": len(ticker_percentiles),
                "ticker_null_percentiles": ticker_percentile_map,
            }

        group_values = list(per_group.values())
        matched = len(group_values) == 2 and all(row["adequate_match"] for row in group_values)
        contradicted = bool(
            matched
            and all(row["ci95_lower"] is not None and row["ci95_lower"] > 0 for row in group_values)
            and all(
                row["eligible_ticker_count"] > 0
                and row["tickers_above_control_median"] / row["eligible_ticker_count"] >= 2 / 3
                for row in group_values
            )
        )
        consistent_percentile = all(
            row["median_ticker_null_percentile"] is not None
            and row["median_ticker_null_percentile"] <= 50
            for row in group_values
        )
        consistent_interval = all(
            row["ci95_upper"] is not None and row["ci95_upper"] <= 0 for row in group_values
        )
        consistent = bool(matched and (consistent_percentile or consistent_interval))
        classification = (
            "contradicted by the evidence"
            if contradicted
            else "consistent with the evidence"
            if consistent
            else "inconclusive"
        )
        by_variant[variant] = {
            "groups": per_group,
            "classification": classification,
            "decision_rule": (
                "Requires adequate exposure/duration matching, positive 95% stock-year "
                "intervals in both groups, and >=2/3 tickers above the null median."
            ),
        }
    classifications = [row["classification"] for row in by_variant.values()]
    combined = classifications[0] if classifications[0] == classifications[1] else "inconclusive"
    return {"by_variant": by_variant, "combined_classification": combined}


def ticker_group_for(ticker: str) -> str:
    from vn_stock_rl.trade_episode.phase4a_data import UNSEEN_TICKERS

    return "unseen_ticker" if ticker in UNSEEN_TICKERS else "training_universe"


class Phase4BJobMonitor:
    """Keep a compact heartbeat and append-safe partial metric trace."""

    def __init__(self, worktree_root: Path, commit_sha: str) -> None:
        self.job = "stock_rl_phase4b"
        self.commit_sha = commit_sha
        self.started = datetime.now(timezone.utc)
        stamp = self.started.strftime("%Y%m%dT%H%M%SZ")
        artifact_root = worktree_root / "RL-trading-agent" / "artifacts"
        status_root = artifact_root / "job_status"
        trace_root = artifact_root / "job_progress"
        status_root.mkdir(parents=True, exist_ok=True)
        trace_root.mkdir(parents=True, exist_ok=True)
        self.status_path = status_root / f"{self.job}.json"
        self.trace_path = trace_root / f"{self.job}-{commit_sha[:8]}-{stamp}.jsonl"
        self._trace = self.trace_path.open("x", encoding="utf-8")
        self.phase_name = "starting"
        self.phase_total = 0
        self.phase_completed = 0
        self.last_heartbeat = time.monotonic()
        self.phase_started = self.last_heartbeat
        self.state: dict[str, Any] = {
            "job": self.job,
            "experiment_id": EXPERIMENT_ID,
            "run_code_commit_sha": commit_sha,
            "status": "running",
            "started_at": self.started.isoformat(),
            "updated_at": self.started.isoformat(),
            "last_heartbeat": self.started.isoformat(),
            "phase": self.phase_name,
            "progress": {"unit": "paths", "completed": 0, "total": 0},
            "throughput": {"paths_per_minute": None},
            "artifacts": {
                "partial_metrics_jsonl": str(self.trace_path),
            },
            "error": None,
        }
        self._write_status()

    def _write_status(self) -> None:
        now = datetime.now(timezone.utc)
        elapsed = max(time.monotonic() - self.phase_started, 1e-9)
        self.state["updated_at"] = now.isoformat()
        self.state["last_heartbeat"] = now.isoformat()
        self.state["phase"] = self.phase_name
        self.state["progress"] = {
            "unit": "paths",
            "completed": self.phase_completed,
            "total": self.phase_total,
        }
        self.state["throughput"] = {
            "paths_per_minute": round(self.phase_completed * 60.0 / elapsed, 2)
            if self.phase_completed
            else None
        }
        temporary = self.status_path.with_suffix(f".json.tmp.{os.getpid()}")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.status_path)
        self.last_heartbeat = time.monotonic()

    def phase(self, name: str, *, total: int) -> None:
        self.phase_name = name
        self.phase_total = int(total)
        self.phase_completed = 0
        self.phase_started = time.monotonic()
        self._write_status()
        print(f"phase={name} total={total}", flush=True)

    def record(self, kind: str, payload: dict[str, Any], *, details=None) -> None:
        self.phase_completed += 1
        event = {
            "experiment_id": EXPERIMENT_ID,
            "run_code_commit_sha": self.commit_sha,
            "phase": self.phase_name,
            "index": self.phase_completed,
            "kind": kind,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        if details is not None:
            event["details"] = details
        self._trace.write(json.dumps(event, default=_json_default, allow_nan=False) + "\n")
        self._trace.flush()
        now = time.monotonic()
        if (
            self.phase_completed % 50 == 0
            or self.phase_completed == self.phase_total
            or now - self.last_heartbeat >= 30.0
        ):
            self._write_status()
            print(
                f"phase={self.phase_name} progress={self.phase_completed}/{self.phase_total}",
                flush=True,
            )

    def complete(self, outputs: list[str]) -> None:
        self.state["status"] = "completed"
        self.state["artifacts"]["final_outputs"] = outputs
        self._write_status()
        self._trace.close()

    def fail(self, error: BaseException) -> None:
        if self.state.get("status") == "completed":
            return
        self.state["status"] = "failed"
        self.state["error"] = {"type": type(error).__name__, "message": str(error)}
        self._write_status()
        if not self._trace.closed:
            self._trace.close()


def summarize_h5_regimes(
    *,
    ppo_regime_values,
    control_regime_values,
    benchmark_regime_values,
    match_group_rows,
    config,
) -> tuple[dict[str, Any], str]:
    """Apply the frozen H5 rule to 2020–2025 year/regime blocks."""

    from vn_stock_rl.trade_episode.phase4b_statistics import bootstrap_paired_blocks

    per_variant_results: dict[str, Any] = {}
    classifications = []
    for variant_index, variant in enumerate(VARIANTS):
        per_variant = {"regimes": {}, "classification": "inconclusive"}
        all_required_positive = True
        adequately_matched = True
        consistent_failure = False
        for group_index, group in enumerate(("training_universe", "unseen_ticker")):
            group_matches = [
                row
                for row in match_group_rows
                if row["variant"] == variant
                and row["split"] in ("validation", "test")
                and row["ticker_group"] == group
            ]
            adequately_matched &= len(group_matches) == 2 and all(
                row["adequate_match"] for row in group_matches
            )
            for regime_index, regime in enumerate(("falling", "sideways")):
                ppo_cells = {}
                control_cells = {}
                mechanical_cells = {}
                buyhold_cells = {}
                for (candidate, ticker, year, label), values in ppo_regime_values.items():
                    if (
                        candidate == variant
                        and ticker_group_for(ticker) == group
                        and year >= 2020
                        and label == regime
                    ):
                        ppo_cells[(ticker, (year, label))] = values
                for (candidate, ticker, year, label), values in control_regime_values.items():
                    if (
                        candidate == variant
                        and ticker_group_for(ticker) == group
                        and year >= 2020
                        and label == regime
                    ):
                        control_cells[(ticker, (year, label))] = values
                for policy_name, target in (
                    ("mechanical_immediate_entry_3day_exit", mechanical_cells),
                    ("buy_and_hold", buyhold_cells),
                ):
                    for (candidate, ticker, year, label), values in benchmark_regime_values.items():
                        if (
                            candidate == policy_name
                            and ticker_group_for(ticker) == group
                            and year >= 2020
                            and label == regime
                        ):
                            target[(ticker, (year, label))] = values

                seedbase = (
                    int(config["uncertainty"]["seed"])
                    + 1000
                    + variant_index * 100
                    + group_index * 10
                    + regime_index
                )
                replicates = int(config["uncertainty"]["replicates"])
                random_effect = bootstrap_paired_blocks(
                    ppo_cells, control_cells, replicates=replicates, seed=seedbase
                )
                mechanical_effect = bootstrap_paired_blocks(
                    ppo_cells, mechanical_cells, replicates=replicates, seed=seedbase + 1
                )
                buyhold_effect = bootstrap_paired_blocks(
                    ppo_cells, buyhold_cells, replicates=replicates, seed=seedbase + 2
                )
                enough_blocks = random_effect["paired_block_count"] > 0
                positive_random = bool(
                    random_effect["ci95_lower"] is not None and random_effect["ci95_lower"] > 0
                )
                positive_references = bool(
                    mechanical_effect["mean_paired_excess_return"] is not None
                    and mechanical_effect["mean_paired_excess_return"] > 0
                    and buyhold_effect["mean_paired_excess_return"] is not None
                    and buyhold_effect["mean_paired_excess_return"] > 0
                )
                all_required_positive &= enough_blocks and positive_random and positive_references
                consistent_failure |= bool(
                    enough_blocks
                    and random_effect["ci95_upper"] is not None
                    and random_effect["ci95_upper"] <= 0
                    and not positive_references
                )
                per_variant["regimes"][f"{group}_{regime}"] = {
                    "ppo_vs_matched_random": random_effect,
                    "ppo_vs_mechanical": mechanical_effect,
                    "ppo_vs_buy_and_hold": buyhold_effect,
                    "unfavorable_regime_advantage": positive_random and positive_references,
                }

        contradicted = adequately_matched and all_required_positive
        consistent = adequately_matched and consistent_failure
        per_variant["classification"] = (
            "contradicted by the evidence"
            if contradicted
            else "consistent with the evidence"
            if consistent
            else "inconclusive"
        )
        per_variant["adequately_matched_validation_and_test"] = bool(adequately_matched)
        per_variant_results[variant] = per_variant
        classifications.append(per_variant["classification"])

    combined = classifications[0] if classifications[0] == classifications[1] else "inconclusive"
    return per_variant_results, combined
