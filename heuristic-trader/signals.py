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

SIGNAL_REGISTRY = {
    "s1_proba": {
        "source": "xs_rl_signal_matrix",
        "column": "s1_proba",
        "description": "Cross-sectional relative momentum (primary signal)",
        "status": "READY",
    },
    "c16_rank": {
        "source": "xs_order_pressure_daily",
        "column": "order_volume_ratio_rank",
        "description": "C16 order volume ratio rank",
        "status": "READY",
    },
    "c17_raw": {
        "source": "xs_order_pressure_daily",
        "column": "order_volume_ratio",
        "description": "C17 raw order volume ratio (not ranked)",
        "status": "READY",
    },
    "c18_delta": {
        "source": "xs_order_pressure_daily",
        "column": "order_volume_ratio_rank_delta",
        "description": "C18 order pressure rank delta (today - yesterday)",
        "status": "READY",
        "derivation": "rank(t) - rank(t-1) per ticker, fail-closed on missing prior",
    },
    "c17_active_boost": {
        "source": "xs_order_pressure_daily",
        "column": "c17_active_boost",
        "description": "C17 raw order volume ratio with active-state boost plus rank-delta adjustment",
        "status": "READY",
        "derivation": "order_volume_ratio + boost_strength * 1[rank < active_rank_threshold] + delta_weight * (rank(t)-rank(t-1))",
    },
    "low_breadth_flag": {
        "source": "xs_order_pressure_daily",
        "column": "is_low_breadth",
        "description": "Date-level low breadth regime flag from active-count percentile",
        "status": "READY",
        "derivation": "active_count(rank<0.2) ranked by date percentile; low_breadth when percentile <= 0.25",
    },
}


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


def load_order_pressure_raw(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """Load C17 raw order volume ratio (not ranked)."""
    cols = ['time', 'ticker', 'order_volume_ratio', 'order_pressure_available']
    df = pd.read_parquet(ORDER_PRESSURE, columns=cols)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df['ticker'].isin(tickers)]
    return df


def load_order_pressure_delta(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """
    Load C18 order pressure rank delta.

    Formula: c18_delta = order_volume_ratio_rank(t) - order_volume_ratio_rank(t-1)

    Derivation rules:
    - Uses only current and prior date data (no future leakage)
    - Per-ticker computation: for each ticker, compute delta from prior trading day
    - Fail-closed: if prior day missing (first observation), set delta to 0.0
    - Column: order_volume_ratio_rank_delta

    Source: H431 (Session 310)
    """
    cols = ['time', 'ticker', 'order_volume_ratio_rank']
    df = pd.read_parquet(ORDER_PRESSURE, columns=cols)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df['ticker'].isin(tickers)]

    df = df.sort_values(['ticker', 'time'])
    df['prior_rank'] = df.groupby('ticker')['order_volume_ratio_rank'].shift(1)
    df['order_volume_ratio_rank_delta'] = df['order_volume_ratio_rank'] - df['prior_rank']
    df['order_volume_ratio_rank_delta'] = df['order_volume_ratio_rank_delta'].fillna(0.0)

    return df[['time', 'ticker', 'order_volume_ratio_rank_delta']]


def load_order_pressure_c17_active_boost(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
    allow_2026: bool = False,
    active_rank_threshold: float = 0.2,
    boost_strength: float = 0.35,
    delta_weight: float = 0.20,
) -> pd.DataFrame:
    """
    Load C17 active-boost transformed signal.

    Formula:
      c17_active_boost =
        order_volume_ratio
        + boost_strength * 1[order_volume_ratio_rank < active_rank_threshold]
        + delta_weight * (order_volume_ratio_rank(t) - order_volume_ratio_rank(t-1))

    This is intentionally non-monotonic relative to raw/rank-only C17-C16 and can
    alter per-date Top-K ordering by boosting active-state names.
    """
    cols = ["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]
    df = pd.read_parquet(ORDER_PRESSURE, columns=cols)
    df = _apply_lockbox_filter(df, start, end, allow_2026)
    if tickers:
        df = df[df["ticker"].isin(tickers)]

    df = df.sort_values(["ticker", "time"]).copy()
    df["prior_rank"] = df.groupby("ticker")["order_volume_ratio_rank"].shift(1)
    df["rank_delta"] = (df["order_volume_ratio_rank"] - df["prior_rank"]).fillna(0.0)
    active_flag = (df["order_volume_ratio_rank"] < float(active_rank_threshold)).astype(float)
    df["c17_active_boost"] = (
        df["order_volume_ratio"]
        + float(boost_strength) * active_flag
        + float(delta_weight) * df["rank_delta"]
    )
    return df[["time", "ticker", "c17_active_boost"]]


def load_low_breadth_regime(
    start: str | None = None,
    end: str | None = None,
    allow_2026: bool = False,
    active_rank_threshold: float = 0.2,
    low_breadth_percentile: float = 0.25,
) -> pd.DataFrame:
    """
    Build date-level low-breadth regime flag from order-pressure active counts.

    Definition mirrors the H528/H529 branch:
    - active state per row: order_volume_ratio_rank < active_rank_threshold
    - active_count per date: sum(active state)
    - breadth_percentile per date: percentile rank of active_count across dates
    - is_low_breadth: breadth_percentile <= low_breadth_percentile
    """
    cols = ["time", "ticker", "order_volume_ratio_rank"]
    df = pd.read_parquet(ORDER_PRESSURE, columns=cols)
    df = _apply_lockbox_filter(df, start, end, allow_2026)

    df["is_active"] = (df["order_volume_ratio_rank"] < float(active_rank_threshold)).astype(int)
    date_breadth = df.groupby("time", as_index=False)["is_active"].sum().rename(columns={"is_active": "active_count"})
    date_breadth["breadth_percentile"] = date_breadth["active_count"].rank(pct=True)
    date_breadth["is_low_breadth"] = (
        date_breadth["breadth_percentile"] <= float(low_breadth_percentile)
    ).astype(int)

    return date_breadth[["time", "active_count", "breadth_percentile", "is_low_breadth"]]


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
    "c16_rank": "C16 order volume ratio rank",
    "c17_raw": "C17 raw order volume ratio (not ranked)",
    "c18_delta": "C18 order pressure rank delta (acceleration)",
    "c17_active_boost": "C17 raw + active-state boost (non-monotonic transform)",
    "low_breadth_flag": "Date-level low breadth regime flag (active-count percentile)",
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
