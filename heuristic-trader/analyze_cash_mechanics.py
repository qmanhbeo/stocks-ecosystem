"""
Cash Mechanics Autopsy - CORRECTED V2

Accounting cleanup to ensure:
- True cash % (actual cash / portfolio value)
- True invested % (holdings value / portfolio value)  
- Position count underfill % (1 - holdings/top_k)
- Corrected target_gap interpretation
- Improved dynamic sizing diagnostic with open_slots
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

import sys

sys.path.insert(0, str(ROOT))

import signals as s
from backtest import (
    load_liquid_lookup,
    load_price_cache,
    load_trad_lookup,
    get_price,
    can_buy_fast,
    is_liquid,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cash Mechanics Autopsy - V2")
    parser.add_argument(
        "--strategy",
        type=str,
        default="blend_70_30_top5",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--initial-capital", type=float, default=1_000_000_000.0)
    parser.add_argument("--use-filters", action="store_true", default=True)
    parser.add_argument("--allow-2026", action="store_true", default=False)
    return parser.parse_args()


def run_cash_mechanics_trace(
    signal_df: pd.DataFrame,
    price_cache: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    signal_col: str,
    top_k: int = 5,
    rebalance_days: int = 10,
    min_hold_days: int = 3,
    initial_capital: float = 1_000_000_000.0,
    use_filters: bool = True,
    record_focus_years: list[int] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    signal_df = signal_df.copy()
    signal_df = signal_df.sort_values("time").reset_index(drop=True)

    dates = signal_df["time"].unique()
    rebalance_indices = list(range(0, len(dates), rebalance_days))

    holdings: dict[str, tuple[int, int]] = {}
    cash = initial_capital
    buy_fee = 0.001

    rebalance_rows = []
    candidate_depth_rows = []

    for ri in rebalance_indices:
        if ri >= len(dates):
            break

        rebal_idx = ri
        prev_date = dates[rebal_idx]

        date = dates[rebal_idx + 1] if rebal_idx + 1 < len(dates) else prev_date
        year = pd.to_datetime(prev_date).year
        is_focus_year = record_focus_years is not None and year in record_focus_years

        portfolio_value_before = cash + sum(
            shares * get_price(price_cache, t, prev_date, "close") or 0
            for t, (shares, _) in holdings.items()
        )
        cash_before = cash
        holdings_value_before = portfolio_value_before - cash_before
        n_holdings_before = len(holdings)

        fixed_target_position_value = initial_capital / top_k
        dynamic_target_position_value = portfolio_value_before / top_k if portfolio_value_before > 0 else fixed_target_position_value

        for ticker in list(holdings.keys()):
            if ticker not in holdings:
                continue

            shares, buy_i = holdings[ticker]
            if rebal_idx - buy_i >= min_hold_days:
                open_price = get_price(price_cache, ticker, date, "open")
                if open_price and open_price > 0:
                    proceeds = shares * open_price * (1 - buy_fee)
                    cash += proceeds
                    del holdings[ticker]

        cash_after_sells = cash

        signal_day_df = signal_df[signal_df["time"] == prev_date]

        depth_counts = {}

        for depth_multiplier in [3, 5, 10, 20]:
            n_to_check = top_k * depth_multiplier
            top_n = signal_day_df.nlargest(n_to_check, signal_col)

            passed_count = 0
            for _, row in top_n.iterrows():
                ticker = row["ticker"]
                if ticker in holdings:
                    continue

                liq_fail = False
                trad_fail = False

                if use_filters:
                    if trad_lookup is not None:
                        if not can_buy_fast(ticker, prev_date, trad_lookup):
                            trad_fail = True
                        elif liquid_lookup is not None:
                            if not is_liquid(ticker, prev_date, liquid_lookup):
                                liq_fail = True
                    elif liquid_lookup is not None:
                        if not is_liquid(ticker, prev_date, liquid_lookup):
                            liq_fail = True

                if not liq_fail and not trad_fail:
                    passed_count += 1

            depth_counts[f"pass_count_depth_{n_to_check}"] = passed_count
            depth_counts[f"would_fill_topk_depth_{n_to_check}"] = 1 if passed_count >= top_k else 0

        all_candidates = signal_day_df.nlargest(1000, signal_col)
        all_passed = 0
        for _, row in all_candidates.iterrows():
            ticker = row["ticker"]
            if ticker in holdings:
                continue

            if use_filters:
                if trad_lookup is not None:
                    if not can_buy_fast(ticker, prev_date, trad_lookup):
                        continue
                if liquid_lookup is not None:
                    if not is_liquid(ticker, prev_date, liquid_lookup):
                        continue

            all_passed += 1

        depth_counts["pass_count_all"] = all_passed
        depth_counts["would_fill_topk_all"] = 1 if all_passed >= top_k else 0

        buys_successful = 0
        buys_failed_price_missing = 0
        buys_failed_insufficient_cash = 0

        for rank, (_, row) in enumerate(signal_day_df.nlargest(top_k * 3, signal_col).iterrows()):
            ticker = row["ticker"]

            if ticker in holdings:
                continue

            if use_filters:
                if trad_lookup is not None:
                    if not can_buy_fast(ticker, prev_date, trad_lookup):
                        continue

                if liquid_lookup is not None:
                    if not is_liquid(ticker, prev_date, liquid_lookup):
                        continue

            open_price = get_price(price_cache, ticker, date, "open")
            if not open_price or open_price <= 0:
                buys_failed_price_missing += 1
                continue

            shares = int(fixed_target_position_value / open_price)
            if shares <= 0:
                continue

            cost = shares * open_price * (1 + buy_fee)
            if cash < cost:
                buys_failed_insufficient_cash += 1
                continue

            cash -= cost
            holdings[ticker] = (shares, rebal_idx)
            buys_successful += 1

            if len(holdings) >= top_k:
                break

        holdings_value_after = sum(
            shares * (get_price(price_cache, t, date, "close") or 0)
            for t, (shares, _) in holdings.items()
        )
        portfolio_value_after = cash + holdings_value_after

        actual_cash_pct = (cash / portfolio_value_after * 100) if portfolio_value_after > 0 else 0
        actual_invested_pct = (holdings_value_after / portfolio_value_after * 100) if portfolio_value_after > 0 else 0
        position_underfill_pct = ((top_k - len(holdings)) / top_k * 100) if top_k > 0 else 0

        target_gap_pct = ((fixed_target_position_value - dynamic_target_position_value) / dynamic_target_position_value * 100) if dynamic_target_position_value > 0 else 0

        open_slots_before = top_k - n_holdings_before
        fixed_slots_affordable = int(cash_after_sells / (fixed_target_position_value * (1 + buy_fee))) if fixed_target_position_value > 0 else 0
        dynamic_slots_affordable = int(cash_after_sells / (dynamic_target_position_value * (1 + buy_fee))) if dynamic_target_position_value > 0 else 0
        dynamic_vs_fixed_slot_delta = dynamic_slots_affordable - fixed_slots_affordable
        dynamic_could_fill_open_slots = 1 if dynamic_slots_affordable >= open_slots_before else 0

        if is_focus_year:
            rebalance_rows.append({
                "rebalance_date": prev_date,
                "year": year,
                "portfolio_value_before": portfolio_value_before,
                "cash_before": cash_before,
                "holdings_value_before": holdings_value_before,
                "fixed_target_position_value": fixed_target_position_value,
                "dynamic_target_position_value": dynamic_target_position_value,
                "target_gap_pct": target_gap_pct,
                "n_holdings_before": n_holdings_before,
                "open_slots_before": open_slots_before,
                "buys_successful": buys_successful,
                "buys_failed_due_to_price_missing": buys_failed_price_missing,
                "buys_failed_due_to_insufficient_cash": buys_failed_insufficient_cash,
                "cash_after": cash,
                "holdings_value_after": holdings_value_after,
                "portfolio_value_after": portfolio_value_after,
                "actual_cash_pct": actual_cash_pct,
                "actual_invested_pct": actual_invested_pct,
                "position_underfill_pct": position_underfill_pct,
                "n_holdings_after": len(holdings),
                "fixed_slots_affordable": fixed_slots_affordable,
                "dynamic_slots_affordable": dynamic_slots_affordable,
                "dynamic_vs_fixed_slot_delta": dynamic_vs_fixed_slot_delta,
                "dynamic_could_fill_open_slots": dynamic_could_fill_open_slots,
                **depth_counts,
            })

        candidate_depth_rows.append({
            "rebalance_date": prev_date,
            "year": year,
            "portfolio_value_before": portfolio_value_before,
            "fixed_target_position_value": fixed_target_position_value,
            "dynamic_target_position_value": dynamic_target_position_value,
            "target_gap_pct": target_gap_pct,
            "n_holdings_before": n_holdings_before,
            "n_holdings_after": len(holdings),
            "actual_cash_pct": actual_cash_pct,
            "actual_invested_pct": actual_invested_pct,
            "position_underfill_pct": position_underfill_pct,
            **depth_counts,
            "fixed_slots_affordable": fixed_slots_affordable,
            "dynamic_slots_affordable": dynamic_slots_affordable,
            "dynamic_vs_fixed_slot_delta": dynamic_vs_fixed_slot_delta,
            "dynamic_could_fill_open_slots": dynamic_could_fill_open_slots,
        })

    rebalance_df = pd.DataFrame(rebalance_rows)
    depth_df = pd.DataFrame(candidate_depth_rows)

    year_summary_rows = []
    for year in sorted(depth_df["year"].unique()):
        year_data = depth_df[depth_df["year"] == year]
        n_rebal = len(year_data)

        row = {
            "year": year,
            "n_rebalance_dates": n_rebal,
            "avg_actual_cash_pct": year_data["actual_cash_pct"].mean(),
            "avg_actual_invested_pct": year_data["actual_invested_pct"].mean(),
            "avg_position_underfill_pct": year_data["position_underfill_pct"].mean(),
            "avg_n_holdings": year_data["n_holdings_after"].mean(),
            "avg_pass_count_depth_15": year_data["pass_count_depth_15"].mean(),
            "avg_pass_count_depth_25": year_data["pass_count_depth_25"].mean(),
            "avg_pass_count_depth_50": year_data["pass_count_depth_50"].mean(),
            "avg_pass_count_depth_100": year_data["pass_count_depth_100"].mean(),
            "avg_would_fill_topk_depth_15": year_data["would_fill_topk_depth_15"].mean() * 100,
            "avg_would_fill_topk_depth_25": year_data["would_fill_topk_depth_25"].mean() * 100,
            "avg_would_fill_topk_depth_50": year_data["would_fill_topk_depth_50"].mean() * 100,
            "avg_would_fill_topk_depth_100": year_data["would_fill_topk_depth_100"].mean() * 100,
            "avg_target_gap_pct": year_data["target_gap_pct"].mean(),
            "avg_dynamic_could_fill_open_slots": year_data["dynamic_could_fill_open_slots"].mean() * 100,
            "avg_dynamic_vs_fixed_slot_delta": year_data["dynamic_vs_fixed_slot_delta"].mean(),
        }

        year_summary_rows.append(row)

    year_summary_df = pd.DataFrame(year_summary_rows)

    return rebalance_df, depth_df, year_summary_df


def run_autopsy(args: argparse.Namespace) -> str:
    start_date = f"{args.start_year}-01-01"
    end_date = f"{args.end_year}-12-31"

    print(f"Loading signal matrix from {start_date} to {end_date}")
    signal_df = s.load_rl_signal_matrix(start=start_date, end=end_date, allow_2026=args.allow_2026)
    signal_df["time"] = pd.to_datetime(signal_df["time"], errors="coerce").dt.normalize()

    print("Loading order pressure signals...")
    c16_df = s.load_order_pressure(start=start_date, end=end_date)
    c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].copy()
    c16_df["time"] = pd.to_datetime(c16_df["time"], errors="coerce").dt.normalize()

    signal_df = signal_df.merge(c16_df, on=["time", "ticker"], how="left")

    if "blend" in signal_df.columns:
        signal_df.drop(columns=["blend"], inplace=True)

    signal_df["blend"] = signal_df["s1_proba"] * 0.7 + signal_df["order_volume_ratio_rank"] * 0.3

    strategy_map = {
        "blend_70_30_top5": ("blend", 5, 10),
        "s1_top5_rebal10": ("s1_proba", 5, 10),
        "c16_only_top5": ("order_volume_ratio_rank", 5, 10),
    }

    if args.strategy not in strategy_map:
        raise ValueError(f"Unknown strategy: {args.strategy}")

    signal_col, top_k, rebalance_days = strategy_map[args.strategy]

    print(f"Strategy: {args.strategy}, signal: {signal_col}, top_k: {top_k}, rebal: {rebalance_days}d")

    print("Loading caches...")
    price_cache = load_price_cache()
    liquid_lookup = load_liquid_lookup()
    trad_lookup = load_trad_lookup()

    record_focus_years = [2017, 2021, 2022, 2025]

    print(f"Running cash mechanics V2 (2015-2025), recording focus years: {record_focus_years}")
    rebalance_df, depth_df, year_summary = run_cash_mechanics_trace(
        signal_df,
        price_cache,
        liquid_lookup,
        trad_lookup,
        signal_col,
        top_k=top_k,
        rebalance_days=rebalance_days,
        min_hold_days=3,
        initial_capital=args.initial_capital,
        use_filters=args.use_filters,
        record_focus_years=record_focus_years,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / "artifacts" / "cash_mechanics_corrected_v2" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    rebalance_df.to_csv(output_dir / "rebalance_cash_mechanics.csv", index=False)
    depth_df.to_csv(output_dir / "candidate_depth_diagnostics.csv", index=False)
    year_summary.to_csv(output_dir / "year_cash_mechanics_summary.csv", index=False)

    focus_years_summary = year_summary[year_summary["year"].isin(record_focus_years)]

    full_summary = {
        "strategy": args.strategy,
        "signal_col": signal_col,
        "top_k": top_k,
        "rebalance_days": rebalance_days,
        "initial_capital": args.initial_capital,
        "record_focus_years": record_focus_years,
        "focus_years_summary": focus_years_summary.to_dict(orient="records"),
        "all_years_summary": year_summary.to_dict(orient="records"),
    }

    with open(output_dir / "summary.json", "w") as f:
        json.dump(full_summary, f, indent=2, default=str)

    readme_content = f"""# Cash Mechanics Autopsy - V2 (CORRECTED ACCOUNTING)

