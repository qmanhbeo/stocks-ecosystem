# Session 88 Log

## Objective
Run `H231`, the first honest acquisition-side pass on the partial CafeF intraday surface:
- prove whether a representative `2023-2025` subset can be normalized onto the VCI daily backbone
- produce an explicitly provisional `H232` lower-bound coverage / continuity read
- avoid any timing-alpha claim or final source promotion / rejection while the fetch remains partial

This session did not try to change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- the daily-data synthesis queue was closed by `H256`
- acquisition-first timing work was the active non-live priority
- the old local intraday verdict (`H225`) was obsolete because the workspace now had a real multi-ticker CafeF fetch
- the honest question was no longer "does intraday alpha work?"
- it was:
  - can the current partial CafeF surface be normalized cleanly?
  - what artifact shape looks plausible?
  - what does the current fetched subset already imply about lower-bound coverage?

## What changed

Added:
- `analysis/h231_intraday_normalization_pilot.py`
- `src/intraday_acquisition_research.py`
- `tests/test_intraday_acquisition_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_timing_intraday_normalization_pilot.json`
- `artifacts/timing_data/20260331_130325_h231_intraday_normalization_pilot_features.parquet`
- `artifacts/timing_data/20260331_130325_h231_intraday_normalization_pilot_factors.parquet`
- `artifacts/timing_data/20260331_130325_h231_intraday_normalization_pilot_ticker_summary.parquet`
- `artifacts/timing_data/20260331_130325_h231_intraday_normalization_pilot_coverage.parquet`
- `artifacts/timing_data/20260331_130325_h231_intraday_normalization_pilot_coverage_summary.parquet`

## H231 outcome

### Contract audited

`H231` stayed narrow:
- analysis window:
  - `2023-01-01` through `2025-12-31`
- no `2026+` read
- no timing-alpha screen
- no attempt to publish the canonical `intraday_structure_daily.parquet` artifact yet

Representative pilot:
- `20` tickers
- explicitly included:
  - liquid banks
  - liquid industrials
  - smaller illiquid names

Carried lower-bound read:
- current raw CafeF subset only
- use it to estimate `H232` coverage / continuity
- do **not** treat that estimate as a final gate while fetch remains partial

### What happened

The good news:
- all `20` representative pilot tickers normalized cleanly onto the VCI backbone
- first-hour and close-hour feature extraction is complete on the pilot:
  - first-hour feature share `1.00`
  - close-hour feature share `1.00`
- current fetched subset already covers a meaningful share of the continuation panel:
  - `207` raw tickers with overlap
  - held-row coverage lower bound `46.57%`
  - missing-session rate in-window `6.61%`

The limiting result:
- the pilot does **not** support a full-session intraday artifact yet
- pilot complete-day share is only `72.32%`, below the `0.90` gate
- current all-available complete-day share among present sessions is `72.11%`
- held-row complete-day lower bound is only `31.71%`

Where the weakness sits:
- liquid banks:
  - complete-day share `97.02%`
- liquid fill names:
  - complete-day share `97.14%`
- liquid industrials:
  - complete-day share `86.04%`
- small illiquid tail:
  - complete-day share `1.12%`
  - median bars per day `1.25`

Interpretation:
- the source is not dead
- the VCI bridge works
- open / first-hour / close-hour structure looks materially more promising than a universal full-session surface
- the current partial fetch is already informative enough to reject the broadest artifact claim:
  - "all representative names reliably provide a five-bar day"
- but it is **not** informative enough to close `H232` as pass or fail for the final source

## Branch decision

Do **not** change the live branch.

What `H231` resolves:
- representative normalization is real
- a reduced-shape intraday artifact is plausible
- full-session completeness is the current bottleneck, especially in the illiquid tail

Branch effect:
- `H231` is **MIXED**
- keep the intraday acquisition branch alive
- keep `H232` open and explicitly provisional while the fetch remains partial
- do **not** publish full `intraday_structure_daily.parquet` yet
- do **not** claim timing alpha from this pass

Next honest move from this result:
- continue the fetch and rerun the `H232` lower-bound read when coverage materially changes
- if intraday work continues before fetch completion, scope it to reduced-shape structure:
  - open gap
  - first hour
  - close hour
- `H234` richer event-source audit remains a valid parallel branch

## Validation

Completed:
- `python -m py_compile analysis/h231_intraday_normalization_pilot.py src/intraday_acquisition_research.py tests/test_intraday_acquisition_research.py`
- `pytest -q tests/test_intraday_acquisition_research.py tests/test_adjust_cafef_intraday_to_vci.py`
- full `conda run -n stocks python analysis/h231_intraday_normalization_pilot.py` run completed

Verdict:
- `H231`: **MIXED**
- `H232`: **DEFERRED / PROVISIONAL**
