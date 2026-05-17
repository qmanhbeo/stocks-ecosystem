# Live State

What this file is for: current operational truth, active constraints, and next
actions. Keep this short. Put detailed run logs in session files, durable
scientific conclusions in findings chunks, and closed paths in dead-end chunks.

## Current Session Pointer

- **Latest session log**: Session 350 (H542 Breadth Transition Momentum)
- **Latest session log path**: `notes/session_00350_log.md`
- **Latest session log path**: `notes/session_00345_log.md`
- **Latest compact reference**: `notes/sessions_compact.md`
- **Current active branch**: breadth exploration
- **Last updated**: 2026-05-17

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
- H511 now tests the k-choice caveat directly with dev-only selection:
  quiet structure remains strong and active clusters still beat random, but C24
  recovery weakens and onset/amplification/carry disentangling remains weak,
  so active-manifold decomposition is still unresolved.
- H512 then runs the immediate refinement with C24-preserving global
  representation (`k=4`) and recovers a passing active decomposition:
  C24 recovery restored (`0.966`), active-vs-random gap strengthened
  (`+0.060`), and mean onset/amplified/carry separation rises to `0.105`.
- H513 then confirms that H512 is not a one-pocket artifact: two strong active
  clusters stay phase-positive out of dev and concentration remains acceptable
  (`dominant share 0.576` vs `0.80` guardrail).
- H514 then runs a feature-augmented amplified-axis refinement and returns
  MIXED under dev-silhouette active-k selection: onset improves, amplified
  overlap weakens.
- H515 then keeps the same refined representation but forces `active_k=5`,
  recovering strong amplified separation (`0.151`) while preserving quiet/C24
  and active-vs-random gates.
- H516 then confirms H515 robustness: two strong clusters remain phase-positive
  with acceptable concentration (`dominant share 0.655 < 0.80`).
- H517 then resolves selection drift by passing a guarded active-k contract:
  H512 remains `k=4`, while H514 is corrected from silhouette `k=3` to guarded
  `k=5` with strong amplified recovery and preserved lift/strength.
- H518 then diagnoses the remaining weak axis: carry separation is now mainly a
  representation-overlap bottleneck (carry Jaccard `0.090`) rather than a
  phase-stability problem (carry cluster still `11/11` positive years).

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

## Hypothesis Queue

Carry-axis exploration branch: COMPLETE (Sessions 332-334, H518-H521).
- H518: diagnosed carry issue as representation-overlap bottleneck (PASSED diagnostic)
- H519: strong carry features improve carry but damage amplified (MIXED)
- H521: weak carry features still conflict with amplified (MIXED)
- Finding: carry/amplified are structurally in tension - the manifold limits to 2-3 clean separations

### New Eureka Hypotheses (Bright-Mind)

1. ~~**Transition Dynamics as Alpha**~~ - **FAILED (Session 335, H522)**: Transition events do NOT capture info beyond static states. Best transition (`transition_to_router` IC=0.2246) is essentially identical to static (`state_router` IC=0.2258), lift -0.0012. Duration features also don't help (long duration is anti-predictive, 5/11 positive years). Conclusion: transitions are NOT the alpha - static states ARE the signal.

2. ~~**Cross-Sectional Relative State Encoding**~~ - **FAILED (Session 336, H523)**: Relative encoding (market/sector percentile) does NOT beat absolute binary labeling. Best relative is -0.0082 below absolute. Participation pressure captured by specific mechanism (low C16), not relative ranking.

3. ~~**State Duration as Hidden Variable**~~ - **PARKED (weak evidence from H522)**: Duration features (long duration) are anti-predictive (5/11 positive years). Similar to transitions - not the path.

4. ~~**Regime-Aware Signal Gating**~~ - **PARKED (H510 resolved)**: H510 already tested regime differences - cash drag is execution, not signal. Regime gating won't solve what execution already fails at.

5. ~~**Observable-Manifold Compression**~~ - **PARKED (H509 already did it)**: H509 did unsupervised clustering. PCA/UMAP is same mechanism, won't break the 2-3 separation limit.

### Fresh Eureka Ideas (Post-H523)

6. ~~**State Combination Alpha**~~ - **FAILED (Session 337, H524)**: Combo states do NOT capture info beyond individual states. Best combo (intersect_router_buyable IC=0.1796) is only +0.0002 lift over best individual (state_router IC=0.1795). Union combos actually hurt. Key discovery: state_quiet is STRONG (IC=0.1552), not neutral as assumed.

7. ~~**Cross-Sectional Breadth as Regime Signal**~~ - **FAILED (Session 338, H525)**: OPPOSITE finding! High breadth dates have WORSE IC (0.1149) than low breadth (0.1454). Lift -0.0305. When many stocks activate together, it's a crowded regime with weaker signal quality. Low breadth dates are better (+0.0177 lift vs baseline).

