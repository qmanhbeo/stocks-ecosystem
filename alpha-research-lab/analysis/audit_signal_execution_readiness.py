#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import MAX_RESEARCH_YEAR, load_s1_decision_panel
from src.repo_paths import artifact_path, data_path

STATUS_RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"
STATUS_LAB_PROMOTED_PENDING_EXECUTION = "LAB_PROMOTED_PENDING_EXECUTION"
DEFAULT_CONTRACT_CSV_PATH = data_path("features/recommendations/signal_promotion_contract_latest.csv")
DEFAULT_CONTRACT_JSON_PATH = data_path("features/recommendations/signal_promotion_contract_latest.json")


@dataclass(frozen=True)
class SignalSpec:
    signal_id: str
    source_path: Path
    source_col: str
    derive: str | None = None


DEFAULT_SIGNAL_SPECS: dict[str, SignalSpec] = {
    "s1": SignalSpec(
        signal_id="s1",
        source_path=data_path("features/xs_barrier_vol_1d_hose_full.parquet"),
        source_col="xs_proba",
    ),
    "c4": SignalSpec("c4", data_path("features/xs_rl_signal_matrix.parquet"), "c4_oc_asym_5d"),
    "c5": SignalSpec("c5", data_path("features/xs_rl_signal_matrix.parquet"), "c5_ins_relative_size_5d"),
    "c6": SignalSpec("c6", data_path("features/xs_rl_signal_matrix.parquet"), "c6_contrarian_intra_5d"),
    "c7": SignalSpec("c7", data_path("features/xs_rl_signal_matrix.parquet"), "c7_ceiling_count_5d"),
    "c8": SignalSpec("c8", data_path("features/xs_rl_signal_matrix.parquet"), "c8_vol_zscore_5d"),
    "c9": SignalSpec("c9", data_path("features/xs_rl_signal_matrix.parquet"), "c9_reversal_1d"),
    "c10": SignalSpec("c10", data_path("features/xs_rl_signal_matrix.parquet"), "c10_illiq_level_rank"),
    "c11": SignalSpec("c11", data_path("features/xs_rl_signal_matrix.parquet"), "c11_ret_60d_lag_rank"),
    "c12": SignalSpec("c12", data_path("features/xs_rl_signal_matrix.parquet"), "c12_gap_absorb_3"),
    "c13": SignalSpec("c13", data_path("features/xs_rl_signal_matrix.parquet"), "c13_compress_blowoff_2"),
    "c14": SignalSpec("c14", data_path("features/xs_rl_signal_matrix.parquet"), "c14_clv_volconf_resid_rank"),
    "c16": SignalSpec("c16", data_path("features/xs_order_pressure_daily.parquet"), "order_volume_ratio_rank"),
    "c17": SignalSpec("c17", data_path("features/xs_order_pressure_daily.parquet"), "order_volume_ratio"),
    "c18": SignalSpec(
        signal_id="c18",
        source_path=data_path("features/xs_order_pressure_daily.parquet"),
        source_col="order_volume_ratio_rank",
        derive="rank_delta_1d",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute lab execution-readiness fields for signal-library entries."
    )
    parser.add_argument(
        "--signals",
        type=str,
        default="s1,c8,c16,c17,c18",
        help="Comma-separated signal ids from built-in registry.",
    )
    parser.add_argument(
        "--custom-signal",
        action="append",
        default=[],
        help="Custom signal spec: signal_id=relative/or/abs/path.parquet:column_name",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--publish-contract",
        action="store_true",
        help="Also publish promotion contract to shared data/features/recommendations.",
    )
    parser.add_argument(
        "--contract-csv-path",
        type=str,
        default=str(DEFAULT_CONTRACT_CSV_PATH),
        help="Target CSV path for shared promotion contract publish.",
    )
    parser.add_argument(
        "--contract-json-path",
        type=str,
        default=str(DEFAULT_CONTRACT_JSON_PATH),
        help="Target JSON path for shared promotion contract publish.",
    )
    parser.add_argument(
        "--contract-as-of-date",
        type=str,
        default="",
        help="Override as_of_date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Optional explicit output directory; default under artifacts/audits timestamp.",
    )
    return parser.parse_args()


def normalize_time_ticker(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out = out.dropna(subset=["time", "ticker"])
    return out


def parse_custom_signal(raw: str) -> SignalSpec:
    if "=" not in raw or ":" not in raw:
        raise ValueError(
            f"Invalid custom signal '{raw}'. Expected signal_id=path.parquet:column_name"
        )
    signal_id, rhs = raw.split("=", 1)
    path_str, col = rhs.rsplit(":", 1)
    path = Path(path_str)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return SignalSpec(signal_id=signal_id.strip(), source_path=path, source_col=col.strip())


def classify_sparsity(coverage_pct: float) -> str:
    if coverage_pct >= 80.0:
        return "dense"
    if coverage_pct >= 30.0:
        return "semi_dense"
    if coverage_pct >= 5.0:
        return "sparse"
    return "ultra_sparse"


def classify_turnover(churn: float) -> str:
    if not np.isfinite(churn):
        return "unknown"
    if churn < 0.25:
        return "low"
    if churn < 0.50:
        return "medium"
    return "high"


def topk_churn_metrics(panel: pd.DataFrame, signal_col: str, top_k: int) -> tuple[float, float]:
    active = panel.dropna(subset=[signal_col]).copy()
    if active.empty:
        return float("nan"), float("nan")

    active = active.sort_values(["time", signal_col], ascending=[True, False])
    selections: list[set[str]] = []
    fill_rates: list[float] = []

    for _, grp in active.groupby("time", sort=True):
        ranked = grp.nlargest(top_k, signal_col)
        sel = set(ranked["ticker"].astype(str))
        if not sel:
            continue
        selections.append(sel)
        fill_rates.append(min(len(sel), top_k) / float(top_k))

    if len(selections) < 2:
        return float("nan"), float(np.mean(fill_rates) if fill_rates else np.nan)

    churns: list[float] = []
    for prev, cur in zip(selections[:-1], selections[1:]):
        denom = max(1, min(top_k, len(prev), len(cur)))
        retention = len(prev.intersection(cur)) / float(denom)
        churns.append(1.0 - retention)

    return float(np.mean(churns)), float(np.mean(fill_rates) if fill_rates else np.nan)


def _safe_float(value: object, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return fallback
    return out if np.isfinite(out) else fallback


def proxy_execution_score(row: pd.Series) -> float:
    """Lightweight execution proxy used by the lab handoff gate."""
    coverage_score = min(max(_safe_float(row.get("coverage_pct"), 0.0) / 100.0, 0.0), 1.0)
    tradability_score = min(max(_safe_float(row.get("tradability_buyable_pct"), 0.0) / 100.0, 0.0), 1.0)
    fill_score = min(max(_safe_float(row.get("topk_fill_rate"), 0.0), 0.0), 1.0)
    churn_penalty = min(max(1.0 - _safe_float(row.get("turnover_proxy_churn"), 1.0), 0.0), 1.0)
    score = (
        0.35 * coverage_score
        + 0.25 * tradability_score
        + 0.25 * fill_score
        + 0.15 * churn_penalty
    )
    return round(float(score), 6)


def evaluate_proxy_gate(row: pd.Series) -> tuple[bool, str]:
    """Return (proxy_gate_pass, readiness_verdict)."""
    coverage_pct = _safe_float(row.get("coverage_pct"), 0.0)
    trad_buyable_pct = _safe_float(row.get("tradability_buyable_pct"), 0.0)
    fill_rate = _safe_float(row.get("topk_fill_rate"), 0.0)
    churn = _safe_float(row.get("turnover_proxy_churn"), 1.0)
    score = proxy_execution_score(row)

    hard_fail = (
        coverage_pct < 5.0
        or trad_buyable_pct < 60.0
        or fill_rate < 0.15
    )
    pass_gate = (
        coverage_pct >= 30.0
        and trad_buyable_pct >= 90.0
        and fill_rate >= 0.35
        and churn <= 0.95
        and score >= 0.55
    )
    if pass_gate:
        return True, "pass"
    if hard_fail:
        return False, "fail"
    return False, "warn"


def build_promotion_contract(
    readiness_df: pd.DataFrame,
    *,
    as_of_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in readiness_df.iterrows():
        pass_gate, verdict = evaluate_proxy_gate(row)
        rows.append(
            {
                "signal_id": str(row.get("signal_id")),
                "as_of_date": as_of_date,
                "contract_version": "v1",
                "source_path": str(row.get("source_path", "")),
                "source_col": str(row.get("source_col", "")),
                "derived": str(row.get("derived", "")),
                "start_year": int(row.get("start_year", 0)),
                "end_year": int(row.get("end_year", 0)),
                "ic_mean": np.nan,
                "ic_positive_year_ratio": np.nan,
                "orthogonality_max_corr": np.nan,
                "coverage_pct": _safe_float(row.get("coverage_pct"), np.nan),
                "sparsity_profile": str(row.get("sparsity_profile", "")),
                "turnover_proxy_churn": _safe_float(row.get("turnover_proxy_churn"), np.nan),
                "tradability_overlap_pct": _safe_float(row.get("tradability_overlap_pct"), np.nan),
                "tradability_buyable_pct": _safe_float(row.get("tradability_buyable_pct"), np.nan),
                "selection_fill_proxy": _safe_float(row.get("topk_fill_rate"), np.nan),
                "proxy_execution_score": proxy_execution_score(row),
                "proxy_gate_pass": bool(pass_gate),
                "execution_readiness_verdict": verdict,
                "lab_promotion_status": (
                    STATUS_LAB_PROMOTED_PENDING_EXECUTION if pass_gate else STATUS_RESEARCH_CANDIDATE
                ),
                "heuristic_validation_ref": "",
                "execution_validation_status": "",
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("signal_id").reset_index(drop=True)
    return out


def build_signal_panel(
    *,
    base_panel: pd.DataFrame,
    spec: SignalSpec,
    parquet_cache: dict[Path, pd.DataFrame],
) -> pd.DataFrame:
    if spec.source_path not in parquet_cache:
        frame = pd.read_parquet(spec.source_path)
        frame = normalize_time_ticker(frame)
        parquet_cache[spec.source_path] = frame

    frame = parquet_cache[spec.source_path]

    if spec.derive == "rank_delta_1d":
        work = frame[["time", "ticker", spec.source_col]].copy()
        work = work.sort_values(["ticker", "time"])
        derived_col = f"{spec.source_col}_delta_1d"
        work[derived_col] = pd.to_numeric(work[spec.source_col], errors="coerce") - pd.to_numeric(
            work.groupby("ticker")[spec.source_col].shift(1), errors="coerce"
        )
        signal_col = derived_col
        signal_frame = work[["time", "ticker", signal_col]]
    else:
        if spec.source_col not in frame.columns:
            raise ValueError(
                f"Signal {spec.signal_id}: column '{spec.source_col}' not found in {spec.source_path}"
            )
        signal_col = spec.source_col
        signal_frame = frame[["time", "ticker", signal_col]].copy()

    panel = base_panel.merge(signal_frame, on=["time", "ticker"], how="left")
    return panel


def compute_readiness_table(
    *,
    specs: Iterable[SignalSpec],
    start_year: int,
    end_year: int,
    top_k: int,
) -> pd.DataFrame:
    if end_year > MAX_RESEARCH_YEAR:
        raise ValueError(
            f"end_year={end_year} exceeds lockbox guard MAX_RESEARCH_YEAR={MAX_RESEARCH_YEAR}"
        )

    base = load_s1_decision_panel(start_year=start_year, end_year=end_year)
    base = base[["time", "ticker"]].copy()

    trad = pd.read_parquet(data_path("features/execution/tradability_daily.parquet"))
    trad = normalize_time_ticker(trad)
    trad = trad[["time", "ticker", "can_buy_next_open"]].drop_duplicates(["time", "ticker"])
    base = base.merge(trad, on=["time", "ticker"], how="left")

    parquet_cache: dict[Path, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []

    panel_rows = int(len(base))

    for spec in specs:
        panel = build_signal_panel(base_panel=base, spec=spec, parquet_cache=parquet_cache)

        signal_col = f"{spec.source_col}_delta_1d" if spec.derive == "rank_delta_1d" else spec.source_col
        signal = pd.to_numeric(panel[signal_col], errors="coerce")
        active_mask = signal.notna()

        active_rows = int(active_mask.sum())
        coverage_pct = 100.0 * active_rows / float(panel_rows) if panel_rows > 0 else float("nan")

        active_panel = panel.loc[active_mask].copy()
        trad_overlap_pct = (
            100.0 * float(active_panel["can_buy_next_open"].notna().mean())
            if active_rows > 0
            else float("nan")
        )
        trad_buyable_pct = (
            100.0 * float(active_panel["can_buy_next_open"].fillna(False).astype(bool).mean())
            if active_rows > 0
            else float("nan")
        )

        churn_proxy, topk_fill_rate = topk_churn_metrics(panel, signal_col, top_k=top_k)

        rows.append(
            {
                "signal_id": spec.signal_id,
                "source_path": str(spec.source_path),
                "source_col": spec.source_col,
                "derived": spec.derive or "",
                "start_year": int(start_year),
                "end_year": int(end_year),
                "panel_rows": panel_rows,
                "active_rows": active_rows,
                "coverage_pct": round(coverage_pct, 4),
                "sparsity_profile": classify_sparsity(coverage_pct),
                "turnover_proxy_churn": round(float(churn_proxy), 6) if np.isfinite(churn_proxy) else np.nan,
                "turnover_proxy_profile": classify_turnover(churn_proxy),
                "topk_fill_rate": round(float(topk_fill_rate), 6) if np.isfinite(topk_fill_rate) else np.nan,
                "tradability_overlap_pct": round(trad_overlap_pct, 4) if np.isfinite(trad_overlap_pct) else np.nan,
                "tradability_buyable_pct": round(trad_buyable_pct, 4) if np.isfinite(trad_buyable_pct) else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("signal_id").reset_index(drop=True)
    return out


def build_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "No signals evaluated."

    lines = []
    lines.append("| signal_id | coverage_pct | sparsity_profile | turnover_proxy_churn | turnover_proxy_profile | tradability_overlap_pct | tradability_buyable_pct |")
    lines.append("|---|---:|---|---:|---|---:|---:|")
    for _, r in df.iterrows():
        lines.append(
            "| {signal_id} | {coverage_pct:.4f} | {sparsity_profile} | {turnover_proxy_churn} | {turnover_proxy_profile} | {tradability_overlap_pct} | {tradability_buyable_pct} |".format(
                signal_id=r["signal_id"],
                coverage_pct=float(r["coverage_pct"]),
                sparsity_profile=r["sparsity_profile"],
                turnover_proxy_churn=(
                    f"{float(r['turnover_proxy_churn']):.6f}" if pd.notna(r["turnover_proxy_churn"]) else "nan"
                ),
                turnover_proxy_profile=r["turnover_proxy_profile"],
                tradability_overlap_pct=(
                    f"{float(r['tradability_overlap_pct']):.4f}" if pd.notna(r["tradability_overlap_pct"]) else "nan"
                ),
                tradability_buyable_pct=(
                    f"{float(r['tradability_buyable_pct']):.4f}" if pd.notna(r["tradability_buyable_pct"]) else "nan"
                ),
            )
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    specs: dict[str, SignalSpec] = dict(DEFAULT_SIGNAL_SPECS)
    for raw in args.custom_signal:
        spec = parse_custom_signal(raw)
        specs[spec.signal_id] = spec

    signal_ids = [s.strip() for s in str(args.signals).split(",") if s.strip()]
    unknown = [s for s in signal_ids if s not in specs]
    if unknown:
        raise ValueError(f"Unknown signals: {unknown}. Add via --custom-signal or use built-ins: {sorted(specs)}")

    selected_specs = [specs[sid] for sid in signal_ids]

    df = compute_readiness_table(
        specs=selected_specs,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        top_k=int(args.top_k),
    )

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = artifact_path("audits", f"{ts}_signal_execution_readiness")
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "signal_execution_readiness.csv"
    md_path = out_dir / "signal_execution_readiness.md"
    json_path = out_dir / "signal_execution_readiness.json"
    contract_path = out_dir / "signal_promotion_contract.csv"
    contract_json_path = out_dir / "signal_promotion_contract.json"

    df.to_csv(csv_path, index=False)
    md_path.write_text(build_markdown_table(df) + "\n", encoding="utf-8")
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")

    as_of_date = args.contract_as_of_date.strip() or datetime.now().strftime("%Y-%m-%d")
    contract_df = build_promotion_contract(df, as_of_date=as_of_date)
    contract_df.to_csv(contract_path, index=False)
    contract_json_path.write_text(contract_df.to_json(orient="records", indent=2), encoding="utf-8")

    published_csv_path = None
    published_json_path = None
    if args.publish_contract:
        published_csv_path = Path(args.contract_csv_path)
        published_json_path = Path(args.contract_json_path)
        published_csv_path.parent.mkdir(parents=True, exist_ok=True)
        published_json_path.parent.mkdir(parents=True, exist_ok=True)
        contract_df.to_csv(published_csv_path, index=False)
        published_json_path.write_text(contract_df.to_json(orient="records", indent=2), encoding="utf-8")

    print(f"rows={len(df)}")
    print(f"csv={csv_path}")
    print(f"md={md_path}")
    print(f"json={json_path}")
    print(f"contract_csv={contract_path}")
    print(f"contract_json={contract_json_path}")
    if published_csv_path is not None and published_json_path is not None:
        print(f"published_contract_csv={published_csv_path}")
        print(f"published_contract_json={published_json_path}")


if __name__ == "__main__":
    main()
