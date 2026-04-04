# Shape-Frontier Plan

This memo records a disciplined follow-up for the shape-driven ideas recently surfaced in `H278`.

## 1. Shape-State Intra-Activation Atoms
**Objective:** fuse the reclaim-style `xs_upward_w_reclaim_*` scores with the existing activation drawdown state so the branch only fires when both the price geometry and the selector drawdown align.
**Steps:**
1. Compute the reclaim atoms for `2015-2025` using `src/price_shape_research.py`; reuse the commit to write the merged dataframe into `artifacts/shape_atoms/` for downstream gates.
2. Merge those scores with `data/features/activation_state_daily.parquet` rows aligned by `time` and `ticker`, then define a state feature such as `shape_activation_signal = reclaim_score * (1 - selector_drawdown_bucket)` or similar to capture depth.
3. Run a small candidate audit (e.g., `analysis/h279_shape_activation_gate_audit.py`) evaluating 5-day hold advantage vs the live sticky branch; treat any positive delta as justification to promote the combined gate. Use the same canonical gate logic from `src/standalone_signal_utils.py`.
4. If the gate passes, integrate it into the activation overlay (compare vs `H179` results). If it mixes, keep the state as offline context only. If it fails, kill the branch.

## 2. Intraday Disagreement + Breadth Gap Router
**Objective:** route continuation decisions by comparing intraday disagreement spikes to sector breadth gaps, turning the leftover intraday branch into a disciplined router rather than a monolithic signal.
**Steps:**
1. Reuse `intraday_shape_core_disagreement` and `fade_tension_disagreement` rows from the reduced-shape panel (`H266/H275` artifacts) and join them with `xs_sector_breadth_5d` (from `data/features/xs_sector_rotation_daily.parquet`) on the observed breakout subset.
2. Define a logistic or deterministic rule that flags “high disagreement + declining breadth” states and use it as a gate inside `analysis/h264_family_aware_continuation_veto_integration.py`-style audits.
3. Audit the gate on the `2023-2025` observed breakout subset: measure the 5-day hold advantage and top quintile return vs the ungated `breakout_followthrough` baseline. If the gate passes, promote as a timing router; if it mixes, keep as offline context; if it fails, treat the idea as a documented negative.
4. **Status:** `H279` mixed: router advantage `+0.000398` vs baseline `+0.000278`; keep the artifacts ready for a confirmation recheck before turning this gate live.

## Documentation / Next Steps
- Record the outcomes in `notes/next_steps.md` (already updated with parking bullet).
- Keep this file as the living checklist for shape ideas before either gets an `H` number.
