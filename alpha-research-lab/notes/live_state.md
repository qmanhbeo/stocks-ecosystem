# Live State

What this file is for: current operational truth, active constraints, and next
actions. Keep this short. Put detailed run logs in session files, durable
scientific conclusions in findings chunks, and closed paths in dead-end chunks.

Latest verified sessions: [Session 139](./session_139_log.md), 2026-05-10  
Last supervision pass: 2026-05-10 (scientific review + H507/H508/H509 structural runs)

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
