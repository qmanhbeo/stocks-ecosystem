# Next Steps & Session History

This is the live small-brain file for current state, recent direction, and next priorities.
Use `notes/session_99_log.md` for the latest full session detail.
Use the branch-result buckets in `README.md` and `README_for_AGENTS.md` when deciding whether a branch outcome is a live promotion, offline evidence promotion, or a branch kill / park.

---

## Current State

**Session status:** Session 99 ran the next materially different fallback after the `H269` current-account failure, still without touching the `2026+` lockbox. `H270` **PASSED**: rewriting the breakout target from generic `buy_now` into fixed breakout-survivor contracts revived the reduced-shape intraday branch on the observed breakout sleeve. The winning contract was `net_soft_survivor` (`5d cycle_return_net > -0.01` and `10d cycle_return_net > 0.00`), where `intraday_shape_core` beat `breakout_path_core` on validation AUC (`0.5168` vs `0.5074`) and delivered positive above-mean top-quintile `10d` returns in both validation (`+0.87%` vs phase mean `+0.18%`) and confirmation (`+0.89%` vs phase mean `+0.59%`). Branch consequence: keep the live branch unchanged, promote `H270` as offline evidence only, and advance the exact branch to deterministic breakout-survivor gate integration (`H271`). (2026-04-03)

### Start next session here

1. Record the next market-session outcome against the **rollback sticky activated** paper-trade book:
   - current active live branch from the `2026-03-26` signal / `2026-03-27` execution:
     - held names: `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
     - cash `0.00%`
   - current activation state: `ON`
2. Keep the live sticky branch frozen:
   - no parameter changes on `2026+`
   - only update `H179/H183` and record completed forward cycles
3. Keep ADV / capacity work parked unless the explicit goal is scale research. Do not reopen it as the active blocker for the small-account branch.
4. Keep the timing-branch closure logic explicit:
   - Session 73's original `H221-H229` closure was correct on the old local stack:
     - event surface v1 failed the continuation / exit predictive gate
     - local intraday coverage was effectively absent
     - local order-book history was absent
   - Session 92 reopened only the reduced-shape intraday slice because genuinely new data now exists
   - `H258` passed the reduced-shape contract audit
   - `H259` failed the first reduced-shape exit predictive screen
   - Session 93 then reopened a narrower family-aware continuation branch on the same observed subset:
     - `H262` passed only for `breakout_followthrough`
     - `H263` passed as a pooled family-aware router
   - do **not** open `H260/H261` on the dead direct-restart contract
   - Session 94 then ran that deterministic follow-through honestly:
     - `H264` failed
     - the best family-router cutoff looked good on validation but broke on confirmation and triggered only `21` exits
     - both global and family-aware `path_core` controls beat it
   - do **not** run `H265`
   - do **not** keep tuning continuation on this intraday branch
   - Session 95 then relocated the surviving breakout-specific intraday information to entry honestly:
     - `H266` passed
     - best intraday model:
       - `intraday_shape_core`
       - validation AUC `0.5151`
       - validation top-quintile cycle return `+0.00233`
       - confirmation top-quintile cycle return `+0.00410`
     - best non-intraday control:
       - `selection_baseline`
       - validation AUC `0.5132`
       - validation top-quintile cycle return `-0.00170`
       - confirmation top-quintile cycle return `-0.00142`
     - observed breakout share:
       - `94.42%`
   - do **not** change the live branch yet
   - Session 96 then completed the first deterministic entry-side follow-through honestly:
     - `H267` passed
     - winning gate:
       - `dev_q90`
       - threshold `0.5198`
   - Session 97 then tested reintegration into the carried broader book honestly:
     - `H268` passed narrowly
   - Session 98 then ran the last narrow current-account compatibility check:
     - `H269` failed
     - candidate `h268_overlay_plus_sticky`:
       - validation relative return `-0.5635`
       - confirmation relative return `-0.3364`
       - overall relative return `-0.5495`
     - operational sticky baseline:
       - validation relative return `-0.0873`
       - confirmation relative return `+0.1880`
       - overall relative return `+0.4660`
     - the candidate also lost to the carried sparse control
     - narrowness cost dominated:
       - `VC` sparse-book rate `0.9800`
       - `VC` avg holdings `0.7014`
   - do **not** change the live branch yet
   - close this exact breakout-trust continuation family on the current contract
   - Session 99 then reopened a materially different breakout-local branch honestly:
     - `H270` passed the breakout survivor label rewrite audit
     - winning contract:
       - `net_soft_survivor`
       - `5d cycle_return_net > -0.01`
       - `10d cycle_return_net > 0.00`
     - winning intraday model:
       - `intraday_shape_core`
       - validation AUC `0.5168` vs `0.5074` for `breakout_path_core`
       - validation top-quintile `10d` return `+0.87%` vs phase mean `+0.18%`
       - confirmation top-quintile `10d` return `+0.89%` vs phase mean `+0.59%`
     - best path control still had the stronger confirmation top-quintile `10d` return:
       - `breakout_path_core`
       - `+1.24%`
   - do **not** change the live branch yet
   - keep `H270` as offline evidence only until deterministic follow-through is tested
   - the next exact branch is:
     - `H271` deterministic breakout-survivor gate integration
   - order-book / queue work remains blocked
5. Treat the current daily-data synthesis queue as exhausted:
   - `H253-H256` closed the remaining recombination ideas on the current stack
   - do **not** keep inventing local model-side branches on this family without:
     - genuinely new data
     - a materially new label / contract
     - or more forward live evidence
   - default back to acquisition-first timing work or live monitoring
6. Start any new timing-data work from the acquisition plan, not from model scripts:
   - read `notes/timing_data_acquisition_plan.md`
   - check `notes/timing_data_source_scorecard.csv`
   - branch order is:
     - intraday / auction acquisition first
     - richer company-event source second
     - otherwise stop timing research and wait for more forward live evidence
   - current acquisition-side practical note:
     - Session 92 resolved the current intraday source shape honestly:
       - `H258` passed the reduced-shape contract audit:
         - `402` raw tickers
         - `398` tickers with `60+` overlap days
         - held-row coverage lower bound `93.05%`
         - missing-session rate `6.87%`
         - liquid-bank / industrial / fill cohorts all around `97%` complete-day share
       - the universal artifact is still **not** honest:
         - complete-day share present `67.50%`
         - the illiquid tail still collapses badly
       - `H259` then failed the first reduced-shape exit predictive screen:
         - no reduced-shape intraday model beat the path-only observed-subset baseline on validation
         - no candidate is promotable
     - Session 93 then narrowed the reopened model-side branch honestly:
       - `H262` passed only for `breakout_followthrough`
       - `H263` passed as a pooled family-aware router:
         - validation AUC `0.4963` vs `0.4895` for `path_core_observed`
         - validation top-quintile hold advantage `-0.00024` vs `-0.00078`
         - confirmation top-quintile hold advantage `+0.00159` vs `-0.00848`
       - the intraday branch is still observed-subset and offline-only:
         - do **not** claim `H233` solved
         - do **not** change the live branch
     - Session 94 then completed the deterministic follow-through:
       - `H264` failed
       - best family-router cutoff:
         - `family_router__thr_0p4`
         - validation relative delta `+0.2006`
         - confirmation relative delta `-0.0760`
         - exit events `21`
       - overall deterministic winner:
         - `global_path_core__thr_0p5`
       - family-aware path-only control also beat the router:
         - `family_path_core__thr_0p55`
       - branch consequence:
         - keep the Session 93 router as offline evidence only
         - do **not** run `H265`
         - pivot away from continuation integration
     - Sessions 89-90 also resolved the parallel event-source search:
       - `H234` passed using the local CafeF company-news archive with exact `published_at` timestamps and conservative title-ticker linkage
       - recovered family coverage already includes:
         - `176` earnings tickers
         - `120` board / management tickers
         - `107` shareholder-meeting tickers
         - `97` rights / issuance tickers
       - `H235` then tested one strict title-alias expansion mode:
         - masked-holdout precision `98.82%`
         - `2,861` added alias-linked unique articles
         - expanded `5d` held-row recent-any coverage `2.30%`
       - branch decision:
         - the richer source is real
         - do **not** open `H236`
         - keep event-surface publication work parked until the mapping / source contract is materially better
   - preferred acquisition-side order from here:
     - first: keep the reduced-shape intraday branch narrow and honest:
       - do **not** reopen the dead global `H259` formulation
       - do **not** claim `H233` solved
     - second: the current continuation-veto follow-through is now closed:
       - `H264` failed
       - do **not** run `H265`
       - do **not** keep tuning continuation on this contract
     - third: the breakout-trust continuation family is now closed on this contract:
       - `H269` failed
     - fourth: the breakout-survivor label rewrite is now live as the exact narrow follow-through:
       - `H270` passed
       - next exact step is `H271`
     - fifth: if that stalls further, fall back to:
       - selector-state / stress summaries
     - sixth: if that stalls further, fall back to:
       - library-grade intraday state atoms
     - seventh: keep the richer event-source branch parked as acquisition evidence only:
       - `H234` passed source identification
       - `H235` is mixed but non-promoting
       - do **not** spend more local effort trying to publish event surface v2 from the current archive alone
     - eighth: if neither is being worked, just keep live monitoring and let fetch continue
   - do not confuse that branch with the separate parked stock-specific entry-alpha architecture branch documented in `README.md`, `README_for_AGENTS.md`, and `notes/session_75_log.md` plus `notes/session_76_log.md` plus `notes/session_77_log.md` plus `notes/session_78_log.md` plus `notes/session_79_log.md`
     - Sessions 75-79 already ran the first offline ladder plus the small-book follow-through (`H238-H248`)
     - current conclusion:
       - useful sparse-book evidence exists
       - historically the branch looks more like `top1/top2` than `top5`
       - local confirmation overlays do not turn that into a live-ready rule
       - `H247` did not rescue the branch by sharpening the label
       - `H248` did not rescue the branch by conditioning on sparse catalyst concentration
       - the only narrow side result still worth remembering is the unsharpened `top2` compact `price_state` model against the `H245` anchor on `2019-2025`
       - because `2026+` stayed locked, that remains offline evidence only
       - no promotable live-ready winner exists
       - Family A (`H247-H248`) is now closed on the current local data stack
     - it is still **not** the active branch while acquisition-first timing work remains policy
6. Treat the live branch as operationally current:
   - `data/features/xs_rl_signal_matrix.parquet` is now current through `2026-03-27`
   - `data/features/activation_state_daily.parquet` is now current through `2026-03-27`
   - `data/features/activation_meta_daily.parquet` is now current through `2026-03-27`
   - `H179` no longer reports a stale matrix
7. Keep the architecture split and the branch decision clear:
   - historical max-return system:
     - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`
     - `+597.09%` relative vs VNINDEX, IR `1.0093`
   - active pseudo-live / live branch:
     - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
     - it won the train-only pseudo-live ladder over `2023-2025`
     - it is the rule currently driving `H179/H183`
   - exit-alpha branch:
     - always-on winner:
       - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
       - validation relative `+54.45%`
       - validation delta vs H207 anchor `+5.48%`
       - confirmation relative `-4.70%`
       - confirmation delta vs H207 anchor `+15.79%`
     - frozen sticky compatibility:
       - `winner_plus_sticky` validation relative `+28.45%` vs incumbent `+29.65%`
       - confirmation relative `+14.63%` vs incumbent `+18.80%`
       - branch decision:
         - exit alpha is real offline
         - do **not** change the live branch from it
   - new-family exit follow-through:
     - `H214`: thesis inconsistency failed cleanly
     - `H215`: failed follow-through was the closest new-family near-miss but still failed the locked gate
     - `H216`: time-under-water failed badly on confirmation
     - `H217`: skipped because no genuinely new exit-family winner displaced H211
   - continuation / hold-vs-exit branch:
     - `H218`: continuation model failed at the first predictive gate
     - `H219`: skipped because H218 produced no promoted continuation model
     - `H220`: skipped because H219 produced no promoted continuation-band winner
   - new-data exit branch:
     - `H221`: corporate-event surface built successfully with held-row coverage `89.59%`
     - `H222`: event predictive screening failed
     - `H223/H224`: skipped because H222 produced no promoted event model
     - `H225`: intraday coverage failed (`0.00%`, only `FPT` 1H local data)
     - `H226-H228`: skipped by rule
     - `H229`: order-book / queue feasibility failed on the local workspace
     - branch decision:
       - stop exit-side research on the current local data stack
       - do not reopen H221-H229 without genuinely new data acquisition
8. Session 65 decision tree outcome:
   - `H192A`: **PASS**
     - the complex `blocked5<=q80 + sector_cap_3` winner is reproducible
     - historical reference metrics match exactly
     - live overlay and live scoreboard now agree with the direct runner
   - `H192B`: **MIXED, NOT EXTREME**
     - recent 30-day monitor on the complex winner:
       - activation-on rate `30.0%`
       - avg cash `59.55%`
       - blocked-extreme rate `36.67%`
       - top-5 buyable mean `4.77`
       - current forward edge vs always-on is positive
     - this is not an “all-cash, obviously too-defensive” state
   - `H193`: **ROLLBACK**
     - expanding-train / next-year test years `2023-2025`
     - winner:
       - `sticky_bonus_0p015`
       - mean relative return `+14.91%`
       - mean IR `0.5856`
     - rejected:
       - `impl__blocked5_q80 + sector_cap_3`
       - mean relative `+14.04%`
       - mean IR `0.4275`
     - branch decision:
       - rollback the active live branch to sticky
       - do **not** run `H194/H195` on the failed blocked-buy family unless the branch is intentionally reopened later
9. Parked future architecture branch:
   - if the repo intentionally continues architecture work around "buy this stock now even if the rest are weak", start from:
     - `README.md`
     - `README_for_AGENTS.md`
     - `notes/session_75_log.md`
     - `notes/session_76_log.md`
     - `notes/session_77_log.md`
     - `notes/session_78_log.md`
     - `notes/session_79_log.md`
   - branch thesis:
     - keep selection alpha as the cross-sectional prior
     - reinterpret activation alpha as a soft exposure prior
     - add stock-specific entry alpha so breadth can vary from `0..K`
   - canonical offline artifacts:
     - `data/features/entry_alpha/candidate_panel_daily.parquet`
     - `data/features/entry_alpha/entry_labels_cycle5.parquet`
     - `data/features/entry_alpha/entry_scores_daily.parquet`
   - Session 75 branch outcome:
     - `H239` sparse breadth was the only strong structural pass
     - `H240-H243` did not produce a promotable rule or model
     - `H244` showed the dev-selected sparse-breadth winner did not survive validation cleanly enough to promote
   - Session 76 branch outcome:
     - `H245` showed the branch behaves more like a historical `top1` contract than a `top5` timing overlay
     - but no audited `top_k` contract survives the honest forward gate cleanly enough to promote
   - Session 77 branch outcome:
     - `H246` showed top1 confirmation overlays are effectively a no-op on the current contract
     - top2 soft-consensus overlays overfit validation and fail badly in confirmation / forward
   - Session 78 branch outcome:
     - `H247` showed the current label-sharpening path does not rescue the branch on `2019-2025`
     - no `label_edge_buffer > 0` candidate beat the carried `H245` `top1/top2` anchors honestly
     - the only surviving side result is the unsharpened `top2` compact `price_state` model, which still needs a future `2026+` lockbox check before it can count as more than offline evidence
   - Session 79 branch outcome:
     - `H248` showed sparse catalyst concentration does not rescue the carried small-book contracts on the current data stack
     - the strongest `top1` gate was a large validation overfit and the best `top2` gate still failed the `2025` floor
     - gated versions of the `H247` `top2` `price_state` side result were uniformly worse
   - this remains lower priority than H230-H237 acquisition-first work

### Hypothesis Queue If Model-Side Research Is Intentionally Reopened

This queue is subordinate to `H230-H237` acquisition-first timing work and to the frozen live sticky branch.
Use it only if the acquisition branch is intentionally paused, blocked, or resolved.
Keep the locked protocol:
- dev `2015-2022`
- validation `2023-2024`
- one-shot confirmation `2025`
- forward lockbox `2026+`

Priority order:
- first: small-book / breadth architecture (`H247-H248`)
- second: selector / activation compatibility (`H249-H250`)
- third: current-data event-surface reuse (`H251`)

Family A — small-book / breadth architecture

- `H247`: dynamic breadth target / label-sharpen audit
  - status:
    - completed in Session 78 on `2019-2025` only
    - failed for the sharpened-label thesis
    - do **not** advance to `H248` from this result alone
  - claim:
    - the parked entry-alpha branch may really be a date-level optimal breadth problem (`K in {0,1,2,3,5}`), not a ticker-local confirmation-overlay problem
  - smallest honest test:
    - reuse:
      - `data/features/entry_alpha/candidate_panel_daily.parquet`
      - `data/features/entry_alpha/entry_labels_cycle5.parquet`
      - `data/features/entry_alpha/entry_scores_daily.parquet`
    - audit whether a sharpened small-book target or discrete-breadth target beats the current `H245/H246` `top1/top2` anchors under the locked protocol
  - pass:
    - continue to `H248`
  - mixed:
    - narrow the branch to `{1,2}` or `{1,5}` breadth contracts only
  - fail:
    - close the current small-book target-sharpening path on the existing label stack

