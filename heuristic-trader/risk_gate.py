"""
Tail-first multi-regime exposure gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KillSwitchThresholds:
    drawdown: float = 0.30
    volatility: float = 0.60
    underfill_ratio: float = 0.80
    reject_ratio: float = 0.90


@dataclass
class GateThresholds:
    vol_fragile: float = 0.35
    vol_stress: float = 0.55
    dd_fragile: float = 0.15
    dd_stress: float = 0.28
    underfill_fragile: float = 0.35
    underfill_stress: float = 0.65
    reject_fragile: float = 0.55
    reject_stress: float = 0.80


@dataclass
class GateScales:
    normal: float = 1.00
    fragile: float = 0.55
    stress: float = 0.30


@dataclass
class GateConfig:
    enabled: bool = False
    profile: str = "off"
    exposure_floor: float = 0.20
    exposure_ceiling: float = 1.00
    cooldown_rebalances: int = 2
    kill_switch: KillSwitchThresholds = field(default_factory=KillSwitchThresholds)
    thresholds: GateThresholds = field(default_factory=GateThresholds)
    scales: GateScales = field(default_factory=GateScales)


@dataclass
class GateContext:
    rolling_vol_20: float | None
    drawdown_abs: float
    underfill_ratio: float
    reject_ratio: float
    benchmark_mom_20: float | None = None
    benchmark_mom_60: float | None = None


@dataclass
class GateDecision:
    gate_state: str
    exposure_scale: float
    kill_switch_active: bool
    reason: str
    cooldown_remaining_next: int
    benchmark_state: str


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def build_gate_config(
    *,
    gate_enabled: bool,
    gate_profile: str,
    exposure_floor: float,
    exposure_ceiling: float,
    cooldown_rebalances: int,
    kill_switch_thresholds: dict[str, Any] | None,
) -> GateConfig:
    cfg = GateConfig(
        enabled=bool(gate_enabled),
        profile=str(gate_profile),
        exposure_floor=float(exposure_floor),
        exposure_ceiling=float(exposure_ceiling),
        cooldown_rebalances=max(0, int(cooldown_rebalances)),
    )
    if kill_switch_thresholds:
        ks = cfg.kill_switch
        ks.drawdown = float(kill_switch_thresholds.get("drawdown", ks.drawdown))
        ks.volatility = float(kill_switch_thresholds.get("volatility", ks.volatility))
        ks.underfill_ratio = float(kill_switch_thresholds.get("underfill_ratio", ks.underfill_ratio))
        ks.reject_ratio = float(kill_switch_thresholds.get("reject_ratio", ks.reject_ratio))
    if cfg.exposure_floor > cfg.exposure_ceiling:
        cfg.exposure_floor = cfg.exposure_ceiling
    return cfg


def _benchmark_state(m20: float | None, m60: float | None) -> str:
    if m20 is None or m60 is None:
        return "unknown"
    if m20 > 0 and m60 > 0:
        return "trend_bull"
    if m20 < 0 and m60 < 0:
        return "trend_bear"
    return "chop"


def _severity_state(ctx: GateContext, cfg: GateConfig) -> tuple[str, list[str]]:
    t = cfg.thresholds
    reasons: list[str] = []
    stress = False
    fragile = False

    if ctx.rolling_vol_20 is not None:
        if ctx.rolling_vol_20 >= t.vol_stress:
            stress = True
            reasons.append("vol_stress")
        elif ctx.rolling_vol_20 >= t.vol_fragile:
            fragile = True
            reasons.append("vol_fragile")

    if ctx.drawdown_abs >= t.dd_stress:
        stress = True
        reasons.append("dd_stress")
    elif ctx.drawdown_abs >= t.dd_fragile:
        fragile = True
        reasons.append("dd_fragile")

    if ctx.underfill_ratio >= t.underfill_stress:
        stress = True
        reasons.append("underfill_stress")
    elif ctx.underfill_ratio >= t.underfill_fragile:
        fragile = True
        reasons.append("underfill_fragile")

    if ctx.reject_ratio >= t.reject_stress:
        stress = True
        reasons.append("reject_stress")
    elif ctx.reject_ratio >= t.reject_fragile:
        fragile = True
        reasons.append("reject_fragile")

    if stress:
        return "stress", reasons
    if fragile:
        return "fragile", reasons
    return "normal", reasons


def _killswitch_triggered(ctx: GateContext, cfg: GateConfig) -> tuple[bool, list[str]]:
    ks = cfg.kill_switch
    reasons: list[str] = []
    if ctx.drawdown_abs >= ks.drawdown:
        reasons.append("kill_drawdown")
    if ctx.rolling_vol_20 is not None and ctx.rolling_vol_20 >= ks.volatility:
        reasons.append("kill_volatility")
    if ctx.underfill_ratio >= ks.underfill_ratio:
        reasons.append("kill_underfill")
    if ctx.reject_ratio >= ks.reject_ratio:
        reasons.append("kill_reject")
    return len(reasons) > 0, reasons


def evaluate_gate(
    *,
    context: GateContext,
    config: GateConfig,
    cooldown_remaining: int,
) -> GateDecision:
    if not config.enabled or config.profile == "off":
        return GateDecision(
            gate_state="disabled",
            exposure_scale=1.0,
            kill_switch_active=False,
            reason="gate_disabled",
            cooldown_remaining_next=0,
            benchmark_state="unknown",
        )

    benchmark_state = _benchmark_state(context.benchmark_mom_20, context.benchmark_mom_60)
    base_state, base_reasons = _severity_state(context, config)
    triggered, kill_reasons = _killswitch_triggered(context, config)
    kill_active = False
    next_cooldown = max(0, int(cooldown_remaining))

    if next_cooldown > 0:
        kill_active = True
        next_cooldown -= 1
    elif triggered:
        kill_active = True
        next_cooldown = max(0, config.cooldown_rebalances - 1)

    scales = config.scales
    if kill_active:
        state = "stress"
        scale = min(scales.stress, config.exposure_floor)
        reasons = ["kill_cooldown" if cooldown_remaining > 0 else "kill_trigger"] + kill_reasons
    else:
        state = base_state
        if state == "stress":
            scale = scales.stress
        elif state == "fragile":
            scale = scales.fragile
        else:
            scale = scales.normal
        reasons = list(base_reasons)

    # Trend-aware modifier (tail-first: de-risk bear/chop, no leverage in bull)
    if benchmark_state == "trend_bear":
        scale *= 0.80
        reasons.append("trend_bear_de_risk")
    elif benchmark_state == "chop":
        scale *= 0.90
        reasons.append("chop_de_risk")

    scale = _clip(scale, config.exposure_floor, config.exposure_ceiling)
    reason = "|".join(sorted(set(reasons))) if reasons else "normal"
    return GateDecision(
        gate_state=state,
        exposure_scale=float(scale),
        kill_switch_active=kill_active,
        reason=reason,
        cooldown_remaining_next=next_cooldown,
        benchmark_state=benchmark_state,
    )
