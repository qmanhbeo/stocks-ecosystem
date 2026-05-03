# Session 215 Log

Date: 2026-05-03

## H367 - Order + Gap Absorption Intersection

### Hypothesis
Combine C16 order pressure + C12 gap absorption signal (intersection).

### Results (dev 2015-2022)
| Signal | IC | Positive Years |
|--------|-----|------------|
| C16 standalone | **+0.0767** | 8/8 |
| C12 standalone | +0.0313 | 8/8 |
| Intersection (AND) | +0.0574 | 8/8 |
| Multiplicative | +0.0688 | 8/8 |

### Verdict
**FAILED** — Both intersection methods UNDERPERFORM C16 alone.
- Intersection (AND): -25% IC loss vs C16
- Multiplicative: -10% IC loss vs C16

C12 adds nothing when combined with C16. Keep C16 standalone.

### Promotion
Dead end. Do not pursue C16+C12 combinations.

### Next
H366: C16 + C7 ceiling intersection

---

## Previous
- Session 214: H365 C16 standalone — PASSED (IC 1.98 vs baseline 0.85)