from __future__ import annotations

import json
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from vn_stock_rl.env import PortfolioChoiceEnv, TradingEnv
from vn_stock_rl.config import EVAL_DEFAULTS
from vn_stock_rl.config.cli_shared import (
    parse_engineered_feature_families,
    parse_helper_window_list,
    parse_news_feature_columns,
    parse_reward_benchmark,
    parse_rs_market_proxies,
    parse_signal_feature_columns,
    parse_window_list,
)
from vn_stock_rl.evaluation.metadata import (
    _load_eval_meta,
    _merge_env_overrides,
    _read_policy_from_metadata,
    _resolve_helper_inputs_from_meta,
)
from vn_stock_rl.evaluation.reporting import _extract_trades, _persist_eval_outputs

ENGINEERED_FEATURE_FAMILIES = (
    "volatility",
    "trend",
    "momentum",
    "volume_context",
    "drawdown",
    "relative_strength",
)

_parse_window_list = parse_window_list
_parse_helper_window_list = parse_helper_window_list
_parse_engineered_feature_families = parse_engineered_feature_families
_parse_rs_market_proxies = parse_rs_market_proxies
_parse_news_feature_columns = parse_news_feature_columns
_parse_signal_feature_columns = parse_signal_feature_columns
_parse_reward_benchmark = parse_reward_benchmark


def _sanitize_path_token(value: str) -> str:
    token = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value).strip())
    token = token.strip("_")
    return token or "unknown"


def _resolve_output_dir(
    output_dir: str,
    model_path: str,
    stock: Optional[str],
    mode: str,
    meta: Optional[Dict[str, Any]],
) -> str:
    default_root = Path(EVAL_DEFAULTS["output_dir"])
    requested_root = Path(output_dir)
    try:
        use_default_layout = requested_root == default_root
    except Exception:
        use_default_layout = str(requested_root) == str(default_root)

    if not use_default_layout:
        return output_dir

    run_name = None
    if isinstance(meta, dict):
        run_name = meta.get("model_name") or meta.get("run_name")
        if not run_name:
            model_best_path = meta.get("model_best_path")
            if isinstance(model_best_path, str) and model_best_path.strip():
                run_name = Path(model_best_path).parent.name
            elif meta.get("run_dir"):
                run_name = Path(str(meta["run_dir"])).name
    if not run_name:
        model_parent = Path(model_path).parent.name
        run_name = model_parent or Path(model_path).stem

    run_token = _sanitize_path_token(run_name)
    portfolio_mode = False
    if isinstance(meta, dict):
        portfolio_mode = bool(meta.get("portfolio_choice"))
        if not portfolio_mode:
            env_cfg = meta.get("environment_config")
            if isinstance(env_cfg, dict):
                portfolio_mode = bool(env_cfg.get("portfolio_choice"))
    stock_label = "PORTFOLIO" if portfolio_mode and not stock else str(stock or "UNKNOWN").upper()
    stock_token = _sanitize_path_token(stock_label)
    mode_token = _sanitize_path_token(mode.lower())
    return str(default_root / f"{run_token}__{stock_token}__{mode_token}")


