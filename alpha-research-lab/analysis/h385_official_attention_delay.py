from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


BRANCH_NAME = "h385_official_attention_delay"
MODE = "research_branch_official_attention_delay"
OUT_DIR = artifact_path("news_flow")

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
C16_PATH = data_path("features/xs_order_pressure_daily.parquet")
NEWS_PATH = data_path("features/news/datasets/news_daily_features.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")

HIGH_FLOW_THRESHOLD = 0.80
NEWS_PROB_THRESHOLD = 0.50
MIN_YEAR_ROWS = 100
MIN_TRAIN_YEARS = 2

NEWS_COLUMNS = [
    "date",
    "ticker",
    "phobert_forward_looking_article_count_1d",
    "phobert_forward_looking_prob_mean",
    "phobert_source_type_article_count_1d",
    "phobert_source_type_official_or_regulatory_prob_mean",
]


@dataclass(frozen=True)
class StateSpec:
    name: str
    label: str
    baseline: str
    family: str


STATE_SPECS = [
    StateSpec("official_all", "Official/regulatory-source rows", "official_all", "official"),
    StateSpec("official_no_support", "Official rows without C16 or insider support", "official_no_support", "official"),
    StateSpec("official_c16", "Official rows with high C16 support", "official_no_support", "official"),
    StateSpec("official_insider", "Official rows with insider support", "official_no_support", "official"),
    StateSpec("official_supported", "Official rows with C16 or insider support", "official_no_support", "official"),
    StateSpec("forward_all", "Forward-looking rows", "forward_all", "forward"),
    StateSpec("forward_no_support", "Forward-looking rows without C16 or insider support", "forward_no_support", "forward"),
    StateSpec("forward_c16", "Forward-looking rows with high C16 support", "forward_no_support", "forward"),
    StateSpec("forward_insider", "Forward-looking rows with insider support", "forward_no_support", "forward"),
    StateSpec("forward_supported", "Forward-looking rows with C16 or insider support", "forward_no_support", "forward"),
    StateSpec("official_forward_all", "Official or forward-looking rows", "official_forward_all", "combined"),
    StateSpec(
        "official_forward_no_support",
        "Official/forward rows without C16 or insider support",
        "official_forward_no_support",
        "combined",
    ),
    StateSpec(
        "official_forward_supported",
        "Official/forward rows with C16 or insider support",
        "official_forward_no_support",
        "combined",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H385: official/forward-looking attention delay audit. Tests whether "
            "official or forward-looking local-news rows need C16/insider support "
            "and pay better over 5 days than 1 day."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_PATH))
    parser.add_argument("--c16-path", type=str, default=str(C16_PATH))
    parser.add_argument("--news-path", type=str, default=str(NEWS_PATH))
    parser.add_argument("--matrix-path", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--min-train-years", type=int, default=MIN_TRAIN_YEARS)
    parser.add_argument("--min-year-rows", type=int, default=MIN_YEAR_ROWS)
    return parser.parse_args()


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _load_future_relative_returns(start_year: int, end_year: int) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    vni_close = load_vni_close().sort_index().reindex(close.index)
    out: pd.DataFrame | None = None
    for periods, column in [(1, "future_rel_return_1d"), (5, "future_rel_return_5d")]:
        stock_future = close.shift(-periods).div(close).sub(1.0)
        vni_future = vni_close.shift(-periods).div(vni_close).sub(1.0).reindex(stock_future.index)
        rel = stock_future.sub(vni_future, axis=0)
        part = to_long(rel, column)
        part["time"] = pd.to_datetime(part["time"], errors="coerce").dt.normalize()
        part["ticker"] = part["ticker"].astype(str).str.upper()
        part = part.loc[part["time"].dt.year.between(int(start_year), int(end_year))].copy()
        out = part if out is None else out.merge(part, on=["time", "ticker"], how="inner", validate="one_to_one")
    if out is None:
        raise ValueError("No future relative returns built")
    return out.dropna(subset=["time", "ticker", "future_rel_return_1d", "future_rel_return_5d"])


def _load_panel(args: argparse.Namespace) -> pd.DataFrame:
    if int(args.end_year) >= 2026:
        raise ValueError("H385 must not train or test on 2026+; set --end-year <= 2025")

    s1 = pd.read_parquet(args.s1_path, columns=["time", "ticker", "actual", "xs_proba"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    c16 = pd.read_parquet(
        args.c16_path,
        columns=["time", "ticker", "order_volume_ratio_rank", "order_pressure_available"],
    ).copy()
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()

    news = pd.read_parquet(args.news_path, columns=NEWS_COLUMNS).copy()
    news["time"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.drop(columns=["date"]).dropna(subset=["time", "ticker"])
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            news[column] = _safe_numeric(news, column)

    matrix = pd.read_parquet(
        args.matrix_path,
        columns=["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix["c5_ins_relative_size_5d"] = _safe_numeric(matrix, "c5_ins_relative_size_5d")
    matrix["c5_signal_present"] = _safe_numeric(matrix, "c5_signal_present")

    rel = _load_future_relative_returns(int(args.start_year), int(args.end_year))

    panel = s1.merge(c16, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(news, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(matrix, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(rel, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.loc[panel["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()

    panel["order_volume_ratio_rank"] = _safe_numeric(panel, "order_volume_ratio_rank", np.nan)
    panel["order_pressure_available"] = panel["order_pressure_available"].astype("boolean").fillna(False).astype(bool)
    panel["c5_ins_relative_size_5d"] = _safe_numeric(panel, "c5_ins_relative_size_5d")
    panel["c5_signal_present"] = _safe_numeric(panel, "c5_signal_present")
    for column in NEWS_COLUMNS:
        if column not in {"date", "ticker"}:
            panel[column] = _safe_numeric(panel, column)

    panel["official_high"] = (
        (panel["phobert_source_type_article_count_1d"] > 0.0)
        & (panel["phobert_source_type_official_or_regulatory_prob_mean"] >= NEWS_PROB_THRESHOLD)
    )
    panel["forward_high"] = (
        (panel["phobert_forward_looking_article_count_1d"] > 0.0)
        & (panel["phobert_forward_looking_prob_mean"] >= NEWS_PROB_THRESHOLD)
    )
    panel["c16_support"] = (
        panel["order_pressure_available"]
        & (panel["order_volume_ratio_rank"] >= HIGH_FLOW_THRESHOLD)
    )
    panel["insider_support"] = (
        (panel["c5_signal_present"] > 0.0)
        & (panel["c5_ins_relative_size_5d"] > 0.0)
    )
    panel["any_support"] = panel["c16_support"] | panel["insider_support"]
    panel["official_or_forward"] = panel["official_high"] | panel["forward_high"]
    panel["year"] = panel["time"].dt.year.astype(int)
    return panel.dropna(subset=["order_volume_ratio_rank", "future_rel_return_1d", "future_rel_return_5d"])


def _state_mask(panel: pd.DataFrame, state: str) -> pd.Series:
    official = panel["official_high"].fillna(False).astype(bool)
    forward = panel["forward_high"].fillna(False).astype(bool)
    official_forward = panel["official_or_forward"].fillna(False).astype(bool)
    c16 = panel["c16_support"].fillna(False).astype(bool)
    insider = panel["insider_support"].fillna(False).astype(bool)
    any_support = panel["any_support"].fillna(False).astype(bool)
    masks = {
        "official_all": official,
        "official_no_support": official & ~any_support,
        "official_c16": official & c16,
        "official_insider": official & insider,
        "official_supported": official & any_support,
        "forward_all": forward,
        "forward_no_support": forward & ~any_support,
        "forward_c16": forward & c16,
        "forward_insider": forward & insider,
        "forward_supported": forward & any_support,
        "official_forward_all": official_forward,
        "official_forward_no_support": official_forward & ~any_support,
        "official_forward_supported": official_forward & any_support,
    }
    if state not in masks:
        raise ValueError(f"Unknown state {state!r}")
    return masks[state]


def _safe_ic(frame: pd.DataFrame, score_col: str, target_col: str, min_rows: int) -> dict[str, object]:
    clean = frame[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < int(min_rows) or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 3:
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    rho, p_value = spearmanr(clean[score_col], clean[target_col])
    rho_value = float(np.asarray(rho).flat[0])
    if not np.isfinite(rho_value):
        return {"rows": int(len(clean)), "ic": None, "p_value": None}
    return {"rows": int(len(clean)), "ic": rho_value, "p_value": float(np.asarray(p_value).flat[0])}


def _metric_record(frame: pd.DataFrame, *, min_rows: int) -> dict[str, object]:
    c16_1d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_1d", int(min_rows))
    c16_5d = _safe_ic(frame, "order_volume_ratio_rank", "future_rel_return_5d", int(min_rows))
    return {
        "rows": int(len(frame)),
        "mean_rel_1d": float(frame["future_rel_return_1d"].mean()) if not frame.empty else None,
        "mean_rel_5d": float(frame["future_rel_return_5d"].mean()) if not frame.empty else None,
        "median_rel_1d": float(frame["future_rel_return_1d"].median()) if not frame.empty else None,
        "median_rel_5d": float(frame["future_rel_return_5d"].median()) if not frame.empty else None,
        "c16_ic_1d": c16_1d["ic"],
        "c16_ic_5d": c16_5d["ic"],
        "c16_ic_1d_p_value": c16_1d["p_value"],
        "c16_ic_5d_p_value": c16_5d["p_value"],
    }


def _fold_rows(panel: pd.DataFrame, *, min_train_years: int, min_year_rows: int) -> pd.DataFrame:
    years = sorted(int(year) for year in panel["year"].unique())
    rows: list[dict[str, object]] = []
    for test_year in years:
        train_years = [year for year in years if year < int(test_year)]
        if len(train_years) < int(min_train_years):
            continue
        train = panel.loc[panel["year"].isin(train_years)].copy()
        test = panel.loc[panel["year"] == int(test_year)].copy()
        for spec in STATE_SPECS:
            train_state = train.loc[_state_mask(train, spec.name)].copy()
            test_state = test.loc[_state_mask(test, spec.name)].copy()
            train_metrics = _metric_record(train_state, min_rows=int(min_year_rows))
            test_metrics = _metric_record(test_state, min_rows=int(min_year_rows))
            rows.append(
                {
                    "test_year": int(test_year),
                    "train_start_year": int(min(train_years)),
                    "train_end_year": int(max(train_years)),
                    "state": spec.name,
                    "label": spec.label,
                    "baseline": spec.baseline,
                    "family": spec.family,
                    **{f"train_{key}": value for key, value in train_metrics.items()},
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )
    return pd.DataFrame(rows)


def _summarize_states(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        state_rows = folds.loc[folds["state"] == spec.name].copy()
        valid = state_rows.loc[state_rows["test_rows"] >= MIN_YEAR_ROWS].copy()
        if valid.empty:
            rows.append(
                {
                    "state": spec.name,
                    "label": spec.label,
                    "baseline": spec.baseline,
                    "family": spec.family,
                    "wf_years": 0,
                    "mean_rows": 0.0,
                    "mean_rel_1d": None,
                    "mean_rel_5d": None,
                    "mean_c16_ic_1d": None,
                    "mean_c16_ic_5d": None,
                    "confirmation_2025_rel_1d": None,
                    "confirmation_2025_rel_5d": None,
                }
            )
            continue
        conf = valid.loc[valid["test_year"] == 2025]
        rows.append(
            {
                "state": spec.name,
                "label": spec.label,
                "baseline": spec.baseline,
                "family": spec.family,
                "wf_years": int(len(valid)),
                "mean_rows": float(valid["test_rows"].mean()),
                "mean_rel_1d": float(valid["test_mean_rel_1d"].mean()),
                "mean_rel_5d": float(valid["test_mean_rel_5d"].mean()),
                "mean_c16_ic_1d": (
                    float(valid["test_c16_ic_1d"].dropna().mean())
                    if valid["test_c16_ic_1d"].notna().any()
                    else None
                ),
                "mean_c16_ic_5d": (
                    float(valid["test_c16_ic_5d"].dropna().mean())
                    if valid["test_c16_ic_5d"].notna().any()
                    else None
                ),
                "confirmation_2025_rel_1d": (
                    float(conf.iloc[0]["test_mean_rel_1d"]) if not conf.empty else None
                ),
                "confirmation_2025_rel_5d": (
                    float(conf.iloc[0]["test_mean_rel_5d"]) if not conf.empty else None
                ),
            }
        )
    summary = pd.DataFrame(rows)
    mean_1d = summary.set_index("state")["mean_rel_1d"].to_dict()
    mean_5d = summary.set_index("state")["mean_rel_5d"].to_dict()
    conf_1d = summary.set_index("state")["confirmation_2025_rel_1d"].to_dict()
    conf_5d = summary.set_index("state")["confirmation_2025_rel_5d"].to_dict()
    summary["lift_vs_baseline_1d"] = [
        (row["mean_rel_1d"] - mean_1d.get(row["baseline"]))
        if row["mean_rel_1d"] is not None and mean_1d.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["lift_vs_baseline_5d"] = [
        (row["mean_rel_5d"] - mean_5d.get(row["baseline"]))
        if row["mean_rel_5d"] is not None and mean_5d.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["confirmation_2025_lift_1d"] = [
        (row["confirmation_2025_rel_1d"] - conf_1d.get(row["baseline"]))
        if row["confirmation_2025_rel_1d"] is not None and conf_1d.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]
    summary["confirmation_2025_lift_5d"] = [
        (row["confirmation_2025_rel_5d"] - conf_5d.get(row["baseline"]))
        if row["confirmation_2025_rel_5d"] is not None and conf_5d.get(row["baseline"]) is not None
        else None
        for _, row in summary.iterrows()
    ]

    lift_by_year = folds[["test_year", "state", "baseline", "test_mean_rel_1d", "test_mean_rel_5d"]].copy()
    base = lift_by_year.rename(
        columns={
            "state": "baseline_state",
            "test_mean_rel_1d": "baseline_mean_rel_1d",
            "test_mean_rel_5d": "baseline_mean_rel_5d",
        }
    )[["test_year", "baseline_state", "baseline_mean_rel_1d", "baseline_mean_rel_5d"]]
    lifted = lift_by_year.merge(
        base,
        left_on=["test_year", "baseline"],
        right_on=["test_year", "baseline_state"],
        how="left",
        validate="many_to_one",
    )
    lifted["lift_1d"] = lifted["test_mean_rel_1d"] - lifted["baseline_mean_rel_1d"]
    lifted["lift_5d"] = lifted["test_mean_rel_5d"] - lifted["baseline_mean_rel_5d"]
    pos_counts = lifted.groupby("state", as_index=False).agg(
        years_with_lift=("lift_5d", lambda s: int(s.dropna().shape[0])),
        pos_lift_5d_years=("lift_5d", lambda s: int((s.dropna() > 0.0).sum())),
        pos_lift_1d_years=("lift_1d", lambda s: int((s.dropna() > 0.0).sum())),
    )
    summary = summary.merge(pos_counts, on="state", how="left", validate="one_to_one")
    summary["pct_pos_lift_5d_years"] = summary["pos_lift_5d_years"] / summary["years_with_lift"].replace(0, np.nan)
    summary["pct_pos_lift_1d_years"] = summary["pos_lift_1d_years"] / summary["years_with_lift"].replace(0, np.nan)
    return summary.sort_values(
        by=["lift_vs_baseline_5d", "mean_rel_5d", "mean_rows"],
        ascending=[False, False, False],
        ignore_index=True,
    )


def _state_record(summary: pd.DataFrame, state: str) -> dict[str, object]:
    row = summary.loc[summary["state"] == state]
    return row.iloc[0].to_dict() if not row.empty else {}


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _passes_delay_gate(row: dict[str, object]) -> bool:
    return bool(
        (_safe_float(row.get("mean_rows")) or 0.0) >= MIN_YEAR_ROWS
        and (_safe_float(row.get("lift_vs_baseline_5d")) or 0.0) > 0.002
        and (_safe_float(row.get("pct_pos_lift_5d_years")) or 0.0) >= 0.60
        and (_safe_float(row.get("confirmation_2025_lift_5d")) or 0.0) > 0.0
        and (_safe_float(row.get("lift_vs_baseline_5d")) or 0.0)
        >= (_safe_float(row.get("lift_vs_baseline_1d")) or -999.0)
    )


def _verdict(summary: pd.DataFrame) -> tuple[str, str, str, list[str], list[str]]:
    primary_states = ["official_supported", "official_forward_supported"]
    secondary_states = ["official_c16", "official_insider", "forward_supported", "forward_c16", "forward_insider"]
    primary_pass = [state for state in primary_states if _passes_delay_gate(_state_record(summary, state))]
    secondary_pass = [state for state in secondary_states if _passes_delay_gate(_state_record(summary, state))]
    if primary_pass:
        return (
            "PASSED",
            "offline_evidence",
            "A primary official/forward support state improved delayed 5d payoff versus unsupported rows.",
            primary_pass,
            secondary_pass,
        )
    if secondary_pass:
        return (
            "MIXED",
            "park_or_narrow",
            "Only a narrower C16/insider support substate improved delayed 5d payoff.",
            primary_pass,
            secondary_pass,
        )
    return (
        "FAILED",
        "branch_kill_or_reframe",
        "No official/forward support state improved delayed 5d payoff cleanly enough.",
        primary_pass,
        secondary_pass,
    )


def main() -> None:
    args = parse_args()
    panel = _load_panel(args)
    if panel.empty:
        raise ValueError("No rows after building H385 panel")
    folds = _fold_rows(
        panel,
        min_train_years=int(args.min_train_years),
        min_year_rows=int(args.min_year_rows),
    )
    if folds.empty:
        raise ValueError("No walk-forward folds produced")
    state_summary = _summarize_states(folds)
    verdict, durable_status, branch_decision, primary_pass, secondary_pass = _verdict(state_summary)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    folds_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_folds.parquet"
    states_path = OUT_DIR / f"{ts}_{BRANCH_NAME}_states.parquet"
    folds.to_parquet(folds_path, index=False)
    state_summary.to_parquet(states_path, index=False)

    key_states = {
        state: _state_record(state_summary, state)
        for state in [
            "official_no_support",
            "official_supported",
            "official_c16",
            "official_insider",
            "forward_no_support",
            "forward_supported",
            "official_forward_no_support",
            "official_forward_supported",
        ]
    }
    summary = {
        "branch": "official_attention_delay",
        "experiment_id": "H385",
        "verdict": verdict,
        "durable_status": durable_status,
        "branch_decision": branch_decision,
        "primary_pass_states": primary_pass,
        "secondary_pass_states": secondary_pass,
        "protocol": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
            "test_years": sorted(int(year) for year in folds["test_year"].unique()),
            "official_threshold": NEWS_PROB_THRESHOLD,
            "forward_threshold": NEWS_PROB_THRESHOLD,
            "high_c16_threshold": HIGH_FLOW_THRESHOLD,
            "support": "high C16 or positive C5 insider signal",
            "primary_target": "future_rel_return_5d",
            "delay_check": "5d lift must be positive, consistent, positive in 2025, and at least as large as 1d lift",
        },
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "official_share": float(panel["official_high"].mean()),
        "forward_share": float(panel["forward_high"].mean()),
        "support_share": float(panel["any_support"].mean()),
        "key_states": key_states,
        "pass_rule": (
            "PASS if official_supported or official_forward_supported has 5d "
            "mean payoff lift >0.002 versus unsupported rows, >=60% positive "
            "5d lift years, positive 2025 5d lift, enough support, and 5d lift "
            "at least as large as 1d lift. MIXED if only a narrower support "
            "substate clears. Otherwise FAILED."
        ),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode=MODE,
        name=BRANCH_NAME,
        summary=summary,
        artifacts={
            "folds": folds_path,
            "states": states_path,
            "s1": Path(args.s1_path),
            "c16": Path(args.c16_path),
            "news": Path(args.news_path),
            "matrix": Path(args.matrix_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "min_train_years": int(args.min_train_years),
            "min_year_rows": int(args.min_year_rows),
        },
    )

    print("H385 official attention delay")
    print(f"saved_summary={summary_path}")
    print(f"folds={folds_path}")
    print(f"states={states_path}")
    print(
        f"verdict={verdict} | primary_pass={primary_pass} | secondary_pass={secondary_pass}"
    )
    print(
        state_summary[
            [
                "state",
                "family",
                "wf_years",
                "mean_rows",
                "mean_rel_1d",
                "mean_rel_5d",
                "lift_vs_baseline_1d",
                "lift_vs_baseline_5d",
                "pct_pos_lift_5d_years",
                "confirmation_2025_lift_5d",
                "mean_c16_ic_5d",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
