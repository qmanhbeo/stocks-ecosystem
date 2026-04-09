"""
H323: policy-beneficiary graph pilot.

Question:
    Can a tiny, explicit political-economy beneficiary map turn raw CafeF
    public-investment / infrastructure policy news into a tradable sector
    response, without using the unfinished LLM cache?

Design:
    - scan raw CafeF titles/summaries for predeclared public-investment and
      infrastructure-project terms
    - assign weekend/holiday articles to the next trading day
    - predeclare direct beneficiaries as Construction & Materials names
    - compare direct beneficiaries against the rest of the universe on high
      policy-intensity days, using both 1d barrier `actual` and 5d relative
      forward return
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.future_return_research import load_future_rel_5d  # noqa: E402
from src.news_event_source_research import iter_news_archive_paths  # noqa: E402
from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


RAW_NEWS_DIR = data_path("news/cafef/raw")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
SECTOR_PATH = data_path("features/sector_classification.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"

THEME_PATTERNS = {
    "core_public_investment": (
        r"\bdau tu cong\b",
        r"\bvon dau tu cong\b",
        r"\bgiai ngan dau tu cong\b",
        r"\bgiai ngan von dau tu cong\b",
    ),
    "transport_infrastructure": (
        r"\bcao toc\b",
        r"\bcao toc bac nam\b",
        r"\bduong vanh dai\b",
        r"\bvanh dai\b",
        r"\bsan bay long thanh\b",
        r"\blong thanh\b",
        r"\bmetro\b",
        r"\bduong sat\b",
        r"\bha tang giao thong\b",
        r"\bdu an giao thong\b",
    ),
}

STATE_SPECS = (
    {
        "state_name": "core_public_investment_1d_high",
        "score_col": "core_public_investment_count_1d",
        "beneficiary_group": "direct_public_works",
        "control_group": "rest",
        "note": "High same-day core public-investment article count",
    },
    {
        "state_name": "transport_infrastructure_1d_high",
        "score_col": "transport_infrastructure_count_1d",
        "beneficiary_group": "direct_public_works",
        "control_group": "rest",
        "note": "High same-day infrastructure-project article count",
    },
    {
        "state_name": "policy_total_5d_high",
        "score_col": "policy_total_count_5d",
        "beneficiary_group": "direct_public_works",
        "control_group": "rest",
        "note": "High 5d combined public-investment / infrastructure article count",
    },
    {
        "state_name": "policy_total_1d_high",
        "score_col": "policy_total_count_1d",
        "beneficiary_group": "direct_public_works",
        "control_group": "rest",
        "note": "High same-day combined public-investment / infrastructure article count",
    },
)

GROUP_ORDER = ("direct_public_works", "second_order_real_estate", "rest")
PASS_MIN_ACTIVE_DAYS = 35
PASS_MIN_FWD5_ACTIVE_EDGE = 0.001
PASS_MIN_FWD5_DID = 0.001
PASS_MIN_ACTUAL_DID = 0.005
MIXED_MIN_ACTIVE_DAYS = 25
MIXED_MIN_FWD5_DID = 0.0


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _fold_text(value: object) -> str:
    text = str(value or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


COMPILED_PATTERNS = {
    theme: tuple(re.compile(pattern) for pattern in patterns)
    for theme, patterns in THEME_PATTERNS.items()
}


def _article_themes(title: str, summary: str) -> list[str]:
    text = _fold_text(f"{title} {summary}")
    themes = [
        theme
        for theme, patterns in COMPILED_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]
    return themes


def _next_trading_day(article_day: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    if pd.isna(article_day):
        return None
    pos = trading_days.searchsorted(pd.Timestamp(article_day).normalize(), side="left")
    if pos >= len(trading_days):
        return None
    return pd.Timestamp(trading_days[pos])


def _scan_policy_articles(trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in iter_news_archive_paths(RAW_NEWS_DIR, start_date=START_DATE, end_date=END_DATE):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    article = json.loads(line)
                except json.JSONDecodeError:
                    continue
                title = str(article.get("title", "") or "")
                summary = str(article.get("summary", "") or "")
                themes = _article_themes(title, summary)
                if not themes:
                    continue
                published_at = pd.to_datetime(article.get("published_at"), errors="coerce", utc=True)
                if pd.isna(published_at):
                    continue
                local_ts = published_at.tz_convert(None)
                article_day = local_ts.normalize()
                signal_day = _next_trading_day(article_day, trading_days)
                if signal_day is None or signal_day.year < 2023 or signal_day.year > 2025:
                    continue
                article_id = str(article.get("article_id", "") or "").strip() or f"{path.stem}:{title[:40]}"
                for theme in themes:
                    rows.append(
                        {
                            "article_id": article_id,
                            "published_at": local_ts,
                            "article_day": article_day,
                            "time": signal_day,
                            "theme": theme,
                            "title": title,
                            "url": str(article.get("url", "") or ""),
                        }
                    )
    if not rows:
        return pd.DataFrame(
            columns=["article_id", "published_at", "article_day", "time", "theme", "title", "url"]
        )
    return pd.DataFrame(rows).drop_duplicates(["article_id", "theme"]).sort_values(["time", "article_id", "theme"])


def _build_policy_daily(policy_articles: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    daily = pd.DataFrame({"time": trading_days})
    if policy_articles.empty:
        for theme in THEME_PATTERNS:
            daily[f"{theme}_count_1d"] = 0
        daily["policy_total_count_1d"] = 0
    else:
        counts = (
            policy_articles.groupby(["time", "theme"], as_index=False)["article_id"]
            .nunique()
            .pivot_table(index="time", columns="theme", values="article_id", fill_value=0)
            .reset_index()
        )
        counts.columns.name = None
        daily = daily.merge(counts, on="time", how="left")
        for theme in THEME_PATTERNS:
            if theme not in daily.columns:
                daily[theme] = 0
            daily[f"{theme}_count_1d"] = pd.to_numeric(daily[theme], errors="coerce").fillna(0).astype(int)
        daily = daily.drop(columns=[theme for theme in THEME_PATTERNS if theme in daily.columns], errors="ignore")
        daily["policy_total_count_1d"] = daily[[f"{theme}_count_1d" for theme in THEME_PATTERNS]].sum(axis=1)

    count_cols = [c for c in daily.columns if c.endswith("_count_1d")]
    for col in count_cols:
        daily[col.replace("_count_1d", "_count_5d")] = (
            pd.to_numeric(daily[col], errors="coerce").fillna(0.0).rolling(5, min_periods=1).sum()
        )
    return daily.sort_values("time").reset_index(drop=True)


def _load_sector_groups() -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_PATH).rename(columns={"symbol": "ticker"}).copy()
    sector["ticker"] = sector["ticker"].astype(str).str.upper()
    for col in ("icb_name2", "icb_name3", "icb_name4"):
        sector[col] = sector[col].fillna("").astype(str)
    sector["beneficiary_group"] = "rest"
    direct_mask = sector["icb_name2"].eq("Xây dựng và Vật liệu")
    second_mask = sector["icb_name2"].eq("Bất động sản")
    sector.loc[second_mask, "beneficiary_group"] = "second_order_real_estate"
    sector.loc[direct_mask, "beneficiary_group"] = "direct_public_works"
    return sector[["ticker", "icb_name2", "icb_name3", "icb_name4", "beneficiary_group"]].drop_duplicates("ticker")


def _load_target_panel() -> pd.DataFrame:
    matrix = pd.read_parquet(MATRIX_PATH, columns=["time", "ticker", "actual"]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix = matrix.loc[matrix["time"].dt.year.between(2023, 2025)].copy()
    fwd5 = load_future_rel_5d(start_year=2023, end_year=2025)
    fwd5["ticker"] = fwd5["ticker"].astype(str).str.upper()
    sector = _load_sector_groups()
    panel = (
        matrix.merge(fwd5, on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(sector, on="ticker", how="left", validate="many_to_one")
    )
    panel["beneficiary_group"] = panel["beneficiary_group"].fillna("rest")
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _build_daily_group_panel(target_panel: pd.DataFrame, policy_daily: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        target_panel.groupby(["time", "beneficiary_group"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            actual_mean=("actual", "mean"),
            fwd5_mean=("fwd_rel_5d", "mean"),
            actual_hit_rate=("actual", lambda s: float((pd.to_numeric(s, errors="coerce") > 0.0).mean())),
        )
        .sort_values(["time", "beneficiary_group"])
    )
    wide = grouped.pivot(index="time", columns="beneficiary_group", values=["tickers", "actual_mean", "fwd5_mean", "actual_hit_rate"])
    wide.columns = [f"{metric}__{group}" for metric, group in wide.columns]
    wide = wide.reset_index()
    for group in GROUP_ORDER:
        for metric in ("tickers", "actual_mean", "fwd5_mean", "actual_hit_rate"):
            col = f"{metric}__{group}"
            if col not in wide.columns:
                wide[col] = np.nan
    for group in ("direct_public_works", "second_order_real_estate"):
        wide[f"actual_edge__{group}_vs_rest"] = wide[f"actual_mean__{group}"] - wide["actual_mean__rest"]
        wide[f"fwd5_edge__{group}_vs_rest"] = wide[f"fwd5_mean__{group}"] - wide["fwd5_mean__rest"]
    return wide.merge(policy_daily, on="time", how="left", validate="one_to_one").sort_values("time").reset_index(drop=True)


def _dev_threshold(frame: pd.DataFrame, score_col: str) -> float:
    dev = frame.loc[phase_mask(frame, "dev", protocol=PROTOCOL), score_col].dropna()
    if dev.empty:
        return 0.0
    threshold = float(dev.quantile(0.80))
    return max(threshold, 1.0)


def _safe_spearman(left: pd.Series, right: pd.Series) -> float | None:
    clean = (
        pd.concat([left.rename("left"), right.rename("right")], axis=1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(clean) < 20 or clean["left"].nunique() < 2 or clean["right"].nunique() < 2:
        return None
    rho = spearmanr(clean["left"], clean["right"]).statistic
    if not np.isfinite(rho):
        return None
    return float(np.asarray(rho).flat[0])


def _phase_stats(frame: pd.DataFrame, spec: dict[str, str], phase: str, threshold: float) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    score_col = spec["score_col"]
    group = spec["beneficiary_group"]
    state = pd.to_numeric(scoped[score_col], errors="coerce").fillna(0.0) >= threshold
    active = scoped.loc[state].copy()
    inactive = scoped.loc[~state].copy()

    actual_edge = f"actual_edge__{group}_vs_rest"
    fwd5_edge = f"fwd5_edge__{group}_vs_rest"
    active_actual = _safe_float(active[actual_edge].mean()) if not active.empty else None
    inactive_actual = _safe_float(inactive[actual_edge].mean()) if not inactive.empty else None
    active_fwd5 = _safe_float(active[fwd5_edge].mean()) if not active.empty else None
    inactive_fwd5 = _safe_float(inactive[fwd5_edge].mean()) if not inactive.empty else None
    active_second_fwd5 = _safe_float(active["fwd5_edge__second_order_real_estate_vs_rest"].mean()) if not active.empty else None
    active_second_actual = _safe_float(active["actual_edge__second_order_real_estate_vs_rest"].mean()) if not active.empty else None
    return {
        "rows": int(len(scoped)),
        "active_days": int(state.sum()),
        "active_score_mean": _safe_float(active[score_col].mean()) if not active.empty else None,
        "active_direct_actual_edge": active_actual,
        "inactive_direct_actual_edge": inactive_actual,
        "actual_did": None if active_actual is None or inactive_actual is None else float(active_actual - inactive_actual),
        "active_direct_fwd5_edge": active_fwd5,
        "inactive_direct_fwd5_edge": inactive_fwd5,
        "fwd5_did": None if active_fwd5 is None or inactive_fwd5 is None else float(active_fwd5 - inactive_fwd5),
        "active_second_order_actual_edge": active_second_actual,
        "active_second_order_fwd5_edge": active_second_fwd5,
        "direct_minus_second_order_fwd5": None
        if active_fwd5 is None or active_second_fwd5 is None
        else float(active_fwd5 - active_second_fwd5),
        "rho_score_direct_fwd5_edge": _safe_spearman(scoped[score_col], scoped[fwd5_edge]),
        "rho_score_direct_actual_edge": _safe_spearman(scoped[score_col], scoped[actual_edge]),
    }


def _evaluate(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spec in STATE_SPECS:
        threshold = _dev_threshold(daily, spec["score_col"])
        row: dict[str, object] = {
            "state_name": spec["state_name"],
            "score_col": spec["score_col"],
            "beneficiary_group": spec["beneficiary_group"],
            "control_group": spec["control_group"],
            "note": spec["note"],
            "dev_q80_threshold": threshold,
        }
        for phase in ("dev", "validation", "confirmation"):
            stats = _phase_stats(daily, spec, phase, threshold)
            for key, value in stats.items():
                row[f"{phase}_{key}"] = value
        val_days = int(row["validation_active_days"] or 0)
        conf_days = int(row["confirmation_active_days"] or 0)
        val_fwd = _safe_float(row["validation_active_direct_fwd5_edge"]) or 0.0
        conf_fwd = _safe_float(row["confirmation_active_direct_fwd5_edge"]) or 0.0
        val_did = _safe_float(row["validation_fwd5_did"]) or 0.0
        conf_did = _safe_float(row["confirmation_fwd5_did"]) or 0.0
        val_actual_did = _safe_float(row["validation_actual_did"]) or 0.0
        conf_actual_did = _safe_float(row["confirmation_actual_did"]) or 0.0
        val_vs_second = _safe_float(row["validation_direct_minus_second_order_fwd5"]) or 0.0
        conf_vs_second = _safe_float(row["confirmation_direct_minus_second_order_fwd5"]) or 0.0

        pass_condition = bool(
            val_days >= PASS_MIN_ACTIVE_DAYS
            and conf_days >= PASS_MIN_ACTIVE_DAYS
            and val_fwd >= PASS_MIN_FWD5_ACTIVE_EDGE
            and conf_fwd >= PASS_MIN_FWD5_ACTIVE_EDGE
            and val_did >= PASS_MIN_FWD5_DID
            and conf_did >= PASS_MIN_FWD5_DID
            and val_actual_did >= PASS_MIN_ACTUAL_DID
            and conf_actual_did >= PASS_MIN_ACTUAL_DID
            and val_vs_second >= 0.0
            and conf_vs_second >= 0.0
        )
        mixed_condition = bool(
            not pass_condition
            and val_days >= MIXED_MIN_ACTIVE_DAYS
            and conf_days >= MIXED_MIN_ACTIVE_DAYS
            and val_did >= MIXED_MIN_FWD5_DID
            and conf_did >= MIXED_MIN_FWD5_DID
            and (val_fwd > 0.0 or conf_fwd > 0.0)
        )
        row["candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    target_panel = _load_target_panel()
    trading_days = pd.DatetimeIndex(sorted(target_panel["time"].dropna().unique()))
    policy_articles = _scan_policy_articles(trading_days)
    policy_daily = _build_policy_daily(policy_articles, trading_days)
    daily = _build_daily_group_panel(target_panel, policy_daily)
    results = _evaluate(daily)

    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2}
    ranked = results.copy()
    ranked["decision_rank"] = ranked["candidate_decision"].map(decision_rank).fillna(9)
    ranked["score"] = (
        pd.to_numeric(ranked["validation_fwd5_did"], errors="coerce").fillna(-9.0)
        + pd.to_numeric(ranked["confirmation_fwd5_did"], errors="coerce").fillna(-9.0)
    )
    best = ranked.sort_values(["decision_rank", "score"], ascending=[True, False]).iloc[0]

    if (results["candidate_decision"] == "PASSED").any():
        verdict = "PASSED"
        branch_decision = (
            "The public-investment beneficiary map produced a stable direct-beneficiary response. "
            "Advance to a sharper policy-theme graph or source-expansion follow-up."
        )
    elif (results["candidate_decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "The local CafeF policy corpus is usable and shows some beneficiary-state structure, "
            "but the direct public-works response is too weak or unstable to promote."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The manually mapped public-investment policy graph does not produce a stable direct-beneficiary "
            "response on the current CafeF title corpus. Park the branch unless a better policy corpus arrives."
        )

    article_path = OUT_DIR / f"{ts}_h323_policy_beneficiary_graph_articles.parquet"
    daily_path = OUT_DIR / f"{ts}_h323_policy_beneficiary_graph_daily.parquet"
    results_path = OUT_DIR / f"{ts}_h323_policy_beneficiary_graph_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_policy_beneficiary_graph_details.json"
    policy_articles.to_parquet(article_path, index=False)
    daily.to_parquet(daily_path, index=False)
    results.to_parquet(results_path, index=False)

    group_counts = (
        target_panel[["ticker", "beneficiary_group"]]
        .drop_duplicates()
        .groupby("beneficiary_group")["ticker"]
        .nunique()
        .to_dict()
    )
    article_summary = {
        "policy_article_theme_rows": int(len(policy_articles)),
        "unique_policy_articles": int(policy_articles["article_id"].nunique()) if not policy_articles.empty else 0,
        "policy_signal_days": int(policy_articles["time"].nunique()) if not policy_articles.empty else 0,
        "theme_article_rows": policy_articles.groupby("theme")["article_id"].nunique().to_dict()
        if not policy_articles.empty
        else {},
    }
    details = {
        "branch_decision": branch_decision,
        "article_summary": article_summary,
        "group_counts": {str(k): int(v) for k, v in group_counts.items()},
        "best_state": _json_safe(best.to_dict()),
        "results": _json_safe(results.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "best_state": best["state_name"],
        "best_state_decision": best["candidate_decision"],
        "best_validation_active_days": int(best["validation_active_days"]),
        "best_confirmation_active_days": int(best["confirmation_active_days"]),
        "best_validation_active_direct_fwd5_edge": _safe_float(best["validation_active_direct_fwd5_edge"]),
        "best_confirmation_active_direct_fwd5_edge": _safe_float(best["confirmation_active_direct_fwd5_edge"]),
        "best_validation_fwd5_did": _safe_float(best["validation_fwd5_did"]),
        "best_confirmation_fwd5_did": _safe_float(best["confirmation_fwd5_did"]),
        "best_validation_actual_did": _safe_float(best["validation_actual_did"]),
        "best_confirmation_actual_did": _safe_float(best["confirmation_actual_did"]),
        "policy_unique_articles": article_summary["unique_policy_articles"],
        "policy_signal_days": article_summary["policy_signal_days"],
        "group_counts": {str(k): int(v) for k, v in group_counts.items()},
    }
    artifacts = {
        "policy_articles": article_path,
        "daily_panel": daily_path,
        "results": results_path,
        "details": details_path,
    }
    metadata = {
        "question": "Can a tiny public-investment policy-event corpus and beneficiary map predict direct public-works beneficiaries?",
        "protocol": {"dev": "2023", "validation": "2024", "confirmation": "2025"},
        "theme_patterns": THEME_PATTERNS,
        "beneficiary_map": {
            "direct_public_works": "icb_name2 == 'Xây dựng và Vật liệu'",
            "second_order_real_estate": "icb_name2 == 'Bất động sản'",
            "rest": "all other mapped or unmapped tickers",
        },
        "note": "CafeF articles are assigned to the first trading day on or after their published date.",
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_policy_beneficiary_graph",
        name="h323_policy_beneficiary_graph",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
