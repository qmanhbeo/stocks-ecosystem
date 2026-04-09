"""
H320: criticality order-parameter audit.

Question:
    Does a raw market-criticality field explain next-cycle selector efficacy
    beyond the existing short-memory activation state?

Design:
    - build daily OHLCV-derived order parameters from raw HOSE stock history
    - use activation_meta_daily as the maintained selector-efficacy spine
    - residualize next-cycle relative return against the incumbent
      full_recent_cycle_relative_return_ewm3 on the dev split
    - test whether criticality features explain the residual target or
      condition the incumbent high-efficacy state in validation and 2025
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_ohlcv_wide


META_PATH = data_path("features/activation_meta_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2015,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

TARGET_COL = "full_future_cycle_relative_return"
BASELINE_COL = "full_recent_cycle_relative_return_ewm3"
BASELINE_HIGH_Q = 0.70
FEATURE_HIGH_Q = 0.80
ROLLING_WINDOW = 252
ROLLING_MIN_DAYS = 60

CRITICALITY_FEATURES = (
    "upward_order",
    "stress_order",
    "synchrony_pressure",
    "susceptibility_pressure",
    "upward_criticality",
    "stress_criticality",
    "limit_cluster_pressure",
    "gap_alignment_pressure",
)

PASS_MIN_ABS_RESID_RHO = 0.06
PASS_MIN_ABS_RESID_LIFT = 0.004
PASS_MIN_ABS_BASE_COND_LIFT = 0.004
MIXED_MIN_ABS_RESID_RHO = 0.03
MIXED_MIN_ABS_RESID_LIFT = 0.002


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


def _safe_spearman(left: pd.Series, right: pd.Series, *, min_rows: int = 30) -> float | None:
    clean = (
        pd.concat([left.rename("left"), right.rename("right")], axis=1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(clean) < min_rows or clean["left"].nunique() < 3 or clean["right"].nunique() < 3:
        return None
    stat = spearmanr(clean["left"], clean["right"]).statistic
    if not np.isfinite(stat):
        return None
    return float(np.asarray(stat).flat[0])


def _trailing_z(series: pd.Series, *, window: int = ROLLING_WINDOW, min_periods: int = ROLLING_MIN_DAYS) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    mean = values.shift(1).rolling(window, min_periods=min_periods).mean()
    std = values.shift(1).rolling(window, min_periods=min_periods).std(ddof=0)
    return (values - mean).div(std.replace(0.0, np.nan))


def _row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return frame[columns].replace([np.inf, -np.inf], np.nan).mean(axis=1, skipna=True)


def _fit_dev_residual(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.copy()
    dev = work.loc[phase_mask(work, "dev", protocol=PROTOCOL), [TARGET_COL, BASELINE_COL]].dropna()
    if len(dev) < 100:
        raise ValueError("Not enough dev rows to fit H320 baseline residual")
    x = np.column_stack([np.ones(len(dev)), dev[BASELINE_COL].to_numpy(dtype=float)])
    y = dev[TARGET_COL].to_numpy(dtype=float)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    pred = beta[0] + beta[1] * pd.to_numeric(work[BASELINE_COL], errors="coerce")
    work["baseline_pred"] = pred
    work["target_residual_vs_recent_ewm3"] = pd.to_numeric(work[TARGET_COL], errors="coerce") - pred
    work.attrs["baseline_beta"] = {"intercept": float(beta[0]), "slope": float(beta[1])}
    return work


def _build_raw_market_features() -> pd.DataFrame:
    wide = load_ohlcv_wide(min_rows=120)
    close = wide["close"].sort_index()
    open_ = wide["open"].reindex_like(close)
    ret1 = close.pct_change(1, fill_method=None)
    prev_close = close.shift(1)
    gap = open_.div(prev_close).sub(1.0)
    intraday = close.div(open_).sub(1.0)
    available = ret1.notna()

    feature = pd.DataFrame(index=close.index)
    feature.index.name = "time"
    feature["raw_ret_std_1d"] = ret1.std(axis=1, skipna=True)
    feature["raw_tail_spread_1d"] = ret1.quantile(0.95, axis=1) - ret1.quantile(0.05, axis=1)
    feature["raw_large_move_share"] = ret1.abs().ge(0.03).where(available).mean(axis=1)
    feature["raw_market_abs_ret"] = ret1.mean(axis=1, skipna=True).abs()
    feature["up_limit_share"] = ret1.ge(0.068).where(available).mean(axis=1)
    feature["down_limit_share"] = ret1.le(-0.068).where(available).mean(axis=1)
    feature["abs_limit_share"] = feature["up_limit_share"] + feature["down_limit_share"]
    feature["up_gap_align_share"] = (gap.gt(0.0) & intraday.gt(0.0)).where(available).mean(axis=1)
    feature["down_gap_align_share"] = (gap.lt(0.0) & intraday.lt(0.0)).where(available).mean(axis=1)
    feature["same_direction_share"] = (
        ((gap.gt(0.0) & intraday.gt(0.0)) | (gap.lt(0.0) & intraday.lt(0.0))).where(available).mean(axis=1)
    )
    feature["gap_abs_share"] = gap.abs().ge(0.02).where(gap.notna()).mean(axis=1)
    feature["raw_breadth_up"] = ret1.gt(0.0).where(available).mean(axis=1)
    feature["raw_breadth_down"] = ret1.lt(0.0).where(available).mean(axis=1)
    feature["raw_breadth_imbalance_abs"] = (feature["raw_breadth_up"] - feature["raw_breadth_down"]).abs()
    return feature.reset_index()


def _build_daily_panel() -> pd.DataFrame:
    meta = pd.read_parquet(META_PATH).copy()
    meta["time"] = pd.to_datetime(meta["time"], errors="coerce").dt.normalize()
    meta = meta.loc[meta["time"].dt.year.between(2015, 2025)].copy()
    raw = _build_raw_market_features()
    raw["time"] = pd.to_datetime(raw["time"], errors="coerce").dt.normalize()

    panel = meta.merge(raw, on="time", how="left", validate="one_to_one")
    z_inputs = {
        "z_xs_breadth_up_1d": "xs_breadth_up_1d",
        "z_xs_breadth_down_1d": "xs_breadth_down_1d",
        "z_xs_tail_spread_1d": "xs_tail_spread_1d",
        "z_xs_ret_std_1d": "xs_ret_std_1d",
        "z_xs_overnight_intraday_spread": "xs_overnight_intraday_spread",
        "z_vni_ret_5d": "vni_ret_5d",
        "z_vni_drawdown_60d": "vni_drawdown_60d",
        "z_up_limit_share": "up_limit_share",
        "z_down_limit_share": "down_limit_share",
        "z_abs_limit_share": "abs_limit_share",
        "z_up_gap_align_share": "up_gap_align_share",
        "z_down_gap_align_share": "down_gap_align_share",
        "z_same_direction_share": "same_direction_share",
        "z_gap_abs_share": "gap_abs_share",
        "z_raw_breadth_imbalance_abs": "raw_breadth_imbalance_abs",
        "z_raw_large_move_share": "raw_large_move_share",
        "z_raw_market_abs_ret": "raw_market_abs_ret",
        "z_raw_ret_std_1d": "raw_ret_std_1d",
        "z_raw_tail_spread_1d": "raw_tail_spread_1d",
    }
    for out_col, in_col in z_inputs.items():
        panel[out_col] = _trailing_z(panel[in_col])

    panel["upward_order"] = _row_mean(
        panel,
        [
            "z_xs_breadth_up_1d",
            "z_up_limit_share",
            "z_up_gap_align_share",
            "z_vni_ret_5d",
        ],
    )
    panel["stress_order"] = _row_mean(
        panel,
        [
            "z_xs_breadth_down_1d",
            "z_down_limit_share",
            "z_down_gap_align_share",
            "z_vni_drawdown_60d",
        ],
    )
    panel["synchrony_pressure"] = _row_mean(
        panel,
        [
            "z_raw_breadth_imbalance_abs",
            "z_same_direction_share",
            "z_raw_market_abs_ret",
            "z_raw_large_move_share",
        ],
    )
    panel["susceptibility_pressure"] = _row_mean(
        panel,
        [
            "z_xs_tail_spread_1d",
            "z_xs_ret_std_1d",
            "z_raw_ret_std_1d",
            "z_raw_tail_spread_1d",
            "z_abs_limit_share",
            "z_gap_abs_share",
        ],
    )
    panel["upward_criticality"] = _row_mean(
        panel,
        ["upward_order", "synchrony_pressure", "susceptibility_pressure"],
    )
    panel["stress_criticality"] = _row_mean(
        panel,
        ["stress_order", "synchrony_pressure", "susceptibility_pressure"],
    )
    panel["limit_cluster_pressure"] = _row_mean(panel, ["z_abs_limit_share", "z_up_limit_share", "z_down_limit_share"])
    panel["gap_alignment_pressure"] = _row_mean(
        panel,
        ["z_same_direction_share", "z_up_gap_align_share", "z_down_gap_align_share", "z_gap_abs_share"],
    )
    panel = _fit_dev_residual(panel)
    return panel.sort_values("time").reset_index(drop=True)


def _dev_threshold(frame: pd.DataFrame, column: str, quantile: float) -> float | None:
    dev = pd.to_numeric(frame.loc[phase_mask(frame, "dev", protocol=PROTOCOL), column], errors="coerce").dropna()
    if len(dev) < 100:
        return None
    return float(dev.quantile(quantile))


def _phase_state_stats(frame: pd.DataFrame, feature_col: str, phase: str, high_threshold: float) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    numeric_cols = scoped.select_dtypes(include=[np.number]).columns
    scoped.loc[:, numeric_cols] = scoped.loc[:, numeric_cols].replace([np.inf, -np.inf], np.nan)
    scoped["feature_high"] = pd.to_numeric(scoped[feature_col], errors="coerce") >= high_threshold
    target_mean = _safe_float(scoped[TARGET_COL].mean())
    resid_mean = _safe_float(scoped["target_residual_vs_recent_ewm3"].mean())
    high = scoped.loc[scoped["feature_high"]].copy()
    not_high = scoped.loc[~scoped["feature_high"]].copy()

    high_target = _safe_float(high[TARGET_COL].mean()) if not high.empty else None
    not_high_target = _safe_float(not_high[TARGET_COL].mean()) if not not_high.empty else None
    high_resid = _safe_float(high["target_residual_vs_recent_ewm3"].mean()) if not high.empty else None
    not_high_resid = _safe_float(not_high["target_residual_vs_recent_ewm3"].mean()) if not not_high.empty else None
    return {
        "rows": int(len(scoped)),
        "active_rows": int(len(high)),
        "target_mean": target_mean,
        "resid_mean": resid_mean,
        "rho_target": _safe_spearman(scoped[feature_col], scoped[TARGET_COL]),
        "rho_residual": _safe_spearman(scoped[feature_col], scoped["target_residual_vs_recent_ewm3"]),
        "high_target_mean": high_target,
        "not_high_target_mean": not_high_target,
        "high_residual_mean": high_resid,
        "not_high_residual_mean": not_high_resid,
        "high_minus_not_target": None
        if high_target is None or not_high_target is None
        else float(high_target - not_high_target),
        "high_minus_not_residual": None
        if high_resid is None or not_high_resid is None
        else float(high_resid - not_high_resid),
    }


def _phase_baseline_conditioning(
    frame: pd.DataFrame,
    feature_col: str,
    phase: str,
    feature_high_threshold: float,
    baseline_high_threshold: float,
) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    numeric_cols = scoped.select_dtypes(include=[np.number]).columns
    scoped.loc[:, numeric_cols] = scoped.loc[:, numeric_cols].replace([np.inf, -np.inf], np.nan)
    scoped = scoped.dropna(subset=[feature_col, BASELINE_COL, TARGET_COL])
    scoped["feature_high"] = scoped[feature_col] >= feature_high_threshold
    scoped["baseline_high"] = scoped[BASELINE_COL] >= baseline_high_threshold
    high_base = scoped.loc[scoped["baseline_high"]].copy()
    both_high = high_base.loc[high_base["feature_high"]].copy()
    base_only = high_base.loc[~high_base["feature_high"]].copy()
    both_target = _safe_float(both_high[TARGET_COL].mean()) if not both_high.empty else None
    base_only_target = _safe_float(base_only[TARGET_COL].mean()) if not base_only.empty else None
    both_resid = _safe_float(both_high["target_residual_vs_recent_ewm3"].mean()) if not both_high.empty else None
    base_only_resid = _safe_float(base_only["target_residual_vs_recent_ewm3"].mean()) if not base_only.empty else None
    return {
        "baseline_high_rows": int(len(high_base)),
        "both_high_rows": int(len(both_high)),
        "base_only_rows": int(len(base_only)),
        "both_high_target_mean": both_target,
        "base_only_target_mean": base_only_target,
        "both_high_residual_mean": both_resid,
        "base_only_residual_mean": base_only_resid,
        "both_minus_base_only_target": None
        if both_target is None or base_only_target is None
        else float(both_target - base_only_target),
        "both_minus_base_only_residual": None
        if both_resid is None or base_only_resid is None
        else float(both_resid - base_only_resid),
    }


def _phase_baseline_summary(frame: pd.DataFrame, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    return {
        "rows": int(len(scoped)),
        "rho_target": _safe_spearman(scoped[BASELINE_COL], scoped[TARGET_COL]),
        "target_mean": _safe_float(scoped[TARGET_COL].mean()),
    }


def _decide_feature(row: pd.Series) -> str:
    dev_signal = _safe_float(row["dev_high_minus_not_residual"])
    if dev_signal is None or abs(dev_signal) < 1e-9:
        dev_signal = _safe_float(row["dev_rho_residual"])
    expected_sign = 0.0 if dev_signal is None else float(np.sign(dev_signal))
    if expected_sign == 0.0:
        return "FAILED"

    val_rho = (_safe_float(row["validation_rho_residual"]) or 0.0) * expected_sign
    conf_rho = (_safe_float(row["confirmation_rho_residual"]) or 0.0) * expected_sign
    val_lift = (_safe_float(row["validation_high_minus_not_residual"]) or 0.0) * expected_sign
    conf_lift = (_safe_float(row["confirmation_high_minus_not_residual"]) or 0.0) * expected_sign
    val_cond = (_safe_float(row["validation_both_minus_base_only_residual"]) or 0.0) * expected_sign
    conf_cond = (_safe_float(row["confirmation_both_minus_base_only_residual"]) or 0.0) * expected_sign

    if (
        val_rho >= PASS_MIN_ABS_RESID_RHO
        and conf_rho >= PASS_MIN_ABS_RESID_RHO
        and val_lift >= PASS_MIN_ABS_RESID_LIFT
        and conf_lift >= PASS_MIN_ABS_RESID_LIFT
        and val_cond >= PASS_MIN_ABS_BASE_COND_LIFT
        and conf_cond >= PASS_MIN_ABS_BASE_COND_LIFT
    ):
        return "PASSED"
    if (
        val_rho >= MIXED_MIN_ABS_RESID_RHO
        and conf_rho >= MIXED_MIN_ABS_RESID_RHO
        and val_lift >= MIXED_MIN_ABS_RESID_LIFT
        and conf_lift >= MIXED_MIN_ABS_RESID_LIFT
    ) or (
        val_cond >= MIXED_MIN_ABS_RESID_LIFT
        and conf_cond >= MIXED_MIN_ABS_RESID_LIFT
        and val_rho >= 0.0
        and conf_rho >= 0.0
    ):
        return "MIXED"
    return "FAILED"


def _evaluate(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    baseline_threshold = _dev_threshold(panel, BASELINE_COL, BASELINE_HIGH_Q)
    if baseline_threshold is None:
        raise ValueError("Unable to derive H320 baseline dev threshold")

    rows: list[dict[str, object]] = []
    for feature_col in CRITICALITY_FEATURES:
        feature_threshold = _dev_threshold(panel, feature_col, FEATURE_HIGH_Q)
        if feature_threshold is None:
            continue
        row: dict[str, object] = {
            "feature": feature_col,
            "feature_high_threshold_dev_q80": feature_threshold,
            "baseline_high_threshold_dev_q70": baseline_threshold,
        }
        for phase in ("dev", "validation", "confirmation"):
            phase_stats = _phase_state_stats(panel, feature_col, phase, feature_threshold)
            cond_stats = _phase_baseline_conditioning(panel, feature_col, phase, feature_threshold, baseline_threshold)
            for key, value in phase_stats.items():
                row[f"{phase}_{key}"] = value
            for key, value in cond_stats.items():
                row[f"{phase}_{key}"] = value
        rows.append(row)

    results = pd.DataFrame(rows)
    if results.empty:
        raise ValueError("No H320 criticality rows were evaluated")
    results["candidate_decision"] = results.apply(_decide_feature, axis=1)

    baseline_summary = {
        phase: _phase_baseline_summary(panel, phase)
        for phase in ("dev", "validation", "confirmation")
    }
    baseline_summary["dev_fit"] = panel.attrs.get("baseline_beta", {})
    baseline_summary["baseline_high_threshold_dev_q70"] = baseline_threshold
    return results, baseline_summary


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = _build_daily_panel()
    results, baseline_summary = _evaluate(panel)

    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2}
    ranked = results.copy()
    ranked["decision_rank"] = ranked["candidate_decision"].map(decision_rank).fillna(9)
    ranked["val_conf_resid_score"] = (
        pd.to_numeric(ranked["validation_rho_residual"], errors="coerce").abs().fillna(0.0)
        + pd.to_numeric(ranked["confirmation_rho_residual"], errors="coerce").abs().fillna(0.0)
    )
    ranked["val_conf_cond_score"] = (
        pd.to_numeric(ranked["validation_both_minus_base_only_residual"], errors="coerce").abs().fillna(0.0)
        + pd.to_numeric(ranked["confirmation_both_minus_base_only_residual"], errors="coerce").abs().fillna(0.0)
    )
    best = ranked.sort_values(
        ["decision_rank", "val_conf_resid_score", "val_conf_cond_score"],
        ascending=[True, False, False],
    ).iloc[0]

    if (results["candidate_decision"] == "PASSED").any():
        verdict = "PASSED"
        branch_decision = (
            "A criticality order-parameter survived residual and conditioning checks. "
            "Advance to a bounded activation-overlay follow-up."
        )
    elif (results["candidate_decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Criticality carries a weak residual or conditioning trace, but not enough to promote. "
            "Keep as offline meta-state evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Raw criticality order-parameters do not explain selector efficacy beyond the "
            "incumbent short-memory activation signal. Park the branch on current data."
        )

    panel_path = OUT_DIR / f"{ts}_h320_criticality_order_parameter_panel.parquet"
    results_path = OUT_DIR / f"{ts}_h320_criticality_order_parameter_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_criticality_order_parameter_details.json"
    panel.to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    detail_payload = {
        "branch_decision": branch_decision,
        "baseline_summary": baseline_summary,
        "best_feature": _json_safe(best.to_dict()),
        "results": _json_safe(results.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(detail_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "best_feature": best["feature"],
        "best_feature_decision": best["candidate_decision"],
        "baseline_validation_rho_target": _safe_float(baseline_summary["validation"]["rho_target"]),
        "baseline_confirmation_rho_target": _safe_float(baseline_summary["confirmation"]["rho_target"]),
        "best_validation_rho_residual": _safe_float(best["validation_rho_residual"]),
        "best_confirmation_rho_residual": _safe_float(best["confirmation_rho_residual"]),
        "best_validation_high_minus_not_residual": _safe_float(best["validation_high_minus_not_residual"]),
        "best_confirmation_high_minus_not_residual": _safe_float(best["confirmation_high_minus_not_residual"]),
        "best_validation_both_minus_base_only_residual": _safe_float(best["validation_both_minus_base_only_residual"]),
        "best_confirmation_both_minus_base_only_residual": _safe_float(best["confirmation_both_minus_base_only_residual"]),
        "rows": int(len(panel)),
    }
    artifacts = {
        "daily_panel": panel_path,
        "results": results_path,
        "details": details_path,
    }
    metadata = {
        "question": "Do raw market-criticality order parameters explain next-cycle selector efficacy beyond recent efficacy memory?",
        "protocol": PROTOCOL.describe(),
        "target": TARGET_COL,
        "baseline": BASELINE_COL,
        "decision_rules": {
            "pass_min_abs_residual_rho": PASS_MIN_ABS_RESID_RHO,
            "pass_min_abs_residual_lift": PASS_MIN_ABS_RESID_LIFT,
            "pass_min_abs_baseline_conditioning_lift": PASS_MIN_ABS_BASE_COND_LIFT,
            "mixed_min_abs_residual_rho": MIXED_MIN_ABS_RESID_RHO,
            "mixed_min_abs_residual_lift": MIXED_MIN_ABS_RESID_LIFT,
        },
        "note": "Feature transforms use trailing 252-session z-scores, shifted one day, to avoid future distribution leakage.",
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_criticality_order_parameter",
        name="criticality_order_parameter",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
