from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from vn_stock_rl.env import PortfolioChoiceEnv
from vn_stock_rl.evaluation.metadata import _to_json_safe
from vn_stock_rl.external_features import (
    default_lab_signal_prediction_dir,
    default_stock_data_dir,
)

DEFAULT_LAB_SIGNAL_COLUMNS = [
    "s1_proba",
    "c4_oc_asym_5d",
    "c5_ins_relative_size_5d",
    "c5_signal_present",
    "c6_contrarian_intra_5d",
    "c7_ceiling_count_5d",
    "c8_vol_zscore_5d",
    "c9_reversal_1d",
    "c10_illiq_level_rank",
    "c11_ret_60d_lag_rank",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
    "c14_clv_volconf_resid_rank",
]
CONDITIONED_SUBCORE_COLUMNS = [
    "s1_proba",
    "c7_ceiling_count_5d",
    "c8_vol_zscore_5d",
    "c10_illiq_level_rank",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
]
DEFAULT_STRATEGIES = ("s1_only", "full_library", "conditioned_subcore")


def _sanitize_name(value: str) -> str:
    cleaned = "".join(ch for ch in str(value) if ch.isalnum() or ch in ("_", "-"))
    return cleaned or "baseline"


def _resolve_strategy_columns(
    strategy_name: str,
    available_signal_columns: list[str],
) -> list[str]:
    if strategy_name == "s1_only":
        columns = ["s1_proba"]
    elif strategy_name == "full_library":
        columns = list(available_signal_columns)
    elif strategy_name == "conditioned_subcore":
        columns = list(CONDITIONED_SUBCORE_COLUMNS)
    else:
        raise ValueError(
            f"Unknown strategy {strategy_name!r}; expected one of {list(DEFAULT_STRATEGIES)}"
        )

    missing = [column for column in columns if column not in available_signal_columns]
    if missing:
        raise ValueError(
            f"Strategy {strategy_name!r} requires missing signal columns: {missing}"
        )
    return columns


def _rank_pct(values: np.ndarray) -> np.ndarray:
    ranked = pd.Series(values, dtype="float64").rank(method="average", pct=True).to_numpy(dtype=np.float64)
    if np.isnan(ranked).any():
        ranked = np.where(np.isfinite(ranked), ranked, 0.5)
    return ranked


def compute_strategy_scores(
    signal_slice: np.ndarray,
    signal_feature_names: Iterable[str],
    strategy_columns: list[str],
) -> np.ndarray:
    name_to_idx = {name: idx for idx, name in enumerate(signal_feature_names)}
    parts: list[np.ndarray] = []
    for column in strategy_columns:
        values = np.asarray(signal_slice[:, name_to_idx[column]], dtype=np.float64)
        if column.endswith("_present"):
            parts.append(np.clip(np.nan_to_num(values, nan=0.0), 0.0, 1.0))
        else:
            parts.append(_rank_pct(values))
    if not parts:
        raise ValueError("At least one strategy column is required")
    return np.mean(np.stack(parts, axis=0), axis=0)


def encode_top_k_action(scores: np.ndarray, top_k: int, cash_index: int) -> tuple[np.ndarray, list[int]]:
    action = np.full(int(top_k), int(cash_index), dtype=np.int64)
    scores_arr = np.asarray(scores, dtype=np.float64)
    candidate_indices = np.flatnonzero(np.isfinite(scores_arr))
    if candidate_indices.size == 0:
        return action, []
    order = np.lexsort((candidate_indices, -scores_arr[candidate_indices]))
    picks = candidate_indices[order][: min(int(top_k), candidate_indices.size)].tolist()
    action[: len(picks)] = np.asarray(picks, dtype=np.int64)
    return action, picks