- `H248`: catalyst-concentrated small-book audit
  - status:
    - completed in Session 79 on `2019-2025` only
    - failed for the sparse-catalyst thesis
    - park Family A small-book continuation on the current data stack
  - claim:
    - small-book structure may matter only on catalyst-dense days rather than on all dates
  - smallest honest test:
    - condition the `H247/H245` small-book contract on sparse catalyst concentration from news / insider / event surfaces
    - do **not** reopen local confirmation overlays
  - pass:
    - keep the catalyst-conditioned small-book branch alive as offline evidence
  - mixed:
    - keep it as narrow offline evidence only
  - fail:
    - park sparse-catalyst small-book work until genuinely new timing data arrives

Family B — selector / activation compatibility

- `H249`: selector-relative activation audit
  - status:
    - completed in Session 80 on `2015-2025` only
    - failed to rescue selector-relative activation compatibility
    - keep `H201` as selector-only offline evidence
  - claim:
    - `state_blend__h199_sector_laggard_gap_absorb__30` may fail only because `h175` is calibrated to `full_library`, not because the offline selector lead is wrong
  - smallest honest test:
    - rebuild activation-meta-style features around the `H201` selector lead
    - rerun an `H202`-style compatibility ladder offline without touching `2026+`
  - pass:
    - continue to `H250`
  - mixed:
    - keep the selector as offline evidence and test only mild trust modifiers later
  - fail:
    - keep `H201` as selector-only offline evidence
    - do **not** keep tuning local `rel_span` / `rel_threshold` variants on the same locked windows

- `H250`: contradiction-state router
  - status:
    - completed in Session 81 on `2015-2025` only
    - mixed: `h250_disagreement_balance` promoted to selector audit and cleared the baseline additive gate
    - it did **not** beat `H201`, so keep it as offline-only evidence
  - claim:
    - the next selector edge may live in disagreement states between `S1`, `C9`, `C12`, `C13`, `C14`, and the `H199` atom rather than in another additive atom
  - smallest honest test:
    - screen sparse interaction / veto states first
    - carry at most one promoted router into a locked selector audit
  - pass:
    - compare it directly against the `H201` offline lead
  - mixed:
    - keep it as RL-state-only or offline-only evidence
  - fail:
    - close the current interaction-state family

Family C — current-data event-surface reuse

- `H251`: event-surface trust modulator
  - status:
    - completed in Session 82 on `2015-2025` only
    - pass: event-surface regimes improved `H201` only as selector trust context
    - promoted regimes:
      - `top5_report_window_ge2`
      - `top5_recent_filing_ge1`
  - claim:
    - `data/features/event_surface_daily.parquet` may fail as exit alpha but still be useful as a selection / activation trust variable
  - smallest honest test:
    - run a conditional IC / selector-efficacy decomposition by event regime before any deterministic integration
  - pass:
    - open `H252`, a light offline trust-modifier audit on `H201` only
  - mixed:
    - keep event surface v1 as an explanatory diagnostic only
  - fail:
    - leave event-surface reuse parked until `event_surface_v2` or richer acquisition passes

- `H252`: H201 event-surface trust audit
  - status:
    - completed in Session 83 on `2015-2025` only
    - pass: `top5_report_window_ge2` survives as a real hard gate around `H201`
    - mixed: the milder `report_window_half_off` variant
    - fail: the `recent_filing_half_off` carry
  - claim:
    - a light deterministic trust modifier around `H201` can convert the `H251` event regimes into cleaner offline selector efficacy without reopening a broad event search
  - smallest honest test:
    - audit mild gating or trust-weighting around `state_blend__h199_sector_laggard_gap_absorb__30`
    - start from `top5_report_window_ge2`
    - keep `top5_recent_filing_ge1` as the only secondary carry
  - pass:
    - keep the hard report-window gate as offline evidence
    - then open `H253`, a narrow frozen-compatibility audit
  - mixed:
    - keep the event regimes as explanatory diagnostics only
  - fail:
    - close current-data event-surface reuse on the present data stack

- `H253`: H252 frozen-compatibility audit
  - status:
    - completed in Session 84 on `2015-2025` only
    - mixed: the hard report-window gate beats frozen sticky on validation, but fails badly against it in `2025` confirmation
  - claim:
    - the `H252` hard report-window gate may be a real offline improvement, but it still has to survive a frozen compatibility audit before it becomes a serious live-adjacent branch
  - smallest honest test:
    - compare `winner_report_window_gate` directly against the frozen sticky incumbent on `2015-2025`
    - do not touch `2026+`
    - do not broaden the event family beyond `top5_report_window_ge2`
  - pass:
    - keep it as serious offline evidence and only then decide whether a live-monitor branch is justified later
  - mixed:
    - keep it as selector-only offline evidence
    - then open `H254`, a hybrid selector switchboard audit
  - fail:
    - keep `H252` as an explanatory offline result, not a compatibility winner

- `H254`: report-window selector switchboard audit
  - status:
    - completed in Session 85 on `2015-2025` only
    - failed: the exact hybrid switchboard underperforms frozen sticky in both validation and confirmation
  - claim:
    - `H201` may be a report-window specialist rather than a universal selector winner, so the right architecture may be incumbent sticky off-regime and hard-gated `H201` on-regime
  - smallest honest test:
    - compare a two-arm switchboard on `2015-2025` only:
      - incumbent sticky off-regime
      - `H252` hard-gated `H201` on-regime
    - do not touch `2026+`
    - do not broaden the event family or contradiction family yet
  - pass:
    - keep it as serious offline hybrid evidence and only then decide whether a live-monitor branch is justified later
  - mixed:
    - keep it as synthesis-only offline evidence
  - fail:
    - close the current-data report-window selector-switchboard branch

- `H255`: report-window contradiction expert
  - status:
    - completed in Session 86 on `2015-2025` only
    - mixed: confirmation improves slightly inside the gate, but validation collapses too hard to promote
  - claim:
    - `H250` may be globally mixed but locally useful inside the `H252` on-dates even though the broader switchboard failed
  - smallest honest test:
    - on `H252` on-dates only, compare plain `H201` vs `H201` plus one contradiction-state overlay
    - do not touch `2026+`
    - do not broaden the event family or reopen the failed switchboard
  - pass:
    - keep it as serious nested-regime offline evidence and only then decide whether any hybrid revisit is justified later
  - mixed:
    - keep it as synthesis-only offline evidence
    - then move to `H256`
  - fail:
    - close the current-data report-window x contradiction branch

- `H256`: event-driven dynamic breadth
  - status:
    - completed in Session 87 on `2015-2025` only
    - mixed: smaller breadth improves validation inside the gate, but confirmation fails catastrophically
  - claim:
    - the parked small-book evidence and the `H252` report-window gate may still represent the same opportunity-concentration regime even though the selector switchboard failed
  - smallest honest test:
    - on `H252` on-dates only, audit `H201` at `K in {1,2,5}`
    - do not touch `2026+`
    - do not reopen the entry-label branch or the failed switchboard
  - pass:
    - keep it as serious offline architecture evidence and only then decide whether any hybrid revisit is justified later
  - mixed:
    - keep it as synthesis-only offline evidence
    - close the current daily-data synthesis queue on this branch family
  - fail:
    - close the current-data event-driven dynamic breadth branch

### Remaining Synthesis Queue

No current daily-data synthesis hypotheses remain open after `H256`.
If this family is intentionally reopened later, require genuinely new data, a materially new label / contract, or more forward live evidence first.

### Post-H256 Options

These are the honest next moves after the current daily-data synthesis queue closed.
Keep them subordinate to the frozen live branch and to acquisition-first timing policy.

- `partial intraday viability check`
  - claim:
    - the current CafeF fetch is already large enough to keep refining the source contract without pretending the final branch gate is closed
  - smallest honest next test:
    - let the fetch continue, then rerun the `H232` lower-bound read and only carry forward reduced-shape open / first-hour / close-hour structure if the partial surface remains the same shape

- `richer event-source branch is parked as acquisition evidence`
  - claim:
    - the local CafeF company-news archive cleared `H234` and the strict title-alias follow-through in `H235` was informative, but the branch still does not have the coverage to justify publication work
  - smallest honest next test:
    - do not open `H236` on the current archive alone
    - only reopen this branch if the company-identity mapping contract improves materially or the source itself gets broader / cleaner
  - status:
    - `H257` event-density router audit failed: alias-expanded event density >2 over 5 days only covers `0.62%` of continuation rows, so gating `H201` by this signal is not sufficient and the router idea is closed on the current stack

- `wait and monitor only`
  - claim:
    - if no acquisition-side work is being done, the honest move is to stop inventing branches and only monitor the live sticky book while fetch continues
  - smallest honest next test:
    - update `H179/H183`, record forward cycles, and let the data-acquisition branch continue untouched

### Reduced-Shape Intraday Hypothesis Queue

Use this queue while the CafeF `1H` surface is broad enough for research but still not honest as a universal five-bar / auction artifact.
Do not use the current `1H` contract to claim full-resolution timing alpha outright.
Use it to learn whether reduced-shape open / first-hour / close-hour structure is structurally publishable and whether it reopens blocked timing branches honestly.

- `representation stability before alpha`
  - claim:
    - the first valid intraday win may be a stable daily structure representation rather than an immediate predictive timing rule
  - smallest honest next test:
    - on a representative pilot subset, audit whether normalized open / first-hour / close-structure features recur with stable distributions across ticker cohorts after the VCI daily-close bridge

- `open-close surface may survive before full-session surface`
  - claim:
    - the usable intraday artifact may initially be restricted to opening and closing windows even if midday continuity remains too weak
  - smallest honest next test:
    - compare completeness and continuity of open-gap, first-30m / first-60m, and close-auction proxies against midday / VWAP-style fields on the fetched subset

- `missingness taxonomy before modeling`
  - claim:
    - partial intraday gaps must be separated into source-empty prefixes, within-coverage outages, and likely illiquidity / halt days before any predictive work is credible
  - smallest honest next test:
    - build a day-ticker missingness taxonomy against daily tradability states and keep it as a QC mask, not a signal

- `liquidity-normalized transferability`
  - claim:
    - relative intraday features scaled by daily range / liquidity may transfer across names even when raw path levels do not
  - smallest honest next test:
    - audit cross-ticker stability of normalized first-hour reversal, range-expansion, and close-repair features on the current pilot subset

- `event-aligned intraday response later`
  - claim:
    - partial intraday can support response-shape mapping, but only once richer company-event timestamps exist
  - smallest honest next test:
    - keep this parked until `H234` identifies a better event source, then intersect event windows with the pilot intraday coverage before any predictive claim

### Bright-mind hypothesis queue

- `reduced-shape intraday exit restart`
  - status:
    - completed in Session 92
    - `H258` passed the reduced-shape contract audit
    - `H259` failed the first reduced-shape exit predictive screen
    - keep the panel as acquisition / offline evidence only
    - do **not** open `H260/H261`
  - claim:
    - the blocked `H225-H228` family is now materially reopened in reduced-shape form: the `2026-04-03` rerun on the current CafeF raw surface shows `402` raw tickers, held-row coverage `93.05%`, and missing-session rate `6.87%`, so coverage is no longer the blocker for an intraday exit screen; the remaining honesty constraint is artifact shape, because complete-day share present is only `67.50%` and the source is still `1H`, not auction-resolution.
  - smallest honest next test:
    - no direct exit follow-through remains open on this contract; if intraday work continues, shift to state-atom or selector-state branches instead.

- `thesis-family intraday contradiction router`
  - status:
    - completed in Sessions 93-94
    - `H262` passed:
      - the mechanism survives only inside `breakout_followthrough`
    - `H263` passed:
      - the pooled family-aware router beats the global `H259` path-only observed baseline
    - `H264` failed:
      - the router does not survive deterministic continuation-veto integration
      - explicit global and family-aware path-only controls both beat it
    - keep the result offline-only:
      - do **not** change the live branch
      - do **not** reopen `H260/H261`
      - do **not** run `H265`
  - claim:
    - the first reduced-shape exit screen failed because it mixed incompatible entry-thesis families; reduced-shape intraday only matters as a contradiction / trust state inside the `breakout_followthrough` family on the current observed subset.
  - smallest honest next test:
    - no further continuation-veto follow-through remains open on this contract; if intraday work continues, relocate the surviving breakout signal closer to entry or selector-state work.

- `family-aware deterministic continuation veto integration`
  - status:
    - completed in Session 94
    - `H264` failed
    - overall deterministic winner:
      - `global_path_core__thr_0p5`
    - best family-aware path-only control:
      - `family_path_core__thr_0p55`
    - best family-router cutoff:
      - `family_router__thr_0p4`
      - strong validation, broken confirmation, only `21` exit events
    - branch consequence:
      - close the continuation-veto follow-through
      - do **not** run `H265`
  - claim:
    - the `H263` pooled router is strong enough to justify one deterministic follow-through: intraday contradiction should veto or downweight continuation only for `breakout_followthrough`, while the other families remain on path-core handling.
  - smallest honest next test:
    - no continuation follow-through remains honest here; the next branch should move the surviving breakout-specific intraday information away from hold-vs-exit and toward entry trust or selector-state use.

- `breakout-entry trust relocation`
  - status:
    - completed in Sessions 95-98
    - `H266` passed the predictive audit on the observed breakout-entry subset
    - `H267` passed the deterministic breakout-sleeve gate follow-through
    - `H268` passed narrow reintegration
    - `H269` failed current-account compatibility
    - keep the result offline-only:
      - do **not** change the live branch
  - claim:
    - the surviving reduced-shape intraday mechanism may belong at entry rather than continuation: if only `breakout_followthrough` wants intraday contradiction, the real edge may be in deciding which breakout entries deserve to be taken or trusted the next day.
  - smallest honest next test:
    - no further breakout-sleeve-only follow-through is honest here; the next step is reintegration:
      - apply the `H267` winner only to `breakout_followthrough` rows inside the broader entry ladder and compare that mixed-family book against the ungated broader baseline

- `family-local breakout trust compatibility integration`
  - status:
    - completed in Sessions 97-98
    - `H268` passed narrowly on the carried sparse-breadth contract
    - `H269` failed in the operational / current-account framing
    - keep the result offline-only:
      - do **not** change the live branch
  - claim:
    - if the `H267` high-conviction gate is real, it should still help when applied only to `breakout_followthrough` rows inside the broader entry book, while leaving the other families unchanged.
  - smallest honest next test:
    - none on the current contract:
      - `H269` already failed the final current-account compatibility check
      - park the branch as offline evidence only

- `breakout survivor label rewrite`
  - status:
    - completed in Session 99
    - `H270` passed on the observed breakout sleeve
    - keep the result offline-only:
      - do **not** change the live branch
  - claim:
    - the intraday contradiction signal may be failing because the branch keeps asking a generic `buy_now` or `hold_vs_exit` question; the real target may be narrower: whether a breakout candidate survives the next `1-2` cycles without immediate failure.
  - smallest honest next test:
    - no more label-contract tuning on this pass:
      - carry the `H270` winner forward to deterministic integration (`H271`)

- `breakout survivor gate integration`
  - status:
    - active next branch after Session 99
    - `H270` passed the label rewrite audit on the observed breakout sleeve
  - claim:
    - if the `H270` survivor-target winner is structurally real, a simple deterministic gate on the observed breakout sleeve should improve realized `10d` breakout-survivor economics without needing broad-book reintegration yet.
  - smallest honest next test:
    - calibrate a tiny dev-only threshold grid on the `H270` winning score (`entry_prob__intraday_shape_core`) under the `net_soft_survivor` contract, compare it against the ungated observed breakout survivor sleeve, and only advance if validation and confirmation `10d` return remain above the carried survivor baseline.

- `top-k intraday stress router`
  - status:
    - first fallback if the breakout-survivor deterministic follow-through fails
  - claim:
    - the pseudo-live failure of the daily blocked-buy family may reflect slow implementation-pain proxies rather than a dead mechanism; rebalance-date breadth of first-hour fade, failed breakout, and weak close-repair across the selector's top names may be the missing activation state variable.
  - smallest honest next test:
    - compute date-level stress summaries over the selector's top-k candidates and test them as offline gates on top of the frozen sticky branch; kill quickly if they only recreate the old blocked-buy defensiveness without improving the `2023-2025` pseudo-live ladder.

- `event-to-intraday state transition`
  - status:
    - novel side branch if the lab wants one more materially different timing experiment before waiting for new data
  - claim:
    - the event branch may have failed because raw event timing is too weak alone, while intraday contradiction may only matter on event-driven repricing days; the real state could be event-triggered intraday truth serum, not raw event features or raw intraday features separately.
  - smallest honest next test:
    - intersect `data/features/event_surface_daily.parquet` with the reduced-shape intraday panel on the `breakout_followthrough`-like candidate subset and test whether event-day intraday contradiction gates outperform the same breakout subset without the event condition.

- `library-grade intraday shape atoms`
  - status:
    - best signal-library fallback if branch-level timing work stalls
  - claim:
    - the lab already captured daily open/close asymmetry and gap absorption, but the new multi-ticker `1H` history can test intraday shape atoms those daily bars could not see cleanly: opening drive then fade, weak morning then close repair, and first-hour range expansion without follow-through.
  - smallest honest next test:
    - build `3-5` reduced-shape cross-sectional atoms and screen them for standalone IC plus correlation vs `S1`, `C4`, and `C12`; kill any feature that collapses onto existing daily gap / close-location axes.

