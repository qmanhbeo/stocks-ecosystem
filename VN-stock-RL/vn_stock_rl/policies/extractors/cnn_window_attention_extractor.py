"""
CNN window-attention extractors for trading observations.

Architecture:
- CNN extracts local temporal patterns.
- Sequence is segmented into overlapping windows.
- Transformer contextualizes window tokens.
- Window-importance pooling learns which windows matter most.
"""

import torch as th
import torch.nn as nn
import torch.nn.functional as F
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


VALID_POOLINGS = {"window_attention", "mean", "last"}


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


def _validate_params(
    lookback_window: int,
    window_size: int,
    stride: int,
    cnn_channels: int,
    embed_dim: int,
    n_heads: int,
    n_layers: int,
    dropout: float,
    pooling: str,
) -> int:
    if window_size <= 0 or window_size > lookback_window:
        raise ValueError(
            f"window_size ({window_size}) must be > 0 and <= lookback_window ({lookback_window})"
        )
    if stride <= 0 or stride > window_size:
        raise ValueError(f"stride ({stride}) must be > 0 and <= window_size ({window_size})")
    if cnn_channels <= 0:
        raise ValueError(f"cnn_channels must be > 0, got {cnn_channels}")
    if embed_dim <= 0:
        raise ValueError(f"embed_dim must be > 0, got {embed_dim}")
    if n_heads <= 0:
        raise ValueError(f"n_heads must be > 0, got {n_heads}")
    if n_layers <= 0:
        raise ValueError(f"n_layers must be > 0, got {n_layers}")
    if embed_dim % n_heads != 0:
        raise ValueError(f"embed_dim ({embed_dim}) must be divisible by n_heads ({n_heads})")
    if not (0.0 <= dropout < 1.0):
        raise ValueError(f"dropout must be in [0, 1), got {dropout}")
    if pooling not in VALID_POOLINGS:
        raise ValueError(f"pooling must be one of {sorted(VALID_POOLINGS)}, got {pooling}")

    n_windows = (lookback_window - window_size) // stride + 1
    if n_windows < 2:
        raise ValueError(
            f"Configuration produces only {n_windows} window(s). "
            "Need at least 2. Try smaller window_size or stride."
        )
    return n_windows