def _max_drawdown(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(arr)
    peaks = np.clip(peaks, 1e-12, None)
    drawdowns = (arr / peaks) - 1.0
    return float(drawdowns.min())


def _annualized_ratio(returns: np.ndarray) -> float | None:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.size == 0:
        return None
    std = float(arr.std(ddof=0))
    if std <= 0.0:
        return None
    return float(arr.mean() / std * np.sqrt(252.0))


def run_portfolio_baseline(
    *,
    mode: str,
    data_dir: str,
    signal_prediction_dir: str,
    signal_columns: list[str],
    strategies: list[str],
    start_date: str | None,
    end_date: str | None,
    portfolio_universe_size: int,
    portfolio_top_k: int,
    portfolio_universe_tickers: list[str] | None,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    env = PortfolioChoiceEnv(
        data_dir=data_dir,
        mode=mode,
        train_episode_sampling_enabled=False,
        start_date=start_date,
        end_date=end_date,
        signal_feature_columns=signal_columns,
        signal_prediction_dir=signal_prediction_dir,
        portfolio_universe_size=portfolio_universe_size,
        portfolio_top_k=portfolio_top_k,
        portfolio_universe_tickers=portfolio_universe_tickers,
    )

    available_columns = list(env.signal_feature_names)
    strategy_columns = {
        strategy_name: _resolve_strategy_columns(strategy_name, available_columns)
        for strategy_name in strategies
    }

    strategy_daily: dict[str, pd.DataFrame] = {}
    strategy_summary: dict[str, dict[str, object]] = {}
    for strategy_name, columns in strategy_columns.items():
        env.reset(seed=1208)
        rows: list[dict[str, object]] = []
        while True:
            step_idx = int(env.current_step)
            signal_date = pd.Timestamp(env.dates[step_idx]).isoformat()
            scores = compute_strategy_scores(
                env.signal_tensor[step_idx],
                env.signal_feature_names,
                columns,
            )
            action, picks = encode_top_k_action(
                scores,
                env.portfolio_top_k,
                env.portfolio_universe_size,
            )
            _obs, reward, terminated, truncated, info = env.step(action)
            rows.append(
                {
                    "strategy": strategy_name,
                    "signal_date": signal_date,
                    "execution_date": pd.Timestamp(env.dates[env.current_step]).isoformat(),
                    "reward": float(reward),
                    "portfolio_value": float(info["portfolio_value"]),
                    "benchmark_portfolio_value": float(info["benchmark_portfolio_value"]),
                    "raw_return": float(info["raw_return"]),
                    "benchmark_return": float(info["benchmark_return"]),
                    "excess_return": float(info["excess_return"]),
                    "cash_weight": float(info["cash_weight"]),
                    "turnover": float(info["turnover"]),
                    "num_holdings": int(info["num_holdings"]),
                    "avg_holding_age": float(info["avg_holding_age"]),
                    "selected_indices": list(picks),
                    "selected_tickers": list(info["selected_tickers"]),
                    "blocked_buy_tickers": list(info["blocked_buy_tickers"]),
                    "blocked_sell_tickers": list(info["blocked_sell_tickers"]),
                }
            )
            if terminated or truncated:
                break

        daily = pd.DataFrame(rows)
        strategy_daily[strategy_name] = daily
        portfolio_values = np.concatenate([[1.0], daily["portfolio_value"].to_numpy(dtype=np.float64)])
        benchmark_values = np.concatenate(
            [[1.0], daily["benchmark_portfolio_value"].to_numpy(dtype=np.float64)]
        )
        final_portfolio_value = float(portfolio_values[-1])
        final_benchmark_value = float(benchmark_values[-1])
        strategy_summary[strategy_name] = {
            "strategy_name": strategy_name,
            "signal_columns": list(columns),
            "days": int(len(daily)),
            "period_start": str(daily["signal_date"].iloc[0]) if not daily.empty else None,
            "period_end": str(daily["execution_date"].iloc[-1]) if not daily.empty else None,
            "portfolio_total_return": float(final_portfolio_value - 1.0),
            "benchmark_total_return": float(final_benchmark_value - 1.0),
            "relative_total_return": float(final_portfolio_value / max(final_benchmark_value, 1e-12) - 1.0),
            "portfolio_sharpe_annualized": _annualized_ratio(
                daily["raw_return"].to_numpy(dtype=np.float64)
            ),
            "information_ratio_annualized": _annualized_ratio(
                daily["excess_return"].to_numpy(dtype=np.float64)
            ),
            "max_drawdown": _max_drawdown(portfolio_values),
            "avg_cash_weight": float(daily["cash_weight"].mean()) if not daily.empty else 1.0,
            "avg_num_holdings": float(daily["num_holdings"].mean()) if not daily.empty else 0.0,
            "avg_holding_age": float(daily["avg_holding_age"].mean()) if not daily.empty else 0.0,
            "rebalance_count": int((daily["turnover"] > 0.0).sum()) if not daily.empty else 0,
            "avg_turnover": float(daily["turnover"].mean()) if not daily.empty else 0.0,
            "blocked_buy_events": int(
                daily["blocked_buy_tickers"].map(len).sum()
            )
            if not daily.empty
            else 0,
            "blocked_sell_events": int(
                daily["blocked_sell_tickers"].map(len).sum()
            )
            if not daily.empty
            else 0,
        }

    overall_summary = {
        "mode": mode,
        "data_dir": str(Path(data_dir).resolve()),
        "signal_prediction_dir": str(Path(signal_prediction_dir).resolve()),
        "signal_feature_columns": list(available_columns),
        "strategies": strategy_summary,
        "portfolio_universe_size": int(env.portfolio_universe_size),
        "portfolio_top_k": int(env.portfolio_top_k),
        "universe_tickers": list(env.universe_tickers),
        "train_start_date": str(pd.Timestamp(env.train_start_date).date()),
        "train_end_date": str(pd.Timestamp(env.train_end_date).date()),
        "val_start_date": str(pd.Timestamp(env.val_start_date).date()),
        "val_end_date": str(pd.Timestamp(env.val_end_date).date()),
        "test_start_date": str(pd.Timestamp(env.test_start_date).date()),
        "test_end_date": str(pd.Timestamp(env.test_end_date).date()),
    }
    env.close()
    return overall_summary, strategy_daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a same-universe deterministic top-k baseline against PortfolioChoiceEnv."
    )
    parser.add_argument(
        "--mode",
        choices=("train", "val", "test"),
        default="test",
        help="Episode split to evaluate (default: test)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(default_stock_data_dir()),
        help="Stock parquet directory (default: shared stock data dir)",
    )
    parser.add_argument(
        "--signal-prediction-dir",
        default=str(default_lab_signal_prediction_dir()),
        help="Per-ticker signal parquet directory (default: adapted lab matrix dir)",
    )
    parser.add_argument(
        "--signal-columns",
        nargs="+",
        default=list(DEFAULT_LAB_SIGNAL_COLUMNS),
        help="Signal columns to expose to the env and the deterministic comparator",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(DEFAULT_STRATEGIES),
        help="Deterministic strategies to evaluate",
    )
    parser.add_argument("--start-date", default=None, help="Optional inclusive start date")
    parser.add_argument("--end-date", default=None, help="Optional inclusive end date")
    parser.add_argument(
        "--portfolio-universe-size",
        type=int,
        default=20,
        help="Target universe size for PortfolioChoiceEnv",
    )
    parser.add_argument(
        "--portfolio-top-k",
        type=int,
        default=3,
        help="Top-k names to hold in the deterministic comparator",
    )
    parser.add_argument(
        "--portfolio-universe-tickers",
        nargs="+",
        default=None,
        help="Optional explicit universe tickers to override automatic universe selection",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional run name for artifacts/evaluation_baselines/<name>",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory (default: artifacts/evaluation_baselines/<name>)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.name or (
        f"portfolio_baseline_{_sanitize_name(args.mode)}_u{int(args.portfolio_universe_size)}"
        f"_k{int(args.portfolio_top_k)}"
    )
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path("artifacts") / "evaluation_baselines" / run_name
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    summary, daily_frames = run_portfolio_baseline(
        mode=args.mode,
        data_dir=args.data_dir,
        signal_prediction_dir=args.signal_prediction_dir,
        signal_columns=[str(column).strip() for column in args.signal_columns if str(column).strip()],
        strategies=[str(strategy).strip() for strategy in args.strategies if str(strategy).strip()],
        start_date=args.start_date,
        end_date=args.end_date,
        portfolio_universe_size=int(args.portfolio_universe_size),
        portfolio_top_k=int(args.portfolio_top_k),
        portfolio_universe_tickers=(
            [str(ticker).strip().upper() for ticker in args.portfolio_universe_tickers]
            if args.portfolio_universe_tickers
            else None
        ),
    )

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(_to_json_safe(summary), handle, ensure_ascii=True, indent=2)
    for strategy_name, daily in daily_frames.items():
        daily.to_parquet(output_dir / f"{strategy_name}_daily.parquet", index=False)

    print(f"Wrote deterministic portfolio baselines to {output_dir}")
    for strategy_name, stats in summary["strategies"].items():
        print(
            f"[{strategy_name}] total={stats['portfolio_total_return']:.4f} "
            f"relative={stats['relative_total_return']:.4f} "
            f"sharpe={stats['portfolio_sharpe_annualized']!s} "
            f"cash={stats['avg_cash_weight']:.4f}"
        )


if __name__ == "__main__":
    main()