8. ~~**Exit Timing Discovery**~~ - **FAILED (Session 339, H526)**: Holding duration does NOT predict different IC. Fresh entry (IC=0.1693) vs sustained (IC=0.1712) only -0.002 difference, noise. Both beat baseline (+0.042). Signal works equally well at entry and as sustained position.

9. ~~**Quiet-State Inverse Alpha**~~ - **FAILED (Session 340, H527)**: Quiet stocks in high-breadth dates IC=0.1248 vs low-breadth IC=0.1225, lift only +0.0022 (below 0.01). No contrarian effect found. Market activity level does NOT meaningfully modulate quiet-stock quality.

10. **Multi-Signal Day Superposition** - C23/C24/C25/C26 fire on different days. Test if the superposition (OR of any active state) captures broader alpha windows that single states miss.

11. **Market Microstructure State Conditioner** - Test bid-ask spread, VWAP deviation, or order arrival rate as state conditioners. Not tested as condition - only as standalone signal.

### Fresh Bright-Mind Ideas (Post-H525)

12. **Temporal Breadth Sweet Spot** - Test if time-since-entry into active state (duration bucket) predicts IC decay. D046 tested horizon decay, not time-in-state. Sweet spot may exist before decay.

13. **Quiet-State Contrarian Filter** - Intersection of state_quiet (IC=0.1552 strong!) + low_breadth (IC=0.1454 better). Both were tested separately; intersection untested.

14. **Breadth-Adjusted Signal Weighting** - Instead of binary filter, weight S1 by inverse breadth (1/active_fraction) to continuously correct for crowding penalty.

15. **Market Regime Breadth Interaction** - Split by bull/bear market (VNI direction), measure if breadth effect differs by regime. H525 averaged across all.

16. **Active-State Concentration Edge** - Test if concentration of signal mass in top-N matters more than count. Top-5 holding 80% of signal = concentrated = stronger?

17. **Exit-Rule Breadth Coupling** - Test if optimal holding period differs by entry breadth. High-breadth entry = signal decays faster = exit sooner.

18. **Replacement Pressure Signal** - Test if rate of active-set composition turnover predicts signal quality. High turnover = fresh alpha = better IC.

### New Eureka Ideas (Post-H527)

19. ~~**Anti-Breadth Entry Signal**~~ - **PASSED (Session 342, H529)**: S1 on low_breadth_dates IC=0.1542 beats baseline (0.1277) by +0.0266 lift (> +0.01). Pure timing mechanism - no C16 required. Confirms H525/H528 findings. High breadth dates IC=0.1085 (-0.0191) worse than baseline. Active+low_breadth still strongest (0.2013, +26% vs active alone).

20. ~~**Quiet-State × Low-Breadth Intersection**~~ - **MIXED** (Session 341, H528): quiet+low_breadth IC=0.1644 (beats min 0.1542 but not > max+0.01). SIGNIFICANT: active+low_breadth IC=0.2013 beats active alone (0.1597) by +0.0416. Low-breadth amplifies active signal by +26%. Dead-end D057 for quiet intersection, but active+low_breadth is a finding.

21. ~~**Breadth-Weighted Position Sizing**~~ - **FAILED (Session 343, H530)**: weighted_score (S1 × inv_breadth) IC=0.1057 is WORSE than baseline (-0.0220). weighted_rank IC=0.1407 (+0.0130) beats baseline but not > binary filter (0.1428). Binary low_breadth filter remains the better implementation.

22. **Active-State Regime Amplifier** - Use low_breadth as positive filter for active state. Next queue item.

22. **Quiet-State Temporal Decay** - Does state_quiet signal decay differently than active states? H526 tested active duration; quiet might have different optimal holding.

23. **Sector-Level Breadth Asymmetry** - Some sectors activate together while others stay isolated. Test if sector-level breadth predicts signal quality differently than market-level.

### New Bright-Mind Ideas (Post-H528)

24. **Breadth Transition Momentum** - Direction of breadth change (contracting vs expanding) may matter more than absolute level. Test if breadth_contracting (high→low) has stronger IC than steady_low. Mechanism: as crowd disperses, signal quality improves.

25. **Quiet-to-Active State Transition** - Stocks transitioning from quiet (rank ≥ 0.75) to active (rank < 0.2) within 3 days may capture pre-crowd alpha. state_quiet is strong (0.1552), active+low_breadth is strong (0.2013). Neither tested the transition.

26. **Sector-Breadth Divergence** - Market high breadth + sector low breadth = sector-specific alpha. Divergence captures isolated signal strength vs market-level crowding. Not tested in previous sector experiments.

