"""
ensemble_wf.py -- X3: Ensemble cross-sectional + single-stock model predictions.

Strategy:
  - Load per-date FPT probabilities from XS model (saved by cross_sectional_wf.py --save-proba)
  - Load per-date FPT probabilities from a single-stock walk-forward run (saved by this script's
    --save-ss-proba flag, or pre-generated)
  - Ensemble: average probas, then apply threshold
  - When both models agree (both > min_conf): high-conviction signal
  - When they disagree: abstain

Usage:
    # Step 1: generate XS probabilities
    python cross_sectional_wf.py --save-proba data/features/xs_fpt_proba.csv

    # Step 2: generate single-stock (E8) probabilities
    python ensemble_wf.py --save-ss-proba data/features/ss_fpt_proba.csv --ss-config configs/E8_rel_plus_tech.json

    # Step 3: ensemble
    python ensemble_wf.py --xs-proba data/features/xs_fpt_proba.csv \\
                          --ss-proba data/features/ss_fpt_proba.csv \\
                          --min-conf 0.55
"""
import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from scipy.stats import binomtest

from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model
from src.run_summary import write_run_summary


def save_single_stock_proba(config_path: str, out_csv: str, min_train_years: int = 3,
                            xs_meta_csv: str = ""):
    """Walk-forward on single-stock E8 config, save per-date FPT probabilities.

    xs_meta_csv: optional path to XS model proba CSV; if provided, xs_proba is added as a feature
                 (H18 — let the SS model learn when to trust the cross-sectional signal).
    """
    with open(config_path) as f:
        config = json.load(f)

    data_cfg  = config.get("data", {})
    file_path = data_cfg.get("file_path", "data/stock/gia_lich_su_FPT_1D.parquet")
    start_date = data_cfg.get("start_date", "2016-01-01")
    target_col = data_cfg.get("target_col", "future_rel_dir_5d")

    df = load_data(file_path, start_date)
    df = generate_features(df, config)
    feature_cols = list(get_feature_columns(df, config))
    df["_year"] = pd.to_datetime(df["time"]).dt.year

    # H18: merge XS proba as a meta-feature (no look-ahead: xs_proba CSV is walk-forward output)
    if xs_meta_csv:
        xs_meta = pd.read_csv(xs_meta_csv, parse_dates=["time"])
        xs_meta = xs_meta[["time", "xs_proba"]].rename(columns={"xs_proba": "xs_meta_proba"})
        df = df.merge(xs_meta, on="time", how="left")
        df["xs_meta_proba"] = df["xs_meta_proba"].fillna(0.5)  # neutral for missing dates
        feature_cols = feature_cols + ["xs_meta_proba"]
        print(f"  H18: xs_meta_proba merged from {xs_meta_csv}")

    start_year = int(df["_year"].min()) + min_train_years
    end_year   = int(df["_year"].max())
    if end_year == datetime.now().year:
        end_year -= 1

    rows = []
    for test_year in range(start_year, end_year + 1):
        train_mask = df["_year"] < test_year
        test_mask  = df["_year"] == test_year
        train_df = df[train_mask].copy()
        test_df  = df[test_mask].copy()
        if len(train_df) < 200 or len(test_df) < 20:
            continue

        X_train = train_df[feature_cols]
        y_train = train_df[target_col]
        X_test  = test_df[feature_cols]
        y_test  = test_df[target_col]

        model_type = config.get("model", {}).get("type", "")
        n_val = max(30, int(len(X_train) * 0.15))
        X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
        X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]

        model = get_model(config)
        if model_type in ("xgboost", "xgboost_classifier"):
            model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
        else:
            model.fit(X_tr, y_tr)

        if not hasattr(model, "predict_proba"):
            print(f"  [WARN] Model {model_type} does not support predict_proba. Skipping.")
            continue

        probas = model.predict_proba(X_test)[:, 1]
        for time_val, proba, actual in zip(test_df["time"].values, probas, y_test.values):
            rows.append({"time": time_val, "year": test_year,
                         "ss_proba": round(float(proba), 4), "actual": int(actual)})

    proba_df = pd.DataFrame(rows)
    proba_df.to_csv(out_csv, index=False)
    print(f"  Single-stock probabilities saved: {out_csv} ({len(proba_df)} rows, "
          f"{proba_df['year'].nunique()} years)")
    return proba_df


