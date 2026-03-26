import glob
import os
import pandas as pd
from typing import Optional, List, Union

from vn_stock_rl.env.base import BaseTradingEnv


class MultiStockEnv(BaseTradingEnv):
    """
    Multi-stock trading environment with 70/15/15 train/val/test split.
    Trains on all stocks, randomly samples from them during training.
    """
    
    def __init__(
        self,
        data_dir: str,
        mode: str = 'train',
        stocks: list = None,
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
        self.data_dir = data_dir
        self.stocks_filter = stocks
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
        # Load all stock data
        self.stock_data = []
        self.stock_names = []
        self.market_feature_count = len(self.help_tickers) * self.base_feature_dim if self.help_tickers else 0
        self.asset_feature_count = len(self.help_assets) * self.base_feature_dim if self.help_assets else 0
        self.market_ma_feature_count = len(self.help_tickers) * self.helpers_ma_feature_count if self.help_tickers else 0
        self.asset_ma_feature_count = len(self.help_assets) * self.helpers_ma_feature_count if self.help_assets else 0
        self.market_returns_feature_count = len(self.help_tickers) * self.helpers_returns_feature_count if self.help_tickers else 0
        self.asset_returns_feature_count = len(self.help_assets) * self.helpers_returns_feature_count if self.help_assets else 0
        preloaded_market_data = None
        preloaded_asset_data = None
        
        parquet_files = glob.glob(os.path.join(self.data_dir, "*.parquet"))
        
        if not parquet_files:
            raise ValueError(f"No parquet files found in {self.data_dir}")
        
        for file_path in parquet_files:
            # Extract stock ticker from filename
            # Handle both formats: "TICKER.parquet" and "gia_lich_su_TICKER_1D.parquet"
            base_name = os.path.basename(file_path).replace('.parquet', '')
            
            # Try to extract ticker from Vietnamese format: gia_lich_su_TICKER_1D
            if 'gia_lich_su_' in base_name and '_1D' in base_name:
                # Extract TICKER from "gia_lich_su_TICKER_1D"
                stock_name = base_name.replace('gia_lich_su_', '').replace('_1D', '')
            else:
                # Use full base name for other formats
                stock_name = base_name
            
            # Filter by stocks list if provided
            if self.stocks_filter and stock_name not in self.stocks_filter:
                continue
            
            try:
                df = pd.read_parquet(file_path)
                df = df.sort_values('time').reset_index(drop=True)
                df = self._filter_df_by_sample_dates(df, context=f"stock dataframe '{stock_name}'")
                df = self._merge_news_features_for_ticker(df, stock_name)
                df = self._merge_signal_features_for_ticker(df, stock_name)
                pretrim_ma_frame = self._compute_pretrim_ma_frame(df)
                pretrim_window_returns_frame = self._compute_pretrim_window_returns_frame_for_windows(
                    df,
                    self.returns_windows,
                )
                pretrim_market_momentum_frame = self._load_market_proxy_pretrim_momentum_frame()
                pretrim_engineered_frame = self._compute_pretrim_engineered_frame(
                    df,
                    market_momentum_frame=pretrim_market_momentum_frame,
                )
                
                market_dfs = []
                if self.help_tickers:
                    if preloaded_market_data is None:
                        preloaded_market_data = self._load_external_data_map(
                            self.help_tickers,
                            self.market_data_dir,
                            "gia_lich_su_",
                            "1D",
                        )
                    df, market_dfs = self._align_base_with_external_data(
                        df,
                        preloaded_market_data,
                    )
                
                asset_dfs = []
                if self.help_assets:
                    if preloaded_asset_data is None:
                        preloaded_asset_data = self._load_external_data_map(
                            self.help_assets,
                            self.help_assets_dir,
                            "fx_commodities_",
                            "1d",
                        )
                    df, asset_dfs = self._align_base_with_external_data(
                        df,
                        preloaded_asset_data,
                    )
                
                cache = self._compute_cache_from_df(
                    df,
                    precomputed_ma_frame=pretrim_ma_frame,
                    precomputed_window_returns_frame=pretrim_window_returns_frame,
                    precomputed_engineered_frame=pretrim_engineered_frame,
                    include_engineered=True,
                )
                market_caches = (
                    [
                        self._compute_cache_from_df(
                            mdf,
                            precomputed_ma_frame=self._compute_pretrim_ma_frame_for_windows(
                                mdf,
                                self.helpers_ma_windows,
                            ),
                            ma_windows=self.helpers_ma_windows,
                            precomputed_window_returns_frame=self._compute_pretrim_window_returns_frame_for_windows(
                                mdf,
                                self.helpers_returns_windows,
                            ),
                            returns_windows=self.helpers_returns_windows,
                            include_engineered=False,
                            include_news=False,
                            include_signal=False,
                        )
                        for mdf in market_dfs
                    ]
                    if market_dfs
                    else None
                )
                asset_caches = (
                    [
                        self._compute_cache_from_df(
                            mdf,
                            precomputed_ma_frame=self._compute_pretrim_ma_frame_for_windows(
                                mdf,
                                self.helpers_ma_windows,
                            ),
                            ma_windows=self.helpers_ma_windows,
                            precomputed_window_returns_frame=self._compute_pretrim_window_returns_frame_for_windows(
                                mdf,
                                self.helpers_returns_windows,
                            ),
                            returns_windows=self.helpers_returns_windows,
                            include_engineered=False,
                            include_news=False,
                            include_signal=False,
                        )
                        for mdf in asset_dfs
                    ]
                    if asset_dfs
                    else None
                )
                
                total_len = len(df)
                splits = self._compute_splits(total_len, self.lookback_window, self.train_split, self.val_split)
                self._validate_mode_split(splits, self.mode, context=f"(stock={stock_name})")
                
                self.stock_data.append({
                    'name': stock_name,
                    'df': df,  # Keep original dataframe with original indices
                    'cache': cache,
                    'market_caches': market_caches,
                    'asset_caches': asset_caches,
                    'train_start': splits['train_start_idx'],
                    'train_end': splits['train_end_idx'],
                    'val_start': splits['val_start_idx'],
                    'val_end': splits['val_end_idx'],
                    'test_start': splits['test_start_idx'],
                    'test_end': splits['test_end_idx']
                })
                self.stock_names.append(stock_name)
                
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
                continue
        
        if not self.stock_data:
            # Provide helpful error message showing what was found
            if self.stocks_filter:
                all_found_tickers = []
                for file_path in parquet_files:
                    base_name = os.path.basename(file_path).replace('.parquet', '')
                    if 'gia_lich_su_' in base_name and '_1D' in base_name:
                        ticker = base_name.replace('gia_lich_su_', '').replace('_1D', '')
                    else:
                        ticker = base_name
                    all_found_tickers.append(ticker)
                
                raise ValueError(
                    f"No valid stock data loaded from {self.data_dir}\n"
                    f"Requested stocks: {self.stocks_filter}\n"
                    f"Available tickers: {sorted(all_found_tickers)}\n"
                    f"Files found: {len(parquet_files)}"
                )
            else:
                raise ValueError(f"No valid stock data loaded from {self.data_dir}")
        
        print(f"Loaded {len(self.stock_data)} stocks: {', '.join(self.stock_names)}")
        
        # For val/test mode: cycle through stocks (shared counter)
        self.val_test_stock_idx = 0
        self.current_stock = None
    
    def _get_current_dataframe(self) -> pd.DataFrame:
        """Returns the dataframe for the current step."""
        return self.current_stock['df']
    
    def _reset_episode_range(self):
        """Sets episode_start_idx and episode_end_idx based on mode and stock selection."""
        if self.mode == 'train':
            # Random stock selection
            stock_idx = self.np_random.integers(0, len(self.stock_data))
            self.current_stock = self.stock_data[stock_idx]
            self._set_active_cache(
                self.current_stock['cache'],
                market_caches=self.current_stock.get('market_caches'),
                asset_caches=self.current_stock.get('asset_caches')
            )
            # -1 because we need t+1 for reward/execution
            train_decision_end = self.current_stock['train_end'] - 1
            self.episode_start_idx, self.episode_end_idx = self._sample_train_episode_bounds(
                self.current_stock['train_start'],
                train_decision_end,
            )
            
        elif self.mode == 'val':
            # Cycle through all stocks
            self.current_stock = self.stock_data[self.val_test_stock_idx]
            self.val_test_stock_idx = (self.val_test_stock_idx + 1) % len(self.stock_data)
            self._set_active_cache(
                self.current_stock['cache'],
                market_caches=self.current_stock.get('market_caches'),
                asset_caches=self.current_stock.get('asset_caches')
            )
            self.episode_start_idx = self.current_stock['val_start']  # Already has gap
            self.episode_end_idx = self.current_stock['val_end'] - 1  # -1 because we need t+1 for reward/execution
            
        else:  # test mode
            # Cycle through all stocks
            self.current_stock = self.stock_data[self.val_test_stock_idx]
            self.val_test_stock_idx = (self.val_test_stock_idx + 1) % len(self.stock_data)
            self._set_active_cache(
                self.current_stock['cache'],
                market_caches=self.current_stock.get('market_caches'),
                asset_caches=self.current_stock.get('asset_caches')
            )
            self.episode_start_idx = self.current_stock['test_start']  # Already has gap
            self.episode_end_idx = self.current_stock['test_end'] - 1  # -1 because we need t+1
    
    def _get_reset_info(self) -> dict:
        """Get info dict for reset with stock information."""
        return {
            'stock': self.current_stock['name'],
            'episode_start': self.episode_start_idx,
            'episode_end': self.episode_end_idx,
            'episode_length': self.episode_end_idx - self.episode_start_idx,
            'mode': self.mode
        }

    def _get_step_info(self, reward: float) -> dict:
        """Get info dict for step with stock information."""
        info = super()._get_step_info(reward)
        info['stock'] = self.current_stock['name']
        return info
    
    def _get_stock_name(self) -> Optional[str]:
        """Returns stock name for display."""
        return self.current_stock['name'] if self.current_stock else None


if __name__ == "__main__":
    print("="*60)
    print("Testing TradingEnv (Single Stock)")
    print("="*60)
    
    env = TradingEnv(data_path="data/stock/gia_lich_su_ACB_1D.parquet", mode='train')
    
    print(f"\nEnvironment created successfully!")
    print(f"Mode: {env.mode}")
    print(f"\nData Splits:")
    print(f"  Train: {env.train_start_date} to {env.train_end_date} ({env.train_end_idx - env.train_start_idx} days)")
    print(f"  Val:   {env.val_start_date} to {env.val_end_date} ({env.val_end_idx - env.val_start_idx} days)")
    print(f"  Test:  {env.test_start_date} to {env.test_end_date} ({env.test_end_idx - env.test_start_idx} days)")
    
    print("\n" + "="*60)
    print("Testing MultiStockEnv")
    print("="*60)
    
    try:
        multi_env = MultiStockEnv(data_dir="data/stock/", mode='train')
        
        print(f"\n[OK] MultiStockEnv created successfully!")
        print(f"Number of stocks: {len(multi_env.stock_data)}")
        print(f"Stocks: {', '.join(multi_env.stock_names)}")
        
        print("\n" + "="*60)
        print("Testing random stock sampling (3 episodes)...")
        print("="*60)
        
        for ep in range(3):
            obs, info = multi_env.reset()
            print(f"\nEpisode {ep + 1}:")
            print(f"  Stock: {info['stock']}")
            print(f"  Length: {info['episode_length']} days")
        
        print("\n" + "="*60)
        print("All tests passed! [OK]")
        print("="*60)
        
    except Exception as e:
        print(f"\n[FAIL] MultiStockEnv test failed: {e}")
        print("Make sure you have parquet files in the data/stock/ directory")

