# Session 248: Macro-C16 Regime Test

Date: 2026-05-03
Focus: Test C16 conditioned on macro regime

## Hypothesis

- **Claim**: C16 strength is regime-dependent - works differently in bear/bull/transition markets
- **Mechanism**: Macro regime modulates C16 effectiveness
- **Evidence**: C16 is contrarian (+26% in down). Macro states haven't been tested.

## Results

### Walk-Forward IC (2015-2022)

| Year | IC_all | IC_BULL | IC_BEAR | IC_FEAR |
|------|-------|---------|---------|---------|
| 2015 | +0.0596 | +0.0598 | +0.0465 | +nan |
| 2016 | +0.0735 | +0.0778 | +0.0484 | +nan |
| 2017 | +0.0768 | +0.0768 | +nan | +nan |
| 2018 | +0.0618 | +0.0645 | +0.0335 | +nan |
| 2019 | +0.0632 | +0.0634 | +0.1389 | +nan |
| 2020 | +0.0916 | +0.1027 | +0.0857 | +nan |
| 2021 | +0.1053 | +0.1003 | +0.1012 | +nan |
| 2022 | +0.0896 | +0.1007 | +0.0795 | +nan |

### Averages

- **All markets**: IC = +0.0777
- **VIX BULL** (VIX < 20): IC = +0.0807 (+3.6%)
- **VIX BEAR** (VIX > 25): IC = +0.0763 (-2%)
- **VIX TRANS** (20-25): IC = +0.0777
- **Breadth FEAR**: NaN (not enough data)

### Verdict

- **WEAK** - macro regime provides minimal C16 boost
- VIX BULL gives +3.6% improvement (+0.0807 vs 0.078)
- VIX BEAR actually worsens C16 (-2%)
- Tier 4 (dead end for macro conditioning)

### Why No Signal?

- C16 is already capturing its own order flow signal
- Macro regime is too noisy at daily frequency
- Market state (up/down) matters more than macro regime

---

## Next Test: Gap Open Momentum (S249)

Test: Overnight gap + C16 = amplify contrarian signal