"""
H292 - macro theme router audit.

Question:
- Do the CafeF macro themes route into the right sector basket, or are they
  just a pooled macro-news count with no sector specificity?

Design:
- use the nonzero macro-theme window already observed in H290/H291, 2015-2017
- build equal-weight sector baskets for banking, real estate, and a combined
  regulated basket from daily close prices
- compare the daily macro-theme fractions against 5d forward excess return for
  the matching sector basket
- test whether the matched theme strengthens when the matching sector rotation
  state and event density are high
- keep the branch only if the matched theme beats the mismatched controls and
  the gated state is materially better than the ungated surface

Usage:
    conda run -n stocks python analysis/h292_macro_theme_router_audit.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close


FEATURE_PATH = data_path("features/xs_llm_news_market_daily.parquet")
SECTOR_CLASS_PATH = data_path("features/sector_classification.parquet")
SECTOR_ROTATION_PATH = data_path("features/xs_sector_rotation_daily.parquet")
EVENT_SURFACE_PATH = data_path("features/event_surface_daily.parquet")

TARGET_YEAR_MIN = 2015
TARGET_YEAR_MAX = 2017
TARGET_HORIZON = 5

MATCHES = {
    "banking": {
        "theme_col": "frac_banking_theme",
        "basket_label": "banking",
        "sector_names": ["ngân hàng", "ngan hang"],
    },
    "real_estate": {
        "theme_col": "frac_real_estate_theme",
        "basket_label": "real_estate",
        "sector_names": ["bất động sản", "bat dong san"],
    },
    "regulation": {
        "theme_col": "frac_regulation_theme",
        "basket_label": "regulated_combo",
        "sector_names": [],
    },
}

CONTROL_THEMES = ["frac_banking_theme", "frac_real_estate_theme", "frac_regulation_theme"]


def _future_excess_return(close: pd.Series, benchmark_close: pd.Series, *, periods: int) -> pd.Series:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark)


def _safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    frame = pd.concat([x, y], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 5 or frame.iloc[:, 0].nunique() < 2 or frame.iloc[:, 1].nunique() < 2:
        return float("nan"), float("nan")
    rho, p = spearmanr(frame.iloc[:, 0], frame.iloc[:, 1])
    return float(rho), float(p)


def _annual_spearman(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year, group in df.groupby(df["time"].dt.year, sort=True):
        rho, p = _safe_spearman(group[feature_col], group[target_col])
        if np.isfinite(rho):
            rows.append({"year": int(year), "rho": float(rho), "p_value": float(p), "n": int(len(group))})
    return pd.DataFrame(rows)


def _summarize_series(series: pd.DataFrame) -> dict[str, object]:
    if series.empty:
        return {
            "mean_rho": float("nan"),
            "daily_hit_rate": float("nan"),
            "positive_years": 0,
            "years_present": 0,
            "annual_rows": 0,
        }
    yearly = series.groupby("year")["rho"].mean()
    return {
        "mean_rho": float(series["rho"].mean()),
        "daily_hit_rate": float((series["rho"] > 0.0).mean()),
        "positive_years": int((yearly > 0.0).sum()),
        "years_present": int(yearly.shape[0]),
        "annual_rows": int(len(series)),
    }


def _load_sector_sets() -> dict[str, set[str]]:
    if not SECTOR_CLASS_PATH.exists():
        return {"banking": set(), "real_estate": set()}
    sector = pd.read_parquet(SECTOR_CLASS_PATH)
    s2 = sector["icb_name2"].astype(str).str.lower()
    s3 = sector["icb_name3"].astype(str).str.lower()

    def _symbols(mask: pd.Series) -> set[str]:
        return set(sector.loc[mask, "symbol"].astype(str).str.upper())

    return {
        "banking": _symbols(s2.str.contains("ngân hàng", na=False) | s2.str.contains("ngan hang", na=False)),
        "real_estate": _symbols(
            s2.str.contains("bất động sản", na=False)
            | s2.str.contains("bat dong san", na=False)
            | s3.str.contains("bất động sản", na=False)
            | s3.str.contains("bat dong san", na=False)
        ),
    }


def _build_sector_close(close_wide: pd.DataFrame, tickers: set[str]) -> pd.Series:
    cols = [c for c in close_wide.columns if str(c).upper() in tickers]
    if not cols:
        return pd.Series(index=close_wide.index, dtype="float64")
    return close_wide[cols].mean(axis=1, skipna=True)


def _build_sector_state_panel() -> pd.DataFrame:
    if not SECTOR_ROTATION_PATH.exists():
        return pd.DataFrame()
    rot = pd.read_parquet(SECTOR_ROTATION_PATH)
    rot["time"] = pd.to_datetime(rot["time"], errors="coerce")
    rot["ticker"] = rot["ticker"].astype(str).str.upper()

    if not EVENT_SURFACE_PATH.exists():
        event = pd.DataFrame()
    else:
        event = pd.read_parquet(EVENT_SURFACE_PATH)
        event["time"] = pd.to_datetime(event["time"], errors="coerce")
        event["ticker"] = event["ticker"].astype(str).str.upper()

    sectors = _load_sector_sets()
    rows: list[pd.DataFrame] = []
    for name, tickers in sectors.items():
        if not tickers:
            continue
        rot_sub = rot[rot["ticker"].isin(tickers)].copy()
        rot_group = (
            rot_sub.groupby("time", as_index=False)
            .agg(
                **{
                    f"{name}_rotation_signal": ("xs_sector_rotation_signal", "mean"),
                    f"{name}_breadth_5d": ("xs_sector_breadth_5d", "mean"),
                }
            )
        )
        if not event.empty:
            event_sub = event[event["ticker"].isin(tickers)].copy()
            event_group = event_sub.groupby("time", as_index=False).agg(
                **{
                    f"{name}_event_density_20d": ("event_density_20d", "mean"),
                    f"{name}_has_any_event_history": ("has_any_event_history", "mean"),
                }
            )
            rot_group = rot_group.merge(event_group, on="time", how="left")
        rows.append(rot_group)

    if not rows:
        return pd.DataFrame()

    out = rows[0]
    for frame in rows[1:]:
        out = out.merge(frame, on="time", how="outer")

    for c in out.columns:
        if c == "time":
            continue
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.sort_values("time").reset_index(drop=True)


def _build_target_panel() -> pd.DataFrame:
    market = pd.read_parquet(FEATURE_PATH)
    market["time"] = pd.to_datetime(market["time"], errors="coerce")
    market = market[market["time"].dt.year.between(TARGET_YEAR_MIN, TARGET_YEAR_MAX)].copy()
    theme_mask = (market[CONTROL_THEMES].fillna(0.0) != 0.0).any(axis=1)
    market = market.loc[theme_mask].copy()

    close_wide = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close_years = pd.Index(close_wide.index.year)
    close_wide = close_wide.loc[(close_years >= TARGET_YEAR_MIN) & (close_years <= TARGET_YEAR_MAX)].copy()
    benchmark = load_vni_close().reindex(close_wide.index)

    sectors = _load_sector_sets()
    bank_close = _build_sector_close(close_wide, sectors["banking"])
    re_close = _build_sector_close(close_wide, sectors["real_estate"])
    regulated_close = pd.concat([bank_close, re_close], axis=1).mean(axis=1, skipna=True)

    target_baskets = {
        "banking": bank_close,
        "real_estate": re_close,
        "regulated_combo": regulated_close,
    }

    sector_state = _build_sector_state_panel()
    sector_state = sector_state[sector_state["time"].dt.year.between(TARGET_YEAR_MIN, TARGET_YEAR_MAX)].copy()

    panels: list[pd.DataFrame] = []
    for basket_label, basket_close in target_baskets.items():
        target = _future_excess_return(basket_close, benchmark.reindex(close_wide.index), periods=TARGET_HORIZON)
        target_df = pd.DataFrame({"time": target.index, "target": target.values})
        target_df["time"] = pd.to_datetime(target_df["time"], errors="coerce")
        target_df = target_df.dropna(subset=["target"])

        if basket_label == "banking":
            state_prefix = "banking"
        elif basket_label == "real_estate":
            state_prefix = "real_estate"
        else:
            state_prefix = "banking"

        state_cols = ["time", f"{state_prefix}_rotation_signal", f"{state_prefix}_breadth_5d"]
        event_col = f"{state_prefix}_event_density_20d"
        if event_col in sector_state.columns:
            state_cols.append(event_col)
        state_df = sector_state[state_cols].copy() if not sector_state.empty else pd.DataFrame(columns=state_cols)

        merged = market.merge(target_df, on="time", how="inner")
        if not state_df.empty:
            merged = merged.merge(state_df, on="time", how="left")
        merged["basket_label"] = basket_label
        panels.append(merged)

    if not panels:
        return pd.DataFrame()
    return pd.concat(panels, ignore_index=True)


@dataclass
class ThemeResult:
    basket_label: str
    feature_name: str
    mean_rho: float
    daily_hit_rate: float
    positive_years: int
    years_present: int
    annual_rows: int
    row_count: int
    nonzero_rows: int
    feature_mean: float
    target_mean: float
    gate_high_rho: float
    gate_low_rho: float
    event_high_rho: float
    event_low_rho: float


def _quantile_gate_rho(df: pd.DataFrame, feature_col: str, target_col: str, gate_col: str) -> tuple[float, float]:
    frame = df[["time", feature_col, target_col, gate_col]].copy()
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty or frame[gate_col].nunique() < 4:
        return float("nan"), float("nan")
    try:
        q = pd.qcut(frame[gate_col], 5, labels=False, duplicates="drop")
    except ValueError:
        return float("nan"), float("nan")
    high = frame[q == q.max()]
    low = frame[q == q.min()]
    high_rho, _ = _safe_spearman(high[feature_col], high[target_col])
    low_rho, _ = _safe_spearman(low[feature_col], low[target_col])
    return high_rho, low_rho


def _evaluate_feature(panel: pd.DataFrame, basket_label: str, feature_col: str) -> ThemeResult:
    target_col = "target"
    sub = panel[panel["basket_label"] == basket_label][["time", feature_col, target_col]].copy()
    annual = _annual_spearman(sub, feature_col, target_col)
    stats = _summarize_series(annual)
    sub["feature"] = pd.to_numeric(sub[feature_col], errors="coerce")
    sub["target"] = pd.to_numeric(sub[target_col], errors="coerce")
    nonzero_rows = int((sub["feature"].fillna(0.0) != 0.0).sum())
    feature_mean = float(sub["feature"].mean()) if len(sub) else float("nan")
    target_mean = float(sub["target"].mean()) if len(sub) else float("nan")

    gate_col = f"{basket_label if basket_label != 'regulated_combo' else 'banking'}_rotation_signal"
    event_col = f"{basket_label if basket_label != 'regulated_combo' else 'banking'}_event_density_20d"
    if basket_label == "regulated_combo":
        # Use the average banking + real estate state as the gate for the
        # combined regulation basket.
        gate_df = panel[panel["basket_label"] == basket_label][["time", feature_col, target_col]].copy()
        gate_state = panel[panel["basket_label"] == "banking"][["time", "banking_rotation_signal", "banking_event_density_20d"]].rename(
            columns={
                "banking_rotation_signal": "banking_gate",
                "banking_event_density_20d": "banking_event",
            }
        )
        re_state = panel[panel["basket_label"] == "real_estate"][["time", "real_estate_rotation_signal", "real_estate_event_density_20d"]].rename(
            columns={
                "real_estate_rotation_signal": "re_gate",
                "real_estate_event_density_20d": "re_event",
            }
        )
        gate_state = gate_state.merge(re_state, on="time", how="inner")
        gate_state["gate"] = gate_state[["banking_gate", "re_gate"]].mean(axis=1)
        gate_state["event"] = gate_state[["banking_event", "re_event"]].mean(axis=1)
        gate_df = gate_df.merge(gate_state[["time", "gate", "event"]], on="time", how="left")
        high_rho, low_rho = _quantile_gate_rho(gate_df.rename(columns={"gate": "gate_col"}), feature_col, target_col, "gate_col")
        event_high_rho, event_low_rho = _quantile_gate_rho(gate_df.rename(columns={"event": "event_col"}), feature_col, target_col, "event_col")
    else:
        gate_df = panel[panel["basket_label"] == basket_label][["time", feature_col, target_col, gate_col]].copy()
        if event_col in panel.columns:
            gate_df[event_col] = panel.loc[panel["basket_label"] == basket_label, event_col].values
        high_rho, low_rho = _quantile_gate_rho(gate_df, feature_col, target_col, gate_col)
        if event_col in gate_df.columns:
            event_high_rho, event_low_rho = _quantile_gate_rho(gate_df, feature_col, target_col, event_col)
        else:
            event_high_rho, event_low_rho = float("nan"), float("nan")

    return ThemeResult(
        basket_label=basket_label,
        feature_name=feature_col,
        mean_rho=float(stats["mean_rho"]),
        daily_hit_rate=float(stats["daily_hit_rate"]),
        positive_years=int(stats["positive_years"]),
        years_present=int(stats["years_present"]),
        annual_rows=int(stats["annual_rows"]),
        row_count=int(len(sub)),
        nonzero_rows=nonzero_rows,
        feature_mean=feature_mean,
        target_mean=target_mean,
        gate_high_rho=float(high_rho),
        gate_low_rho=float(low_rho),
        event_high_rho=float(event_high_rho),
        event_low_rho=float(event_low_rho),
    )


def main() -> None:
    print("Building macro theme router audit panel...")
    panel = _build_target_panel()
    if panel.empty:
        raise ValueError("No matched macro-theme rows for the router audit window")

    features = CONTROL_THEMES
    results: list[ThemeResult] = []
    for basket_label in ["banking", "real_estate", "regulated_combo"]:
        for feature in features:
            results.append(_evaluate_feature(panel, basket_label, feature))

    result_df = pd.DataFrame([r.__dict__ for r in results])
    result_df = result_df.sort_values(
        by=["mean_rho", "gate_high_rho", "daily_hit_rate"],
        ascending=[False, False, False],
        ignore_index=True,
    )

    best_rows = {
        basket: group.sort_values(by=["mean_rho", "gate_high_rho"], ascending=[False, False]).iloc[0].to_dict()
        for basket, group in result_df.groupby("basket_label", sort=False)
    }

    bucket_table = []
    for basket in ["banking", "real_estate", "regulated_combo"]:
        row = best_rows[basket]
        bucket_table.append(
            {
                "basket_label": basket,
                "best_feature": row["feature_name"],
                "best_mean_rho": float(row["mean_rho"]),
                "best_daily_hit_rate": float(row["daily_hit_rate"]),
                "best_positive_years": int(row["positive_years"]),
                "best_years_present": int(row["years_present"]),
                "best_gate_high_rho": float(row["gate_high_rho"]),
                "best_gate_low_rho": float(row["gate_low_rho"]),
                "best_event_high_rho": float(row["event_high_rho"]),
                "best_event_low_rho": float(row["event_low_rho"]),
            }
        )

    bank_best = best_rows["banking"]
    re_best = best_rows["real_estate"]
    reg_best = best_rows["regulated_combo"]

    pass_condition = bool(
        bank_best["feature_name"] == "frac_banking_theme"
        and re_best["feature_name"] == "frac_real_estate_theme"
        and bank_best["mean_rho"] > 0.02
        and re_best["mean_rho"] > 0.02
        and bank_best["mean_rho"] > result_df[result_df["basket_label"] == "banking"]["mean_rho"].min()
        and re_best["mean_rho"] > result_df[result_df["basket_label"] == "real_estate"]["mean_rho"].min()
        and bank_best["gate_high_rho"] >= bank_best["gate_low_rho"]
        and re_best["gate_high_rho"] >= re_best["gate_low_rho"]
    )
    mixed_condition = bool(
        bank_best["feature_name"] == "frac_banking_theme"
        or re_best["feature_name"] == "frac_real_estate_theme"
        or reg_best["feature_name"] == "frac_regulation_theme"
    )
    verdict = "PASS" if pass_condition else "MIXED" if mixed_condition else "FAIL"

    print("\nH292 MACRO THEME ROUTER RESULTS")
    print("=" * 140)
    print("Feature / basket table:")
    print(
        result_df[
            [
                "basket_label",
                "feature_name",
                "mean_rho",
                "daily_hit_rate",
                "positive_years",
                "years_present",
                "gate_high_rho",
                "gate_low_rho",
                "event_high_rho",
                "event_low_rho",
            ]
        ].to_string(index=False)
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h292_macro_theme_router_audit_details.json"
    summary = {
        "verdict": verdict,
        "best_basket": str(result_df.iloc[0]["basket_label"]),
        "best_feature": str(result_df.iloc[0]["feature_name"]),
        "best_mean_rho": float(result_df.iloc[0]["mean_rho"]),
        "best_daily_hit_rate": float(result_df.iloc[0]["daily_hit_rate"]),
        "best_positive_years": int(result_df.iloc[0]["positive_years"]),
        "best_years_present": int(result_df.iloc[0]["years_present"]),
        "feature_table": result_df.to_dict("records"),
        "bucket_table": bucket_table,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "window_years": sorted(int(y) for y in panel["time"].dt.year.unique().tolist()),
        "active_theme_days": int(panel["time"].nunique()),
        "active_theme_rows": int(len(panel)),
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h292_macro_theme_router_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H292"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
