# Findings 331-360

## F339: H379 Dynamic Candidate Thermodynamics Passes As Offline Policy Evidence (2026-05-04, Session 255)

Finding:
- Claim: the candidate panel contains enough pre-decision temperature
  information to choose portfolio breadth (`cash/top1/top2/top5/top10`) better
  than random K policies.
- Evidence: `analysis/h379_dynamic_candidate_thermodynamics.py` used TRUE
  walk-forward validation with train years strictly before each test year,
  `2019-2025` data only, and no S1/C16 baseline comparison. The primary
  benchmark was `2,000` random invested action policies over
  `top1/top2/top5/top10`.
- Result: mean policy absolute cycle return `+0.00665` versus random invested
  mean `+0.00508`, lift `+0.00157`; `4 / 5` walk-forward years beat the random
  invested mean; 2025 confirmation lift was `+0.00108`.
- Weakness: only `1 / 5` years beat the random invested p95, 2021 failed, and
  2025 was only `69.2` percentile versus random invested policies.

Why it matters:
- This reopens dynamic breadth only as offline policy evidence, not a live
  branch change. The signal is about when to concentrate/diversify/cash, not
  a new ticker-level alpha.
- The durable clue is `candidate_count`: it was selected in 2023, 2024, and
  2025, suggesting candidate-universe temperature may be a better next test
  than a broad multi-feature router.
- Next honest step is a narrower full-portfolio `candidate_count` K/cash router
  compared to random K/cash policies, with 2026 still excluded from fitting.

Source:
- [session_255_log.md](./session_255_log.md)
- `artifacts/run_summaries/20260504_124306_h379_dynamic_candidate_thermodynamics_research_branch_dynamic_candidate_thermodynamics.json`

## F340: H380 Candidate Count Router Strengthens The Portfolio-Policy Branch (2026-05-04, Session 257)

Finding:
- Claim: candidate-count regimes alone can route portfolio breadth
  (`cash/top1/top2/top5/top10`) better than random K/cash policies.
- Evidence: `analysis/h380_candidate_count_policy_router.py` used TRUE
  walk-forward validation with train years strictly before each test year,
  `2019-2025` data only, no `2026+`, and no S1/C16 baseline comparison. The
  only candidate inputs were raw `candidate_count`, 1-day and 5-day
  candidate-count changes, and distance from the 20-day trailing mean.
- Result: mean policy absolute cycle return `+0.00796` versus random K/cash mean
  `+0.00407`, lift `+0.00389`; mean lift versus random invested policies was
  `+0.00281`; `4 / 5` years beat both random K/cash and random invested means.
  The 2025 confirmation lift was `+0.00472` versus random K/cash and `+0.00381`
  versus random invested.
- Weakness: 2021 failed both random means, so this is not a universal live
  policy rule.

Why it matters:
- H380 addresses the H379 next-step directly and confirms that the durable
  policy clue was raw `candidate_count`: every fold selected raw count, not
  delta or rolling-mean transforms.
- Promote PP5 only as offline portfolio-policy evidence. Do not change the live
  sticky branch and do not add this to `signal_library.md` because it is not a
  ticker-day alpha signal.

Source:
- [session_257_log.md](./session_257_log.md)
- `artifacts/run_summaries/20260504_125947_h380_candidate_count_policy_router_research_branch_candidate_count_policy_router.json`