- `small-book close-shape confirmation`
  - claim:
    - `H246-H248` killed daily local confirmation overlays on the parked entry-alpha branch, but they did not test signal-day intraday close-shape confirmation available by `T` close; the historical `top1/top2` branch may only survive when candidate leaders absorb weakness into the close before the next open.
  - smallest honest next test:
    - on the existing `H245/H247` candidate panel, condition `top1/top2` entry on signal-day close-hour / close-repair proxies that are known at `T` close, and only continue if `2025` confirmation beats the carried small-book anchors without weakening the locked `2026+` barrier.

10. Session 66 selection-side first pass:
   - locked protocol is now codified in code:
     - dev `2015-2022`
     - validation `2023-2024`
     - one-shot confirmation `2025`
     - forward lockbox `2026+`
   - `H151`: **FAIL**
     - no existing-signal tradability-conditioned composite beat the always-on `full_library` selector baseline on validation
     - no promoted candidate
   - `H152`: **PARTIAL**
     - dev-pass standalone survivors inside `liq_open_basic`:
       - `h152_sector_laggard_tradable`
       - `h152_limit_release_pressure`
       - `h152_liq_open_continue_3`
       - `h152_breakout_volume_quality`
     - none showed naive always-on selector relevance
     - treat them as candidate atoms, not promoted selectors
11. Session 67 additive follow-through:
   - `H196`: **FAIL**
     - no `H152` atom cleared the locked additive promotion rule on top of `full_library`
     - nearest miss:
       - `full_library + h152_sector_laggard_tradable`
       - validation relative `+47.01%` vs baseline `+43.45%`
       - validation IR `0.8863` vs baseline `0.8211`
       - but confirmation IR deterioration failed the promotion gate
     - branch effect:
       - close the `H152` additive path
   - `H197`: **SKIP**
     - skipped by rule because `H196` produced no promoted atoms
   - `H198`: **SKIP**
     - skipped by rule because `H197` produced no promoted winner
   - `H199`: **PARTIAL PASS**
     - second-wave survivors:
       - `h199_sector_laggard_gap_absorb`
       - `h199_breakout_after_compression`
       - `h199_ceiling_release_followthrough`
     - only promoted candidate:
       - `h199_sector_laggard_gap_absorb`
       - dev IC `+0.0117`
       - corr with S1 `+0.0629`
       - validation IC `+0.0015`
       - confirmation IC `+0.0135`
       - naive validation selector relevance `+3.70%`
     - branch effect:
       - carry exactly this atom into the next additive test
12. Session 68 H199 follow-through:
   - `H200`: **PASS**
     - `full_library + h199_sector_laggard_gap_absorb`
     - validation relative `+68.21%` vs baseline `+43.45%`
     - validation IR `1.16` vs baseline `0.82`
     - confirmation relative `-5.95%` vs baseline `-20.02%`
     - promoted cleanly under the locked additive gate
   - `H201`: **PASS**
     - best state-scoped blend:
       - `state_blend__h199_sector_laggard_gap_absorb__30`
       - validation relative `+46.17%`
       - validation IR `0.90`
       - confirmation relative `-13.43%`
       - confirmation delta vs baseline `+6.58%`
     - this is now the strongest offline selector candidate from the `H199` family
   - `H202`: **FAIL**
     - always-on winner selector stayed strong:
       - validation relative `+46.17%`
       - validation IR `0.90`
     - but `winner + sticky activation` lost to the incumbent sticky branch:
       - winner + sticky validation relative `+16.64%`
       - incumbent `full_library + sticky` validation relative `+29.65%`
       - winner + sticky confirmation relative `+24.70%`
       - incumbent confirmation relative `+18.80%`
13. Session 80 selector-relative activation follow-through:
   - `H249`: **FAIL**
     - carried selector:
       - `state_blend__h199_sector_laggard_gap_absorb__30`
     - control rerun with the incumbent sticky gate reproduced the `H202` failure:
       - validation relative `+16.64%`
       - validation delta vs incumbent `-13.01%`
       - confirmation relative `+24.70%`
       - confirmation delta vs incumbent `+5.90%`
     - selector-relative gate candidate:
       - overall gate share `53.82%`
       - gate agreement vs incumbent `72.63%`
       - validation relative `+16.18%`
       - validation delta vs incumbent `-13.47%`
       - confirmation relative `-19.10%`
       - confirmation delta vs incumbent `-37.90%`
     - branch effect:
       - rebuilding `rel2 > 0` on the selector's own history does **not** rescue compatibility
       - keep `H201` as selector-only offline evidence
       - if model-side queue work is intentionally continued later, move to `H250`
     - branch effect:
       - do not replace the live branch
       - keep the H201 winner as offline-only research evidence
14. Session 81 contradiction-state router follow-through:
   - `H250`: **MIXED**
     - promoted router:
       - `h250_disagreement_balance`
       - active share `13.35%`
       - dev IC `+0.0184`
       - validation IC `+0.0159`
       - confirmation IC `+0.0184`
     - direct selector audit:
       - `full_library_plus__h250_disagreement_balance`
       - validation relative `+78.16%`
       - validation delta vs baseline `+34.71%`
       - confirmation relative `-20.80%`
       - confirmation delta vs baseline `-0.78%`
     - direct comparison vs `H201`:
       - validation delta `+31.99%`
       - confirmation delta `-7.36%`
     - branch effect:
       - contradiction-state routing is real enough to keep as offline-only evidence
       - `h250_disagreement_balance` does **not** replace `state_blend__h199_sector_laggard_gap_absorb__30`
       - if model-side queue work is intentionally continued later, move to `H251`
15. Session 82 event-surface trust-modulator follow-through:
   - `H251`: **PASS**
     - promoted trust regimes on the `H201` winner:
       - `top5_report_window_ge2`
         - overall gate share `49.21%`
         - validation IC delta `+0.0104`
         - confirmation IC delta `+0.0134`
         - validation top-5 edge delta `+0.0174`
         - confirmation top-5 edge delta `+0.0146`
       - `top5_recent_filing_ge1`
         - overall gate share `58.99%`
         - validation IC delta `+0.0038`
         - confirmation IC delta `+0.0198`
         - validation top-5 edge delta `+0.0016`
         - confirmation top-5 edge delta `+0.0043`
     - branch effect:
       - event surface v1 remains closed as an exit predictor on the current stack
       - it does reopen narrowly as selector trust context for `state_blend__h199_sector_laggard_gap_absorb__30`
       - baseline and `H250`-augmented selectors are mixed only under the same regimes
       - if model-side queue work is intentionally continued later, move to `H252`
16. Session 83 H201 event-surface trust audit:
   - `H252`: **PASS**
     - promoted winner:
       - `winner_report_window_gate`
       - regime `top5_report_window_ge2`
       - overall gate share `49.34%`
       - validation relative `+59.57%`
       - validation delta vs `H201` always-on `+13.40%`
       - validation IR delta `+0.33`
       - confirmation relative `-10.98%`
       - confirmation delta vs `H201` always-on `+2.45%`
     - mixed only:
       - `winner_report_window_half_off`
       - confirmation improves slightly, but validation deteriorates
     - failed carry:
       - `winner_recent_filing_half_off`
       - degrades both validation and confirmation materially
     - branch effect:
       - event surface v1 still does **not** reopen as a broad family
       - the only surviving H252 implementation is a hard `top5_report_window_ge2` gate around `H201`
       - keep that as offline evidence only
       - if model-side queue work is intentionally continued later, move to `H253`
17. Session 84 frozen compatibility audit:
   - `H253`: **MIXED**
     - `winner_report_window_gate`
       - validation relative `+59.57%`
       - validation delta vs incumbent sticky `+29.91%`
       - validation IR delta `+0.62`
       - confirmation relative `-10.98%`
       - confirmation delta vs incumbent sticky `-29.78%`
       - confirmation IR delta `-1.17`
     - `winner_always_on`
       - also fails compatibility in confirmation against frozen sticky
     - branch effect:
       - the hard report-window gate remains offline regime evidence only
       - frozen sticky remains the live-adjacent benchmark
       - if model-side queue work is intentionally continued later, move to `H254`
18. Session 85 report-window selector switchboard audit:
   - `H254`: **FAIL**
     - `switchboard_h201_on_regime`
       - validation relative `+23.51%`
       - validation delta vs incumbent sticky `-6.14%`
       - validation IR delta `-0.08`
       - confirmation relative `+5.72%`
       - confirmation delta vs incumbent sticky `-13.08%`
       - confirmation IR delta `-0.43`
     - branch effect:
       - close the current-data report-window selector-switchboard branch
       - keep `H252/H253` as offline regime evidence only
       - if model-side queue work is intentionally continued later, move to `H255`
19. Session 86 report-window contradiction expert:
   - `H255`: **MIXED**
     - `winner_plus_router_report_window_gate`
       - validation relative `+5.65%`
       - validation delta vs `H252` baseline `-53.92%`
       - validation IR delta vs `H252` baseline `-1.04`
       - confirmation relative `-8.20%`
       - confirmation delta vs `H252` baseline `+2.78%`
       - confirmation IR delta vs `H252` baseline `+0.04`
     - branch effect:
       - keep the nested contradiction branch as synthesis-only offline evidence
       - do not reopen the failed switchboard from it
       - if model-side queue work is intentionally continued later, move to `H256`
20. Session 87 event-driven dynamic breadth:
   - `H256`: **MIXED**
     - `winner_report_window_gate_k1`
       - validation relative `+74.44%`
       - validation delta vs gated `K=5` baseline `+14.87%`
       - confirmation relative `-50.07%`
       - confirmation delta vs gated `K=5` baseline `-39.08%`
     - `winner_report_window_gate_k2`
       - validation relative `+69.33%`
       - validation delta vs gated `K=5` baseline `+9.76%`
       - confirmation relative `-42.63%`
       - confirmation delta vs gated `K=5` baseline `-31.65%`
     - branch effect:
       - smaller breadth is only validation-side structure on the current stack
       - the current daily-data synthesis queue is now closed
       - return non-live focus to acquisition-first timing work or live monitoring
13. Session 69 selector follow-through:
   - `H203`: **PASS**
     - one pair candidate survived the always-on additive gate:
       - `full_library_pair__h199_sector_laggard_gap_absorb__h199_breakout_after_compression`
       - validation relative `+65.60%`
       - validation IR `1.14`
       - confirmation relative `-14.86%`
     - branch effect:
       - the pair family earned one more test
   - `H205`: **FAIL**
     - state-scoped pair blends did not beat the H201 offline lead:
       - best:
         - `state_pair_blend__h199_sector_laggard_gap_absorb__h199_breakout_after_compression__10`
         - validation relative `+48.31%`
         - delta vs H201 winner `+2.14%`
         - validation IR `0.89`
         - delta vs H201 winner `-0.01`
         - confirmation relative `-19.39%`
         - delta vs H201 winner `-5.96%`
     - branch effect:
       - do not run `H206`
       - close the H203/H205 pairwise extension family
   - `H204`: **FAIL**
     - all five fresh atoms were evaluated under the locked dev / validation / confirmation protocol
     - four passed the dev standalone gate, but none showed selector relevance
     - best dev IC:
       - `h204_sector_mom_laggard_volume`
       - dev IC `+0.0257`
       - validation IC `+0.0124`
       - confirmation IC `+0.0291`
       - validation selector relevance `-29.91%`
       - confirmation selector relevance `-35.41%`
     - branch effect:
       - stop the current selector-discovery ladder here
       - do not keep recombining H199/H204 atoms against the same locked protocol window
14. Session 70 exit-alpha ladder:
   - objective:
     - test whether the missing edge is post-entry exit timing rather than more selection or activation complexity
   - `H207`: **PASS**
     - promoted always-on anchor:
       - `rank_decay__rank_exit_threshold_5p0__replacement_margin_0p05`
       - validation relative `+48.96%`
       - validation delta vs always-on baseline `+5.51%`
       - validation IR `0.89`
       - validation IR delta `+0.07`
       - confirmation relative `-20.49%`
       - confirmation delta `-0.48%`
   - `H208`: **FAIL**
     - time-plus-decay variants did not beat the H207 rank-decay winner under the locked promotion rule
   - `H209`: **FAIL**
     - sticky winner exits improved slightly but did not clear the promotion gate over the H207 anchor
   - `H210`: **FAIL**
     - liquidity-deterioration exits added no value
   - `H211`: **PASS**
     - promoted always-on exit winner:
       - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
       - validation relative `+54.45%`
       - validation delta vs H207 anchor `+5.48%`
       - validation IR `1.17`
       - validation IR delta `+0.28`
       - confirmation relative `-4.70%`
       - confirmation delta vs H207 anchor `+15.79%`
   - `H212`: **FAIL**
     - replacement-pressure exits did not beat the H211 winner
   - `H213`: **FAIL**
     - the H211 winner improved always-on selector economics
     - but failed frozen sticky compatibility:
       - `full_library_plus_sticky`: validation relative `+29.65%`, IR `0.61`, confirmation relative `+18.80%`
       - `winner_plus_sticky`: validation relative `+28.45%`, IR `0.62`, confirmation relative `+14.63%`
     - branch effect:
       - keep the live sticky branch unchanged
       - close the current exit ladder
       - do not retune H207-H213 thresholds against `2025`
15. Session 71 genuinely new exit-family follow-through:
   - objective:
     - reopen exit research only with genuinely different post-entry families, not H207-H213 threshold tuning
   - `H214`: **FAIL**
     - thesis inconsistency exit did not come close to the H211 winner
     - best new variant:
       - `thesis_inconsistency__score_drop_threshold_0p05__thesis_drop_threshold_0p1`
       - validation relative `+28.44%`
       - delta vs H211 `-26.01%`
   - `H215`: **FAIL, NEAR-MISS**
     - best variant:
       - `failed_followthrough__current_return_threshold_0p0__grace_days_2__peak_return_threshold_0p03__score_drop_threshold_0p0`
       - validation relative `+56.39%`
       - delta vs H211 `+1.95%`
       - validation IR delta `+0.0448`
       - confirmation delta `-0.52%`
     - real information, but not enough to promote
   - `H216`: **FAIL**
     - best variant:
       - `time_under_water__grace_days_5__peak_return_threshold_0p03__underwater_days_threshold_3`
       - validation relative `+55.30%`
       - delta vs H211 `+0.85%`
       - confirmation delta `-34.66%`
     - strong confirmation failure
   - `H217`: **SKIP**
     - skipped by rule because no new family displaced H211
   - branch effect:
     - the current exit ladder is more clearly closed
     - do not reopen H214-H217 on the same locked window
13. Session 72 continuation / hold-vs-exit hazard branch:
   - objective:
     - change the exit target itself instead of inventing another explicit sell heuristic
   - target:
     - forward `5`-day hold-vs-benchmark advantage for legally sellable held positions
   - `H218`: **FAIL**
     - best model:
       - `continuation_core`
       - validation AUC `0.5060`
       - validation top-quintile hold advantage `-0.0058`
       - confirmation AUC `0.5106`
       - confirmation top-quintile hold advantage `-0.0081`
     - branch effect:
       - no continuation model is worth converting into an exit rule
   - `H219`: **SKIP**
     - skipped by rule because H218 produced no promoted continuation model
   - `H220`: **SKIP**
     - skipped by rule because H219 produced no promoted continuation-band winner
   - branch effect:
     - close H218-H220
     - the next honest exit branch now requires a genuinely new data family
14. Session 73 genuinely new-data exit branch:
   - `H221`: **PASS**
     - built `data/features/event_surface_daily.parquet`
     - ticker/day coverage:
       - `394` tickers
       - `845,646` rows
       - held-position coverage `89.59%`
     - branch effect:
       - event data is usable locally
   - `H222`: **FAIL**
     - best model:
       - `event_only_core`
       - validation AUC `0.5180`
       - validation top-quintile hold advantage `-0.0030`
       - confirmation AUC `0.4862`
       - confirmation top-quintile hold advantage `-0.0108`
     - branch effect:
       - corporate-event surface does not create useful continuation / exit signal on current data
   - `H223`: **SKIP**
     - skipped by rule because H222 produced no promoted event model
   - `H224`: **SKIP**
     - skipped by rule because H223 was skipped
   - `H225`: **FAIL**
     - local intraday coverage is not usable:
       - only `gia_lich_su_FPT_1H.parquet` exists
       - held-row coverage `0.00%`
   - `H226-H228`: **SKIP**
     - intraday branch closed by the H225 coverage gate
   - `H229`: **FAIL**
     - no historical queue / depth archive exists under local `data/`
     - only schema evidence exists in `analysis/probe_vnstock2_output.txt`
   - branch effect:
     - close H221-H229
     - do not continue exit-side research on the current local data stack
15. Session 74 acquisition-branch codification:
   - no new model branch was opened
   - new canonical acquisition docs:
     - `notes/timing_data_acquisition_plan.md`
     - `notes/timing_data_source_scorecard.csv`
   - active acquisition decision tree:
     - `H230-H233`: multi-ticker intraday / auction acquisition
     - if that fails: `H234-H236` richer company-event source
     - if that fails: `H237` stop timing research and wait for new data or more live evidence
   - branch effect:
     - future sessions should treat timing-data acquisition as the active non-live branch
