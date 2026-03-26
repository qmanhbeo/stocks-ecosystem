"""
Standalone significance checks for dense signal candidates.

Outputs:
- IC/year consistency for ticker-day standalone features
- Correlation with S1 (H93 xs_proba) for orthogonality
- Context check for date-level regime signal vs S1 daily top-5 edge
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data_loader import load_data
from src.feature_engineering import generate_features
from src.run_summary import write_run_summary

STOCK_DIR = REPO_ROOT / "data" / "stock"
S1_PATH = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
OC_PATH = REPO_ROOT / "data" / "features" / "xs_open_close_asymmetry.parquet"
SKEW_PATH = REPO_ROOT / "data" / "features" / "xs_return_skewness.parquet"
DISP_PATH = REPO_ROOT / "data" / "features" / "xs_dispersion_regime_daily.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


CFG = {
    "data": {"target_col": "future_rel_dir_5d", "start_date": "2012-01-01"},
    "features": {
        "base_cols": [],
        "use_lags": False,
        "use_ma": False,
        "use_ma_dist": True,
        "ma_windows": [5, 10, 20, 50],
        "use_rsi": True,
        "use_macd": True,
        "use_bb": True,
        "use_atr": True,
        "use_candle": True,
        "use_stoch": True,
        "use_willr": False,
        "use_adx": True,
        "use_hist_vol": True,
        "hist_vol_windows": [5, 10, 20],
        "use_cci": False,
        "use_volume_signals": False,
        "use_market_relative": True,
        "index_file": "data/stock/gia_lich_su_VNINDEX_1D.parquet",
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
    },
    "model": {"type": "xgboost_classifier", "params": {}},
}


def load_future_rel_5d() -> pd.DataFrame:
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            raw = load_data(str(f), "2012-01-01")
            if len(raw) < 300:
                continue
            feat = generate_features(raw, CFG)
            parts.append(feat[["time", "future_rel_return_5d"]].assign(ticker=ticker))
        except Exception:
            continue
    out = pd.concat(parts, ignore_index=True)
    out["time"] = pd.to_datetime(out["time"])
    return out


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for y, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 500:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append({"year": int(y), "n": int(len(gg)), "ic": float(rho), "p_value": float(p)})
    return pd.DataFrame(rows)


def summarize_ic(tbl: pd.DataFrame) -> dict:
    if tbl.empty:
        return {"avg_ic": None, "pos_years": 0, "years": 0}
    return {
        "avg_ic": float(tbl["ic"].mean()),
        "pos_years": int((tbl["ic"] > 0).sum()),
        "years": int(len(tbl)),
    }


def main():
    fr = load_future_rel_5d()
    s1 = pd.read_parquet(S1_PATH)
    s1["time"] = pd.to_datetime(s1["time"])

    oc = pd.read_parquet(OC_PATH)[["time", "ticker", "oc_asym_5d"]]
    oc["time"] = pd.to_datetime(oc["time"])
    skew = pd.read_parquet(SKEW_PATH)[["time", "ticker", "ret_skew_z20"]]
    skew["time"] = pd.to_datetime(skew["time"])
    disp = pd.read_parquet(DISP_PATH)[["time", "xs_dispersion_z20"]]
    disp["time"] = pd.to_datetime(disp["time"])

    m_oc = fr.merge(oc, on=["time", "ticker"], how="inner").merge(
        s1[["time", "ticker", "xs_proba"]], on=["time", "ticker"], how="inner"
    )
    m_sk = fr.merge(skew, on=["time", "ticker"], how="inner").merge(
        s1[["time", "ticker", "xs_proba"]], on=["time", "ticker"], how="inner"
    )

    ic_oc = yearly_ic(m_oc, "oc_asym_5d", "future_rel_return_5d")
    ic_sk = yearly_ic(m_sk, "ret_skew_z20", "future_rel_return_5d")

    corr_oc_s1 = float(m_oc[["oc_asym_5d", "xs_proba"]].corr(method="spearman").iloc[0, 1])
    corr_sk_s1 = float(m_sk[["ret_skew_z20", "xs_proba"]].corr(method="spearman").iloc[0, 1])

    # Date-level context check: dispersion vs daily S1 top-5 edge.
    m_daily = s1.merge(fr, on=["time", "ticker"], how="inner")
    top5 = (
        m_daily.sort_values(["time", "xs_proba"], ascending=[True, False])
        .groupby("time")
        .head(5)
        .groupby("time")["future_rel_return_5d"]
        .mean()
        .rename("s1_top5_edge")
        .reset_index()
    )
    ctx = top5.merge(disp, on="time", how="left").dropna()
    ctx_ic, ctx_p = spearmanr(ctx["xs_dispersion_z20"], ctx["s1_top5_edge"])

    out = {
        "oc_asym_5d": {
            **summarize_ic(ic_oc),
            "corr_with_s1": corr_oc_s1,
        },
        "ret_skew_z20": {
            **summarize_ic(ic_sk),
            "corr_with_s1": corr_sk_s1,
        },
        "dispersion_context_vs_s1_top5_edge": {
            "spearman": float(ctx_ic),
            "p_value": float(ctx_p),
            "n_days": int(len(ctx)),
        },
    }

    print(json.dumps(out, indent=2))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_dense_signal_standalone_checks_details.json"
    details.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="dense_signal_standalone_checks",
        summary=out,
        artifacts={"details_json": str(details)},
        metadata={},
    )
    print(f"summary: {path}")


if __name__ == "__main__":
    main()
