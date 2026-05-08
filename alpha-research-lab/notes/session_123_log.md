# Session 123 Log — 2026-05-08

## H474: capacity_as_signal_not_veto

**Decision: PASSED** (with caveat on tight_expansion sparsity)

### Hypothesis
Tradability capacity (total order count percentile) should be a SIGNAL INPUT, not a binary
veto. Low capacity = hidden demand that couldn't execute. Continuous percentile captures
different dynamics than the failed H391 binary release state.

Connection to H391 (tradability_release_pulse, D009): H391 tested BLOCKED->RELEASED
(binary state transition). H474 tests CONTINUOUS capacity percentile — fundamentally
different mechanism.

### Command / code
```bash
python analysis/h474_capacity_as_signal_not_veto.py
```

### Inputs
- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet` (start_year=2018)
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet` (engine=pyarrow)
- 648,164 rows, 99.4% coverage, order_count>0: 98.6%

### Saved artifact
`artifacts/run_summaries/20260508_194212_capacity_as_signal_not_veto_research_branch.json`

### Results

| State | IC | Lift vs Baseline | Positive Years |
|-------|-----|-------------------|----------------|
| all_rows (baseline) | 0.1194 | — | 8/8 |
| **tight_capacity (Q1)** | **0.1840** | **+0.0646** | **8/8** |
| tight_has_volume | 0.1840 | +0.0646 | 8/8 |
| mid_capacity (Q3) | 0.1063 | -0.0131 | 8/8 |
| loose_capacity (Q5) | 0.0737 | -0.0457 | 8/8 |
| tight_expansion | 0.2147 | +0.0953 | 2/2 (sparse: NaN 6/8 years) |

### Yearly breakdown (tight_capacity vs baseline)

| Year | Baseline IC | tight_capacity IC | Lift |
|------|-----------|-------------------|------|
| 2018 | 0.135 | 0.193 | +0.058 |
| 2019 | 0.145 | 0.182 | +0.037 |
| 2020 | 0.108 | 0.165 | +0.057 |
| 2021 | 0.123 | 0.185 | +0.062 |
| 2022 | 0.082 | 0.181 | +0.099 |
| 2023 | 0.121 | 0.191 | +0.070 |
| 2024 | 0.132 | 0.207 | +0.075 |
| 2025 | 0.109 | 0.167 | +0.058 |

**8/8 positive years** with consistent lift (+0.037 to +0.099).

### Interpretation

**tight_capacity is the key signal**: Low order count = IC 0.184 (+0.065 lift).
This is the OPPOSITE of the intuition that more activity = more information.
Mechanism: sparse order flow = hidden demand that couldn't fully execute,
or under-followed stocks with uncrowded alpha. HIGH order count = liquid,
crowded, already-priced.

**loose_capacity is anti-predictive**: IC 0.074 (-0.046). Crowded liquid stocks
perform WORSE. This is the inverse of "liquid = safe" — in VN market, liquidity
itself is a crowding indicator, not a quality signal.

**tight_expansion is sparse**: Only 2/8 years have enough rows. The vol regime
cross makes the state too sparse for reliable inference. tight_capacity alone is
the durable signal.

**tight_has_volume ≈ tight_capacity**: Adding volume filter doesn't help — the
low-count signal is already capturing what matters.

**Caveat**: The signal is NOT about tradability (buyability). It's about order
activity/attention. Low activity tickers have stronger S1 quality, suggesting
the candidate model sees something in thin-traded names. This aligns with the
illiquidity amplification pattern (C23/C24/C25/C26).

### Result: PASSED

- tight_capacity IC 0.184 (+0.065 lift), 8/8 positive years
- tight_expansion sparse but strong (only 2/8 years)
- loose_capacity anti-predictive (-0.046)
- NEW capacity signal — fundamentally different from H391 binary release

### Verdict: PASSED

**C27 NEW SIGNAL CANDIDATE**: tight_capacity (low order count from CafeF order_stats)
as a signal conditioner. Mechanism: sparse order activity = hidden demand / under-followed
alpha. Do NOT use as a veto — use as a positive filter that lifts low-activity names.

**Next:** Batch 11 queue complete (AK replacement_quality_revival was H437, AL = H472
dead-end, AM = H473 dead-end, AN = H474 PASSED). Remaining EUREKA items from
live_state: AP (residual signal discovery), AQ (replacement quality delta), AR (zero
liquidity anomaly), AS (intraday session routing), AT (adaptive signal weights), AU
(extreme negative sentiment), AV (breadth threshold finder). Consider next item from
bright-mind queue.