27. **Inverse Breadth Entry Timing** - Entry on breadth_decrease day (inflection) vs already-low breadth day. Captures timing when crowd starts dispersing. H525/H528 tested level, not change direction.

28. **Breadth Concentration Edge** - Not how many active, but how concentrated. Top-5 holding 80%+ of active weight = concentrated = stronger? Adds quality to breadth quantity.

29. **Multi-Signal Breadth Composite** - OR of C23/C24/C25/C26 on low_breadth dates (vs all dates). H524 combos failed at same-breadth, but low_breadth might amplify all.

30. **Breadth-Periodicity as Calendar Effect** - Does breadth exhibit predictable weekly/monthly patterns? Month-start/Monday systematically lower? H400 failed for signal, but breadth calendar untested.

31. **Replacement Pressure Amplification** - High turnover in active-set = fresh alpha. Combine with low_breadth filter for temporal depth.

### New Bright-Mind Ideas (Post-H530)

32. **Breadth-Triggered Entry Decay Detection** - ~~Test if signal quality rebounds after high-breadth spikes. Compare IC 1d/3d/5d post-high-breadth. Mechanism: high breadth = crowd saturation, cooldown after spike may restore signal quality.~~ **MIXED (Session 345, H532)**: post-spike alone (0.1170) still below baseline; lowbreadth_post_spike combo = 0.1982 (+0.0706), stronger than H531!

33. **Breadth-Sector Cross-Filter** - ~~Sector-level breadth vs market-level breadth. Low sector + high market = sector-specific alpha. H526 tested sector×C23, not sector×breadth.~~ **FAILED (Session 346, H533)**: intersection too sparse (37 rows). Data not available for this test.

34. **Active State Duration Sweet Spot** - ~~H526 tested fresh vs sustained, not duration buckets. Test 1d vs 2-3d vs 4d+ in active state.~~ **PASSED (Session 346, H534)**: duration_8pl IC=0.1832 (+0.0530 vs baseline). Longer active-state duration predicts STRONGER signal, not decay!

35. **Breadth-Capacity Intersection** - ~~H474 tight_capacity (IC=0.184) + H529 low_breadth = intersection untested. Combine hidden demand + regime amplifier.~~ **PASSED (Session 344, H531)**: intersection IC=0.1979 beats best single by +0.0100 lift, +0.0702 vs baseline.

36. **Inverse Breadth Signal** - High breadth degrades S1 by -0.0305 IC (H525). Document as risk signal: exclude high-breadth dates to reduce cash drag.

### New Eureka Ideas (Post-H532)

37. **Triple-Intersection Alpha** - ~~Test tight_capacity + low_breadth + active (C16<0.2) three-way intersection. H531 (tight+low, 0.1979) + H528 (active+low, 0.2013) suggest triple could exceed 0.21.~~ **MIXED/D059 (Session 347, H535)**: triple_intersection IC=0.1956 (+0.0653 vs baseline) but IDENTICAL to active_low_breadth. tight_capacity is redundant when combined with active+low_breadth.

38. **Capacity Expansion Regime** - ~~Test if contracting capacity (fewer orders over time) + S1 beats static tight_capacity. Hidden demand growing = stronger signal.~~ **MIXED/F427 (Session 348, H538)**: OPPOSITE FINDING! tight_expanding (IC=0.1697) beats tight_contracting (IC=0.1553) by +0.0144. More orders arriving = stronger, not fewer.

39. **Breadth-Weighted Composite** - H530 FAILED weighting raw S1 by 1/breadth. Try weighting the C23/C24/C25/C26 COMPOSITE instead, not S1 directly.

40. **Breadth Transition Momentum** - ~~Direction of breadth change (contracting vs expanding) may matter more than absolute level.~~ **MIXED/F428 (Session 350, H542)**: contracting_to_low IC=0.1467 is essentially TIED with steady_low (0.1463, +0.0004). Transition adds nothing over static low breadth.

