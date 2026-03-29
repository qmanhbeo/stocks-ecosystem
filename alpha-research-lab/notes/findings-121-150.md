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

## F126: The Live `full_library` Activation Branch Was Unblocked By Rebuilding the Producer Chain, Not By Inventing New Timing Logic; A Current-Year `S1` Extension Plus Grid-Backed `C4/C5/Dispersion` Builders Restored the Shared Matrix Through 2026-03-27 (2026-03-29, Session 62)

Session 62 resolved the operational blocker exposed in Session 60.

The real issue was upstream data production:
- the shared `full_library` matrix stopped at `2025-12-31`
- `C4`, `C5`, and dispersion builders were inheriting a stale historical `S1` grid
- current-year `S1` rows needed a dedicated live extension path

The fixes were:
- build `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
- merge that live extension into `build_rl_signal_matrix.py`
- rebuild `C4`, `C5`, and dispersion features from dense stock-day grids instead of the stale `S1` spine

After that rebuild chain, these shared artifacts became current through `2026-03-27`:
- `xs_rl_signal_matrix.parquet`
- `activation_state_daily.parquet`
- `activation_meta_daily.parquet`

**Key finding:** the activation branch was blocked by stale producer infrastructure, not by missing alpha or missing activation logic.

**Implication:** future live blockers should be treated first as data-contract and producer-chain problems, not as a cue to reopen broad hypothesis search.

## F127: On Current 2026 YTD Data, the Sticky Activated Book Still Trails VNINDEX, but It Materially Beats the Sticky Always-On Book; Activation Is Improving the Realized Path Even Before the Year Has Matured (2026-03-29, Session 62)

Once the live branch was refreshed, Session 62 built the first current-year activated-vs-always-on scoreboard.

`2026` YTD so far:
- sticky activated:
  - `-3.33%` relative vs VNINDEX
  - IR `-0.36`
- sticky always-on:
  - `-11.22%` relative
  - IR `-1.65`

Both are below benchmark in this short forward window so far, but the activated branch is still materially better.

**Key finding:** activation is not just a historical backtest improvement. It is already reducing damage in the current live-paper period, even though that short period is not yet benchmark-beating.

**Implication:** the right live comparison is activated vs always-on, not activated vs an idealized historical benchmark alone.

## F128: A Small Retention Bonus (`sticky_bonus_0p015`) Improved the Historical Activation Champion; Sticky Holdings Now Replace Plain `rel2_gt0` As the Best Uncapped Long-Only System (2026-03-29, Session 62)

Session 62 tested whether churn leakage could be reduced without changing the selector or the activation family.

Best result:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- `+509.76%` relative vs VNINDEX
- information ratio `0.9372`
- avg daily turnover `0.2227`

Plain `rel2_gt0` reference:
- `+480.72%` relative
- information ratio `0.9095`
- avg daily turnover `0.2269`

So a modest incumbent-retention bonus improved both return and IR while slightly reducing churn.

**Key finding:** the best current system is no longer the plain activation rule. It is the same rule plus a small retention bonus.

**Implication:** future refinement work should start from the sticky champion, not from plain `rel2_gt0`.

## F129: A Mild Sector Cap (`max 3 names per sector`) Helps Slightly but Is Dominated by the Sticky Champion; It Is a Secondary Refinement, Not the New Core (2026-03-29, Session 62)

Session 62 also tested mild sector concentration control on the activated selector.

Best sector-cap result:
- `sector_cap_3`
- `+482.21%` relative vs VNINDEX
- information ratio `0.9123`

This is slightly better than plain `rel2_gt0`, but still below the sticky champion:
- sticky `0.015`: `+509.76%` relative, IR `0.9372`

**Key finding:** mild sector diversification has some value, but it does not beat the retention-based improvement.

**Implication:** if sector control is revisited, it should be tested only as a companion to the sticky champion, not as a replacement for it.

## F130: Local Exposure Sizing Around `recent_rel2` Failed; Once the Selector-Efficacy Condition Is Positive, Binary Activation Still Beats the Nearby Sizing Variants (2026-03-29, Session 62)

Session 62 tested stepped and continuous exposure schedules using the same `recent_rel2` state that powers the activation champion.

Examples:
- `half_full_0_1bp`: `+379.51%` relative, IR `0.8441`
- `continuous_clip_1bp`: `+341.01%` relative, IR `0.7921`
- `quarter_half_full`: `+302.46%` relative, IR `0.7724`

All of them underperformed the plain binary activated rule:
- `h175__rel2_gt0`: `+480.72%` relative, IR `0.9095`

**Key finding:** nearby exposure-sizing variants are not the right way to improve this branch.

**Implication:** keep activation binary for now once the recent-efficacy condition is met, and only reopen sizing if a materially stronger state variable appears.

## F131: Sticky Retention and Mild Sector Diversification Do Not Stack; `sticky_bonus_0p015` Still Beats `sticky_bonus_0p015 + sector_cap_3` (2026-03-29, Session 63)

Session 63 started by testing whether the two independently positive local refinements from Session 62 could be combined.

Reference:
- `sticky_bonus_0p015`
- `+509.76%` relative vs VNINDEX
- IR `0.9372`

Combined candidate:
- `sticky_bonus_0p015 + sector_cap_3`
- `+498.04%` relative
- IR `0.9280`

So the mild sector cap did not compound with the sticky turnover reduction.

**Key finding:** sector diversification remains secondary. The sticky improvement is the real local gain; adding `sector_cap_3` on top does not create a new champion.

**Implication:** if sector control is used later, it should be tested only alongside stronger new information, not assumed to stack automatically with sticky retention.

## F132: A Direct Implementation-Pain Veto (`blocked3<=q80`) Improved the Sticky Champion Again; The Best Current System Is Now Sticky Retention Plus a Blocked-Buy Pressure Veto (2026-03-29, Session 63)

Session 63 then tested whether the sticky champion should deactivate when recent implementation strain is high.

Best result:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked3_q80`
- `+527.16%` relative vs VNINDEX
- IR `0.9471`
- avg cash `41.47%`
- blocked-buy events `42`

