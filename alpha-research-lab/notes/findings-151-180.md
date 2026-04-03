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

## F162: H250 Finds One Real Contradiction-State Router, But It Does Not Dislodge `H201` As The Current Offline Lead (2026-03-31, Session 81)

Session 81 ran `H250`, the queued contradiction-state router branch built from disagreement states between:
- continuation family:
  - `S1`
  - `C12`
  - `C14`
  - `H199`
- reversal / veto family:
  - `C9`
  - `C13`

The branch stayed disciplined:
- no live-branch change
- no `2026+` lockbox read
- one sparse router family only
- at most one promoted winner carried into direct selector audit

### What passed

Promoted router:
- `h250_disagreement_balance`
- active share `13.35%`
- dev IC `+0.0184`
- corr with `S1` `+0.0905`
- validation IC `+0.0159`
- confirmation IC `+0.0184`
- validation selector relevance `+33.27%`

So the contradiction-state idea is not empty:
- there is a real sparse router state in the current data stack
- it is not just another highly correlated restatement of `S1`

Direct audit against the selector backbone:
- `full_library_plus__h250_disagreement_balance`
- validation relative `+78.16%`
- validation delta vs baseline `+34.71%`
- validation IR delta vs baseline `+0.53`
- confirmation relative `-20.80%`
- confirmation delta vs baseline `-0.78%`

That is strong enough to clear the baseline additive gate.

### What failed

Direct comparison vs the current `H201` offline lead:
- `state_blend__h199_sector_laggard_gap_absorb__30`
- `H250` validation delta vs `H201`: `+31.99%`
- `H250` confirmation delta vs `H201`: `-7.36%`

So the new router improves validation dramatically, but it still gives back too much on confirmation.

### Branch consequence

**Key finding:** contradiction-state routing is a real selector family on the current stack, but the best current router does not yet beat `H201` where it matters most. `h250_disagreement_balance` is stronger than the baseline and worth keeping, but it is not the new offline leader.

**Implication:** keep `h250_disagreement_balance` as offline-only / RL-state evidence. Keep `state_blend__h199_sector_laggard_gap_absorb__30` as the current offline lead selector. If the model-side queue is intentionally continued later, move to the next materially different family (`H251`) rather than tuning more local `H250` variants immediately.

## F163: H251 Reopens Event Surface v1 As A Narrow Trust Modulator For `H201`, Not As A New Standalone Predictor (2026-03-31, Session 82)

Session 82 ran `H251`, the queued event-surface reuse test. The question was deliberately narrow:
- do **not** reopen the event surface as exit alpha
- do **not** touch the live branch
- do **not** read `2026+`
- test only whether the already-published event surface can tell us when to trust the strongest current offline selector

Carried selector backbones:
- `full_library_baseline`
- `state_blend__h199_sector_laggard_gap_absorb__30`
- `full_library_plus__h250_disagreement_balance`

Pre-specified event regimes screened:
- `top5_any_event_ge1`
- `top5_recent_filing_ge1`
- `top5_report_window_ge2`

### What passed

Only the `H201` winner showed clean, repeated benefit from the event surface as trust context.

Best candidate:
- `state_blend__h199_sector_laggard_gap_absorb__30 + top5_report_window_ge2`
- overall gate share `49.21%`
- validation IC delta `+0.0104`
- confirmation IC delta `+0.0134`
- validation top-5 edge delta `+0.0174`
- confirmation top-5 edge delta `+0.0146`

Second promoted regime:
- `state_blend__h199_sector_laggard_gap_absorb__30 + top5_recent_filing_ge1`
- overall gate share `58.99%`
- validation IC delta `+0.0038`
- confirmation IC delta `+0.0198`
- validation top-5 edge delta `+0.0016`
- confirmation top-5 edge delta `+0.0043`

That result is important because it says the published event surface is not dead everywhere:
- it failed as an exit / continuation predictive family
- but it still contains useful context about when the current offline selector is more trustworthy

