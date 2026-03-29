"""
Build quality-weighted insider signal features (H108).

Extends xs_insider_features.parquet with quality dimensions:
- Tier weighting: CEO/Chairman > CFO/Deputy > Board member > related party
- Position-size normalization: net volume / shares before transaction
- Execution commitment: actual / planned volume (did they follow through?)
- CEO-only signal: highest information asymmetry subset

Input:  data/features/xs_insider_deals_raw.parquet
Output: data/features/xs_insider_quality_features.parquet

Columns (trading_day, ticker):
    xs_ins_quality_buy_5d      — tier-weighted net plan vol, 5d rolling
    xs_ins_quality_buy_30d     — same, 30d rolling
    xs_ins_ceo_buy_5d          — CEO/Chairman only net plan vol, 5d rolling
    xs_ins_relative_size_5d    — net plan vol / VolumeBeforeTransaction, 5d mean
    xs_ins_exec_rate_5d        — actual/plan ratio for buys only, 5d mean

Usage:
    conda activate stocks
    python data_tools/build_insider_quality_features.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.stock_day_grid import build_stock_day_grid

RAW_PATH = REPO_ROOT / "data" / "features" / "xs_insider_deals_raw.parquet"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_insider_quality_features.parquet"
STOCK_DIR = REPO_ROOT / "data" / "stock"
EXCLUDE = {"VNINDEX", "VN30"}

# Vietnamese position titles → tier weights (higher = more informative)
TIER_WEIGHTS = {
    # Tier 1 — C-suite and board chair (highest information asymmetry)
    "Chủ tịch HĐQT": 1.0,
    "Phó Chủ tịch HĐQT": 1.0,
    "Tổng Giám đốc": 1.0,
    "Giám đốc": 1.0,
    # Tier 2 — Senior management
    "Phó Tổng GĐ": 0.7,
    "Phó Giám đốc": 0.7,
    "Giám đốc Tài chính": 0.7,
    "Kế toán trưởng": 0.7,
    "Công bố thông tin": 0.7,
    # Tier 3 — Board and supervisory members
    "Thành viên HĐQT": 0.5,
    "Thành viên HĐQT độc lập": 0.5,
    "Thành viên BKS": 0.5,
    "Trưởng BKS": 0.5,
    # Family/related (lowest weight — least informative)
    "Vợ": 0.3,
    "vợ": 0.3,
    "Chồng": 0.3,
    "Con": 0.3,
    "Em": 0.3,
    "Anh": 0.3,
    "Chị": 0.3,
    "Mẹ": 0.3,
    "Cha": 0.3,
    "Bố": 0.3,
}
DEFAULT_TIER_WEIGHT = 0.4  # unnamed or other positions


def assign_tier(pos: str) -> float:
    return TIER_WEIGHTS.get(pos.strip() if isinstance(pos, str) else "", DEFAULT_TIER_WEIGHT)


def rolling_sum(piv: pd.DataFrame, window: int) -> pd.DataFrame:
    """Backward-looking rolling sum with 1-day shift to avoid lookahead."""
    return piv.shift(1).rolling(window, min_periods=1).sum()


def rolling_mean(piv: pd.DataFrame, window: int) -> pd.DataFrame:
    """Backward-looking rolling mean with 1-day shift to avoid lookahead."""
    return piv.shift(1).rolling(window, min_periods=1).mean()


def melt_panel(piv: pd.DataFrame, col_name: str) -> pd.DataFrame:
    m = piv.reset_index().rename(columns={"index": "trading_day", "published_date": "trading_day"})
    m = m.melt(id_vars="trading_day", var_name="ticker", value_name=col_name)
    return m


def build_features() -> pd.DataFrame:
    raw = pd.read_parquet(RAW_PATH)
    raw["published_date"] = pd.to_datetime(raw["published_date"])

    # Only insider transactions (is_insider=True) — cleaner signal
    ins = raw[raw["is_insider"]].copy()
    ins["tier_weight"] = ins["TransactionManPosition"].map(assign_tier).fillna(DEFAULT_TIER_WEIGHT)

    # Quality score = net_plan_vol weighted by tier
    ins["quality_plan"] = ins["net_plan_vol"] * ins["tier_weight"]

    # Relative size = net_plan_vol / VolumeBeforeTransaction (position-normalized conviction)
    ins["relative_size"] = np.where(
        ins["VolumeBeforeTransaction"] > 0,
        ins["net_plan_vol"] / ins["VolumeBeforeTransaction"],
        0.0,
    )

    # Execution commitment for BUY transactions only
    # Positive exec_rate means insider followed through on their announced buy
    buy_mask = ins["net_plan_vol"] > 0
    ins["exec_rate"] = np.where(
        buy_mask & (ins["net_plan_vol"] > 0),
        ins["net_real_vol"].clip(upper=ins["net_plan_vol"]) / ins["net_plan_vol"],
        np.nan,
    )

    # CEO/Chairman tier-1 only subset
    ceo_mask = ins["TransactionManPosition"].isin([k for k, v in TIER_WEIGHTS.items() if v >= 1.0])
    ceo = ins[ceo_mask].copy()

    # Load grid
    grid_df = build_stock_day_grid(
        stock_dir=STOCK_DIR,
        exclude=EXCLUDE,
        start_year=2015,
    ).rename(columns={"time": "trading_day"})
    grid = grid_df.drop_duplicates()
    trading_days = sorted(grid["trading_day"].unique())

    def make_panel(df: pd.DataFrame, val_col: str) -> pd.DataFrame:
        return df.pivot_table(
            index="published_date", columns="ticker", values=val_col, aggfunc="sum"
        ).reindex(index=pd.to_datetime(trading_days)).fillna(0)

    def make_mean_panel(df: pd.DataFrame, val_col: str) -> pd.DataFrame:
        return df.pivot_table(
            index="published_date", columns="ticker", values=val_col, aggfunc="mean"
        ).reindex(index=pd.to_datetime(trading_days)).fillna(0)

    # Pivot each signal dimension
    quality_piv = make_panel(ins, "quality_plan")
    relsize_piv = make_mean_panel(ins[ins["net_plan_vol"] != 0], "relative_size")
    exec_piv = make_mean_panel(ins[buy_mask], "exec_rate")
    ceo_piv = make_panel(ceo, "quality_plan")

    # Rolling aggregations
    q5 = rolling_sum(quality_piv, 5)
    q30 = rolling_sum(quality_piv, 30)
    ceo5 = rolling_sum(ceo_piv, 5)
    rs5 = rolling_mean(relsize_piv, 5)
    er5 = rolling_mean(exec_piv, 5)

    # Melt to long format and merge
    dfs = [
        melt_panel(q5,   "xs_ins_quality_buy_5d"),
        melt_panel(q30,  "xs_ins_quality_buy_30d"),
        melt_panel(ceo5, "xs_ins_ceo_buy_5d"),
        melt_panel(rs5,  "xs_ins_relative_size_5d"),
        melt_panel(er5,  "xs_ins_exec_rate_5d"),
    ]

    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(df, on=["trading_day", "ticker"], how="left")

    result = grid.merge(result, on=["trading_day", "ticker"], how="left")
    for col in result.columns[2:]:
        result[col] = result[col].fillna(0)

    return result.sort_values(["trading_day", "ticker"]).reset_index(drop=True)


def main():
    print("Building insider quality features (H108)...")
    feat = build_features()

    feat_cols = [c for c in feat.columns if c not in ("trading_day", "ticker")]
    nonzero = feat[feat_cols].abs().sum(axis=1) > 0
    pct = 100 * nonzero.sum() / len(feat)
    print(f"Non-zero rows: {nonzero.sum():,} / {len(feat):,} ({pct:.1f}%)")
    for col in feat_cols:
        nz = (feat[col] != 0).sum()
        print(f"  {col}: {nz:,} ({100*nz/len(feat):.2f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved {len(feat):,} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
