"""
Count model parameters for one or more policy architectures.

Examples:
    vn-stock-count-params --stock ACB
    vn-stock-count-params --stock ACB --help-tickers VNINDEX VN30 --help-assets fx_vnd_usd gold oil
    vn-stock-count-params --stock ACB --policies mlp cnn transformer
    vn-stock-count-params --all-stocks --output-csv artifacts/param_counts.csv
"""

from __future__ import annotations

import argparse
import csv
import gc
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
from typing import List

import torch as th
from stable_baselines3 import PPO
from sb3_contrib import RecurrentPPO

from vn_stock_rl.config import POLICY_CONFIGS
from vn_stock_rl.policies.extractors.cnn_attention_extractor import (
    CNNAttentionExtractor,
    CNNAttentionExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.cnn_extractor import StockClassicCNNExtractor, StockMultiCNNExtractor
from vn_stock_rl.policies.extractors.cnn_lstm_extractor import (
    StockClassicCNNExtractorForLSTM,
    StockMultiCNNExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.cnn_window_attention_extractor import (
    CNNWindowAttentionExtractor,
    CNNWindowAttentionExtractorForLSTM,
)
from vn_stock_rl.policies.extractors.transformer_extractor import (
    StockTransformerExtractor,
    StockTransformerExtractorForLSTM,
)
from vn_stock_rl.policies.registry import available_policies, normalize_policy
from vn_stock_rl.training.env_builder import build_env_from_args, filter_help_tickers


ALL_POLICIES = available_policies()

INTERNAL_POLICY_MAP = {
    "mlp": "mlp",
    "lstm": "lstm",
    "cnn": "cnn",
    "cnn-lstm": "cnn_lstm",
    "cnn-attention": "cnn_attention",
    "cnn-attention-lstm": "cnn_attention_lstm",
    "cnn-window-attention": "cnn_window_attention",
    "cnn-window-attention-lstm": "cnn_window_attention_lstm",
    "multi-cnn": "multi_cnn",
    "multi-cnn-lstm": "multi_cnn_lstm",
    "transformer": "transformer",
    "transformer-lstm": "transformer_lstm",
}

DISPLAY_POLICY_MAP = {
    v: k for k, v in INTERNAL_POLICY_MAP.items()
}


def _normalize_policy(policy: str) -> str:
    normalized = normalize_policy(policy)
    if normalized in INTERNAL_POLICY_MAP.values():
        return normalized
    raise ValueError(f"Unknown policy '{policy}'. Valid options: {', '.join(ALL_POLICIES)}")


def _format_policy(policy_internal: str) -> str:
    return DISPLAY_POLICY_MAP.get(policy_internal, policy_internal)


def _build_env(args: argparse.Namespace):
    args.help_tickers = filter_help_tickers(args.help_tickers, args.stock, args.stocks, args.all_stocks)
    args.help_assets = [a.lower() for a in args.help_assets] if args.help_assets else None
    return build_env_from_args(args)


def _build_model(policy: str, env):
    if policy == "mlp":
        cfg = POLICY_CONFIGS["mlp"]
        policy_kwargs = {
            "activation_fn": th.nn.ReLU,
            "net_arch": {
                "pi": cfg["policy_kwargs"]["net_arch"]["pi"],
                "vf": cfg["policy_kwargs"]["net_arch"]["vf"],
            },
        }
        return PPO(
            "MlpPolicy",
            env,
            policy_kwargs=policy_kwargs,
            verbose=0,
            device="cpu",
            learning_rate=cfg["model_kwargs"]["learning_rate"],
            n_steps=cfg["model_kwargs"]["n_steps"],
            batch_size=cfg["model_kwargs"]["batch_size"],
            n_epochs=cfg["model_kwargs"]["n_epochs"],
            gamma=cfg["model_kwargs"]["gamma"],
            gae_lambda=cfg["model_kwargs"]["gae_lambda"],
            clip_range=cfg["model_kwargs"]["clip_range"],
        )

    if policy == "lstm":
        cfg = POLICY_CONFIGS["lstm"]
        policy_kwargs = {
            "lstm_hidden_size": cfg["policy_kwargs"]["lstm_hidden_size"],
            "n_lstm_layers": cfg["policy_kwargs"]["n_lstm_layers"],
            "enable_critic_lstm": cfg["policy_kwargs"]["enable_critic_lstm"],
            "shared_lstm": cfg["policy_kwargs"]["shared_lstm"],
            "activation_fn": th.nn.ReLU,
            "net_arch": cfg["policy_kwargs"]["net_arch"],
        }
        return RecurrentPPO(
            "MlpLstmPolicy",
            env,
            policy_kwargs=policy_kwargs,
            verbose=0,
            device="cpu",
            learning_rate=cfg["model_kwargs"]["learning_rate"],
            n_steps=cfg["model_kwargs"]["n_steps"],
            batch_size=cfg["model_kwargs"]["batch_size"],
            n_epochs=cfg["model_kwargs"]["n_epochs"],
            gamma=cfg["model_kwargs"]["gamma"],
            gae_lambda=cfg["model_kwargs"]["gae_lambda"],
            clip_range=cfg["model_kwargs"]["clip_range"],
        )

    lookback_window = int(getattr(env, "lookback_window"))

    recurrent_map = {
        "cnn_lstm": ("cnn_lstm", StockClassicCNNExtractorForLSTM),
        "cnn_attention_lstm": ("cnn_attention_lstm", CNNAttentionExtractorForLSTM),
        "cnn_window_attention_lstm": ("cnn_window_attention_lstm", CNNWindowAttentionExtractorForLSTM),
        "multi_cnn_lstm": ("multi_cnn_lstm", StockMultiCNNExtractorForLSTM),
        "transformer_lstm": ("transformer_lstm", StockTransformerExtractorForLSTM),
    }
    if policy in recurrent_map:
        cfg_key, extractor_cls = recurrent_map[policy]
        cfg = POLICY_CONFIGS[cfg_key]
        extractor_kwargs = dict(cfg["policy_kwargs"].get("features_extractor_kwargs", {}))
        extractor_kwargs["lookback_window"] = lookback_window
        policy_kwargs = {
            "features_extractor_class": extractor_cls,
            "features_extractor_kwargs": extractor_kwargs,
            "lstm_hidden_size": cfg["policy_kwargs"]["lstm_hidden_size"],
            "n_lstm_layers": cfg["policy_kwargs"]["n_lstm_layers"],
            "enable_critic_lstm": cfg["policy_kwargs"]["enable_critic_lstm"],
            "shared_lstm": cfg["policy_kwargs"]["shared_lstm"],
            "activation_fn": th.nn.ReLU,
            "net_arch": cfg["policy_kwargs"]["net_arch"],
        }
        return RecurrentPPO(
            "MlpLstmPolicy",
            env,
            policy_kwargs=policy_kwargs,
            verbose=0,
            device="cpu",
            learning_rate=cfg["model_kwargs"]["learning_rate"],
            n_steps=cfg["model_kwargs"]["n_steps"],
            batch_size=cfg["model_kwargs"]["batch_size"],
            n_epochs=cfg["model_kwargs"]["n_epochs"],
            gamma=cfg["model_kwargs"]["gamma"],
            gae_lambda=cfg["model_kwargs"]["gae_lambda"],
            clip_range=cfg["model_kwargs"]["clip_range"],
        )

    ppo_map = {
        "cnn": ("cnn", StockClassicCNNExtractor),
        "cnn_attention": ("cnn_attention", CNNAttentionExtractor),
        "cnn_window_attention": ("cnn_window_attention", CNNWindowAttentionExtractor),
        "multi_cnn": ("multi_cnn", StockMultiCNNExtractor),
        "transformer": ("transformer", StockTransformerExtractor),
    }
    if policy in ppo_map:
        cfg_key, extractor_cls = ppo_map[policy]
        cfg = POLICY_CONFIGS[cfg_key]
        extractor_kwargs = dict(cfg["policy_kwargs"].get("features_extractor_kwargs", {}))
        extractor_kwargs["lookback_window"] = lookback_window
        policy_kwargs = {
            "features_extractor_class": extractor_cls,
            "features_extractor_kwargs": extractor_kwargs,
            "activation_fn": th.nn.ReLU,
            "net_arch": {
                "pi": cfg["policy_kwargs"]["net_arch"]["pi"],
                "vf": cfg["policy_kwargs"]["net_arch"]["vf"],
            },
        }
        return PPO(
            "MlpPolicy",
            env,
            policy_kwargs=policy_kwargs,
            verbose=0,
            device="cpu",
            learning_rate=cfg["model_kwargs"]["learning_rate"],
            n_steps=cfg["model_kwargs"]["n_steps"],
            batch_size=cfg["model_kwargs"]["batch_size"],
            n_epochs=cfg["model_kwargs"]["n_epochs"],
            gamma=cfg["model_kwargs"]["gamma"],
            gae_lambda=cfg["model_kwargs"]["gae_lambda"],
            clip_range=cfg["model_kwargs"]["clip_range"],
        )

    raise ValueError(f"Unsupported policy: {policy}")


def _count_params(model) -> tuple[int, int, int]:
    total = sum(p.numel() for p in model.policy.parameters())
    trainable = sum(p.numel() for p in model.policy.parameters() if p.requires_grad)
    frozen = total - trainable
    return total, trainable, frozen


def _write_csv(path: str, rows: list[dict]):
    if not rows:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    headers = [
        "policy",
        "policy_internal",
        "total_params",
        "trainable_params",
        "frozen_params",
        "observation_shape",
        "action_space_n",
        "lookback_window",
        "status",
        "error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count parameters for one or more supported policies."
    )
    parser.add_argument("--stock", type=str, default=None, help="Single-stock ticker (e.g., ACB)")
    parser.add_argument(
        "--stocks",
        type=str,
        nargs="+",
        default=None,
        help="List of stocks for multi-stock mode (e.g., ACB VNM HPG)",
    )
    parser.add_argument(
        "--all-stocks",
        action="store_true",
        help="Use all stocks in --data-dir (multi-stock mode).",
    )
    parser.add_argument("--data-dir", type=str, default="data/stock/")
    parser.add_argument("--help-tickers", type=str, nargs="+", default=None)
    parser.add_argument("--market-data-dir", type=str, default="data/stock/")
    parser.add_argument("--help-assets", type=str, nargs="+", default=None)
    parser.add_argument("--help-assets-dir", type=str, default="data/fx-commodities/")
    parser.add_argument(
        "--policies",
        type=str,
        nargs="+",
        default=ALL_POLICIES.copy(),
        help="Subset of policies to count. Defaults to all.",
    )
    parser.add_argument("--output-csv", type=str, default=None, help="Optional CSV output path.")
    parser.add_argument("--sort", choices=["asc", "desc", "none"], default="desc")
    parser.add_argument("--stop-on-error", action="store_true")
    args = parser.parse_args()

    mode_count = sum([args.stock is not None, args.stocks is not None, args.all_stocks])
    if mode_count == 0:
        parser.error("Specify one of: --stock, --stocks, or --all-stocks")
    if mode_count > 1:
        parser.error("Only one mode is allowed: --stock, --stocks, or --all-stocks")

    try:
        selected = [_normalize_policy(p) for p in args.policies]
    except ValueError as exc:
        parser.error(str(exc))

    env = _build_env(args)
    obs_shape = tuple(env.observation_space.shape)
    action_n = int(getattr(env.action_space, "n", -1))
    lookback_window = int(getattr(env, "lookback_window", -1))

    print("=" * 80)
    print("PARAMETER COUNT")
    print("=" * 80)
    print(f"Observation shape: {obs_shape}")
    print(f"Action space n: {action_n}")
    print(f"Lookback window: {lookback_window}")
    print(f"Policies ({len(selected)}): {', '.join(_format_policy(p) for p in selected)}")
    print("=" * 80)

    rows = []
    for idx, policy in enumerate(selected, start=1):
        display = _format_policy(policy)
        print(f"[{idx}/{len(selected)}] {display} ... ", end="", flush=True)
        model = None
        error = ""
        status = "OK"
        total = trainable = frozen = 0
        try:
            model = _build_model(policy, env)
            total, trainable, frozen = _count_params(model)
            print(f"{total:,} params")
        except Exception as exc:
            status = "FAILED"
            error = str(exc)
            print(f"FAILED ({error})")
            if args.stop_on_error:
                rows.append(
                    {
                        "policy": display,
                        "policy_internal": policy,
                        "total_params": total,
                        "trainable_params": trainable,
                        "frozen_params": frozen,
                        "observation_shape": str(obs_shape),
                        "action_space_n": action_n,
                        "lookback_window": lookback_window,
                        "status": status,
                        "error": error,
                    }
                )
                break
        finally:
            if model is not None:
                del model
            gc.collect()

        rows.append(
            {
                "policy": display,
                "policy_internal": policy,
                "total_params": total,
                "trainable_params": trainable,
                "frozen_params": frozen,
                "observation_shape": str(obs_shape),
                "action_space_n": action_n,
                "lookback_window": lookback_window,
                "status": status,
                "error": error,
            }
        )

    if args.sort != "none":
        reverse = args.sort == "desc"
        rows.sort(key=lambda r: int(r["total_params"]), reverse=reverse)

    print()
    print("policy,total_params,trainable_params,frozen_params,status")
    for row in rows:
        print(
            f"{row['policy']},{row['total_params']},{row['trainable_params']},"
            f"{row['frozen_params']},{row['status']}"
        )

    if args.output_csv:
        _write_csv(args.output_csv, rows)
        print(f"\nSaved CSV: {args.output_csv}")

    failed = sum(1 for row in rows if row["status"] != "OK")
    print()
    print(f"Completed: {len(rows)} | Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