### What did not generalize

The same regimes did **not** behave like a general-purpose selector upgrade.

Mixed only:
- `full_library_baseline + top5_report_window_ge2`
  - edge improves in validation and confirmation
  - IC deteriorates in both windows
- `full_library_plus__h250_disagreement_balance + top5_report_window_ge2`
  - edge improves in validation and confirmation
  - IC deteriorates in both windows
- `full_library_plus__h250_disagreement_balance + top5_recent_filing_ge1`
  - confirmation improves
  - validation edge turns negative

So the branch should stay narrow:
- this is not evidence that event surface v1 rescues every selector
- this is not evidence that `H250` becomes the new leader under event conditioning
- this is not a reason to reopen the old exit-side event search

### Branch consequence

**Key finding:** event surface v1 is still closed as an exit predictor on the current local stack, but it passes as a narrow trust modulator for the current `H201` offline selector. The cleanest reusable regime is `top5_report_window_ge2`, with `top5_recent_filing_ge1` as a weaker secondary carry.

**Implication:** keep `state_blend__h199_sector_laggard_gap_absorb__30` as the current offline lead. Reopen the event branch only as a light offline trust-audit (`H252`) on `H201`, not as a broader event-family search and not as a live-branch change.

## F164: H252 Confirms The Event Reuse Edge Only As A Hard Report-Window Gate Around `H201`, Not As A Soft Trust Dial (2026-03-31, Session 83)

Session 83 ran `H252`, the follow-through that `H251` explicitly asked for.

The contract stayed narrow:
- same `H201` selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- same locked years:
  - dev `2015-2022`
  - validation `2023-2024`
  - confirmation `2025`
- no `2026+` read
- no reopening of the old exit-side event family
- only one primary regime and one secondary carry:
  - `top5_report_window_ge2`
  - `top5_recent_filing_ge1`

### What passed

The promoted winner is not a soft schedule. It is a real hard gate:
- `winner_report_window_gate`
- regime:
  - `top5_report_window_ge2`
- overall gate share `49.34%`
- validation relative `+59.57%`
- validation delta vs `H201` always-on `+13.40%`
- validation IR delta `+0.33`
- confirmation relative `-10.98%`
- confirmation delta vs `H201` always-on `+2.45%`
- confirmation IR delta `+0.10`

That is enough to count as a real offline improvement over always-on `H201`.

### What did not survive

The softer variants do not carry the branch.

Mixed only:
- `winner_report_window_half_off`
- validation relative delta `-7.13%`
- validation IR delta `-0.01`
- confirmation relative delta `+0.26%`
- confirmation IR delta `-0.09`

Failed cleanly:
- `winner_recent_filing_half_off`
- validation relative delta `-25.97%`
- validation IR delta `-0.39`
- confirmation relative delta `-12.43%`

So the lesson is precise:
- the report-window signal is real enough to matter
- but only as a stronger exposure decision
- the current data does **not** support the broader idea that event surface v1 is a generic soft trust dial around `H201`

### Branch consequence

**Key finding:** the current-data event reuse branch survives only as `H201 + top5_report_window_ge2` with a hard on/off exposure gate. The weaker partial-exposure version is not the winner, and the recent-filing carry is not promotable.

**Implication:** keep `winner_report_window_gate` as offline evidence only. Do not broaden the event family again. If the model-side queue is intentionally continued later, the next honest question is `H253`: whether this hard-gated offline winner survives a frozen compatibility audit against the incumbent sticky branch.

## F165: H253 Shows The Hard Report-Window Gate Is Real Offline Evidence But Not A Frozen-Compatibility Winner (2026-03-31, Session 84)

Session 84 ran `H253`, the direct follow-through that `H252` asked for.

The contract stayed narrow:
- same carried selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- same carried regime:
  - `top5_report_window_ge2`
- same locked years:
  - dev `2015-2022`
  - validation `2023-2024`
  - confirmation `2025`
