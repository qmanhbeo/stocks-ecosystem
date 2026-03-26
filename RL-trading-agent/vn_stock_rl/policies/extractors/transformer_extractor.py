"""
Transformer-based feature extractors for trading observations.

This module provides:
- StockTransformerExtractor: self-attention extractor for PPO
- StockTransformerExtractorForLSTM: self-attention extractor for RecurrentPPO
"""

import math

import torch as th
import torch.nn as nn
import torch.nn.functional as F
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


VALID_POS_ENCODINGS = {"learnable", "sinusoidal"}
VALID_POOLINGS = {"mean", "last", "cls", "attention"}


def _validate_observation_layout(observation_space: spaces.Box, lookback_window: int) -> tuple[int, int]:
    if lookback_window <= 0:
        raise ValueError(f"lookback_window must be > 0, got {lookback_window}")

    obs_size = int(observation_space.shape[0])
    for extra_state_dim in (3, 2):
        feature_dim = obs_size - extra_state_dim
        if feature_dim <= 0 or feature_dim % lookback_window != 0:
            continue
        n_features = feature_dim // lookback_window
        if n_features > 0:
            expected_size = lookback_window * n_features + extra_state_dim
            if obs_size == expected_size:
                return n_features, extra_state_dim
    raise ValueError(
        "Invalid observation layout. Expected lookback_window * n_features + extra_state_dim "
        "with n_features > 0 and extra_state_dim in {2, 3}. "
        f"Got obs size {obs_size}, lookback_window {lookback_window}"
    )


def _validate_transformer_params(
    d_model: int,
    n_heads: int,
    n_layers: int,
    dropout: float,
    pos_encoding: str,
    pooling: str,
):
    if d_model <= 0:
        raise ValueError(f"d_model must be > 0, got {d_model}")
    if n_heads <= 0:
        raise ValueError(f"n_heads must be > 0, got {n_heads}")
    if n_layers <= 0:
        raise ValueError(f"n_layers must be > 0, got {n_layers}")
    if not (0.0 <= dropout < 1.0):
        raise ValueError(f"dropout must be in [0, 1), got {dropout}")
    if d_model % n_heads != 0:
        raise ValueError(f"d_model ({d_model}) must be divisible by n_heads ({n_heads})")
    if pos_encoding not in VALID_POS_ENCODINGS:
        raise ValueError(f"pos_encoding must be one of {sorted(VALID_POS_ENCODINGS)}, got {pos_encoding}")
    if pooling not in VALID_POOLINGS:
        raise ValueError(f"pooling must be one of {sorted(VALID_POOLINGS)}, got {pooling}")


class LearnablePositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 200):
        super().__init__()
        self.max_len = int(max_len)
        self.pos_embedding = nn.Parameter(th.randn(1, self.max_len, d_model) * 0.02)

    def forward(self, x: th.Tensor) -> th.Tensor:
        seq_len = x.size(1)
        if seq_len > self.max_len:
            raise ValueError(f"seq_len ({seq_len}) exceeds max_len ({self.max_len})")
        return x + self.pos_embedding[:, :seq_len, :]


class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 200):
        super().__init__()
        self.max_len = int(max_len)

        position = th.arange(self.max_len, dtype=th.float32).unsqueeze(1)
        div_term = th.exp(th.arange(0, d_model, 2, dtype=th.float32) * (-math.log(10000.0) / d_model))

        pe = th.zeros(1, self.max_len, d_model, dtype=th.float32)
        pe[0, :, 0::2] = th.sin(position * div_term)
        odd_dim = pe[0, :, 1::2].shape[-1]
        if odd_dim > 0:
            pe[0, :, 1::2] = th.cos(position * div_term[:odd_dim])
        self.register_buffer("pe", pe)

    def forward(self, x: th.Tensor) -> th.Tensor:
        seq_len = x.size(1)
        if seq_len > self.max_len:
            raise ValueError(f"seq_len ({seq_len}) exceeds max_len ({self.max_len})")
        return x + self.pe[:, :seq_len, :]


