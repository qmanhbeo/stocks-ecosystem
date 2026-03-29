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

## F137: The Complex `blocked5<=q80 + sector_cap_3` Winner Is Reproducible Once Historical and Live Runners Share One Canonical Spec; Session 65 Parity Passed Exactly Against the Archived Session 64 Reference (2026-03-29, Session 65)

Session 65 first solved the branch-drift problem rather than blindly running more tweaks.

Changes:
- one canonical champion spec
- one shared gate-construction path
- live overlay and live scoreboard rerun on that shared path

Result:
- the historical `2019-2025` reproduction of
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`
  matched the archived Session 64 reference exactly:
  - portfolio total return `12.581092`
  - relative vs VNINDEX `5.970914`
  - information ratio `1.009283`
  - avg cash `0.427508`
  - avg daily turnover `0.203567`
- the refreshed `H179` and `H183` runners matched the direct champion runner exactly on overlapping dates

**Key finding:** the defense-vs-overfit problem was not caused by a silent live/historical runner mismatch. The complex winner is real on the current artifact surface.

**Implication:** the next branch decision had to come from honest pseudo-live testing, not from blaming parity drift.

## F138: The Complex Historical Winner Fails the Expanding-Train / Next-Year Pseudo-Live Ladder; The Simpler Sticky Baseline Beats All Blocked-Buy Variants on Mean Relative Return and Mean IR Over 2023-2025 (2026-03-29, Session 65)

Session 65 then ran the first proper pseudo-live ladder with:
- train-only threshold calibration
- expanding train windows
- next-year tests for `2023`, `2024`, and `2025`

Candidate ranking:

| Variant | Mean Relative Return | Mean IR | Mean Cash | Frontier |
|---|---:|---:|---:|---|
| `sticky_bonus_0p015` | **+14.91%** | **0.5856** | 37.87% | Yes |
| `impl__blocked5_q80 + sector_cap_3` | +14.04% | 0.4275 | 41.55% | No |
| `impl__blocked5_q80` | +14.04% | 0.4275 | 41.55% | No |
| `impl__blocked3_q80` | +13.18% | 0.3912 | 42.22% | No |

So the complex winner was not “wrong” historically.
It was simply weaker than the simpler sticky baseline once evaluated under train-only pseudo-live discipline.

**Key finding:** the blocked-buy veto family and sector cap improve historical full-window results, but they do not survive the stronger pseudo-live ranking bar.

**Implication:** the active live branch should be rolled back to `sticky_bonus_0p015` unless and until new forward evidence justifies reopening the veto family.

## F139: Rolling Back to Sticky Produces a More Credible Live Branch; It Is Active Again, Holds `ANV`, `PGV`, `PTB`, `PTL`, `VSI`, and Still Beats Sticky Always-On in 2026 YTD Even Though Both Trail VNINDEX (2026-03-29, Session 65)

After `H193` rejected the complex winner, Session 65 reran the live overlay and live scoreboard on the rollback candidate:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

Latest live state (`2026-03-26` signal / `2026-03-27` execution):
- activation `ON`
- holdings:
  - `ANV`
  - `PGV`
  - `PTB`
  - `PTL`
  - `VSI`

`2026` YTD scoreboard:
- activated sticky:
  - `-3.33%` relative vs VNINDEX
  - IR `-0.36`
- sticky always-on:
  - `-11.22%` relative
  - IR `-1.65`

So the rollback branch is not benchmark-beating yet in this short live-forward slice, but it is:
- active rather than pathologically defensive
- materially better than its always-on counterpart

**Key finding:** the simpler sticky branch is the right current live branch even though the more complex blocked-buy family remains the stronger historical full-window system.

**Implication:** forward monitoring should now focus on sticky vs sticky always-on. The blocked-buy family should stay archived until that simpler live branch clearly fails.

## F140: The Locked Anti-Leakage Protocol Is Now Codified In Code: Dev `2015-2022`, Validation `2023-2024`, One-Shot Confirmation `2025`, Forward Lockbox `2026+` (2026-03-29, Session 66)

Session 66 moved the selection-side branch out of free-form notes and into reusable code:
- `src/research_protocol.py`
- `src/tradability_conditioned_research.py`

This locks the offline research process to:
- dev / discovery: `2015-2022`
- validation ranking: `2023-2024`
- one-shot confirmation: `2025`
- live / forward lockbox: `2026+`

**Key finding:** the repo now has a first-class anti-leakage protocol for reopening alpha discovery while the live sticky branch stays frozen.

**Implication:** future selection-side work should stop scattering year windows through ad hoc scripts. New selector candidates should rank on dev / validation first and only touch `2025` once per promoted candidate.

## F141: H151 Fails Cleanly; No Narrow Tradability-Conditioned Composite From The Existing Library Beats The Always-On `full_library` Selector Baseline (2026-03-29, Session 66)

Session 66 ran the first locked-protocol selector bakeoff over the H150-derived sub-core:
- `core_4 = S1 + C7 + C12 + C13`
- `core_5 = S1 + C7 + C10 + C12 + C13`
- `core_6 = S1 + C7 + C8 + C10 + C12 + C13`

Validation (`2023-2024`) winner remained the baseline:
- `full_library_baseline`
- relative return `+43.45%`
- IR `0.8211`

Narrow composites all lost validation badly:
- `core_5`: `-23.98%`, IR `-0.4041`
- `core_6`: `-33.20%`, IR `-0.6980`
- `core_4`: `-54.97%`, IR `-1.4111`

None survived `2025` confirmation and no selector candidate was promoted.

**Key finding:** the strongest conditional-uplift signals from H150 do not automatically form a stronger standalone selector when compressed into a small always-on composite.

**Implication:** the current full-library selector remains the right backbone. Further selection-side work should focus on additive atoms or genuinely new signals, not on shrinking the library to the H150 sub-core.

## F142: H152 Finds Four New Tradability-Conditioned Standalone Signals With Real Dev IC And Low S1 Correlation, But None Yet Show Naive Always-On Selector Relevance (2026-03-29, Session 66)

Session 66 then ran the first locked-protocol tradable-state search inside the basic liquidity-opening state:
- `liq_open_basic = can_buy_next_open & tv_to_adv20 >= 1.10 & clv >= 0.45`

Dev-pass standalone survivors:
- `h152_sector_laggard_tradable`
  - dev IC `+0.0264`
  - corr with S1 `+0.1536`
  - validation IC `+0.0163`
- `h152_limit_release_pressure`
  - dev IC `+0.0236`
  - corr with S1 `+0.1552`
  - validation IC `+0.0127`
- `h152_liq_open_continue_3`
  - dev IC `+0.0248`
  - corr with S1 `+0.1331`
- `h152_breakout_volume_quality`
  - dev IC `+0.0196`
  - corr with S1 `+0.1006`

But their naive always-on selector tests were poor:
- validation relative returns ranged from `-23.00%` to `-60.76%`
- no signal was promoted to selector stage

**Key finding:** there are still new tradability-conditioned alpha atoms available in the data, but they are not drop-in replacements for the current selector.

**Implication:** the right next research move is additive bakeoff work on the strongest new atoms, not immediate selector replacement or live-branch changes.

## F143: Sequential Hypothesis Ladders Are Now The Standard Lab Method; Experiment Families Should Use Explicit Decision Trees Rather Than Broad Unordered Sweeps (2026-03-29, Session 66)

Session 66 made explicit what had already become the most reliable working pattern:
- run a branch as a sequence
- let each result unlock, narrow, or kill the next step
- freeze live branches while new hypotheses run offline
- avoid continuing to tune a failed family unless the branch is intentionally reopened

**Key finding:** this process discipline is not just stylistic. It is the main defense against quiet test-set tuning and branch drift.

**Implication:** future sessions should default to ordered hypothesis ladders with explicit stop / continue conditions, not flat experiment lists.

## F144: H196 Closes The First Additive Path; None Of The H152 Atoms Survive The Locked Selector-Level Promotion Gate On Top Of `full_library` (2026-03-29, Session 67)

Session 67 tested the strongest H152 atoms in the most conservative additive form:
- keep the selector backbone fixed at `full_library`
- add exactly one atom at a time
- no custom weighting
- no new activation logic

Best candidate:
- `full_library + h152_sector_laggard_tradable`
- validation relative return:
  - `+47.01%`
  - baseline `+43.45%`
  - delta `+3.56%`
- validation IR:
  - `0.8863`
  - baseline `0.8211`
  - delta `+0.0653`

But that still did **not** pass the locked gate because confirmation deteriorated too much on risk-adjusted terms.

All other H152 atoms were worse:
- `h152_breakout_volume_quality`
- `h152_limit_release_pressure`
- `h152_liq_open_continue_3`

`H197/H198` were then skipped by rule because H196 produced no promoted atoms.

**Key finding:** the H152 atoms have real standalone state-level signal, but they are not additive enough one at a time to justify promotion on top of the current selector backbone.

**Implication:** the first additive family is closed. Do not keep tuning the H152 atoms against `2025`. The next honest move is a second-wave signal search, not a wider additive sweep over the same atoms.

## F145: H199 Finds One Worth-Carrying Second-Wave Atom, `h199_sector_laggard_gap_absorb`; It Is Not A Selector Replacement, But It Is Strong Enough To Enter The Next Additive Ladder (2026-03-29, Session 67)

Session 67 then ran a more specific tradability-transition search inside `liq_open_basic`:
- `h199_floor_release_rebound`
- `h199_ceiling_release_followthrough`
- `h199_sector_laggard_gap_absorb`
- `h199_breakout_after_compression`
- `h199_buyable_reversal_after_1d_weakness`

The clear winner was:
- `h199_sector_laggard_gap_absorb`
  - dev IC `+0.0117`
  - corr with S1 `+0.0629`
  - validation IC `+0.0015`
  - confirmation IC `+0.0135`
  - naive validation selector relevance `+3.70%`

Two others passed the dev gate but failed the selector relevance check:
- `h199_breakout_after_compression`
- `h199_ceiling_release_followthrough`

**Key finding:** the second-wave search did not yield a replacement selector, but it did yield one credible new atom with low S1 correlation and positive validation / confirmation IC inside the tradable state.

**Implication:** the next sequential branch should test exactly one additive family:
- `H200`: add `h199_sector_laggard_gap_absorb` to `full_library`
- then only if it passes:
  - `H201`: state-scoped additive blend
  - `H202`: sticky-activation compatibility

## F146: The H199 Winner, `h199_sector_laggard_gap_absorb`, Survives Both The Additive And State-Scoped Selector Ladders; It Is The Strongest New Offline Selector Candidate Since The Live Branch Was Frozen (2026-03-29, Session 68)

Session 68 advanced the promoted H199 atom through the next two selector-only gates.

### H200 additive result
- `full_library + h199_sector_laggard_gap_absorb`
- validation relative return:
  - `+68.21%`
  - baseline `+43.45%`
  - delta `+24.76%`
- validation IR:
  - `1.16`
  - baseline `0.82`
  - delta `+0.34`
- confirmation relative return:
  - `-5.95%`
  - baseline `-20.02%`
  - delta `+14.07%`

### H201 state-scoped result
Best variant:
- `state_blend__h199_sector_laggard_gap_absorb__30`
- validation relative `+46.17%`
- validation IR `0.90`
- confirmation relative `-13.43%`
- confirmation delta vs baseline `+6.58%`

**Key finding:** this is the first post-freeze selector candidate that survives both an additive selector bakeoff and a state-scoped refinement ladder under the locked anti-leakage protocol.

**Implication:** `state_blend__h199_sector_laggard_gap_absorb__30` is now the current **offline lead selector candidate**. It deserves to be carried forward in selector-side research, but not yet promoted to the live branch.

## F147: The New H199-Based Selector Candidate Fails Frozen Sticky-Activation Compatibility; Stronger Selection Alpha Alone Is Not Enough To Replace The Live Branch (2026-03-29, Session 68)

Session 68 then ran the decisive compatibility check:
- keep activation fixed at:
  - `h175__rel2_gt0 + sticky_bonus_0p015`
- compare:
  - `winner_always_on`
  - `winner_plus_sticky`
  - incumbent `full_library_plus_sticky`

Results:
- `winner_always_on`
  - validation relative `+46.17%`
  - validation IR `0.90`
- incumbent `full_library_plus_sticky`
  - validation relative `+29.65%`
  - validation IR `0.61`
  - confirmation relative `+18.80%`
- `winner_plus_sticky`
  - validation relative `+16.64%`
  - validation delta vs incumbent `-13.01%`
  - validation IR `0.40`
  - validation IR delta `-0.21`
  - confirmation relative `+24.70%`

So the new selector is genuinely stronger in always-on form, but it loses under the frozen sticky overlay.

**Key finding:** stronger selector alpha is not automatically deployable selector alpha. The current live branch is still constrained by activation compatibility, not just selection quality.

**Implication:** do **not** replace the live sticky branch with the H199-based selector. Keep the live branch frozen and treat the H201 winner as offline-only evidence unless a future branch finds a clean, non-overfit way to make it activation-compatible.

## F148: The H203 Pairwise Extension Looks Good In Always-On Form But Fails The Next Sequential Gate; The Pair Branch Is Closed (2026-03-29, Session 69)

Session 69 extended the H199 family one step further:
- start from the H201 offline lead:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- test whether adding one companion atom helps:
  - always-on first via `H203`
  - then state-scoped via `H205`

### H203 result
Promoted pair:
- `full_library_pair__h199_sector_laggard_gap_absorb__h199_breakout_after_compression`
- validation relative `+65.60%`
- validation IR `1.14`
- confirmation relative `-14.86%`

This was strong enough to continue the ladder.

### H205 result
Best state-scoped pair variant:
- `state_pair_blend__h199_sector_laggard_gap_absorb__h199_breakout_after_compression__10`
- validation relative `+48.31%`
- delta vs the H201 winner `+2.14%`
- validation IR `0.89`
- delta vs the H201 winner `-0.01`
- confirmation relative `-19.39%`
- delta vs the H201 winner `-5.96%`

So the pair branch failed the locked promotion rule at the state-scoped stage.

**Key finding:** the H199 pairwise extension has real always-on selector information, but it is not strong enough in the next sequential state-scoped gate to dislodge the current offline lead.

**Implication:** close the H203/H205 pair family. Do not keep tuning pairwise H199 recombinations against the same validation / confirmation windows.

## F149: The Fresh H204 Tradability Families Show Standalone IC But No Selector Relevance; The Current Selector-Discovery Ladder Is Exhausted (2026-03-29, Session 69)

Session 69 then reopened the genuinely new-family search with:
- `h204_sector_accel_release`
- `h204_ceiling_memory_gap_absorb`
- `h204_breakout_sector_accel_buyable`
- `h204_sector_mom_laggard_volume`
- `h204_release_after_floor_pressure`

Several signals passed the dev standalone gate:
- `h204_sector_mom_laggard_volume`
  - dev IC `+0.0257`
  - validation IC `+0.0124`
  - confirmation IC `+0.0291`
- `h204_sector_accel_release`
  - dev IC `+0.0168`
  - validation IC `+0.0123`
  - confirmation IC `+0.0152`
- `h204_release_after_floor_pressure`
  - dev IC `+0.0304`
  - validation IC `+0.0036`
  - confirmation IC `+0.0224`

But none had selector relevance:
- `h204_sector_mom_laggard_volume`
  - validation selector return `-29.91%`
  - confirmation selector return `-35.41%`
- `h204_sector_accel_release`
  - validation selector return `-9.62%`
  - confirmation selector return `-28.37%`

**Key finding:** the fresh H204 families contain cross-sectional state-level signal, but not in a form that survives naive selector economics under the current protocol.

**Implication:** stop the current selector-discovery ladder here. The next honest selector-side branch must depend on a genuinely new data family or a different high-level hypothesis family, not more recombination of H199/H204 atoms.
