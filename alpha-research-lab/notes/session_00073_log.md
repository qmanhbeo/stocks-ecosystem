# Session 73 Log

## Objective
Implement the first genuinely new-data exit ladder and carry it through its real stop conditions.

Planned order:
- `H221`: corporate-event surface artifact + coverage audit
- `H222`: event predictive screening on the continuation target
- `H223`: deterministic event-informed exit integration only if `H222` passes
- `H224`: sticky-activation compatibility only if `H223` passes
- `H225-H228`: intraday / auction structure branch only if the event branch fails
- `H229`: order-book / queue feasibility audit if corporate events and intraday do not open a deployable branch

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- no tuning on `2026+`
- live sticky branch remains frozen:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## Starting point

Session 72 had already closed the continuation / hold-vs-exit hazard branch:
- `H218`: fail
- `H219/H220`: skipped

That meant the next honest exit-side branch needed a genuinely new information source, not another reformulation over the same daily OHLCV-derived state.

## Implementation

### New reusable code

Added:
- `src/event_surface_research.py`
  - builds the canonical event surface on the matrix spine
  - merges sparse corporate-event / insider / earnings-timing information into a dense `(time, ticker)` panel
  - exposes event feature lists for screening and deterministic integration
- `data_tools/build_event_surface_daily.py`
  - canonical builder for `data/features/event_surface_daily.parquet`

Extended:
- `src/deterministic_portfolio.py`
  - generic `coef__feature_name` support in `continuation_hazard`
  - `multi_rule_any` family for clean rule composition
  - current-step feature-matrix values now available to exit rules
- `src/exit_experiment_utils.py`
  - `load_full_library_backbone(...)` can now attach extra feature frames like the event surface without contaminating selector scoring

Tests:
- `tests/test_event_surface_research.py`
- extended `tests/test_exit_alpha.py`

### New analyses

Added:
- `analysis/h221_event_surface_artifact.py`
- `analysis/h222_event_surface_predictive_screen.py`
- `analysis/h223_event_surface_exit_integration.py`
- `analysis/h224_event_surface_activation_compatibility.py`
- `analysis/h225_intraday_structure_feasibility.py`
- `analysis/h226_intraday_predictive_screen.py`
- `analysis/h227_intraday_exit_integration.py`
- `analysis/h228_intraday_activation_compatibility.py`
- `analysis/h229_order_book_feasibility_audit.py`

## H221 — Corporate Event Surface Artifact

Result:
- **PASS** on coverage

New artifact:
- `data/features/event_surface_daily.parquet`

Coverage summary:
- `394` tickers
- `845,646` rows
- held-position coverage `89.59%`
- dividend-event tickers `51`
- issuance-event tickers `52`
- insider-event tickers `387`

Interpretation:
- the corporate-event branch is locally usable
- this is not a fake data-availability branch

## H222 — Event Predictive Screening

Target:
- same continuation / hold-vs-exit label used by Session 72

Models tested:
- `event_only_core`
- `event_plus_path_core`
- `event_plus_path_thesis`

Best model:
- `event_only_core`
- validation AUC `0.5180`
- validation top-quintile hold advantage `-0.0030`
- confirmation AUC `0.4862`
- confirmation top-quintile hold advantage `-0.0108`

Branch result:
- **FAIL**

Interpretation:
- event timing exists in the data now
- it still does not produce useful continuation / exit alpha on the locked protocol
- the event branch dies before deterministic integration

## H223 — Event Exit Integration

Rule:
- only run if `H222` produces a promoted event model

Result:
- **SKIP**
- reason:
  - `H222` produced no promoted event model

## H224 — Event Sticky Compatibility

Rule:
- only run if `H223` produces a promoted exit winner

Result:
- **SKIP**
- reason:
  - `H223` was skipped

## H225 — Intraday / Auction Structure Feasibility

Result:
- **FAIL** on coverage

Local state:
- only `data/stock/gia_lich_su_FPT_1H.parquet` exists
- held-position coverage `0.00%`

Interpretation:
- the local intraday branch is not usable for general exit research

## H226-H228 — Intraday Follow-through

Result:
- **SKIP** by rule

Reasons:
- `H226`: skipped because `H225` coverage gate failed
- `H227`: skipped because `H226` produced no promoted intraday model
- `H228`: skipped because `H227` produced no promoted exit winner

## H229 — Order-book / Queue Feasibility Audit

Result:
- **FAIL** locally

Audit conclusion:
- no historical queue/depth archive exists under local `data/`
- only schema evidence exists in:
  - `analysis/probe_vnstock2_output.txt`

Interpretation:
- order-book / queue research is not feasible on the current local workspace

## Branch decision

Session 73 closes the first genuinely new-data exit ladder.

Current conclusions:
- the corporate-event surface is worth keeping as a published artifact
- it does **not** create a useful continuation / exit branch on current data
- local intraday coverage is too sparse
- local order-book history is absent

Therefore:
- stop exit-side research on the current local data stack
- do **not** reopen `H221-H229` without actual new data acquisition
- keep the live branch unchanged
- keep H211 as offline-only exit evidence

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_exit_event_surface_artifact.json`
- `artifacts/run_summaries/latest_portfolio_exit_event_surface_predictive_screen.json`
- `artifacts/run_summaries/latest_portfolio_exit_event_surface_integration.json`
- `artifacts/run_summaries/latest_portfolio_exit_event_surface_activation_compatibility.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_structure_feasibility.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_predictive_screen.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_integration.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_activation_compatibility.json`
- `artifacts/run_summaries/latest_portfolio_exit_order_book_feasibility_audit.json`

New feature artifact:
- `data/features/event_surface_daily.parquet`

## Validation

Session 73 hygiene completed:
- `python -m py_compile` passed on all touched files
- focused tests passed:
  - `tests/test_event_surface_research.py`
  - `tests/test_exit_alpha.py`
  - `tests/test_continuation_exit_research.py`
- `git diff --check` will be run after doc updates
