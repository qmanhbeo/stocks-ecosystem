"""
H308: stock-local predictability atlas.

Question:
    Does an all-HOSE stock-local atlas reveal a non-random, stable tail of
    recipient stocks worth deeper interrogation after null control and
    multiple-testing discipline, or does the apparent per-ticker structure stay
    too weak to justify reopening stock-local alpha hunting?

Smallest honest test:
    Freeze the canonical S1/H93 surface, build a top-5 recipient panel, then:
      1. measure per-ticker recipient edge in dev / validation / confirmation
      2. compare the dev->validation rank stability against a within-day
         permutation null that keeps S1 selection dates fixed
      3. estimate empirical p-values for each ticker's min(dev, validation)
         recipient edge under that null
      4. apply BH-style multiple-testing control
      5. inspect whether any surviving nominal tail has coherent local-structure
         diagnostics rather than just random positive noise

Decision rule:
    PASSED:
      - dev->validation rank stability beats the 95th percentile of the null
      - at least 5 tickers survive q <= 0.10 and keep positive confirmation
        edge
    MIXED:
      - pass bar fails
      - but a nominal tail (empirical p <= 0.10 with positive confirmation)
        still exists
      - and that nominal tail lines up with at least two coherent local
        diagnostics instead of random walk-like noise
    FAILED:
      - no null-controlled stable tail survives
      - and the atlas does not leave behind a coherent recurrent-recipient
        diagnostic line
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import STOCK_DIR, load_s1_frame


TOP_N = 5
START_YEAR = 2015
END_YEAR = 2025
DEV_END_YEAR = 2022
VAL_END_YEAR = 2024

MIN_DEV_DAYS = 20
MIN_VAL_DAYS = 10
MIN_CONF_DAYS = 5
N_PERM = 200
FDR_ALPHA = 0.10
RANK_STABILITY_ALPHA = 0.05
NOMINAL_P_ALPHA = 0.10
MIN_PASS_FDR_TAIL = 5
MIN_MIXED_NOMINAL_TAIL = 5

DIAGNOSTIC_SPECS = (
    ("dev_ret_autocorr_1d", "Lag-1 close-to-close autocorrelation", "neutral"),
    ("dev_variance_ratio_5d", "Variance ratio over 5d versus 1d", "neutral"),
    ("dev_overnight_share_abs", "Share of absolute move coming from overnight gap", "lower"),
    ("dev_zero_range_rate", "Fraction of dev days with zero daily range", "lower"),
    ("dev_median_value_bn", "Median daily traded value in bn VND", "higher"),
)

STRUCTURAL_MIXED_RULES = (
    ("dev_overnight_share_abs", "lower", -0.25),
    ("dev_zero_range_rate", "lower", -0.25),
    ("dev_median_value_bn", "higher", 0.25),
)

OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"


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


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _phase_name(ts: pd.Timestamp) -> str:
    year = int(ts.year)
    if year <= DEV_END_YEAR:
        return "dev"
    if year <= VAL_END_YEAR:
        return "validation"
    return "confirmation"


def _phase_code(ts: pd.Timestamp) -> int:
    phase = _phase_name(ts)
    return {"dev": 0, "validation": 1, "confirmation": 2}[phase]


def load_selected_panel() -> pd.DataFrame:
    s1 = load_s1_frame()[["time", "ticker", "xs_proba", "actual"]].copy()
    s1 = s1.loc[s1["time"].dt.year.between(START_YEAR, END_YEAR)].copy()

    rows: list[pd.DataFrame] = []
    for date, day in s1.groupby("time", sort=True):
        day = day.replace([np.inf, -np.inf], np.nan).dropna()
        if len(day) < TOP_N:
            continue
        baseline = float(day["actual"].mean())
        top = day.nlargest(TOP_N, "xs_proba").copy()
        top["selection_edge"] = top["actual"] - baseline
        top["phase_name"] = _phase_name(pd.Timestamp(date))
        top["phase_code"] = _phase_code(pd.Timestamp(date))
        rows.append(top[["time", "ticker", "xs_proba", "actual", "selection_edge", "phase_name", "phase_code"]])
    if not rows:
        return pd.DataFrame(
            columns=["time", "ticker", "xs_proba", "actual", "selection_edge", "phase_name", "phase_code"]
        )
    return pd.concat(rows, ignore_index=True)


def _build_observed_atlas(selected: pd.DataFrame) -> pd.DataFrame:
    stats = (
        selected.groupby(["ticker", "phase_name"])["selection_edge"]
        .agg(["mean", "count"])
        .reset_index()
    )
    edge_wide = stats.pivot(index="ticker", columns="phase_name", values="mean")
    count_wide = stats.pivot(index="ticker", columns="phase_name", values="count").fillna(0)

    tickers = sorted(set(edge_wide.index.astype(str)) | set(count_wide.index.astype(str)))
    atlas = pd.DataFrame({"ticker": tickers}).set_index("ticker")
    for phase in ("dev", "validation", "confirmation"):
        edge_series = edge_wide.get(phase)
        count_series = count_wide.get(phase)
        atlas[f"{phase}_edge"] = (
            edge_series.reindex(atlas.index).astype(float) if edge_series is not None else np.nan
        )
        atlas[f"{phase}_days"] = (
            count_series.reindex(atlas.index).astype(float) if count_series is not None else 0.0
        )
    atlas = atlas.reset_index()
    for phase in ("dev", "validation", "confirmation"):
        atlas[f"{phase}_days"] = pd.to_numeric(atlas[f"{phase}_days"], errors="coerce").fillna(0).astype(int)
    atlas["qualified"] = (
        (atlas["dev_days"] >= MIN_DEV_DAYS)
        & (atlas["validation_days"] >= MIN_VAL_DAYS)
        & (atlas["confirmation_days"] >= MIN_CONF_DAYS)
    )
    atlas["stable_dev_val"] = atlas["qualified"] & (atlas["dev_edge"] > 0.0) & (atlas["validation_edge"] > 0.0)
    atlas["stable_all"] = atlas["stable_dev_val"] & (atlas["confirmation_edge"] > 0.0)
    atlas["min_dev_val_edge"] = atlas[["dev_edge", "validation_edge"]].min(axis=1)
    atlas["avg_dev_val_edge"] = atlas[["dev_edge", "validation_edge"]].mean(axis=1)
    return atlas


def _bh_qvalues(p_values: pd.Series) -> pd.Series:
    values = pd.to_numeric(p_values, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)
    valid = np.isfinite(values)
    if not valid.any():
        return pd.Series(out, index=p_values.index, dtype=float)
    valid_values = values[valid]
    order = np.argsort(valid_values)
    ranked = valid_values[order]
    m = float(len(ranked))
    raw = ranked * m / np.arange(1.0, m + 1.0)
    adjusted = np.minimum.accumulate(raw[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    restored = np.empty_like(adjusted)
    restored[order] = adjusted
    out[np.where(valid)[0]] = restored
    return pd.Series(out, index=p_values.index, dtype=float)


def _build_null_outputs(selected: pd.DataFrame, atlas: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    work = selected.sort_values(["time", "ticker"]).reset_index(drop=True).copy()
    work["day_id"] = pd.factorize(work["time"], sort=True)[0]

    tickers = atlas["ticker"].astype(str).tolist()
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(tickers)}
    work["ticker_idx"] = work["ticker"].map(ticker_to_idx).astype(int)

    ticker_idx = work["ticker_idx"].to_numpy(dtype=int)
    phase_code = pd.to_numeric(work["phase_code"], errors="coerce").astype(int).to_numpy()
    observed_edge = pd.to_numeric(work["selection_edge"], errors="coerce").astype(float).to_numpy()

    counts = np.zeros((len(tickers), 3), dtype=int)
    np.add.at(counts, (ticker_idx, phase_code), 1)
    observed_sums = np.zeros((len(tickers), 3), dtype=float)
    np.add.at(observed_sums, (ticker_idx, phase_code), observed_edge)
    observed_means = observed_sums / np.where(counts == 0, np.nan, counts)

    qualified_mask = atlas["qualified"].fillna(False).to_numpy(dtype=bool)
    qualified_idx = np.flatnonzero(qualified_mask)
    observed_rank_corr = (
        float(spearmanr(observed_means[qualified_idx, 0], observed_means[qualified_idx, 1]).statistic)
        if len(qualified_idx) >= 5
        else None
    )

    observed_min_edge = atlas["min_dev_val_edge"].to_numpy(dtype=float)
    perm_ge = np.zeros(len(tickers), dtype=int)
    null_rank_corrs: list[float] = []

    day_bounds: list[tuple[int, int]] = []
    start = 0
    for _, day_rows in work.groupby("day_id", sort=True):
        stop = start + len(day_rows)
        day_bounds.append((start, stop))
        start = stop

    rng = np.random.default_rng(0)
    for _ in range(N_PERM):
        perm_edge = observed_edge.copy()
        for left, right in day_bounds:
            perm_edge[left:right] = rng.permutation(perm_edge[left:right])

        perm_sums = np.zeros((len(tickers), 3), dtype=float)
        np.add.at(perm_sums, (ticker_idx, phase_code), perm_edge)
        perm_means = perm_sums / np.where(counts == 0, np.nan, counts)

        perm_min = np.full(len(tickers), np.nan, dtype=float)
        valid_pair = np.isfinite(perm_means[:, 0]) & np.isfinite(perm_means[:, 1])
        perm_min[valid_pair] = np.minimum(perm_means[valid_pair, 0], perm_means[valid_pair, 1])
        valid_perm_min = np.isfinite(perm_min) & np.isfinite(observed_min_edge)
        perm_ge[valid_perm_min] += (perm_min[valid_perm_min] >= observed_min_edge[valid_perm_min]).astype(int)

        if len(qualified_idx) >= 5:
            stat = spearmanr(perm_means[qualified_idx, 0], perm_means[qualified_idx, 1]).statistic
            null_rank_corrs.append(float(stat))

    empirical_p = np.full(len(tickers), np.nan, dtype=float)
    valid_obs = np.isfinite(observed_min_edge)
    empirical_p[valid_obs] = (perm_ge[valid_obs] + 1.0) / (float(N_PERM) + 1.0)

    atlas = atlas.copy()
    atlas["empirical_p_min_dev_val_edge"] = empirical_p
    atlas["q_value_min_dev_val_edge"] = np.nan
    qualified_series = atlas["qualified"].fillna(False).astype(bool)
    atlas.loc[qualified_series, "q_value_min_dev_val_edge"] = _bh_qvalues(
        atlas.loc[qualified_series, "empirical_p_min_dev_val_edge"]
    )

    null_summary = {
        "n_perm": int(N_PERM),
        "observed_rank_corr_dev_val": observed_rank_corr,
        "rank_corr_null_mean": float(np.mean(null_rank_corrs)) if null_rank_corrs else None,
        "rank_corr_null_p95": float(np.quantile(null_rank_corrs, 0.95)) if null_rank_corrs else None,
        "rank_corr_empirical_p": (
            float((1 + sum(value >= (observed_rank_corr or -np.inf) for value in null_rank_corrs)) / (len(null_rank_corrs) + 1))
            if null_rank_corrs and observed_rank_corr is not None
            else None
        ),
    }
    return atlas, null_summary


def _safe_autocorr(series: pd.Series, lag: int = 1) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < max(30, lag + 5) or clean.nunique() < 5:
        return None
    stat = clean.autocorr(lag=lag)
    return None if pd.isna(stat) else float(stat)


def _build_local_diagnostics() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in {"VNINDEX", "VN30"}:
            continue
        try:
            frame = pd.read_parquet(path, columns=["time", "open", "high", "low", "close", "volume"])
        except Exception:
            continue
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
        frame = frame.loc[frame["time"].dt.year.between(START_YEAR, DEV_END_YEAR)].sort_values("time").copy()
        if len(frame) < 200:
            continue

        close_ret = frame["close"].pct_change()
        ret_5d = frame["close"].pct_change(5)
        gap_ret = frame["open"].div(frame["close"].shift(1)).sub(1.0)
        intraday_ret = frame["close"].div(frame["open"]).sub(1.0)

        var_1d = pd.to_numeric(close_ret, errors="coerce").replace([np.inf, -np.inf], np.nan).var(ddof=0)
        var_5d = pd.to_numeric(ret_5d, errors="coerce").replace([np.inf, -np.inf], np.nan).var(ddof=0)
        variance_ratio = None
        if pd.notna(var_1d) and pd.notna(var_5d) and float(var_1d) > 0.0:
            variance_ratio = float(var_5d / (5.0 * var_1d))

        overnight_abs = gap_ret.abs().replace([np.inf, -np.inf], np.nan)
        intraday_abs = intraday_ret.abs().replace([np.inf, -np.inf], np.nan)
        overnight_share = None
        denom = float(overnight_abs.mean() + intraday_abs.mean()) if pd.notna(overnight_abs.mean()) and pd.notna(intraday_abs.mean()) else None
        if denom is not None and denom > 0.0:
            overnight_share = float(overnight_abs.mean() / denom)

        traded_value_bn = (frame["close"] * frame["volume"]) / 1e9
        rows.append(
            {
                "ticker": ticker,
                "dev_ret_autocorr_1d": _safe_autocorr(close_ret, lag=1),
                "dev_variance_ratio_5d": variance_ratio,
                "dev_overnight_share_abs": overnight_share,
                "dev_zero_range_rate": float((frame["high"].round(6) == frame["low"].round(6)).mean()),
                "dev_median_value_bn": float(traded_value_bn.replace([np.inf, -np.inf], np.nan).median()),
                "dev_days_ohlcv": int(len(frame)),
            }
        )
    return pd.DataFrame(rows)


def _diagnostic_correlations(frame: pd.DataFrame) -> dict[str, object]:
    out: dict[str, object] = {}
    qualified = frame.loc[frame["qualified"].fillna(False).astype(bool)].copy()
    for column, _, _ in DIAGNOSTIC_SPECS:
        clean = qualified[[column, "min_dev_val_edge"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 10 or clean[column].nunique() < 5 or clean["min_dev_val_edge"].nunique() < 5:
            out[column] = {"spearman": None, "n": int(len(clean))}
            continue
        stat = spearmanr(clean[column], clean["min_dev_val_edge"]).statistic
        out[column] = {"spearman": float(stat), "n": int(len(clean))}
    return out


def _tail_summary(frame: pd.DataFrame, *, tail_col: str) -> dict[str, object]:
    qualified = frame.loc[frame["qualified"].fillna(False).astype(bool)].copy()
    tail = qualified.loc[qualified[tail_col].fillna(False).astype(bool)].copy()
    rest = qualified.loc[~qualified[tail_col].fillna(False).astype(bool)].copy()
    summary: dict[str, object] = {
        "tail_count": int(len(tail)),
        "tail_tickers": tail["ticker"].astype(str).tolist(),
        "reference_qualified_count": int(len(qualified)),
    }
    for column, _, _ in DIAGNOSTIC_SPECS:
        summary[f"{column}_tail_median"] = _safe_float(tail[column].median()) if column in tail else None
        summary[f"{column}_rest_median"] = _safe_float(rest[column].median()) if column in rest else None
    return summary


def _structural_mixed_hits(diag_corrs: dict[str, object]) -> dict[str, object]:
    hits: list[str] = []
    for column, direction, threshold in STRUCTURAL_MIXED_RULES:
        stat = _safe_float(diag_corrs.get(column, {}).get("spearman"))
        if stat is None:
            continue
        if direction == "lower" and stat <= threshold:
            hits.append(column)
        if direction == "higher" and stat >= threshold:
            hits.append(column)
    return {"count": int(len(hits)), "columns": hits}


def main() -> None:
    selected = load_selected_panel()
    atlas = _build_observed_atlas(selected)
    atlas, null_summary = _build_null_outputs(selected, atlas)

    diagnostics = _build_local_diagnostics()
    atlas = atlas.merge(diagnostics, on="ticker", how="left", validate="one_to_one")

    atlas["fdr_tail"] = (
        atlas["qualified"].fillna(False).astype(bool)
        & atlas["q_value_min_dev_val_edge"].le(FDR_ALPHA).fillna(False)
        & atlas["confirmation_edge"].gt(0.0).fillna(False)
    )
    atlas["nominal_tail"] = (
        atlas["qualified"].fillna(False).astype(bool)
        & atlas["empirical_p_min_dev_val_edge"].le(NOMINAL_P_ALPHA).fillna(False)
        & atlas["confirmation_edge"].gt(0.0).fillna(False)
    )

    diag_corrs = _diagnostic_correlations(atlas)
    structural_hits = _structural_mixed_hits(diag_corrs)
    fdr_tail = atlas.loc[atlas["fdr_tail"]].copy()
    nominal_tail = atlas.loc[atlas["nominal_tail"]].copy()

    pass_condition = bool(
        (_safe_float(null_summary.get("rank_corr_empirical_p")) or 1.0) <= RANK_STABILITY_ALPHA
        and int(len(fdr_tail)) >= MIN_PASS_FDR_TAIL
    )
    mixed_condition = bool(
        not pass_condition
        and int(len(nominal_tail)) >= MIN_MIXED_NOMINAL_TAIL
        and int(structural_hits["count"]) >= 2
    )
    decision = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"

    nominal_tail = nominal_tail.sort_values(
        by=["empirical_p_min_dev_val_edge", "min_dev_val_edge", "confirmation_edge"],
        ascending=[True, False, False],
        ignore_index=True,
    )
    fdr_tail = fdr_tail.sort_values(
        by=["q_value_min_dev_val_edge", "min_dev_val_edge", "confirmation_edge"],
        ascending=[True, False, False],
        ignore_index=True,
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h308_stock_local_predictability_atlas"
    atlas_path = OUT_DIR / f"{artifact_stem}_atlas.parquet"
    selected_path = OUT_DIR / f"{artifact_stem}_selected_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    atlas.to_parquet(atlas_path, index=False)
    selected.to_parquet(selected_path, index=False)

    summary = {
        "decision": decision,
        "qualified_ticker_count": int(atlas["qualified"].fillna(False).sum()),
        "stable_dev_val_count": int(atlas["stable_dev_val"].fillna(False).sum()),
        "stable_all_count": int(atlas["stable_all"].fillna(False).sum()),
        "null_summary": null_summary,
        "fdr_tail_count": int(len(fdr_tail)),
        "nominal_tail_count": int(len(nominal_tail)),
        "fdr_tail_tickers": fdr_tail["ticker"].astype(str).tolist(),
        "nominal_tail_tickers": nominal_tail["ticker"].astype(str).tolist(),
        "best_nominal_tail": nominal_tail.head(10).to_dict(orient="records"),
        "diagnostic_correlations": diag_corrs,
        "structural_mixed_hits": structural_hits,
        "nominal_tail_summary": _tail_summary(atlas, tail_col="nominal_tail"),
        "branch_decision": {
            "PASSED": "A null-controlled recurrent-recipient tail survives, so a tiny stock-local follow-up is honest.",
            "MIXED": "No null-controlled broad stock-local branch survives, but a small nominal recurrent-recipient tail clusters in smoother and more liquid names, so keep only a bounded diagnostic line.",
            "FAILED": "The apparent per-ticker tail is not stable enough after null control to justify more stock-local work; keep the branch closed.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "atlas": atlas.sort_values(
            by=["nominal_tail", "fdr_tail", "min_dev_val_edge", "confirmation_edge"],
            ascending=[False, False, False, False],
            ignore_index=True,
        ).to_dict(orient="records"),
        "fdr_tail": fdr_tail.to_dict(orient="records"),
        "nominal_tail": nominal_tail.to_dict(orient="records"),
        "thresholds": {
            "min_dev_days": MIN_DEV_DAYS,
            "min_validation_days": MIN_VAL_DAYS,
            "min_confirmation_days": MIN_CONF_DAYS,
            "n_perm": N_PERM,
            "fdr_alpha": FDR_ALPHA,
            "rank_stability_alpha": RANK_STABILITY_ALPHA,
            "nominal_p_alpha": NOMINAL_P_ALPHA,
            "min_pass_fdr_tail": MIN_PASS_FDR_TAIL,
            "min_mixed_nominal_tail": MIN_MIXED_NOMINAL_TAIL,
            "structural_mixed_rules": _json_safe(
                [{"column": c, "direction": d, "threshold": t} for c, d, t in STRUCTURAL_MIXED_RULES]
            ),
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_stock_local_predictability_atlas",
        name="h308_stock_local_predictability_atlas",
        summary=summary,
        artifacts={
            "atlas": atlas_path,
            "selected_panel": selected_path,
            "details": details_path,
        },
        metadata={
            "session": 134,
            "branch_contract": "H308 is a frozen-S1 HOSE-wide recipient atlas with within-day permutation null control and BH-style multiple-testing discipline; only a null-controlled stable tail may reopen stock-local work.",
        },
    )

    print("H308 stock-local predictability atlas")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
