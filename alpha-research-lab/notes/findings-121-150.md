# Findings 121-150

## F121: A Faster Smoothed Selector-Efficacy Rule (`rel2_gt0`) Is the New Long-Only Champion; It Beat Both the Always-On Selector and the First H170 Winner (2026-03-29, Session 59)

Session 59 stress-tested the H170 family with:
- threshold sweeps
- smoothing-window sweeps
- hit-rate gates
- yearly walk-forward rule selection

The strongest result was a **simpler** fixed rule than the original H170 winner:

| Strategy | Activation Rule | Total Return | Relative vs VNINDEX | IR | Max DD |
|---|---|---:|---:|---:|---:|
| `full_library + k5_r5_eq` | `always_on` | +769.71% | +346.40% | 0.81 | -34.04% |
| `full_library + k5_r5_eq` | `H170 recentsm__rel3_gt0` | +841.14% | +383.07% | 0.84 | -34.00% |
| `full_library + k5_r5_eq` | **`H175 h175__rel2_gt0`** | **+1052.77%** | **+491.69%** | **0.93** | **-20.57%** |

This means:
- the activation edge is real
- the edge is **not** coming from broader complexity
- a short-memory selector-efficacy rule is currently best

`h175__rel2_gt0` only uses a faster smoothed version of completed-cycle relative selector performance.
It is still path-dependent and still look-ahead safe.

**Key finding:** once activation alpha became real, a **simpler** efficacy-memory rule beat both the always-on selector and the more elaborate first-generation H170 gate.

**Implication:** the active branch should now stress and validate the `rel2_gt0` family rather than jumping immediately to larger learned timing models.

## F122: Added Complexity Did Not Beat the New Fixed Activation Champion; Three-State Sizing, Walk-Forward Rule Selection, and the Compact Meta-Model All Lost to `h175__rel2_gt0` (2026-03-29, Session 59)

Session 59 also tested three follow-up complexity paths:

### 1. H175 yearly walk-forward rule selection
- `h175__wf_best_train_rel`
- result: `+369.89%` total, `+141.19%` relative, IR `0.49`

### 2. H176 three-state sizing on top of H170
Best result:
- `h176__rel3_0_p01`
- `+580.02%` total, `+249.04%` relative, IR `0.70`

### 3. H177 compact walk-forward logistic meta-model
Best result:
- `h177__prob_ge60`
- `+480.78%` total, `+198.10%` relative, IR `0.60`

All of them underperformed the new fixed champion:
- `h175__rel2_gt0`: `+1052.77%` total, `+491.69%` relative, IR `0.93`

**Key finding:** at the current stage, the activation problem does **not** reward additional model complexity. The fixed path-dependent rule is stronger than:
- yearly rule re-selection
- 3-state sizing
- compact logistic meta-modeling

**Implication:** the next experiments should stay disciplined:
- stress the fixed `rel2_gt0` champion more honestly
- only add complexity if it beats that exact rule
- do not assume that “more learned” means “better activation alpha”

## F123: `H175 rel2_gt0` Survived Honest Stress; It Beat the Always-On Selector in 15 of 16 Start-Year / Fee Scenarios and Kept the Original `2019-2025` Edge Intact (2026-03-29, Session 60)

Session 60 finally stressed the fixed champion the right way:
- fixed activation-memory warm-up from `2015`
- alternate evaluation starts: `2016`, `2017`, `2018`, `2019`
- round-trip cost stress: `0.10%`, `0.30%`, `0.50%`, `0.70%`

Headline result:
- `15 / 16` scenarios beat always-on on both relative return and information ratio

Original reference scenario still held:

| Strategy | Window | RT Cost | Relative vs VNINDEX | IR | Max DD |
|---|---|---:|---:|---:|---:|
| `full_library + k5_r5_eq + always_on` | 2019–2025 | 0.30% | +346.40% | 0.81 | -34.04% |
| `full_library + k5_r5_eq + h175__rel2_gt0` | 2019–2025 | 0.30% | **+491.69%** | **0.93** | **-20.57%** |

Best stressed scenario:
- start `2016`
- RT cost `0.10%`
- `+1181.98%` relative vs VNINDEX
- IR `0.94`

Only failing scenario:
- start `2017`
- RT cost `0.10%`
- relative underperformance vs always-on: `-0.5904`
- IR underperformance: `-0.0030`

**Key finding:** the fixed champion is no longer just “best on the original holdout.” It is robust enough to treat as the current operational activation rule.

**Implication:** the next branch should shift from gate discovery to honest live-data operationalization.

## F124: The Activation Overlay Is Operational, But Not Yet Truly Live; The Latest Matrix-Supported Overlay State Is `ON` With `DBT`, `FIT`, `KLB`, `PDN`, `TMT`, While the Shared `full_library` Matrix Still Ends at 2025-12-31 (2026-03-29, Session 60)

Session 60 implemented `H179` and turned the activation champion into an execution-facing overlay runner.

Latest matrix-supported state:
- signal date: `2025-12-30`
- execution date: `2025-12-31`
- activation: `ON`
- recent `rel2` state: `+0.008169`
- held names after execution:
  - `DBT`
  - `FIT`
  - `KLB`
  - `PDN`
  - `TMT`

But the runner also exposed the real operational blocker:
- stock data extends to `2026-03-27`
- `data/features/xs_rl_signal_matrix.parquet` still ends at `2025-12-31`

So the activation branch is now blocked by **live feature freshness**, not by another open activation hypothesis.

**Key finding:** the overlay runner exists and works, but it is only honest through the matrix end date.

**Implication:** current-date operational work should focus on rebuilding the full-library signal surface and then rerunning the overlay, not on inventing new timing logic.

## F125: Small Local Guards Around `rel2_gt0` Did Not Improve the Champion; The Best One Reduced Drawdown Slightly but Gave Up Too Much Return and IR (2026-03-29, Session 60)

Session 60 tested a deliberately narrow set of local augmentations around `h175__rel2_gt0`:
- hit-rate guards
- selector-confidence guards
- entry-quality guards
- drawdown guard
- one blocked-buy pressure guard

Best augmentation:
- `h180__rel2_gt0_conf_q50`
- `+413.39%` relative vs VNINDEX
- IR `0.88`
- max DD `-18.94%`

Champion baseline remained better:
- `h175__rel2_gt0`
- `+491.69%` relative
- IR `0.93`
- max DD `-20.57%`

Delta of best augmentation vs champion:
- relative return: `-0.7830`
- IR: `-0.0417`

**Key finding:** nearby cosmetic guards do not improve the fixed champion enough to justify replacing it.

**Implication:** stop spending time on small local tweaks around `rel2_gt0` until the live overlay branch is current and being monitored in real time.