16. Run the next branch in this exact order:
   - live track:
     - keep the live scoreboard running on the rollback sticky branch
     - if sticky stays ahead of sticky always-on for at least `2` additional completed rebalance cycles:
       - keep monitoring only
       - do not reopen blocked-buy family work yet
     - if sticky falls behind sticky always-on over `>= 2` completed cycles:
       - rerun `H192A` to confirm parity has not drifted
       - then choose one branch only:
         - reopen `H194/H195` if the problem is clearly activation-local again
         - otherwise stop local activation tuning and move fully back to selection-side work
   - research track:
     - keep `state_blend__h199_sector_laggard_gap_absorb__30` as the current offline lead selector
     - do **not** replace the live sticky branch from that result alone
     - keep the exit-alpha result archived as offline-only evidence:
       - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
       - do not promote it to live under the current sticky overlay
     - the current selector-discovery ladder is now exhausted:
       - H199 additive path resolved
       - H203/H205 pairwise extension resolved
       - H204 fresh-family search resolved
     - the current exit ladder is also resolved:
       - H207-H213 complete
       - exit alpha exists offline
       - sticky compatibility failed
       - H214-H217 new-family follow-through complete
       - no new family displaced H211
       - H218-H220 continuation / hold-vs-exit branch complete
       - no predictive continuation model emerged
     - exit-side work is now closed on the current local data stack:
       - corporate-event surface failed the predictive gate
       - intraday / auction structure failed the local coverage gate
       - order-book / queue feasibility failed locally
     - if continuing exit research later, the next honest move is new data acquisition:
       - company-specific public event timestamps beyond the current sparse event surface
       - multi-ticker intraday / auction data
       - historical order-book / queue archives
     - do **not** reopen:
       - H199 pairwise recombinations
       - H204 atom recombinations
       - H206, because H205 produced no promoted winner
       - H207-H213 threshold retuning on the same locked window
       - H214-H217 retuning on the same locked window
       - H218-H220 retuning on the same locked window
       - H221-H229 on the same local data stack without new data acquisition
   - anti-leakage rule:
     - do not keep tuning the closed `H152` additive family against `2025`
     - do not keep retuning the exact single-atom `H199` family against `2025` after `H200/H201/H202` resolved it
     - do not keep retuning the closed H203/H205 pairwise branch or H204 fresh-family branch against `2025`
     - do not keep retuning the closed exit-alpha branch H207-H213 against `2025`
     - do not keep retuning the closed new-family exit branch H214-H217 against `2025`
     - do not keep retuning the closed continuation exit branch H218-H220 against `2025`
     - rank them on dev / validation
     - use `2025` once per promoted candidate only
17. Keep the architecture split clear:
   - selection alpha = choose the right names
   - activation alpha = decide whether the selector should be on
   - exit alpha = decide when to stop holding a bought name after entry
   - sequential hypothesis ladders are now the default lab method:
     - one result should unlock, narrow, or kill the next branch
     - avoid broad unordered sweeps when a decision tree is possible
   - Session 65 says selection alpha is strong, activation alpha is still real, but the currently *deployable* form is simpler than the historical max-return stack:
     - fixed path-dependent selector-efficacy rule
     - plus a small retention bonus
   - blocked-buy veto and sector cap stay as archived historical improvements, not the active live branch
18. Only after the sticky live branch has clearly failed forward should the branch reopen these secondary ideas:
   - `H194`: blocked-buy + sector-cap recalibration (implemented, not run after rollback)
   - `H195`: blocked-buy hysteresis (implemented, not run after rollback)
   - keep RL exploratory only; do not spend more compute on new RL ladders until the branch is intentionally reopened

### Session 64 implementation-pain follow-through

- `H190` result:
  - **PASS**
  - sector control finally helped once paired with the stronger blocked-buy veto family
  - best:
    - `impl__blocked5_q80 + sector_cap_3`
    - `+597.09%` relative vs VNINDEX
    - IR `1.0093`
    - avg daily turnover `0.2036`
  - this beat the plain `impl__blocked5_q80` winner:
    - `+590.23%` relative
    - IR `1.0027`
- `H191` result:
  - **PASS**
  - the blocked-buy veto family improved again
  - best pure veto:
    - `impl__blocked5_q80`
    - `+590.23%` relative vs VNINDEX
    - IR `1.0027`
  - this beat the Session 63 `blocked3<=q80` winner:
    - `+527.16%` relative
    - IR `0.9471`
  - local hysteresis around `blocked3` did not add anything over the plain threshold
- final live reruns on the current winner:
  - rule: `h175__rel2_gt0 + sticky_bonus_0p015 + blocked5<=q80 + sector_cap_3`
  - current overlay state from `2026-03-26` signal / `2026-03-27` execution:
    - activation `OFF`
    - held names: none
    - cash `100.00%`
  - `2026` YTD scoreboard:
    - activated: `+5.73%` relative vs VNINDEX, IR `1.17`, avg cash `100.00%`
    - always-on: `-11.22%` relative, IR `-1.65`
  - practical read:
    - the historical winner still prefers to stay out on the current live date
    - the forward edge so far is still entirely defensive

### Session 65 defense-vs-overfit decision

- `H192A` result:
  - **PASS**
  - the complex `blocked5<=q80 + sector_cap_3` winner is reproducible
  - historical reference parity holds exactly against the archived Session 64 summary
  - the live overlay and live scoreboard now match the direct champion runner after the shared-helper refactor
- `H192B` result:
  - **MIXED**
  - recent 30-day monitor on the complex winner:
    - activation-on rate `30.0%`
    - avg cash `59.55%`
    - blocked-extreme rate `36.67%`
    - top-5 buyable mean `4.77`
    - `2026` YTD relative return vs VNINDEX `+3.75%`
    - delta vs always-on `+14.97%`
  - practical read:
    - the complex winner is not “broken by all-cash behavior”
    - but it is not obviously the right live branch either
- `H193` result:
  - **ROLLBACK**
  - expanding-train / next-year tests `2023-2025` rejected the complex winner
  - aggregate ranking:
    - `sticky_bonus_0p015`: mean relative `+14.91%`, mean IR `0.5856`
    - `impl__blocked5_q80 + sector_cap_3`: mean relative `+14.04%`, mean IR `0.4275`
    - `impl__blocked5_q80`: mean relative `+14.04%`, mean IR `0.4275`
    - `impl__blocked3_q80`: mean relative `+13.18%`, mean IR `0.3912`
  - branch decision:
    - active live branch rolled back to sticky
    - `H194/H195` remain implemented but were **not** run because the blocked-buy family failed the pseudo-live gate
- live reruns on the rollback sticky branch:
  - current official activated overlay state:
    - signal date `2026-03-26`
    - execution date `2026-03-27`
    - activation `ON`
    - held names: `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
    - cash `0.00%`
  - `2026` YTD scoreboard:
    - activated sticky: `-3.33%` relative vs VNINDEX, IR `-0.36`
    - sticky always-on: `-11.22%` relative, IR `-1.65`
  - practical read:
    - sticky still trails benchmark in the short 2026 window
    - sticky is materially better than sticky always-on
    - this is good enough to keep the rollback branch live for now

### Session 63 local-refinement follow-through

- `H187` result:
  - **FAIL**
  - sticky + sector cap did not stack
  - best remained the sticky champion:
    - `sticky_bonus_0p015`
    - `+509.76%` relative vs VNINDEX
    - IR `0.9372`
  - combined `sticky_bonus_0p015 + sector_cap_3` underperformed:
    - `+498.04%` relative
    - IR `0.9280`
- `H188` result:
  - **PASS**
  - implementation-pain veto improved the champion
  - best:
    - `impl__blocked3_q80`
    - `+527.16%` relative vs VNINDEX
    - IR `0.9471`
    - avg cash `41.47%`
    - blocked-buy events `42`
  - sticky baseline:
    - `+509.76%` relative
    - IR `0.9372`
    - blocked-buy events `68`
- `H189` result:
  - **FAIL**
  - basket-coherence / score-dispersion guards improved neither return nor IR
  - best remained the sticky baseline; every coherence gate gave up too much return and pushed cash too high
- live reruns on the new `H188` winner:
  - current official activated overlay state:
    - signal date `2026-03-26`
    - execution date `2026-03-27`
    - activation `OFF`
    - held names: none
    - cash `100.00%`
    - rule: `h175__rel2_gt0 + sticky_bonus_0p015 + blocked3<=q80`
  - `2026` YTD scoreboard:
    - activated: `+5.73%` relative vs VNINDEX, IR `1.17`, avg cash `100.00%`
    - always-on: `-11.22%` relative, IR `-1.65`, avg cash `5.49%`
  - practical read:
    - the new champion is improving the short live-forward path by staying out
    - the live branch is now more defensive than the Session 62 sticky champion

### Session 62 live-refresh and local-refinement decision

- `H181` result:
  - refreshed the current-date signal surface through `2026-03-27`
  - new current-year `S1` live extension:
    - `data/features/xs_barrier_vol_1d_hose_live_current.parquet`
    - `2026-01-05` -> `2026-03-27`
    - latest labeled date `2026-03-26`
  - rebuilt:
    - `data/features/xs_open_close_asymmetry.parquet`
    - `data/features/xs_insider_quality_features.parquet`
    - `data/features/xs_dispersion_regime_daily.parquet`
    - `data/features/xs_price_limit_daily.parquet`
    - `data/features/xs_volume_zscore_daily.parquet`
    - `data/features/xs_shortterm_reversal.parquet`
    - `data/features/xs_sector_rotation_daily.parquet`
    - `data/features/execution/tradability_daily.parquet`
    - `data/features/xs_rl_signal_matrix.parquet`
    - `data/features/activation_state_daily.parquet`
    - `data/features/activation_meta_daily.parquet`
  - key infra fix:
    - `C4`, `C5`, and dispersion features no longer inherit the stale `S1` grid
- `H182` result:
  - reran the live activation overlay first on the plain `rel2_gt0` rule, then on the new sticky champion
  - current official sticky overlay state:
    - signal date `2026-03-26`
    - execution date `2026-03-27`
    - activation `ON`
    - held names: `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
    - recent `rel2` state: `+0.013101`
- `H183` result:
  - current-year scoreboard is now live on current data
  - sticky activated book vs sticky always-on (`2026` YTD so far):
    - activated: `-3.33%` relative vs VNINDEX, IR `-0.36`
    - always-on: `-11.22%` relative, IR `-1.65`
  - practical read:
    - both are below benchmark in the short 2026 window so far
    - activation is still materially improving the realized path
- `H184` result:
  - **PASS** — sticky holdings / displacement margin improved the historical champion
  - best:
    - `sticky_bonus_0p015`
    - `+509.76%` relative vs VNINDEX
    - IR `0.9372`
    - avg daily turnover `0.2227`
  - plain `rel2_gt0` reference:
    - `+480.72%` relative
    - IR `0.9095`
    - avg daily turnover `0.2269`
- `H185` result:
  - **MIXED** — sector caps can help slightly, but not enough to beat the sticky champion
  - best:
    - `sector_cap_3`
    - `+482.21%` relative vs VNINDEX
    - IR `0.9123`
  - better than plain `rel2_gt0`, but still worse than `sticky_bonus_0p015`
- `H186` result:
  - **FAIL** — local exposure sizing around `rel2_gt0` gave up too much return
  - all tested half/continuous exposure schedules underperformed the binary sticky champion
  - branch decision:
    - keep activation binary for now once the recent-efficacy condition is met
    - do not reopen local sizing unless a stronger state variable appears

### Session 60 operational activation decision

- Session 60 executed the direct follow-up queue:
  - `H178`: robustness stress for `h175__rel2_gt0`
  - `H179`: live-paper activation overlay
  - `H180`: small augmentations around the champion
- `H178` result:
  - `h175__rel2_gt0` beat always-on on both relative return and information ratio in `15 / 16` stress scenarios
  - the only failing scenario was a mild one:
    - start `2017`
    - round-trip cost `0.10%`
    - relative underperformance `-0.5904`
    - IR underperformance `-0.0030`
  - on the original `2019-2025`, `0.30%` RT setup it still matches the champion:
    - always-on: `+346.40%` relative, IR `0.81`
    - `h175__rel2_gt0`: `+491.69%` relative, IR `0.93`
  - practical read:
    - the activation champion is robust enough to operationalize
    - it is not just a one-window artifact
- `H179` result:
  - the live-paper activation overlay runner is now operational
  - latest matrix-supported overlay state:
    - signal date `2025-12-30`
    - execution date `2025-12-31`
    - activation `ON`
    - held names: `DBT`, `FIT`, `KLB`, `PDN`, `TMT`
    - recent `rel2` state: `+0.008169`
  - but this is **not** yet a true current-date live overlay because:
    - `data/features/xs_rl_signal_matrix.parquet` ends at `2025-12-31`
    - stock data now extends to `2026-03-27`
- `H180` result:
  - no small augmentation beat the plain `h175__rel2_gt0` champion
  - best guard:
    - `h180__rel2_gt0_conf_q50`
    - improved max DD to `-18.94%`
    - but reduced relative return to `+413.39%`
    - and reduced IR to `0.88`
  - branch decision:
    - keep the plain fixed champion
    - stop searching for nearby cosmetic tweaks until the live overlay is current

### Session 59 activation-meta decision

- Session 58 found the first real activation family:
  - `H170 recentsm__rel3_gt0`
- Session 59 stress-tested and extended that family:
  - `H175`: threshold/window sweeps plus yearly walk-forward calibration
  - `H176`: 3-state exposure sizing
  - `H177`: compact walk-forward logistic meta-model
- New champion:
  - `H175` `h175__rel2_gt0`
  - `full_library + k5_r5_eq`
  - `+1052.77%` total
  - `+491.69%` relative vs VNINDEX
  - IR `0.93`
  - max DD `-20.57%`
- This beat:
  - the Session 58 `H170` winner (`+383.07%` relative, IR `0.84`)
  - the old always-on champion (`+346.40%` relative, IR `0.81`)
- Important negative results:
  - `H175` walk-forward yearly rule selection underperformed the fixed `rel2_gt0` rule
  - `H176` 3-state sizing improved several branches but did not beat the new fixed champion
  - `H177` compact activation meta-model helped, but did not beat the fixed champion either
- Branch decision:
  - activation alpha remains active
  - but the branch is now **simpler**, not more complex:
    - fixed smoothed selector-efficacy rules beat the heavier follow-ups
  - do not escalate to larger learned activation models until the fixed champion is stressed more honestly

### Session 58 activation-meta decision

- Session 57 established that deterministic **binary** activation was not enough.
- Session 58 rebuilt the branch around materially different hypotheses:
  - partial exposure sizing
  - path-dependent recent selector efficacy
  - interaction terms
  - entry-window quality
  - hysteresis
  - selector-specific activation
- New artifact:
  - `data/features/activation_meta_daily.parquet`
- Main result:
  - **activation alpha is real only in the smoothed recent-selector-efficacy family**
  - new best gate:
    - `H170` `recentsm__rel3_gt0`
    - `full_library + k5_r5_eq`
    - `+841.14%` total
    - `+383.07%` relative vs VNINDEX
    - information ratio `0.84`
    - max DD `-34.00%`
  - this beats the previous always-on champion:
    - `+769.71%` total
    - `+346.40%` relative
    - information ratio `0.81`
    - max DD `-34.04%`
- Secondary read:
  - `H163` partial exposure sizing improved weaker selectors and reduced drawdown in places, but did not beat the always-on full-library selector
  - `H164`, `H166`, `H167`, `H171`, `H172`, `H173`, and `H174` all failed to beat the champion
  - `H168` and `H169` materially helped `S1`, not `full_library`
- Branch decision:
  - activation alpha is **not** a generic regime-gating problem
  - activation alpha is now the active branch again, but narrowly:
    - selector-efficacy persistence
    - path dependence
    - eventually sizing / meta-labeling on top of `H170`
  - `H151/H152` are now parked behind the `H170` follow-up queue
  - this was later refined further by Session 59, which found a stronger fixed `H175 rel2_gt0` rule

### Session 57 activation-alpha decision

- The repo now treats the problem as two layers:
  - **selection alpha**: choose the right names
  - **activation alpha**: decide when the selector should be on or off
- Session 57 built the canonical activation-state artifact:
  - `data/features/activation_state_daily.parquet`
- H157-H162 tested deterministic binary activation overlays on the frozen selectors:
  - `full_library + k5_r5_eq`
  - `S1`-only `k5_r5_eq`
- Main result:
  - **no deterministic activation gate beat the always-on `full_library + k5_r5_eq` selector**
  - always-on `full_library + k5_r5_eq` remains the current long-only champion:
    - `+769.71%` total
    - `+346.40%` relative vs VNINDEX
    - information ratio `0.81`
    - max drawdown `-34.04%`
- Best near-misses:
  - `H157` opportunity-density `opp__spread_q70`: improved drawdown to `-26.51%` but cut relative return to `+286.05%`
  - `H159` market regime `mkt__credit_risk_on_ge2`: `+266.81%` relative with lower max DD `-28.32%`, but still below the always-on selector
  - `H161` recent efficacy `recent__prev_cycle_gt_m02`: `+314.10%` relative, but still below the always-on selector and with **worse** max DD `-38.96%`
