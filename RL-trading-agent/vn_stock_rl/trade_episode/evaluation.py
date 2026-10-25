from __future__ import annotations

import json
from typing import Any

import numpy as np


def summarize_calendar_performance(
    equity_curve,
    exposure,
    trades,
    *,
    buy_and_hold_equity=None,
    annual_benchmark: float = 0.07,
    intervals_per_year: int = 252,
) -> dict[str, float | int | None]:
    """Summarize a chronological realized portfolio curve; does not run a policy."""

    equity = np.asarray(equity_curve, dtype=np.float64)
    invested = np.asarray(exposure, dtype=bool)
    if equity.ndim != 1 or len(equity) == 0 or not np.isfinite(equity).all() or (equity <= 0).any():
        raise ValueError("equity_curve must be a non-empty finite positive 1D series")
    if invested.ndim != 1 or len(invested) != len(equity):
        raise ValueError("exposure must have one value per equity point")
    if intervals_per_year <= 0 or annual_benchmark <= -1:
        raise ValueError("Invalid benchmark or annualization setting")

    intervals = len(equity) - 1
    cagr = (
        None
        if intervals == 0
        else float((equity[-1] / equity[0]) ** (intervals_per_year / intervals) - 1.0)
    )
    drawdowns = equity / np.maximum.accumulate(equity) - 1.0
    records = list(trades)
    durations = [
        float(row["holding_duration"]) for row in records if row.get("holding_duration") is not None
    ]
    waits = [
        float(row["waiting_duration"]) for row in records if row.get("waiting_duration") is not None
    ]
    returns = [
        float(row["raw_trade_return"]) for row in records if row.get("raw_trade_return") is not None
    ]

    buy_hold_cagr = None
    if buy_and_hold_equity is not None:
        benchmark = np.asarray(buy_and_hold_equity, dtype=np.float64)
        if (
            benchmark.shape != equity.shape
            or not np.isfinite(benchmark).all()
            or (benchmark <= 0).any()
        ):
            raise ValueError("buy_and_hold_equity must match the positive finite equity curve")
        if intervals:
            buy_hold_cagr = float(
                (benchmark[-1] / benchmark[0]) ** (intervals_per_year / intervals) - 1.0
            )

    return {
        "chronological_portfolio_cagr": cagr,
        "maximum_drawdown": float(drawdowns.min()),
        "exposure_percentage": float(invested.mean() * 100.0),
        "number_of_trades": len(records),
        "average_waiting_duration": None if not waits else float(np.mean(waits)),
        "average_holding_duration": None if not durations else float(np.mean(durations)),
        "win_rate": None if not returns else float(np.mean(np.asarray(returns) > 0.0)),
        "buy_and_hold_cagr": buy_hold_cagr,
        "annual_benchmark_cagr": float(annual_benchmark),
        "annual_benchmark_terminal_value": float(
            (1.0 + annual_benchmark) ** (intervals / intervals_per_year)
        ),
        "final_portfolio_value": float(equity[-1]),
        "total_calendar_return": float(equity[-1] / equity[0] - 1.0),
        "evaluated_trading_intervals": int(intervals),
    }


