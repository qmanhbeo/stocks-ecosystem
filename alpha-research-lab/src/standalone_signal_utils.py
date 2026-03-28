from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
S1_PATH = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
STOCK_DIR = REPO_ROOT / "data" / "stock"
RL_MATRIX_PATH = REPO_ROOT / "data" / "features" / "xs_rl_signal_matrix.parquet"
SECTOR_CLASS_PATH = REPO_ROOT / "data" / "features" / "sector_classification.parquet"

EXCLUDE = {"VNINDEX", "VN30"}
PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.60
VALUE_SCALE = 1e9


def load_s1_frame() -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH)
    s1["time"] = pd.to_datetime(s1["time"])
    return s1[s1["time"].dt.year <= 2025].copy()


def load_stock_panel(columns: list[str], min_rows: int = 0) -> pd.DataFrame:
    parts = []
    use_cols = ["time"] + columns
    for path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(path, columns=use_cols)
        except Exception:
            continue
        if len(df) < min_rows:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        df["ticker"] = ticker
        parts.append(df[["time", "ticker"] + columns])
    if not parts:
        return pd.DataFrame(columns=["time", "ticker"] + columns)
    return pd.concat(parts, ignore_index=True)


def load_ohlcv_wide(min_rows: int = 0) -> dict[str, pd.DataFrame]:
    long = load_stock_panel(["open", "high", "low", "close", "volume"], min_rows=min_rows)
    return {
        col: long.pivot_table(index="time", columns="ticker", values=col).sort_index()
        for col in ["open", "high", "low", "close", "volume"]
    }


def load_vni_close() -> pd.Series:
    vni = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet", columns=["time", "close"])
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time").set_index("time")
    return vni["close"]


def load_sector_labels(level: str = "icb_name3") -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_CLASS_PATH)
    sector = sector.rename(columns={"symbol": "ticker"})
    sector["sector_label"] = sector[level].fillna("Other")
    return sector[["ticker", "sector_label"]].drop_duplicates()


