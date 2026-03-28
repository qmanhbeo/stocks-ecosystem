# Session 43 Log (2026-03-28)

## Summary

Session 43 ran the first full conditional-microstructure wave from the H125-H132 plan.

**Net result:** five directions failed or collapsed into existing signals. One new signal survived:
`H130` gap absorption with intraday confirmation, promoted to `C12`.

## Experiments

### H125 — Beta Residual -> FAIL

**Script:** `analysis/h125_beta_residual_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124339_h125_beta_residual_standalone_signal.json`

Residualizing 60d beta against illiquidity and abnormal volume kills the signal completely.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_beta_resid_60d_rank | -0.0019 | 5/11 | +0.019 | fail |
| xs_low_beta_resid_60d | +0.0019 | 6/11 | -0.019 | fail |

**Interpretation:** H124 was not hiding a real beta factor. The earlier low-beta result was almost entirely the illiquidity/attention axis already captured elsewhere.

---

### H127 — Close-Location Persistence -> REJECTED AS REDUNDANT

**Script:** `analysis/h127_close_location_persistence_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124334_h127_close_location_persistence_standalone_signal.json`

Plain close-location signals are wrong-way, but the volume-confirmed variant does have signal.

| Feature | IC | Pos Years | Corr S1 | Pairwise Check | Verdict |
|---------|-----|-----------|---------|----------------|---------|
| xs_clv_5d_rank | -0.0446 | 0/11 | -0.325 | — | fail |
| xs_clv_10d_rank | -0.0217 | 0/11 | -0.230 | — | fail |
| xs_clv_posret_5d_rank | -0.0332 | 0/11 | -0.249 | — | fail |
| xs_clv_volconf_5d_rank | +0.0149 | 11/11 | +0.105 | corr C8 = +0.903 | duplicate |

**Interpretation:** "close near high plus volume" is real, but it is effectively just a restatement of `C8` volume activity, not a new RL axis.

---

### H128 — Compression Breakout -> FAIL

**Script:** `analysis/h128_compression_breakout_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124332_h128_compression_breakout_standalone_signal.json`

The tested continuation orientation is strongly anti-predictive.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_compress_breakout_1 | -0.0541 | 0/11 | -0.321 | fail |
| xs_compress_breakout_2 | -0.0351 | 1/11 | -0.191 | fail |
| xs_compress_breakout_3 | -0.0540 | 0/11 | -0.340 | fail |

**Interpretation:** post-compression expansion looks more like exhaustion than breakout continuation in this market. This should be revisited later as a reversal hypothesis, not abandoned as noise.

---

### H130 — Gap Absorption -> C12 PASS

**Script:** `analysis/h130_gap_absorption_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124404_h130_gap_absorption_standalone_signal.json`

This was the only clean success of the wave.

| Feature | IC | Pos Years | Corr S1 | Key Pairwise Corr | Verdict |
|---------|-----|-----------|---------|-------------------|---------|
| xs_gap_absorb_1 | +0.0117 | 11/11 | +0.022 | corr C4 = +0.298 | pass but weaker |
| xs_gap_absorb_2 | +0.0334 | 10/11 | +0.151 | corr C4 = +0.453 | redundant |
| xs_gap_absorb_3 | +0.0284 | 11/11 | +0.131 | max corr = +0.202 | **PROMOTE** |
| xs_gap_reject_1 | +0.0073 | 8/11 | +0.062 | — | fail |

**Interpretation:** the market rewards gaps that are validated intraday. The best formulation requires:
- overnight gap
- positive intraday session
- strong close in the daily range

**Promoted:** `xs_gap_absorb_3` -> **C12**

---

### H131 — Sector Breadth Shock -> FAIL

**Script:** `analysis/h131_sector_breadth_shock_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124353_h131_sector_breadth_shock_standalone_signal.json`

Breadth changes do not add predictive power beyond the existing sector setup.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_breadth_shock_laggard | -0.0034 | 4/11 | -0.043 | fail |
| xs_breadth_shock_leader | -0.0052 | 2/11 | -0.033 | fail |
| xs_breadth_impulse_laggard | -0.0048 | 3/11 | -0.041 | fail |

---

### H132 — Liquidity Trap Release -> FAIL

**Script:** `analysis/h132_liquidity_trap_release_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_124359_h132_liquidity_trap_release_standalone_signal.json`

Conditioning illiquidity on return and close-strength improves intuition, but not enough signal.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_liq_release_1 | +0.0067 | 10/11 | +0.019 | fail |
| xs_liq_release_2 | -0.0452 | 1/11 | -0.306 | fail |
| xs_liq_release_3 | +0.0043 | 9/11 | +0.007 | fail |

## RL Matrix Update

`data_tools/build_rl_signal_matrix.py` was updated to export:

- `c12_gap_absorb_3`

**Output:** `data/features/xs_rl_signal_matrix.parquet`

**Final shape:** `826,404 x 14`

Coverage:
- `c12_gap_absorb_3`: 825,445 / 826,404 rows

## Handoff Notes

- Promote only `C12 = xs_gap_absorb_3`
- Do not promote `xs_gap_absorb_1`; it is valid but weaker and close to the C4 threshold
- Keep `H127` in rejected as a duplicate of `C8`
- The best immediate follow-up is `H133`: reinterpret H128 as compression blow-off reversal