- Secondary result:
  - several activation gates materially improved the weaker `S1`-only selector
  - but none of them overtook the always-on `full_library` selector
- Branch decision at the end of Session 57:
  - activation alpha was **not solved**
  - deterministic binary on/off gating became a tested branch, not an open assumption
  - that result was later superseded by Session 58's path-dependent activation wave

### Session 53 strategic decision

- ADV / capacity is now **parked for the current-account branch**.
- That means:
  - it remains documented clearly as an unresolved scale / deployability problem
  - it is **not** treated as the active blocker for the current account size
  - the branch does **not** claim ADV is solved
- Active next research branch:
  - keep the deterministic paper-trade branch running
  - move the main research queue to **long-only portfolio-choice RL**
  - benchmark RL against a **same-universe deterministic top-k comparator** before interpreting results
- Previously planned tradability-conditioned alpha branch is now parked, not deleted:
  - `H151`: narrow tradability-conditioned composite
  - `H152`: tradability-conditioned alpha search

### Session 54 implementation update

- `H153` now has a concrete RL-side runner:
  - `python -m vn_stock_rl.evaluation.portfolio_baseline`
- It reuses `PortfolioChoiceEnv`, so the deterministic comparator:
  - uses the exact same universe selection logic as RL
  - uses the same long-only execution and settlement rules
  - writes comparable summary and daily baseline outputs
- H153 real baseline result on the first live branch configuration:
  - universe size `20`, top-k `3`, test split `2025-06-12` to `2025-12-30`
  - `s1_only`: `-2.50%` total, `-25.99%` relative
  - `full_library`: `+0.41%` total, `-23.78%` relative
  - `conditioned_subcore`: `+6.32%` total, `-19.30%` relative
  - equal-weight universe benchmark: `+31.74%`
- H154 smoke run passed end to end after patching the trainer to disable the SB3 progress bar automatically when `rich` / `tqdm` extras are unavailable.
- Historical note:
  - at the end of Session 54, the full H154 ladder and H155 were still pending
  - Session 55 completed the first real H154 ladder; see the Session 55 update below for the live state

### Session 55 RL pilot update

- `H154` first real pilot ladder is now complete on seed `1208` with the same:
  - portfolio universe size `20`
  - top-k `3`
  - test split `2025-06-12` to `2025-12-31`
  - PPO `mlp` policy
  - `100000` timesteps
- Held-out RL evaluation results:
  - `S1` only RL:
    - return `+40.30%`
    - equal-weight universe benchmark `+31.74%`
    - Sharpe `2.72`
    - max drawdown `-8.55%`
    - rebalances `1`
  - full-matrix RL (`S1 + C4-C14`):
    - return `-7.90%`
    - Sharpe `-0.27`
    - max drawdown `-30.65%`
    - rebalances `90`
  - conditioned sub-core RL (`S1 + C7 + C8 + C10 + C12 + C13`):
    - return `+15.60%`
    - Sharpe `1.01`
    - max drawdown `-18.59%`
    - rebalances `97`
- Same-universe deterministic comparators from H153:
  - `s1_only`: `-2.50%`
  - `full_library`: `+0.41%`
  - `conditioned_subcore`: `+6.32%`
- Practical reading:
  - `S1`-only RL is the only clear winner on the first seed
  - conditioned sub-core RL beats its deterministic comparator but still trails the benchmark and trails `S1`-only RL badly
  - full-matrix RL is a clean failure on this setup
- Active next step:
  - run `H155` multi-seed robustness on `S1`-only first
  - treat conditioned sub-core as optional secondary validation
  - do not promote the richer feature sets without a stronger explanation for the churn / underperformance

### Session 56 H155 multi-seed update

- `H155` ran the required `S1`-only seed sweep on:
  - `1208`
  - `1209`
  - `1210`
  - `1211`
- Held-out RL returns on the same `2025-06-12` to `2025-12-31` test split:
  - `1208`: `+40.30%`, Sharpe `2.72`, max DD `-8.55%`, rebalances `1`
  - `1209`: `+43.44%`, Sharpe `1.89`, max DD `-21.17%`, rebalances `41`
  - `1210`: `-1.06%`, Sharpe `0.12`, max DD `-30.59%`, rebalances `86`
  - `1211`: `-17.98%`, Sharpe `-1.10`, max DD `-36.04%`, rebalances `88`
- Reference lines:
  - deterministic `s1_only`: `-2.50%`
  - equal-weight universe benchmark: `+31.74%`
- Aggregate read:
  - mean RL return: `+16.18%`
  - median RL return: `+19.62%`
  - benchmark wins: `2 / 4`
  - deterministic wins: `3 / 4`
  - positive-return seeds: `2 / 4`
- Practical reading:
  - `S1`-only RL can clearly extract useful behavior on some seeds
  - but it is not stable enough to promote as the main branch
  - the branch is now exploratory, not primary
  - optional conditioned sub-core seed sweeps were not run because the `S1` branch already failed the stability gate

### Session 57 activation-alpha wave

- `H157`: opportunity-density gates
  - no gate beat always-on `full_library`
  - best real gate: `opp__spread_q70`
    - `+652.12%` total
    - `+286.05%` relative
    - information ratio `0.71`
    - max DD `-26.51%`
- `H158`: tradability-breadth gates
  - no non-trivial gate beat always-on `full_library`
  - `trad__top10_buyable_ge5` matched always-on exactly, which means it was effectively always true
  - strongest real uplift appeared on the weaker `S1` selector, not on the champion
- `H159`: market-regime gates
  - best full-library gate: `mkt__credit_risk_on_ge2`
    - `+614.63%` total
    - `+266.81%` relative
    - information ratio `0.68`
    - max DD `-28.32%`
  - still below always-on `full_library`
- `H160`: breadth/dispersion gates
  - best full-library gate: `bd__disp_q60`
    - `+378.70%` total
    - `+145.71%` relative
    - information ratio `0.53`
  - no activation win
- `H161`: recent-efficacy/cooldown gates
  - nearest full-library miss: `recent__prev_cycle_gt_m02`
    - `+706.77%` total
    - `+314.10%` relative
    - information ratio `0.76`
    - max DD `-38.96%`
  - this is the closest branch, but still not an improvement over always-on
- `H162`: composite activation score
  - strongest result was on the weaker `S1` selector:
    - `comp__score_q70`
    - `+209.28%` total
    - `+58.75%` relative
    - max DD `-16.68%`
  - still far below always-on `full_library`
- Practical read:
  - the repo is stronger at **selection alpha** than **activation alpha**
  - if activation is revisited later, it should not start from another binary on/off gate sweep
  - the next honest step is back to selection-side work

### New reality check after Session 51

**Session 52 operational blocker and workaround**
- Goal was to fetch fresh stock data and emit a live `full_library` paper-trade recommendation.
- The raw stock universe now mostly reaches **Friday, 2026-03-27**, but the local state is mixed:
  - many tickers now have long history through `2026-03-27`
  - some tickers are still stale or truncated (example observed: `BCG` ends `2025-10-08`)
  - `VNINDEX` currently holds only a recent slice (`2025-12-22` to `2026-03-27`)
- The current live `S1` artifact remains stale at `2026-03-11`:
  - `data/features/xs_live_validation_h54_2026.parquet`
- Attempting to rerun `analysis/h75_2026_holdout.py` failed because the live scorer needs long price history to build features, and the current refreshed stock set is not historically consistent enough.
- Workaround used:
  - merged the truncated root `VNINDEX` file with the local full-history backup at `../media-output/signal-xs-momentum/data/stock/gia_lich_su_VNINDEX_1D.parquet`
  - rebuilt live `S1` for the full 2026 slice on the fly
  - rebuilt the stock-derived `full_library` inputs for 2026 on the fly
- Practical consequence:
  - the **official** live pipeline is still not restored end-to-end
  - but an **ad hoc honest paper-trade state for the 2026-03-27 close was produced**
- Historical note:
  - during Session 52, root `VNINDEX` was truncated and had to be recovered from a local backup
  - after Session 55, root `data/stock/gia_lich_su_VNINDEX_1D.parquet` has been refreshed back to full history through `2026-03-27`
  - this removes the benchmark file itself as the active blocker, but it does not prove the full raw stock surface is now historically consistent enough for official live scoring
- Date clarification:
  - `2026-03-28` is a Saturday
  - the latest actionable market close in the refreshed data is `2026-03-27`
  - the paper-trade action below is for the next trading session after that close

**Session 52 live paper-trade checkpoint — 2026-03-27 close**
- Strategy: `full_library + k5_r5_eq`
- Historical cadence result on the latest signal date:
  - **no rebalance** on `2026-03-27`
- Running paper-trade book after the `2026-03-27` execution:
  - `ANV`
  - `PTB`
  - `PTL`
  - `VSI`
  - cash: `19.57%`
- Fresh-entry top-5 snapshot from the same close, if starting from cash:
  - `PTB`
  - `PAC`
  - `VNG`
  - `APG`
  - `DTL`
- Important caveat:
  - this state came from a one-off live assembly workflow, not from a persisted repo script or refreshed official artifact

**Execution alignment correction (Session 49)**
- The deterministic portfolio engine had a one-day liquidity timing bug:
  - tradability flags and `ADV20` were read from the execution-date row (`T+1`)
  - the shared contract defines them on the signal-date row (`T`), because they govern the **next** open
- Fixed behavior:
  - `can_buy_next_open`, `can_sell_next_open`, and `ADV20` now come from the signal-date row
  - the engine still executes at `T+1` open and enforces `T+2.5` sellability
- Implication:
  - Session 48 H138/H139 figures are superseded by Session 49 reruns
  - the qualitative conclusion stays the same on capacity, but the uncapped baseline is materially stronger

**H135 - Signal Library Portfolio Baseline (corrected)**
- Session 46 found a scoring bug in the original H135 blend:
  - non-presence signals were averaged in raw scale
  - `C4` and `C5` were not already on a common `0-1` rank scale
  - corrected blend logic now cross-sectionally ranks each non-presence signal by date before averaging
- Corrected H135 baseline under the same execution contract:
  - next-open execution
  - `T+2.5` sellability (`T+3` close decision, `T+4` open exit fill)
  - zero-volume / ceiling / floor tradability blocks
  - 0.30% round-trip cost
  - top-5 equal-weight, 3-day rebalance
- Corrected result:
  - `s1_only`: `-68.33%` total, `-10.01%` annualized
  - `recent_core`: `-46.81%` total, `-5.63%` annualized
  - `full_library`: `+72.10%` total, `+5.11%` annualized
  - benchmark VNINDEX: `+223.17%` total
- Implication: the library is **not dead**, but default construction still underperforms badly.

**H136 - Portfolio Construction Sweep**
- Swept `full_library` across:
  - `top_k = 3, 5, 8, 10`
  - rebalance cadence `= 3, 5, 10`
  - weighting `= equal, linear, square`
  - score gate `= none, 0.521, 0.570, 0.600`
- Best configuration:
  - `top_k = 5`
  - rebalance every `5` signal days
  - `equal` weighting
  - score gate effectively irrelevant (`none`, `0.521`, and `0.570` tied)
- Best result:
  - `+1105.71%` total return
  - `+25.66%` annualized
  - `+273.09%` relative vs VNINDEX
  - information ratio `0.50`
  - max drawdown `-59.76%`
  - `8/11` positive years
- Structural takeaway:
  - rebalance cadence matters more than fancy weighting
  - `5d` and `10d` cadence dominate `3d`
  - `equal` weighting beats `linear` and `square`
  - portfolio construction, not more signal mining, is the dominant frontier right now

**H137 - Nested Walk-Forward Portfolio Selection**
- Tested the honest version of “let the machine choose construction”:
  - expanding train window
  - minimum 4 train years
  - select the best H136-style config on past years only
  - freeze it and test on the next year
  - test years: `2019-2025`
- Out-of-sample stitched result:
  - `+21.38%` total
  - `+2.84%` annualized
  - `-42.46%` relative vs VNINDEX
  - information ratio `-0.08`
  - max drawdown `-55.65%`
- Selected configs were simple, not exotic:
  - mostly `top_k=5`, rebalance every `10` days, `equal` weighting
  - early years briefly chose `top_k=3` or `top_k=10` with `5d` cadence
- Implication:
  - the H136 full-sample winner is not reliable enough to trust directly
  - simple nested config selection does **not** yet justify “ML for construction”
  - the next honest path is smaller, simpler, and more realistic within a long-only framework

**H138 - Fixed-Menu Honest Validation (rerun after signal-date liquidity fix)**
- Reran the fixed menu on the honest `2019-2025` holdout under the corrected engine:
  - `k3_r5_eq` = top-3, 5-day cadence, equal weight
  - `k5_r5_eq` = top-5, 5-day cadence, equal weight
  - `k5_r10_eq` = top-5, 10-day cadence, equal weight
- Result: **all three simple fixed rules still beat VNINDEX, and by more than Session 48 suggested**
  - `k5_r5_eq`: `+769.49%` total, `+36.59%` annualized, `+346.29%` relative, IR `0.81`, `7/7` positive years
  - `k3_r5_eq`: `+748.57%` total, `+36.11%` annualized, `+335.55%` relative, IR `0.70`, `6/7` positive years
  - `k5_r10_eq`: `+573.69%` total, `+31.65%` annualized, `+245.79%` relative, IR `0.67`, `4/7` positive years
- Implication:
  - H137’s yearly selector was even worse than previously thought
  - the corrected uncapped long-only baseline is strong enough to matter
  - but deployability still has to survive explicit capacity rules

**H139 - Capacity / Fee Stress (rerun after signal-date liquidity fix)**
- Reran the H138 fixed-menu stress on `2019-2025` across:
  - notionals `50m, 100m, 250m, 500m, 1B VND`
  - ADV participation caps `0.0%, 0.5%, 1.0%, 2.0%`
  - round-trip costs `0.30%, 0.50%`
- Corrected result:
  - **uncapped** scenarios are very strong
  - at `0.30%` RT and no cap, `k5_r5_eq` now reaches `+769.49%` total and `+346.29%` relative vs VNINDEX
  - at `0.50%` RT and no cap, all three candidates remain positive benchmark-relative
  - but **every capped scenario still fails**
- Critical deployability finding:
  - with any positive ADV cap in the tested grid, positive relative return count = `0`
  - best relative return by cap:
    - `0.0%`: `+346.29%`
    - `0.5%`: `-47.52%`
    - `1.0%`: `-46.36%`
    - `2.0%`: `-43.24%`
  - minimum average cash weight by cap:
    - `0.5%`: `99.40%`
    - `1.0%`: `98.81%`
    - `2.0%`: `97.74%`
- Implication:
  - the corrected engine strengthens the uncapped economics
  - it does **not** rescue deployability under explicit participation caps

**H140 - Retail Capacity-Aware Validation**
- Tested the actual retail-sized long-only question on the honest `2019-2025` holdout:
  - notionals `20m, 50m, 100m, 200m VND`
  - ADV caps `2%, 5%, 10%`
  - ADV20 floors `250m, 500m, 1B, 2B, 5B VND`
  - round-trip costs `0.30%, 0.50%`
  - candidate menu = the corrected H138 fixed rules
- Result: **no retail-viable scenario**
  - viability gate = `relative_total_return > 0`, `avg_cash_weight < 25%`, `positive_years >= 5/7`
  - count meeting that gate: `0`
  - best scenario:
    - `k5_r10_eq`
    - `20m` notional
    - `2%` ADV cap
    - `1B` ADV20 floor
    - `0.30%` RT cost
    - `+12.00%` total, but `-42.51%` relative, `87.13%` average cash, only `2/7` positive years
- Implication:
  - even retail-sized long-only deployability still collapses once actual liquidity rules are imposed
  - the next move is **not** synthetic hedging or shorting
  - the old “not RL yet” reading is now superseded by the Session 53 current-account prioritization decision

**H141 - Capacity-Aware Construction Sweep**
- Designed to search a tiny long-only menu only inside H140-viable liquidity regions.
- Actual result:
  - H140 produced `0` viable liquidity settings
  - H141 therefore stopped immediately and wrote a formal empty-result summary
- Implication:
  - there is no honest long-only retail region to optimize inside at the moment

**H142 - Live Candidate Blotter (diagnostic only)**
- Implemented the daily blotter exporter for future live/paper-trade validation.
- Because H141 had no winner, the script was run manually on the top H140 scenario only as a diagnostic:
  - `top_k=5`, rebalance every `10` days, equal weight
  - `20m` notional, `2%` ADV cap, `1B` ADV20 floor, `0.30%` RT
- Latest diagnostic snapshot (`2025-12-31` execution):
  - held only `SHB`
  - target notional about `19.70m VND`
  - target usage about `1.87%` of ADV20
  - cash still `12.06%`
- Implication:
  - the tooling is ready
  - the long-only candidate itself is not strong enough to justify live promotion

**H143 - Liquidity-Aware Scoring**
- Tested soft tradability-aware score variants on the honest `2019-2025` holdout:
  - `liq_base`
  - `liq_x_adv_rank`
  - `liq_x_tradability_rank`
  - `liq_blend_70_30`
  - `liq_blend_50_50`
  - `liq_log_adv`
