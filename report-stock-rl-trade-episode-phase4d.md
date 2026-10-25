# Stock RL Phase 4D — Supervised Exit Test

**H6: Inconclusive.** Frozen-entry supervised exits show predictive ordering, but not a reliable advantage over the predeclared controls. This experiment does not establish that the signals produce profitable trade timing.

## Results

| Policy / measure | 12 training tickers | 3 unseen tickers |
|---|---:|---:|
| ExtraTrees + S1/C16 chronological CAGR | 1.45% | 3.01% |
| Matched random exit mean CAGR | 0.59% | −0.28% |
| Mechanical 20-interval exit CAGR | 6.19% | 4.55% |
| ExtraTrees + S1/C16 exposure | 25.8% | 25.7% |

CAGRs are equal-weight means of separate stock paths, not a combined portfolio. Randomized controls shared all entry dates; for ExtraTrees + S1/C16 they matched mean duration within 1.2 intervals and exposure within 2.7 percentage points. The paired 95% CAGR-difference intervals versus matched random were wide and crossed zero: training +0.86 pp [−5.17, +6.45], unseen +3.29 pp [−5.99, +12.50]. The supervised controller beat the three-day baseline but not the stronger 20-day mechanical exit.

On exploratory labels, ExtraTrees Spearman correlation was 0.464 market-only and 0.469 with S1/C16; MAE improved from 0.531 to 0.529. Ridge Alpha features did not improve MAE. This is evidence of predictive association, not proof of decision value. The three unseen tickers and 2023–25 exploratory period provide limited, previously examined evidence.

Frozen PPO’s separate full-policy reference had 16.6–17.8% training-ticker CAGR and 14.0% unseen CAGR, with 94–97% exposure and roughly 36–38% drawdowns. PPO selected different entries, so this is descriptive rather than an exit-only comparison. The PPO-entry diagnostic is overlapping per-trade analysis and is not a portfolio result.

## Protocol and verification

Models used 20,129 training examples from 12 tickers (2015–19); thresholds used 2020–22 validation, and exploratory evaluation used 2023–25. DGC, MBB, and VHC were excluded from fitting and threshold selection. No 2026 observations entered. Four supervised variants and 100 randomized replicates/model were evaluated; PPO was not retrained. Reward and next-open execution were unchanged.

H6 remains **inconclusive**, not contradicted: uncertainty permits material gains, Ridge random controls missed the predeclared duration/exposure match, and no model beat all controls. Alpha augmentation helped ExtraTrees descriptively, without a precise, consistent advantage. One initial attempt stopped before evaluation; the successful run completed. A NaN in a reused PPO summary interrupted JSON serialization, so final JSON was rebuilt from saved CSVs without refitting or reevaluating.

Focused tests: **71 passed**; Ruff passed. No checkpoint or shared-data changes were detected. Compact result tables and model hashes are in `RL-trading-agent/research/trade_episode/phase4d/results/`; model files remain isolated under the ignored `RL-trading-agent/artifacts/trade_episode/phase4d-20261025-run2/`.

**Next:** test a predeclared exit policy on a later untouched period, with more unseen tickers and adequate matched controls, before investing in further PPO training.

**Provenance:** evaluation code commit `501f6c2cf41434a08083c8567cd6bb9d2f9b33a6`; metrics finalizer commit `e3b84c6302027802fab269f37839ad5b76f060fd`. The report/artifact commit SHA and push receipt are provided in the delivery handoff; the completed experiment branch is pushed without rewriting history.
