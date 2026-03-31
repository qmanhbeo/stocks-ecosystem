from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.champion_activation_utils import (
    CURRENT_CHAMPION_REFERENCE_SUMMARY_PATH,
    current_champion_variant,
    load_champion_setup,
    run_champion_variant,
)
from src.champion_branch_experiment_utils import (
    compare_daily_frames,
    jsonable,
    latest_execution_window,
    slice_execution_year,
)
from src.run_summary import write_run_summary

OUT_DIR = ROOT / "artifacts/portfolio_baselines"
OVERLAY_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_live_activation_overlay.json"
SCOREBOARD_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_portfolio_live_activation_scoreboard.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_summary_path(path: Path) -> Path:
    candidates = [
        path,
        ROOT / path,
        ROOT.parent / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(path)


def _metric_deltas(current_summary: dict[str, object], reference_summary: dict[str, object]) -> dict[str, object]:
    metrics = [
        "portfolio_total_return",
        "relative_total_return",
        "information_ratio_annualized",
        "max_drawdown",
        "avg_cash_weight",
        "avg_daily_turnover",
    ]
    deltas: dict[str, object] = {}
    for metric in metrics:
        current = current_summary.get(metric)
        reference = reference_summary.get(metric)
        delta = None
        if current is not None and reference is not None:
            delta = float(current) - float(reference)
        deltas[metric] = {
            "current": jsonable(current),
            "reference": jsonable(reference),
            "delta": jsonable(delta),
        }
    return deltas


def _metrics_within_tolerance(deltas: dict[str, object], *, tolerance: float = 1e-4) -> bool:
    for item in deltas.values():
        delta = item.get("delta")
        if delta is None:
            return False
        if abs(float(delta)) > float(tolerance):
            return False
    return True


def main() -> None:
    spec = current_champion_variant()

    setup_hist = load_champion_setup(start_year=2019, end_year=2025)
    hist_run = run_champion_variant(setup_hist, spec=spec)
    reference_path = _resolve_summary_path(CURRENT_CHAMPION_REFERENCE_SUMMARY_PATH)
    reference_payload = _load_json(reference_path)
    reference_winner = reference_payload["summary"]["winner"]
    reference_deltas = _metric_deltas(hist_run.result.summary, reference_winner)
    reference_pass = _metrics_within_tolerance(reference_deltas)

    setup_live = load_champion_setup(start_year=2019, end_year=2026)
    live_run = run_champion_variant(setup_live, spec=spec, capture_blotter=True)
    direct_overlay_daily = latest_execution_window(live_run.result.daily, execution_days=20)
    direct_scoreboard_daily = slice_execution_year(live_run.result.daily, 2026)

    overlay_path = _resolve_summary_path(OVERLAY_SUMMARY_PATH)
    overlay_payload = _load_json(overlay_path)
    overlay_daily = pd.read_parquet(_resolve_summary_path(Path(overlay_payload["artifacts"]["daily"])))
    overlay_compare = compare_daily_frames(
        direct_overlay_daily,
        overlay_daily,
        on=("signal_date", "execution_date"),
        columns=(
            "activation_on",
            "activation_scale",
            "cash_weight",
            "num_holdings",
            "held_tickers",
            "requested_tickers",
            "turnover",
        ),
    )

    scoreboard_path = _resolve_summary_path(SCOREBOARD_SUMMARY_PATH)
    scoreboard_payload = _load_json(scoreboard_path)
    scoreboard_daily = pd.read_parquet(_resolve_summary_path(Path(scoreboard_payload["artifacts"]["daily"])))
    scoreboard_activated = scoreboard_daily.loc[scoreboard_daily["variant"] == "activated"].drop(columns=["variant"])
    scoreboard_compare = compare_daily_frames(
        direct_scoreboard_daily,
        scoreboard_activated,
        on=("signal_date", "execution_date"),
        columns=(
            "activation_on",
            "activation_scale",
            "cash_weight",
            "num_holdings",
            "held_tickers",
            "requested_tickers",
            "turnover",
        ),
    )

    summary = {
        "spec": {
            "name": spec.name,
            "rel_span": int(spec.rel_span),
            "rel_threshold": float(spec.rel_threshold),
            "incumbent_score_bonus": float(spec.incumbent_score_bonus),
            "blocked_buy_span": spec.blocked_buy_span,
            "blocked_buy_max_quantile": spec.blocked_buy_max_quantile,
            "blocked_buy_off_quantile": spec.blocked_buy_off_quantile,
            "max_names_per_sector": spec.max_names_per_sector,
        },
        "historical_reference_check": {
            "passes": bool(reference_pass),
            "reference_path": str(reference_path),
            "deltas": reference_deltas,
        },
        "overlay_overlap_check": overlay_compare,
        "scoreboard_overlap_check": scoreboard_compare,
        "overall_pass": bool(reference_pass and overlay_compare["matches"] and scoreboard_compare["matches"]),
        "direct_latest_overlay_day": jsonable(
            direct_overlay_daily.sort_values("execution_date").tail(1).iloc[0].to_dict()
        ) if not direct_overlay_daily.empty else {},
        "direct_latest_scoreboard_day": jsonable(
            direct_scoreboard_daily.sort_values("execution_date").tail(1).iloc[0].to_dict()
        ) if not direct_scoreboard_daily.empty else {},
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    direct_overlay_path = OUT_DIR / f"{ts}_h192a_champion_parity_audit_overlay_daily.parquet"
    direct_scoreboard_path = OUT_DIR / f"{ts}_h192a_champion_parity_audit_scoreboard_daily.parquet"
    direct_overlay_daily.to_parquet(direct_overlay_path, index=False)
    direct_scoreboard_daily.to_parquet(direct_scoreboard_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_activation_champion_parity_audit",
        name="h192a_champion_parity_audit",
        summary=summary,
        artifacts={
            "overlay_daily": str(direct_overlay_path),
            "scoreboard_daily": str(direct_scoreboard_path),
        },
        metadata={
            "reference_summary": str(reference_path),
            "overlay_summary": str(overlay_path),
            "scoreboard_summary": str(scoreboard_path),
        },
    )

    print("H192A: CHAMPION PARITY AUDIT")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