- Same retail grid as H140:
  - notionals `20m, 50m, 100m VND`
  - ADV caps `2%, 5%, 10%`
  - ADV20 floors `250m, 500m, 1B VND`
  - `0.30%` round-trip cost
- Result: **no retail-viable scenario**
  - best scenario:
    - `liq_blend_50_50`
    - `k3_r5_eq`
    - `20m` notional
    - `10%` ADV cap
    - `250m` ADV20 floor
    - `+32.46%` total
    - `-32.01%` relative vs VNINDEX
    - `25.11%` average cash
    - `4/7` positive years
- Implication:
  - soft tradability-aware ranking improves the absolute curve materially versus H140
  - but score engineering alone still does not create a deployable retail region

**H144 - Entry Slicing Simulation**
- Tested staged long-only accumulation on the best H143 variants plus `liq_base`:
  - variants = `liq_base`, `liq_blend_50_50`, `liq_x_tradability_rank`
  - construction fixed to `k5_r5_eq`
  - entry slices `= 1, 2, 3, 5` days
  - sliced runs interpret ADV cap as a **daily buy limit**, not an overall position cap
- Result: **no retail-viable scenario**
  - best scenario:
    - `liq_x_tradability_rank`
    - unsliced baseline (`entry_slice_days = 1`)
    - `20m` notional
    - `5%` ADV cap
    - `250m` ADV20 floor
    - `+28.57%` total
    - `-34.01%` relative
    - `25.79%` average cash
    - `4/7` positive years
  - sliced versions slightly reduced cash drag (`25.18%` vs `25.79%`) but did **not** improve benchmark-relative economics
- Implication:
  - multi-day entry planning is now modeled realistically
  - execution mechanics help modestly, but not enough to rescue deployability

**H145 - Volume-Confirmed Entry Filter**
- Tested entry gates on the strongest H143 score variant (`liq_blend_50_50`):
  - `none`
  - `adv20_125`
  - `adv20_150`
  - `adv5_150`
  - `adv20_125_clv50`
- Same retail grid as H143.
- Result: **no retail-viable scenario**, but this is the closest any retail branch has come so far
  - best scenario:
    - gate = `adv20_125_clv50`
    - `k3_r5_eq` or `k5_r5_eq`
    - `20m` notional
    - `5%` ADV cap
    - `1B` ADV20 floor
    - `+93.88%` total
    - `-0.49%` relative vs VNINDEX
    - `33.52%` average cash
    - `4/7` positive years
- Implication:
  - “only enter when liquidity is opening” is the strongest friction lever tested so far
  - the book is still not deployable by the current gate, but it is now near benchmark-flat instead of deeply negative

**H146 - Variable-Breadth Portfolio**
- Tested variable breadth on the strongest H145 combination:
  - score variant = `liq_blend_50_50`
  - entry gate = `adv20_125_clv50`
  - `max_k = 3, 5`
  - score gates `= none, 0.55, 0.60`
  - minimum deployable weight `= 10%, 15%, 20%`
  - thin-name cap `= off or 2 names`
- Result: **no retail-viable scenario**
  - best scenario is effectively the same as the H145 near-miss:
    - `+93.88%` total
    - `-0.49%` relative
    - `33.52%` average cash
    - `4/7` positive years
    - average holdings only `0.74`
- Implication:
  - fixed `top_k` is **not** the main remaining bottleneck once the stronger liquidity-opening gate is applied
  - the next honest move is not another broad construction sweep; it is either:
    - a very local refinement around the H145 near-miss, or
    - a new long-only alpha search conditioned on tradability / liquidity-opening states

**H147 - Liquidity-State Opportunity Audit**
- Audited the H145 near-miss directly around:
  - score variant `liq_blend_50_50`
  - construction `k3_r5_eq`
  - local gate grid on `tv_to_adv20` and `clv`
  - `20m`, `5%` ADV cap, `0.30%` RT
- Best audited state:
  - gate = `adv20_125_clv45` or `adv20_125_clv50`
  - `1B` ADV20 floor
  - same economics as the H145 near-miss:
    - `+93.88%` total
    - `-0.49%` relative vs VNINDEX
    - `33.52%` average cash
    - `4/7` positive years
- Critical audit finding:
  - zero-candidate days are extremely common in the raw state count (`~97%` of dates)
  - `2019` and `2020` are fully in cash in the best scenario
  - the near-miss is coming from a **very sparse opportunity state**, not from an obviously bad ranking inside a rich state
- Implication:
  - local threshold tuning was worth testing once
  - but the bottleneck is now clearly opportunity density, not just “wrong threshold”

**H148 - Local Liquidity-Gate Refinement**
- Swept only the H145 neighborhood:
  - score variant fixed at `liq_blend_50_50`
  - candidate menu fixed at `k3_r5_eq`, `k5_r5_eq`, `k5_r10_eq`
  - `tv_to_adv20 >= 1.05, 1.10, 1.15, 1.20, 1.25`
  - `clv >= none, 0.45, 0.50, 0.55`
  - ADV20 floor `= 500m, 750m, 1B, 1.5B`
  - notionals `= 20m, 50m`
  - ADV caps `= 5%, 10%`
- Result: **no retail-viable scenario**
  - the best scenario is exactly the old H145 near-miss:
    - `adv20_125_clv45` or `adv20_125_clv50`
    - `k3_r5_eq`
    - `20m`
    - `5%` ADV cap
    - `1B` floor
    - `+93.88%` total
    - `-0.49%` relative
    - `33.52%` cash
    - `4/7` positive years
- Implication:
  - the “just tweak the gate a little more” branch is exhausted
  - there is no justification for another local threshold sweep unless new alpha enters the system

**H149 - Soft Activation Score**
- Replaced the hard H145-style entry gate with soft activation variants built on top of `liq_blend_50_50`:
  - `soft_85_15`
  - `soft_75_25`
  - `soft_65_35`
  - `soft_mul`
- Tested only the tight menu:
  - `k3_r5_eq`, `k5_r5_eq`
  - notionals `20m, 50m`
  - ADV caps `5%, 10%`
  - ADV20 floors `500m, 750m, 1B`
- Result: **hard fail**
  - best scenario:
    - `soft_85_15`
    - `k3_r5_eq`
    - `50m`
    - `5%` ADV cap
    - `500m` floor
    - `-0.57%` total
    - `-48.97%` relative
    - `36.65%` average cash
    - `3/7` positive years
- Implication:
  - the H145 gate is not failing because it is “too binary”
  - softening the gate increases turnover and degrades the economics materially

**H150 - Conditional Alpha Decomposition**
- Tested each signal in the RL matrix under four states:
  - unrestricted
  - `tv_to_adv20 >= 1.10`
  - `tv_to_adv20 >= 1.10 and clv >= 0.45`
  - `tv_to_adv20 >= 1.25 and clv >= 0.50`
- Best unrestricted signal:
  - `s1_proba`
  - avg daily IC `+0.1491`
  - `11/11` positive years
- Best liquidity-opening state:
  - `s1_proba` under `tv110`
  - avg daily IC `+0.1510`
  - `11/11` positive years
- Strongest conditional uplifts vs unrestricted:
  - `c7_ceiling_count_5d` under `tv125_clv50`: avg daily IC `+0.0592`
  - `c12_gap_absorb_3` under `tv125_clv50`: avg daily IC `+0.0496`
  - `c13_compress_blowoff_2` under `tv110`: avg daily IC `+0.0464`
  - `c10_illiq_level_rank` under `tv110`: avg daily IC `+0.0343`
  - `c8_vol_zscore_5d` also improves materially in liquidity-opening states
- Implication:
  - the library does have a **tradability-conditioned sub-core**
  - but current construction is still not enough to monetize it under the retail gate
  - the next experiment should not be another generic construction tweak; it should be a **narrow tradability-conditioned composite** built from the surviving signals

**Hard rule**
- this repo is permanently long-only
- no synthetic hedges
- no stock shorting assumptions
- no research branches that cannot realistically make money as long-only in Vietnam

**Next frontier**
- narrow tradability-conditioned composite from the surviving H150 signals:
  - base = `s1_proba`
  - strongest conditioned uplifts = `c7`, `c12`, `c13`, `c10`, with `c8` as a secondary candidate
- new long-only alpha search should also be explicitly conditioned on liquidity-opening / tradability states
- do **not** spend another session on generic construction sweeps or softer gating
- long-only execution and blotter validation only after a candidate becomes benchmark-positive under the retail gate
- keep RL deferred until a deterministic long-only deployable baseline exists

**Immediate operational next steps around the live paper trade**
1. Record the next market-session outcome against the current paper-trade book: `ANV`, `PTB`, `PTL`, `VSI`, cash `19.57%`
2. Persist the ad hoc live-assembly workflow into a real repo script if repeated live paper trades are expected
3. Restore canonical full-history continuity in root `data/stock/`, especially `VNINDEX`, so the official live scorer works again without the media-output fallback
4. Rerun `analysis/h75_2026_holdout.py` against the restored canonical benchmark and refresh the official live `S1` artifact
5. Rebuild or publish the latest stock-derived `full_library` features in a repeatable way before the next rebalance date

### Current production system

**H54 - Full HOSE Rank Portfolio**
- +25.52% avg edge, Sharpe 9.17, 11/11 positive years (2015-2025)
- IC +0.1515 vs +0.088 on the older 52-stock universe
- No external VIX filter
- 2026 live validation through 2026-03-11: IC +0.1323, gross/trade +0.155%, net/trade -0.145% @0.30% RT
- Run:
  `conda run -n stocks python analysis/h40_rank_portfolio.py --probas data/features/xs_barrier_all_probas_hose_full.parquet --no-vix-filter`

### Important reference systems

**H52 - Honest benchmark**
- +11.64% avg edge, Sharpe 1.83, 8/9 positive years
- Run:
  `conda run -n stocks python analysis/h52_nested_wf_params.py`

**H87(alpha=0.7) - Sharpe-optimized near-champion**
- +25.03% avg edge, Sharpe 10.25, 11/11 positive years
- Built from H77 + H86 classifier probas blended with regressor scores
- Saved artifact: `data/features/xs_blend_h87_alpha0.7.parquet`
- Executable economics are only marginally different from H54 on daily H=1
- Higher-cost fallback: weekly H=5 becomes better than H54 daily above roughly `0.49%` RT

**H43 - Historical previous champion**
- +13.75% avg edge, Sharpe 4.58, 11/11 positive years
- Contamination documented

### What Session 26 established

- H87a (H77 + H86 classifier) is neutral: +24.75% edge, Sharpe 9.42, IC +0.1502.
- H87(alpha=0.5) narrowly misses the Session 26 target: +24.94% edge, Sharpe 9.94.
- H87(alpha=0.7) clears the target: +25.03% edge, Sharpe 10.25.
- H78 E=1 overturns the old inference: daily rebalancing still wins in executable T+1-open terms.
- H63 no-VIX cost stress gives H54 an exact break-even near 0.54% RT; practical safe zone is `<= 0.50%` RT.
- H87(alpha=0.7) now exists as a saved tradable artifact, but its daily executable economics are almost identical to H54.
- H75 current no-VIX live validation keeps strong IC in 2026 (`+0.1323`) and positive executable gross returns, but net is still slightly negative so far at `0.30%` RT.
- H88 closes the deployment fallback rule: below ~`0.49%` RT use H54 daily; above that use H87 weekly.
- H54 remains champion on raw edge, but H87(alpha=0.7) is now the best "Sharpe > 10 and edge > 25" reference point.

---

## Session History