- no `2026+` read
- no broader event-family reopen
- direct comparison only against the frozen sticky incumbent

### What survived

The `H252` winner stays informative, but it is not promotable against the real benchmark:
- `winner_report_window_gate`
- validation relative `+59.57%`
- validation delta vs incumbent sticky `+29.91%`
- validation IR delta `+0.62`
- confirmation relative `-10.98%`
- confirmation delta vs incumbent sticky `-29.78%`
- confirmation IR delta `-1.17`

That means the report-window gate is still capturing something real.
It improves `H201` materially on validation.
But it does **not** survive the only comparison that matters for live-adjacent credibility: the frozen sticky incumbent still wins confirmation by a large margin.

The comparison against always-on `H201` sharpens the conclusion:
- always-on `H201` was also worse than incumbent sticky in confirmation
- so the gate helps `H201` locally
- but not enough to turn the branch into a compatibility winner

### Branch consequence

**Key finding:** event-conditioned `H201` is a regime-specific offline clue, not a deployable frozen-compatibility winner on the current stack. The hard report-window gate improves `H201` relative to its own always-on version, but frozen sticky remains the stronger live-adjacent benchmark.

**Implication:** keep `winner_report_window_gate` as offline regime evidence only, keep the live branch unchanged, and do not broaden the event branch again. If the model-side queue is intentionally continued later, the next honest follow-through is `H254`: a hybrid switchboard audit that keeps incumbent sticky off-regime and uses the `H252` hard-gated `H201` path only on-regime.

## F166: H254 Closes The Report-Window Selector Switchboard Branch On The Current Stack (2026-03-31, Session 85)

Session 85 ran `H254`, the direct hybrid follow-through that `F165` asked for.

The contract stayed exact and narrow:
- same carried selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- same carried regime:
  - `top5_report_window_ge2`
- same locked years:
  - dev `2015-2022`
  - validation `2023-2024`
  - confirmation `2025`
- no `2026+` read
- no new event-family or contradiction-family search
- off-regime behavior kept the incumbent sticky branch intact
- on-regime behavior used the hard-gated `H201` leg only

### What failed

The hybrid switchboard does not survive the incumbent benchmark:
- `switchboard_h201_on_regime`
- validation relative `+23.51%`
- validation delta vs incumbent sticky `-6.14%`
- validation IR delta `-0.08`
- confirmation relative `+5.72%`
- confirmation delta vs incumbent sticky `-13.08%`
- confirmation IR delta `-0.43`

That is the key result.
The switchboard helps the bad confirmation behavior of the naked `H201` paths.
But it still loses to the frozen sticky incumbent in both phases that matter.

The comparison also clarifies where the branch dies:
- `winner_report_window_gate` had stronger validation but catastrophic confirmation
- the switchboard softens that confirmation damage
- yet the validation giveback is large enough that the hybrid still fails cleanly overall

So the lab now has a precise negative result:
- `H201` may carry regime-specific information
- but current-data report-window specialization is not enough to justify selector switching around the frozen sticky incumbent

### Branch consequence

**Key finding:** the current stack does not support a report-window selector switchboard around `H201`. The hybrid is better than the naked `H201` confirmation paths, but still materially worse than frozen sticky in both validation and confirmation.

**Implication:** close the current-data switchboard branch, keep `H252/H253` as offline regime evidence only, keep the live branch unchanged, and if the model-side queue is intentionally continued later move to `H255`: the report-window contradiction expert.

## F167: H255 Shows The Contradiction Overlay Helps Confirmation A Bit Inside The Report-Window Gate, But Validation Collapses Too Hard To Promote (2026-03-31, Session 86)

Session 86 ran `H255`, the narrow nested-regime follow-through after the switchboard failure.

The contract stayed disciplined:
- same carried selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- same carried `H250` router:
  - `h250_disagreement_balance`
- same carried `H252` regime:
  - `top5_report_window_ge2`