class AttentionPooling(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.attention = nn.Linear(d_model, 1)

    def forward(self, x: th.Tensor) -> th.Tensor:
        weights = F.softmax(self.attention(x).squeeze(-1), dim=1).unsqueeze(-1)
        return (x * weights).sum(dim=1)


class _BaseStockTransformerExtractor(BaseFeaturesExtractor):
    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 90,
        d_model: int = 128,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.1,
        pos_encoding: str = "learnable",
        pooling: str = "attention",
    ):
        super().__init__(observation_space, features_dim)

        _validate_transformer_params(
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
            dropout=dropout,
            pos_encoding=pos_encoding,
            pooling=pooling,
        )

        self.lookback_window = int(lookback_window)
        self.d_model = int(d_model)
        self.pooling = pooling
        self.n_features, self.extra_state_dim = _validate_observation_layout(observation_space, self.lookback_window)

        # Normalize per-token feature scale before attention.
        self.input_norm = nn.LayerNorm(self.n_features, eps=1e-6)
        self.input_projection = nn.Linear(self.n_features, self.d_model)
        self.embedding_norm = nn.LayerNorm(self.d_model, eps=1e-6)
        self.embedding_dropout = nn.Dropout(dropout)

        if pos_encoding == "learnable":
            self.pos_encoder = LearnablePositionalEncoding(self.d_model, max_len=self.lookback_window + 10)
        else:
            self.pos_encoder = SinusoidalPositionalEncoding(self.d_model, max_len=self.lookback_window + 10)

        if self.pooling == "cls":
            self.cls_token = nn.Parameter(th.randn(1, 1, self.d_model) * 0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model,
            nhead=n_heads,
            dim_feedforward=self.d_model * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.post_transformer_norm = nn.LayerNorm(self.d_model, eps=1e-6)

        if self.pooling == "attention":
            self.attention_pool = AttentionPooling(self.d_model)

        self.output_projection = nn.Sequential(
            nn.Linear(self.d_model + self.extra_state_dim, features_dim),
            nn.ReLU(),
        )

    def _pool_sequence(self, transformer_output: th.Tensor) -> th.Tensor:
        if self.pooling == "mean":
            return transformer_output.mean(dim=1)
        if self.pooling == "last":
            return transformer_output[:, -1, :]
        if self.pooling == "cls":
            return transformer_output[:, 0, :]
        if self.pooling == "attention":
            return self.attention_pool(transformer_output)
        raise ValueError(f"Unexpected pooling mode: {self.pooling}")

    def _transform(self, observations: th.Tensor) -> th.Tensor:
        batch_size = observations.shape[0]
        ohlcv_flat = observations[:, :-self.extra_state_dim]
        ohlcv_window = ohlcv_flat.reshape(batch_size, self.lookback_window, self.n_features)

        # Guard against non-finite / extreme input values from raw market features.
        x = th.nan_to_num(ohlcv_window, nan=0.0, posinf=1e6, neginf=-1e6)
        x = th.clamp(x, min=-1e6, max=1e6)
        x = self.input_norm(x)
        x = self.input_projection(x)
        x = self.embedding_norm(x)
        x = self.pos_encoder(x)
        x = self.embedding_dropout(x)
        x = th.nan_to_num(x, nan=0.0, posinf=1e4, neginf=-1e4)
        if self.pooling == "cls":
            cls_tokens = self.cls_token.expand(batch_size, -1, -1)
            x = th.cat([cls_tokens, x], dim=1)

        transformer_output = self.transformer(x)
        transformer_output = self.post_transformer_norm(transformer_output)
        transformer_output = th.nan_to_num(transformer_output, nan=0.0, posinf=1e4, neginf=-1e4)
        return self._pool_sequence(transformer_output)


class StockTransformerExtractor(_BaseStockTransformerExtractor):
    """Transformer extractor for PPO."""

    def forward(self, observations: th.Tensor) -> th.Tensor:
        pooled = self._transform(observations)
        extra_state = th.nan_to_num(observations[:, -self.extra_state_dim:], nan=0.0, posinf=1e4, neginf=-1e4)
        combined = th.cat([pooled, extra_state], dim=1)
        output = self.output_projection(combined)
        return th.nan_to_num(output, nan=0.0, posinf=1e4, neginf=-1e4)


class StockTransformerExtractorForLSTM(_BaseStockTransformerExtractor):
    """Transformer extractor for RecurrentPPO."""

    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 90,
        d_model: int = 128,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.1,
        pos_encoding: str = "learnable",
        pooling: str = "attention",
    ):
        super().__init__(
            observation_space=observation_space,
            features_dim=features_dim,
            lookback_window=lookback_window,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
            dropout=dropout,
            pos_encoding=pos_encoding,
            pooling=pooling,
        )

    def forward(self, observations: th.Tensor) -> th.Tensor:
        pooled = self._transform(observations)
        extra_state = th.nan_to_num(observations[:, -self.extra_state_dim:], nan=0.0, posinf=1e4, neginf=-1e4)
        combined = th.cat([pooled, extra_state], dim=1)
        output = self.output_projection(combined)
        return th.nan_to_num(output, nan=0.0, posinf=1e4, neginf=-1e4)