| Session | Date | Key Result | Best System After |
|---------|------|-----------|-------------------|
| 01 | 2026-03-16 | Framework built; baselines run | None (OHLCV = 0 edge) |
| 02 | 2026-03-16 | OHLCV exhaustion confirmed (F2) | None |
| 03 | 2026-03-16 | Relative momentum discovered -> E8 +0.73% (F4, F6) | E8 +0.73% |
| 04 | 2026-03-16 | XS model: 53-55% acc all 11 years (F7); single-stock feature space exhausted | XS model |
| 05 | 2026-03-16 | 9 new signal directions all failed; ensemble infrastructure built; X2 +3.87% (F10a, F10b) | X2 +3.87% |
| 06 | 2026-03-16 | Ensemble breakthrough X3 +10.28%; VIX filter X8 +8.76% (F11, F13) | X8 +8.76% |
| 07 | 2026-03-16 | Triple barrier E32 fixes 2021; X8-E32 +13.96% (F14); 10d horizon failed (F15) | X8-E32 +13.96% |
| 08 | 2026-03-16 | Barrier XS near-fixes 2022; H22 +15.13% Sharpe 1.52 (F16, F17) | H22 +15.13% |
| 09 | 2026-03-17 | Methodology audit; H23 multi-stock +21.94% 11/11 (F18-F20) | H23 +21.94%* |
| 10 | 2026-03-17 | Macro regime filters; H26 FPT +23.97% Sharpe 2.04; H27 portfolio Sharpe 2.80 (F21, F22) | H26 +23.97% |
| 11 | 2026-03-17 | New data; TAIEX+KOSPI H23 Sharpe 3.72 (F23, F24) | H23+TAIEX +20.94% |
| 12 | 2026-03-17 | Model arch sweep; H38 VIX[15,30] +18.71% FPT champion (F25) | H38 +18.71% (FPT) |
| 13 | 2026-03-17 | Rank portfolio H43: IC=+0.088, 11/11 years, Sharpe 4.58 (F26) | H43 +13.75% |
| 14 | 2026-03-17 | H44 portfolio refinements: daily rebalancing optimal | H43 unchanged |
| 15 | 2026-03-17 | H45 dollar: +0.409%/trade, 9.1%/yr net; turnover reduction kills strategy (F27-F29) | H43 confirmed |
| 16 | 2026-03-18 | Contamination eliminated: H52 honest +11.64% Sharpe 1.83; H50a VIX-clean +11.85% (F30-F31) | H43 (pub: H52) |
| 17 | 2026-03-18 | Universe expansion 52->393 stocks: H54 +25.52% Sharpe 9.17 (F32) | H54 +25.52% |
| 18 | 2026-03-18 | H54 validated: H55 +1.037%/trade liquid, H56 honest Sharpe 7.35, H57 no survivorship bias (F33-F35) | H54 (confirmed) |
| 19-23 | 2026-03-18/19 | Kill tests, execution audit, 2026 holdout (H75): IC=+0.1323 PASS, gross +0.258%, net -0.042% @0.30%RT | H54 (cost-limited) |
| 24 | 2026-03-19 | H84 FAIL, H78 NEUTRAL, H85 FAIL (F36-F38) | H54 unchanged |
| 25 | 2026-03-19 | H77-H86 all NEUTRAL/FAIL; 1% barrier optimal (F39); H54 remains champion | H54 unchanged |
| 26 | 2026-03-19 | H87 alpha=0.7 operationalized; H75 live IC +0.1323; H54/H87 crossover ~0.49% RT | H54 unchanged |
| 27 | 2026-03-24 | H54 parked (deployment gap); next-signal search begins | H54 PARKED |
| 28 | 2026-03-24 | H90 PASS (vol IC+0.0084); H91 MIXED (1d Sharpe 11.63); H93 PASS (Sharpe 15.08, std 1.60%); H94 NEUTRAL | H93 = best RL signal |
| 29 | 2026-03-24 | H89 FAIL (news too sparse, IC −0.0044); H92 FAIL (sector sub-models < pooled); H95 DEFERRED (no hist foreign flow) | H93 unchanged |
| 30 | 2026-03-25 | H96 FAIL (rolling news IC −0.0008); H97 BLOCKED (API 403); H99 FAIL (body extraction IC −0.0128); news path exhausted | H93 unchanged |
| 31 | 2026-03-26 | H97 FAIL (insider IC −0.0007, Sharpe 15.08→10.77); C2 candidate added; CafeF GDCoDong API discovered | H93 unchanged |
| 32 | 2026-03-26 | C2 standalone tested: IC +0.0256 (9/11 years), but Top-5 edge +0.09% and only 5/11 positive years; not tradeable standalone | H93 unchanged |
| 33 | 2026-03-26 | H98 infra implemented (LLM extractor + builder + WF flags); smoke test shows local Ollama timeout in this runtime, full H98 run pending | H93 unchanged |
| 34 | 2026-03-26 | **H98 PARKED**; H100/H101/H102 dense sweeps run — H101 PASS (Sharpe 15.34), H100/H102 FAIL (variance blow-up) | H93/H101 tie-class |
| 35 | 2026-03-26 | Standalone gate enforced; H103 return skewness FAIL; dense standalone checks logged (H100 standalone +, H101 context weak, H103 standalone weak) | H93/H101 tie-class |
| 36 | 2026-03-26 | H104 earnings calendar dense features built; H104 and H105 both FAIL (Sharpe collapse), standalone IC weak | H93/H101 tie-class |
| 37 | 2026-03-27 | H106 C3 regime-conditional IC: dispersion spread ≤2%, p=0.124 — C3 REJECTED; dense search closed | H93 only |
| 38 | 2026-03-28 | H107 FAIL (overnight decomp); H108 PASS (C5 xs_ins_relative_size IC +0.037); H109 FAIL (52-ticker); H110 FAIL (VNM ETF cross-sectional); H111 PARTIAL (breadth PASS, rotation FAIL) | H93 + C4 + C5 |
| 39 | 2026-03-28 | H112 PASS (C6 contrarian_intra); H113 PENDING; H114 FAIL (VN30); H115 PASS (C7 ceiling); H116 PASS (C8 vol_zscore); H117 PASS (C9 reversal); H118-H120 FAIL; RL matrix built | H93 + C4-C9 |
| 40 | 2026-03-28 | H121 PASS (C10 illiq_level IC +0.021, corr +0.008); H113 fetch failed at 302/394; H122 written not run | H93 + C4-C10 |
| 41 | 2026-03-28 | H122 FAIL (spread proxy); C10 added to RL matrix; C10 pairwise corr vs C4-C9 all low | H93 + C4-C10 |
| 42 | 2026-03-28 | H123 PASS (C11 continuation); H124 standalone PASS but rejected on independence; C11 added to RL matrix, low-beta signal excluded | H93 + C4-C11 |
| 43 | 2026-03-28 | H125/H131/H132 FAIL; H127 standalone PASS but redundant with C8; H128 anti-predictive; H130 PASS (C12 gap absorption) | H93 + C4-C12 |
| 44 | 2026-03-28 | H133 PASS (C13 compression blow-off); H134 PASS (C14 residual close-strength); H126 standalone PASS but redundant with C11 | H93 + C4-C14 |
| 45 | 2026-03-28 | H135 initial realistic portfolio baseline logged as FAIL; later corrected in Session 46 after signal-scale bug fix | H93 + C4-C14 |
| 46 | 2026-03-28 | H135 corrected: full_library baseline turns positive; H136 sweep finds top-5 equal-weight, 5d cadence, +1105.71% total and +25.66% annualized | H93 + C4-C14 |
| 47 | 2026-03-28 | H137 nested walk-forward selection: +21.38% total OOS but -42.46% vs VNINDEX; simple config selection overfits and does not validate ML construction yet | H93 + C4-C14 |
| 48 | 2026-03-28 | H138 fixed simple rules beat VNINDEX on holdout; H139 shows uncapped economics survive but any tested ADV cap collapses deployability | H93 + C4-C14 |
| 49 | 2026-03-28 | Signal-date liquidity fix applied; corrected H138/H139 reruns strengthen uncapped long-only economics, but H140 finds zero retail-viable scenarios and H141 stops | H93 + C4-C14 |
| 50 | 2026-03-28 | H143-H146: liquidity-aware scoring, entry slicing, volume-confirmed gating, and variable breadth all fail the retail gate; H145 is the closest near-miss | H93 + C4-C14 |
| 51 | 2026-03-28 | H147-H150: H145 near-miss is sparse-state driven; local refinement and soft activation fail; H150 identifies a tradability-conditioned sub-core | H93 + C4-C14 |
| 52 | 2026-03-28 | Official live pipeline blocked by truncated benchmark history, but an honest ad hoc live full_library paper-trade state was recovered for the 2026-03-27 close | H93 + C4-C14 |
| 53 | 2026-03-29 | ADV / capacity explicitly parked for the current-account branch; RL becomes the active next research branch with deterministic benchmark-first gating | H93 + C4-C14 |
| 54 | 2026-03-29 | H153 same-universe deterministic comparator implemented and run; conditioned sub-core best in the RL universe but still below equal-weight benchmark; H154 smoke passed | H93 + C4-C14 |
| 55 | 2026-03-29 | H154 first real pilot ladder completed: `S1`-only RL beats deterministic comparator and equal-weight benchmark on seed 1208; conditioned sub-core is mixed; full matrix fails cleanly | H93 + C4-C14 |
| 56 | 2026-03-29 | H155 multi-seed robustness shows `S1`-only RL is high-variance: 2 strong wins, 2 failures; RL remains exploratory and the active branch returns to `H151/H152` | H93 + C4-C14 |
| 57 | 2026-03-29 | H157-H162 activation-alpha wave completed: binary on/off activation does not beat always-on `full_library + k5_r5_eq`; selection alpha vs activation alpha split is now explicit; active branch returns to `H151/H152` | H93 + C4-C14 |
| 66 | 2026-03-29 | H151/H152 first pass under locked `2015-2025` protocol: no narrow existing-signal composite beats `full_library`; four new tradable-state atoms pass standalone gates but none are promoted selectors | H93 + C4-C14 |
| 67 | 2026-03-29 | H196-H199: the H152 additive path closes; second-wave search promotes `h199_sector_laggard_gap_absorb` as the one worth-carrying atom | H93 + C4-C14 |
| 68 | 2026-03-29 | H200-H202: the H199 atom survives additive and state-scoped selector gates but fails frozen sticky-activation compatibility; keep it offline-only | H93 + C4-C14 |
| 69 | 2026-03-29 | H203-H205/H204: pairwise selector extension fails the next sequential gate and fresh H204 families show no selector relevance; selector-discovery ladder is exhausted | H93 + C4-C14 |
| 70 | 2026-03-29 | H207-H213 exit-alpha ladder: rank-decay and strength-exhaustion exits win offline, but the promoted exit winner fails frozen sticky compatibility; live branch remains unchanged | H93 + C4-C14 |
| 71 | 2026-03-29 | H214-H217 genuinely new exit-family follow-through: thesis inconsistency, failed follow-through, and time-under-water do not beat the H211 winner; new-family sticky compatibility is skipped | H93 + C4-C14 |
| 72 | 2026-03-29 | H218-H220 continuation / hold-vs-exit hazard branch: no dev-trained continuation model clears the predictive gate, so exit bands and sticky compatibility are skipped | H93 + C4-C14 |
| 73 | 2026-03-29 | H221-H229: event surface builds but fails predictive screening; intraday / order-book follow-through fails locally; exit-side research is blocked by missing data, not more rule ideas | H93 + C4-C14 |
| 74 | 2026-03-29 | Timing-data acquisition branch formalized: next honest timing work is source acquisition first, with explicit viability gates before modeling can reopen | H93 + C4-C14 |
| 75 | 2026-03-30 | H238-H244 entry-alpha ladder: sparse breadth is real offline evidence, but no rule/model/soft-prior/live-compatibility variant is promotable | H93 + C4-C14 |
| 76 | 2026-03-30 | H245 entry-alpha contract audit: branch looks historically like a small-book `top1` contract, but no audited `top_k` survives the honest forward gate; branch remains offline-only | H93 + C4-C14 |
| 77 | 2026-03-30 | H246 small-book overlay follow-through: top1 confirmation overlays are a no-op and top2 soft-consensus overlays overfit validation; branch remains offline-only | H93 + C4-C14 |
| 78 | 2026-03-31 | H247 label-sharpen audit fails; sharpened labels do not rescue the small-book branch, and one unsharpened `top2` price-state side result remains offline-only | H93 + C4-C14 |
| 79 | 2026-03-31 | H248 catalyst-concentrated small-book follow-through fails; sparse catalyst concentration does not rescue the branch, and Family A closes on the current data stack | H93 + C4-C14 |
| 80 | 2026-03-31 | H249 selector-relative activation audit fails; rebuilding sticky activation from the H201 winner's own `rel2` history does not rescue compatibility | H93 + C4-C14 |
| 81 | 2026-03-31 | H250 contradiction-state router follow-through is mixed: one real routed selector survives as offline evidence, but it does not dislodge `H201` | H93 + C4-C14 |
| 82 | 2026-03-31 | H251 event-surface trust-modulator follow-through passes narrowly: report-window and recent-filing regimes improve `H201` offline and justify a light trust-audit follow-through | H93 + C4-C14 |
| 83 | 2026-03-31 | H252 trust audit passes only as a hard report-window gate around `H201`; soft trust schedules do not survive cleanly, so the next narrow follow-through is frozen compatibility, not broader event search | H93 + C4-C14 |
| 84 | 2026-03-31 | H253 frozen compatibility audit is mixed: the hard report-window gate strengthens `H201` on validation but fails badly versus frozen sticky in `2025`, so the branch remains offline-only and the next synthesis follow-through is a hybrid switchboard audit | H93 + C4-C14 |
| 85 | 2026-03-31 | H254 report-window selector switchboard fails: the exact hybrid improves naked `H201` confirmation behavior but still loses to frozen sticky in both validation and confirmation, so the switchboard branch closes and the next synthesis follow-through becomes the contradiction expert | H93 + C4-C14 |
| 86 | 2026-03-31 | H255 report-window contradiction expert is mixed: the nested contradiction overlay softens confirmation inside the gate but validation collapses far too hard to promote, so the branch stays synthesis-only and the next follow-through becomes dynamic breadth | H93 + C4-C14 |
| 87 | 2026-03-31 | H256 event-driven dynamic breadth is mixed: smaller breadth helps validation inside the report-window gate but fails catastrophically in confirmation, so the current daily-data synthesis queue closes and effort should shift back to acquisition-first timing work or live monitoring | H93 + C4-C14 |
| 88 | 2026-03-31 | H231 intraday normalization pilot is mixed: the VCI bridge works and reduced-shape intraday structure looks viable on a representative subset, but full-session completeness is still too weak to close H232 while the fetch remains partial | H93 + C4-C14 |
| 89 | 2026-03-31 | H234 richer event-source audit passes: the local CafeF company-news archive is a real richer company-event source candidate with exact publish timestamps and broad company-specific families, but the conservative seed stays too sparse to skip H235 | H93 + C4-C14 |
| 90 | 2026-03-31 | H235 event-source sample audit is mixed: strict title-alias expansion is high-precision and highly novel versus event surface v1, but held-row coverage only rises to 2.30%, so H236 stays closed and active effort returns to intraday/H232 or live monitoring | H93 + C4-C14 |
| 91 | 2026-03-31 | H257 event-density router fails: alias-expanded event density never covers enough held rows to gate `H201`, so the richer event source stays parked and non-live effort returns to intraday or live monitoring | H93 + C4-C14 |
| 92 | 2026-04-03 | H258-H259 reduced-shape intraday restart: the current CafeF `1H` surface passes as a reduced-shape research contract, but the first reduced-shape exit predictive screen fails, so the panel stays offline-only and `H260/H261` stay closed | H93 + C4-C14 |
| 93 | 2026-04-03 | H262-H263 family-aware intraday continuation follow-through passes: reduced-shape contradiction survives only inside `breakout_followthrough`, and the pooled family-aware router beats the global H259 baseline on the observed subset, so the next honest step is deterministic family-aware integration, not another generic intraday screen | H93 + C4-C14 |

\* Contaminated: stock selection was post-hoc.

---

## XS Momentum Signal Status: PARKED (as of Session 27, 2026-03-24)

The cross-sectional momentum signal (H54) is **parked — not production-ready**.

**What is confirmed:**
- Ranking skill intact: WF IC = +0.152, 2026 live IC = +0.134
- Gross returns positive in backtest and 2026 holdout
- 4/4 robustness tests pass

**What is NOT closed (deployment gap):**
1. Real fills at T+1 open unverified (partial fills, queue position, mid/small-cap slippage)
2. Net P&L negative at 0.30% RT in 2026 partial year — not yet confirmed positive
3. No execution infrastructure for daily rebalancing
4. Signal degrades to ~half IC in top-50 liquid stocks

**Fallback rule (for reference, if/when deployed):**
- RT cost < 0.49%: use H54 daily
- RT cost > 0.49%: use H87(alpha=0.7) weekly

**Conditions to unpark:** real fill data + net P&L confirmed positive over full year + execution infra.

See `notes/session_27_log.md` and `notes/findings-031-060.md` (F53) for full rationale.

---

## Session 28 Results (2026-03-24)

- **H90 PASS:** Volume features → IC +0.1599, Sharpe 9.48. `xs_barrier_vol_hose_full.parquet`
- **H91 MIXED:** 1-day target → IC +0.1395, Sharpe 11.63. Lower variance is the key finding. `xs_barrier_1d_hose_full.parquet`
- **H93 PASS:** Volume + 1-day combined → IC +0.1491, edge std **1.60%**, Sharpe **15.08**. **Best RL signal.** `xs_barrier_vol_1d_hose_full.parquet`
- **H94 NEUTRAL:** Sector-relative features on H93 → Sharpe 14.21 (regression). H93 stands.

See `notes/session_28_log.md` and `notes/findings-031-060.md` (F54–F57).

---

## Session 31 Results (2026-03-26)

- **H97 FAIL:** Insider deals → IC +0.1484 (−0.0007 vs H93), Sharpe **10.77** (−4.31 vs H93). 3.57% sparse, same XGBoost failure as news (F66).
- **Standalone IC:** insider_net_plan_5d avg +0.025, 9/11 years positive. Near-zero corr with S1 (−0.027). Added as **C2 candidate**.
- **Data source:** CafeF GDCoDong API discovered (`cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`) — 394/394 tickers, 2010–2026, free/no auth.
- **KBS/VCI vnstock:** KBS endpoint returns `[]` (unpopulated); VCI wrapper unimplemented.

Infrastructure built: `data_tools/fetch_insider_deals.py`, `data_tools/build_insider_features.py`, `--use-insider` flag in WF.

See `notes/session_31_log.md` and `notes/findings-061-090.md` (F66).

**H93 remains best RL signal (Sharpe 15.08, IC +0.1491, edge std 1.60%).**

---

## Session 32 Results (2026-03-26)

- **C2 standalone test complete:** pure event-day ranking by `insider_net_plan_5d`.
- **Signal quality unchanged:** standalone IC **+0.0256**, 9/11 years positive, 3.57% row coverage.
- **Portfolio quality weak:** Top-1 **−0.304%**, Top-3 **+0.049%**, Top-5 **+0.090%** (5d relative edge).
- **Stability weak:** Top-5 positive in **5/11** years, Sharpe proxy **0.51**.
- **Verdict:** C2 remains RL-candidate context signal, but **not a standalone tradable strategy**.