- same locked years:
  - dev `2015-2022`
  - validation `2023-2024`
  - confirmation `2025`
- no `2026+` read
- no broader event-family reopen
- no switchboard revisit

### What happened

The nested contradiction overlay is not dead noise, but it is not a winner either:
- `winner_plus_router_report_window_gate`
- validation relative `+5.65%`
- validation delta vs `H252` baseline `-53.92%`
- validation IR delta vs `H252` baseline `-1.04`
- confirmation relative `-8.20%`
- confirmation delta vs `H252` baseline `+2.78%`
- confirmation IR delta vs `H252` baseline `+0.04`

That means the overlay does exactly one useful thing:
- it softens confirmation a bit inside the gated regime

But the cost is too large:
- the validation collapse is overwhelming
- so the branch does **not** satisfy the honest nested-regime gate

This matters because it clarifies the earlier synthesis story:
- `H250` is a real family globally
- `H252` is a real regime gate
- but simply nesting the promoted contradiction router inside the promoted report-window regime does not combine into a stronger selector branch on the current stack

### Branch consequence

**Key finding:** report-window contradiction routing is only a weak near-miss on the current stack. It modestly improves confirmation versus the `H252` hard-gated baseline, but validation degrades far too much for promotion.

**Implication:** keep `H255` as synthesis-only offline evidence, do not reopen the failed switchboard from it, keep the live branch unchanged, and if the model-side queue is intentionally continued later move to `H256`: the event-driven dynamic breadth audit.

## F168: H256 Closes The Current Daily-Data Synthesis Queue; Report-Window Dynamic Breadth Improves Validation But Breaks Confirmation (2026-03-31, Session 87)

Session 87 ran `H256`, the last remaining synthesis follow-through on the current daily-data stack.

The contract stayed exact:
- same carried selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- same carried regime:
  - `top5_report_window_ge2`
- same locked years:
  - dev `2015-2022`
  - validation `2023-2024`
  - confirmation `2025`
- no `2026+` read
- no switchboard reopen
- no entry-label reopen
- breadth audit only:
  - `K in {1,2,5}`

### What happened

The small-book intuition is real on validation:
- `K=1`
  - validation relative `+74.44%`
  - validation delta vs gated `K=5` baseline `+14.87%`
- `K=2`
  - validation relative `+69.33%`
  - validation delta vs gated `K=5` baseline `+9.76%`

But both candidates fail violently on confirmation:
- `K=1`
  - confirmation relative `-50.07%`
  - confirmation delta vs gated `K=5` baseline `-39.08%`
- `K=2`
  - confirmation relative `-42.63%`
  - confirmation delta vs gated `K=5` baseline `-31.65%`

So the branch says something useful but not deployable:
- the report-window dates do look like concentrated opportunity states in validation
- but the current stack cannot turn that into a robust smaller-breadth contract

This closes the interpretation loop on the recent synthesis queue:
- report-window gating is real
- contradiction routing is locally real
- smaller breadth is locally real
- but none of the recombinations survive the locked confirmation test well enough to become the next branch winner

### Branch consequence

**Key finding:** the current daily-data synthesis queue is exhausted. Event-driven dynamic breadth improves validation inside the report-window regime, but the confirmation damage is too large, so no smaller-breadth candidate is promotable.

**Implication:** keep `H256` as synthesis-only offline evidence, close the current local model-side synthesis queue on this branch family, keep the live branch unchanged, and shift non-live effort back to acquisition-first timing-data work or forward live monitoring rather than further recombination on the same stack.

## F169: H231 Shows The Partial CafeF Intraday Surface Normalizes Cleanly, But Full-Session Completeness Is Not Yet Honest Enough To Publish As A Universal Artifact (2026-03-31, Session 88)

Session 88 ran `H231`, the first acquisition-side pass on the current multi-ticker CafeF fetch, and kept it deliberately narrow:
- analysis window:
  - `2023-2025`
