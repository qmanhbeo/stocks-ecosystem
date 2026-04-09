"""
H296: liquidity router audit.

Question:
    If big names matter mainly as execution sleeves, can a frozen H54
    cross-sectional ranker improve executable economics by routing:
      - large-cap / high-liquidity names to daily H=1
      - mid-cap / mid-liquidity names to weekly H=5

Smallest honest mode:
    Keep the saved H54 ranker fixed, build a predeclared rolling liquidity
    map from historical OHLCV only, and compare the router against two
    one-size-fits-all baselines on the same eligible universe.

Predeclared liquidity buckets:
    - large: top 50 by trailing 20d avg VND volume (shifted 1 day)
    - mid:   ranks 51-200 by the same metric
    - thin:  ranks > 200

Cost assumptions:
    - large daily H=1: 0.20% RT
    - mid weekly H=5: 0.50% RT
    - thin names are not traded by the router

Decision rule:
    PASSED:
      - router avg annual net > both one-size-fits-all baselines
      - router avg annual net > 0
      - router executed-slot share >= 70%
    MIXED:
      - router beats both baselines, but stays negative or coverage is too low
    FAILED:
      - router does not beat both baselines
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary


DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
STOCK_DIR = data_path("stock")
VNI_FILE = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
END_YEAR = 2025
TOP_N = 5
MIN_PROBA = 0.55
LARGE_TOP_K = 50
MID_TOP_K = 200
ROLLING_LIQ_WINDOW = 20
ROLLING_LIQ_MIN_DAYS = 5
LARGE_COST_RT = 0.002
MID_COST_RT = 0.005

PASS_MIN_EXECUTED_SLOT_SHARE = 0.70


def load_vni() -> pd.DataFrame:
    frame = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    frame["time"] = pd.to_datetime(frame["time"])
    return frame.sort_values("time").reset_index(drop=True)


def load_price_and_liquidity_panel(tickers: list[str], vni: pd.DataFrame) -> pd.DataFrame:
    vni_open = vni["open"].values
    vni_idx = {ts: i for i, ts in enumerate(vni["time"].values)}
    ticker_set = set(tickers)
    records: list[pd.DataFrame] = []

    for stock_file in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = stock_file.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker not in ticker_set or ticker == "VNINDEX":
            continue
        try:
            frame = pd.read_parquet(stock_file, columns=["time", "open", "close", "volume"])
        except Exception:
            continue

        frame["time"] = pd.to_datetime(frame["time"])
        frame = frame.sort_values("time").reset_index(drop=True)
        open_arr = frame["open"].to_numpy(dtype=float)
        close_arr = frame["close"].to_numpy(dtype=float)
        volume_arr = frame["volume"].to_numpy(dtype=float)
        times_arr = frame["time"].to_numpy()
        avg_vnd_vol = (
            pd.Series(close_arr * volume_arr)
            .rolling(ROLLING_LIQ_WINDOW, min_periods=ROLLING_LIQ_MIN_DAYS)
            .mean()
            .shift(1)
            .to_numpy(dtype=float)
        )

        fwd_h1 = np.full(len(frame), np.nan)
        fwd_h5 = np.full(len(frame), np.nan)
        for idx, ts in enumerate(times_arr):
            vni_pos = vni_idx.get(ts)
            if vni_pos is None:
                continue
            for hold, out in ((1, fwd_h1), (5, fwd_h5)):
                stock_exit = idx + 1 + hold
                vni_exit = vni_pos + 1 + hold
                if stock_exit >= len(frame) or vni_exit >= len(vni_open):
                    continue
                stock_entry_open = open_arr[idx + 1]
                stock_exit_open = open_arr[stock_exit]
                vni_entry_open = vni_open[vni_pos + 1]
                vni_exit_open = vni_open[vni_exit]
                if stock_entry_open <= 0 or vni_entry_open <= 0:
                    continue
                out[idx] = (
                    (stock_exit_open / stock_entry_open - 1.0)
                    - (vni_exit_open / vni_entry_open - 1.0)
                )

        records.append(
            pd.DataFrame(
                {
                    "time": frame["time"],
                    "ticker": ticker,
                    "avg_vnd_vol": avg_vnd_vol,
                    "fwd_h1": fwd_h1,
                    "fwd_h5": fwd_h5,
                }
            )
        )

    if not records:
        return pd.DataFrame(columns=["time", "ticker", "avg_vnd_vol", "fwd_h1", "fwd_h5"])
    return pd.concat(records, ignore_index=True)


def build_panel(probas_path: Path) -> pd.DataFrame:
    probas = pd.read_parquet(probas_path)
    probas["time"] = pd.to_datetime(probas["time"])
    probas = probas.loc[probas["time"].dt.year.between(START_YEAR, END_YEAR)].copy()

    vni = load_vni()
    price_panel = load_price_and_liquidity_panel(sorted(probas["ticker"].unique()), vni)
    merged = probas.merge(price_panel, on=["time", "ticker"], how="left")
    merged["liq_rank"] = merged.groupby("time")["avg_vnd_vol"].rank(
        ascending=False, method="first"
    )
    merged["bucket"] = np.where(
        merged["liq_rank"] <= LARGE_TOP_K,
        "large",
        np.where(merged["liq_rank"] <= MID_TOP_K, "mid", "thin"),
    )
    return merged


def _signal_calendar(panel: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(pd.Timestamp(ts) for ts in panel["time"].dropna().unique())


def _strategy_container() -> dict[str, float | int]:
    return {
        "gross": 0.0,
        "net": 0.0,
        "signal_dates": 0,
        "requested_slots": 0,
        "eligible_slots": 0,
        "executed_slots": 0,
        "raw_large_slots": 0,
        "raw_mid_slots": 0,
        "raw_thin_slots": 0,
        "raw_top5_count": 0,
    }


def _update_raw_bucket_counts(bucket: str, container: dict[str, float | int]) -> None:
    if bucket == "large":
        container["raw_large_slots"] += 1
    elif bucket == "mid":
        container["raw_mid_slots"] += 1
    else:
        container["raw_thin_slots"] += 1


def simulate_strategies(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    yearly: dict[str, dict[int, dict[str, float | int]]] = {
        "eligible_all_h1": defaultdict(_strategy_container),
        "eligible_all_h5_weekly": defaultdict(_strategy_container),
        "liquidity_router": defaultdict(_strategy_container),
    }

    calendar = _signal_calendar(panel)
    for date_idx, signal_date in enumerate(calendar):
        day = panel.loc[panel["time"] == signal_date].copy()
        day = day.sort_values("xs_proba", ascending=False)
        day = day.loc[day["xs_proba"] >= MIN_PROBA].copy()
        if len(day) < TOP_N:
            continue

        raw_top5 = day.head(TOP_N).copy()
        eligible_top5 = day.loc[day["bucket"] != "thin"].head(TOP_N).copy()
        year = int(signal_date.year)
        weekly_rebalance = date_idx % 5 == 0

        for strategy_name, container in yearly.items():
            bucket = container[year]
            bucket["signal_dates"] += 1
            bucket["requested_slots"] += TOP_N
            bucket["raw_top5_count"] += int(len(raw_top5))
            for bucket_name in raw_top5["bucket"].tolist():
                _update_raw_bucket_counts(str(bucket_name), bucket)

        # Daily H=1 on the eligible large+mid sleeve.
        h1_bucket = yearly["eligible_all_h1"][year]
        h1_bucket["eligible_slots"] += int(len(eligible_top5))
        for _, row in eligible_top5.iterrows():
            ret = pd.to_numeric(row.get("fwd_h1"), errors="coerce")
            if pd.isna(ret):
                continue
            cost = LARGE_COST_RT if row["bucket"] == "large" else MID_COST_RT
            h1_bucket["gross"] += float(ret) / TOP_N
            h1_bucket["net"] += float(ret - cost) / TOP_N
            h1_bucket["executed_slots"] += 1

        # Weekly H=5 on the same eligible sleeve.
        h5_bucket = yearly["eligible_all_h5_weekly"][year]
        if weekly_rebalance:
            h5_bucket["eligible_slots"] += int(len(eligible_top5))
            for _, row in eligible_top5.iterrows():
                ret = pd.to_numeric(row.get("fwd_h5"), errors="coerce")
                if pd.isna(ret):
                    continue
                cost = LARGE_COST_RT if row["bucket"] == "large" else MID_COST_RT
                h5_bucket["gross"] += float(ret) / TOP_N
                h5_bucket["net"] += float(ret - cost) / TOP_N
                h5_bucket["executed_slots"] += 1

        # Routed sleeve: large daily H=1, mid weekly H=5.
        router_bucket = yearly["liquidity_router"][year]
        router_bucket["eligible_slots"] += int(len(eligible_top5))
        for _, row in eligible_top5.iterrows():
            ret = None
            cost = None
            if row["bucket"] == "large":
                ret = pd.to_numeric(row.get("fwd_h1"), errors="coerce")
                cost = LARGE_COST_RT
            elif row["bucket"] == "mid" and weekly_rebalance:
                ret = pd.to_numeric(row.get("fwd_h5"), errors="coerce")
                cost = MID_COST_RT
            if ret is None or pd.isna(ret) or cost is None:
                continue
            router_bucket["gross"] += float(ret) / TOP_N
            router_bucket["net"] += float(ret - cost) / TOP_N
            router_bucket["executed_slots"] += 1

    rows: list[dict[str, object]] = []
    strategy_summary: dict[str, object] = {}
    for strategy_name, by_year in yearly.items():
        annual_nets = []
        annual_gross = []
        executed_slot_share = []
        eligible_slot_share = []
        raw_large_share = []
        raw_mid_share = []
        raw_thin_share = []
        signal_dates = []

        for year in sorted(by_year):
            values = by_year[year]
            raw_total = max(int(values["raw_top5_count"]), 1)
            requested = max(int(values["requested_slots"]), 1)
            annual_nets.append(float(values["net"]))
            annual_gross.append(float(values["gross"]))
            executed_slot_share.append(float(values["executed_slots"]) / requested)
            eligible_slot_share.append(float(values["eligible_slots"]) / requested)
            raw_large_share.append(float(values["raw_large_slots"]) / raw_total)
            raw_mid_share.append(float(values["raw_mid_slots"]) / raw_total)
            raw_thin_share.append(float(values["raw_thin_slots"]) / raw_total)
            signal_dates.append(int(values["signal_dates"]))
            rows.append(
                {
                    "strategy": strategy_name,
                    "year": year,
                    "annual_gross": float(values["gross"]),
                    "annual_net": float(values["net"]),
                    "signal_dates": int(values["signal_dates"]),
                    "eligible_slot_share": float(values["eligible_slots"]) / requested,
                    "executed_slot_share": float(values["executed_slots"]) / requested,
                    "raw_large_slot_share": float(values["raw_large_slots"]) / raw_total,
                    "raw_mid_slot_share": float(values["raw_mid_slots"]) / raw_total,
                    "raw_thin_slot_share": float(values["raw_thin_slots"]) / raw_total,
                }
            )

        strategy_summary[strategy_name] = {
            "avg_annual_gross": float(np.mean(annual_gross)) if annual_gross else None,
            "avg_annual_net": float(np.mean(annual_nets)) if annual_nets else None,
            "positive_years": int(sum(value > 0 for value in annual_nets)),
            "years": int(len(annual_nets)),
            "avg_signal_dates": float(np.mean(signal_dates)) if signal_dates else None,
            "avg_eligible_slot_share": float(np.mean(eligible_slot_share)) if eligible_slot_share else None,
            "avg_executed_slot_share": float(np.mean(executed_slot_share)) if executed_slot_share else None,
            "avg_raw_large_slot_share": float(np.mean(raw_large_share)) if raw_large_share else None,
            "avg_raw_mid_slot_share": float(np.mean(raw_mid_share)) if raw_mid_share else None,
            "avg_raw_thin_slot_share": float(np.mean(raw_thin_share)) if raw_thin_share else None,
        }

    return pd.DataFrame(rows), strategy_summary


def main() -> None:
    probas_path = Path(DEFAULT_PROBAS)
    panel = build_panel(probas_path)
    yearly_results, strategy_summary = simulate_strategies(panel)

    router = strategy_summary["liquidity_router"]
    h1 = strategy_summary["eligible_all_h1"]
    h5 = strategy_summary["eligible_all_h5_weekly"]

    router_beats_baselines = bool(
        (router.get("avg_annual_net") or -np.inf) > (h1.get("avg_annual_net") or -np.inf)
        and (router.get("avg_annual_net") or -np.inf) > (h5.get("avg_annual_net") or -np.inf)
    )
    router_positive = bool((router.get("avg_annual_net") or 0.0) > 0.0)
    router_coverage_ok = bool((router.get("avg_executed_slot_share") or 0.0) >= PASS_MIN_EXECUTED_SLOT_SHARE)

    if router_beats_baselines and router_positive and router_coverage_ok:
        verdict = "PASSED"
        branch_decision = (
            "Promote the liquidity router as a real offline execution follow-through and test it "
            "against the frozen H54 benchmark in a more explicit path simulation."
        )
    elif router_beats_baselines:
        verdict = "MIXED"
        branch_decision = (
            "The router is directionally better than the one-size-fits-all eligible baselines, "
            "but it still fails as a deployable branch because net stays negative or slot "
            "coverage collapses. Keep only as weak execution-allocation evidence."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Kill the liquidity-router branch on the current contract. The simple sleeve split "
            "does not improve on the eligible one-size-fits-all baselines."
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{ts}_h296_liquidity_router_audit_yearly.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h296_liquidity_router_audit_details.json"
    yearly_results.to_parquet(results_path, index=False)

    summary_payload = {
        "verdict": verdict,
        "hypothesis": (
            "A frozen H54 ranker may still support a useful execution sleeve if large names run "
            "daily H=1 and mid names run weekly H=5 under realistic bucket-specific costs."
        ),
        "branch_contract": {
            "ranker": str(probas_path),
            "large_bucket": f"top {LARGE_TOP_K} rolling liquidity rank",
            "mid_bucket": f"ranks {LARGE_TOP_K + 1}-{MID_TOP_K}",
            "costs": {
                "large_daily_h1_rt": LARGE_COST_RT,
                "mid_weekly_h5_rt": MID_COST_RT,
            },
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
        },
        "strategy_summary": strategy_summary,
        "comparisons": {
            "router_minus_all_h1_ann_net": (router.get("avg_annual_net") or 0.0) - (h1.get("avg_annual_net") or 0.0),
            "router_minus_all_h5_ann_net": (router.get("avg_annual_net") or 0.0) - (h5.get("avg_annual_net") or 0.0),
            "raw_top5_thin_share": h1.get("avg_raw_thin_slot_share"),
        },
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_liquidity_router_audit",
        name="h296_liquidity_router_audit",
        summary=summary_payload,
        artifacts={
            "yearly_results": str(results_path),
            "details": str(details_path),
        },
        metadata={
            "session": 127,
            "start_year": START_YEAR,
            "end_year": END_YEAR,
        },
    )

    print("H296 liquidity router audit")
    print(
        pd.DataFrame(
            [
                {"strategy": key, **value}
                for key, value in strategy_summary.items()
            ]
        ).to_string(index=False)
    )
    print(f"\nVerdict: {verdict}")
    print(branch_decision)


if __name__ == "__main__":
    main()