def _load_vni_trend(vni_path: str, window: int = 20) -> pd.Series:
    """Compute VNINDEX N-day return, indexed by date."""
    vni = pd.read_parquet(vni_path)[["time", "close"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    ret = vni["close"] / vni["close"].shift(window) - 1
    return pd.Series(ret.values, index=vni["time"].values)


def _load_rel_return(fpt_path: str, vni_path: str, window: int = 60) -> pd.Series:
    """Compute FPT 60d relative return vs VNINDEX, indexed by date."""
    fpt = pd.read_parquet(fpt_path)[["time", "close"]].copy()
    fpt["time"] = pd.to_datetime(fpt["time"])
    fpt = fpt.sort_values("time")
    vni = pd.read_parquet(vni_path)[["time", "close"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    fpt_ret = fpt["close"] / fpt["close"].shift(window) - 1
    vni_ret = vni["close"] / vni["close"].shift(window) - 1
    rel = fpt_ret.values - vni_ret.reindex(fpt.index).values
    return pd.Series(rel, index=fpt["time"].values)


def run_ensemble(xs_proba_csv: str, ss_proba_csv: str,
                 min_conf: float = 0.55, agree_only: bool = False,
                 trend_filter: float = 0.0, xs_weight: float = 0.5,
                 vix_min: float = 0.0, vix_max: float = 0.0,
                 vn_trend_min: float = 0.0,
                 vn_trend_window: int = 20, vn_trend_min2: float = 0.0,
                 vn_trend_window2: int = 60,
                 direction_breakdown: bool = False):
    """
    Ensemble XS model + single-stock model probabilities.

    min_conf        : minimum average probability for any prediction (default 0.55)
    agree_only      : if True, only trade when both models agree on direction
    trend_filter    : block counter-trend signals via FPT 60d relative return threshold
    xs_weight       : weight given to XS model (default 0.5 = equal; 0.7 = XS-heavy)
    vix_min         : minimum VIX level required to trade (e.g. 18 = skip low-vol regimes)
    vix_max         : maximum VIX level to allow trading (e.g. 40 = skip extreme crash regimes)
    vn_trend_min    : minimum VNINDEX N-day return to allow trading (e.g. -0.08 = skip when
                      VNINDEX has fallen >8% over the window; blocks deep bear markets like 2022)
    vn_trend_window : lookback window in days for vn_trend_min (default 20; try 60 for slower filter)
    vn_trend_min2   : second VNINDEX trend threshold (different window, AND with vn_trend_min)
    vn_trend_window2: lookback window for vn_trend_min2 (default 60)
    """
    xs = pd.read_csv(xs_proba_csv, parse_dates=["time"])
    ss = pd.read_csv(ss_proba_csv, parse_dates=["time"])

    merged = xs.merge(ss[["time", "ss_proba"]], on="time", how="inner")
    if len(merged) == 0:
        print("  No overlapping dates between XS and single-stock probabilities.")
        return

    # Ensemble: weighted average probability
    ss_weight = 1.0 - xs_weight
    merged["ens_proba"] = merged["xs_proba"] * xs_weight + merged["ss_proba"] * ss_weight
    merged["ens_pred"]  = (merged["ens_proba"] > 0.5).astype(int)
    merged["xs_pred"]   = (merged["xs_proba"] > 0.5).astype(int)
    merged["ss_pred"]   = (merged["ss_proba"] > 0.5).astype(int)

    # Agreement mask
    merged["agree"] = (merged["xs_pred"] == merged["ss_pred"]).astype(int)

    # Confidence mask
    merged["confident"] = (np.abs(merged["ens_proba"] - 0.5) >= (min_conf - 0.5)).astype(int)

    # VIX filter: only trade within VIX band [vix_min, vix_max]
    if vix_min > 0 or vix_max > 0:
        vix_path = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
        if vix_path.exists():
            vix_df = pd.read_parquet(vix_path)[["time", "close"]].copy()
            vix_df["time"] = pd.to_datetime(vix_df["time"])
            vix_df = vix_df.rename(columns={"close": "vix_close"}).sort_values("time")
            vix_aligned = vix_df.set_index("time")["vix_close"].reindex(merged["time"].values, method="ffill")
            merged["vix"] = vix_aligned.values
            if vix_min > 0:
                merged["confident"] = merged["confident"] & (merged["vix"] >= vix_min).astype(int)
            if vix_max > 0:
                merged["confident"] = merged["confident"] & (merged["vix"] <= vix_max).astype(int)
        else:
            print(f"  [WARN] VIX data not found at {vix_path}. VIX filter disabled.")
            vix_min = 0.0
            vix_max = 0.0

    # VNINDEX trend filter: skip trades when broad market is in sustained decline
    # Supports two windows simultaneously (AND logic) for stronger discrimination
    vni_path = "data/stock/gia_lich_su_VNINDEX_1D.parquet"
    for _w, _thr in [(vn_trend_window, vn_trend_min), (vn_trend_window2, vn_trend_min2)]:
        if _thr == 0.0:
            continue
        try:
            vni_trend = _load_vni_trend(vni_path, window=_w)
            vni_aligned = vni_trend.reindex(merged["time"].values, method="ffill")
            merged[f"vn_trend_{_w}d"] = vni_aligned.values
            merged["confident"] = merged["confident"] & (merged[f"vn_trend_{_w}d"] >= _thr).astype(int)
        except Exception as e:
            print(f"  [WARN] VNINDEX trend filter ({_w}d): {e}. Disabled.")

    # Trend filter: block counter-trend signals based on FPT 60d relative return
    if trend_filter > 0:
        try:
            rel60 = _load_rel_return(
                "data/stock/gia_lich_su_FPT_1D.parquet",
                "data/stock/gia_lich_su_VNINDEX_1D.parquet",
                window=60
            )
            rel60_aligned = rel60.reindex(merged["time"].values, method="ffill")
            merged["rel60"] = rel60_aligned.values
            # Block: don't predict underperformance (0) when 60d trend strongly positive
            counter_trend = (
                ((merged["ens_pred"] == 0) & (merged["rel60"] > trend_filter)) |
                ((merged["ens_pred"] == 1) & (merged["rel60"] < -trend_filter))
            )
            merged["confident"] = merged["confident"] & (~counter_trend).astype(int)
        except Exception as e:
            print(f"  [WARN] Could not load trend data: {e}. Trend filter disabled.")
            trend_filter = 0.0

    print(f"\n{'='*70}")
    print(f"ENSEMBLE WALK-FORWARD: XS + Single-Stock")
    print(f"XS proba: {xs_proba_csv}  |  SS proba: {ss_proba_csv}")
    vn_trend_parts = ""
    if vn_trend_min != 0.0:
        vn_trend_parts += f"  |  VN {vn_trend_window}d >= {vn_trend_min:.0%}"
    if vn_trend_min2 != 0.0:
        vn_trend_parts += f" & {vn_trend_window2}d >= {vn_trend_min2:.0%}"
    vix_parts = ""
    if vix_min > 0:
        vix_parts += f"  |  VIX >= {vix_min:.1f}"
    if vix_max > 0:
        vix_parts += f"  |  VIX <= {vix_max:.1f}"
    print(f"Min confidence: {min_conf:.2f}  |  Agree-only: {agree_only}"
          + vix_parts
          + vn_trend_parts
          + (f"  |  Trend filter: {trend_filter:.0%}" if trend_filter > 0 else ""))
    print(f"{'='*70}")
    print(f"\n  {'year':>5}  {'n_all':>7}  {'xs_acc':>8}  {'ss_acc':>8}  {'ens_acc':>8}"
          f"  {'n_conf':>7}  {'conf_acc':>9}  {'edge':>7}")
    print("  " + "-" * 72)

    per_year = []
    for year, grp in merged.groupby("year"):
        actual = grp["actual"].values
        naive  = actual.mean()

        xs_acc  = (grp["xs_pred"].values == actual).mean()
        ss_acc  = (grp["ss_pred"].values == actual).mean()
        ens_acc = (grp["ens_pred"].values == actual).mean()

        # Apply filter: confident AND (optionally) agree
        filt = grp["confident"].values.astype(bool)
        if agree_only:
            filt = filt & grp["agree"].values.astype(bool)

        n_conf = filt.sum()
        if n_conf >= 5:
            conf_actual = actual[filt]
            conf_pred   = grp["ens_pred"].values[filt]
            conf_acc    = (conf_pred == conf_actual).mean()
            edge        = conf_acc - naive
            pval = binomtest(int((conf_pred == conf_actual).sum()), n_conf, naive).pvalue
            sig  = "*" if pval < 0.05 else " "
        else:
            conf_acc = edge = float("nan")
            sig = " "

        print(f"  {year:>5}  {len(grp):>7}  {xs_acc*100:>7.1f}%  {ss_acc*100:>7.1f}%"
              f"  {ens_acc*100:>7.1f}%  {n_conf:>7}  "
              + (f"{conf_acc*100:>8.1f}%  {edge*100:>+6.2f}%{sig}" if not np.isnan(conf_acc) else "     N/A       N/A"))

        # H25: per-direction breakdown
        if direction_breakdown and n_conf >= 5:
            conf_pred_arr   = grp["ens_pred"].values[filt]
            conf_actual_arr = actual[filt]
            for direction, label in [(1, "UP  "), (0, "DOWN")]:
                dir_mask = conf_pred_arr == direction
                if dir_mask.sum() >= 3:
                    n_d  = dir_mask.sum()
                    acc_d = (conf_pred_arr[dir_mask] == conf_actual_arr[dir_mask]).mean()
                    edge_d = acc_d - naive
                    print(f"         {label}  n={n_d:>3}  acc={acc_d*100:.1f}%  edge={edge_d*100:+.2f}%")

        per_year.append({
            "year": int(year), "n_all": len(grp),
            "xs_acc": round(xs_acc, 4), "ss_acc": round(ss_acc, 4),
            "ens_acc": round(ens_acc, 4),
            "n_conf": int(n_conf),
            "conf_acc": round(conf_acc, 4) if not np.isnan(conf_acc) else None,
            "conf_edge": round(edge, 4) if not np.isnan(edge) else None,
        })

    if not per_year:
        return

    # Summary
    valid = [r for r in per_year if r["conf_acc"] is not None]
    if valid:
        avg_edge = np.mean([r["conf_edge"] for r in valid])
        avg_acc  = np.mean([r["conf_acc"] for r in valid])
        print(f"\n  SUMMARY (Ensemble, n_conf ≥ 5)")
        print(f"  Avg conf acc  : {avg_acc*100:.2f}%")
        print(f"  Avg conf edge : {avg_edge*100:+.2f}%")

    name = "X3_ensemble"
    if trend_filter > 0:
        name = f"X5_ensemble_trend_{trend_filter:.2f}"
    if xs_weight != 0.5:
        name = f"X6_ensemble_xswt_{xs_weight:.1f}"
    if vix_min > 0 or vix_max > 0:
        name = f"X8_ensemble_vix{vix_min:.0f}" + (f"_max{vix_max:.0f}" if vix_max > 0 else "")
    if vn_trend_min != 0.0 or vn_trend_min2 != 0.0:
        w1, t1 = vn_trend_window, vn_trend_min
        w2, t2 = vn_trend_window2, vn_trend_min2
        if vn_trend_min2 == 0.0:
            name = f"X9_vntrend{w1}d_{t1:.2f}"
        else:
            name = f"X9_vntrend{w1}d_{t1:.2f}_and_{w2}d_{t2:.2f}"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "ts": ts,
        "name": name,
        "xs_proba_csv": xs_proba_csv,
        "ss_proba_csv": ss_proba_csv,
        "min_conf": min_conf,
        "agree_only": agree_only,
        "trend_filter": trend_filter,
        "xs_weight": xs_weight,
        "vix_min": vix_min,
        "vix_max": vix_max,
        "vn_trend_min": vn_trend_min,
        "vn_trend_window": vn_trend_window,
        "vn_trend_min2": vn_trend_min2,
        "vn_trend_window2": vn_trend_window2,
        "per_year": per_year,
    }
    with open("xs_wf_results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"\n  Results appended to xs_wf_results.jsonl")

    summary_path = write_run_summary(
        ts=ts,
        mode="ensemble",
        name=name,
        summary={
            "avg_conf_acc": round(float(np.mean([r["conf_acc"] for r in valid])), 4) if valid else None,
            "avg_conf_edge": round(float(np.mean([r["conf_edge"] for r in valid])), 4) if valid else None,
            "n_valid_years": len(valid),
            "total_years": len(per_year),
        },
        artifacts={
            "xs_proba_csv": xs_proba_csv,
            "ss_proba_csv": ss_proba_csv,
            "xs_wf_log": "xs_wf_results.jsonl",
        },
        metadata={
            "min_conf": min_conf,
            "agree_only": agree_only,
            "xs_weight": xs_weight,
            "vix_min": vix_min,
            "vix_max": vix_max,
        },
    )
    print(f"  Run summary saved to {summary_path}")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X3: Ensemble XS + single-stock probabilities")
    sub = parser.add_subparsers(dest="cmd")

    # Step 2: generate single-stock probabilities
    p_ss = sub.add_parser("save-ss", help="Save single-stock walk-forward probabilities")
    p_ss.add_argument("--ss-config", required=True, help="Config JSON for single-stock model (e.g. E8)")
    p_ss.add_argument("--out", required=True, help="Output CSV path for single-stock probabilities")
    p_ss.add_argument("--min-train-years", type=int, default=3)
    p_ss.add_argument("--xs-meta", default="", help="[H18] XS proba CSV to add as meta-feature in SS training")

    # Step 3: ensemble
    p_ens = sub.add_parser("ensemble", help="Run ensemble analysis")
    p_ens.add_argument("--xs-proba", required=True, help="XS model proba CSV")
    p_ens.add_argument("--ss-proba", required=True, help="Single-stock proba CSV")
    p_ens.add_argument("--min-conf", type=float, default=0.55,
                       help="Minimum ensemble proba for a prediction (default 0.55)")
    p_ens.add_argument("--agree-only", action="store_true",
                       help="Only trade when both models agree on direction")
    p_ens.add_argument("--trend-filter", type=float, default=0.0,
                       help="Block counter-trend signals: threshold for FPT 60d relative return "
                            "(e.g. 0.05 = block bearish signals when FPT has beaten VNINDEX by 5%+ over 60d)")
    p_ens.add_argument("--xs-weight", type=float, default=0.5,
                       help="Weight for XS model in ensemble (default 0.5 = equal weight; 0.7 = XS-heavy)")
    p_ens.add_argument("--vix-min", type=float, default=0.0,
                       help="Minimum VIX level required to trade (e.g. 18 = skip low-vol regimes)")
    p_ens.add_argument("--vix-max", type=float, default=0.0,
                       help="Maximum VIX level allowed to trade (e.g. 40 = skip extreme crash regimes; "
                            "0 = no cap)")
    p_ens.add_argument("--vn-trend-min", type=float, default=0.0,
                       help="Minimum VNINDEX N-day return to allow trading (e.g. -0.05 blocks "
                            ">5%% decline; blocks deep bear markets like 2022)")
    p_ens.add_argument("--vn-trend-window", type=int, default=20,
                       help="Lookback window for --vn-trend-min (default 20; try 60 for slower filter)")
    p_ens.add_argument("--vn-trend-min2", type=float, default=0.0,
                       help="Second VNINDEX trend threshold (different window, AND logic)")
    p_ens.add_argument("--vn-trend-window2", type=int, default=60,
                       help="Lookback window for --vn-trend-min2 (default 60)")
    p_ens.add_argument("--direction-breakdown", action="store_true",
                       help="H25: print per-direction (UP/DOWN) accuracy breakdown per year")

    args = parser.parse_args()

    if args.cmd == "save-ss":
        save_single_stock_proba(args.ss_config, args.out, args.min_train_years,
                                getattr(args, "xs_meta", ""))
    elif args.cmd == "ensemble":
        run_ensemble(args.xs_proba, args.ss_proba, args.min_conf, args.agree_only,
                     getattr(args, "trend_filter", 0.0), getattr(args, "xs_weight", 0.5),
                     getattr(args, "vix_min", 0.0), getattr(args, "vix_max", 0.0),
                     getattr(args, "vn_trend_min", 0.0),
                     getattr(args, "vn_trend_window", 20),
                     getattr(args, "vn_trend_min2", 0.0),
                     getattr(args, "vn_trend_window2", 60),
                     getattr(args, "direction_breakdown", False))
    else:
        parser.print_help()