Artifacts:
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_standalone_signal.json`
- `artifacts/run_summaries/20260326_150012_c2_insider_standalone_details.json`

See `notes/session_32_log.md`.

---

## Session 30 Results (2026-03-25)

- **H96 FAIL:** Rolling 5d/30d news → IC +0.1483 (−0.0008 vs H93). 5.1% coverage still too sparse (F63).
- **H97 BLOCKED:** vnstock API returns 403 Forbidden in cloud environment. Need local access.
- **H99 FAIL:** Body-text extraction → IC +0.1363 (−0.0128 vs H93). 5.2× more obs but noisier (F64).
- **News path exhausted** (F65): keyword lexicon insufficient. Only H98 (LLM) remains untested.

Infrastructure built: `data_tools/build_rolling_news_sentiment.py`, `--use-rolling-news` and `--news-path` flags in WF.

See `notes/session_30_log.md` for full details.

---

## Session 29 Results (2026-03-24)

- **H89 FAIL:** Keyword news sentiment IC 0.1361 vs H93 0.1405 (−0.0044). Signal too sparse (0.8% coverage). `xs_news_sentiment_daily.parquet` built; need rolling/LLM approach to fix.
- **H92 FAIL:** Banking (20 tickers) IC 0.1077 vs pooled 0.1238 (−0.0161). Real estate (57) IC 0.1308 vs pooled 0.1393 (−0.0085). Pooled model wins — more data outweighs sector specificity.
- **H95 DEFERRED:** Historical daily foreign flow not available via vnstock (F59).
- **Infrastructure built:** `data_tools/fetch_sector_classification.py`, `data_tools/extract_news_sentiment.py`, `--sector` filter in WF (diacritic-normalized), `data/features/sector_classification.parquet` (398 tickers, ICB classification).

See `notes/session_29_log.md` and `notes/findings-061-090.md` (F58–F61).

**H93 remains best RL signal (Sharpe 15.08, IC +0.1491, edge std 1.60%).**

---

## Session 33 Results (2026-03-26)

- **Implemented:** `data_tools/extract_llm_news_features.py` (LLM extraction to `data/llm_cache/`).
- **Implemented:** `data_tools/build_llm_news_features.py` (outputs ticker-day + dense market-daily parquets).
- **WF integrated:** new flags `--use-llm-news`, `--use-llm-market` in `cross_sectional_wf.py`.
- **Smoke verification:** 3-day extraction run writes cache files but all batches timed out (local Ollama unavailable in this environment).
- **Build verification:** both H98 feature parquets built; dense market feature file has zero NaNs.
- **WF verification:** both LLM feature blocks merge and train-path works.

See `notes/session_33_log.md`.

---

## Session 34 Results (2026-03-26)

- **H98 LLM path: PARKED explicitly.** Infrastructure exists, but extraction is too slow/unstable operationally in current runtime.
- **H100 (open/close asymmetry): MIXED/FAIL for RL quality.**
  - IC +0.1541 (+0.005 vs H93), edge +25.36% (+1.21%)
  - Sharpe **11.63** (−3.45 vs H93), std 2.18% (+0.58%)
- **H101 (dispersion regime): PASS (risk-adjusted).**
  - IC +0.1474 (−0.0017 vs H93), edge +23.83% (−0.32%)
  - Sharpe **15.34** (+0.26 vs H93), std 1.55% (−0.05%)
- **H102 (H100+H101): FAIL.**
  - IC +0.1531 (+0.004), edge +25.23% (+1.08%)
  - Sharpe **9.96** (−5.12), std 2.53% (+0.93%)

See `notes/session_34_log.md`.

---

## Session 35 Results (2026-03-26)

- **H103 implemented and tested:** dense return-skewness branch.
- **H103 result:** IC +0.1489 (~flat), edge +24.19% (~flat), Sharpe **10.63** (large drop) => FAIL.
- **Standalone gate added explicitly** via `analysis/standalone_dense_signal_checks.py`.
- **Standalone summary:**
  - H100 proxy (`oc_asym_5d`): IC +0.0273, 10/11 years positive, corr with S1 +0.147.
  - H101 context (`xs_dispersion_z20` vs S1 top5 edge): Spearman −0.0289, p=0.13 (weak).
  - H103 proxy (`ret_skew_z20`): IC +0.0019, 6/11 years positive, corr with S1 −0.0035 (too weak).

See `notes/session_35_log.md`.

---

## Session 36 Results (2026-03-26)

- **H104 implemented:** dense earnings/reporting calendar features (`xs_earnings_calendar_daily.parquet`).
- **H104 result:** IC +0.1480 (−0.0011), edge +24.14% (~flat), Sharpe **11.80** (−3.28) => FAIL.
- **H105 (H101+earnings) result:** IC +0.1466 (−0.0008 vs H101), Sharpe **11.96** (−3.38 vs H101) => FAIL.
- **Standalone gate:** earnings calendar features show weak standalone IC (~0.001 to 0.006 range) and weak context relation with S1.

See `notes/session_36_log.md`.

---

## Session 38 Results (2026-03-28)

**Signal library now has: S1 (confirmed) + C1 + C2 + C4 + C5 (candidates)**

- **H107 (Overnight gap decomposition): FAIL as hypothesis, but reveals C4.**
  overnight_mom_5d IC ≈ 0; intraday_mom_5d IC = −0.034; oc_asym_5d IC = +0.0225 (11/11 years).
  Signal lives in the contrast, not the components. oc_asym_5d → promoted to **C4 candidate**.

- **H108 (Insider quality): PASS.**
  xs_ins_relative_size_5d (net_plan / VolumeBeforeTransaction) IC = +0.0374, 10/11 years, corr = −0.008.
  +46% over raw C2. Position-size normalization is the key dimension. → **C5 candidate** (supersedes C2).

- **H109 (Earnings quality 52 tickers): FAIL.**
  Best: xs_roe_delta_rank IC = +0.0049 (8/11 years). Universe too small. Re-test at 394 tickers.

- **H110 (VNM ETF foreign demand proxy): FAIL.**
  VNM ETF premium is a market-direction signal (date-level IC +0.132 for VNINDEX) but provides no
  cross-sectional stock differentiation. Foreign affinity beta is too noisy.

- **H111 (Sector rotation): PARTIAL PASS.**
  xs_sector_rotation_signal IC = −0.0379 (intra-sector rank anti-predictive: laggards beat leaders).
  xs_sector_breadth_5d (fraction of sector stocks positive): IC = +0.0143, 8/11 years, corr = −0.004. → PASS.
  Queued: H112 = contrarian intra-sector signal (sector_mom_rank × (1 − intra_sector_rank)).

New artifacts:
- `data/features/xs_insider_quality_features.parquet` — xs_ins_relative_size_5d (C5)
- `data/features/xs_sector_rotation_daily.parquet` — xs_sector_breadth_5d
- `data/features/xs_earnings_quality_daily.parquet` — 52-ticker earnings quality
- `data/features/xs_foreign_demand_daily.parquet` — VNM ETF features (not predictive)

## Historical Snapshot: Session 49

### Signal library status after Session 44
| Signal | IC | Corr w/ S1 | Coverage | Status |
|--------|----|------------|----------|--------|
| S1/H93 | +0.149 | N/A | 100% | CONFIRMED |
| C4 oc_asym_5d | +0.023 | +0.147 | 100% | Candidate |
| C5 ins_relative_size | +0.037 | −0.008 | 3.4% | Candidate |
| C6 contrarian_intra_5d | +0.030 | +0.142 | 100% | Candidate (S39) |
| C7 xs_ceiling_count_5d | +0.012 | +0.064 | 100% | Candidate (S39) |
| C8 xs_vol_zscore_5d | +0.011 | +0.068 | 100% | Candidate (S39) |
| C9 xs_reversal_1d | +0.028 | +0.161 | 100% | Candidate (S39) |
| C10 xs_illiq_level_rank | +0.021 | +0.008 | 100% | **NEW S40** |
| C11 xs_ret_60d_lag_rank | +0.010 | +0.008 | 100% | **NEW S42** |
| C12 xs_gap_absorb_3 | +0.028 | +0.131 | 100% | **NEW S43** |
| C13 xs_compress_blowoff_2 | +0.035 | +0.191 | 100% | **NEW S44** |
| C14 xs_clv_volconf_resid_rank | +0.013 | +0.102 | 100% | **NEW S44** |
| C1 keyword news | +0.043 | +0.009 | 0.8% | Candidate (inconsistent) |

Note: RL signal matrix built at `data/features/xs_rl_signal_matrix.parquet` (S1+C4+C5+C6+C7+C8+C9+C10+C11+C12+C13+C14, 826k rows × 16 cols).

### Session 44 experiment results (2026-03-28)
- **H133 PASS** — compression blow-off reversal survives as a new reversal state
  - `xs_compress_blowoff_2`: IC +0.0351, 10/11 years, corr S1 = +0.191, max candidate corr = +0.154 → **C13 candidate**
  - `xs_compress_blowoff_1` and `xs_compress_blowoff_3` are stronger on IC but fail S1 overlap (`+0.321`, `+0.340`)
- **H134 PASS** — residual close-location survives explicit de-duplication vs C8
  - `xs_clv_volconf_resid_rank`: IC +0.0131, 11/11 years, corr S1 = +0.102, max candidate corr = +0.099 → **C14 candidate**
  - H127's core intuition was partly real; it just needed residualization against C8
- **H126 MIXED** — 90d/120d continuation is real but redundant
  - `xs_ret_90d_lag_rank`: IC +0.0108, 11/11 years, corr C11 = +0.775
  - `xs_ret_120d_lag_rank`: IC +0.0109, 10/11 years, corr C11 = +0.664
  - sector-neutral variants fall below the 0.01 gate
  - Verdict: reject as a restatement of C11
- **C13/C14 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c13_compress_blowoff_2` and `c14_clv_volconf_resid_rank`
  - resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 16 cols)
- **PAIRWISE CHECK** — C13 remains orthogonal to the current promoted set
  - max corr vs existing candidates: +0.154
  - corr vs C12: +0.006
- **PAIRWISE CHECK** — C14 remains orthogonal to the current promoted set
  - max corr vs existing candidates: +0.099
  - corr vs C13: -0.002

### Session 43 experiment results (2026-03-28)
- **H125 FAIL** — residualized beta has no surviving edge
  - `xs_beta_resid_60d_rank`: IC -0.0019
  - `xs_low_beta_resid_60d`: IC +0.0019
- **H127 MIXED** — close-location with volume confirmation passes standalone but is a duplicate of C8
  - `xs_clv_volconf_5d_rank`: IC +0.0149, 11/11 years, corr S1 = +0.105
  - pairwise corr vs C8 = +0.903 → rejected as redundant
  - plain close-location ranks are anti-predictive
- **H128 FAIL** — compression breakout continuation is strongly wrong-way
  - best feature `xs_compress_breakout_2`: IC -0.0351
  - the tested breakout-follow-through thesis is anti-predictive
- **H130 PASS** — confirmed gap absorption adds a new microstructure axis
  - `xs_gap_absorb_1`: IC +0.0117, 11/11 years, corr C4 = +0.298 → passes but weaker
  - `xs_gap_absorb_2`: IC +0.0334, 10/11 years, corr C4 = +0.453 → redundant with C4
  - `xs_gap_absorb_3`: IC +0.0284, 11/11 years, corr S1 = +0.131, corr C4 = +0.202 → **C12 candidate**
- **H131 FAIL** — sector breadth shock has no standalone value
  - best feature `xs_breadth_shock_laggard`: IC -0.0034
- **H132 FAIL** — conditional liquidity release remains below threshold
  - best feature `xs_liq_release_1`: IC +0.0067
- **C12 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c12_gap_absorb_3`
  - resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 14 cols)
- **PAIRWISE CHECK** — C12 remains orthogonal to the current promoted set
  - corr vs C4: +0.202
  - corr vs C5: +0.005
  - corr vs C6: -0.032
  - corr vs C7: +0.037
  - corr vs C8: +0.027
  - corr vs C9: -0.004
  - corr vs C10: -0.146
  - corr vs C11: -0.017

### Session 40-43 experiment results (2026-03-28)
- **H121 PASS** — xs_illiq_level_rank IC +0.021 (10/11 years), corr S1=+0.008 → **C10 candidate**
  - Script: `analysis/h121_amihud_illiquidity_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_113807_h121_amihud_illiquidity_standalone_signal.json`
- **H113 FAIL** — Earnings quality 394T: best IC=+0.006 (xs_eps_yoy_rank), all below 0.01 gate. Path closed.
- **H122 FAIL** — Bid-ask spread (Corwin-Schultz) tested and rejected
  - Script: `analysis/h122_bid_ask_spread_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_120457_h122_bid_ask_spread_standalone_signal.json`
- **H123 PASS** — 60d excess-return rank passed with IC +0.0101 (9/11 years), corr S1=+0.008. The reversal orientation failed, so the promoted signal is medium-term continuation.
  - Script: `analysis/h123_3m_reversal_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_121637_h123_3m_reversal_standalone_signal.json`
  - Promoted to **C11**
- **H124 MIXED** — low-beta orientation passed standalone (IC +0.0131, 7/11 years) but beta regime is redundant with C10.
  - Script: `analysis/h124_beta_regime_standalone.py`
  - Artifact: `artifacts/run_summaries/20260328_121804_h124_beta_regime_standalone_signal.json`
  - Pairwise corr vs C10: +0.5524
  - **Rejected** for RL state
- **C10/C11 MATRIX UPDATE** — `data_tools/build_rl_signal_matrix.py` now exports `c10_illiq_level_rank` and `c11_ret_60d_lag_rank`
  - Resulting matrix: `data/features/xs_rl_signal_matrix.parquet` (826,404 rows x 13 cols)
- **PAIRWISE CHECK** — C10 remains orthogonal to the other candidates
  - corr vs C4: -0.1224
  - corr vs C5: +0.0313
  - corr vs C6: +0.0150
  - corr vs C7: +0.0044
  - corr vs C8: +0.0184
  - corr vs C9: +0.0012
  - corr vs C11: -0.0686
- **PAIRWISE CHECK** — H124 low-beta signal does not qualify as an RL candidate
  - corr vs C10: +0.5524
  - corr vs S1: -0.0051
  - Low-beta is mostly the same axis as illiquidity/size, so it stays out of the matrix

### Session 45 experiment results (2026-03-28)
- **H135 IMPLEMENTED** — realistic deterministic portfolio baseline for the promoted RL signal library
  - script: `analysis/h135_signal_library_portfolio_baseline.py`
  - engine: `src/deterministic_portfolio.py`
  - tradability artifact published: `data/features/execution/tradability_daily.parquet`
- **INITIAL BASELINE RESULT WAS WRONG-SCALED**
  - the first `full_library` blend averaged raw signal columns directly
  - Session 46 found that `C4` and `C5` were not on a common `0-1` rank scale inside the matrix
  - the Session 45 `full_library` fail should be treated as a logging artifact, not the final scientific verdict
- **CAPACITY STRESS REMAINS VALID**
  - `1B VND` notional with `1% ADV20` participation leaves the system ~`99.9%` in cash
  - capacity is still a first-order stress dimension, not a safe default constant

### Session 46 experiment results (2026-03-28)
- **H135 CORRECTED** — non-presence signals are now cross-sectionally ranked by date before blending
  - `s1_only`: `-68.33%` total, `-10.01%` annualized, IR `-0.57`
  - `recent_core`: `-46.81%` total, `-5.63%` annualized, IR `-0.40`
  - `full_library`: `+72.10%` total, `+5.11%` annualized, IR `-0.05`
  - benchmark VNINDEX: `+223.17%` total over the same 2015-2025 window
- **H136 PASS** — deterministic portfolio construction materially improves monetization
  - script: `analysis/h136_portfolio_construction_sweep.py`
  - best configuration: `top_k=5`, rebalance every `5` signal days, `equal` weighting
  - score gate is effectively irrelevant in the winning region (`none`, `0.521`, `0.570` tie)
  - best result: `+1105.71%` total, `+25.66%` annualized, `+273.09%` relative vs VNINDEX, IR `0.50`, max DD `-59.76%`, `8/11` positive years
- **SWEEP PATTERN**
  - `5d` cadence dominates the grid; `10d` is the next-best regime; `3d` is materially worse
  - `equal` weighting beats `linear` and `square`
  - `top_k=5` is best absolute performer; `top_k=8/10` are competitive but lower
- **STRATEGIC VERDICT**
  - historical verdict from Session 46: do not pivot to RL yet
  - the next honest bottleneck is validating and capacity-stressing the deterministic portfolio candidate
  - RL should be treated as a later overlay that must beat this deterministic baseline
  - superseded operationally by Session 53, which parks capacity for the current-account branch and starts RL with deterministic benchmark-first gating

### Session 47 experiment results (2026-03-28)
- **H137 IMPLEMENTED** — nested walk-forward portfolio-construction selection
  - script: `analysis/h137_nested_portfolio_selection.py`
  - helper module: `src/portfolio_construction_search.py`
  - protocol: pick the best H136-style config on train years only, then test on the next year
- **H137 FAIL** — simple ML-style config selection does not validate out of sample
  - stitched OOS test years `2019-2025`
  - `+21.38%` total, `+2.84%` annualized
  - `-42.46%` relative vs VNINDEX
  - information ratio `-0.08`
  - max drawdown `-55.65%`
- **SELECTION PATTERN**
  - selected configs are mostly simple:
    - `top_k=5`, `rebalance_every=10`, `equal` weighting chosen `4/7` test years
    - early years briefly choose `top_k=3`, `5d`, `equal`
    - one year chooses `top_k=10`, `5d`, `equal`
  - this is not a case where exotic weighting or thresholding saves the result
- **STRATEGIC VERDICT**
  - direct “machine learns the best config” is not production-ready from this dataset
  - full-sample H136 winner is too optimistic
  - next work should simplify further inside a realistic long-only framework instead of adding more ML complexity

### Session 48 experiment results (2026-03-28)
- **H138 PASS** — simple fixed long-only rules beat benchmark on the honest holdout
  - script: `analysis/h138_fixed_menu_validation.py`
  - holdout: `2019-2025`
  - `k3_r5_eq`: `+303.01%` total, `+106.86%` relative vs VNINDEX
  - `k5_r5_eq`: `+271.38%` total, `+90.62%` relative vs VNINDEX
  - `k5_r10_eq`: `+241.90%` total, `+75.49%` relative vs VNINDEX
  - fixed rules outperform the H137 selector
- **H139 MIXED** — the edge survives fees but not capacity
  - script: `analysis/h139_fixed_menu_capacity_fee_stress.py`
  - at `0.50%` RT and no ADV cap, all three candidates remain positive benchmark-relative
  - with any tested ADV cap (`0.5%`, `1%`, `2%`), positive relative-return scenarios drop to `0`
  - capped scenarios stay mostly in cash (`97%+`)
- **STRATEGIC VERDICT**
  - long-only is not dead
  - but deployability is still unresolved
  - historical verdict from Session 48: do not add more ML or RL complexity until capacity is addressed honestly
  - superseded operationally by Session 53 for the current-account branch only

### Next queue after Session 59 (in order)

1. **H178: robustness stress for `h175__rel2_gt0`**
   - test alternate start years and rolling subperiods
   - test fee sensitivity around the current 0.30% RT assumption
   - the goal is to verify that the new champion is not a narrow split artifact
2. **H179: live-paper activation overlay**
   - apply `h175__rel2_gt0` on top of the current deterministic paper-trade branch
   - compare live paper outcomes against the always-on selector state
3. **H180: only small augmentations around the champion**
   - example: add a hit-rate guard to `rel2_gt0`
   - do not reopen broad activation-family mining unless `H178` weakens the current champion materially
4. **Selection-side work: parked secondary branch**
   - `H151`: narrow tradability-conditioned composite
   - `H152`: tradability-conditioned alpha search
   - keep these parked unless the `rel2_gt0` branch fails robustness
5. **RL branch: exploratory only**
   - keep the H155 artifact as evidence that RL can work sometimes
   - do not spend more compute on new RL ladders unless one of these changes first:
     - reward design
     - observation scaling / normalization
     - action or turnover control

### Remaining blocked paths
- **H98 LLM Sentiment** — PARKED (runtime/throughput bottleneck; re-open when local inference restored)
- **H95 Foreign flow** — BLOCKED (historical daily data not available via vnstock)
- **Order book imbalance** — BLOCKED (intraday data not available historically)

---

## Working Rules

- 2026 data: monitor-only. Do not use for tuning.
- For any material experiment, save a compact result summary and update notes.
- Archived reasoning lives in session logs; this file stays lean.
