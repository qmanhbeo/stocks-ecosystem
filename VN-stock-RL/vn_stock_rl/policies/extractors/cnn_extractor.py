"""
CNN feature extractors for trading observations.

This module provides:
- StockClassicCNNExtractor: legacy stacked Conv1D extractor (k=3/5/7)
- StockMultiCNNExtractor: parallel multi-scale Conv1D extractor
- StockCNNExtractor: compatibility wrapper used by older checkpoints
"""

import torch as th
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


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


def _build_classic_conv_stack(n_features: int, use_batch_norm: bool) -> nn.Sequential:
    layers = [
        nn.Conv1d(in_channels=n_features, out_channels=32, kernel_size=3, padding=1),
        nn.ReLU(),
    ]
    if use_batch_norm:
        layers.append(nn.BatchNorm1d(32))

    layers.extend(
        [
            nn.Conv1d(in_channels=32, out_channels=64, kernel_size=5, padding=2),
            nn.ReLU(),
        ]
    )
    if use_batch_norm:
        layers.append(nn.BatchNorm1d(64))

    layers.extend(
        [
            nn.Conv1d(in_channels=64, out_channels=64, kernel_size=7, padding=3),
            nn.ReLU(),
        ]
    )
    if use_batch_norm:
        layers.append(nn.BatchNorm1d(64))

    return nn.Sequential(*layers)


