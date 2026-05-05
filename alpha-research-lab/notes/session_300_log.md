# Session 300 Log

**Date**: 2026-05-05
**Focus**: H419 `insider_additive`

## Summary

- Tested B57 (insider adds to additive).
- Added insider signal to H413.
- Verdict: **MIXED** - marginal, essentially no help.

## H419 - Insider Signal Add

**Hypothesis:**
Insider adds to Vol+S1 additive.

**Command / code:**
```bash
python alpha-research-lab/analysis/h419_insider_additive.py
```

| Signal | IC |
|--------|-----|
| S1 alone | +0.118 |
| Volume alone | +0.075 |
| **Insider alone** | **-0.002** |
| H413 (0.1V+0.9S) | +0.135 |
| **3-way** | **+0.135** |

**Delta**: +0.0004 (within noise)

**Verdict: MIXED**

- Insider alone is NEGATIVE (-0.002)!
- Adding to H413 gives near-zero (+0.0004) - no help
- Same pattern as C16, Foreign - all too weak
- Interestingly, historically strong signals (insider, C16, foreign) are now weak

**CONCLUSION**: This pattern is robust. Adding MORE signals doesn't help. The confirmed standard stands.

Source: F382 (or D024)