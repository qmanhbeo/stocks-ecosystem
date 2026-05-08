import argparse
import pandas as pd

DATA_ROOT = "/home/manh/stocks-ecosystem/data"
MAX_RESEARCH_YEAR = 2025

RL_SIGNAL_MATRIX = f"{DATA_ROOT}/features/xs_rl_signal_matrix.parquet"
ACTIVATION_STATE = f"{DATA_ROOT}/features/activation_state_daily.parquet"
ACTIVATION_META = f"{DATA_ROOT}/features/activation_meta_daily.parquet"
ORDER_PRESSURE = f"{DATA_ROOT}/features/xs_order_pressure_daily.parquet"
INSIDER_FEATURES = f"{DATA_ROOT}/features/xs_insider_quality_features.parquet"
EVENT_SURFACE = f"{DATA_ROOT}/features/event_surface_daily.parquet"


def _apply_lockbox_filter(
    df: pd.DataFrame,
    start: str | None,
    end: str | None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """Apply lockbox filtering to dataframe."""
    result = df.copy()
    if start:
        result = result[result['time'] >= pd.to_datetime(start)]
    if end:
        max_date = pd.to_datetime(end)
        lockbox_date = pd.to_datetime(f"{MAX_RESEARCH_YEAR}-12-31")
        if not allow_2026 and max_date > lockbox_date:
            raise ValueError(
                f"end={end} includes 2026+ which is forbidden. "
                f"Max allowed end date is {MAX_RESEARCH_YEAR}-12-31. "
                f"Use --allow-lockbox flag to override (only for testing)."
            )
        result = result[result['time'] <= max_date]
    if not allow_2026:
        lockbox_date = pd.to_datetime(f"{MAX_RESEARCH_YEAR}-12-31")
        if 'time' in result.columns:
            future_rows = result[result['time'] > lockbox_date]
            if len(future_rows) > 0:
                raise ValueError(
                    f"Data contains {len(future_rows)} rows after {MAX_RESEARCH_YEAR}-12-31. "
                    f"Use --allow-lockbox flag to include 2026+ (only for testing)."
                )
    return result


def parse_lockbox_args():
    """Parse lockbox-related CLI arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--allow-lockbox', action='store_true',
                        help='Allow 2026+ data (for testing only, not for real trading)')
    return parser.parse_known_args()[0]

def load_rl_signal_matrix(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    cols = ['time', 'ticker', 's1_proba', 'c4_oc_asym_5d', 'c5_ins_relative_size_5d',
            'c5_signal_present', 'c6_contrarian_intra_5d', 'c7_ceiling_count_5d',
            'c8_vol_zscore_5d', 'c9_reversal_1d', 'c10_illiq_level_rank',
            'c11_ret_60d_lag_rank', 'c12_gap_absorb_3', 'c13_compress_blowoff_2',
            'c14_clv_volconf_resid_rank', 'actual']
    df = pd.read_parquet(RL_SIGNAL_MATRIX, columns=cols)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df

def load_activation_state(
    start: str | None = None,
    end: str | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    df = pd.read_parquet(ACTIVATION_STATE)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    return df


def load_activation_meta(
    start: str | None = None,
    end: str | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    df = pd.read_parquet(ACTIVATION_META)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    return df


def load_order_pressure(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    df = pd.read_parquet(ORDER_PRESSURE)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df


def load_insider_features(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    df = pd.read_parquet(INSIDER_FEATURES)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
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
    allow_2026: bool = False,
) -> pd.DataFrame:
    df = pd.read_parquet(EVENT_SURFACE)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df


def load_stock_daily(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    import glob
    pattern = f"{DATA_ROOT}/stock/gia_lich_su_{ticker}_1D.parquet"
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No data for {ticker}")
    df = pd.read_parquet(matches[0])
    df = df.sort_values("time").reset_index(drop=True)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    return df


if __name__ == "__main__":
    df = load_rl_signal_matrix()
    print(f"RL Signal Matrix loaded: {df.shape}")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"Columns: {list(df.columns)}")
    print(f"Unique tickers: {df['ticker'].nunique()}")