- no `2026+` read
- no timing-alpha claim
- no attempt to publish `data/features/intraday_structure_daily.parquet`
- only:
  - representative normalization
  - first-pass feature extraction
  - a provisional `H232` lower-bound coverage / continuity estimate

### What happened

The normalization part is real:
- all `20` representative pilot tickers normalized cleanly onto the VCI daily backbone
- first-hour feature share on the pilot:
  - `1.00`
- close-hour feature share on the pilot:
  - `1.00`
- current partial fetch already overlaps meaningfully with the continuation panel:
  - `207` raw tickers
  - held-row coverage lower bound `46.57%`
  - missing-session rate in-window `6.61%`

But the broader full-session artifact claim does **not** survive the same pass:
- pilot complete-day share:
  - `72.32%`
- current all-available complete-day share among present sessions:
  - `72.11%`
- held-row complete-day lower bound:
  - `31.71%`

The failure is highly structured, not random:
- liquid banks:
  - about `97%` complete-day share
- liquid fill names:
  - about `97%`
- liquid industrials:
  - about `86%`
- small illiquid tail:
  - about `1%`
  - median bars per day only `1.25`

That means the source has cleared one important bar and failed another:
- cleared:
  - the VCI bridge works
  - open / first-hour / close-hour structure can be extracted honestly on a representative subset
- failed:
  - the current partial surface does **not** justify a universal five-bar intraday artifact for the full long-only universe

### Branch consequence

**Key finding:** the partial CafeF intraday source is viable enough to keep the intraday acquisition branch open, but only as a reduced-shape / provisional surface right now. It is not honest yet to publish a universal full-session intraday artifact or to use this pass as a timing-alpha verdict.

**Implication:** keep `H231` as a mixed acquisition result, keep `H232` explicitly provisional while the fetch remains partial, keep the live branch unchanged, and if intraday work continues before fetch completion focus on open-gap / first-hour / close-hour structure rather than a universal five-bar session representation. `H234` remains the valid parallel fallback branch.

## F170: H234 Passes The Richer Event-Source Audit; The Local CafeF Company-News Archive Is A Real Company-Event Candidate, But The Conservative Seed Is Still Too Sparse To Skip H235 (2026-03-31, Session 89)

Session 89 ran `H234`, the richer company-event source audit, and kept it deliberately conservative:
- source audited:
  - local CafeF company-news archive
- extraction rule:
  - title-ticker seed only
  - exact `published_at` timestamps only
- analysis window:
  - `2023-2025`
- no predictive screen
- no `2026+` read

### What happened

The source passes as a richer company-event candidate than event surface v1.

At the source-identification level, the result is strong:
- total articles scanned:
  - `312,488`
- title-ticker company articles:
  - `1,257`
- timestamp coverage on those title-ticker articles:
  - `100%`
- family-qualified company-event articles:
  - `1,072`
- candidate ticker coverage:
  - `190`

The recovered company-specific families are exactly the kinds of information v1 is missing broadly:
- `earnings_company`
  - `176` tickers
- `board_management`
  - `120` tickers
- `shareholder_meeting`
  - `107` tickers
- `rights_issuance`
  - `97` tickers

So `H234` resolves the acquisition question cleanly:
- yes, a richer, timestamped company-event source is already locally available
- yes, it clears the meaningful-subset bar
- yes, it adds company-specific event timing that the current event surface does not broadly contain

But the same audit also exposes the next bottleneck:
- the conservative title-ticker seed is sparse on held rows
- recent-any company-event coverage on the held-position panel is only:
  - `1d` `0.22%`
  - `5d` `0.75%`
  - `20d` `1.15%`

That does **not** fail `H234`, because source identification and operational coverage are different questions.
It does tell the lab exactly what `H235` must do:
- test whether a richer extraction pass can improve usable coverage or information content
- preserve first-public timestamps
- avoid leakage while expanding beyond the conservative seed

### Branch consequence

**Key finding:** the local CafeF company-news archive is a real richer event-source candidate. It should replace source hunting as the active event-data question.

