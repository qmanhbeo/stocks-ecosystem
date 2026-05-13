# Session 44 Log (2026-03-28)

## Summary

Session 44 ran the next queue from Session 43: `H133`, `H134`, and `H126`.

**Net result:** two new signals were promoted. `H133` produced `C13` (compression blow-off reversal),
`H134` produced `C14` (residual close-strength after removing C8), and `H126` was rejected as a
longer-horizon duplicate of `C11`.

## Experiments

### H133 — Compression Blow-Off Reversal -> C13 PASS

**Script:** `analysis/h133_compression_blowoff_reversal_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_125618_h133_compression_blowoff_reversal_standalone_signal.json`

This is the sign-flipped interpretation of H128. The market treats post-compression expansion as
an exhaustion state, not a breakout state.

| Feature | IC | Pos Years | Corr S1 | Max Candidate Corr | Verdict |
|---------|-----|-----------|---------|--------------------|---------|
| xs_compress_blowoff_1 | +0.0541 | 11/11 | +0.321 | — | fail on S1 overlap |
| xs_compress_blowoff_2 | +0.0351 | 10/11 | +0.191 | +0.154 | **PROMOTE** |
| xs_compress_blowoff_3 | +0.0540 | 11/11 | +0.340 | — | fail on S1 overlap |

**Interpretation:** the strongest raw reversal states overlap too much with S1, but the
second formulation is both powerful and independent enough to promote.

**Promoted:** `xs_compress_blowoff_2` -> **C13**

---

### H134 — Close-Location Residual vs C8 -> C14 PASS

**Script:** `analysis/h134_close_location_residual_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_125440_h134_close_location_residual_standalone_signal.json`

H127's volume-confirmed close-location signal survives after removing the C8 volume axis.

| Feature | IC | Pos Years | Corr S1 | Max Candidate Corr | Verdict |
|---------|-----|-----------|---------|--------------------|---------|
| xs_clv_volconf_resid_rank | +0.0131 | 11/11 | +0.102 | +0.099 | **PROMOTE** |
| xs_clv_volconf_resid_inverted | -0.0131 | 0/11 | -0.102 | — | fail |

**Interpretation:** most of H127 was just volume, but not all of it. After residualization against
`C8`, a smaller close-strength signal remains and is genuinely orthogonal.

**Promoted:** `xs_clv_volconf_resid_rank` -> **C14**

---

### H126 — Longer-Horizon Continuation -> REJECTED AS REDUNDANT

**Script:** `analysis/h126_long_horizon_continuation_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_125405_h126_long_horizon_continuation_standalone_signal.json`

The raw 90d and 120d continuation signals are real, but they are just longer-window versions of C11.

| Feature | IC | Pos Years | Corr S1 | Key Pairwise Corr | Verdict |
|---------|-----|-----------|---------|-------------------|---------|
| xs_ret_90d_lag_rank | +0.0108 | 11/11 | +0.002 | corr C11 = +0.775 | duplicate |
| xs_ret_120d_lag_rank | +0.0109 | 10/11 | -0.003 | corr C11 = +0.664 | duplicate |
| xs_ret_90d_sector_neutral_rank | +0.0074 | 9/11 | -0.001 | — | fail |
| xs_ret_120d_sector_neutral_rank | +0.0077 | 8/11 | -0.004 | — | fail |

**Interpretation:** the continuation effect extends to 90d/120d, but it is not a new RL axis.
Sector-neutralization strips too much of it away to leave a promotable signal.

## RL Matrix Update

`data_tools/build_rl_signal_matrix.py` was updated to export:

- `c13_compress_blowoff_2`
- `c14_clv_volconf_resid_rank`

**Output:** `data/features/xs_rl_signal_matrix.parquet`

**Final shape:** `826,404 x 16`

Coverage:
- `c13_compress_blowoff_2`: 824,627 / 826,404 rows
- `c14_clv_volconf_resid_rank`: 825,839 / 826,404 rows

## Pairwise Check

The two new signals are independent from the existing library and from each other.

| Pair | Spearman rho |
|------|--------------|
| C13 vs max existing candidate | +0.154 |
| C14 vs max existing candidate | +0.099 |
| C13 vs C14 | -0.002 |

## Handoff Notes

- Promote `C13 = xs_compress_blowoff_2`
- Promote `C14 = xs_clv_volconf_resid_rank`
- Keep `H126` in the rejected table as a duplicate of `C11`
- The most natural next move is to combine the new reversal and gap-state signals (`H135`)
