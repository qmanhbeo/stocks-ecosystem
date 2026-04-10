"""
H330 - hybrid news cascade audit.

Question:
- Can a deterministic-first novelty router recover the teacher novelty-alpha
  contract while sending only the ambiguous article tail to the paid API?

Design:
- reuse the H329 deterministic novelty rules as the student
- define a small predeclared policy ladder from strict to aggressive
- for each policy:
  - keep deterministic labels only for high-confidence rows
  - route the ambiguous rows back to the teacher label as an oracle fallback
  - measure holdout novelty-label recovery on `2017`
  - rerun the H291-style novelty decay contract on `2015-2017`
  - estimate API cost share from both article counts and `article_text_length`
- verdict logic:
  - PASS: preserve all key novelty contracts with at most 60% API share and
    holdout `follow_up` F1 of at least 0.15
  - MIXED: preserve all contracts with at most 75% API share, or preserve at
    least two contracts with at most 60% API share
  - FAILED otherwise

This does not change the live branch and does not use `2026+`.
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import h329_title_sequence_novelty_distillation as h329  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

HOLDOUT_YEAR = 2017
PASS_MAX_API_ARTICLE_SHARE = 0.60
PASS_MAX_API_TEXT_SHARE = 0.60
MIXED_MAX_API_ARTICLE_SHARE = 0.75
MIXED_MAX_API_TEXT_SHARE = 0.75
PASS_FOLLOWUP_F1 = 0.15


@dataclass(frozen=True)
class CascadePolicy:
    name: str
    description: str
    enable_new: bool = False
    new_max_similarity: float = 0.0
    new_max_tickers: int = 0
    enable_follow_up: bool = False
    follow_min_similarity: float = 0.0
    follow_max_similarity: float = 0.0
    follow_max_gap_days: int = 0
    follow_max_story_matches: int = 0
    follow_max_tickers: int = 0
    enable_recycled: bool = False
    recycled_min_similarity: float = 1.0
    recycled_min_summary_jaccard: float = 1.0
    recycled_min_story_matches: int = 999
    recycled_max_tickers: int = 0


POLICIES = [
    CascadePolicy(
        name="new_only_strict",
        description="Only auto-label the cleanest obvious new single-name rows.",
        enable_new=True,
        new_max_similarity=0.08,
        new_max_tickers=1,
    ),
    CascadePolicy(
        name="new_only_balanced",
        description="Auto-label obvious new rows on one- and two-ticker stories.",
        enable_new=True,
        new_max_similarity=0.12,
        new_max_tickers=2,
    ),
    CascadePolicy(
        name="new_plus_recycled",
        description="Keep obvious new rows plus very strong recycled repeats; route follow_up to API.",
        enable_new=True,
        new_max_similarity=0.12,
        new_max_tickers=2,
        enable_recycled=True,
        recycled_min_similarity=0.72,
        recycled_min_summary_jaccard=0.90,
        recycled_min_story_matches=8,
        recycled_max_tickers=6,
    ),
    CascadePolicy(
        name="balanced_triple",
        description="Moderate coverage for all three labels with a conservative follow_up gate.",
        enable_new=True,
        new_max_similarity=0.12,
        new_max_tickers=2,
        enable_follow_up=True,
        follow_min_similarity=0.24,
        follow_max_similarity=0.48,
        follow_max_gap_days=3,
        follow_max_story_matches=2,
        follow_max_tickers=2,
        enable_recycled=True,
        recycled_min_similarity=0.68,
        recycled_min_summary_jaccard=0.88,
        recycled_min_story_matches=5,
        recycled_max_tickers=8,
    ),
    CascadePolicy(
        name="aggressive_triple",
        description="Broader high-confidence routing for all labels before handing off to API.",
        enable_new=True,
        new_max_similarity=0.16,
        new_max_tickers=3,
        enable_follow_up=True,
        follow_min_similarity=0.23,
        follow_max_similarity=0.55,
        follow_max_gap_days=4,
        follow_max_story_matches=3,
        follow_max_tickers=3,
        enable_recycled=True,
        recycled_min_similarity=0.60,
        recycled_min_summary_jaccard=0.82,
        recycled_min_story_matches=4,
        recycled_max_tickers=12,
    ),
]


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


def _load_text_lengths() -> dict[str, int]:
    lengths: dict[str, int] = {}
    files = sorted(path for path in h329.CACHE_DIR.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem))
    for cache_path in files:
        with cache_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                article_id = str(obj.get("id", "") or "").strip()
                if not article_id:
                    continue
                length = obj.get("article_text_length")
                if isinstance(length, (int, float)) and math.isfinite(length):
                    lengths[article_id] = int(length)
    return lengths


def _attach_text_lengths(frame: pd.DataFrame) -> pd.DataFrame:
    lengths = _load_text_lengths()
    out = frame.copy()
    fallback = out["title"].fillna("").str.len() + out["summary"].fillna("").str.len()
    out["article_text_length"] = out["article_id"].map(lengths).fillna(fallback).astype(int)
    return out


def _high_conf_new(row: pd.Series, policy: CascadePolicy) -> bool:
    gap_days = row["best_story_gap_days"]
    return bool(
        row["deterministic_novelty"] == "new"
        and int(row["ticker_count"]) <= int(policy.new_max_tickers)
        and float(row["best_combined_similarity"]) <= float(policy.new_max_similarity)
        and int(row["story_matches_30d"]) == 0
        and int(row["recent_story_matches_7d"]) == 0
        and not bool(row["exact_title_repeat"])
        and (pd.isna(gap_days) or int(gap_days) > h329.FOLLOWUP_STORY_GAP_DAYS)
    )


def _high_conf_follow_up(row: pd.Series, policy: CascadePolicy) -> bool:
    gap_days = row["best_story_gap_days"]
    if pd.isna(gap_days):
        return False
    return bool(
        row["deterministic_novelty"] == "follow_up"
        and int(row["ticker_count"]) <= int(policy.follow_max_tickers)
        and int(gap_days) <= int(policy.follow_max_gap_days)
        and float(row["best_combined_similarity"]) >= float(policy.follow_min_similarity)
        and float(row["best_combined_similarity"]) <= float(policy.follow_max_similarity)
        and int(row["recent_story_matches_7d"]) >= 1
        and int(row["story_matches_30d"]) <= int(policy.follow_max_story_matches)
    )


def _high_conf_recycled(row: pd.Series, policy: CascadePolicy) -> bool:
    return bool(
        row["deterministic_novelty"] == "recycled"
        and int(row["ticker_count"]) <= int(policy.recycled_max_tickers)
        and (
            bool(row["exact_title_repeat"])
            or float(row["best_combined_similarity"]) >= float(policy.recycled_min_similarity)
            or float(row["best_summary_jaccard"]) >= float(policy.recycled_min_summary_jaccard)
            or int(row["story_matches_30d"]) >= int(policy.recycled_min_story_matches)
        )
    )


def _route_reason(row: pd.Series, policy: CascadePolicy) -> str:
    if policy.enable_new and _high_conf_new(row, policy):
        return "deterministic_new"
    if policy.enable_follow_up and _high_conf_follow_up(row, policy):
        return "deterministic_follow_up"
    if policy.enable_recycled and _high_conf_recycled(row, policy):
        return "deterministic_recycled"
    return "teacher_fallback"


def _apply_policy(frame: pd.DataFrame, policy: CascadePolicy) -> pd.DataFrame:
    out = frame.copy()
    route_reason = out.apply(_route_reason, axis=1, policy=policy)
    out["policy_name"] = policy.name
    out["route_reason"] = route_reason
    out["use_deterministic"] = out["route_reason"] != "teacher_fallback"
    out["hybrid_novelty"] = np.where(out["use_deterministic"], out["deterministic_novelty"], out["teacher_novelty"])
    return out


def _reference_articles(frame: pd.DataFrame, *, mode: str) -> pd.DataFrame:
    out = frame.copy()
    if mode == "deterministic_only":
        out["policy_name"] = mode
        out["route_reason"] = "deterministic_all"
        out["use_deterministic"] = True
        out["hybrid_novelty"] = out["deterministic_novelty"]
        return out
    if mode == "teacher_oracle":
        out["policy_name"] = mode
        out["route_reason"] = "teacher_all"
        out["use_deterministic"] = False
        out["hybrid_novelty"] = out["teacher_novelty"]
        return out
    raise ValueError(f"Unknown reference mode: {mode}")


def _lookup_feature_stat(feature_df: pd.DataFrame, source_name: str, horizon: str, feature_name: str) -> dict[str, object]:
    subset = feature_df[
        (feature_df["source_name"] == source_name)
        & (feature_df["horizon"] == horizon)
        & (feature_df["feature_name"] == feature_name)
    ]
    if subset.empty:
        return {}
    return subset.iloc[0].to_dict()


def _evaluate_policy(
    frame: pd.DataFrame,
    *,
    source_name: str,
    is_hybrid_policy: bool,
    teacher_feature_results: pd.DataFrame,
) -> tuple[dict[str, object], list[dict[str, object]], pd.DataFrame]:
    full_report, _ = h329._classification_report(
        frame,
        actual_col="teacher_novelty",
        pred_col="hybrid_novelty",
    )
    holdout = frame[frame["time"].dt.year == HOLDOUT_YEAR].copy()
    holdout_report, _ = h329._classification_report(
        holdout,
        actual_col="teacher_novelty",
        pred_col="hybrid_novelty",
    )
    holdout_follow_row = next(
        (row for row in holdout_report["per_label"] if row["label"] == "follow_up"),
        {"precision": 0.0, "recall": 0.0, "f1": 0.0},
    )

    total_articles = int(len(frame))
    total_text = int(pd.to_numeric(frame["article_text_length"], errors="coerce").fillna(0).sum())
    api_articles = int((~frame["use_deterministic"]).sum())
    deterministic_articles = int(frame["use_deterministic"].sum())
    api_text = int(pd.to_numeric(frame.loc[~frame["use_deterministic"], "article_text_length"], errors="coerce").fillna(0).sum())
    deterministic_text = total_text - api_text

    panel = h329._build_novelty_panel(frame, "hybrid_novelty")
    feature_results = h329._evaluate_decay_contract(panel, source_name)

    alpha_contract_rows = []
    preserved_contracts = 0
    for horizon, feature_name in h329.KEY_ALPHA_CONTRACTS.items():
        teacher_row = _lookup_feature_stat(teacher_feature_results, "teacher_oracle", horizon, feature_name)
        policy_row = _lookup_feature_stat(feature_results, source_name, horizon, feature_name)
        teacher_ic = float(teacher_row.get("mean_ic", np.nan))
        policy_ic = float(policy_row.get("mean_ic", np.nan))
        sign_preserved = bool(
            np.isfinite(teacher_ic)
            and np.isfinite(policy_ic)
            and teacher_ic != 0.0
            and math.copysign(1.0, policy_ic) == math.copysign(1.0, teacher_ic)
        )
        if sign_preserved:
            preserved_contracts += 1
        alpha_contract_rows.append(
            {
                "policy_name": source_name,
                "horizon": horizon,
                "feature_name": feature_name,
                "teacher_mean_ic": teacher_ic,
                "policy_mean_ic": policy_ic,
                "teacher_hit_rate": teacher_row.get("daily_hit_rate"),
                "policy_hit_rate": policy_row.get("daily_hit_rate"),
                "teacher_positive_years": teacher_row.get("positive_years"),
                "policy_positive_years": policy_row.get("positive_years"),
                "sign_preserved": sign_preserved,
            }
        )

    api_article_share = float(api_articles / total_articles) if total_articles else float("nan")
    api_text_share = float(api_text / total_text) if total_text else float("nan")
    deterministic_article_share = float(deterministic_articles / total_articles) if total_articles else float("nan")
    deterministic_text_share = float(deterministic_text / total_text) if total_text else float("nan")

    if is_hybrid_policy:
        pass_condition = bool(
            preserved_contracts >= 3
            and api_article_share <= PASS_MAX_API_ARTICLE_SHARE
            and api_text_share <= PASS_MAX_API_TEXT_SHARE
            and float(holdout_follow_row["f1"]) >= PASS_FOLLOWUP_F1
        )
        mixed_condition = bool(
            (
                preserved_contracts >= 3
                and api_article_share <= MIXED_MAX_API_ARTICLE_SHARE
                and api_text_share <= MIXED_MAX_API_TEXT_SHARE
            )
            or (
                preserved_contracts >= 2
                and api_article_share <= PASS_MAX_API_ARTICLE_SHARE
                and api_text_share <= PASS_MAX_API_TEXT_SHARE
            )
        )
        verdict = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    else:
        verdict = "REFERENCE"

    summary_row = {
        "policy_name": source_name,
        "policy_kind": "hybrid" if is_hybrid_policy else "reference",
        "verdict": verdict,
        "article_rows": total_articles,
        "api_articles": api_articles,
        "deterministic_articles": deterministic_articles,
        "api_article_share": api_article_share,
        "deterministic_article_share": deterministic_article_share,
        "api_text_length": api_text,
        "deterministic_text_length": deterministic_text,
        "api_text_share": api_text_share,
        "deterministic_text_share": deterministic_text_share,
        "holdout_macro_f1": float(holdout_report["macro_f1"]),
        "holdout_accuracy": float(holdout_report["accuracy"]),
        "holdout_balanced_accuracy": float(holdout_report["balanced_accuracy"]),
        "holdout_follow_up_precision": float(holdout_follow_row["precision"]),
        "holdout_follow_up_recall": float(holdout_follow_row["recall"]),
        "holdout_follow_up_f1": float(holdout_follow_row["f1"]),
        "full_macro_f1": float(full_report["macro_f1"]),
        "full_accuracy": float(full_report["accuracy"]),
        "full_balanced_accuracy": float(full_report["balanced_accuracy"]),
        "preserved_alpha_contracts": int(preserved_contracts),
    }
    return summary_row, alpha_contract_rows, feature_results


def main() -> None:
    teacher_articles = _attach_text_lengths(h329.load_teacher_articles())
    distilled_articles = h329.assign_deterministic_novelty(teacher_articles)
    distilled_articles["article_text_length"] = teacher_articles["article_text_length"].to_numpy()

    reference_frames = {
        "teacher_oracle": _reference_articles(distilled_articles, mode="teacher_oracle"),
        "deterministic_only": _reference_articles(distilled_articles, mode="deterministic_only"),
    }

    summary_rows: list[dict[str, object]] = []
    alpha_contract_rows: list[dict[str, object]] = []
    feature_frames: list[pd.DataFrame] = []
    route_frames: list[pd.DataFrame] = []

    teacher_features = h329._evaluate_decay_contract(
        h329._build_novelty_panel(reference_frames["teacher_oracle"], "hybrid_novelty"),
        "teacher_oracle",
    )
    teacher_summary, _, _ = _evaluate_policy(
        reference_frames["teacher_oracle"],
        source_name="teacher_oracle",
        is_hybrid_policy=False,
        teacher_feature_results=teacher_features,
    )
    summary_rows.append(teacher_summary)
    alpha_contract_rows.extend(
        [
            {
                "policy_name": "teacher_oracle",
                "horizon": horizon,
                "feature_name": feature_name,
                "teacher_mean_ic": float(
                    _lookup_feature_stat(teacher_features, "teacher_oracle", horizon, feature_name).get("mean_ic", np.nan)
                ),
                "policy_mean_ic": float(
                    _lookup_feature_stat(teacher_features, "teacher_oracle", horizon, feature_name).get("mean_ic", np.nan)
                ),
                "teacher_hit_rate": _lookup_feature_stat(teacher_features, "teacher_oracle", horizon, feature_name).get(
                    "daily_hit_rate"
                ),
                "policy_hit_rate": _lookup_feature_stat(teacher_features, "teacher_oracle", horizon, feature_name).get(
                    "daily_hit_rate"
                ),
                "teacher_positive_years": _lookup_feature_stat(
                    teacher_features, "teacher_oracle", horizon, feature_name
                ).get("positive_years"),
                "policy_positive_years": _lookup_feature_stat(
                    teacher_features, "teacher_oracle", horizon, feature_name
                ).get("positive_years"),
                "sign_preserved": True,
            }
            for horizon, feature_name in h329.KEY_ALPHA_CONTRACTS.items()
        ]
    )
    feature_frames.append(teacher_features)

    deterministic_summary, deterministic_alpha_rows, deterministic_features = _evaluate_policy(
        reference_frames["deterministic_only"],
        source_name="deterministic_only",
        is_hybrid_policy=False,
        teacher_feature_results=teacher_features,
    )
    summary_rows.append(deterministic_summary)
    alpha_contract_rows.extend(deterministic_alpha_rows)
    feature_frames.append(deterministic_features)

    for policy in POLICIES:
        routed = _apply_policy(distilled_articles, policy)
        route_frames.append(
            routed[
                [
                    "policy_name",
                    "time",
                    "article_id",
                    "tickers_joined",
                    "ticker_count",
                    "teacher_novelty",
                    "deterministic_novelty",
                    "hybrid_novelty",
                    "route_reason",
                    "use_deterministic",
                    "article_text_length",
                    "best_combined_similarity",
                    "best_summary_jaccard",
                    "best_story_gap_days",
                    "recent_story_matches_7d",
                    "story_matches_30d",
                    "exact_title_repeat",
                    "title",
                ]
            ].copy()
        )
        summary_row, policy_alpha_rows, policy_features = _evaluate_policy(
            routed,
            source_name=policy.name,
            is_hybrid_policy=True,
            teacher_feature_results=teacher_features,
        )
        summary_row["policy_description"] = policy.description
        summary_rows.append(summary_row)
        alpha_contract_rows.extend(policy_alpha_rows)
        feature_frames.append(policy_features)

    summary_df = pd.DataFrame(summary_rows)
    alpha_contract_df = pd.DataFrame(alpha_contract_rows)
    feature_results = pd.concat(feature_frames, ignore_index=True)
    route_df = pd.concat(route_frames, ignore_index=True)

    deterministic_row = summary_df.loc[summary_df["policy_name"] == "deterministic_only"].iloc[0]
    for column in ["holdout_macro_f1", "holdout_follow_up_f1", "preserved_alpha_contracts"]:
        summary_df[f"{column}_delta_vs_deterministic"] = pd.to_numeric(summary_df[column], errors="coerce") - float(
            deterministic_row[column]
        )

    hybrid_rows = summary_df[summary_df["policy_kind"] == "hybrid"].copy()
    hybrid_rows = hybrid_rows.sort_values(
        by=[
            "preserved_alpha_contracts",
            "api_text_share",
            "api_article_share",
            "holdout_follow_up_f1",
            "holdout_macro_f1",
        ],
        ascending=[False, True, True, False, False],
        ignore_index=True,
    )
    if hybrid_rows.empty:
        raise RuntimeError("No hybrid rows were evaluated")
    best_policy_row = hybrid_rows.iloc[0].to_dict()
    verdict = str(best_policy_row["verdict"])

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = OUT_DIR / f"{ts}_h330_hybrid_news_cascade_policy_summary.parquet"
    contracts_path = OUT_DIR / f"{ts}_h330_hybrid_news_cascade_alpha_contracts.parquet"
    routes_path = OUT_DIR / f"{ts}_h330_hybrid_news_cascade_routes.parquet"
    feature_path = OUT_DIR / f"{ts}_h330_hybrid_news_cascade_feature_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_h330_hybrid_news_cascade_audit_details.json"

    summary_df.to_parquet(summary_path, index=False)
    alpha_contract_df.to_parquet(contracts_path, index=False)
    route_df.to_parquet(routes_path, index=False)
    feature_results.to_parquet(feature_path, index=False)

    summary = {
        "verdict": verdict,
        "best_policy": _json_safe(best_policy_row),
        "teacher_window": {
            "date_min": _json_safe(teacher_articles["time"].min()),
            "date_max": _json_safe(teacher_articles["time"].max()),
            "article_rows": int(len(teacher_articles)),
            "days": int(teacher_articles["time"].nunique()),
        },
        "references": {
            "teacher_oracle": _json_safe(summary_df.loc[summary_df["policy_name"] == "teacher_oracle"].iloc[0].to_dict()),
            "deterministic_only": _json_safe(
                summary_df.loc[summary_df["policy_name"] == "deterministic_only"].iloc[0].to_dict()
            ),
        },
        "hybrid_policies": _json_safe(hybrid_rows.to_dict(orient="records")),
        "alpha_contract_rows": _json_safe(alpha_contract_df.to_dict(orient="records")),
        "policy_specs": [_json_safe(policy.__dict__) for policy in POLICIES],
        "artifacts": {
            "policy_summary": str(summary_path.relative_to(ROOT)),
            "alpha_contracts": str(contracts_path.relative_to(ROOT)),
            "routes": str(routes_path.relative_to(ROOT)),
            "feature_results": str(feature_path.relative_to(ROOT)),
        },
    }
    details_path.write_text(json.dumps(_json_safe(summary), indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_hybrid_news_cascade_audit",
        name="h330_hybrid_news_cascade_audit",
        summary=summary,
        artifacts={
            "policy_summary": str(summary_path),
            "alpha_contracts": str(contracts_path),
            "routes": str(routes_path),
            "feature_results": str(feature_path),
            "details": str(details_path),
        },
        metadata={
            "session": 149,
            "holdout_year": HOLDOUT_YEAR,
            "policy_names": [policy.name for policy in POLICIES],
        },
    )

    print("H330 HYBRID NEWS CASCADE AUDIT")
    print(f"Verdict: {verdict}")
    print("Best hybrid policy:", best_policy_row["policy_name"])
    print(
        "Best policy preserved contracts / api article share / api text share:",
        f"{int(best_policy_row['preserved_alpha_contracts'])} / "
        f"{float(best_policy_row['api_article_share']):.4f} / "
        f"{float(best_policy_row['api_text_share']):.4f}",
    )
    print(
        "Best policy holdout follow_up precision / recall / f1:",
        f"{float(best_policy_row['holdout_follow_up_precision']):.4f} / "
        f"{float(best_policy_row['holdout_follow_up_recall']):.4f} / "
        f"{float(best_policy_row['holdout_follow_up_f1']):.4f}",
    )
    print(hybrid_rows.to_string(index=False))


if __name__ == "__main__":
    main()
