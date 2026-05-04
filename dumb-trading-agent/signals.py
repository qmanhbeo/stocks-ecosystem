import pandas as pd

DATA_ROOT = "/home/manh/stocks-ecosystem/data"

RL_SIGNAL_MATRIX = f"{DATA_ROOT}/features/xs_rl_signal_matrix.parquet"
ACTIVATION_STATE = f"{DATA_ROOT}/features/activation_state_daily.parquet"
ACTIVATION_META = f"{DATA_ROOT}/features/activation_meta_daily.parquet"
ORDER_PRESSURE = f"{DATA_ROOT}/features/xs_order_pressure_daily.parquet"
INSIDER_FEATURES = f"{DATA_ROOT}/features/xs_insider_quality_features.parquet"
EVENT_SURFACE = f"{DATA_ROOT}/features/event_surface_daily.parquet"

def load_rl_signal_matrix(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    cols = ['time', 'ticker', 's1_proba', 'c4_oc_asym_5d', 'c5_ins_relative_size_5d',
            'c5_signal_present', 'c6_contrarian_intra_5d', 'c7_ceiling_count_5d',
            'c8_vol_zscore_5d', 'c9_reversal_1d', 'c10_illiq_level_rank',
            'c11_ret_60d_lag_rank', 'c12_gap_absorb_3', 'c13_compress_blowoff_2',
            'c14_clv_volconf_resid_rank', 'actual']
    df = pd.read_parquet(RL_SIGNAL_MATRIX, columns=cols)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df

def load_activation_state(
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(ACTIVATION_STATE)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    return df

def load_activation_meta(
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(ACTIVATION_META)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    return df

def load_order_pressure(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(ORDER_PRESSURE)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df

def load_insider_features(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(INSIDER_FEATURES)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df

SIGNAL_CATALOG = {
    "s1_proba": "Cross-sectional relative momentum (primary signal)",
    "c4_oc_asym_5d": "Open/close asymmetry 5d",
    "c5_ins_relative_size_5d": "Insider relative size (normalized conviction)",
    "c5_signal_present": "Insider signal present flag",
    "c6_contrarian_intra_5d": "Contrarian intra-sector 5d",
    "c7_ceiling_count_5d": "Price ceiling count 5d",
    "c8_vol_zscore_5d": "Volume z-score 5d",
    "c9_reversal_1d": "1-day reversal",
    "c10_illiq_level_rank": "Illiquidity level rank",
    "c11_ret_60d_lag_rank": "60-day return lag rank",
    "c12_gap_absorb_3": "Gap absorb 3d",
    "c13_compress_blowoff_2": "Compression blowoff 2d",
"c14_clv_volconf_resid_rank": "CLV volume confirmed residual rank",
}


def load_event_surface(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(EVENT_SURFACE)
    if start:
        df = df[df['time'] >= pd.to_datetime(start)]
    if end:
        df = df[df['time'] <= pd.to_datetime(end)]
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df


def load_stock_daily(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    import glob
    pattern = f"{DATA_ROOT}/stock/gia_lich_su_{ticker}_1D.parquet"
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No data for {ticker}")
    df = pd.read_parquet(matches[0])
    df = df.sort_values("time").reset_index(drop=True)
    if start:
        df = df[df["time"] >= pd.to_datetime(start)]
    if end:
        df = df[df["time"] <= pd.to_datetime(end)]
    return df


if __name__ == "__main__":
    df = load_rl_signal_matrix()
    print(f"RL Signal Matrix loaded: {df.shape}")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"Columns: {list(df.columns)}")
    print(f"Unique tickers: {df['ticker'].nunique()}")