"""
BR5: market_sentiment_regime_gate

Hypothesis: H482 found ticker-level ultra_negative doesn't filter S1 quality.
But MARKET-WIDE sentiment might be a REGIME indicator. Compute market avg sentiment
per day, test S1/C23 IC in market-sentiment bottom vs top 20%.
Mechanism: market sentiment predicts signal quality across all tickers.

First test: market-level avg PhoBERT sentiment × S1/C23 IC vs random baseline.
Compare: S1 in market-sentiment bottom 20% vs top 20% vs all rows.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "market_sentiment_regime_gate"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H482 found ticker-level ultra_negative doesn't filter S1 quality. "
        "But MARKET-WIDE sentiment might be a REGIME indicator. "
        "Compute market avg sentiment per day, test S1/C23 IC in market-sentiment "
        "bottom vs top 20%. Mechanism: market sentiment predicts signal quality."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR5 market_sentiment_regime_gate test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--phobert-path", type=str,
                        default=str(data_path("features/news/datasets/phobert_ticker_day_sentiment.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    import re
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_volume"] - order_stats["sell_volume"]) /
        (order_stats["buy_volume"] + order_stats["sell_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    phobert = pd.read_parquet(args.phobert_path)
    phobert = phobert.rename(columns={"date": "time"})
    phobert["time"] = pd.to_datetime(phobert["time"])
    phobert = phobert[phobert["time"].dt.year <= 2025]

    phobert = pd.read_parquet(args.phobert_path)
    phobert = phobert.rename(columns={"date": "time"})
    phobert["time"] = pd.to_datetime(phobert["time"])
    phobert = phobert[phobert["time"].dt.year <= 2025]

    available = [c for c in ["phobert_prob_neg_mean", "phobert_prob_pos_mean"] if c in phobert.columns]
    if available:
        has_news_mask = phobert["phobert_article_count_1d"] > 0 if "phobert_article_count_1d" in phobert.columns else phobert[available[0]] > 0
        phobert_with_news = phobert[has_news_mask]
        market_sentiment = phobert_with_news.groupby("time")[available].mean()
        market_sentiment = market_sentiment.reset_index()
        market_sentiment = market_sentiment.rename(columns={
            "phobert_prob_neg_mean": "market_avg_prob_neg",
            "phobert_prob_pos_mean": "market_avg_prob_pos",
        })

        date_neg_rank = market_sentiment["market_avg_prob_neg"].rank(method="average", pct=True)
        market_sentiment["market_bearish"] = date_neg_rank >= 0.80
        market_sentiment["market_bullish"] = date_neg_rank <= 0.20
        market_sentiment["market_neutral"] = ~market_sentiment["market_bearish"] & ~market_sentiment["market_bullish"]

        panel = panel.merge(
            market_sentiment[["time", "market_bearish", "market_bullish", "market_neutral"]],
            on="time",
            how="left",
        )

        panel["market_bearish"] = panel["market_bearish"].fillna(False)
        panel["market_bullish"] = panel["market_bullish"].fillna(False)
        panel["market_neutral"] = panel["market_neutral"].fillna(False)

        panel["mkt_bearish_buy_exp"] = panel["market_bearish"] & panel["buy_heavy_expansion"]
        panel["mkt_bullish_buy_exp"] = panel["market_bullish"] & panel["buy_heavy_expansion"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("market_bearish", "Market avg sentiment = bearish (top 20% prob_neg)", family="market_sentiment"),
    StateSpec("market_bullish", "Market avg sentiment = bullish (bottom 20% prob_neg)", family="market_sentiment"),
    StateSpec("market_neutral", "Market avg sentiment = neutral", family="market_sentiment"),
    StateSpec("buy_heavy_expansion", "C20: buy_heavy × vol expansion", family="signal", primary=True),
    StateSpec("mkt_bearish_buy_exp", "Bearish market + C20 signal", family="combo"),
    StateSpec("mkt_bullish_buy_exp", "Bullish market + C20 signal", family="combo"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    c20_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c20_lift = c20_ic - baseline_ic

    bearish_ic = results[results["name"] == "market_bearish"]["avg_ic"].iloc[0] if not results.empty else 0
    bullish_ic = results[results["name"] == "market_bullish"]["avg_ic"].iloc[0] if not results.empty else 0
    neutral_ic = results[results["name"] == "market_neutral"]["avg_ic"].iloc[0] if not results.empty else 0
    bearish_lift = bearish_ic - baseline_ic
    bullish_lift = bullish_ic - baseline_ic

    mkt_bearish_c20_ic = results[results["name"] == "mkt_bearish_buy_exp"]["avg_ic"].iloc[0] if not results.empty else 0
    mkt_bullish_c20_ic = results[results["name"] == "mkt_bullish_buy_exp"]["avg_ic"].iloc[0] if not results.empty else 0
    mkt_bearish_c20_lift = mkt_bearish_c20_ic - baseline_ic
    mkt_bullish_c20_lift = mkt_bullish_c20_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    sentiment_regime_differential = max(bearish_lift, bullish_lift) - min(bearish_lift, bullish_lift)

    if sentiment_regime_differential > 0.01 and mkt_bearish_c20_lift > c20_lift + 0.005:
        decision = "PASSED"
    elif sentiment_regime_differential > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c20_ic": float(c20_ic),
            "c20_lift": float(c20_lift),
            "market_bearish_ic": float(bearish_ic),
            "market_bullish_ic": float(bullish_ic),
            "market_neutral_ic": float(neutral_ic),
            "bearish_lift": float(bearish_lift),
            "bullish_lift": float(bullish_lift),
            "mkt_bearish_c20_ic": float(mkt_bearish_c20_ic),
            "mkt_bullish_c20_ic": float(mkt_bullish_c20_ic),
            "mkt_bearish_c20_lift": float(mkt_bearish_c20_lift),
            "mkt_bullish_c20_lift": float(mkt_bullish_c20_lift),
            "sentiment_regime_differential": float(sentiment_regime_differential),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"C20 (buy_heavy × exp): IC={c20_ic:.4f}, lift={c20_lift:+.4f}")
    print(f"\nMarket sentiment regime:")
    print(f"  market_bearish: IC={bearish_ic:.4f}, lift={bearish_lift:+.4f}")
    print(f"  market_bullish: IC={bullish_ic:.4f}, lift={bullish_lift:+.4f}")
    print(f"  market_neutral: IC={neutral_ic:.4f}")
    print(f"\nMarket sentiment × C20:")
    print(f"  bearish + C20: IC={mkt_bearish_c20_ic:.4f}, lift={mkt_bearish_c20_lift:+.4f}")
    print(f"  bullish + C20: IC={mkt_bullish_c20_ic:.4f}, lift={mkt_bullish_c20_lift:+.4f}")
    print(f"\nSentiment regime differential: {sentiment_regime_differential:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
