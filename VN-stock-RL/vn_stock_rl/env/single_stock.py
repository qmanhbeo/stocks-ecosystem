import pandas as pd
from typing import Optional, List, Union

from vn_stock_rl.env.base import BaseTradingEnv


class TradingEnv(BaseTradingEnv):
    """
    Simple Trading Environment with 70/15/15 train/val/test split.
    
    Features:
    - Last N days of OHLCV data (raw prices and volumes)
    - Minimum hold constraint (3 days)
    - Transaction tax (0.3% on all sales)
    - Train-only normalization
    
    Action space: {0, 1} (flat or long)
    State space: [past_selected_ohlcv, past_ma, past_calendar, pos, count, can_exit]
    """
    
    def __init__(
        self,
        data_path: str,
        mode: str = 'train',  # 'train', 'val', or 'test'
        train_split: float = None,
        val_split: float = None,
        min_hold_days: int = None,
        buy_fee_rate: float = None,
        sell_fee_rate: float = None,
        capital_gains_tax_rate: float = None,
        stop_loss: float = None,
        lookback_window: int = None,
        reward_shaping: Optional[dict] = None,
        drawdown_penalty_enabled: Optional[bool] = None,
        drawdown_penalty_lambda: Optional[float] = None,
        drawdown_penalty_train_only: Optional[bool] = None,
        reward_benchmark: Optional[str] = None,
        benchmark_weight: Optional[float] = None,
        benchmark_relative_reward: Optional[bool] = None,
        train_episode_sampling: Optional[dict] = None,
        train_episode_sampling_enabled: Optional[bool] = None,
        train_episode_min_fraction: Optional[float] = None,
        train_episode_max_fraction: Optional[float] = None,
        start_episode_position: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source_mode: Optional[str] = None,
        ohlcv: Optional[List[str]] = None,
        calendar_features: Optional[List[str]] = None,
        ma_windows: Optional[List[int]] = None,
        helpers_ma_windows: Optional[List[Union[int, str]]] = None,
        returns_windows: Optional[List[int]] = None,
        helpers_returns_windows: Optional[List[Union[int, str]]] = None,
        engineered_features: Optional[List[str]] = None,
        window_policy: Optional[str] = None,
        feature_windows: Optional[List[int]] = None,
        logspace_min: Optional[int] = None,
        logspace_max: Optional[int] = None,
        logspace_count: Optional[int] = None,
        rs_market_proxies: Optional[List[str]] = None,
        rs_include_long: Optional[bool] = None,
        include_can_exit: bool = True,
        help_tickers: Optional[List[str]] = None,
        market_data_dir: str = "data/stock/",
        help_assets: Optional[List[str]] = None,
        help_assets_dir: str = "data/fx-commodities/",
        news_feature_columns: Optional[List[str]] = None,
        news_prediction_dir: Optional[str] = None,
        signal_feature_columns: Optional[List[str]] = None,
        signal_prediction_dir: Optional[str] = None,
    ):
        self.data_path = data_path
        super().__init__(
            mode=mode,
            train_split=train_split,
            val_split=val_split,
            min_hold_days=min_hold_days,
            buy_fee_rate=buy_fee_rate,
            sell_fee_rate=sell_fee_rate,
            capital_gains_tax_rate=capital_gains_tax_rate,
            stop_loss=stop_loss,
            lookback_window=lookback_window,
            reward_shaping=reward_shaping,
            drawdown_penalty_enabled=drawdown_penalty_enabled,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
            drawdown_penalty_train_only=drawdown_penalty_train_only,
            reward_benchmark=reward_benchmark,
            benchmark_weight=benchmark_weight,
            benchmark_relative_reward=benchmark_relative_reward,
            train_episode_sampling=train_episode_sampling,
            train_episode_sampling_enabled=train_episode_sampling_enabled,
            train_episode_min_fraction=train_episode_min_fraction,
            train_episode_max_fraction=train_episode_max_fraction,
            start_episode_position=start_episode_position,
            start_date=start_date,
            end_date=end_date,
            source_mode=source_mode,
            ohlcv=ohlcv,
            calendar_features=calendar_features,
            ma_windows=ma_windows,
            helpers_ma_windows=helpers_ma_windows,
            returns_windows=returns_windows,
            helpers_returns_windows=helpers_returns_windows,
            engineered_features=engineered_features,
            window_policy=window_policy,
            feature_windows=feature_windows,
            logspace_min=logspace_min,
            logspace_max=logspace_max,
            logspace_count=logspace_count,
            rs_market_proxies=rs_market_proxies,
            rs_include_long=rs_include_long,
            include_can_exit=include_can_exit,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
            news_feature_columns=news_feature_columns,
            news_prediction_dir=news_prediction_dir,
            signal_feature_columns=signal_feature_columns,
            signal_prediction_dir=signal_prediction_dir,
        )
    
    def _setup_data(self):
        """Setup data loading and split calculation."""
        # Load data
        self.df = pd.read_parquet(self.data_path)
        self.df = self.df.sort_values('time').reset_index(drop=True)
        self.df = self._filter_df_by_sample_dates(
            self.df,
            context=f"stock dataframe '{self._infer_ticker_from_data_path(self.data_path)}'",
        )
        self.df = self._merge_news_features_for_ticker(
            self.df,
            self._infer_ticker_from_data_path(self.data_path),
        )
        self.df = self._merge_signal_features_for_ticker(
            self.df,
            self._infer_ticker_from_data_path(self.data_path),
        )
        pretrim_ma_frame = self._compute_pretrim_ma_frame(self.df)
        pretrim_window_returns_frame = self._compute_pretrim_window_returns_frame_for_windows(
            self.df,
            self.returns_windows,
        )
        pretrim_market_momentum_frame = self._load_market_proxy_pretrim_momentum_frame()
        pretrim_engineered_frame = self._compute_pretrim_engineered_frame(
            self.df,
            market_momentum_frame=pretrim_market_momentum_frame,
        )
        
        market_dfs = []
        if self.help_tickers:
            self.df, market_dfs = self._load_and_align_market_data(
                self.df,
                self.help_tickers,
                self.market_data_dir,
                "gia_lich_su_",
                "1D"
            )
        
        asset_dfs = []
        if self.help_assets:
            self.df, asset_dfs = self._load_and_align_market_data(
                self.df,
                self.help_assets,
                self.help_assets_dir,
                "fx_commodities_",
                "1d"
            )
        
        cache = self._compute_cache_from_df(
            self.df,
            precomputed_ma_frame=pretrim_ma_frame,
            precomputed_window_returns_frame=pretrim_window_returns_frame,
            precomputed_engineered_frame=pretrim_engineered_frame,
            include_engineered=True,
        )
        market_caches = (
            [
                self._compute_cache_from_df(
                    df,
                    precomputed_ma_frame=self._compute_pretrim_ma_frame_for_windows(
                        df,
                        self.helpers_ma_windows,
                    ),
                    ma_windows=self.helpers_ma_windows,
                    precomputed_window_returns_frame=self._compute_pretrim_window_returns_frame_for_windows(
                        df,
                        self.helpers_returns_windows,
                    ),
                    returns_windows=self.helpers_returns_windows,
                    include_engineered=False,
                    include_news=False,
                    include_signal=False,
                )
                for df in market_dfs
            ]
            if market_dfs
            else None
        )
        asset_caches = (
            [
                self._compute_cache_from_df(
                    df,
                    precomputed_ma_frame=self._compute_pretrim_ma_frame_for_windows(
                        df,
                        self.helpers_ma_windows,
                    ),
                    ma_windows=self.helpers_ma_windows,
                    precomputed_window_returns_frame=self._compute_pretrim_window_returns_frame_for_windows(
                        df,
                        self.helpers_returns_windows,
                    ),
                    returns_windows=self.helpers_returns_windows,
                    include_engineered=False,
                    include_news=False,
                    include_signal=False,
                )
                for df in asset_dfs
            ]
            if asset_dfs
            else None
        )
        self._set_active_cache(cache, market_caches=market_caches, asset_caches=asset_caches)
        
        total_len = len(self.df)
        splits = self._compute_splits(total_len, self.lookback_window, self.train_split, self.val_split)
        self._validate_mode_split(splits, self.mode)
        
        self.valid_start_idx = splits['valid_start_idx']
        self.train_start_idx = splits['train_start_idx']
        self.train_end_idx = splits['train_end_idx']
        self.val_start_idx = splits['val_start_idx']
        self.val_end_idx = splits['val_end_idx']
        self.test_start_idx = splits['test_start_idx']
        self.test_end_idx = splits['test_end_idx']
        
        # Store dates for logging
        self.train_start_date = self.df.iloc[self.train_start_idx]['time']
        self.train_end_date = self.df.iloc[self.train_end_idx]['time']
        self.val_start_date = self.df.iloc[self.val_start_idx]['time']
        self.val_end_date = self.df.iloc[self.val_end_idx]['time']
        self.test_start_date = self.df.iloc[self.test_start_idx]['time']
        self.test_end_date = self.df.iloc[self.test_end_idx]['time']
    
    def _get_current_dataframe(self) -> pd.DataFrame:
        """Returns the dataframe for the current step."""
        return self.df
    
    def _reset_episode_range(self):
        """Sets episode_start_idx and episode_end_idx based on mode."""
        if self.mode == 'train':
            # -1 because we need t+1 for reward/execution
            train_decision_end = self.train_end_idx - 1
            self.episode_start_idx, self.episode_end_idx = self._sample_train_episode_bounds(
                self.train_start_idx,
                train_decision_end,
            )
        elif self.mode == 'val':
            self.episode_start_idx = self.val_start_idx  # Already has gap
            self.episode_end_idx = self.val_end_idx - 1  # -1 because we need t+1 for reward/execution
        elif self.mode == 'test':
            self.episode_start_idx = self.test_start_idx  # Already has gap
            self.episode_end_idx = self.test_end_idx - 1  # -1 because we need t+1 for reward/execution
        else:
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'train', 'val', or 'test'")