Sticky baseline:
- `+509.76%` relative
- IR `0.9372`
- blocked-buy events `68`

This is the first local refinement after Session 62 that improved the champion again.

**Key finding:** the most useful next refinement is not another confidence filter. It is a direct veto on recent blocked-buy strain.

**Implication:** the current best system is now:
- fixed selector-efficacy activation
- plus sticky retention
- plus a blocked-buy pressure veto

## F133: Basket-Coherence / Score-Dispersion Guards Failed on the Sticky Champion; They Reduced Return Too Much and Mostly Added Cash (2026-03-29, Session 63)

Session 63 tested several basket-shape guards on the sticky champion:
- coherence quantiles
- spread + score-std conjunctions
- spread/overlap and std/overlap conjunctions

All of them underperformed the sticky baseline.

Examples:
- `coh__q60`: `+423.72%` relative, IR `0.8960`, avg cash `58.63%`
- `coh__q70`: `+288.69%` relative, IR `0.7399`, avg cash `65.17%`
- sticky baseline: `+509.76%`, IR `0.9372`, avg cash `36.29%`

**Key finding:** current basket-shape coherence is not the lever that improves this branch.

**Implication:** future local work should stay focused on implementation strain and closely related veto variables, not on more coherence-style guards.

## F134: The Implementation-Pain Family Improved Again When Refined Locally; `blocked5<=q80` Beats the Earlier `blocked3<=q80` Winner (2026-03-29, Session 64)

Session 64 refined the blocked-buy veto family directly.

Best pure veto:
- `impl__blocked5_q80`
- `+590.23%` relative vs VNINDEX
- IR `1.0027`

Previous winner:
- `impl__blocked3_q80`
- `+527.16%` relative
- IR `0.9471`

So the slower blocked-buy memory turned out to be stronger than the shorter one.

**Key finding:** the implementation-pain branch is real enough that local refinement matters, and the better state variable is `blocked5`, not `blocked3`.

**Implication:** future veto-family work should center on `blocked5` and related strain persistence, not on returning to the older `blocked3` baseline.

## F135: Sector Control Finally Became Additive Once the Stronger `blocked5<=q80` Veto Was Active; The Current Best System Is `blocked5<=q80 + sector_cap_3` (2026-03-29, Session 64)

Session 64 then retested sector control against the stronger veto family.

Best overall result:
- `impl__blocked5_q80 + sector_cap_3`
- `+597.09%` relative vs VNINDEX
- IR `1.0093`

Reference:
- `impl__blocked5_q80`
- `+590.23%` relative
- IR `1.0027`

This is the first time sector control has clearly improved the best current system.

**Key finding:** sector diversification was not generally useless; it just needed to be paired with the right implementation-pain regime first.

**Implication:** the current best uncapped long-only system now includes:
- selector-efficacy activation
- sticky retention
- blocked-buy veto
- mild sector cap

## F136: The Current Live Winner Is Still Fully Defensive; On the Latest Live Date It Is `OFF / cash`, and Its 2026 YTD Outperformance vs Always-On Is Entirely Defensive So Far (2026-03-29, Session 64)

After rerunning the canonical live overlay and scoreboard on the new winner:
- rule: `blocked5<=q80 + sector_cap_3` on top of the sticky activation branch
- latest live state (`2026-03-26` signal / `2026-03-27` execution):
  - activation `OFF`
  - held names: none
  - cash `100.00%`

Current-year scoreboard:
- activated: `+5.73%` relative vs VNINDEX, IR `1.17`
- always-on: `-11.22%` relative, IR `-1.65`

**Key finding:** the forward live edge is still real relative to always-on, but for now it is entirely coming from defense.

**Implication:** the branch now needs monitoring and possibly mild re-entry logic, not more generic activation families.
