# Live State

What this file is for: current operational truth, active constraints, and next
actions. Keep this short. Put detailed run logs in session files, durable
scientific conclusions in findings chunks, and closed paths in dead-end chunks.

## Current Session Pointer

- **Latest session log**: Session 324 (H510 Bull Participation State Audit)
- **Latest session log path**: `notes/session_00324_log.md`
- **Latest compact reference**: `notes/sessions_compact.md`
- **Current active branch**: structure-mapping mode
- **Last updated**: 2026-05-11

**WARNING**: Do not infer next session number from old live_state prose;
always inspect `notes/session_*_log.md` and choose the next available number.

---

## Current Read

- Batch 16/17 is complete through BU5.
- C23/C24 family remains the strongest verified signal family.
- `c16_low × C23` remains the strongest recent state (`IC=0.2838`, `+0.1540`,
  Session 132).
- Most post-C23 micro-conditioners are now weak, sparse, or dead-end:
  D042-D049, plus sparse sector-vol state in Session 138.
- The bottleneck has shifted from "find another +0.003 filter" to
  "explain latent structure of the surviving family."
- H507 now supports a coherent latent-state framing:
  onset/amplified/router/carry states show stable IC separation from quiet and
  coherent `-> carry -> quiet` transition flow, with sparsity caveat.
- H508 now supports ontology compression:
  freshness/cofire/low-C16 are nested C23 layers, while C24 remains a distinct
  residual emission channel.
- H509 now adds unsupervised latent-state evidence:
  emission clustering (no symbolic state inputs) reproduces strong quiet-vs-
  active separation, stable phase centroids, and a distinct C24-like channel,
  while onset/amplification/carry remain partially entangled.
  Skeptical caveat: selected `k=6` is useful but not uniquely proven; current
  k-choice summary uses full-period IC diagnostics, so treat it as structural
  evidence rather than final latent-contract selection.

---

**Appeal from heuristic-trader: execution failure traced to bull-regime cash drag (2026-05-11)**

heuristic-trader has completed its current execution-validation pass and is formally handing the next research question back to alpha-research-lab.

## Appeal Summary

The current signal stack has predictive structure in the lab, but execution-level validation shows that the strategy family fails in strong bull regimes because it becomes too cash-heavy / under-participated.

This is no longer primarily an infrastructure issue in heuristic-trader.

## Evidence from heuristic-trader

### 1. Infrastructure is now trusted

- Cache path bug fixed.
- `liquid_lookup.joblib` parity fixed and promoted.
- `trad_lookup.joblib` extended from accidental 2019 start to 2015 start.
- Clean execution-validation surface now starts at 2015-01-05.
- `test_parity.py`: PASS.
- `test_diagnostics_regression.py`: PASS.
- `collect_diagnostics=True` does not alter metrics.

Relevant heuristic-trader findings:
- F00007: Cache parity / missing-date semantics fixed.
- F00008: Walk-forward validation added.
- F00009: trad_lookup extended to 2015.
- F00010: Cash drag identified as bull-regime failure mechanism.

### 2. Walk-forward validation shows regime-sensitive failure

Default walk-forward now uses 11 annual folds from 2015-2025.

Key behavior:
- Strong bull years 2017 and 2025 destroyed all tested strategies.
- 2021 and 2022 were strong / successful years for some strategies.
- Single-period performance was misleading; fold robustness is now required before promotion.

### 3. Trade-level diagnostics identified the execution failure mode

Ticker-level PnL attribution found:

| Strategy | Realized PnL | Bull-regime cash exposure | Classification |
|----------|--------------|---------------------------|----------------|
| `blend_70_30_top5` | +0.76B | ~62-64% cash | Portfolio/exposure failure: selected names made money, but too much cash |
| `s1_top5_rebal10` | -0.06B | ~50-75% cash | Mixed signal + exposure failure |
| `c16_only_top5` | -0.18B | ~87-93% cash | Structurally cash-heavy; not viable standalone |

Core finding:
- Failure years 2017/2025: ~71.3% average cash.
- Success years 2021/2022: ~61.4% average cash.
- Estimated bull-regime cash drag: ~30.5%.

Important wording:
This does **not** prove that ticker selection is always good. It proves that cash/exposure is the primary identified mechanism for `blend_70_30_top5`, while `s1_top5_rebal10` remains mixed and `c16_only_top5` is structurally cash-heavy.

## Signals already wired in heuristic-trader

Heuristic-trader now consumes:

| Signal | Status |
|--------|--------|
| S1 `s1_proba` | existing |
| C16 `order_volume_ratio_rank` | existing |
| C17 `order_volume_ratio` | newly wired |
| C18 `order_volume_ratio_rank_delta` | newly wired |

C17/C18 quick execution tests:
- `c17_raw_top5_rebal10`: -1.37% mean annualized, 5/11 positive folds, FRAGILE.
- `c18_delta_top5_rebal10`: +0.16% mean annualized, 6/11 positive folds, FRAGILE.
- C18 is better than C17, but neither solves the cash-drag / bull-regime failure.

## Signals not yet export-ready for heuristic-trader

These remain lab-side work:

| Signal family | Status |
|---------------|--------|
| C19 | NEEDS_EXPORT |
| C20 | NEEDS_EXPORT |
| C21 | NEEDS_EXPORT |
| C22 | NEEDS_EXPORT |
| C23 | NEEDS_EXPORT |
| C24 | NEEDS_EXPORT |
| C25 | NOT READY — needs VWAP computation |
| C26 | NEEDS_EXPORT |

