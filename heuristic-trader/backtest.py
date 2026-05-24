"""
Constraint-compliant backtest engine.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import constraints as c
from risk_gate import GateContext, build_gate_config, evaluate_gate

_DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR = _DEFAULT_CACHE_DIR
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"


@dataclass
class BacktestResult:
    name: str
    total_return: float
    annualized_return: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    curve: pd.DataFrame
    constraints_followed: str = "N/A"
    n_filtered: int = 0
    diagnostics: Optional[dict] = None


@dataclass
class Diagnostics:
    trade_log: pd.DataFrame
    selection_log: pd.DataFrame
    filtered_breakdown: pd.DataFrame


# === Pre-computed lookup helpers ===

def load_liquid_lookup() -> dict:
    """Load cached liquid date->tickers lookup."""
    import joblib
    if LIQUID_CACHE_FILE.exists():
        return joblib.load(LIQUID_CACHE_FILE)
    return {}


def load_trad_lookup() -> dict:
    """Load cached tradability (ticker,date)->can_buy lookup."""
    import joblib
    if TRAD_CACHE_FILE.exists():
        return joblib.load(TRAD_CACHE_FILE)
    return {}


def is_liquid(ticker: str, date, liquid_lookup: dict) -> bool:
    """Fast liquid check using pre-computed lookup.
    
    Returns True only if:
    - date IS in lookup AND ticker IS in the liquid set for that date
    """
    if date not in liquid_lookup:
        return False  # No data = NOT liquid
    return ticker in liquid_lookup.get(date, set())


def can_buy_fast(ticker: str, date, trad_lookup: dict) -> bool:
    """Fast tradability check using pre-computed lookup.
    
    Returns True only if:
    - (ticker, date) IS in lookup AND can_buy is True
    """
    if (ticker, date) not in trad_lookup:
        return False  # No data = NOT allowed
    return bool(trad_lookup.get((ticker, date), False))


# === Price lookups ===

def load_price_cache() -> dict[str, pd.DataFrame]:
    """Load cached price data."""
    if PRICE_CACHE_FILE.exists():
        pc = pd.read_parquet(PRICE_CACHE_FILE)
        return {t: g.set_index("time") for t, g in pc.groupby("ticker")}
    return {}


def get_price(cache: dict, ticker: str, date, price_type: str = "close") -> float | None:
    """Get price for ticker at date."""
    if ticker not in cache:
        return None
    try:
        return float(cache[ticker].loc[date, price_type])
    except KeyError:
        return None


# === Legacy filter functions (for when pre-computed not available) ===

def check_liquid(cache: dict, ticker: str, date, min_volume: int = 500_000) -> bool:
    """Check liquidity (legacy - compute on the fly).
    
    HARD RULE: "No exact ticker-date row, no claim."
    - Missing ticker: returns False (fail closed)
    - Missing date: returns False (no fallback to previous/nearest/last date)
    - Fallback can create stale/lookahead-like liquidity claims
    - Cache promotion requires parity with this behavior
    """
    if ticker not in cache:
        return False
    try:
        df = cache[ticker]
        dates_sorted = sorted(df.index)
        if date not in dates_sorted:
            return False  # Fail closed - no fallback
        idx = dates_sorted.index(date)
        start_idx = max(0, idx - 5)
        recent = df.iloc[start_idx:idx+1]
        if len(recent) < 3:
            return False
        avg_volume = recent['volume'].mean()
        if avg_volume < min_volume:
            return False
        if len(recent) >= 2:
            price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
            if price_change < 0.001:
                return False
        return True
    except:
        return False


def check_can_buy(tradability_df: pd.DataFrame | None, ticker: str, date) -> bool:
    """Check can_buy_next_open (legacy - compute on the fly)."""
    if tradability_df is None:
        return True
    try:
        row = tradability_df[(tradability_df['time'] == date) & (tradability_df['ticker'] == ticker)]
        if len(row) == 0:
            return False
        return bool(row['can_buy_next_open'].iloc[0])
    except:
        return True


def _build_benchmark_context(start_date, end_date) -> dict[pd.Timestamp, dict[str, float]]:
    """Build VNINDEX rolling-momentum context keyed by normalized date."""
    try:
        vn = c.load_vnindex(start=str(pd.Timestamp(start_date).date()), end=str(pd.Timestamp(end_date).date()))
    except Exception:
        return {}
    if vn is None or len(vn) == 0:
        return {}
    df = vn.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["time"]).sort_values("time")
    if len(df) == 0:
        return {}
    df["mom_20"] = df["open"].pct_change(20)
    df["mom_60"] = df["open"].pct_change(60)
    out: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in df.iterrows():
        out[pd.Timestamp(row["time"]).normalize()] = {
            "mom_20": float(row["mom_20"]) if pd.notna(row["mom_20"]) else float("nan"),
            "mom_60": float(row["mom_60"]) if pd.notna(row["mom_60"]) else float("nan"),
        }
    return out


def _safe_signal(v: Any) -> float:
    try:
        out = float(v)
    except Exception:
        return float("-inf")
    if pd.isna(out):
        return float("-inf")
    return out


def _with_incumbent_bonus(signal_value: float, bonus_bps: float) -> float:
    if signal_value == float("-inf") or bonus_bps <= 0:
        return signal_value
    bonus_scale = bonus_bps / 10_000.0
    return signal_value + abs(signal_value) * bonus_scale


def _resolve_regime_override(
    *,
    base_value: Any,
    key: str,
    regime_translation: dict[str, Any] | None,
    gate_state: str,
    benchmark_state: str,
) -> Any:
    if not regime_translation:
        return base_value
    value = base_value
    by_gate = regime_translation.get("by_gate_state")
    by_bench = regime_translation.get("by_benchmark_state")
    if isinstance(by_gate, dict):
        gate_cfg = by_gate.get(gate_state, {})
        if isinstance(gate_cfg, dict) and key in gate_cfg:
            value = gate_cfg[key]
    if isinstance(by_bench, dict):
        bench_cfg = by_bench.get(benchmark_state, {})
        if isinstance(bench_cfg, dict) and key in bench_cfg:
            value = bench_cfg[key]
    direct_gate_cfg = regime_translation.get(gate_state, {})
    if isinstance(direct_gate_cfg, dict) and key in direct_gate_cfg:
        value = direct_gate_cfg[key]
    direct_bench_cfg = regime_translation.get(benchmark_state, {})
    if isinstance(direct_bench_cfg, dict) and key in direct_bench_cfg:
        value = direct_bench_cfg[key]
    return value


def _target_slots_from_mode(top_k: int, exposure_scale: float, mode: str) -> int:
    if mode == "dynamic_by_gate":
        return int(max(1, min(top_k, round(top_k * float(exposure_scale)))))
    return int(max(1, top_k))


def _conviction_weights(
    ranked_scores: list[tuple[str, float]],
    mode: str,
    strength: float,
    cap: float,
) -> dict[str, float]:
    if len(ranked_scores) == 0:
        return {}
    if mode != "rank_gap" or len(ranked_scores) == 1 or strength <= 0:
        return {t: 1.0 / len(ranked_scores) for t, _ in ranked_scores}
    cap = max(1.0, float(cap))
    out: dict[str, float] = {}
    top_score = ranked_scores[0][1]
    raw_weights: list[float] = []
    tickers: list[str] = []
    for ticker, score in ranked_scores:
        gap = max(0.0, top_score - score)
        raw = 1.0 / (1.0 + float(strength) * gap)
        raw_weights.append(float(min(cap, max(1e-6, raw))))
        tickers.append(ticker)
    weight_sum = float(sum(raw_weights))
    if weight_sum <= 0:
        return {t: 1.0 / len(ranked_scores) for t, _ in ranked_scores}
    for ticker, w in zip(tickers, raw_weights):
        out[ticker] = float(w / weight_sum)
    return out


# === Main backtest function ===

def simulate_topk_constraint_compliant(
    signal_df: pd.DataFrame,
    cache: dict[str, pd.DataFrame],
    signal_col: str = "s1_proba",
    top_k: int = 5,
    rebalance_days: int = 5,
    min_hold_days: int = 3,
    initial_capital: float = 1_000_000_000.0,
    buy_fee: float = c.DEFAULT_BUY_FEE_RATE,
    sell_fee: float = c.DEFAULT_SELL_FEE_RATE,
    tradability_df: pd.DataFrame | None = None,
    min_volume: int = 500_000,
    use_filters: bool = True,
    liquid_lookup: dict | None = None,
    trad_lookup: dict | None = None,
    collect_diagnostics: bool = False,
    candidate_scan_multiplier: int = 3,
    sizing_mode: str = "fixed_initial",
    fallback_mode: str = "none",
    gate_enabled: bool = False,
    gate_profile: str = "off",
    exposure_floor: float = 0.20,
    exposure_ceiling: float = 1.00,
    kill_switch_thresholds: dict | None = None,
    cooldown_rebalances: int = 2,
    incumbent_bonus_bps: float = 0.0,
    replace_threshold_bps: float = 0.0,
    max_new_positions_per_rebalance: int | None = None,
    underfill_recovery_days: int = 0,
    recovery_target_slots_mode: str = "fixed_target",
    regime_translation: dict | None = None,
    conviction_mode: str = "off",
    conviction_strength: float = 0.0,
    conviction_cap: float = 2.0,
) -> BacktestResult:
    """Constraint-compliant top-K by signal backtest."""

    signal_df = signal_df.sort_values("time").reset_index(drop=True)
    dates = sorted(signal_df["time"].unique())
    valid_fallback_modes = {"none", "reallocate_selected"}
    if fallback_mode not in valid_fallback_modes:
        allowed = ", ".join(sorted(valid_fallback_modes))
        raise ValueError(f"Unknown fallback_mode '{fallback_mode}'. Allowed values: {allowed}")
    valid_recovery_modes = {"fixed_target", "dynamic_by_gate"}
    if recovery_target_slots_mode not in valid_recovery_modes:
        allowed = ", ".join(sorted(valid_recovery_modes))
        raise ValueError(
            f"Unknown recovery_target_slots_mode '{recovery_target_slots_mode}'. "
            f"Allowed values: {allowed}"
        )
    valid_conviction_modes = {"off", "rank_gap"}
    if conviction_mode not in valid_conviction_modes:
        allowed = ", ".join(sorted(valid_conviction_modes))
        raise ValueError(f"Unknown conviction_mode '{conviction_mode}'. Allowed values: {allowed}")

    if len(dates) < 2:
        return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())

    holdings: dict[str, tuple[int, int]] = {}
    cash = initial_capital
    equity_curve = []
    n_trades = 0
    n_skips = 0
    n_filtered = 0

    diagnostics_trades = []
    diagnostics_selections = []
    diagnostics_filtered = []
    diagnostics_fallback = []
    diagnostics_gate = []

    gate_cfg = build_gate_config(
        gate_enabled=gate_enabled,
        gate_profile=gate_profile,
        exposure_floor=exposure_floor,
        exposure_ceiling=exposure_ceiling,
        cooldown_rebalances=cooldown_rebalances,
        kill_switch_thresholds=kill_switch_thresholds,
    )
    cooldown_remaining = 0
    current_gate_state = "disabled" if not gate_cfg.enabled else "normal"
    current_exposure_scale = 1.0
    current_kill_switch_active = False
    current_gate_reason = "gate_disabled" if not gate_cfg.enabled else "init"
    current_benchmark_state = "unknown"
    next_rebalance_i = max(1, int(rebalance_days))
    recovery_backlog_slots = 0
    recovery_window_remaining = 0
    benchmark_context = (
        _build_benchmark_context(dates[0], dates[-1])
        if gate_cfg.enabled and len(dates) > 0
        else {}
    )

    for i, date in enumerate(dates):
        day_df = signal_df[signal_df["time"] == date]
        if len(day_df) == 0:
            continue

        # REBALANCE on dynamic schedule (defaults to fixed cadence)
        if i > 0 and i >= next_rebalance_i:
            prev_date = dates[i - 1]
            pre_rebalance_holdings = set(holdings.keys())
            active_rebalance_days = int(
                _resolve_regime_override(
                    base_value=rebalance_days,
                    key="rebalance_interval_days",
                    regime_translation=regime_translation,
                    gate_state=current_gate_state,
                    benchmark_state=current_benchmark_state,
                )
            )
            active_rebalance_days = max(1, active_rebalance_days)
            next_rebalance_i = i + active_rebalance_days

            signal_day_df = signal_df[signal_df["time"] == prev_date]
            signal_map: dict[str, float] = {
                str(row["ticker"]): _safe_signal(row[signal_col])
                for _, row in signal_day_df[["ticker", signal_col]].iterrows()
            }

            active_scan_multiplier = int(
                _resolve_regime_override(
                    base_value=candidate_scan_multiplier,
                    key="candidate_scan_multiplier",
                    regime_translation=regime_translation,
                    gate_state=current_gate_state,
                    benchmark_state=current_benchmark_state,
                )
            )
            active_scan_multiplier = max(1, active_scan_multiplier)
            n_candidates_to_scan = top_k * active_scan_multiplier

            selected_candidates: list[str] = []
            candidate_scores: dict[str, float] = {}
            n_filtered_liq = 0
            n_filtered_trad = 0
            for rank, (_, row) in enumerate(signal_day_df.nlargest(n_candidates_to_scan, signal_col).iterrows()):
                ticker = row["ticker"]
                signal_val = _safe_signal(row.get(signal_col, None))
                
                # Check tradability
                if use_filters:
                    if trad_lookup is not None:
                        if not can_buy_fast(ticker, prev_date, trad_lookup):
                            n_filtered += 1
                            n_filtered_trad += 1
                            passed_trad = False
                            if collect_diagnostics:
                                diagnostics_selections.append({
                                    "rebalance_date": prev_date,
                                    "ticker": ticker,
                                    "signal": signal_val,
                                    "rank": rank + 1,
                                    "passed_liquidity": True,
                                    "passed_tradability": False,
                                    "selected": False,
                                    "final_selected": False,
                                    "selection_stage": "filter",
                                    "filter_reason": "tradability",
                                })
                            continue
                    elif tradability_df is not None:
                        if not check_can_buy(tradability_df, ticker, prev_date):
                            n_filtered += 1
                            n_filtered_trad += 1
                            passed_trad = False
                            if collect_diagnostics:
                                diagnostics_selections.append({
                                    "rebalance_date": prev_date,
                                    "ticker": ticker,
                                    "signal": signal_val,
                                    "rank": rank + 1,
                                    "passed_liquidity": True,
                                    "passed_tradability": False,
                                    "selected": False,
                                    "final_selected": False,
                                    "selection_stage": "filter",
                                    "filter_reason": "tradability",
                                })
                            continue
                
                # Check liquidity
                if use_filters:
                    if liquid_lookup is not None:
                        if not is_liquid(ticker, prev_date, liquid_lookup):
                            n_filtered += 1
                            n_filtered_liq += 1
                            passed_liq = False
                            if collect_diagnostics:
                                diagnostics_selections.append({
                                    "rebalance_date": prev_date,
                                    "ticker": ticker,
                                    "signal": signal_val,
                                    "rank": rank + 1,
                                    "passed_liquidity": False,
                                    "passed_tradability": True,
                                    "selected": False,
                                    "final_selected": False,
                                    "selection_stage": "filter",
                                    "filter_reason": "liquidity",
                                })
                            continue
                    elif not check_liquid(cache, ticker, prev_date, min_volume):
                        n_filtered += 1
                        n_filtered_liq += 1
                        passed_liq = False
                        if collect_diagnostics:
                            diagnostics_selections.append({
                                "rebalance_date": prev_date,
                                "ticker": ticker,
                                "signal": signal_val,
                                "rank": rank + 1,
                                "passed_liquidity": False,
                                "passed_tradability": True,
                                "selected": False,
                                "final_selected": False,
                                "selection_stage": "filter",
                                "filter_reason": "liquidity",
                            })
                        continue

                if ticker not in selected_candidates:
                    selected_candidates.append(ticker)
                    candidate_scores[ticker] = signal_val

                if collect_diagnostics:
                    diagnostics_selections.append({
                        "rebalance_date": prev_date,
                        "ticker": ticker,
                        "signal": signal_val,
                        "rank": rank + 1,
                        "passed_liquidity": True,
                        "passed_tradability": True,
                        "selected": True,
                        "final_selected": False,
                        "selection_stage": "scan_pass",
                        "filter_reason": None,
                    })

            if collect_diagnostics:
                diagnostics_filtered.append({
                    "rebalance_date": prev_date,
                    "n_candidates": n_candidates_to_scan,
                    "n_filtered_liquidity": n_filtered_liq,
                    "n_filtered_tradability": n_filtered_trad,
                    "n_selected": min(len(selected_candidates), top_k),
                    "scan_multiplier_active": active_scan_multiplier,
                })

            holdings_value_before_buys = 0.0
            for t, (shares, _) in holdings.items():
                prev_close_price = get_price(cache, t, prev_date, "close")
                if prev_close_price:
                    holdings_value_before_buys += shares * prev_close_price
            cash_before_buys = cash
            current_portfolio_value = cash_before_buys + holdings_value_before_buys

            desired_slots = _target_slots_from_mode(
                top_k=top_k,
                exposure_scale=current_exposure_scale,
                mode=recovery_target_slots_mode,
            )
            recovery_additional_slots = 0
            if recovery_backlog_slots > 0 and recovery_window_remaining > 0:
                recovery_additional_slots = int(recovery_backlog_slots)
                recovery_window_remaining = max(0, recovery_window_remaining - 1)
            target_slots = int(min(top_k, desired_slots + recovery_additional_slots))

            active_max_new_positions = _resolve_regime_override(
                base_value=max_new_positions_per_rebalance,
                key="max_new_positions_per_rebalance",
                regime_translation=regime_translation,
                gate_state=current_gate_state,
                benchmark_state=current_benchmark_state,
            )
            if active_max_new_positions is None:
                max_new_this_rebalance = None
            else:
                max_new_this_rebalance = max(0, int(active_max_new_positions))

            locked_incumbents: list[str] = []
            replaceable_incumbents: list[str] = []
            incumbent_scores: dict[str, float] = {}
            for ticker, (_, entry_idx) in holdings.items():
                hold_days = i - entry_idx
                incumbent_scores[ticker] = _safe_signal(signal_map.get(ticker, float("-inf")))
                if hold_days < min_hold_days:
                    locked_incumbents.append(ticker)
                else:
                    replaceable_incumbents.append(ticker)

            replaceable_incumbents = sorted(
                replaceable_incumbents,
                key=lambda t: _with_incumbent_bonus(incumbent_scores.get(t, float("-inf")), incumbent_bonus_bps),
                reverse=True,
            )
            challengers = [t for t in selected_candidates if t not in holdings]
            challengers = sorted(challengers, key=lambda t: candidate_scores.get(t, float("-inf")), reverse=True)

            selected_tickers: list[str] = list(locked_incumbents[:target_slots])
            selected_set = set(selected_tickers)
            slots_remaining = max(0, target_slots - len(selected_tickers))
            incumbent_pool = list(replaceable_incumbents)
            challenger_idx = 0
            incumbent_idx = 0
            new_positions_added = 0
            replace_threshold = max(0.0, float(replace_threshold_bps) / 10_000.0)

            while slots_remaining > 0:
                inc = incumbent_pool[incumbent_idx] if incumbent_idx < len(incumbent_pool) else None
                ch = challengers[challenger_idx] if challenger_idx < len(challengers) else None
                inc_score = (
                    _with_incumbent_bonus(incumbent_scores.get(inc, float("-inf")), incumbent_bonus_bps)
                    if inc is not None
                    else float("-inf")
                )
                ch_score = candidate_scores.get(ch, float("-inf")) if ch is not None else float("-inf")
                challenger_allowed = (
                    ch is not None
                    and (max_new_this_rebalance is None or new_positions_added < max_new_this_rebalance)
                )
                choose_challenger = False
                if challenger_allowed:
                    if inc is None:
                        choose_challenger = True
                    else:
                        threshold = inc_score + abs(inc_score) * replace_threshold
                        choose_challenger = ch_score >= threshold
                if choose_challenger:
                    if ch not in selected_set:
                        selected_tickers.append(ch)
                        selected_set.add(ch)
                        new_positions_added += 1
                        slots_remaining -= 1
                    challenger_idx += 1
                    continue
                if inc is not None:
                    if inc not in selected_set:
                        selected_tickers.append(inc)
                        selected_set.add(inc)
                        slots_remaining -= 1
                    incumbent_idx += 1
                    continue
                if ch is not None and challenger_allowed:
                    if ch not in selected_set:
                        selected_tickers.append(ch)
                        selected_set.add(ch)
                        new_positions_added += 1
                        slots_remaining -= 1
                    challenger_idx += 1
                    continue
                break

            selected_tickers = selected_tickers[:target_slots]
            selected_set = set(selected_tickers)
            selected_count = len(selected_tickers)
            effective_target_slots = max(1, min(top_k, target_slots))

            if sizing_mode == "fixed_initial":
                default_target_position_value = initial_capital / top_k
            else:  # dynamic_portfolio
                default_target_position_value = current_portfolio_value / top_k

            fallback_triggered = (
                fallback_mode == "reallocate_selected"
                and selected_count > 0
                and selected_count < effective_target_slots
            )
            if fallback_mode == "reallocate_selected" and selected_count > 0:
                if sizing_mode == "fixed_initial":
                    target_position_value = initial_capital / selected_count
                else:  # dynamic_portfolio
                    target_position_value = current_portfolio_value / selected_count
            else:
                target_position_value = default_target_position_value

            n_candidates_scan = n_candidates_to_scan
            reject_ratio = (
                float(n_filtered_liq + n_filtered_trad) / float(n_candidates_scan)
                if n_candidates_scan > 0
                else 0.0
            )
            underfill_ratio = (
                float(max(0, effective_target_slots - selected_count)) / float(effective_target_slots)
                if effective_target_slots > 0
                else 0.0
            )
            if len(equity_curve) >= 21:
                hist = pd.DataFrame(equity_curve)
                recent = hist["portfolio_value"].pct_change().dropna().tail(20)
                rolling_vol_20 = (
                    float(recent.std() * np.sqrt(252))
                    if len(recent) > 1 and recent.std() > 0
                    else None
                )
                current_dd = float(hist["portfolio_value"].iloc[-1] / hist["portfolio_value"].cummax().iloc[-1] - 1.0)
                drawdown_abs = abs(min(0.0, current_dd))
            else:
                rolling_vol_20 = None
                drawdown_abs = 0.0

            bench = benchmark_context.get(pd.Timestamp(prev_date).normalize(), {})
            mom_20 = None if pd.isna(bench.get("mom_20", np.nan)) else float(bench.get("mom_20"))
            mom_60 = None if pd.isna(bench.get("mom_60", np.nan)) else float(bench.get("mom_60"))

            gate_decision = evaluate_gate(
                context=GateContext(
                    rolling_vol_20=rolling_vol_20,
                    drawdown_abs=drawdown_abs,
                    underfill_ratio=underfill_ratio,
                    reject_ratio=reject_ratio,
                    benchmark_mom_20=mom_20,
                    benchmark_mom_60=mom_60,
                ),
                config=gate_cfg,
                cooldown_remaining=cooldown_remaining,
            )
            cooldown_remaining = gate_decision.cooldown_remaining_next
            current_gate_state = gate_decision.gate_state
            current_exposure_scale = gate_decision.exposure_scale
            current_kill_switch_active = gate_decision.kill_switch_active
            current_gate_reason = gate_decision.reason
            current_benchmark_state = gate_decision.benchmark_state
            target_position_value *= current_exposure_scale

            deficit = max(0, desired_slots - selected_count)
            if underfill_recovery_days > 0:
                if deficit > 0:
                    recovery_backlog_slots = min(top_k, recovery_backlog_slots + deficit)
                    recovery_window_remaining = max(recovery_window_remaining, int(underfill_recovery_days))
                elif recovery_backlog_slots > 0 and selected_count >= desired_slots:
                    recovered = max(0, selected_count - desired_slots)
                    recovery_backlog_slots = max(0, recovery_backlog_slots - recovered)
                    if recovery_backlog_slots == 0:
                        recovery_window_remaining = 0

            if collect_diagnostics:
                diagnostics_gate.append(
                    {
                        "rebalance_date": prev_date,
                        "gate_state": current_gate_state,
                        "exposure_scale": current_exposure_scale,
                        "kill_switch_active": current_kill_switch_active,
                        "gate_reason": current_gate_reason,
                        "cooldown_remaining": cooldown_remaining,
                        "benchmark_state": current_benchmark_state,
                        "rolling_vol_20": rolling_vol_20,
                        "drawdown_abs": drawdown_abs,
                        "underfill_ratio": underfill_ratio,
                        "reject_ratio": reject_ratio,
                        "selected_count": selected_count,
                        "desired_slots": desired_slots,
                        "target_slots": target_slots,
                        "scan_multiplier_active": active_scan_multiplier,
                        "rebalance_days_active": active_rebalance_days,
                        "max_new_positions_active": (
                            max_new_this_rebalance if max_new_this_rebalance is not None else -1
                        ),
                    }
                )

            if collect_diagnostics:
                diagnostics_fallback.append({
                    "rebalance_date": prev_date,
                    "fallback_mode": fallback_mode,
                    "fallback_triggered": fallback_triggered,
                    "selected_count": selected_count,
                    "top_k": top_k,
                    "sizing_mode": sizing_mode,
                    "target_position_value": target_position_value,
                    "default_target_position_value": default_target_position_value,
                    "current_portfolio_value": current_portfolio_value,
                    "cash_before_buys": cash_before_buys,
                    "holdings_value_before_buys": holdings_value_before_buys,
                    "desired_slots": desired_slots,
                    "target_slots": target_slots,
                    "recovery_backlog_slots": recovery_backlog_slots,
                    "recovery_window_remaining": recovery_window_remaining,
                    "new_positions_selected": new_positions_added,
                    "max_new_positions_active": (
                        max_new_this_rebalance if max_new_this_rebalance is not None else -1
                    ),
                })

            # SELL positions not selected and eligible for sell
            for ticker in list(holdings.keys()):
                if ticker in selected_set:
                    continue
                shares, entry_idx = holdings[ticker]
                hold_days = i - entry_idx
                if hold_days < min_hold_days:
                    continue
                open_price = get_price(cache, ticker, prev_date, "open")
                if open_price and open_price > 0:
                    sell_value = shares * open_price * (1 - sell_fee)
                    cash += sell_value
                    n_trades += 1
                    if collect_diagnostics:
                        fee = shares * open_price * sell_fee
                        diagnostics_trades.append({
                            "date": prev_date,
                            "action": "SELL",
                            "ticker": ticker,
                            "price": open_price,
                            "shares": shares,
                            "value": shares * open_price,
                            "fee": fee,
                            "reason": "rebalance_replace",
                        })
                else:
                    n_skips += 1
                del holdings[ticker]

            ordered_selected = sorted(
                selected_tickers,
                key=lambda t: (
                    1 if t in pre_rebalance_holdings else 0,
                    candidate_scores.get(t, incumbent_scores.get(t, float("-inf"))),
                ),
                reverse=True,
            )
            conviction_ranked = [
                (t, candidate_scores.get(t, incumbent_scores.get(t, float("-inf"))))
                for t in ordered_selected
                if t not in holdings
            ]
            conviction_weights = _conviction_weights(
                ranked_scores=conviction_ranked,
                mode=conviction_mode,
                strength=float(conviction_strength),
                cap=float(conviction_cap),
            )

            for ticker in ordered_selected:
                if ticker in holdings:
                    continue

                open_price = get_price(cache, ticker, date, "open")
                if open_price and open_price > 0 and cash > 0:
                    alloc_weight = conviction_weights.get(ticker, 1.0 / max(1, len(conviction_ranked)))
                    position_value = target_position_value * alloc_weight * max(1, len(conviction_ranked))
                    shares = int(position_value / open_price)
                    if shares > 0:
                        cost = shares * open_price * (1 + buy_fee)
                        if cash >= cost:
                            cash -= cost
                            holdings[ticker] = (shares, i)
                            n_trades += 1
                            if collect_diagnostics:
                                fee = shares * open_price * buy_fee
                                diagnostics_trades.append({
                                    "date": date,
                                    "action": "BUY",
                                    "ticker": ticker,
                                    "price": open_price,
                                    "shares": shares,
                                    "value": shares * open_price,
                                    "fee": fee,
                                    "reason": "rebalance",
                                    "conviction_weight": alloc_weight,
                                })

            if collect_diagnostics and len(diagnostics_selections) > 0:
                sel_df = pd.DataFrame(diagnostics_selections)
                mask = sel_df["rebalance_date"] == prev_date
                if mask.any():
                    idxs = sel_df[mask & sel_df["ticker"].isin(selected_set)].index
                    if len(idxs) > 0:
                        for idx in idxs:
                            diagnostics_selections[idx]["final_selected"] = True
                            diagnostics_selections[idx]["selection_stage"] = "final_selection"

        # Calculate portfolio value
        holdings_value = 0
        for ticker, (shares, _) in holdings.items():
            close_price = get_price(cache, ticker, date, "close")
            if close_price:
                holdings_value += shares * close_price

        portfolio_value = cash + holdings_value
        equity_curve.append({
            "date": date,
            "portfolio_value": portfolio_value,
            "cash": cash,
            "holdings_value": holdings_value,
            "n_holdings": len(holdings),
            "gate_state": current_gate_state,
            "exposure_scale": current_exposure_scale,
            "kill_switch_active": current_kill_switch_active,
            "gate_reason": current_gate_reason,
            "cooldown_remaining": cooldown_remaining,
            "benchmark_state": current_benchmark_state,
            "recovery_backlog_slots": recovery_backlog_slots,
            "recovery_window_remaining": recovery_window_remaining,
        })

    curve = pd.DataFrame(equity_curve)
    if len(curve) == 0:
        return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())

    curve["return_pct"] = curve["portfolio_value"].pct_change()
    curve["return"] = curve["portfolio_value"] / initial_capital - 1.0
    
    ret = curve["return"].iloc[-1]
    returns = curve["return_pct"].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (curve["portfolio_value"] / curve["portfolio_value"].cummax() - 1.0).min()

    diagnostics_dict = None
    if collect_diagnostics:
        diagnostics_dict = {
            "trade_log": pd.DataFrame(diagnostics_trades) if diagnostics_trades else pd.DataFrame(),
            "selection_log": pd.DataFrame(diagnostics_selections) if diagnostics_selections else pd.DataFrame(),
            "filtered_breakdown": pd.DataFrame(diagnostics_filtered) if diagnostics_filtered else pd.DataFrame(),
            "fallback_log": pd.DataFrame(diagnostics_fallback) if diagnostics_fallback else pd.DataFrame(),
            "gate_log": pd.DataFrame(diagnostics_gate) if diagnostics_gate else pd.DataFrame(),
        }

    return BacktestResult(
        f"TopK_{signal_col}_K{top_k}_R{rebalance_days}_H{min_hold_days}",
        ret,
        ret / (len(curve) / 252) if len(curve) > 0 else 0,
        sharpe,
        max_dd,
        n_trades,
        curve,
        n_filtered=n_filtered,
        diagnostics=diagnostics_dict,
    )


def get_cached_vnindex() -> BacktestResult:
    """Get VNINDEX baseline (cached)."""
    import signals as s
    
    VNINDEX_FILE = CACHE_DIR / "vnindex_baseline.parquet"
    if VNINDEX_FILE.exists():
        df = pd.read_parquet(VNINDEX_FILE)
    else:
        import constraints as cn
        vn = cn.load_vnindex(start="2019-01-01", end="2025-12-31")
        if len(vn) == 0:
            return BacktestResult("", 0, 0, 0, 0, 0, pd.DataFrame())
        
        start_open = vn["open"].iloc[0]
        end_open = vn["open"].iloc[-1]
        shares = int(100_000_000 / start_open)
        cost = shares * start_open * 1.001
        initial_cash = 100_000_000 - cost
        proceeds = shares * end_open * 0.9984
        final_value = initial_cash + proceeds
        ret = (final_value / 100_000_000) - 1.0
        
        curve = vn[["time", "open"]].copy()
        curve["holdings_value"] = curve["open"] * shares
        curve["cash"] = initial_cash
        curve["portfolio_value"] = curve["cash"] + curve["holdings_value"]
        curve["return"] = curve["portfolio_value"] / 100_000_000 - 1.0
        curve["return_pct"] = curve["portfolio_value"].pct_change()
        
        df = curve
        df.to_parquet(VNINDEX_FILE)
    
    import numpy as np
    returns = df["return_pct"].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (df["portfolio_value"] / df["portfolio_value"].cummax() - 1.0).min()
    
    return BacktestResult(
        "VNINDEX_hold",
        df["return"].iloc[-1],
        df["return"].iloc[-1] / (len(df) / 252) if len(df) > 0 else 0,
        sharpe,
        max_dd,
        2,
        df,
    )