**Implication:** mark `H234` as passed, keep the live branch unchanged, and move directly to `H235`: a sample audit of the news-derived event surface. Do not jump straight to event surface v2, and do not confuse source availability with predictive validation.

## F171: H235 Is Mixed; Strict Title-Alias Expansion Is High-Precision And Highly Novel Versus Event Surface v1, But Operational Coverage Is Still Far Too Thin To Open H236 (2026-03-31, Session 90)

Session 90 ran `H235`, the event-source sample audit and coverage gate, on top of the passed `H234` source.

The branch question was no longer whether the CafeF company-news archive is real.
`H234` had already answered that.
The real question in `H235` was:
- can the source be expanded beyond the conservative title-ticker seed without leaking?
- does that expansion improve information content or usable coverage enough to justify event-surface publication work?

### What happened

The strict title-alias audit came back much cleaner than the conservative expectation on linkage quality.

Using a train-only alias lexicon learned from `2023-2024` title-ticker event articles:
- learned alias rows:
  - `105`
- learned tickers:
  - `57`

On the masked `2025` title-ticker holdout:
- holdout rows:
  - `194`
- assigned rows:
  - `85`
- assigned share:
  - `43.81%`
- assigned precision:
  - `98.82%`

That is a real result.
It means the richer source is not failing because title expansion is hopelessly noisy.

The expansion also added a lot of company-specific article inventory:
- seed unique qualified articles:
  - `1,072`
- added alias-linked unique articles:
  - `2,861`
- expanded candidate daily rows:
  - `3,429`

And most of those expanded daily rows are genuinely new relative to the current company-specific proxy surface in `event_surface_daily.parquet`:
- novel rows versus v1:
  - `2,554`
- novel share versus v1:
  - `74.48%`

So the source still matters.
It is not merely re-encoding what v1 already has.

But the operational gate still fails clearly.

Held-row recent-any company-event coverage improves, but only from a very small base:
- seed `5d` coverage:
  - `0.75%`
- expanded `5d` coverage:
  - `2.30%`
- delta:
  - `+1.55` percentage points

At `20d`, the source is still sparse:
- seed `20d` coverage:
  - `1.15%`
- expanded `20d` coverage:
  - `3.54%`

Those numbers are directionally better but nowhere near the `H235` operational bar.

### Branch consequence

**Key finding:** the richer event source is real, and strict title-alias expansion can recover a lot of novel company-specific information without obvious leakage, but the source is still too sparse operationally to justify `event_surface_v2` publication on the current archive / mapping contract.

**Implication:** mark `H235` as mixed, keep `H236` closed, preserve `H234-H235` as acquisition evidence, and route active non-live effort back to the provisional intraday branch (`H232`) or live monitoring. Do not keep spending local model effort on this event-source branch unless the company-identity mapping contract or the source breadth materially improves.

## F172: H257 Event-Density Router Fails; Alias-Expanded Density Never Covers Enough Held Rows To Gate `H201` (2026-03-31, Session 91)

Session 91 ran `H257`, the event-density router audit, which attempted to gate `H201` by alias-expanded event counts (`≥2` events over the trailing 5 days) on top of the previously validated `H235` surface.

The gating threshold only touched 14 held rows out of 2,261 total (coverage 0.62%, gating share 0.62%), so a router built from this signal simply leaves almost the entire continuation panel empty.

**Implication:** the router idea is closed on the current stack. Keep the richer event source as acquisition evidence, focus on continuing the partial intraday branch (`H232`), and revisit the gate only if a materially different mapping/coverage contract arrives.

## F173: H258 Shows The Current CafeF `1H` Surface Passes As A Reduced-Shape Research Contract, Even Though A Universal Five-Bar / Auction Artifact Is Still Not Honest (2026-04-03, Session 92)