41. **Sector-Breadth Divergence** - Market high + sector low breadth = sector-specific alpha. Test where sector breadth < market breadth (inverse of #33).

42. **Capacity-Volume-Breadth Triple** - ~~tight_capacity (H474) × vol_expansion (H446) × low_breadth (H529).~~ **FAILED/D060 (Session 349, H541)**: Data-gated - volume loading insufficient. Three confirmed amplifiers combined.

### New Bright-Mind Ideas (Post-H542)

43. **Duration-Weighted Signal Strength** - Use log(1+consecutive_days_in_active) as continuous weight modifier instead of binary filter. H534 showed duration predicts STRONGER signal - now use it as strength modifier, not just filter.

44. **Breadth-Adaptive Exit Rules** - Exit faster on high-breadth dates (signal already weak per H525), hold longer on low-breadth dates. H526 tested regime-agnostic exit with no difference - now test regime-dependent exit.

45. **Capacity Direction as Signal Weight** - Use capacity_expanding (more orders arriving) as continuous weight, not filter. H538 showed expanding beats contracting by +0.0144 - now use as strength modifier.

46. **Breadth-Concentration Interaction** - Combine market-level breadth (crowding) with signal concentration (top-N share of signal mass). H399 partially explored volume concentration, but breadth×concentration untested.

47. **Sector-Breadth Divergence** - Sector moving opposite to market breadth contains alpha (strong sector in weak market = isolation). H525 showed breadth at market level - now sector×breadth interaction.

48. **Quiet-State Duration Sweet Spot** - H534 found strong duration effect for active state (longer = stronger). Test if quiet state has OPPOSITE pattern (longer = decay?).

49. **Regime-Adaptive Position Multiplier** - From H510 appeal: cash drag in bull regimes. Use VNI direction + breadth as exposure multiplier to reduce cash drag.

50. **Multi-Signal Low-Breadth Filter** - Apply low_breadth filter to C23/C24/C25/C26 COMPOSITE (not just S1). H524 failed for same-breadth combos, but low_breadth amplified all signals in H532.

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

4. **Active-manifold disentangling under dev-only k discipline**
- Status: DONE (Session 325, H511).
- Result: DOES NOT SUPPORT (failed preservation/disentangling gates).
- Key read: selected global `k=5` preserved quiet (`0.99797`) and active beats
  random (`+0.04266` lift gap), but C24 recovery degraded (`0.5911`) and
  onset/amplification/carry separation stayed weak (`mean max-Jaccard 0.0592`).

5. **C24-preserving representation-first refinement**
- Status: DONE (Session 326, H512).
- Result: PASSED.
- Key read: with forced global `k=4`, quiet/C24 preservation gates pass
  (`0.9634` / `0.9660`), active-vs-random lift gap improves to `+0.0604`,
  mean onset/amplified/carry separation improves to `0.1048`, and strong
  non-sparse active clusters increase to `2`.

6. **H512 robustness stability follow-through**
- Status: DONE (Session 327, H513).
- Result: PASSED.
- Key read: strong cluster count `2`, both phase-positive in validation and
  confirmation, dominant cluster share `0.576` below one-pocket guardrail.

7. **Amplified-axis refinement (feature-augmented, silhouette-selected)**
- Status: DONE (Session 328, H514).
- Result: MIXED.
- Key read: onset improved but amplified overlap fell to `0.032` under selected
  `active_k=3`.

8. **Amplified-axis refinement follow-through (forced active k)**
- Status: DONE (Session 329, H515).
- Result: PASSED.
- Key read: forced `active_k=5` recovers amplified overlap to `0.151` while
  preserving quiet/C24 and active-vs-random gates.

9. **Robustness audit for forced-k amplified variant**
- Status: DONE (Session 330, H516).
- Result: PASSED.
- Key read: strong cluster count `2`, both phase-positive out of dev, dominant
  share `0.655` below one-pocket guardrail.

10. **Active-k selection-discipline audit**
- Status: DONE (Session 331, H517).
- Result: PASSED.
- Key read: guarded contract fixes H514 (`k3 -> k5`) and keeps H512 stable.

11. **Carry-axis bottleneck diagnostic**
- Status: DONE (Session 332, H518).
- Result: PASSED (diagnostic).
- Key read: carry weakness is overlap/representation-limited, not phase-unstable.

12. **Carry-axis representation refinement**
- Status: DONE (Session 333, H519).
- Result: MIXED.
- Key read: carry Jaccard improved to 0.146 (+62% vs H518 0.090), but amplified dropped to 0.031 (-80% vs H518 0.151).
- Trade-off: carry-focused temporal features (flow_persist, imbalance_persist, order_pressure_sustain) improve carry but hurt amplified.

13. **Balanced carry-amplified search**
- Status: DONE (Session 334, H521).
- Result: MIXED.
- Key read: even "weak" carry features (simple lags) improve carry (+25%) but still damage amplified (-38%).
- Conclusion: carry and amplified are structurally in tension in the observable manifold - this is a latent property, not feature engineering.

14. **Branch conclusion: carry-amplified conflict**
- Status: DOCUMENTED.
- Key finding: onset/amplified/carry cannot all be cleanly separated in current observable space.
- The manifold appears limited to 2-3 clean separations (quiet + 1-2 active states).
- This concludes the carry-axis exploration branch.

---

## Known Open Questions

- Are C23/C24 primitives, or emissions of one deeper microstructure state?
- Why does low C16 route C23 better than high C16?
- Is freshness a timing mechanism or just a proxy for state transition edges?
- Are sparse wins (sector/state pockets) phase transitions or sample artifacts?
- Which findings survive when interpreted as latent-state dynamics rather than
  per-feature signal claims?
