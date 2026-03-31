# Findings 151-180

## F151: Genuinely New Exit Families Still Do Not Beat The Existing H211 Strength-Exhaustion Winner; The Current Exit Branch Is More Clearly Closed On Existing Data (2026-03-29, Session 71)

Session 71 reopened exit research the right way:
- not by retuning `H207-H213`
- not by changing thresholds on the existing exhaustion winner
- but by testing genuinely different post-entry hypothesis families against the current H211 anchor

New families tested:
- `H214`: thesis inconsistency
- `H215`: failed follow-through
- `H216`: time under water

Current anchor coming in:
- `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
- validation relative `+54.45%`
- validation IR `1.17`
- confirmation relative `-4.70%`

### H214 — Thesis inconsistency
Best new variant:
- `thesis_inconsistency__score_drop_threshold_0p05__thesis_drop_threshold_0p1`
- validation relative `+28.44%`
- validation delta vs H211 `-26.01%`
- confirmation relative `-13.78%`

This was a clear fail.

### H215 — Failed follow-through
Best new variant:
- `failed_followthrough__current_return_threshold_0p0__grace_days_2__peak_return_threshold_0p03__score_drop_threshold_0p0`
- validation relative `+56.39%`
- validation delta vs H211 `+1.95%`
- validation IR delta `+0.0448`
- confirmation relative `-5.22%`
- confirmation delta vs H211 `-0.52%`

This was a real near-miss, but it still failed the locked promotion gate.

### H216 — Time under water
Best new variant:
- `time_under_water__grace_days_5__peak_return_threshold_0p03__underwater_days_threshold_3`
- validation relative `+55.30%`
- validation delta vs H211 `+0.85%`
- validation IR delta `+0.2334`
- confirmation relative `-39.36%`
- confirmation delta vs H211 `-34.66%`

This was a hard confirmation fail.

### H217 — Sticky compatibility
Skipped by rule:
- no genuinely new family displaced the H211 anchor
- so there was no new exit-family winner worth testing under the frozen sticky branch

**Key finding:** the current best exit-alpha evidence remains the original H211 strength-exhaustion family. The newer, genuinely different post-entry families do not beat it under the locked protocol.

**Implication:** close the current exit branch more firmly. Do not reopen it with more threshold tuning on the same data. The next honest exit branch now requires either:
- a genuinely new data family, or
- a materially different exit hypothesis family that is not a variant of H211/H214-H216.

## F152: The Continuation / Hold-vs-Exit Hazard Family Fails At The First Predictive Gate; Changing The Exit Target Alone Does Not Yet Create Useful Exit Alpha On Current Data (2026-03-29, Session 72)

Session 72 tested a genuinely different high-level hypothesis family:
- not a new sell rule
- not a new threshold stack
- but a new target:
  - “should this legally sellable held position be kept for one more cycle?”

The branch built continuation labels from the frozen `full_library` selector:
- forward `5`-day stock return minus forward `5`-day benchmark return
- label = `1` when that hold advantage is positive

Three dev-trained continuation models were tested:
- `continuation_core`
- `continuation_plus_thesis`
- `continuation_plus_rank`

Best result:
- `continuation_core`
- validation AUC `0.5060`
- validation top-quintile hold advantage `-0.0058`
- confirmation AUC `0.5106`
- confirmation top-quintile hold advantage `-0.0081`

Other models were not better:
- `continuation_plus_rank`
  - validation AUC `0.5031`
  - confirmation AUC `0.5230`
  - top-quintile hold advantage still negative
- `continuation_plus_thesis`
  - validation AUC `0.4996`
  - confirmation AUC `0.5225`
  - top-quintile hold advantage still negative

Because `H218` failed, the next two rungs were skipped:
- `H219`: continuation exit bands
- `H220`: sticky compatibility

**Key finding:** a materially different exit target is not enough by itself. On current daily data, the hold-vs-exit continuation family does not contain useful predictive edge.

**Implication:** close `H218-H220` and do not retune it on the same locked window. The next honest exit branch must now depend on a genuinely new data family, not just a new formulation over the same daily inputs.

## F153: The Corporate-Event Surface Has Real Local Coverage But Does Not Create Useful Continuation / Exit Signal Under The Locked Protocol; The Event Branch Dies Before Deterministic Integration (2026-03-29, Session 73)

Session 73 opened the first genuinely new-data exit branch the right way:
- `H221`: build a reusable corporate-event surface
- `H222`: test it on the continuation / hold-vs-exit target
- only if that passed, continue to deterministic exit integration

### H221 — Coverage is real
The new event surface was built successfully at:
- `data/features/event_surface_daily.parquet`

Coverage summary:
- `394` tickers
- `845,646` `(time, ticker)` rows
- held-position coverage `89.59%`
- event-source history coverage:
  - dividend-event tickers `51`
  - issuance-event tickers `52`
  - insider-event tickers `387`

This means the event branch did **not** fail for trivial data sparsity reasons.

### H222 — Predictive screening fails anyway
Best model:
- `event_only_core`
- validation AUC `0.5180`
- validation top-quintile hold advantage `-0.0030`
- confirmation AUC `0.4862`
- confirmation top-quintile hold advantage `-0.0108`

Other variants were not better:
- `event_plus_path_core`
- `event_plus_path_thesis`

So the branch died at the predictive screen:
- `H223`: skipped
- `H224`: skipped

**Key finding:** adding corporate-event timing to the current daily held-position state does not create useful continuation / exit alpha on the locked `2015-2025` protocol.

**Implication:** do not keep tuning the event branch locally. The event surface is now a valid published artifact, but the exit-side event family is closed on current data.

## F154: Exit-Side New-Data Research Is Now Blocked Locally By Information Availability, Not By More Rule Ideas (2026-03-29, Session 73)

After the event branch failed at `H222`, Session 73 carried the ladder forward honestly instead of quietly stopping.

### H225 — Intraday / auction structure fails on local coverage
Local intraday state:
- only `data/stock/gia_lich_su_FPT_1H.parquet` exists
- held-position coverage against the continuation panel is `0.00%`

So:
- `H225`: fail
- `H226-H228`: skipped by rule

### H229 — Order-book / queue feasibility fails locally
Local feasibility audit result:
- no historical queue/depth archive exists under local `data/`
- only a schema probe exists in:
  - `analysis/probe_vnstock2_output.txt`

So:
- local order-book / queue research is **not feasible now**

**Key finding:** the exit branch is now blocked by missing information, not by a lack of more threshold ideas. On the current local workspace, the honest exit-side branch is closed.

**Implication:** do not continue exit tuning on the current local data stack. The next honest exit-side move requires actual new data acquisition:
- richer company-event timestamps
- multi-ticker intraday / auction data
- historical order-book / queue archives

## F155: Once Timing Research Is Closed On The Current Local Data Stack, The Next Active Branch Must Be Data Acquisition First, Not More Timing Rule Tuning (2026-03-29, Session 74)

Session 74 did not open another model family.

It codified the operational consequence of Sessions 70-73:
- the live sticky branch stays frozen
- timing research on the current local daily stack is exhausted
- the next honest work is acquisition-first, not more rule invention

Active acquisition order is now:
1. multi-ticker intraday / auction data
2. richer company-event source than the current event surface v1
3. otherwise stop timing research and wait for either real data access or more forward live evidence

This is now documented explicitly in:
- `notes/timing_data_acquisition_plan.md`
- `notes/timing_data_source_scorecard.csv`

**Key finding:** when the lab reaches the information limit of the current stack, the next branch should be operational data acquisition with explicit viability gates, not another loop of offline timing experiments.

## F156: A Usable Timing-Data Source Must Clear Coverage, Timestamp, And Continuity Gates Before It Is Allowed To Reopen Modeling (2026-03-29, Session 74)

Session 74 also made the acquisition branch concrete instead of leaving it as a loose idea.

For intraday / auction data to count as usable, it must satisfy:
- historical access, not live-only
- multi-ticker coverage
- enough held-row coverage to matter
- stable timestamps and session structure
- enough fields to derive first-hour and close-auction features

For a richer company-event source to count as usable, it must satisfy:
- first-public timestamps are recoverable
- event timing is company-specific, not just quarter-phase
- coverage materially improves over event surface v1
- the source is not leak-prone or retrospectively backfilled

**Key finding:** new data access is not enough by itself. A new source only reopens timing research after it clears explicit viability gates first.

## F157: The Entry-Alpha Branch Looks More Like A Small-Book `Top1` Contract Than A `Top5` Timing Overlay, But No Audited Contract Survives The Honest Forward Gate (2026-03-30, Session 76)

Session 76 ran `H245`, the first honest contract audit after the Session 75 entry-alpha ladder.

The question was not:
- "can another `top5` threshold be tuned?"

It was:
- "does this branch actually want a smaller book, such as `top1` or `top2`?"

### Audited contract winners

#### `top_k = 1`
Winner:
- `topk1__topm5__score_0p6__gap_none`

Metrics:
- validation relative `+67.91%`
- confirmation (`2025`) relative `+48.14%`
- forward (`2026+`) relative `-15.20%`

Matched fixed-`top1` baseline:
- validation relative `-73.98%`
- confirmation relative `-29.34%`
- forward relative `-14.56%`

Interpretation:
- historically this is the strongest audited contract by far
- but the forward result is still bad, and the forward IR deterioration breaks the honest gate

#### `top_k = 2`
Winner:
- `topk2__topm5__score_0p65__gap_0p03`

Metrics:
- validation relative `+20.27%`
- confirmation relative `-14.60%`
- forward relative `-3.30%`

This did not beat its own fixed-`top2` baseline cleanly enough.

#### `top_k = 3`
Winner:
- `topk3__topm5__score_0p7__gap_0p03`

Metrics:
- validation relative `+2.21%`
- confirmation relative `-4.79%`
- forward relative `+11.44%`

This had the best forward result, but validation was too weak for it to be the right historical contract.

#### `top_k = 5`
Winner:
- `topk5__topm5__score_0p65__gap_0p03`

Metrics:
- validation relative `+28.04%`
- confirmation relative `-22.13%`
- forward relative `-2.75%`

This reproduces the Session 75 `H244` result.

### Contract-level conclusion

Against the audited `top5` winner, the audited `top1` winner improved:
- validation by `+39.87%`
- confirmation by `+70.27%`

But it was worse in `2026+` by:
- `-12.44%`

So the branch thesis is now sharper:
- the entry-alpha family behaves more like a **small-book historical contract** than a `top5` timing overlay
- but no audited `top_k` contract is honestly promotable

**Key finding:** `H245` strengthens the offline architectural conclusion without changing live policy. The right offline interpretation is "small-book structure is real," not "entry alpha is ready."

**Implication:** if the branch is intentionally reopened, the next honest continuation should be a small-book follow-through such as `H246`, not another generic `top5` timing sweep.

## F158: Local Confirmation / Calibration Overlays Do Not Rescue The Small-Book Entry-Alpha Branch On The Current Label Contract (2026-03-30, Session 77)

Session 77 ran `H246`, the first honest follow-through after `H245`.

The question was:
- can a **light** confirmation / calibration overlay improve the small-book contract?

The branch stayed disciplined:
- no new full model family
- no return to generic `top5` timing sweeps
- only `top1` / `top2`
- only local confirmation-style overlays

Overlays tested:
- `soft_consensus_threshold`
- `soft_reversal_threshold`
- `soft_gap_absorb_threshold`
- `soft_uncrowded_threshold`
- `near_cutoff_no_confirm_veto`
- `soft_consensus_plus_veto`

### Top1 result
Base contract from `H245`:
- `topk1__topm5__score_0p6__gap_none`

Best overlay by validation:
- `topk1__near_cutoff_no_confirm_veto`

But all top1 overlays produced exactly the same result as the base sparse contract:
- validation relative `+67.91%`
- confirmation relative `+48.14%`
- forward relative `-15.20%`
- all deltas vs base = `0.00%`

This means the local confirmation overlays were effectively a **no-op** for the `top1` contract.

### Top2 result
Base contract from `H245`:
- `topk2__topm5__score_0p65__gap_0p03`

Validation winner:
- `topk2__soft_consensus_threshold`

Metrics:
- validation relative `+135.26%`
- validation delta vs base `+114.99%`
- confirmation relative `-42.25%`
- confirmation delta vs base `-27.65%`
- forward relative `-25.14%`
- forward delta vs base `-21.84%`

This is a clean validation overfit.

Lighter veto-style overlays were less bad:
- `near_cutoff_no_confirm_veto`
- `soft_consensus_plus_veto`

Metrics:
- validation around `+30%`
- confirmation around `-34%`
- forward around `+2.50%`

These showed small forward improvements over the base sparse `top2` contract, but they still degraded confirmation too much and did not clear the honest gate.

**Key finding:** local confirmation / calibration overlays are not the missing ingredient on the current small-book entry-alpha label contract. For `top1`, they do nothing. For `top2`, the strongest overlay overfits validation badly.

**Implication:** close the local-overlay sub-branch. If the entry-alpha branch is intentionally reopened, the next honest continuation should be `H247`: keep it small-book, but stop testing more local overlays on the same target and instead sharpen the label / target for the compact-model branch.

## F159: Sharpening The Small-Book Entry Label Does Not Rescue The Parked Entry-Alpha Branch; The Only Surviving Improvement Is An Unsharpened `top2` Compact Model Side Result (2026-03-31, Session 78)

Session 78 ran `H247`, the first label-sharpen follow-through after `H246`.

The branch stayed disciplined:
- no live-branch change
- no new broad model family
- no `2026+` lockbox read
- only `top1/top2`
- only compact-model variants against sharper `buy_now_label` definitions

Audited label buffers:
- `0.00`
- `0.01`
- `0.02`
- `0.03`

The key branch question was:
- does sharpening the small-book target fix the compact-model branch?

### What failed

No sharpened candidate (`label_edge_buffer > 0`) cleared the validation-plus-`2025` gate.

Best sharpened `top2` candidate:
- `topk2__blend__label_0p03__threshold_0p55`

Metrics vs the carried `H245` `top2` anchor:
- validation AUC `0.549`
- confirmation AUC `0.574`
- validation delta `+85.80%`
- confirmation delta `-33.94%`

This is still a validation-heavy overfit, not a rescue.

Best sharpened `top1` candidate:
- `topk1__blend__label_0p03__threshold_0p55`

Metrics vs the carried `H245` `top1` anchor:
- validation delta `+38.16%`
- confirmation delta `-96.68%`

So the specific `H247` thesis is rejected:
- the current branch is **not** fixed by simply making the label stricter

### What survived as offline evidence

The best overall `top2` candidate in the run was **not** sharpened:
- `topk2__price_state__label_0__threshold_0p55`

Metrics vs the `H245` `top2` anchor:
- validation relative `+93.79%`
- validation delta `+73.52%`
- confirmation relative `-12.12%`
- confirmation delta `+2.47%`

This matters, but only narrowly:
- it says the current compact-model branch may have a real `top2` contract on the existing label
- it does **not** count as support for the sharpened-label path
- because Session 78 intentionally did not read `2026+`, it also does **not** become an honest promoted winner

**Key finding:** the current small-book entry-alpha branch is not rescued by label sharpening. The only meaningful survivor from `H247` is a narrower side result: the unsharpened `top2` `price_state` compact model is stronger than the carried `H245` anchor on `2019-2025`.

**Implication:** close the current label-sharpening path on the existing data stack. Do **not** advance to `H248` from `H247` alone. If this architecture is intentionally reopened later, the only honest leftover is a future `2026+` lockbox check on the unsharpened `top2` compact-model side result.

## F160: Sparse Catalyst Gating Does Not Rescue The Current Small-Book Entry-Alpha Branch; Family A Closes On The Existing Data Stack (2026-03-31, Session 79)

Session 79 ran `H248`, the queued catalyst-concentrated follow-through after `H247`.

The branch stayed disciplined:
- no live-branch change
- no new model family
- no `2026+` lockbox read
- only carried small-book contracts
- only date-level gates built from sparse catalyst families

Carried contracts:
- `H245` `top1` anchor
- `H245` `top2` anchor
- the `H247` unsharpened `top2` `price_state` side result

Catalyst families used:
- rolling news presence
- insider relative-size support
- event / filing support from the published event surface

Tested gate family:
- `highconv_ge1`
- `highconv_ge2`
- `multisource_ge1`
- `news_or_insider_ge1`

### What failed

Best `top1` result:
- `h245_top1_anchor__highconv_ge1`

Metrics vs its always-on anchor:
- validation delta `+332.33%`
- confirmation delta `-81.90%`

This is a clean validation overfit.

Best `top2` anchor result:
- `h245_top2_anchor__highconv_ge2`

Metrics vs its always-on anchor:
- validation delta `+38.82%`
- confirmation delta `-16.22%`

This is closer, but it still fails the offline gate.

For the `H247` `top2` `price_state` side result, every tested gate made the contract worse.

### Branch consequence

So the catalyst thesis is rejected on the current stack:
- sparse catalyst concentration does **not** rescue the carried small-book contracts
- the current `H247` side result does **not** want these date-level gates

**Key finding:** Family A now fails both ways on current data:
- sharpening the small-book label fails (`H247`)
- catalyst-concentrated date gating fails (`H248`)

**Implication:** close `H247-H248` on the existing local data stack. Do **not** keep tuning small-book catalyst gates locally. If the model-side queue is intentionally continued later, move to the next materially different family (`H249`) rather than adding more `H247/H248` variants.

## F161: Selector-Relative `rel2` Does Not Rescue The `H201` Offline Winner; The H199 Selector Lead Remains Offline-Only Evidence (2026-03-31, Session 80)

Session 80 ran `H249`, the queued selector-relative activation follow-through for the `H201` winner:
- `state_blend__h199_sector_laggard_gap_absorb__30`

The branch stayed disciplined:
- no live-branch change
- no new selector family
- no `2026+` lockbox read
- same sticky displacement rule as `H202`
- only the activation gate source changed

Compared variants:
- `winner_always_on`
- `winner_plus_full_rel2_sticky`
  - control rerun of the frozen `H202` logic
- `winner_plus_selector_rel2_sticky`
  - gate rebuilt from the winner's own prior-cycle relative returns
- incumbent:
  - `full_library_plus_sticky`

### What failed

Incumbent sticky branch:
- validation relative `+29.65%`
- validation IR `0.61`
- confirmation relative `+18.80%`

Control rerun:
- `winner_plus_full_rel2_sticky`
- validation relative `+16.64%`
- validation delta vs incumbent `-13.01%`
- confirmation relative `+24.70%`
- confirmation delta vs incumbent `+5.90%`

This confirms the original `H202` failure mode still reproduces cleanly.

Selector-relative candidate:
- `winner_plus_selector_rel2_sticky`
- overall gate share `53.82%`
- validation gate share `55.51%`
- confirmation gate share `42.57%`
- gate agreement vs incumbent `72.63%`
- validation relative `+16.18%`
- validation delta vs incumbent `-13.47%`
- validation IR delta `-0.21`
- confirmation relative `-19.10%`
- confirmation delta vs incumbent `-37.90%`

So the selector-relative gate is not just “basically the same rule,” but it still does **not** help:
- validation remains well below the incumbent sticky branch
- confirmation becomes materially worse than both the incumbent and the `H202` control

### Branch consequence

**Key finding:** the `H201` winner is not blocked merely by using `full_library` as the `rel2` calibration source. Rebuilding `rel2 > 0` on the selector's own return history does not rescue activation compatibility.

**Implication:** keep `state_blend__h199_sector_laggard_gap_absorb__30` as selector-only offline evidence. Do **not** keep tuning local `rel_span` / `rel_threshold` variants of this same gate on the current locked windows. If model-side queue work is intentionally continued later, move to the next materially different family (`H250`).