Session 92 reran the intraday branch on the now-current raw CafeF `1H` surface and asked a narrower question than `H233`:
- not "can the lab already publish a universal intraday artifact?"
- but "is the source now strong enough to reopen blocked intraday work as a reduced-shape open / first-hour / close-hour contract?"

The answer was yes.

Coverage / continuity now look materially different from the old `H225` world:
- raw tickers:
  - `402`
- tickers with any overlap:
  - `402`
- tickers with at least `60` overlap days:
  - `398`
- held-row coverage lower bound:
  - `93.05%`
- missing-session rate in-window:
  - `6.87%`

The reduced-shape feature surface is also structurally dense:
- observed reduced-shape rows:
  - `261,990`
- open-gap feature share:
  - `99.996%`
- first-60m feature share:
  - `99.988%`
- close-hour feature share:
  - `99.9996%`

And the liquid cohorts are clean enough to support research honestly:
- liquid banks complete-day share:
  - `97.10%`
- liquid industrials complete-day share:
  - `96.72%`
- liquid fill names complete-day share:
  - `97.07%`

But the universal artifact is still not honest:
- complete-day share present:
  - `67.50%`
- small-tail complete-day share:
  - `0.53%`

So the result is not:
- "H233 is done"

It is:
- the source passes as a reduced-shape research contract
- the source still fails as a universal five-bar / auction-resolution contract

**Key finding:** the old intraday block was truly a data-availability block, not a hidden modeling verdict. Multi-ticker intraday research can now reopen honestly in reduced-shape form.

**Implication:** treat the current CafeF `1H` source as real offline evidence and a usable reduced-shape panel. Keep universal `H233` publication unresolved, but do allow the first reduced-shape predictive screen to run.

## F174: H259 Fails The First Reduced-Shape Intraday Exit Screen; Better Intraday Coverage Does Not Yet Produce Exit Alpha On The Current Continuation Target (2026-04-03, Session 92)

After `H258` passed the contract audit, Session 92 ran the first real reduced-shape predictive screen instead of stopping at data QA.

The screen stayed narrow:
- observed subset only
- custom reduced-shape protocol:
  - dev `2023`
  - validation `2024`
  - confirmation `2025`
- no `2026+` read
- no deterministic integration

Observed sample:
- continuation rows:
  - `2,259`
- observed intraday rows:
  - `2,102`
- observed share:
  - `93.05%`

Baseline on the observed subset:
- `path_core_observed`
- validation AUC:
  - `0.4895`
- validation top-quintile hold advantage:
  - `-0.00078`
- confirmation AUC:
  - `0.4517`
- confirmation top-quintile hold advantage:
  - `-0.00848`

Best intraday model:
- `intraday_shape_core`
- validation AUC:
  - `0.4806`
- validation top-quintile hold advantage:
  - `-0.00128`
- confirmation AUC:
  - `0.5147`
- confirmation top-quintile hold advantage:
  - `-0.00518`

Other reduced-shape variants were worse:
- `intraday_shape_plus_path`
- `intraday_shape_atoms`

No model was promotable, and the best intraday candidate still lost to the path-only observed-subset baseline on the validation gate that matters most for continuation-family promotion.

**Key finding:** the current CafeF `1H` surface is good enough to reopen research, but the first reduced-shape exit-family predictive screen still fails. Better intraday availability is not, by itself, evidence of exit alpha.

**Implication:** keep `H258` as real acquisition / offline evidence, but close the direct reduced-shape exit restart on the current continuation target. Do **not** open `H260/H261` from this result. If intraday model work continues later, pivot toward library-grade intraday state atoms or selector-state stress summaries rather than immediate exit integration.

## F175: H262 Shows Reduced-Shape Intraday Contradiction Survives Only Inside `breakout_followthrough`; The Global H259 Failure Was An Aggregation Failure, Not A Total Mechanism Kill (2026-04-03, Session 93)

Session 93 reopened the `H259` result the narrow way:
- no new data fetch
- no `2026+` read
- no direct deterministic integration
- just a family-scoped audit on the saved `H259` observed panel

