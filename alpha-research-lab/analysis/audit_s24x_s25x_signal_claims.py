from __future__ import annotations

import argparse
import glob
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


MODE = "audit_s24x_s25x_signal_claims"
NAME = "s24x_s25x_signal_claim_audit"

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
ORDER_RAW_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
INSIDER_GLOB = str(data_path("insider_cache/*.parquet"))
DIVIDEND_GLOB = str(data_path("dividend_cache/*.parquet"))


@dataclass(frozen=True)
class ClaimSpec:
    name: str
    mask_col: str
    signal_col: str = "order_volume_ratio_rank"
    claim_group: str = "misc"


CLAIMS = [
    ClaimSpec("c16_all", "all_rows", claim_group="baseline"),
    ClaimSpec("vol_high_buy_count_gt_80", "vol_high_buy_count_gt_80", claim_group="volume"),
    ClaimSpec("vol_low_buy_count_lt_20", "vol_low_buy_count_lt_20", claim_group="volume"),
    ClaimSpec("january_doy_le10", "january_doy_le10", claim_group="calendar"),
    ClaimSpec("january_first_10_trading_days", "january_first_10_trading_days", claim_group="calendar"),
    ClaimSpec("monday", "monday", claim_group="calendar"),
    ClaimSpec("february_mid", "february_mid", claim_group="calendar"),
    ClaimSpec("march_late", "march_late", claim_group="calendar"),
    ClaimSpec("may", "may", claim_group="calendar"),
    ClaimSpec("september_late", "september_late", claim_group="calendar"),
    ClaimSpec("october", "october", claim_group="calendar"),
    ClaimSpec("monday_january_doy_le10", "monday_january_doy_le10", claim_group="calendar"),
    ClaimSpec("leaky_target_market_down", "leaky_target_market_down", claim_group="leak_check"),
    ClaimSpec("leaky_target_market_down_2d", "leaky_target_market_down_2d", claim_group="leak_check"),
    ClaimSpec("observed_vni_down", "observed_vni_down", claim_group="market_regime"),
    ClaimSpec("observed_vni_down_2d", "observed_vni_down_2d", claim_group="market_regime"),
    ClaimSpec("observed_vni_bottom_quintile", "observed_vni_bottom_quintile", claim_group="market_regime"),
    ClaimSpec("observed_stock_down", "observed_stock_down", claim_group="stock_regime"),
    ClaimSpec("observed_stock_down_2d", "observed_stock_down_2d", claim_group="stock_regime"),
    ClaimSpec("insider_lead_original_calendar_plus_1", "insider_lead_original_calendar_plus_1", claim_group="insider"),
    ClaimSpec("insider_lead_next_trading_day", "insider_lead_next_trading_day", claim_group="insider"),
    ClaimSpec("old_record_date_exact_any_event", "old_record_date_exact_any_event", claim_group="dividend"),
    ClaimSpec("dividend_record_next_30d", "dividend_record_next_30d", claim_group="dividend"),
    ClaimSpec("dividend_exright_next_30d", "dividend_exright_next_30d", claim_group="dividend"),
    ClaimSpec("rank_accel_5d", "all_rows", "rank_accel_5d", claim_group="rank_accel"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit S24x-S25x strong signal claims against the canonical 1d "
            "barrier target, separating observable states from target-derived "
            "leaky states."
        )
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-year-rows", type=int, default=50)
    return parser.parse_args()


def _ticker(value: object) -> str:
    return str(value).strip().upper()


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 2:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho = float(np.asarray(rho).flat[0])
    if not np.isfinite(rho):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho, "p_value": float(np.asarray(p_value).flat[0])}


def _summarize_claim(frame: pd.DataFrame, spec: ClaimSpec, min_year_rows: int) -> dict[str, object]:
    scoped = frame.loc[frame[spec.mask_col].fillna(False).astype(bool)].copy()
    all_stat = _safe_ic(scoped, spec.signal_col, "actual", min_year_rows)
    rows = []
    for year, group in scoped.groupby("year", sort=True):
        stat = _safe_ic(group, spec.signal_col, "actual", min_year_rows)
        rows.append({"year": int(year), **stat})
    valid_ics = [row["ic"] for row in rows if row["ic"] is not None]
    date_count = int(scoped["time"].nunique()) if not scoped.empty else 0
    return {
        "name": spec.name,
        "claim_group": spec.claim_group,
        "signal_col": spec.signal_col,
        "rows": int(all_stat["rows"]),
        "dates": date_count,
        "overall_ic": all_stat["ic"],
        "overall_p_value": all_stat["p_value"],
        "avg_year_ic": float(np.mean(valid_ics)) if valid_ics else None,
        "pos_years": int(sum(1 for value in valid_ics if value > 0)),
        "years": int(len(valid_ics)),
        "yearly": rows,
    }