These appear more relevant than C17/C18 because they may encode regime / participation structure rather than simple order-pressure level or delta.

## Formal Research Question for alpha-research-lab

The lab should investigate:

**Why do signals with valid IC translate into under-participated, cash-heavy portfolios during bull regimes?**

More specifically:

1. Are C23/C24/C25/C26 emissions of a latent participation / liquidity-expansion regime?
2. Can the lab identify a regime state where cash drag becomes dangerous?
3. Can the lab produce a signal, regime flag, or exposure multiplier that tells heuristic-trader when to increase participation?
4. Is the current S1/C16 family structurally defensive, or is the cash exposure caused by execution filters and tradability constraints?
5. Are 2017 and 2025 similar at the signal-state level?
6. Why did 2021 work while 2017/2025 failed, despite all being bull-market years?

## Suggested Next Lab Work

Priority branch:

**Bull participation / cash-drag regime investigation**

Focus years:
- Failure bull years: 2017, 2025.
- Success / contrast years: 2021, 2022.
- Secondary comparison: 2019, 2024.

Recommended experiments:

1. Compare C23/C24/C25/C26 states across 2017, 2021, 2022, 2025.
2. Test whether high-cash execution years correspond to missing / inactive participation states.
3. Build a candidate `participation_regime` or `bull_exposure_state` feature.
4. Export a clean daily `(time, ticker, signal)` or `(time, market_regime)` surface for heuristic-trader.
5. Do not tune on 2026.
6. Do not optimize strategy parameters inside the lab.
7. Do not promote any signal until heuristic-trader validates it under execution constraints.

## Required Output Back to heuristic-trader

The lab should return one of:

1. A new exported signal surface:
   - `time`
   - `ticker`
   - signal column
   - no 2026 leakage
   - documented formula

or

2. A market-level regime surface:
   - `time`
   - `regime_state`
   - `exposure_multiplier` or `participation_flag`
   - documented formula

or

3. A negative finding:
   - C23-C26 do not explain bull cash drag.
   - Cash drag is caused by execution filters / portfolio construction, not signal state.

## Current Decision

H510 resolved the appeal with a NEGATIVE FINDING (Case C):
- Latent state ecology does NOT explain heuristic-trader bull-market cash drag
- C23 active state is higher in failure years than success years
- 2017 had stronger IC (0.149) than 2021 (0.123) despite being a failure year
- The problem is execution/portfolio construction in heuristic-trader, not missing signal states

The next move is to return the question to heuristic-trader for execution-level investigation.

### H510: Bull Participation State Audit (2026-05-11)

**Result: NEGATIVE FINDING (Case C)**

- Used H509 clustered panel (k=6) with 826,404 rows (2015-2025)
- Compared latent state distributions: failure bull years (2017, 2025) vs success contrast (2021, 2022)
- **Key finding**: C23 (active state) is actually HIGHER in failure years (4.55%) than success years (3.97%)
- **Key finding**: Overall IC is HIGHER in 2017 (0.149) than 2021 (0.123) or 2022 (0.082)
- **Conclusion**: Latent state ecology does NOT explain bull-market cash drag
- Cash drag is caused by execution/portfolio construction in heuristic-trader, not missing signal states
- No export to heuristic-trader warranted from latent-state side

**Session**: [Session 324](./notes/session_00324_log.md)

---

## Research Posture (Active)

The lab is now in **structure-mapping mode**, not incremental conditioner
mining.

Primary objective:
- infer latent organization behind C23/C24/C25/C26 and associated routers

Secondary objective:
- distinguish primitives vs routers vs conditioners vs surface artifacts

Out of scope for this queue:
- portfolio construction optimization
- deployability tuning
- new broad sweeps of tiny threshold variants

Hard constraints:
- no `2026+` backtest years unless explicit forward-only protocol
- no target-derived state columns (`actual`, `s1_barrier_hit_1d`)
- keep using `experiment_contract` scaffolds and run summaries

---

## Structural Queue (Next)

1. **Latent state switching audit**
- Status: DONE (Session 139, H507).
- Result: SUPPORTS latent-state structure; preserve sparsity caveat.

2. **Router equivalence / ablation map**
- Status: DONE (Session 139, H508).
- Result: compression confirmed (nested router/timing layers on C23; C24 distinct).

3. **Ontology compression pass**
- Status: H509 RUN COMPLETE (Session 139).
- Result: SUPPORTS latent ontology with caveat (partial rediscovery).
- Key read: k-sweep (`4/5/6`) beat random partitions; best `k=6` had
  active-lift `+0.0782` vs all rows and random-lift gap `+0.0746`.
- Caveat: onset/amplification/carry are not yet cleanly disentangled as
  separate latent states under the current observable emission set.

4. **Next structural pass**
- Status: READY.
- Next best question: can we disentangle active-manifold substructure
  (onset/amplification/carry) without reintroducing symbolic labels, while
  preserving H509's quiet/C24 recovery and random-baseline separation.
- Immediate posture: refine H509 observable emission representation and k-choice
  discipline first; do not jump to HMM/manifold branches yet.

---

## Known Open Questions

- Are C23/C24 primitives, or emissions of one deeper microstructure state?
- Why does low C16 route C23 better than high C16?
- Is freshness a timing mechanism or just a proxy for state transition edges?
- Are sparse wins (sector/state pockets) phase transitions or sample artifacts?
- Which findings survive when interpreted as latent-state dynamics rather than
  per-feature signal claims?
