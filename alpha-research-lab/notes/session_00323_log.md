# Session 323 Log

**Date:** 2026-05-08
**Experiment:** H443 prop_foreign_predator_prey
**Status:** COMPLETE

## Hypothesis

Foreign and proprietary flows may be useful only as a conflict/absorption game, not as raw net-flow ranks. Test predator-prey states where one flow type absorbs or follows another.

Connection: standalone foreign/proprietary paths and foreign additive H418 failed, but the raw surfaces now exist. Smallest honest test: predeclare foreign-sell/prop-buy absorption, foreign-buy/local-distribution, and prop-following-foreign states crossed only with Vol+S1 strength, C16, and news support; compare to raw foreign, raw proprietary, H418, and random same-support controls.

## Command

```bash
python analysis/h443_prop_foreign_predator_prey.py
```

## Inputs

- S1 panel: 826,404 rows, 394 tickers
- Foreign flow: YES
- Proprietary trading: YES
- C16: YES
- News: YES

## Results

| State | IC | Pos Years | Rows |
|-------|-----|-----------|------|
| all_rows (baseline) | 0.1335 | 11/11 | 826,404 |
| ff_buy | 0.1188 | 11/11 | 265,780 |
| ff_sell | 0.1004 | 11/11 | 244,840 |
| pt_buy | 0.0797 | 4/4 | 22,378 |
| pt_sell | 0.0887 | 4/4 | 23,588 |
| ff_sell_pt_buy_absorption | 0.0621 | 4/4 | 11,076 |
| ff_buy_pt_sell_distribution | 0.0959 | 4/4 | 9,849 |
| prop_follow_ff | 0.0842 | 4/4 | 21,558 |
| ff_sell_pt_buy_high_c16 | 0.1190 | 3/3 | 957 |
| ff_buy_pt_sell_high_c16 | 0.1232 | 3/4 | 1,431 |

## Key Findings

1. **All predator-prey states LOWER than baseline**: The predator-prey hypothesis is NOT supported
2. **Foreign flow alone is weaker than baseline**: ff_buy (0.1188) and ff_sell (0.1004) both underperform all_rows (0.1335)
3. **Proprietary flow is even weaker**: pt_buy (0.0797) and pt_sell (0.0887) are significantly below baseline
4. **Absorption state (ff_sell_pt_buy) is weakest**: IC=0.0621, far below baseline (-0.0714 lift)
5. **Adding high C16 helps marginally**: ff_buy_pt_sell_high_c16 reaches 0.1232, but still below baseline
6. **Sample sizes are small for combined states**: Combined predator-prey states have 9k-21k rows vs 826k baseline

## Verdict: FAILED

The hypothesis that foreign and proprietary flows would be useful as a conflict/absorption game is NOT supported. All predator-prey states have lower IC than the baseline S1 panel. The raw flows themselves (foreign buy/sell) also underperform the baseline, suggesting that flow direction alone is not predictive - the existing S1 signal already captures any useful information from these flows.

## Saved Artifact

`/home/manh/stocks-ecosystem/alpha-research-lab/artifacts/run_summaries/20260508_171817_h443_prop_foreign_predator_prey_research_branch.json`

## Dead-End Note

This path (prop_foreign_predator_prey) should be marked as a dead-end. The predator-prey interaction between foreign and proprietary flows does not add predictive value over the baseline S1 signal. Do not reopen this branch unless there is materially different data or a different representation contract.