class StockClassicCNNExtractor(BaseFeaturesExtractor):
    """
    Classic stacked 1D-CNN extractor (k=3,5,7).

    Default `use_batch_norm=False` is kept for checkpoint compatibility.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 20,
        use_batch_norm: bool = False,
    ):
        super().__init__(observation_space, features_dim)

        self.lookback_window = lookback_window
        self.n_features, self.extra_state_dim = _validate_observation_layout(observation_space, lookback_window)
        self.use_batch_norm = bool(use_batch_norm)
        self.conv_layers = _build_classic_conv_stack(self.n_features, self.use_batch_norm)

        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.projection = nn.Sequential(
            nn.Linear(64 + self.extra_state_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: th.Tensor) -> th.Tensor:
        batch_size = observations.shape[0]
        ohlcv_flat = observations[:, :-self.extra_state_dim]
        extra_state = observations[:, -self.extra_state_dim:]

        ohlcv_window = ohlcv_flat.reshape(batch_size, self.lookback_window, self.n_features)
        ohlcv_channels = ohlcv_window.transpose(1, 2)

        conv_features = self.conv_layers(ohlcv_channels)
        pooled = self.global_pool(conv_features).squeeze(-1)
        combined = th.cat([pooled, extra_state], dim=1)
        return self.projection(combined)


class StockMultiCNNExtractor(BaseFeaturesExtractor):
    """Parallel multi-scale CNN extractor with configurable windows."""

    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 20,
        multi_scale_windows=None,
        branch_channels: int = 24,
    ):
        super().__init__(observation_space, features_dim)

        self.lookback_window = lookback_window
        self.n_features, self.extra_state_dim = _validate_observation_layout(observation_space, lookback_window)

        if multi_scale_windows is None:
            multi_scale_windows = [5, 10, 20, 30, 60, 90]
        if not isinstance(multi_scale_windows, (list, tuple)) or not multi_scale_windows:
            raise ValueError("multi_scale_windows must be a non-empty list/tuple")

        raw_windows = sorted({int(w) for w in multi_scale_windows if int(w) > 0})
        active_windows = [w for w in raw_windows if w <= self.lookback_window]
        if not active_windows:
            active_windows = [self.lookback_window]

        self.multi_scale_windows = active_windows
        self.branch_channels = int(branch_channels)
        if self.branch_channels <= 0:
            raise ValueError("branch_channels must be > 0")

        self.branches = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv1d(
                        in_channels=self.n_features,
                        out_channels=self.branch_channels,
                        kernel_size=window,
                        padding=window // 2,
                    ),
                    nn.ReLU(),
                    nn.BatchNorm1d(self.branch_channels),
                )
                for window in self.multi_scale_windows
            ]
        )
        self.global_pool = nn.AdaptiveAvgPool1d(1)

        concat_dim = self.branch_channels * len(self.multi_scale_windows) + self.extra_state_dim
        self.projection = nn.Sequential(
            nn.Linear(concat_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: th.Tensor) -> th.Tensor:
        batch_size = observations.shape[0]
        ohlcv_flat = observations[:, :-self.extra_state_dim]
        extra_state = observations[:, -self.extra_state_dim:]

        ohlcv_window = ohlcv_flat.reshape(batch_size, self.lookback_window, self.n_features)
        ohlcv_channels = ohlcv_window.transpose(1, 2)

        branch_embeddings = []
        for branch in self.branches:
            branch_features = branch(ohlcv_channels)
            pooled = self.global_pool(branch_features).squeeze(-1)
            branch_embeddings.append(pooled)

        multiscale_features = th.cat(branch_embeddings, dim=1)
        combined = th.cat([multiscale_features, extra_state], dim=1)
        return self.projection(combined)


class StockCNNExtractor(BaseFeaturesExtractor):
    """
    Backward-compatible wrapper class for older checkpoints.

    Behavior:
    - If `multi_scale_windows` or `branch_channels` is provided, use multi-scale layout.
    - Otherwise, use classic stacked-conv layout.
    - In classic mode, `use_batch_norm=False` by default for checkpoint compatibility.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 128,
        lookback_window: int = 20,
        multi_scale_windows=None,
        branch_channels: int = None,
        use_batch_norm: bool = False,
    ):
        super().__init__(observation_space, features_dim)

        self.lookback_window = lookback_window
        self.n_features, self.extra_state_dim = _validate_observation_layout(observation_space, lookback_window)

        self._use_multi = multi_scale_windows is not None or branch_channels is not None

        if self._use_multi:
            if multi_scale_windows is None:
                multi_scale_windows = [5, 10, 20, 30, 60, 90]
            if branch_channels is None:
                branch_channels = 24

            raw_windows = sorted({int(w) for w in multi_scale_windows if int(w) > 0})
            active_windows = [w for w in raw_windows if w <= self.lookback_window]
            if not active_windows:
                active_windows = [self.lookback_window]

            self.multi_scale_windows = active_windows
            self.branch_channels = int(branch_channels)
            if self.branch_channels <= 0:
                raise ValueError("branch_channels must be > 0")

            self.branches = nn.ModuleList(
                [
                    nn.Sequential(
                        nn.Conv1d(
                            in_channels=self.n_features,
                            out_channels=self.branch_channels,
                            kernel_size=window,
                            padding=window // 2,
                        ),
                        nn.ReLU(),
                        nn.BatchNorm1d(self.branch_channels),
                    )
                    for window in self.multi_scale_windows
                ]
            )
            concat_dim = self.branch_channels * len(self.multi_scale_windows) + self.extra_state_dim
            self.projection = nn.Sequential(nn.Linear(concat_dim, features_dim), nn.ReLU())
        else:
            self.use_batch_norm = bool(use_batch_norm)
            self.conv_layers = _build_classic_conv_stack(self.n_features, self.use_batch_norm)
            self.projection = nn.Sequential(nn.Linear(64 + self.extra_state_dim, features_dim), nn.ReLU())

        self.global_pool = nn.AdaptiveAvgPool1d(1)

    def forward(self, observations: th.Tensor) -> th.Tensor:
        batch_size = observations.shape[0]
        ohlcv_flat = observations[:, :-self.extra_state_dim]
        extra_state = observations[:, -self.extra_state_dim:]

        ohlcv_window = ohlcv_flat.reshape(batch_size, self.lookback_window, self.n_features)
        ohlcv_channels = ohlcv_window.transpose(1, 2)

        if self._use_multi:
            branch_embeddings = []
            for branch in self.branches:
                branch_features = branch(ohlcv_channels)
                pooled = self.global_pool(branch_features).squeeze(-1)
                branch_embeddings.append(pooled)
            cnn_features = th.cat(branch_embeddings, dim=1)
        else:
            conv_features = self.conv_layers(ohlcv_channels)
            cnn_features = self.global_pool(conv_features).squeeze(-1)

        combined = th.cat([cnn_features, extra_state], dim=1)
        return self.projection(combined)