The key split already existed inside the panel:
- `momentum_continuation`
- `breakout_followthrough`
- `crowding_pressure`

Family sample sizes were still large enough to support an honest local audit:
- `momentum_continuation`:
  - dev `498`
  - validation `509`
  - confirmation `448`
- `breakout_followthrough`:
  - dev `143`
  - validation `97`
  - confirmation `103`
- `crowding_pressure`:
  - dev `93`
  - validation `127`
  - confirmation `84`

Three family-local models were tested:
- `path_core`
- `intraday_atoms`
- `intraday_atoms_plus_path`

Only one family survived:
- `breakout_followthrough`
  - family path-core validation AUC:
    - `0.5273`
  - best candidate:
    - `intraday_atoms`
  - validation AUC delta vs family path-core:
    - `+0.1589`
  - validation top-quintile hold-advantage delta vs family path-core:
    - `+0.0308`
  - confirmation top-quintile hold advantage:
    - `+0.0457`

The other families failed cleanly:
- `crowding_pressure`
  - best intraday candidate lifted validation AUC modestly
  - but validation top-quintile hold advantage got worse
- `momentum_continuation`
  - best intraday candidate lost on both validation AUC and validation top-quintile hold advantage

**Key finding:** the `H259` failure was not a total rejection of reduced-shape intraday contradiction. The real surviving mechanism is narrow: intraday contradiction survives only inside the `breakout_followthrough` entry-thesis family on the observed `2023-2025` subset.

**Implication:** do not reopen global reduced-shape continuation modeling. Carry forward only the family-aware branch. Keep `momentum_continuation` and `crowding_pressure` on path-only treatment unless a later materially different contract reopens them.

## F176: H263 Shows The Pooled Family-Aware Intraday Router Beats The Global H259 Baseline On The Observed Subset, So The Next Honest Step Is Deterministic Family-Aware Integration (2026-04-03, Session 93)

After `H262` passed, Session 93 ran the smallest honest recombination:
- use the `H262` family-local winner only where it actually passed
- leave the failed families on their own path-core baseline
- compare the pooled router back against the global `H259` benchmarks on the same observed subset

The pooled router was simple:
- `breakout_followthrough`:
  - use `intraday_atoms`
- `crowding_pressure`:
  - keep `path_core`
- `momentum_continuation`:
  - keep `path_core`

Global benchmark from `H259`:
- `path_core_observed`
  - validation AUC:
    - `0.4895`
  - validation top-quintile hold advantage:
    - `-0.00078`
  - confirmation top-quintile hold advantage:
    - `-0.00848`

Best global intraday benchmark:
- `intraday_shape_core`
  - validation AUC:
    - `0.4806`
  - validation top-quintile hold advantage:
    - `-0.00128`
  - confirmation top-quintile hold advantage:
    - `-0.00518`

Pooled family-aware router:
- validation AUC:
  - `0.4963`
- validation top-quintile hold advantage:
  - `-0.00024`
- confirmation top-quintile hold advantage:
  - `+0.00159`

Delta vs the global path baseline:
- validation AUC:
  - `+0.0067`
- validation top-quintile hold advantage:
  - `+0.00054`
- confirmation top-quintile hold advantage:
  - `+0.01007`

So the narrow recombination does pass the branch rule:
- it beats the global path-only observed baseline on both validation gate dimensions
- and it is no worse than the baseline on confirmation top-quintile hold advantage

**Key finding:** reduced-shape intraday does have continuation value on the current observed subset, but only as a family-aware router. The useful contract is narrow and still offline-only; it is not evidence that the original global `H259` formulation should be revived.

**Implication:** keep the live branch unchanged. Keep `H260/H261` closed. Advance only to a narrow `H264`-style deterministic family-aware continuation veto integration on the observed `2023-2025` subset. If that deterministic follow-through fails, the honest fallback is to keep this as offline evidence only and return to selector-state stress or library-atom work.
