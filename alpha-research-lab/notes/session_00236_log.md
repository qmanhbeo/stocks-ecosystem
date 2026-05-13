# Session 236: S236 eureka tests

**Date:** 2026-05-03
**Focus:** Test S236 bright-mind ideas

## Results

| Test | IC | Result |
|------|-----|-------|
| exit hold_1d | 0.48 | baseline |
| exit hold_5d | 2.41 | Returns grow with hold |
| foreign_c13_triple 2leg | 0.093 | baseline |
| foreign_c13_triple 3leg | 0.080 | FAILED |
| C16 -> 1d | 0.020 | baseline |
| C16 -> 5d | 0.022 | NEUTRAL |
| C16 -> 20d | 0.018 | worse |

## Findings

- **exit_signal**: Returns grow with hold days. Early exit doesn't help - HOLD 5d optimal.
- **foreign_c13_triple**: Adding foreign makes it WORSE (-14%). Foreign is noise.
- **alternative_label**: 5d slightly better (+8%), 20d worse.
  - C16 works best on short horizons.

## Concluded

- S236: All major ideas FAILED or NEUTRAL
- Queue exhausted again