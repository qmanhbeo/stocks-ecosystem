# Session 101 Log

## Objective
Run H445 semantic_novelty_saturation experiment from the NEW EUREKA queue (item 5).

Hypothesis: News volume may be harmful when semantic novelty is exhausted, while high novelty plus muted price response may be delayed alpha.

This session did not change the live branch.
It did not read 2026+.

## Starting point

Coming in:
- H444 signal_ignorance_weight PASSED as offline evidence (worst regime -0.1369 lift)
- Queue had item 5: semantic_novelty_saturation as next

## What changed

Added:
- `analysis/h445_semantic_novelty_saturation.py`

Method:
- Used PhoBERT article counts (news_article_count columns were all zeros)
- Created novelty proxies: first_in_5d_proxy, repeat_coverage
- Created attention states: has_news, high_attention
- Created response states: muted_response, strong_response
- Tested combinations: exhaustion (has_news + repeat), delayed_alpha, novel_delayed, novel_responded

Saved artifacts:
- `artifacts/run_summaries/h445_semantic_novelty_saturation.json`

## Results

| State | IC | Lift vs Baseline | Rows |
|-------|-----|------------------|------|
| all_rows (baseline) | 0.1335 | - | 826404 |
| has_news | 0.1038 | -0.0297 | 174158 |
| no_news | 0.1409 | +0.0073 | 652246 |
| first_in_5d (novel) | 0.1265 | -0.0071 | 47322 |
| repeat_coverage | 0.1047 | -0.0288 | 230156 |
| high_attention | 0.1038 | -0.0297 | 174158 |
| **exhaustion** | **0.0861** | **-0.0474** | 61516 |
| delayed_alpha | 0.0452 | -0.0884 | 112734 |
| novel_delayed | 0.0577 | -0.0759 | 29616 |
| novel_responded | 0.0881 | -0.0454 | 4039 |

## Key Finding: NEGATIVE RESULT

**News (PhoBERT counts) hurts S1 signal quality:**
- All news states have NEGATIVE IC lift vs baseline
- `no_news` (IC=0.1409) actually beats `has_news` (IC=0.1038) by +0.037
- Exhaustion state (high repetition + attention) has worst IC: 0.0861 (-0.0474 lift)
- Delayed alpha (news + muted response) is worst overall: -0.0884 lift

**This is a NEGATIVE finding, not a signal promotion:**
- Raw article counts from PhoBERT are not predictive as a standalone feature
- News actually degrades S1 signal quality
- The "exhaustion" mechanism is confirmed: high repetition coverage with attention hurts

## Verdict: FAILED (as signal) / CONFIRMED (as dead-end)

The hypothesis tested whether novelty adds beyond count - the result shows BOTH novel and repeated news are negative. This confirms news article counts are NOT good signals in this formulation.

**Dead-end D035**: News (PhoBERT article counts) are not predictive - they degrade S1 quality.

**Next Steps**:
- Do not use raw news counts as signals
- Continue using source-type and sentiment features which H440/H383 found useful
- The novelty dimension (first-in-5d) might still work when combined with stronger features