def to_long(wide_df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    return wide_df.reset_index().melt(id_vars="time", var_name="ticker", value_name=col_name)


def rank_frame(wide_df: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    return wide_df.rank(axis=1, method="average", ascending=ascending, pct=True)


def winsorize_by_row(wide_df: pd.DataFrame, lower: float = 0.01, upper: float = 0.99) -> pd.DataFrame:
    lo = wide_df.quantile(lower, axis=1)
    hi = wide_df.quantile(upper, axis=1)
    return wide_df.clip(lo, hi, axis=0)


def safe_clv(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    denom = high - low
    clv = (close - low).div(denom.replace(0, np.nan))
    return clv.mask(denom == 0, 0.5)


def compute_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, periods: int) -> pd.DataFrame:
    stock_ret = close.pct_change(periods)
    bench_ret = benchmark_close.pct_change(periods).reindex(stock_ret.index)
    return stock_ret.sub(bench_ret, axis=0)


def compute_beta(close: pd.DataFrame, benchmark_close: pd.Series, window: int, min_days: int) -> pd.DataFrame:
    stock_ret = close.pct_change(1)
    bench_ret = benchmark_close.pct_change(1).reindex(stock_ret.index)
    bench_mean = bench_ret.rolling(window, min_periods=min_days).mean()
    bench_var = bench_ret.rolling(window, min_periods=min_days).var(ddof=0)
    stock_mean = stock_ret.rolling(window, min_periods=min_days).mean()
    stock_xy_mean = stock_ret.mul(bench_ret, axis=0).rolling(window, min_periods=min_days).mean()
    return (stock_xy_mean - stock_mean.mul(bench_mean, axis=0)).div(
        bench_var.replace(0, np.nan), axis=0
    )


def cross_sectional_residual(target: pd.DataFrame, *controls: pd.DataFrame, min_obs: int = 20) -> pd.DataFrame:
    residual = pd.DataFrame(index=target.index, columns=target.columns, dtype=float)
    for date in target.index:
        pieces = [target.loc[date].rename("target")]
        for idx, control in enumerate(controls):
            pieces.append(control.loc[date].rename(f"control_{idx}"))
        frame = pd.concat(pieces, axis=1).dropna()
        if len(frame) < min_obs:
            continue
        x = np.ones((len(frame), 1), dtype=float)
        for idx in range(len(controls)):
            x = np.column_stack([x, frame[f"control_{idx}"].to_numpy(dtype=float)])
        y = frame["target"].to_numpy(dtype=float)
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        resid = y - x @ beta
        residual.loc[date, frame.index] = resid
    return residual


def compute_illiq(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    daily_value = close * volume / VALUE_SCALE
    ret1 = close.pct_change(1)
    return ret1.abs().div(daily_value.replace(0, np.nan))


def compute_illiq_level_rank(
    close: pd.DataFrame, volume: pd.DataFrame, window: int = 20, min_days: int = 10
) -> pd.DataFrame:
    illiq = compute_illiq(close, volume)
    illiq_20d = illiq.rolling(window, min_periods=min_days).mean()
    return rank_frame(illiq_20d, ascending=True)


def compute_volume_zscore(volume: pd.DataFrame, baseline_window: int = 60, min_days: int = 20) -> pd.DataFrame:
    vol_mean = volume.rolling(baseline_window, min_periods=min_days).mean()
    vol_std = volume.rolling(baseline_window, min_periods=min_days).std(ddof=0)
    return (volume - vol_mean).div(vol_std.replace(0, np.nan))


def daily_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> pd.DataFrame:
    rows = []
    for date, g in df.groupby("time"):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 10:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append(
            {
                "time": pd.Timestamp(date),
                "n": int(len(gg)),
                "ic": float(np.asarray(rho).flat[0]),
                "p_value": float(np.asarray(p).flat[0]),
            }
        )
    return pd.DataFrame(rows)


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict]:
    rows = []
    for year, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 500:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append(
            {
                "year": int(year),
                "n": int(len(gg)),
                "ic": float(np.asarray(rho).flat[0]),
                "p_value": float(np.asarray(p).flat[0]),
            }
        )
    return rows


def summarize_ic(rows: list[dict]) -> dict:
    if not rows:
        return {"avg_ic": None, "pos_years": 0, "years": 0, "pct_years_positive": None}
    ics = [row["ic"] for row in rows]
    pos_years = sum(1 for ic in ics if ic > 0)
    return {
        "avg_ic": float(np.mean(ics)),
        "pos_years": int(pos_years),
        "years": int(len(rows)),
        "pct_years_positive": float(pos_years / len(rows)),
        "yearly": rows,
    }


def spearman_stat(left: pd.Series, right: pd.Series) -> float:
    clean = pd.concat([left, right], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 100:
        return float("nan")
    stat = spearmanr(clean.iloc[:, 0], clean.iloc[:, 1]).statistic
    return float(np.asarray(stat).flat[0])


def gate_pass(avg_ic: float | None, corr: float, pct_years_positive: float | None) -> bool:
    return (
        abs(avg_ic or 0) > PASS_IC
        and abs(corr) < PASS_CORR
        and (pct_years_positive or 0) >= PASS_PCT_YEARS
    )


def evaluate_features(
    merged: pd.DataFrame, feature_cols: list[str], s1_col: str = "xs_proba", target_col: str = "actual"
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for feat_col in feature_cols:
        ic_rows = yearly_ic(merged, feat_col, target_col)
        ic_sum = summarize_ic(ic_rows)
        corr = spearman_stat(merged[feat_col], merged[s1_col])
        results[feat_col] = {
            **ic_sum,
            "corr_with_s1": corr,
            "gate_pass": gate_pass(ic_sum.get("avg_ic"), corr, ic_sum.get("pct_years_positive")),
        }
    return results


def load_candidate_matrix() -> pd.DataFrame:
    matrix = pd.read_parquet(RL_MATRIX_PATH)
    matrix["time"] = pd.to_datetime(matrix["time"])
    return matrix


def candidate_columns(matrix: pd.DataFrame) -> list[str]:
    return [
        col
        for col in matrix.columns
        if col.startswith("c") and col != "c5_signal_present"
    ]


def pairwise_candidate_corrs(feature_df: pd.DataFrame, feature_col: str) -> dict[str, float]:
    matrix = load_candidate_matrix()
    merged = matrix.merge(feature_df[["time", "ticker", feature_col]], on=["time", "ticker"], how="inner")
    corrs = {}
    for col in candidate_columns(matrix):
        corrs[col] = spearman_stat(merged[feature_col], merged[col])
    return corrs


def annotate_redundancy(
    feature_df: pd.DataFrame, results: dict[str, dict], threshold: float = PASS_CORR
) -> dict[str, dict]:
    for feature_col, result in results.items():
        if not result.get("gate_pass"):
            result["candidate_corrs"] = {}
            result["max_abs_candidate_corr"] = None
            result["redundant_with"] = None
            result["final_pass"] = False
            continue
        corrs = pairwise_candidate_corrs(feature_df, feature_col)
        valid = {k: v for k, v in corrs.items() if pd.notna(v)}
        if valid:
            redundant_with, max_abs_corr = max(valid.items(), key=lambda item: abs(item[1]))
            max_abs_corr = float(abs(max_abs_corr))
            result["candidate_corrs"] = valid
            result["max_abs_candidate_corr"] = max_abs_corr
            result["redundant_with"] = redundant_with if max_abs_corr >= threshold else None
            result["final_pass"] = max_abs_corr < threshold
        else:
            result["candidate_corrs"] = {}
            result["max_abs_candidate_corr"] = None
            result["redundant_with"] = None
            result["final_pass"] = True
    return results