def evaluate_chronological_policy(
    model,
    env,
    *,
    seed: int = 1208,
    deterministic: bool = True,
) -> dict[str, Any]:
    """Run one chronological, wealth-compounding masked policy path.

    A completed episode's realized price ratio compounds the wealth carried into
    the next episode. A data-end open position is marked to market and remains an
    open position; it is never converted to a synthetic sale.
    """

    if env.n_rows < 2:
        raise ValueError("Chronological evaluation needs at least two rows")
    current_index = 0
    wealth = 1.0
    equity_curve = [1.0]
    exposure = [False]
    daily_path: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    action_counts = {"WAIT": 0, "BUY": 0, "HOLD": 0, "SELL": 0}
    open_position_at_end = False
    open_position_when_stopped = False
    incomplete_horizon = False
    stopped_on_open_truncation = False
    total_steps = 0

    while current_index < env.n_rows - 1:
        observation, reset_info = env.reset(
            seed=seed if total_steps == 0 else None,
            options={"start_index": current_index},
        )
        episode_actions: list[dict[str, Any]] = []
        episode_action_counts = {"WAIT": 0, "BUY": 0, "HOLD": 0, "SELL": 0}
        episode_bought = False
        episode_start_date = reset_info["episode_start_date"]
        episode_start_index = int(reset_info["episode_start_index"])
        while True:
            action_mask = env.action_masks()
            position_before = bool(env._position_in)
            action, _ = model.predict(
                observation,
                deterministic=deterministic,
                action_masks=action_mask,
            )
            action = int(np.asarray(action).reshape(-1)[0])
            if not action_mask[action]:
                raise RuntimeError("Evaluation policy selected an invalid masked action")
            action_name = (
                "SELL"
                if position_before and action == 0
                else "HOLD"
                if position_before
                else "BUY"
                if action == 1
                else "WAIT"
            )
            action_date = env._date_label(env._market_index)
            action_counts[action_name] += 1
            episode_action_counts[action_name] += 1
            if action_name == "BUY":
                episode_bought = True
            observation, reward, terminated, truncated, info = env.step(action)
            total_steps += 1
            marked_equity = wealth * info["mark_to_market_portfolio_value"]
            previous_equity = equity_curve[-1]
            equity_curve.append(marked_equity)
            exposure.append(bool(info["position"]))
            current_index = int(info["decision_index"])
            daily_path.append(
                {
                    "decision_date": action_date,
                    "execution_date": info["date"],
                    "interval_return": float(marked_equity / previous_equity - 1.0),
                    "portfolio_value": float(marked_equity),
                    "exposure": bool(info["position"]),
                    "cash": float(wealth * info["cash"]),
                    "position_value": float(wealth * info["position_value"]),
                }
            )
            episode_actions.append(
                {
                    "decision_date": action_date,
                    "action": action_name,
                    "valid_actions": [
                        int(index) for index, valid in enumerate(action_mask) if valid
                    ],
                    "reward": float(reward),
                }
            )

            if terminated:
                trade = {
                    "ticker": info["ticker"],
                    "entry_date": info["entry_date"],
                    "entry_price": info["entry_price"],
                    "exit_date": info["exit_date"],
                    "exit_price": info["exit_price"],
                    "waiting_duration": info["waiting_duration"],
                    "holding_duration": info["holding_duration"],
                    "raw_trade_return": info["raw_trade_return"],
                    "annualized_log_trade_return": info["annualized_log_trade_return"],
                    "terminal_rl_reward": float(reward),
                }
                trades.append(trade)
                wealth *= float(info["cash"])
                episodes.append(
                    _episode_record(
                        len(episodes),
                        episode_start_date,
                        episode_start_index,
                        current_index,
                        info,
                        episode_bought,
                        episode_actions,
                        episode_action_counts,
                        trade,
                    )
                )
                break

            if truncated:
                episodes.append(
                    _episode_record(
                        len(episodes),
                        episode_start_date,
                        episode_start_index,
                        current_index,
                        info,
                        episode_bought,
                        episode_actions,
                        episode_action_counts,
                        None,
                    )
                )
                if info["truncation_reason"] == "data_end":
                    open_position_at_end = bool(info["position"])
                    break
                if info["position"]:
                    open_position_when_stopped = True
                    incomplete_horizon = True
                    # Do not reset an open position to OUT at the same price. The
                    # final equity point is marked to market and evaluation ends.
                    stopped_on_open_truncation = True
                    break
                # A finite no-trade episode ends in cash. Continue the calendar
                # at the same date with a fresh decision episode.
                break

        if current_index >= env.n_rows - 1 or open_position_at_end or stopped_on_open_truncation:
            break
        if total_steps >= env.n_rows:
            raise RuntimeError("Chronological evaluation did not advance through the data")

    buy_and_hold = np.ones(env.n_rows, dtype=np.float64)
    if env.n_rows > 1:
        buy_and_hold[1:] = env.close_prices[1:] / env.open_prices[1]
    curve = np.asarray(equity_curve, dtype=np.float64)
    exposure_array = np.asarray(exposure, dtype=bool)
    if len(curve) != len(exposure_array):
        raise RuntimeError("Equity and exposure histories have inconsistent lengths")
    if len(curve) > len(buy_and_hold):
        raise RuntimeError("Policy generated more daily points than the evaluation data")
    result = summarize_calendar_performance(
        curve,
        exposure_array,
        trades,
        buy_and_hold_equity=buy_and_hold[: len(curve)],
    )
    result.update(
        {
            "trades": trades,
            "episodes": episodes,
            "action_counts": action_counts,
            "daily_path": daily_path,
            "open_position_at_end": open_position_at_end,
            "open_position_when_stopped": open_position_when_stopped,
            "incomplete_horizon": incomplete_horizon,
            "episode_count": len(episodes),
            "no_trade_episode_count": sum(not row["bought"] for row in episodes),
            "no_trade_episode_frequency": None
            if not episodes
            else float(sum(not row["bought"] for row in episodes) / len(episodes)),
            "truncated_episode_count": sum(row["truncated"] for row in episodes),
            "truncated_episode_frequency": None
            if not episodes
            else float(sum(row["truncated"] for row in episodes) / len(episodes)),
            "incomplete_episode_count": sum(
                row["bought"] and not row["completed_trade"] for row in episodes
            ),
            "open_position_truncated_episode_count": sum(
                row["bought"] and row["truncated"] and row["truncation_reason"] != "data_end"
                for row in episodes
            ),
            "median_terminal_rl_reward": None
            if not trades
            else float(np.median([row["terminal_rl_reward"] for row in trades])),
            "median_waiting_duration": None
            if not trades
            else float(np.median([row["waiting_duration"] for row in trades])),
            "median_holding_duration": None
            if not trades
            else float(np.median([row["holding_duration"] for row in trades])),
            "first_action_buy_frequency": None
            if not episodes
            else float(
                np.mean(
                    [json.loads(row["action_sequence"])[0]["action"] == "BUY" for row in episodes]
                )
            ),
            "immediate_buy_trade_frequency": None
            if not trades
            else float(np.mean([row["waiting_duration"] == 0 for row in trades])),
            "minimum_hold_exit_frequency": None
            if not trades
            else float(
                np.mean([row["holding_duration"] == env.min_holding_intervals for row in trades])
            ),
            "evaluation_end_date": env._date_label(min(current_index, env.n_rows - 1)),
            "final_mark_to_market_value": float(curve[-1]),
            "mean_terminal_rl_reward": None
            if not trades
            else float(np.mean([row["terminal_rl_reward"] for row in trades])),
            "mean_annualized_log_trade_return": None
            if not trades
            else float(np.mean([row["annualized_log_trade_return"] for row in trades])),
        }
    )
    return result


