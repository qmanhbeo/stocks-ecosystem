"""Canonical runtime defaults exported as mutable dictionaries."""

from __future__ import annotations

from copy import deepcopy

from vn_stock_rl.config.types import EnvConfig, EvaluationConfig, PolicyConfig, TrainingConfig


DEFAULT_ENVIRONMENT = EnvConfig()
DEFAULT_TRAINING = TrainingConfig()
DEFAULT_EVALUATION = EvaluationConfig()

DEFAULT_POLICY_LIBRARY: dict[str, PolicyConfig] = {
    "mlp": PolicyConfig(
        model_kwargs={
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [256, 128, 128], "vf": [256, 128, 64]},
        },
    ),
    "cnn": PolicyConfig(
        model_kwargs={
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [128], "vf": [128]},
            "features_extractor_kwargs": {"features_dim": 128, "use_batch_norm": True},
        },
    ),
    "lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
    "cnn_lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "features_extractor_kwargs": {"features_dim": 128, "use_batch_norm": True},
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
    "multi_cnn": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 128,
            "n_epochs": 4,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.1,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [768, 384, 192, 56], "vf": [768, 384, 192, 56]},
            "features_extractor_kwargs": {
                "features_dim": 384,
                "multi_scale_windows": [3, 5, 10, 20, 30, 45, 60, 90],
                "branch_channels": 48,
            },
        },
    ),
    "multi_cnn_lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "features_extractor_kwargs": {
                "features_dim": 128,
                "multi_scale_windows": [5, 10, 20, 30, 60, 90],
                "branch_channels": 24,
            },
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
    "cnn_attention": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [128], "vf": [128]},
            "features_extractor_kwargs": {
                "features_dim": 128,
                "window_size": 15,
                "stride": 7,
                "cnn_channels": 64,
                "embed_dim": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pooling": "attention",
            },
        },
    ),
    "cnn_attention_lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "features_extractor_kwargs": {
                "features_dim": 128,
                "window_size": 15,
                "stride": 7,
                "cnn_channels": 64,
                "embed_dim": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pooling": "attention",
            },
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
    "cnn_window_attention": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [128], "vf": [128]},
            "features_extractor_kwargs": {
                "features_dim": 128,
                "window_size": 15,
                "stride": 7,
                "cnn_channels": 64,
                "embed_dim": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pooling": "window_attention",
            },
        },
    ),
    "cnn_window_attention_lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "features_extractor_kwargs": {
                "features_dim": 128,
                "window_size": 15,
                "stride": 7,
                "cnn_channels": 64,
                "embed_dim": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pooling": "window_attention",
            },
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
    "transformer": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "activation_fn": "relu",
            "net_arch": {"pi": [128], "vf": [128]},
            "features_extractor_kwargs": {
                "features_dim": 128,
                "d_model": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pos_encoding": "learnable",
                "pooling": "attention",
            },
        },
    ),
    "transformer_lstm": PolicyConfig(
        model_kwargs={
            "learning_rate": 1e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        },
        policy_kwargs={
            "features_extractor_kwargs": {
                "features_dim": 128,
                "d_model": 128,
                "n_heads": 4,
                "n_layers": 2,
                "dropout": 0.1,
                "pos_encoding": "learnable",
                "pooling": "attention",
            },
            "lstm_hidden_size": 128,
            "n_lstm_layers": 1,
            "enable_critic_lstm": True,
            "shared_lstm": False,
            "activation_fn": "relu",
            "net_arch": [],
        },
    ),
}

DEFAULT_CONFIG = DEFAULT_ENVIRONMENT.to_dict()
POLICY_CONFIGS = {name: cfg.to_dict() for name, cfg in DEFAULT_POLICY_LIBRARY.items()}
TRAIN_DEFAULTS = DEFAULT_TRAINING.to_dict()
EVAL_DEFAULTS = DEFAULT_EVALUATION.to_dict()

_BASE_DEFAULT_CONFIG = deepcopy(DEFAULT_CONFIG)
_BASE_POLICY_CONFIGS = deepcopy(POLICY_CONFIGS)
_BASE_TRAIN_DEFAULTS = deepcopy(TRAIN_DEFAULTS)
_BASE_EVAL_DEFAULTS = deepcopy(EVAL_DEFAULTS)


def reset_runtime_defaults() -> None:
    """Reset mutable runtime default dictionaries for tests and scripts."""

    DEFAULT_CONFIG.clear()
    DEFAULT_CONFIG.update(deepcopy(_BASE_DEFAULT_CONFIG))

    POLICY_CONFIGS.clear()
    POLICY_CONFIGS.update(deepcopy(_BASE_POLICY_CONFIGS))

    TRAIN_DEFAULTS.clear()
    TRAIN_DEFAULTS.update(deepcopy(_BASE_TRAIN_DEFAULTS))

    EVAL_DEFAULTS.clear()
    EVAL_DEFAULTS.update(deepcopy(_BASE_EVAL_DEFAULTS))
