"""
H332 - surrogate disagreement residual audit.

Question:
- Does the remaining short-horizon information in the cheap LLM-surrogate
  branch sit in the hard tail where the deterministic student disagrees with
  the teacher or routes back to the teacher?

Design:
- use the `aggressive_triple` H330 hybrid policy as the predeclared surrogate
  contract because it was the best cost / contract trade-off
- merge the H330 route table with H331 teacher-versus-student field
  disagreements
- build a small predeclared ticker-day state set:
  - `fallback_day`
  - `novelty_disagree_day`
  - `lexical_2plus_day`
  - `hard_tail_day = fallback or novelty_disagree or lexical_2plus`
  - control: `safe_only_day`
- audit `1d` and `5d` forward excess-return reactions vs `VNINDEX`
- measure both signed response and absolute-response uplift against `safe_only`

Verdict rule:
- PASS:
  - at least one residual state has positive signed uplift vs `safe_only` on
    both `1d` and `5d`
  - the same state has positive absolute-response uplift on both horizons
  - and its mean daily IC is positive on at least one horizon
- MIXED:
  - at least one residual state has positive absolute-response uplift on both
    horizons and positive signed uplift on at least one horizon
- FAILED otherwise

This does not change the live branch and does not use `2026+`.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import h329_title_sequence_novelty_distillation as h329  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
TARGET_HORIZONS = (1, 5)
POLICY_NAME = "aggressive_triple"
STATE_COLUMNS = (
    "fallback_day",
    "novelty_disagree_day",
    "lexical_2plus_day",
    "hard_tail_day",
    "safe_only_day",
)
TESTED_RESIDUAL_STATES = (
    "fallback_day",
    "novelty_disagree_day",
    "lexical_2plus_day",
    "hard_tail_day",
)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value.relative_to(ROOT))
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _load_artifact_path(latest_summary_name: str, artifact_key: str) -> Path:
    summary_path = ROOT / "artifacts" / "run_summaries" / latest_summary_name
    obj = json.loads(summary_path.read_text(encoding="utf-8"))
    rel_path = obj["artifacts"][artifact_key]
    return ROOT / rel_path


def load_state_panel() -> pd.DataFrame:
    route_path = _load_artifact_path(
        "latest_research_branch_hybrid_news_cascade_audit.json",
        "routes",
    )
    article_path = _load_artifact_path(
        "latest_research_branch_deterministic_event_family_router_audit.json",
        "articles",
    )

    routes = pd.read_parquet(route_path)
    routes = routes[routes["policy_name"] == POLICY_NAME].copy()
    routes["time"] = pd.to_datetime(routes["time"], errors="coerce")
    routes["novelty_disagree"] = routes["teacher_novelty"] != routes["deterministic_novelty"]
    routes["fallback"] = ~routes["use_deterministic"].astype(bool)

    articles = pd.read_parquet(article_path)
    fields = ["source_authority", "expectation_alignment", "impact_scope", "event_type"]
    for field in fields:
        articles[f"{field}_present"] = articles[f"teacher_{field}"].notna()
        articles[f"{field}_disagree_present"] = (
            articles[f"{field}_present"]
            & (articles[f"teacher_{field}"] != articles[f"deterministic_{field}"])
        )
    articles["present_field_disagree_count"] = articles[[f"{field}_disagree_present" for field in fields]].sum(axis=1)

    merged = routes.merge(
        articles[["article_id", "present_field_disagree_count"]],
        on="article_id",
        how="left",
    )
    merged["present_field_disagree_count"] = pd.to_numeric(
        merged["present_field_disagree_count"],
        errors="coerce",
    ).fillna(0).astype(int)
    merged["lexical_2plus"] = merged["present_field_disagree_count"] >= 2
    merged["hard_tail"] = merged["fallback"] | merged["novelty_disagree"] | merged["lexical_2plus"]
    merged["safe_article"] = (
        merged["use_deterministic"].astype(bool)
        & (~merged["novelty_disagree"])
        & (~merged["lexical_2plus"])
    )

    rows: list[dict[str, object]] = []
    for row in merged.itertuples(index=False):
        for ticker in str(row.tickers_joined).split(","):
            ticker = ticker.strip().upper()
            if not ticker:
                continue
            rows.append(
                {
                    "time": pd.Timestamp(row.time),
                    "ticker": ticker,
                    "fallback_day": int(bool(row.fallback)),
                    "novelty_disagree_day": int(bool(row.novelty_disagree)),
                    "lexical_2plus_day": int(bool(row.lexical_2plus)),
                    "hard_tail_day": int(bool(row.hard_tail)),
                    "safe_article": int(bool(row.safe_article)),
                }
            )
    if not rows:
        raise RuntimeError("No disagreement residual rows could be built from H330/H331 artifacts")

    panel = pd.DataFrame(rows)
    daily = panel.groupby(["time", "ticker"], as_index=False)[
        ["fallback_day", "novelty_disagree_day", "lexical_2plus_day", "hard_tail_day", "safe_article"]
    ].sum()
    for column in ["fallback_day", "novelty_disagree_day", "lexical_2plus_day", "hard_tail_day"]:
        daily[column] = (daily[column] > 0).astype(int)
    daily["safe_only_day"] = ((daily["safe_article"] > 0) & (daily["hard_tail_day"] == 0)).astype(int)
    daily = daily.drop(columns=["safe_article"])
    return daily.sort_values(["time", "ticker"]).reset_index(drop=True)


def _evaluate_states(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, object]], str, dict[str, object]]:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[(close.index.year >= 2015) & (close.index.year <= 2017)].copy()
    benchmark_close = load_vni_close().reindex(close.index)

    rows = []
    state_summaries = []
    passing_candidates = []
    mixed_candidates = []

    for horizon in TARGET_HORIZONS:
        target = h329._future_excess_return(close, benchmark_close, periods=horizon)
        target_long = to_long(target, f"future_rel_return_{horizon}d")
        target_long["time"] = pd.to_datetime(target_long["time"], errors="coerce")
        target_long = target_long[(target_long["time"].dt.year >= 2015) & (target_long["time"].dt.year <= 2017)].copy()
        target_col = f"future_rel_return_{horizon}d"
        target_long[target_col] = pd.to_numeric(target_long[target_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        target_long = target_long.dropna(subset=[target_col])
        target_long[f"future_rel_abs_return_{horizon}d"] = target_long[target_col].abs()

        merged = panel.merge(target_long, on=["time", "ticker"], how="inner")
        safe_subset = merged[merged["safe_only_day"] > 0].copy()
        safe_mean_signed = float(pd.to_numeric(safe_subset[target_col], errors="coerce").mean()) if not safe_subset.empty else float("nan")
        safe_mean_abs = (
            float(pd.to_numeric(safe_subset[f"future_rel_abs_return_{horizon}d"], errors="coerce").mean())
            if not safe_subset.empty
            else float("nan")
        )

        for state in STATE_COLUMNS:
            ic_rows = h329._daily_ic_series(merged[["time", state, target_col]].copy(), state, target_col)
            stats = h329._summary_from_series(ic_rows)
            active = merged[merged[state] > 0].copy()
            active_mean_signed = float(pd.to_numeric(active[target_col], errors="coerce").mean()) if not active.empty else float("nan")
            active_mean_abs = (
                float(pd.to_numeric(active[f"future_rel_abs_return_{horizon}d"], errors="coerce").mean())
                if not active.empty
                else float("nan")
            )
            uplift_signed = active_mean_signed - safe_mean_signed if np.isfinite(active_mean_signed) and np.isfinite(safe_mean_signed) else float("nan")
            uplift_abs = active_mean_abs - safe_mean_abs if np.isfinite(active_mean_abs) and np.isfinite(safe_mean_abs) else float("nan")

            row = {
                "horizon": f"{horizon}d",
                "state_name": state,
                "row_count": int(len(merged)),
                "active_rows": int((merged[state] > 0).sum()),
                "active_share": float((merged[state] > 0).mean()),
                "safe_only_active_rows": int((merged["safe_only_day"] > 0).sum()),
                "safe_only_mean_signed": safe_mean_signed,
                "safe_only_mean_abs": safe_mean_abs,
                "active_mean_signed": active_mean_signed,
                "active_mean_abs": active_mean_abs,
                "signed_uplift_vs_safe_only": uplift_signed,
                "abs_uplift_vs_safe_only": uplift_abs,
                **stats,
            }
            rows.append(row)

    results = pd.DataFrame(rows)

    for state in TESTED_RESIDUAL_STATES:
        state_rows = results[results["state_name"] == state].copy()
        if state_rows.empty:
            continue
        horizon_map = {row["horizon"]: row for row in state_rows.to_dict(orient="records")}
        row_1d = horizon_map.get("1d", {})
        row_5d = horizon_map.get("5d", {})
        pass_candidate = bool(
            float(row_1d.get("signed_uplift_vs_safe_only", float("nan"))) > 0.0
            and float(row_5d.get("signed_uplift_vs_safe_only", float("nan"))) > 0.0
            and float(row_1d.get("abs_uplift_vs_safe_only", float("nan"))) > 0.0
            and float(row_5d.get("abs_uplift_vs_safe_only", float("nan"))) > 0.0
            and (
                float(row_1d.get("mean_ic", float("nan"))) > 0.0
                or float(row_5d.get("mean_ic", float("nan"))) > 0.0
            )
        )
        mixed_candidate = bool(
            float(row_1d.get("abs_uplift_vs_safe_only", float("nan"))) > 0.0
            and float(row_5d.get("abs_uplift_vs_safe_only", float("nan"))) > 0.0
            and (
                float(row_1d.get("signed_uplift_vs_safe_only", float("nan"))) > 0.0
                or float(row_5d.get("signed_uplift_vs_safe_only", float("nan"))) > 0.0
            )
        )
        summary = {
            "state_name": state,
            "pass_candidate": pass_candidate,
            "mixed_candidate": mixed_candidate,
            "one_day_signed_uplift": row_1d.get("signed_uplift_vs_safe_only"),
            "five_day_signed_uplift": row_5d.get("signed_uplift_vs_safe_only"),
            "one_day_abs_uplift": row_1d.get("abs_uplift_vs_safe_only"),
            "five_day_abs_uplift": row_5d.get("abs_uplift_vs_safe_only"),
            "one_day_mean_ic": row_1d.get("mean_ic"),
            "five_day_mean_ic": row_5d.get("mean_ic"),
        }
        state_summaries.append(summary)
        if pass_candidate:
            passing_candidates.append(summary)
        if mixed_candidate:
            mixed_candidates.append(summary)

    if passing_candidates:
        verdict = "PASSED"
        best = passing_candidates[0]
    elif mixed_candidates:
        verdict = "MIXED"
        best = mixed_candidates[0]
    else:
        verdict = "FAILED"
        ranked = sorted(
            state_summaries,
            key=lambda item: (
                float(item.get("one_day_abs_uplift") or float("-inf"))
                + float(item.get("five_day_abs_uplift") or float("-inf"))
            ),
            reverse=True,
        )
        best = ranked[0] if ranked else {}

    return results, state_summaries, verdict, best


def main() -> None:
    panel = load_state_panel()
    results, state_summaries, verdict, best_state = _evaluate_states(panel)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel_path = OUT_DIR / f"{ts}_h332_surrogate_disagreement_residual_panel.parquet"
    results_path = OUT_DIR / f"{ts}_h332_surrogate_disagreement_residual_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_h332_surrogate_disagreement_residual_audit_details.json"

    panel.to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    summary = {
        "verdict": verdict,
        "policy_name": POLICY_NAME,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "state_activity": _json_safe(
            {
                state: {
                    "active_rows": int((panel[state] > 0).sum()),
                    "active_share": float((panel[state] > 0).mean()),
                }
                for state in STATE_COLUMNS
            }
        ),
        "state_summaries": _json_safe(state_summaries),
        "best_state": _json_safe(best_state),
        "artifacts": {
            "panel": str(panel_path.relative_to(ROOT)),
            "results": str(results_path.relative_to(ROOT)),
        },
    }
    details_path.write_text(json.dumps(_json_safe(summary), indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_surrogate_disagreement_residual_audit",
        name="h332_surrogate_disagreement_residual_audit",
        summary=summary,
        artifacts={
            "panel": str(panel_path),
            "results": str(results_path),
            "details": str(details_path),
        },
        metadata={
            "session": 151,
            "policy_name": POLICY_NAME,
            "target_horizons": list(TARGET_HORIZONS),
        },
    )

    print("H332 SURROGATE DISAGREEMENT RESIDUAL AUDIT")
    print(f"Verdict: {verdict}")
    print("Best state:", best_state.get("state_name"))
    print(pd.DataFrame(state_summaries).to_string(index=False))


if __name__ == "__main__":
    main()