def _episode_record(
    episode_index: int,
    start_date: str,
    start_index: int,
    end_index: int,
    info: dict[str, Any],
    bought: bool,
    actions: list[dict[str, Any]],
    action_counts: dict[str, int],
    trade: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact, machine-readable trajectory row for audit logs."""

    return {
        "ticker": info["ticker"],
        "episode_index": episode_index,
        "start_date": start_date,
        "start_index": start_index,
        "end_date": info["date"],
        "end_index": end_index,
        "bought": bought,
        "completed_trade": trade is not None,
        "terminated": trade is not None,
        "truncated": trade is None,
        "termination_reason": info["termination_reason"],
        "truncation_reason": info["truncation_reason"],
        "entry_date": info["entry_date"],
        "entry_price": info["entry_price"],
        "exit_date": info["exit_date"],
        "exit_price": info["exit_price"],
        "waiting_duration": info["waiting_duration"],
        "holding_duration": info["holding_duration"],
        "raw_trade_return": info["raw_trade_return"],
        "annualized_log_trade_return": info["annualized_log_trade_return"],
        "terminal_rl_reward": None if trade is None else trade["terminal_rl_reward"],
        "cash": info["cash"],
        "position_value": info["position_value"],
        "mark_to_market_portfolio_value": info["mark_to_market_portfolio_value"],
        "action_counts": json.dumps(action_counts, separators=(",", ":")),
        "action_sequence": json.dumps(actions, separators=(",", ":")),
    }