class LocalPatternCNN(nn.Module):
    def __init__(self, n_features: int, cnn_channels: int = 64):
        super().__init__()
        self.conv_stack = nn.Sequential(
            nn.Conv1d(n_features, cnn_channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(cnn_channels),
            nn.Conv1d(cnn_channels, cnn_channels, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.BatchNorm1d(cnn_channels),
            nn.Conv1d(cnn_channels, cnn_channels, kernel_size=7, padding=3),
            nn.ReLU(),
            nn.BatchNorm1d(cnn_channels),
        )

    def forward(self, x: th.Tensor) -> th.Tensor:
        return self.conv_stack(x)


class WindowSegmenter(nn.Module):
    def __init__(
        self,
        window_size: int,
        stride: int,
        cnn_channels: int,
        embed_dim: int,
        max_windows: int,
    ):
        super().__init__()
        self.window_size = int(window_size)
        self.stride = int(stride)
        self.window_projection = nn.Linear(cnn_channels * self.window_size, embed_dim)
        self.window_position_embedding = nn.Parameter(th.randn(1, max_windows, embed_dim) * 0.02)

    def forward(self, cnn_features: th.Tensor) -> th.Tensor:
        batch_size, _, seq_len = cnn_features.shape
        windows = []
        for start in range(0, seq_len - self.window_size + 1, self.stride):
            end = start + self.window_size
            window = cnn_features[:, :, start:end]
            windows.append(window.reshape(batch_size, -1))

        windows_tensor = th.stack(windows, dim=1)
        embeddings = self.window_projection(windows_tensor)
        n_windows = embeddings.size(1)
        embeddings = embeddings + self.window_position_embedding[:, :n_windows, :]
        return embeddings


class WindowTransformer(nn.Module):
    def __init__(self, embed_dim: int, n_heads: int, n_layers: int, dropout: float):
        super().__init__()
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=n_heads,
            dim_feedforward=embed_dim * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.output_norm = nn.LayerNorm(embed_dim, eps=1e-6)

    def forward(self, x: th.Tensor) -> th.Tensor:
        return self.output_norm(self.transformer(x))


class WindowImportancePooling(nn.Module):
    """Learns soft weights over windows and pools by weighted sum."""

    def __init__(self, embed_dim: int):
        super().__init__()
        self.scorer = nn.Linear(embed_dim, 1)
        nn.init.normal_(self.scorer.weight, std=0.01)
        nn.init.zeros_(self.scorer.bias)

    def forward(self, x: th.Tensor):
        logits = self.scorer(x).squeeze(-1)  # [B, W]
        logits = logits - logits.max(dim=1, keepdim=True)[0]
        weights = F.softmax(logits, dim=1)  # [B, W]
        pooled = (x * weights.unsqueeze(-1)).sum(dim=1)
        return pooled, weights


class _BaseCNNWindowAttentionExtractor(BaseFeaturesExtractor):
    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 90,
        window_size: int = 15,
        stride: int = 7,
        cnn_channels: int = 64,
        embed_dim: int = 128,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.1,
        pooling: str = "window_attention",
    ):
        super().__init__(observation_space, features_dim)

        self.lookback_window = int(lookback_window)
        self.window_size = int(window_size)
        self.stride = int(stride)
        self.embed_dim = int(embed_dim)
        self.pooling = pooling
        self.last_window_weights = None

        self.n_features, self.extra_state_dim = _validate_observation_layout(observation_space, self.lookback_window)
        self.n_windows = _validate_params(
            lookback_window=self.lookback_window,
            window_size=self.window_size,
            stride=self.stride,
            cnn_channels=cnn_channels,
            embed_dim=self.embed_dim,
            n_heads=n_heads,
            n_layers=n_layers,
            dropout=dropout,
            pooling=self.pooling,
        )

        self.input_norm = nn.LayerNorm(self.n_features, eps=1e-6)
        self.local_cnn = LocalPatternCNN(self.n_features, cnn_channels)
        self.window_segmenter = WindowSegmenter(
            window_size=self.window_size,
            stride=self.stride,
            cnn_channels=cnn_channels,
            embed_dim=self.embed_dim,
            max_windows=self.n_windows + 1,
        )
        self.window_transformer = WindowTransformer(
            embed_dim=self.embed_dim,
            n_heads=n_heads,
            n_layers=n_layers,
            dropout=dropout,
        )

        if self.pooling == "window_attention":
            self.window_importance_pool = WindowImportancePooling(self.embed_dim)

        self.output_projection = nn.Sequential(
            nn.Linear(self.embed_dim + self.extra_state_dim, features_dim),
            nn.ReLU(),
        )

    def _pool(self, attended_windows: th.Tensor) -> th.Tensor:
        if self.pooling == "window_attention":
            pooled, weights = self.window_importance_pool(attended_windows)
            self.last_window_weights = weights.detach()
            return pooled
        self.last_window_weights = None
        if self.pooling == "mean":
            return attended_windows.mean(dim=1)
        if self.pooling == "last":
            return attended_windows[:, -1, :]
        raise ValueError(f"Unexpected pooling mode: {self.pooling}")

    def _extract_embedding(self, observations: th.Tensor) -> th.Tensor:
        batch_size = observations.shape[0]
        ohlcv_flat = observations[:, :-self.extra_state_dim]
        ohlcv_window = ohlcv_flat.reshape(batch_size, self.lookback_window, self.n_features)

        # [batch, lookback, n_features] -> [batch, n_features, lookback]
        ohlcv_channels = ohlcv_window.transpose(1, 2)
        ohlcv_channels = th.nan_to_num(ohlcv_channels, nan=0.0, posinf=1e6, neginf=-1e6)
        ohlcv_channels = th.clamp(ohlcv_channels, min=-1e6, max=1e6)

        # Normalize per-timestep feature vectors before convolution.
        ohlcv_channels = ohlcv_channels.transpose(1, 2)
        ohlcv_channels = self.input_norm(ohlcv_channels)
        ohlcv_channels = ohlcv_channels.transpose(1, 2)

        cnn_features = self.local_cnn(ohlcv_channels)
        window_embeddings = self.window_segmenter(cnn_features)
        window_embeddings = th.nan_to_num(window_embeddings, nan=0.0, posinf=1e4, neginf=-1e4)
        attended_windows = self.window_transformer(window_embeddings)
        attended_windows = th.nan_to_num(attended_windows, nan=0.0, posinf=1e4, neginf=-1e4)
        return self._pool(attended_windows)


class CNNWindowAttentionExtractor(_BaseCNNWindowAttentionExtractor):
    """CNN-window-attention extractor for PPO."""

    def forward(self, observations: th.Tensor) -> th.Tensor:
        pooled = self._extract_embedding(observations)
        extra_state = th.nan_to_num(observations[:, -self.extra_state_dim:], nan=0.0, posinf=1e4, neginf=-1e4)
        combined = th.cat([pooled, extra_state], dim=1)
        output = self.output_projection(combined)
        return th.nan_to_num(output, nan=0.0, posinf=1e4, neginf=-1e4)


class CNNWindowAttentionExtractorForLSTM(_BaseCNNWindowAttentionExtractor):
    """CNN-window-attention extractor for RecurrentPPO."""

    def forward(self, observations: th.Tensor) -> th.Tensor:
        pooled = self._extract_embedding(observations)
        extra_state = th.nan_to_num(observations[:, -self.extra_state_dim:], nan=0.0, posinf=1e4, neginf=-1e4)
        combined = th.cat([pooled, extra_state], dim=1)
        output = self.output_projection(combined)
        return th.nan_to_num(output, nan=0.0, posinf=1e4, neginf=-1e4)
