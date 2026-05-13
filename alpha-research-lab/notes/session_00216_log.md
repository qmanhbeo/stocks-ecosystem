# Session 216 Log

Date: 2026-05-03

## H366 - Order + Ceiling Intersection

### Hypothesis
Combine C16 order pressure + C7 ceiling count signal (intersection).

### Results (dev 2015-2022)
| Signal | IC | Positive Years |
|--------|-----|------------|
| C16 standalone | **+0.0767** | 8/8 |
| C7 standalone | +0.0079 | 4/8 |
| Intersection (AND) | +0.0639 | 8/8 |
| Multiplicative | +0.0746 | 8/8 |

### Verdict
**FAILED** — Both intersection methods UNDERPERFORM C16 alone.
- Intersection (AND): -17% IC loss vs C16
- Multiplicative: -3% IC loss vs C16

C7 (ceiling count) adds nothing when combined with C16. Keep C16 standalone.

### Promotion
Dead end. Do not pursue C16+C7 combinations.

### Next
H368: C16 + sector laggard, or H369: C5 + C16

---

## Previous
- Session 215: H367 — C16 + C12 intersection — FAILED (IC +0.0574 vs +0.0767)
- Session 214: H365 C16 standalone — PASSED (IC 1.98 vs baseline 0.85)