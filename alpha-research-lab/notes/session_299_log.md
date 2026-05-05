# Session 299 Log

**Date**: 2026-05-05
**Focus**: H418 `foreign_additive`

## Summary

- Tested B56 (foreign flow adds to additive).
- Added foreign signal to H413.
- Verdict: **FAILED** - foreign doesn't help, actually hurts.

## H418 - Foreign Flow Add

**Hypothesis:**
Foreign flow adds to Vol+S1 additive.

**Command / code:**
```bash
python alpha-research-lab/analysis/h418_foreign_additive.py
```

| Signal | IC |
|--------|-----|
| S1 alone | +0.118 |
| Volume alone | +0.075 |
| Foreign alone | +0.004 |
| H413 (0.1V+0.9S) | +0.135 |
| **3-way** | **+0.128** |

**Verdict: FAILED**

- Foreign has near-zero IC alone (+0.004)
- Adding it HURTS: -0.006 IC drop
- Pattern similar to C16 - too weak to contribute

**Conclusion**: Same as C16 - some signals are too weak to add.

Source anchor: D023