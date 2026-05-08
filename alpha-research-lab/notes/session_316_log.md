# Session 316 - 2026-05-08

## H437: replacement_quality_revival

**Hypothesis:** Quality (S1 IC, C16 IC, forward returns) of entering tickers vs exiting tickers predicts forward alpha. Different from H388 which tested freshness - this tests quality. Entering quality > exiting quality = alpha.

**Command / code:**
`python3 analysis/h437_replacement_quality_revival.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets

**Saved artifact:**
`artifacts/run_summaries/20260508_155656_h437_replacement_quality_revival_research_branch.json`

**Results:**

| Metric | Value |
|--------|-------|
| all_rows avg IC | 0.1173 (7/7 pos years) |
| top10_exiting avg IC | 0.1262 (7/7 pos years) |
| top10_stable avg IC | 0.0792 (7/7 pos years) |
| top10_entering avg IC | 0.0660 (6/7 pos years) |
| Enter vs Exit lift | **-0.0602** |

**Decision:** FAILED

**Interpretation:**
- H437 FAILED - opposite of hypothesis!
- Exiting tickers are STRONGER (IC=0.126) than all rows and stable
- Entering tickers are WEAKEST (IC=0.066)
- The entering vs exiting lift is -0.060 (entering is WORSE)
- This is completely opposite of the hypothesis
- Note: H388 already showed top-5 fresh weak vs stale-repeat controls failed
- This confirms the same pattern: exiting/stable tickers outperform entering ones

**Verdict: FAILED** (Dead-end D031)

**Next step:** Stop replacement quality testing. Both entering and exiting tickers are positive IC signals (which is interesting), but entering tickers are weaker than exiting ones. This aligns with H388's finding that fresh reappearances are not strong. Move to next queue item.