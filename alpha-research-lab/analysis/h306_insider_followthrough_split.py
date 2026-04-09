"""
H306: insider follow-through split audit.

Question:
    Is low execution follow-through on the positive side of C5 a pollutant that
    should be gated or downweighted, rather than treated as part of the same
    bullish insider-conviction signal?
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

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.feature_engineering import generate_features
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary

QUALITY_PATH = data_path("features/xs_insider_quality_features.parquet")
EVENT_PATH = data_path("features/event_surface_daily.parquet")
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
STOCK_DIR = data_path("stock")
INDEX_FILE = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
EXCLUDE = {"VNINDEX", "VN30"}

PROTOCOL = ResearchProtocol(
    dev_start_year=2015,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

CFG = {
    "data": {"target_col": "future_rel_dir_5d", "start_date": "2012-01-01"},
    "features": {
        "base_cols": [],
        "use_lags": False,
        "use_ma": False,
        "use_ma_dist": True,
        "ma_windows": [5, 10, 20, 50],
        "use_rsi": True,
        "use_macd": True,
        "use_bb": True,
        "use_atr": True,
        "use_candle": True,
        "use_stoch": True,
        "use_willr": False,
        "use_adx": True,
        "use_hist_vol": True,
        "hist_vol_windows": [5, 10, 20],
        "use_cci": False,
        "use_volume_signals": False,
        "use_market_relative": True,
        "index_file": str(INDEX_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
    },
    "model": {"type": "xgboost_classifier", "params": {}},
}

PASS_RETENTION = 0.98
MIXED_RETENTION = 0.95
PASS_CONFIRMATION_UPLIFT = 0.005
MIN_PHASE_ROWS = 100


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
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


def load_future_rel_5d() -> pd.DataFrame:
    parts = []
    for path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        raw = load_data(path, "2012-01-01")
        if len(raw) < 300:
            continue
        feat = generate_features(raw, CFG)
        if "future_rel_return_5d" not in feat.columns:
            continue
        parts.append(feat[["time", "future_rel_return_5d"]].assign(ticker=ticker))
    out = pd.concat(parts, ignore_index=True)
    out = out.rename(columns={"time": "trading_day", "future_rel_return_5d": "fwd_rel_5d"})
    out["trading_day"] = pd.to_datetime(out["trading_day"])
    return out


def _yearly_ic(fire: pd.DataFrame, signal_col: str) -> list[dict[str, object]]:
    rows = []
    for year, group in fire[fire["year"] <= 2025].groupby("year"):
        gg = group[[signal_col, "fwd_rel_5d"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 20 or gg[signal_col].nunique() < 3 or gg["fwd_rel_5d"].nunique() < 3:
            continue
        rho, p = spearmanr(gg[signal_col], gg["fwd_rel_5d"])
        rows.append({"year": int(year), "n": int(len(gg)), "ic": float(rho), "p_value": float(p)})
    return rows


def _phase_ic(frame: pd.DataFrame, *, signal_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame.rename(columns={"trading_day": "time"}), phase, protocol=PROTOCOL)].copy()
    scoped = scoped[[signal_col, "fwd_rel_5d"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(scoped) < 30 or scoped[signal_col].nunique() < 3 or scoped["fwd_rel_5d"].nunique() < 3:
        return {"rows": int(len(scoped)), "pooled_ic": None}
    rho = spearmanr(scoped[signal_col], scoped["fwd_rel_5d"]).statistic
    return {"rows": int(len(scoped)), "pooled_ic": float(np.asarray(rho).flat[0])}


def _corr_with_s1(frame: pd.DataFrame, signal_col: str) -> float | None:
    clean = frame[[signal_col, "xs_proba"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 100 or clean[signal_col].nunique() < 3:
        return None
    rho = spearmanr(clean[signal_col], clean["xs_proba"]).statistic
    return float(np.asarray(rho).flat[0])


def load_panel() -> pd.DataFrame:
    quality = pd.read_parquet(
        QUALITY_PATH,
        columns=["trading_day", "ticker", "xs_ins_relative_size_5d", "xs_ins_exec_rate_5d"],
    )
    quality["trading_day"] = pd.to_datetime(quality["trading_day"])

    event = pd.read_parquet(EVENT_PATH, columns=["time", "ticker", "recent_any_filing_5d"])
    event = event.rename(columns={"time": "trading_day"})
    event["trading_day"] = pd.to_datetime(event["trading_day"])

    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba"])
    s1 = s1.rename(columns={"time": "trading_day"})
    s1["trading_day"] = pd.to_datetime(s1["trading_day"])
    s1 = s1[s1["trading_day"].dt.year <= 2025]

    future_rel = load_future_rel_5d()

    frame = quality.merge(event, on=["trading_day", "ticker"], how="left")
    frame = frame.merge(future_rel, on=["trading_day", "ticker"], how="inner")
    frame = frame.merge(s1, on=["trading_day", "ticker"], how="inner")
    frame = frame[frame["trading_day"].dt.year.between(2015, 2025)].copy()
    frame["year"] = frame["trading_day"].dt.year

    for column in ("xs_ins_relative_size_5d", "xs_ins_exec_rate_5d", "recent_any_filing_5d", "xs_proba"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame


def build_candidate_scores(frame: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    work = frame.copy()
    score = work["xs_ins_relative_size_5d"]
    exec_rate = work["xs_ins_exec_rate_5d"]
    recent_filing = work["recent_any_filing_5d"] > 0.0

    dev_buy = work.loc[
        (work["year"] <= PROTOCOL.dev_end_year)
        & (score > 0.0)
        & (exec_rate > 0.0),
        "xs_ins_exec_rate_5d",
    ]
    if dev_buy.empty:
        raise ValueError("No positive-buy exec_rate rows in the dev window")
    dev_exec_threshold = float(dev_buy.median())

    work["c5_raw"] = score
    work["c5_gate_pos_exec_gt_0"] = score.mask((score > 0.0) & (exec_rate <= 0.0), 0.0)
    work["c5_gate_pos_exec_gt_dev_median"] = score.mask(
        (score > 0.0) & (exec_rate <= dev_exec_threshold),
        0.0,
    )
    work["c5_scale_pos_exec_cap_dev_median"] = np.where(
        score > 0.0,
        score * np.clip(exec_rate / dev_exec_threshold, 0.0, 1.0),
        score,
    )
    work["c5_gate_pos_exec_gt_dev_median_recent_filing"] = score.mask(
        (score > 0.0) & ((exec_rate <= dev_exec_threshold) | (~recent_filing)),
        0.0,
    )
    return work, dev_exec_threshold


def _summarize_candidate(frame: pd.DataFrame, *, signal_col: str) -> dict[str, object]:
    fire = frame.loc[frame[signal_col] != 0.0].copy()
    yearly = _yearly_ic(fire, signal_col)
    phase_rows = {
        phase: _phase_ic(fire, signal_col=signal_col, phase=phase)
        for phase in ("dev", "validation", "confirmation")
    }
    avg_ic = float(np.mean([row["ic"] for row in yearly])) if yearly else None
    pos_years = int(sum(1 for row in yearly if row["ic"] > 0.0))
    return {
        "signal_name": signal_col,
        "fire_rows": int(len(fire)),
        "coverage_pct": float(100.0 * len(fire) / len(frame)),
        "avg_ic": avg_ic,
        "pos_years": pos_years,
        "years": int(len(yearly)),
        "pct_years_positive": float(pos_years / len(yearly)) if yearly else None,
        "corr_with_s1": _corr_with_s1(fire, signal_col),
        "phase_details": phase_rows,
        "yearly": yearly,
        "dev_pooled_ic": phase_rows["dev"]["pooled_ic"],
        "dev_rows": phase_rows["dev"]["rows"],
        "validation_pooled_ic": phase_rows["validation"]["pooled_ic"],
        "validation_rows": phase_rows["validation"]["rows"],
        "confirmation_pooled_ic": phase_rows["confirmation"]["pooled_ic"],
        "confirmation_rows": phase_rows["confirmation"]["rows"],
    }


def _apply_decision(results: pd.DataFrame) -> pd.DataFrame:
    baseline = results.loc[results["signal_name"] == "c5_raw"].iloc[0]
    baseline_avg_ic = _safe_float(baseline["avg_ic"]) or 0.0
    baseline_pos_years = int(baseline["pos_years"])
    baseline_val = _safe_float(baseline["validation_pooled_ic"]) or 0.0
    baseline_conf = _safe_float(baseline["confirmation_pooled_ic"]) or 0.0

    rows = []
    for _, row in results.iterrows():
        item = row.to_dict()
        if item["signal_name"] == "c5_raw":
            item["avg_ic_retention_vs_baseline"] = 1.0
            item["validation_ic_uplift_vs_baseline"] = 0.0
            item["confirmation_ic_uplift_vs_baseline"] = 0.0
            item["candidate_decision"] = "BASELINE"
            rows.append(item)
            continue

        avg_ic = _safe_float(item["avg_ic"]) or 0.0
        retention = avg_ic / baseline_avg_ic if baseline_avg_ic else None
        val_ic = _safe_float(item["validation_pooled_ic"]) or 0.0
        conf_ic = _safe_float(item["confirmation_pooled_ic"]) or 0.0
        pos_years = int(item["pos_years"])
        val_rows = int(item["validation_rows"])
        conf_rows = int(item["confirmation_rows"])
        corr = abs(_safe_float(item["corr_with_s1"]) or 0.0)

        pass_condition = bool(
            retention is not None
            and retention >= PASS_RETENTION
            and pos_years > baseline_pos_years
            and val_rows >= MIN_PHASE_ROWS
            and conf_rows >= MIN_PHASE_ROWS
            and val_ic > 0.0
            and conf_ic > 0.0
            and (conf_ic - baseline_conf) >= PASS_CONFIRMATION_UPLIFT
            and corr < 0.30
        )
        mixed_condition = bool(
            not pass_condition
            and retention is not None
            and retention >= MIXED_RETENTION
            and pos_years > baseline_pos_years
            and conf_ic > 0.0
            and (conf_ic - baseline_conf) > 0.0
        )

        item["avg_ic_retention_vs_baseline"] = retention
        item["validation_ic_uplift_vs_baseline"] = val_ic - baseline_val
        item["confirmation_ic_uplift_vs_baseline"] = conf_ic - baseline_conf
        item["candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
        rows.append(item)

    out = pd.DataFrame(rows)
    decision_rank = {"PASSED": 3, "MIXED": 2, "FAILED": 1, "BASELINE": 0}
    out["_decision_rank"] = out["candidate_decision"].map(decision_rank).fillna(0)
    return out.sort_values(
        by=[
            "_decision_rank",
            "confirmation_ic_uplift_vs_baseline",
            "avg_ic_retention_vs_baseline",
            "avg_ic",
            "pos_years",
            "signal_name",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel = load_panel()
    panel, dev_exec_threshold = build_candidate_scores(panel)

    candidate_cols = [
        "c5_raw",
        "c5_gate_pos_exec_gt_0",
        "c5_gate_pos_exec_gt_dev_median",
        "c5_scale_pos_exec_cap_dev_median",
        "c5_gate_pos_exec_gt_dev_median_recent_filing",
    ]
    results = pd.DataFrame([_summarize_candidate(panel, signal_col=col) for col in candidate_cols])
    results = _apply_decision(results)

    pass_rows = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed_rows = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"
    best_candidate = (
        results.loc[results["candidate_decision"] != "BASELINE"].iloc[0].to_dict()
        if not results.loc[results["candidate_decision"] != "BASELINE"].empty
        else {}
    )
    baseline_row = results.loc[results["signal_name"] == "c5_raw"].iloc[0].to_dict()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h306_insider_followthrough_split"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    results.to_parquet(results_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "dev_exec_rate_threshold": dev_exec_threshold,
        "baseline_row": baseline_row,
        "best_candidate": best_candidate,
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "branch_decision": {
            "PASSED": "Execution follow-through survives as a robustness rewrite of C5: weak bullish follow-through should be gated or downweighted rather than pooled into the same signal.",
            "MIXED": "Execution follow-through helps C5 only weakly or inconsistently; keep it as a narrow robustness clue, not a rewritten signal yet.",
            "FAILED": "Execution follow-through does not improve C5 enough to justify a conditioned rewrite; keep exec_rate as standalone negative evidence only.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "results": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "thresholds": {
            "pass_retention": PASS_RETENTION,
            "mixed_retention": MIXED_RETENTION,
            "pass_confirmation_uplift": PASS_CONFIRMATION_UPLIFT,
            "min_phase_rows": MIN_PHASE_ROWS,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_insider_followthrough_split",
        name="h306_insider_followthrough_split",
        summary=summary,
        artifacts={
            "results": results_path,
            "details": details_path,
        },
        metadata={
            "session": 132,
            "protocol": PROTOCOL.describe(),
            "branch_contract": "H306 is a 2015-2025 C5 rewrite audit on the original H108 5d relative-return target, using dev-defined exec-rate thresholds and no live-branch change.",
        },
    )

    print("H306 insider follow-through split audit")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