def _meta_indicates_portfolio(meta: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(meta, dict):
        return False
    if meta.get("portfolio_choice") is not None:
        return bool(meta.get("portfolio_choice"))
    env_cfg = meta.get("environment_config")
    if not isinstance(env_cfg, dict):
        return False
    if env_cfg.get("portfolio_choice") is not None:
        return bool(env_cfg.get("portfolio_choice"))
    input_features = env_cfg.get("input_features")
    if not isinstance(input_features, dict):
        return False
    portfolio_features = input_features.get("portfolio_features")
    if not isinstance(portfolio_features, dict):
        return False
    return bool(portfolio_features.get("mode"))

def _load_model(model_path: str) -> Tuple[Any, str, bool]:
    """
    Load a model from disk and detect its type.
    
    Returns:
        model: Loaded model instance
        model_type: String description (e.g., 'LSTM', 'CNN', 'MLP')
        is_recurrent: Whether the model is recurrent (needs LSTM state)
    """
    try:
        from stable_baselines3 import PPO
        from sb3_contrib import RecurrentPPO
        # Import custom extractors so SB3 can deserialize them
        from vn_stock_rl.policies.extractors.cnn_extractor import (
            StockClassicCNNExtractor,
            StockMultiCNNExtractor,
            StockCNNExtractor,
        )  # noqa: F401
        from vn_stock_rl.policies.extractors.cnn_lstm_extractor import (
            StockClassicCNNExtractorForLSTM,
            StockMultiCNNExtractorForLSTM,
            StockCNNExtractorForLSTM,
        )  # noqa: F401
        from vn_stock_rl.policies.extractors.cnn_attention_extractor import (
            CNNAttentionExtractor,
            CNNAttentionExtractorForLSTM,
        )  # noqa: F401
        from vn_stock_rl.policies.extractors.cnn_window_attention_extractor import (
            CNNWindowAttentionExtractor,
            CNNWindowAttentionExtractorForLSTM,
        )  # noqa: F401
        from vn_stock_rl.policies.extractors.transformer_extractor import (
            StockTransformerExtractor,
            StockTransformerExtractorForLSTM,
        )  # noqa: F401
    except Exception as e:
        raise ImportError(
            "Missing dependencies for model loading. "
            "Install stable-baselines3 and sb3-contrib, and ensure custom extractors are available."
        ) from e

    meta_policy = _read_policy_from_metadata(model_path)
    
    # Try to load as RecurrentPPO first, then fall back to PPO
    try:
        model = RecurrentPPO.load(model_path)
        extractor_name = type(model.policy.features_extractor).__name__ if hasattr(model.policy, 'features_extractor') else ""
        if extractor_name == "StockMultiCNNExtractorForLSTM":
            model_type = "MULTI-CNN+LSTM"
        elif extractor_name == "StockClassicCNNExtractorForLSTM":
            model_type = "CNN+LSTM"
        elif extractor_name == "CNNAttentionExtractorForLSTM":
            model_type = "CNN-ATTENTION+LSTM"
        elif extractor_name == "CNNWindowAttentionExtractorForLSTM":
            model_type = "CNN-WINDOW-ATTENTION+LSTM"
        elif extractor_name == "StockTransformerExtractorForLSTM":
            model_type = "TRANSFORMER+LSTM"
        elif extractor_name == "StockCNNExtractorForLSTM":
            # Compatibility wrapper class. Use metadata when available.
            if meta_policy == "multi-cnn-lstm":
                model_type = "MULTI-CNN+LSTM"
            else:
                model_type = "CNN+LSTM"
        else:
            if meta_policy == "cnn-attention-lstm":
                model_type = "CNN-ATTENTION+LSTM"
            elif meta_policy == "cnn-window-attention-lstm":
                model_type = "CNN-WINDOW-ATTENTION+LSTM"
            elif meta_policy == "transformer-lstm":
                model_type = "TRANSFORMER+LSTM"
            else:
                model_type = "LSTM"
        return model, model_type, True
    except Exception:
        try:
            model = PPO.load(model_path)
            extractor_name = type(model.policy.features_extractor).__name__ if hasattr(model.policy, 'features_extractor') else ""
            if extractor_name == "StockMultiCNNExtractor":
                model_type = "MULTI-CNN"
            elif extractor_name == "StockClassicCNNExtractor":
                model_type = "CNN"
            elif extractor_name == "CNNAttentionExtractor":
                model_type = "CNN-ATTENTION"
            elif extractor_name == "CNNWindowAttentionExtractor":
                model_type = "CNN-WINDOW-ATTENTION"
            elif extractor_name == "StockTransformerExtractor":
                model_type = "TRANSFORMER"
            elif extractor_name == "StockCNNExtractor":
                # Compatibility wrapper class. Use metadata when available.
                if meta_policy == "multi-cnn":
                    model_type = "MULTI-CNN"
                else:
                    model_type = "CNN"
            else:
                if meta_policy == "cnn-attention":
                    model_type = "CNN-ATTENTION"
                elif meta_policy == "cnn-window-attention":
                    model_type = "CNN-WINDOW-ATTENTION"
                elif meta_policy == "transformer":
                    model_type = "TRANSFORMER"
                else:
                    model_type = "MLP"
            return model, model_type, False
        except Exception as e:
            raise ValueError(f"Could not load model: {e}")

def _resolve_include_can_exit(
    forced_policy: Optional[str],
    expected_obs_dim: Optional[int],
    data_path: str,
    mode: str,
    help_tickers: Optional[list],
    market_data_dir: str,
    help_assets: Optional[list],
    help_assets_dir: str,
    env_kwargs: Dict[str, Any],
) -> bool:
    if forced_policy:
        return True
    probe_env = TradingEnv(
        data_path=data_path,
        mode=mode,
        include_can_exit=True,
        help_tickers=help_tickers,
        market_data_dir=market_data_dir,
        help_assets=help_assets,
        help_assets_dir=help_assets_dir,
        **env_kwargs
    )
    feature_dim = int(probe_env.n_features)
    expected_with_can_exit = feature_dim + 3
    expected_without_can_exit = feature_dim + 2
    probe_env.close()
    if expected_obs_dim == expected_with_can_exit:
        return True
    if expected_obs_dim == expected_without_can_exit:
        return False
    raise ValueError(
        "Model observation size does not match environment feature layout. "
        f"Model expects {expected_obs_dim}, while environment expects either "
        f"{expected_without_can_exit} (without can_exit) or "
        f"{expected_with_can_exit} (with can_exit). "
        "Check model/data/helper-feature compatibility."
    )

def _run_evaluation_episode(
    env,
    model: Any,
    is_recurrent: bool,
    deterministic: bool,
    forced_policy: Optional[str],
    render: bool,
) -> pd.DataFrame:
    obs, _info = env.reset()
    lstm_states = None
    episode_start = np.ones((1,), dtype=bool)
    portfolio_mode = bool(getattr(env, "portfolio_choice", False))
    history = {
        'step': [],
        'date': [],
        'open': [],
        'close': [],
        'position': [],
        'hold_count': [],
        'action': [],
        'reward': [],
        'raw_return': [],
        'benchmark_return': [],
        'excess_return': [],
        'drawdown_penalty': [],
        'portfolio_value': [],
        'benchmark_portfolio_value': [],
    }
    if portfolio_mode:
        history['num_holdings'] = []
        history['avg_holding_age'] = []
        history['cash_weight'] = []
        history['selected_tickers'] = []
    history_step = history['step']
    history_date = history['date']
    history_open = history['open']
    history_close = history['close']
    history_position = history['position']
    history_hold_count = history['hold_count']
    history_action = history['action']
    history_reward = history['reward']
    history_raw_return = history['raw_return']
    history_benchmark_return = history['benchmark_return']
    history_excess_return = history['excess_return']
    history_drawdown_penalty = history['drawdown_penalty']
    history_portfolio_value = history['portfolio_value']
    history_benchmark_portfolio_value = history['benchmark_portfolio_value']
    history_num_holdings = history.get('num_holdings')
    history_avg_holding_age = history.get('avg_holding_age')
    history_cash_weight = history.get('cash_weight')
    history_selected_tickers = history.get('selected_tickers')
    time_values = env.df['time'].to_numpy()
    open_values = env.df['open'].to_numpy()
    close_values = env.df['close'].to_numpy()

    done = False
    portfolio_value = 1.0
    while not done:
        if forced_policy == "flat":
            if portfolio_mode:
                action_value = np.full(
                    env.portfolio_top_k,
                    env.portfolio_universe_size,
                    dtype=np.int64,
                )
            else:
                action_value = 0
        elif forced_policy == "buy_hold":
            if portfolio_mode:
                picks = list(range(min(env.portfolio_top_k, env.portfolio_universe_size)))
                while len(picks) < env.portfolio_top_k:
                    picks.append(env.portfolio_universe_size)
                action_value = np.asarray(picks, dtype=np.int64)
            else:
                action_value = 1
        else:
            if is_recurrent:
                action, lstm_states = model.predict(
                    obs,
                    state=lstm_states,
                    episode_start=episode_start,
                    deterministic=deterministic
                )
                episode_start[0] = False
            else:
                action, _states = model.predict(obs, deterministic=deterministic)
            if portfolio_mode:
                action_value = np.asarray(action, dtype=np.int64).reshape(-1)
            else:
                action_value = int(np.asarray(action).squeeze())

        current_step = env.current_step
        history_step.append(current_step)
        history_date.append(time_values[current_step])
        history_open.append(open_values[current_step])
        history_close.append(close_values[current_step])
        history_position.append(env.position)
        history_hold_count.append(np.nan if portfolio_mode else env.hold_count)
        if portfolio_mode:
            history_action.append(json.dumps(np.asarray(action_value, dtype=np.int64).reshape(-1).tolist()))
        else:
            history_action.append(action_value)

        obs, reward, terminated, truncated, info = env.step(action_value)
        raw_return = float(info.get('raw_return', reward))
        benchmark_return = float(info.get('benchmark_return', 0.0))
        excess_return = float(info.get('excess_return', raw_return - benchmark_return))
        drawdown_penalty = float(info.get('drawdown_penalty', 0.0))
        portfolio_value *= (1 + raw_return)
        history_reward.append(float(reward))
        history_raw_return.append(raw_return)
        history_benchmark_return.append(benchmark_return)
        history_excess_return.append(excess_return)
        history_drawdown_penalty.append(drawdown_penalty)
        history_portfolio_value.append(portfolio_value)
        history_benchmark_portfolio_value.append(float(info.get('benchmark_portfolio_value', 1.0)))
        if portfolio_mode:
            history_num_holdings.append(int(info.get('num_holdings', getattr(env, 'num_holdings', 0))))
            history_avg_holding_age.append(float(info.get('avg_holding_age', getattr(env, 'avg_holding_age', 0.0))))
            history_cash_weight.append(float(info.get('cash_weight', 0.0)))
            history_selected_tickers.append(json.dumps(info.get('selected_tickers', [])))
        if render:
            env.render()
        done = terminated or truncated

    return pd.DataFrame(history)

def _compute_eval_metrics(
    df_history: pd.DataFrame,
    env,
    stats: Dict[str, Any],
    model_type: str,
    mode: str,
    include_can_exit: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    portfolio_mode = bool(getattr(env, "portfolio_choice", False))
    rl_agent_return = float(df_history['portfolio_value'].iloc[-1] - 1.0)
    daily_returns = df_history['raw_return'].to_numpy(dtype=np.float64)
    sharpe = np.mean(daily_returns) / np.std(daily_returns) if np.std(daily_returns) > 0 else 0.0
    sharpe_annualized = float(sharpe * np.sqrt(252))
    portfolio_values = df_history['portfolio_value'].to_numpy(dtype=np.float64)
    running_max = np.maximum.accumulate(portfolio_values)
    drawdown = (portfolio_values - running_max) / running_max
    max_drawdown = float(np.min(drawdown))

    metrics = {
        "model_type": model_type,
        "mode": mode,
        "portfolio_choice": bool(portfolio_mode),
        "total_return_additive": stats["total_return"],
        "rl_return_geometric": rl_agent_return,
        "num_trade_executions": stats["num_trades"],
        "num_winning_trades": stats["num_winning_trades"],
        "win_rate": float(stats["win_rate"]),
        "avg_trade_return": float(stats["avg_trade_return"]),
        "total_steps": stats["total_steps"],
        "reward_mode": stats.get("reward_mode"),
        "reward_benchmark": stats.get("reward_benchmark"),
        "benchmark_weight": float(stats.get("benchmark_weight", 1.0)),
        "sharpe_annualized": sharpe_annualized,
        "max_drawdown": max_drawdown,
        "env_lookback_window": int(getattr(env, "lookback_window", 0)),
        "env_min_hold_days": int(getattr(env, "min_hold_days", 0)),
        "env_buy_fee_rate": float(env.buy_fee_rate),
        "env_sell_fee_rate": float(env.sell_fee_rate),
        "env_capital_gains_tax_rate": float(env.capital_gains_tax_rate),
        "env_stop_loss": (
            float(env.stop_loss)
            if getattr(env, "stop_loss", None) is not None
            else None
        ),
        "env_source_mode": str(getattr(env, "source_mode", "return")),
        "env_ohlcv": list(getattr(env, "ohlcv_fields", [])),
        "env_calendar_features": list(getattr(env, "calendar_features", [])),
        "env_normalize": bool(getattr(env, "normalize", False)),
        "env_include_can_exit": bool(include_can_exit),
    }

    if portfolio_mode:
        benchmark_series = df_history["benchmark_portfolio_value"].to_numpy(dtype=np.float64)
        naive_buy_hold_return = float(benchmark_series[-1] - 1.0)
        aligned_buy_hold_return = naive_buy_hold_return
        aligned_buy_hold_series = benchmark_series
        time_in_market = float((df_history["num_holdings"].to_numpy(dtype=np.float64) > 0).mean())
        metrics.update(
            {
                "buy_hold_naive": naive_buy_hold_return,
                "buy_hold_aligned": aligned_buy_hold_return,
                "time_in_market": time_in_market,
                "avg_num_holdings": float(df_history["num_holdings"].mean()),
                "avg_holding_age": float(df_history["avg_holding_age"].mean()),
                "avg_cash_weight": float(df_history["cash_weight"].mean()),
                "env_portfolio_universe_size": int(getattr(env, "portfolio_universe_size", 0)),
                "env_portfolio_top_k": int(getattr(env, "portfolio_top_k", 0)),
                "env_portfolio_universe_tickers": list(getattr(env, "universe_tickers", [])),
                "total_trades_completed": int(stats["num_trades"]),
                "avg_hold_days": None,
            }
        )
    else:
        steps = df_history['step'].values
        open_exec = env.df['open'].values[steps + 1]
        naive_buy_hold_return = float((open_exec[-1] / open_exec[0]) - 1.0)

        entry_exec_idx = env.episode_start_idx + 2
        aligned_buy_hold_series = None
        aligned_buy_hold_return = None
        if entry_exec_idx < len(env.df):
            entry_exec_price = env.df.iloc[entry_exec_idx]['open']
            aligned_buy_hold_series = np.where(
                (steps + 1) < entry_exec_idx,
                1.0,
                (1 - env.buy_fee_rate) * (open_exec / entry_exec_price)
            )
            aligned_buy_hold_return = float(aligned_buy_hold_series[-1] - 1.0)

        time_in_market = float((df_history['position'] == 1).sum() / len(df_history))
        metrics.update(
            {
                "buy_hold_naive": naive_buy_hold_return,
                "buy_hold_aligned": (
                    float(aligned_buy_hold_return) if aligned_buy_hold_return is not None else None
                ),
                "time_in_market": time_in_market,
            }
        )
        df_trades = _extract_trades(
            df_history,
            buy_fee_rate=float(env.buy_fee_rate),
            sell_fee_rate=float(env.sell_fee_rate),
            capital_gains_tax_rate=float(env.capital_gains_tax_rate),
        )
        if not df_trades.empty:
            metrics["total_trades_completed"] = int(len(df_trades))
            metrics["avg_hold_days"] = float(df_trades["hold_days"].mean())
        else:
            metrics["total_trades_completed"] = 0
            metrics["avg_hold_days"] = None

    summary = {
        "naive_buy_hold_return": float(naive_buy_hold_return),
        "aligned_buy_hold_return": (
            float(aligned_buy_hold_return) if aligned_buy_hold_return is not None else None
        ),
        "aligned_buy_hold_series": aligned_buy_hold_series,
        "rl_agent_return": rl_agent_return,
        "time_in_market": float(time_in_market),
        "sharpe_annualized": sharpe_annualized,
        "max_drawdown": max_drawdown,
    }
    return metrics, summary

def evaluate_model(
    model_path: str,
    stock: Optional[str],
    portfolio_choice: Optional[bool] = None,
    portfolio_universe_size: Optional[int] = None,
    portfolio_top_k: Optional[int] = None,
    data_dir: str = "data/stock/",
    help_tickers: Optional[list] = None,
    market_data_dir: str = "data/stock/",
    help_assets: Optional[list] = None,
    help_assets_dir: str = "data/fx-commodities/",
    mode: str = 'test',  # 'train', 'val', or 'test'
    output_dir: str = EVAL_DEFAULTS["output_dir"],
    deterministic: bool = True,
    render: bool = False,
    forced_policy: Optional[str] = None,
    metrics_only: bool = False,
    lookback_window: Optional[int] = None,
    drawdown_penalty_enabled: Optional[bool] = None,
    drawdown_penalty_lambda: Optional[float] = None,
    drawdown_penalty_train_only: Optional[bool] = None,
    reward_benchmark: Optional[str] = None,
    benchmark_weight: Optional[float] = None,
    benchmark_relative_reward: Optional[bool] = None,
    train_episode_sampling_enabled: Optional[bool] = None,
    train_episode_min_fraction: Optional[float] = None,
    train_episode_max_fraction: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source_mode: Optional[str] = None,
    ma_windows: Optional[list] = None,
    helpers_ma_windows: Optional[list] = None,
    returns_windows: Optional[list] = None,
    helpers_returns_windows: Optional[list] = None,
    engineered_features: Optional[list] = None,
    window_policy: Optional[str] = None,
    feature_windows: Optional[list] = None,
    logspace_min: Optional[int] = None,
    logspace_max: Optional[int] = None,
    logspace_count: Optional[int] = None,
    rs_market_proxies: Optional[list] = None,
    rs_include_long: Optional[bool] = None,
    calendar_features: Optional[list] = None,
    news_feature_columns: Optional[list] = None,
    news_prediction_dir: Optional[str] = None,
    signal_feature_columns: Optional[list] = None,
    signal_prediction_dir: Optional[str] = None,
    train_split: Optional[float] = None,
    val_split: Optional[float] = None,
    min_hold_days: Optional[int] = None,
    buy_fee_rate: Optional[float] = None,
    sell_fee_rate: Optional[float] = None,
    capital_gains_tax_rate: Optional[float] = None,
    stop_loss: Optional[float] = None,
):
    """
    Evaluate a trained model and generate detailed analysis.
    
    Args:
        model_path: Path to saved model (.zip file)
        stock: Stock ticker (e.g., 'ACB'). Optional in portfolio mode.
        portfolio_choice: Override metadata and evaluate as portfolio-choice env
        portfolio_universe_size: Optional portfolio universe-size override
        portfolio_top_k: Optional portfolio top-k override
        data_dir: Directory containing parquet files
        help_tickers: Optional list of helper tickers to append as features
        market_data_dir: Directory containing market parquet files
        mode: Which data split to evaluate on ('train', 'val', or 'test')
        output_dir: Root directory to save results
        deterministic: Use deterministic actions (no exploration)
        render: Print step-by-step info
        forced_policy: Force actions without loading a model ('flat' or 'buy_hold')
        metrics_only: If True, only write metrics_summary.json (skip plots/history/trades files)
        lookback_window/drawdown_penalty_*/benchmark_relative_reward/reward_benchmark/benchmark_weight/train_episode_sampling_*/start_date/end_date/source_mode/ma_windows/helpers_ma_windows/returns_windows/helpers_returns_windows/engineered_features/window_policy/feature_windows/logspace_*/rs_*/calendar_features/news_feature_columns/news_prediction_dir/signal_feature_columns/signal_prediction_dir/train_split/val_split/min_hold_days/buy_fee_rate/sell_fee_rate/
            capital_gains_tax_rate/stop_loss: Optional env overrides.
            If not provided, values are auto-loaded from model metadata when available.
    """
    if forced_policy not in (None, "flat", "buy_hold"):
        raise ValueError("forced_policy must be None, 'flat', or 'buy_hold'")
    if window_policy is not None:
        parsed_policy = str(window_policy).strip().lower()
        if parsed_policy not in {"explicit", "logspace"}:
            raise ValueError(f"--window-policy must be 'explicit' or 'logspace', got {window_policy}")
    if drawdown_penalty_lambda is not None:
        drawdown_penalty_lambda = float(drawdown_penalty_lambda)
        if drawdown_penalty_lambda < 0.0:
            raise ValueError(
                f"--drawdown-penalty-lambda must be >= 0.0, got {drawdown_penalty_lambda}"
            )
    reward_benchmark = _parse_reward_benchmark(reward_benchmark)
    if benchmark_weight is not None:
        benchmark_weight = float(benchmark_weight)
        if benchmark_weight < 0.0:
            raise ValueError(
                f"--benchmark-weight must be >= 0.0, got {benchmark_weight}"
            )
    if train_episode_min_fraction is not None:
        train_episode_min_fraction = float(train_episode_min_fraction)
        if not (0.0 < train_episode_min_fraction <= 1.0):
            raise ValueError(
                f"--train-episode-min-fraction must be in (0,1], got {train_episode_min_fraction}"
            )
    if train_episode_max_fraction is not None:
        train_episode_max_fraction = float(train_episode_max_fraction)
        if not (0.0 < train_episode_max_fraction <= 1.0):
            raise ValueError(
                f"--train-episode-max-fraction must be in (0,1], got {train_episode_max_fraction}"
            )
    if (
        train_episode_min_fraction is not None
        and train_episode_max_fraction is not None
        and train_episode_min_fraction > train_episode_max_fraction
    ):
        raise ValueError(
            "--train-episode-min-fraction must be <= --train-episode-max-fraction, got "
            f"{train_episode_min_fraction} > {train_episode_max_fraction}"
        )

    meta = _load_eval_meta(model_path)
    if portfolio_universe_size is not None and int(portfolio_universe_size) < 1:
        raise ValueError(f"--portfolio-universe-size must be >= 1, got {portfolio_universe_size}")
    if portfolio_top_k is not None and int(portfolio_top_k) < 1:
        raise ValueError(f"--portfolio-top-k must be >= 1, got {portfolio_top_k}")
    resolved_portfolio_choice = (
        _meta_indicates_portfolio(meta) if portfolio_choice is None else bool(portfolio_choice)
    )
    if not resolved_portfolio_choice and not stock:
        raise ValueError("Single-stock evaluation requires --stock")
    help_tickers, market_data_dir, help_assets, help_assets_dir = _resolve_helper_inputs_from_meta(
        meta,
        help_tickers,
        market_data_dir,
        help_assets,
        help_assets_dir,
    )

    stock_label = stock or ("PORTFOLIO" if resolved_portfolio_choice else None)
    output_dir = _resolve_output_dir(output_dir, model_path, stock_label, mode, meta)
    os.makedirs(output_dir, exist_ok=True)
    data_path = (
        None
        if resolved_portfolio_choice
        else os.path.join(data_dir, f"gia_lich_su_{stock}_1D.parquet")
    )

    print("="*60)
    print("Model Evaluation")
    print("="*60)
    print(f"Model: {model_path}")
    if resolved_portfolio_choice:
        print("Mode: Portfolio-Choice")
        print(f"Data directory: {data_dir}")
    else:
        print(f"Stock: {stock}")
        print(f"Data: {data_path}")
    if help_tickers and not resolved_portfolio_choice:
        print(f"Help Tickers: {', '.join(help_tickers)}")
        print(f"Market Data Dir: {market_data_dir}")
    if help_assets and not resolved_portfolio_choice:
        print(f"Help Assets: {', '.join(help_assets)}")
        print(f"Help Assets Dir: {help_assets_dir}")
    print(f"Mode: {mode}")
    print(f"Output Dir: {output_dir}")
    print(f"Deterministic: {deterministic}")
    print(f"Metrics Only: {metrics_only}")
    if forced_policy:
        print(f"Forced Policy: {forced_policy}")
    print("="*60 + "\n")

    print("Loading model and environment...")
    model = None
    is_recurrent = False
    expected_obs_dim = None
    if forced_policy:
        model_type = "FORCED-FLAT" if forced_policy == "flat" else "FORCED-BUY_HOLD"
        print(f"[OK] Forced policy active ({model_type}) - skipping model load")
    else:
        model, model_type, is_recurrent = _load_model(model_path)
        expected_obs_dim = int(model.observation_space.shape[0])
        if model_type == "MULTI-CNN+LSTM":
            print("[OK] Loaded RecurrentPPO (MULTI-CNN+LSTM) model")
        elif model_type == "CNN+LSTM":
            print("[OK] Loaded RecurrentPPO (CNN+LSTM) model")
        elif model_type == "CNN-ATTENTION+LSTM":
            print("[OK] Loaded RecurrentPPO (CNN-ATTENTION+LSTM) model")
        elif model_type == "CNN-WINDOW-ATTENTION+LSTM":
            print("[OK] Loaded RecurrentPPO (CNN-WINDOW-ATTENTION+LSTM) model")
        elif model_type == "TRANSFORMER+LSTM":
            print("[OK] Loaded RecurrentPPO (TRANSFORMER+LSTM) model")
        elif model_type == "LSTM":
            print("[OK] Loaded RecurrentPPO (LSTM) model")
        elif model_type == "MULTI-CNN":
            print("[OK] Loaded PPO (MULTI-CNN) model")
        elif model_type == "CNN":
            print("[OK] Loaded PPO (CNN) model")
        elif model_type == "CNN-ATTENTION":
            print("[OK] Loaded PPO (CNN-ATTENTION) model")
        elif model_type == "CNN-WINDOW-ATTENTION":
            print("[OK] Loaded PPO (CNN-WINDOW-ATTENTION) model")
        elif model_type == "TRANSFORMER":
            print("[OK] Loaded PPO (TRANSFORMER) model")
        else:
            print("[OK] Loaded PPO (MLP) model")

    explicit_env_overrides = {
        "portfolio_choice": resolved_portfolio_choice,
        "portfolio_universe_size": portfolio_universe_size,
        "portfolio_top_k": portfolio_top_k,
        "lookback_window": lookback_window,
        "drawdown_penalty_enabled": drawdown_penalty_enabled,
        "drawdown_penalty_lambda": drawdown_penalty_lambda,
        "drawdown_penalty_train_only": drawdown_penalty_train_only,
        "reward_benchmark": reward_benchmark,
        "benchmark_weight": benchmark_weight,
        "benchmark_relative_reward": benchmark_relative_reward,
        "train_episode_sampling_enabled": train_episode_sampling_enabled,
        "train_episode_min_fraction": train_episode_min_fraction,
        "train_episode_max_fraction": train_episode_max_fraction,
        "start_date": start_date,
        "end_date": end_date,
        "source_mode": source_mode,
        "ma_windows": _parse_window_list(ma_windows, "--ma-windows"),
        "helpers_ma_windows": _parse_helper_window_list(helpers_ma_windows, "--helpers-ma-windows"),
        "returns_windows": _parse_window_list(returns_windows, "--returns-windows"),
        "helpers_returns_windows": _parse_helper_window_list(
            helpers_returns_windows,
            "--helpers-returns-windows",
        ),
        "engineered_features": _parse_engineered_feature_families(engineered_features),
        "window_policy": (str(window_policy).strip().lower() if window_policy is not None else None),
        "feature_windows": _parse_window_list(feature_windows, "--feature-windows"),
        "logspace_min": logspace_min,
        "logspace_max": logspace_max,
        "logspace_count": logspace_count,
        "rs_market_proxies": _parse_rs_market_proxies(rs_market_proxies),
        "rs_include_long": rs_include_long,
        "calendar_features": calendar_features,
        "news_feature_columns": _parse_news_feature_columns(news_feature_columns),
        "news_prediction_dir": news_prediction_dir,
        "signal_feature_columns": _parse_signal_feature_columns(signal_feature_columns),
        "signal_prediction_dir": signal_prediction_dir,
        "train_split": train_split,
        "val_split": val_split,
        "min_hold_days": min_hold_days,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "capital_gains_tax_rate": capital_gains_tax_rate,
        "stop_loss": stop_loss,
    }
    env_kwargs = _merge_env_overrides(meta, explicit_env_overrides, forced_policy)
    portfolio_env_keys = {
        "portfolio_choice",
        "portfolio_universe_size",
        "portfolio_top_k",
        "portfolio_universe_tickers",
    }
    if not resolved_portfolio_choice:
        for key in portfolio_env_keys:
            env_kwargs.pop(key, None)
    env_kwargs["train_episode_sampling_enabled"] = False
    if not resolved_portfolio_choice:
        # Evaluation must be deterministic/comparable: disable randomized start-in-position.
        env_kwargs["start_episode_position"] = 0.0

    if help_tickers and not resolved_portfolio_choice:
        help_tickers = [t.upper() for t in help_tickers if t.upper() != stock.upper()]
        if not help_tickers:
            help_tickers = None
    if env_kwargs:
        env_desc = ", ".join(f"{k}={env_kwargs[k]}" for k in sorted(env_kwargs.keys()))
        print(f"Environment settings: {env_desc}")

    if resolved_portfolio_choice:
        portfolio_env_kwargs = {
            key: value
            for key, value in env_kwargs.items()
            if key in {
                "train_split",
                "val_split",
                "buy_fee_rate",
                "sell_fee_rate",
                "capital_gains_tax_rate",
                "drawdown_penalty_enabled",
                "drawdown_penalty_lambda",
                "drawdown_penalty_train_only",
                "reward_benchmark",
                "benchmark_weight",
                "benchmark_relative_reward",
                "train_episode_sampling_enabled",
                "train_episode_min_fraction",
                "train_episode_max_fraction",
                "start_date",
                "end_date",
                "signal_feature_columns",
                "signal_prediction_dir",
                "portfolio_universe_size",
                "portfolio_top_k",
                "portfolio_universe_tickers",
            }
        }
        include_can_exit = False
        env = PortfolioChoiceEnv(
            data_dir=data_dir,
            mode=mode,
            **portfolio_env_kwargs,
        )
    else:
        include_can_exit = _resolve_include_can_exit(
            forced_policy=forced_policy,
            expected_obs_dim=expected_obs_dim,
            data_path=data_path,
            mode=mode,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
            env_kwargs=env_kwargs,
        )

        env = TradingEnv(
            data_path=data_path,
            mode=mode,
            include_can_exit=include_can_exit,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
            **env_kwargs
        )
    print(f"Model type: {model_type}")
    if resolved_portfolio_choice:
        print(
            f"Resolved universe ({len(getattr(env, 'universe_tickers', []))}): "
            + ", ".join(getattr(env, "universe_tickers", []))
        )
    else:
        print(f"Observation compatibility: include_can_exit={include_can_exit}")
    print(f"\nEvaluation period:")
    if mode == 'train':
        print(f"  {env.train_start_date} to {env.train_end_date}")
        print(f"  ({env.train_end_idx - env.train_start_idx} days)")
    elif mode == 'val':
        print(f"  {env.val_start_date} to {env.val_end_date}")
        print(f"  ({env.val_end_idx - env.val_start_idx} days)")
    else:
        print(f"  {env.test_start_date} to {env.test_end_date}")
        print(f"  ({env.test_end_idx - env.test_start_idx} days)")
    print()

    print("Running evaluation episode...\n")
    df_history = _run_evaluation_episode(
        env=env,
        model=model,
        is_recurrent=is_recurrent,
        deterministic=deterministic,
        forced_policy=forced_policy,
        render=render,
    )

    stats = env.get_episode_stats()
    stats["buy_fee_rate"] = float(env.buy_fee_rate)
    stats["sell_fee_rate"] = float(env.sell_fee_rate)
    stats["capital_gains_tax_rate"] = float(env.capital_gains_tax_rate)

    print("\n" + "="*60)
    print("Evaluation Results")
    print("="*60)
    print(f"Model Type: {model_type}")
    reward_label = "Total Reward" if stats.get("reward_mode") != "raw_return" else "Total Return"
    print(f"{reward_label}: {stats['total_return']:.4f} ({stats['total_return']*100:.2f}%)")
    trade_label = "Rebalance Executions" if resolved_portfolio_choice else "Trade Executions (buy & sell)"
    print(f"{trade_label}: {stats['num_trades']}")
    print(f"Winning Trades: {stats['num_winning_trades']}")
    print(f"Win Rate: {stats['win_rate']:.2%}")
    print(f"Average Trade Return: {stats['avg_trade_return']:.4f}")
    print(f"Total Steps: {stats['total_steps']}")
    print("="*60)

    metrics, summary = _compute_eval_metrics(
        df_history=df_history,
        env=env,
        stats=stats,
        model_type=model_type,
        mode=mode,
        include_can_exit=include_can_exit,
    )
    naive_buy_hold_return = summary["naive_buy_hold_return"]
    aligned_buy_hold_return = summary["aligned_buy_hold_return"]
    aligned_buy_hold_series = summary["aligned_buy_hold_series"]
    rl_agent_return = summary["rl_agent_return"]
    time_in_market = summary["time_in_market"]
    sharpe_annualized = summary["sharpe_annualized"]
    max_drawdown = summary["max_drawdown"]

    print("\nAdditional Metrics:")
    print("-"*60)
    benchmark_label = "Equal-Weight Universe Benchmark" if resolved_portfolio_choice else "Buy & Hold Return"
    print(f"{benchmark_label} (naive): {naive_buy_hold_return:.4f} ({naive_buy_hold_return*100:.2f}%)")
    if aligned_buy_hold_return is not None and not resolved_portfolio_choice:
        print(
            f"Buy & Hold Return (execution-aligned, buy fee): "
            f"{aligned_buy_hold_return:.4f} ({aligned_buy_hold_return*100:.2f}%)"
        )
    elif not resolved_portfolio_choice:
        print("Buy & Hold Return (execution-aligned): N/A (episode too short)")
    print(f"RL Agent Return: {rl_agent_return:.4f} ({rl_agent_return*100:.2f}%)")
    if aligned_buy_hold_return is not None:
        print(f"Outperformance vs aligned: {(rl_agent_return - aligned_buy_hold_return)*100:.2f}%")
    else:
        print(f"Outperformance vs naive: {(rl_agent_return - naive_buy_hold_return)*100:.2f}%")
    additive_label = "reward" if stats.get("reward_mode") != "raw_return" else "return"
    print(f"\nNote: Environment's additive {additive_label}: {stats['total_return']:.4f} (for reference only)")
    print(f"Time in Market: {time_in_market:.2%}")
    print(f"Sharpe Ratio (annualized): {sharpe_annualized:.2f}")
    print(f"Max Drawdown: {max_drawdown:.4f} ({max_drawdown*100:.2f}%)")
    print("-"*60)

    _persist_eval_outputs(
        output_dir=output_dir,
        metrics_only=metrics_only,
        df_history=df_history,
        stats=stats,
        model_type=model_type,
        stock=(stock or "PORTFOLIO"),
        mode=mode,
        aligned_buy_hold_series=aligned_buy_hold_series,
        metrics=metrics,
    )
    return df_history, stats
