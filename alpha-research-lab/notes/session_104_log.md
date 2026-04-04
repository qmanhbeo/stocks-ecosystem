# Session 104 Log

## Objective
Run the next exact queue item after Session 103 closed the top-k stress-router branch:
- `H275`: test whether reduced-shape intraday atoms are strong enough to survive as offline signal-library state features, even if they do not survive as an activation router

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H274` had already failed and closed the top-k intraday stress-router branch on the frozen sticky contract
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- the next honest fallback from `next_steps.md` was explicitly signal-library scoped:
  - do not open another gate
  - instead audit whether reduced-shape intraday atoms can survive as offline state features
- the predeclared comparison anchors were:
  - `S1`
  - `C4`
  - `C12`
- the reduced-shape contract from `H258` was already available with strong overlap on the `2023-2025` branch

## What changed

Added:
- `analysis/h275_library_grade_intraday_shape_atoms.py`

Saved artifacts:
- `artifacts/run_summaries/latest_signal_library_intraday_shape_atoms.json`
- `artifacts/portfolio_baselines/20260404_131509_h275_library_grade_intraday_shape_atoms_results.parquet`
- `artifacts/portfolio_baselines/20260404_131509_h275_library_grade_intraday_shape_atoms_scored_panel.parquet`

### H275 - Library-Grade Intraday Shape Atom Audit
**Hypothesis:**
Even if reduced-shape intraday information is not strong enough to become a selector-state gate, the orthogonal disagreement part of that information may still survive as offline state features for the signal library.

**Command / code:**
`conda run -n stocks python analysis/h275_library_grade_intraday_shape_atoms.py`

**Inputs:**
- reduced-shape intraday source:
  - `H258` reduced-shape panel
- evaluation window:
  - observed subset only
  - `2023-2025` only
- anchor columns:
  - `s1_proba`
  - `c4_oc_asym_5d`
  - `c12_gap_absorb_3`
- predeclared candidate atoms:
  - raw:
    - `fade_tension_rank`
    - `failed_breakout_rank`
    - `intraday_shape_core_rank`
  - disagreement:
    - `fade_tension_disagreement`
    - `intraday_shape_core_disagreement`
- dev gate:
  - standalone IC `> 0.01`
  - positive years `>= 60%`
  - max dev correlation `< 0.30` versus `S1`, `C4`, and `C12`
- holdout rule:
  - validation IC `> 0.01`
  - confirmation IC `> 0.01`

**Saved artifact:**
`artifacts/run_summaries/latest_signal_library_intraday_shape_atoms.json`

| Metric | Value | Note |
|--------|-------|------|
| observed row count | `243,763` | reduced-shape observed subset merged to the RL matrix |
| matrix row count | `258,375` | `2023-2025` matrix rows |
| observed row share | `0.9434` | observed reduced-shape share on the audited window |
| observed dates | `718` | `2023-2025` overlap dates |
| observed tickers | `394` | full audited ticker breadth |
| winner 1 | `fade_tension_disagreement` | disagreement atom |
| winner 1 dev / validation / confirmation IC | `+0.0323 / +0.0367 / +0.0202` | all above the `0.01` gate |
| winner 1 max dev anchor corr | `0.0667` | well below the `0.30` redundancy bar |
| winner 2 | `intraday_shape_core_disagreement` | disagreement atom |
| winner 2 dev / validation / confirmation IC | `+0.0330 / +0.0259 / +0.0160` | all above the `0.01` gate |
| winner 2 max dev anchor corr | `0.0751` | well below the `0.30` redundancy bar |
| strongest raw atom | `fade_tension_rank` | raw reduced-shape atom |
| strongest raw atom dev / validation / confirmation IC | `+0.0701 / +0.0821 / +0.0568` | predictive but not orthogonal |
| strongest raw atom max dev anchor corr | `0.3189` | fails the redundancy bar against `S1` |

**Result:**
`H275` passes as offline signal-library evidence.

What passed:
- two disagreement atoms survived the full standalone gate on the observed subset:
  - `fade_tension_disagreement`
  - `intraday_shape_core_disagreement`
- both stayed:
  - predictive in dev
  - positive on validation
  - positive on confirmation
  - below the correlation bar against `S1`, `C4`, and `C12`

What did **not** pass:
- the raw reduced-shape atoms were not clean library candidates
- they were predictive, but redundant:
  - `fade_tension_rank` failed on `S1` correlation
  - `failed_breakout_rank` failed on `C4` correlation
  - `intraday_shape_core_rank` failed on `C4` correlation

So the transportable part of the intraday branch is not the raw atom itself.
It is the disagreement component left after removing the existing daily continuation / gap / close-location axes.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 104 resolves:
- `H275` passes:
  - reduced-shape intraday disagreement survives as offline state-feature evidence
  - the raw atoms are real but redundant with the current daily library

Branch effect:
- promote:
  - `fade_tension_disagreement`
  - `intraday_shape_core_disagreement`
  as observed-subset offline signal-library candidates
- do **not** promote any live gate or activation rule from this line
- keep the live sticky branch unchanged
- if more timing experimentation is desired after this library-grade resolution:
  - the next materially different side branch is `event-to-intraday state transition`
- otherwise:
  - pause timing-model invention and wait for new data or more forward evidence

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h275_library_grade_intraday_shape_atoms.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h275_library_grade_intraday_shape_atoms.py`
- read `artifacts/run_summaries/latest_signal_library_intraday_shape_atoms.json`

Verdict:
- `H275`: **PASSED**
