"""Fixed-entry chronological policies and portfolio accounting for Phase 4D."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from vn_stock_rl.trade_episode.environment import annualized_log_excess_reward
from vn_stock_rl.trade_episode.phase4d_supervised import exit_feature_vector


def _split_mask(stock, split: str) -> np.ndarray:
    return np.asarray(stock.split_masks["test" if split == "exploratory" else split], dtype=bool)


def _date_label(value) -> str:
    return str(pd.Timestamp(value).date())


def make_entry_schedule(
    stock,
    *,
    split: str,
    stride: int,
    maximum_holding_intervals: int,
) -> dict[str, Any]:
    """Create identical prespecified, legal buy slots for all exit policies."""

    partition = _split_mask(stock, split)
    selected = np.flatnonzero(partition)
    if selected.size < maximum_holding_intervals + 3:
        return {"ticker": stock.ticker, "decision_indices": [], "slots": 0, "unbuyable": 0}
    first, last = int(selected[0]), int(selected[-1])
    # A buy at open[e+1] has max-horizon exit fill at e+1+H.
    slots = list(range(first, last - maximum_holding_intervals, stride))
    legal = [index for index in slots if stock.can_buy[index] and index + 1 <= last]
    return {
        "ticker": stock.ticker,
        "decision_indices": legal,
        "slots": len(slots),
        "unbuyable": len(slots) - len(legal),
    }


def _model_input(model, feature_tuple: tuple[np.ndarray, np.ndarray, np.ndarray]) -> np.ndarray:
    market_x, alpha_x, age_x = feature_tuple
    if model.feature_set == "market_only":
        return market_x.reshape(1, -1)
    if model.feature_set == "market_plus_alpha":
        return alpha_x.reshape(1, -1)
    if model.feature_set == "age_only":
        return age_x.reshape(1, -1)
    if model.feature_set == "constant":
        return age_x.reshape(1, -1)
    raise ValueError(f"Unsupported model feature set: {model.feature_set}")


def _should_sell(
    *,
    policy_kind: str,
    current_age: int,
    can_sell: bool,
    fixed_duration: int | None,
    sampled_duration: int | None,
    model,
    threshold: float | None,
    stock,
    decision_index: int,
    phase4a_state_config: dict[str, Any],
    maximum_holding_intervals: int,
    model_last_decision_age: int,
) -> tuple[bool, float | None, bool]:
    if not can_sell or current_age + 1 < 3:
        return False, None, False
    if policy_kind == "fixed":
        return bool(fixed_duration is not None and current_age + 1 >= fixed_duration), None, False
    if policy_kind == "random":
        should_exit = sampled_duration is not None and current_age + 1 >= sampled_duration
        return bool(should_exit), None, False
    if policy_kind != "supervised" or model is None or threshold is None:
        raise ValueError(f"Invalid Phase 4D policy specification: {policy_kind}")

    forced = current_age > model_last_decision_age or current_age + 4 > maximum_holding_intervals
    if forced:
        return True, None, True
    feature_tuple = exit_feature_vector(
        stock,
        decision_index=decision_index,
        current_holding_age=current_age,
        phase4a_state_config=phase4a_state_config,
    )
    prediction = float(model.predict(_model_input(model, feature_tuple))[0])
    return prediction < threshold, prediction, False


def simulate_fixed_entry_policy(
    stock,
    *,
    split: str,
    entry_decision_indices: list[int] | np.ndarray,
    policy_id: str,
    policy_kind: str,
    phase4a_state_config: dict[str, Any],
    maximum_holding_intervals: int,
    model_last_decision_age: int,
    regime_by_date: dict[str, str],
    model=None,
    threshold: float | None = None,
    fixed_duration: int | None = None,
    duration_pool: tuple[int, ...] | list[int] | None = None,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Execute one long-only path with fixed entry slots and next-open fills."""

    partition = _split_mask(stock, split)
    selected = np.flatnonzero(partition)
    if selected.size < 2:
        raise ValueError(f"{stock.ticker}: split {split} has fewer than two rows")
    first, last = int(selected[0]), int(selected[-1])
    indices = [int(index) for index in entry_decision_indices]
    if any(not partition[index] for index in indices):
        raise ValueError("An entry schedule crossed its chronological partition")
    if any(b <= a for a, b in zip(indices, indices[1:], strict=False)):
        raise ValueError("Entry schedule must be strictly chronological")

    rng = np.random.default_rng(random_seed)
    cash = 1.0
    shares = 0.0
    in_position = False
    entry_fill_index: int | None = None
    entry_decision_index: int | None = None
    entry_price: float | None = None
    sampled_duration: int | None = None
    last_exit_fill_index = first
    slot_set = set(indices)
    skipped_while_open: list[int] = []
    skipped_end_or_illegal: list[int] = []
    trades: list[dict[str, Any]] = []
    equity = np.full(last - first + 1, np.nan, dtype=np.float64)
    exposure = np.zeros(last - first + 1, dtype=bool)
    forced_exit_count = 0

    for decision_index in range(first, last + 1):
        local_index = decision_index - first
        date_key = _date_label(stock.dates[decision_index])

        # Record value at today's close, after any order submitted yesterday filled.
        equity[local_index] = (
            shares * float(stock.closes[decision_index]) if in_position else cash
        )
        exposure[local_index] = in_position

        if in_position:
            if decision_index in slot_set:
                skipped_while_open.append(decision_index)
            current_age = decision_index - int(entry_fill_index)
            if policy_kind == "random" and sampled_duration is None:
                if not duration_pool:
                    raise ValueError("Random exit policy needs a validation duration pool")
                sampled_duration = int(rng.choice(np.asarray(duration_pool, dtype=np.int64)))
            sell, prediction, forced = _should_sell(
                policy_kind=policy_kind,
                current_age=current_age,
                can_sell=bool(stock.can_sell[decision_index]),
                fixed_duration=fixed_duration,
                sampled_duration=sampled_duration,
                model=model,
                threshold=threshold,
                stock=stock,
                decision_index=decision_index,
                phase4a_state_config=phase4a_state_config,
                maximum_holding_intervals=maximum_holding_intervals,
                model_last_decision_age=model_last_decision_age,
            )
            if sell and decision_index + 1 <= last:
                exit_fill_index = decision_index + 1
                exit_price = float(stock.opens[exit_fill_index])
                duration = exit_fill_index - int(entry_fill_index)
                if duration < 3:
                    raise RuntimeError("SELL violated the three-interval minimum")
                reward = annualized_log_excess_reward(
                    float(entry_price), exit_price, duration
                )
                raw_return = exit_price / float(entry_price) - 1.0
                trade = {
                    "policy": policy_id,
                    "ticker": stock.ticker,
                    "split": split,
                    "entry_decision_date": _date_label(stock.dates[int(entry_decision_index)]),
                    "entry_date": _date_label(stock.dates[int(entry_fill_index)]),
                    "entry_price": float(entry_price),
                    "exit_decision_date": date_key,
                    "exit_date": _date_label(stock.dates[exit_fill_index]),
                    "exit_price": exit_price,
                    "entry_year": int(pd.Timestamp(stock.dates[int(entry_decision_index)]).year),
                    "exit_year": int(pd.Timestamp(stock.dates[exit_fill_index]).year),
                    "entry_regime": regime_by_date.get(
                        _date_label(stock.dates[int(entry_decision_index)]), "unknown"
                    ),
                    "waiting_duration": max(
                        0, int(entry_decision_index) - int(last_exit_fill_index)
                    ),
                    "holding_duration": int(duration),
                    "raw_trade_return": float(raw_return),
                    "annualized_log_trade_return": float(
                        252.0 / duration * np.log(exit_price / float(entry_price))
                    ),
                    "terminal_rl_reward": float(reward),
                    "predicted_delta_reward": prediction,
                    "forced_by_horizon": bool(forced),
                    "incomplete": False,
                }
                trades.append(trade)
                if forced:
                    forced_exit_count += 1
                cash = shares * exit_price
                shares = 0.0
                in_position = False
                entry_fill_index = None
                entry_decision_index = None
                entry_price = None
                sampled_duration = None
                last_exit_fill_index = exit_fill_index
            continue

        if decision_index not in slot_set:
            continue
        if not stock.can_buy[decision_index] or decision_index + 1 > last:
            skipped_end_or_illegal.append(decision_index)
            continue
        entry_decision_index = decision_index
        entry_fill_index = decision_index + 1
        entry_price = float(stock.opens[entry_fill_index])
        shares = cash / entry_price
        cash = 0.0
        in_position = True
        if policy_kind == "random":
            if not duration_pool:
                raise ValueError("Random exit policy needs a validation duration pool")
            sampled_duration = int(rng.choice(np.asarray(duration_pool, dtype=np.int64)))

    incomplete_positions = 0
    if in_position:
        incomplete_positions = 1
        trade = {
            "policy": policy_id,
            "ticker": stock.ticker,
            "split": split,
            "entry_decision_date": _date_label(stock.dates[int(entry_decision_index)]),
            "entry_date": _date_label(stock.dates[int(entry_fill_index)]),
            "entry_price": float(entry_price),
            "exit_decision_date": None,
            "exit_date": None,
            "exit_price": None,
            "entry_year": int(pd.Timestamp(stock.dates[int(entry_decision_index)]).year),
            "exit_year": None,
            "entry_regime": regime_by_date.get(
                _date_label(stock.dates[int(entry_decision_index)]), "unknown"
            ),
            "waiting_duration": max(0, int(entry_decision_index) - int(last_exit_fill_index)),
            "holding_duration": int(last - int(entry_fill_index)),
            "raw_trade_return": None,
            "annualized_log_trade_return": None,
            "terminal_rl_reward": None,
            "predicted_delta_reward": None,
            "forced_by_horizon": False,
            "incomplete": True,
            "mark_to_market_value": float(shares * stock.closes[last]),
        }
        trades.append(trade)

    if np.isnan(equity).any() or (equity <= 0).any():
        raise RuntimeError(f"{stock.ticker}: invalid chronological equity path")
    intervals = max(1, len(equity) - 1)
    final_value = float(equity[-1])
    cagr = float(final_value ** (252.0 / intervals) - 1.0)
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    daily_rows: list[dict[str, Any]] = []
    for local_index, value in enumerate(equity):
        global_index = first + local_index
        if local_index == 0:
            log_return = 0.0
            attributed_regime = "warmup"
        else:
            previous_value = float(equity[local_index - 1])
            log_return = float(np.log(value / previous_value))
            prior_date = _date_label(stock.dates[global_index - 1])
            attributed_regime = regime_by_date.get(prior_date, "unknown")
        daily_rows.append(
            {
                "policy": policy_id,
                "ticker": stock.ticker,
                "split": split,
                "date": _date_label(stock.dates[global_index]),
                "year": int(pd.Timestamp(stock.dates[global_index]).year),
                "equity": float(value),
                "log_return": log_return,
                "exposure": bool(exposure[local_index]),
                "regime": attributed_regime,
            }
        )
    completed = [trade for trade in trades if not trade["incomplete"]]
    holding = [int(trade["holding_duration"]) for trade in completed]
    waiting = [int(trade["waiting_duration"]) for trade in trades]
    returns = [float(trade["raw_trade_return"]) for trade in completed]
    rewards = [float(trade["terminal_rl_reward"]) for trade in completed]
    entered_indices = [
        int(stock.dates.get_loc(pd.Timestamp(trade["entry_decision_date"])))
        for trade in trades
        if trade["entry_decision_date"] is not None
    ]
    return {
        "policy": policy_id,
        "ticker": stock.ticker,
        "split": split,
        "final_portfolio_value": final_value,
        "total_calendar_return": final_value - 1.0,
        "chronological_portfolio_cagr": cagr,
        "maximum_drawdown": float(drawdown.min()),
        "exposure_percentage": float(np.mean(exposure[1:]) * 100.0),
        "number_of_trades": len(completed),
        "win_rate": None if not returns else float(np.mean(np.asarray(returns) > 0.0)),
        "mean_terminal_rl_reward": None if not rewards else float(np.mean(rewards)),
        "median_terminal_rl_reward": None if not rewards else float(np.median(rewards)),
        "mean_holding_duration": None if not holding else float(np.mean(holding)),
        "median_holding_duration": None if not holding else float(np.median(holding)),
        "mean_waiting_duration": None if not waiting else float(np.mean(waiting)),
        "incomplete_open_positions": incomplete_positions,
        "incomplete_mark_to_market_value": (
            float(shares * stock.closes[last]) if in_position else None
        ),
        "scheduled_entry_slots": len(indices),
        "executed_entry_count": len(entered_indices),
        "skipped_while_open_count": len(skipped_while_open),
        "skipped_unbuyable_or_end_count": len(skipped_end_or_illegal),
        "executed_entry_decision_indices": entered_indices,
        "forced_exit_count": forced_exit_count,
        "trades": trades,
        "daily_path": daily_rows,
    }


def summarize_year_regime(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Summarize path-level log wealth by contiguous calendar-year/regime blocks."""

    frame = pd.DataFrame(result["daily_path"])
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for (year, regime), group in frame.groupby(["year", "regime"], sort=True):
        values = group["log_return"].to_numpy(dtype=np.float64)
        rows.append(
            {
                "policy": result["policy"],
                "ticker": result["ticker"],
                "split": result["split"],
                "year": int(year),
                "regime": regime,
                "trading_intervals": int(len(values)),
                "log_wealth_return": float(values.sum()),
                "compounded_return": float(np.expm1(values.sum())),
                "exposure_percentage": float(group["exposure"].mean() * 100.0),
            }
        )
    return rows
