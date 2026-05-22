import math

from risk_gate import GateContext, build_gate_config, evaluate_gate


def test_gate_disabled_returns_identity_scale() -> None:
    cfg = build_gate_config(
        gate_enabled=False,
        gate_profile="off",
        exposure_floor=0.2,
        exposure_ceiling=1.0,
        cooldown_rebalances=2,
        kill_switch_thresholds=None,
    )
    d = evaluate_gate(
        context=GateContext(
            rolling_vol_20=0.9,
            drawdown_abs=0.4,
            underfill_ratio=0.9,
            reject_ratio=0.9,
        ),
        config=cfg,
        cooldown_remaining=0,
    )
    assert d.exposure_scale == 1.0
    assert d.gate_state == "disabled"
    assert d.kill_switch_active is False


def test_killswitch_and_cooldown_behavior() -> None:
    cfg = build_gate_config(
        gate_enabled=True,
        gate_profile="tail_first_v1",
        exposure_floor=0.15,
        exposure_ceiling=1.0,
        cooldown_rebalances=2,
        kill_switch_thresholds={"drawdown": 0.25},
    )
    first = evaluate_gate(
        context=GateContext(
            rolling_vol_20=0.10,
            drawdown_abs=0.30,
            underfill_ratio=0.10,
            reject_ratio=0.10,
            benchmark_mom_20=0.01,
            benchmark_mom_60=0.01,
        ),
        config=cfg,
        cooldown_remaining=0,
    )
    assert first.kill_switch_active is True
    assert first.cooldown_remaining_next == 1
    assert first.gate_state == "stress"
    assert math.isclose(first.exposure_scale, 0.15, rel_tol=1e-9)

    second = evaluate_gate(
        context=GateContext(
            rolling_vol_20=0.10,
            drawdown_abs=0.01,
            underfill_ratio=0.10,
            reject_ratio=0.10,
            benchmark_mom_20=0.01,
            benchmark_mom_60=0.01,
        ),
        config=cfg,
        cooldown_remaining=first.cooldown_remaining_next,
    )
    assert second.kill_switch_active is True
    assert second.cooldown_remaining_next == 0