def _load_base_panel(start_year: int, end_year: int) -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].map(_ticker)
    s1 = s1.loc[s1["time"].dt.year.between(start_year, end_year)].copy()

    c16 = pd.read_parquet(C16_PATH, columns=["time", "ticker", "order_volume_ratio_rank"]).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].map(_ticker)

    raw = pd.read_parquet(ORDER_RAW_PATH, columns=["date", "ticker", "buy_order_count"]).copy()
    raw = raw.rename(columns={"date": "time"})
    raw["time"] = pd.to_datetime(raw["time"], errors="coerce").dt.normalize()
    raw["ticker"] = raw["ticker"].map(_ticker)
    raw["buy_order_count"] = pd.to_numeric(raw["buy_order_count"], errors="coerce")
    raw["buy_count_rank"] = raw.groupby("time")["buy_order_count"].rank(pct=True)

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(raw[["time", "ticker", "buy_count_rank"]], on=["time", "ticker"], how="left")
    panel["year"] = panel["time"].dt.year.astype(int)
    panel["actual"] = pd.to_numeric(panel["actual"], errors="coerce")
    panel["order_volume_ratio_rank"] = pd.to_numeric(panel["order_volume_ratio_rank"], errors="coerce")
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _add_returns(panel: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    returns = to_long(close.div(close.shift(1)).sub(1.0), "stock_return_1d")
    returns_2 = to_long(close.div(close.shift(2)).sub(1.0), "stock_return_2d")
    returns["time"] = pd.to_datetime(returns["time"], errors="coerce").dt.normalize()
    returns_2["time"] = pd.to_datetime(returns_2["time"], errors="coerce").dt.normalize()
    returns["ticker"] = returns["ticker"].map(_ticker)
    returns_2["ticker"] = returns_2["ticker"].map(_ticker)
    returns = returns.merge(returns_2, on=["time", "ticker"], how="inner", validate="one_to_one")
    returns = returns.loc[returns["time"].dt.year.between(start_year, end_year)].copy()

    market = pd.DataFrame(
        {
            "time": pd.to_datetime(vni_close.index, errors="coerce").normalize(),
            "vni_return_1d": vni_close.div(vni_close.shift(1)).sub(1.0).to_numpy(dtype=float),
        }
    )
    market["prev_vni_return_1d"] = market["vni_return_1d"].shift(1)
    market["vni_return_rank"] = market["vni_return_1d"].rank(pct=True)
    out = panel.merge(returns, on=["time", "ticker"], how="left", validate="one_to_one")
    out = out.merge(market, on="time", how="left", validate="many_to_one")
    return out


def _event_keys_from_dates(events: pd.DataFrame, date_col: str, trading_dates: np.ndarray, window_days: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    events = events.dropna(subset=["ticker", date_col]).copy()
    for ticker, event_date in events[["ticker", date_col]].itertuples(index=False):
        event_ts = pd.Timestamp(event_date).normalize()
        start_ts = event_ts - pd.Timedelta(days=window_days)
        start_idx = int(np.searchsorted(trading_dates, np.datetime64(start_ts), side="left"))
        end_idx = int(np.searchsorted(trading_dates, np.datetime64(event_ts), side="right"))
        for trading_day in trading_dates[start_idx:end_idx]:
            rows.append({"ticker": ticker, "time": pd.Timestamp(trading_day).normalize()})
    if not rows:
        return pd.DataFrame(columns=["ticker", "time"])
    return pd.DataFrame(rows).drop_duplicates()


def _add_insider(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for path in glob.glob(INSIDER_GLOB):
        try:
            frame = pd.read_parquet(path, columns=["ticker", "published_date", "RealBuyVolume", "RealSellVolume"])
        except Exception:
            continue
        frames.append(frame)
    if not frames:
        panel["insider_lead_original_calendar_plus_1"] = False
        panel["insider_lead_next_trading_day"] = False
        return panel

    insider = pd.concat(frames, ignore_index=True)
    insider["ticker"] = insider["ticker"].map(_ticker)
    insider["published_date"] = pd.to_datetime(insider["published_date"], errors="coerce").dt.normalize()
    insider["net_real_buy"] = (
        pd.to_numeric(insider["RealBuyVolume"], errors="coerce").fillna(0.0)
        - pd.to_numeric(insider["RealSellVolume"], errors="coerce").fillna(0.0)
    )
    insider = insider.loc[insider["net_real_buy"] > 0].dropna(subset=["published_date"]).copy()

    original = insider[["ticker", "published_date"]].copy()
    original["time"] = original["published_date"] + pd.Timedelta(days=1)
    original = original[["ticker", "time"]].drop_duplicates()
    original["insider_lead_original_calendar_plus_1"] = True

    trading_dates = np.array(sorted(panel["time"].dropna().unique()), dtype="datetime64[ns]")
    mapped_rows = []
    for ticker, published_date in insider[["ticker", "published_date"]].itertuples(index=False):
        idx = int(np.searchsorted(trading_dates, np.datetime64(published_date), side="right"))
        if idx < len(trading_dates):
            mapped_rows.append({"ticker": ticker, "time": pd.Timestamp(trading_dates[idx]).normalize()})
    mapped = pd.DataFrame(mapped_rows).drop_duplicates() if mapped_rows else pd.DataFrame(columns=["ticker", "time"])
    mapped["insider_lead_next_trading_day"] = True

    out = panel.merge(original, on=["time", "ticker"], how="left", validate="one_to_one")
    out = out.merge(mapped, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in ["insider_lead_original_calendar_plus_1", "insider_lead_next_trading_day"]:
        out[column] = out[column].fillna(False).astype(bool)
    return out


def _add_dividends(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for path in glob.glob(DIVIDEND_GLOB):
        try:
            frame = pd.read_parquet(
                path,
                columns=["ticker", "event_list_code", "record_date", "exright_date"],
            )
        except Exception:
            continue
        frames.append(frame)
    if not frames:
        for column in ["old_record_date_exact_any_event", "dividend_record_next_30d", "dividend_exright_next_30d"]:
            panel[column] = False
        return panel

    events = pd.concat(frames, ignore_index=True)
    events["ticker"] = events["ticker"].map(_ticker)
    for column in ["record_date", "exright_date"]:
        events[column] = pd.to_datetime(events[column], errors="coerce").dt.normalize()
        events.loc[events[column].dt.year < 1900, column] = pd.NaT

    old_exact = events.dropna(subset=["record_date"])[["ticker", "record_date"]].rename(columns={"record_date": "time"})
    old_exact = old_exact.drop_duplicates()
    old_exact["old_record_date_exact_any_event"] = True

    div = events.loc[events["event_list_code"].astype(str).str.upper().eq("DIV")].copy()
    trading_dates = np.array(sorted(panel["time"].dropna().unique()), dtype="datetime64[ns]")
    record_keys = _event_keys_from_dates(div, "record_date", trading_dates, 30)
    exright_keys = _event_keys_from_dates(div, "exright_date", trading_dates, 30)
    record_keys["dividend_record_next_30d"] = True
    exright_keys["dividend_exright_next_30d"] = True

    out = panel.merge(old_exact, on=["time", "ticker"], how="left", validate="one_to_one")
    out = out.merge(record_keys, on=["time", "ticker"], how="left", validate="one_to_one")
    out = out.merge(exright_keys, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in ["old_record_date_exact_any_event", "dividend_record_next_30d", "dividend_exright_next_30d"]:
        out[column] = out[column].fillna(False).astype(bool)
    return out


def _add_claim_masks(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["all_rows"] = True
    out["vol_high_buy_count_gt_80"] = out["buy_count_rank"] > 0.8
    out["vol_low_buy_count_lt_20"] = out["buy_count_rank"] < 0.2

    day_index = (
        out[["time"]]
        .drop_duplicates()
        .sort_values("time")
        .assign(year=lambda frame: frame["time"].dt.year)
    )
    day_index["trading_day_of_year"] = day_index.groupby("year").cumcount() + 1
    out = out.merge(day_index[["time", "trading_day_of_year"]], on="time", how="left", validate="many_to_one")

    out["january_doy_le10"] = out["time"].dt.dayofyear <= 10
    out["january_first_10_trading_days"] = out["trading_day_of_year"] <= 10
    out["monday"] = out["time"].dt.dayofweek == 0
    out["february_mid"] = (out["time"].dt.month == 2) & (out["time"].dt.day >= 15)
    out["march_late"] = (out["time"].dt.month == 3) & (out["time"].dt.isocalendar().week.astype(int) > 10)
    out["may"] = out["time"].dt.month == 5
    out["september_late"] = (out["time"].dt.month == 9) & (out["time"].dt.isocalendar().week.astype(int) > 36)
    out["october"] = out["time"].dt.month == 10
    out["monday_january_doy_le10"] = out["january_doy_le10"] & out["monday"]

    market_target = out.groupby("time", as_index=False)["actual"].mean().rename(columns={"actual": "target_hit_rate"})
    market_target["leaky_target_market_down"] = market_target["target_hit_rate"] <= 0.5
    market_target["leaky_target_market_down_2d"] = (
        market_target["leaky_target_market_down"] & market_target["leaky_target_market_down"].shift(1).fillna(False)
    )
    out = out.merge(
        market_target[["time", "leaky_target_market_down", "leaky_target_market_down_2d"]],
        on="time",
        how="left",
        validate="many_to_one",
    )

    out["observed_vni_down"] = out["vni_return_1d"] < 0.0
    out["observed_vni_down_2d"] = (out["vni_return_1d"] < 0.0) & (out["prev_vni_return_1d"] < 0.0)
    out["observed_vni_bottom_quintile"] = out["vni_return_rank"] <= 0.2
    out["observed_stock_down"] = out["stock_return_1d"] < 0.0
    out = out.sort_values(["ticker", "time"])
    out["prev_stock_down"] = out.groupby("ticker")["observed_stock_down"].shift(1).fillna(False)
    out["observed_stock_down_2d"] = out["observed_stock_down"] & out["prev_stock_down"]
    out["rank_accel_5d"] = out["order_volume_ratio_rank"] - out.groupby("ticker")["order_volume_ratio_rank"].shift(5)
    return out


def main() -> None:
    args = parse_args()
    if int(args.end_year) >= 2026:
        raise ValueError("Do not include 2026+ in this audit.")

    panel = _load_base_panel(int(args.start_year), int(args.end_year))
    panel = _add_returns(panel, int(args.start_year), int(args.end_year))
    panel = _add_insider(panel)
    panel = _add_dividends(panel)
    panel = _add_claim_masks(panel)

    metrics = [_summarize_claim(panel, spec, int(args.min_year_rows)) for spec in CLAIMS]
    baseline = next(item for item in metrics if item["name"] == "c16_all")
    baseline_ic = baseline["avg_year_ic"]
    for item in metrics:
        item["lift_vs_c16_avg_year_ic"] = (
            float(item["avg_year_ic"] - baseline_ic)
            if item["avg_year_ic"] is not None and baseline_ic is not None
            else None
        )

    out_dir = artifact_path("audits")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_path = out_dir / f"{ts}_s24x_s25x_signal_claim_audit_metrics.csv"
    yearly_path = out_dir / f"{ts}_s24x_s25x_signal_claim_audit_yearly.csv"

    metrics_frame = pd.DataFrame([{k: v for k, v in row.items() if k != "yearly"} for row in metrics])
    yearly_rows = []
    for row in metrics:
        for year_row in row["yearly"]:
            yearly_rows.append({"name": row["name"], **year_row})
    yearly_frame = pd.DataFrame(yearly_rows)
    metrics_frame.to_csv(metrics_path, index=False)
    yearly_frame.to_csv(yearly_path, index=False)

    status_notes = {
        "leak_error": [
            "leaky_target_market_down",
            "leaky_target_market_down_2d",
        ],
        "needs_downgrade_if_not_confirmed_observable": [
            "observed_vni_down",
            "observed_vni_down_2d",
            "observed_stock_down",
            "observed_stock_down_2d",
            "observed_vni_bottom_quintile",
        ],
        "sparse_or_context_only": [
            "monday_january_doy_le10",
            "old_record_date_exact_any_event",
            "dividend_record_next_30d",
            "dividend_exright_next_30d",
        ],
    }
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=NAME,
        summary={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "target": "actual binary 1d barrier label from xs_barrier_vol_1d_hose_full.parquet",
            "baseline_avg_year_ic": baseline_ic,
            "metrics": metrics,
            "status_notes": status_notes,
        },
        artifacts={"metrics_csv": metrics_path, "yearly_csv": yearly_path},
        metadata={
            "purpose": "Audit S24x-S25x strong signal claims for target leakage and observable-state robustness.",
            "no_2026_rows": True,
        },
    )

    display = metrics_frame[
        [
            "name",
            "claim_group",
            "rows",
            "dates",
            "avg_year_ic",
            "pos_years",
            "years",
            "lift_vs_c16_avg_year_ic",
        ]
    ].copy()
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 220)
    print(display.to_string(index=False))
    print(f"\nSaved metrics: {metrics_path}")
    print(f"Saved yearly: {yearly_path}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