## Strategy
{args.strategy}

## Key Fixes in V2

1. **True Cash Metrics**:
   - `actual_cash_pct`: cash_after / portfolio_value_after * 100
   - `actual_invested_pct`: holdings_value_after / portfolio_value_after * 100
   - `position_underfill_pct`: (top_k - n_holdings) / top_k * 100

2. **Corrected target_gap_pct interpretation**:
   - positive = portfolio below initial-equivalent, but FIXED sizing is LARGER than dynamic
   - negative = portfolio above initial, FIXED sizing is SMALLER than dynamic

3. **Improved dynamic sizing diagnostic**:
   - `open_slots_before`: top_k - n_holdings_before
   - `fixed_slots_affordable`: cash / (fixed_target * (1+fee))
   - `dynamic_slots_affordable`: cash / (dynamic_target * (1+fee))
   - `dynamic_vs_fixed_slot_delta`: dynamic - fixed

## Focus Years Summary

{focus_years_summary.to_string(index=False)}

## All Years Summary

{year_summary.to_string(index=False)}
"""

    with open(output_dir / "README.md", "w") as f:
        f.write(readme_content)

    print("\n" + "=" * 80)
    print("YEAR CASH MECHANICS SUMMARY (FOCUS YEARS)")
    print("=" * 80)
    print(focus_years_summary.to_string(index=False))

    print("\n" + "=" * 80)
    print("KEY METRICS INTERPRETATION")
    print("=" * 80)
    for _, row in focus_years_summary.iterrows():
        print(f"Year {int(row['year'])}: actual_cash={row['avg_actual_cash_pct']:.1f}%, "
              f"actual_invested={row['avg_actual_invested_pct']:.1f}%, "
              f"underfill={row['avg_position_underfill_pct']:.1f}%, "
              f"target_gap={row['avg_target_gap_pct']:.1f}%, "
              f"dyn_could_fill={row['avg_dynamic_could_fill_open_slots']:.0f}%")

    print(f"\nArtifacts saved to: {output_dir}")
    return str(output_dir)


def main() -> None:
    run_autopsy(parse_args())


if __name__ == "__main__":
    main()