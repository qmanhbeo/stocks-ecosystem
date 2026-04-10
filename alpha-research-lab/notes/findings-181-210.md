# Findings F181-F210

## F181: H267 Shows A Dev-Calibrated High-Conviction Breakout Trust Gate Survives Deterministic Integration On The Observed Breakout Sleeve (2026-04-03, Session 96)

Session 96 took the smallest honest follow-through after `H266`:
- same restarted `2023-2025` window
- no `2026+` read
- same observed `breakout_followthrough` entry subset
- no live-branch change

The question was no longer:
- "does the intraday score rank breakout entries better?"

It was:
- can a simple deterministic gate built from that score actually improve the realized breakout-only sleeve?

The gate grid was predeclared from the dev distribution of the `H266` winner score:
- `dev_q50`
- `dev_q80`
- `dev_q90`

Baseline:
- `observed_breakout_always_on`
  - validation relative return:
    - `-0.1615`
  - confirmation relative return:
    - `-0.3327`
  - overall relative return:
    - `-0.4499`
  - validation IR:
    - `-0.7329`
  - confirmation IR:
    - `-1.6465`

Winning gate:
- `dev_q90`
  - threshold:
    - `0.5198`
  - allowed rows:
    - `536`
      - dev `207`
      - validation `178`
      - confirmation `151`
  - validation relative return:
    - `+0.2659`
  - confirmation relative return:
    - `+0.0029`
  - overall relative return:
    - `+0.2638`
  - validation IR:
    - `+0.9988`
  - confirmation IR:
    - `+0.0734`

Delta vs the ungated observed-breakout baseline:
- validation relative delta:
  - `+0.4274`
- confirmation relative delta:
  - `+0.3357`
- validation IR delta:
  - `+1.7316`
- confirmation IR delta:
  - `+1.7199`

So `H267` is a real deterministic pass on its own local contract:
- the score is no longer only a predictive ranking artifact
- a simple high-conviction gate materially improves the realized breakout sleeve

**Key finding:** the reduced-shape intraday breakout-trust branch survives deterministic integration on the observed breakout sleeve when restricted to high-conviction entries.

**Implication:** advance to family-local breakout trust compatibility integration (`H268`), not to live promotion.

## F182: H267 Also Sharpens The Boundary Of What Has And Has Not Been Proven; The Working Contract Is Still A Narrow Breakout Sleeve, Not A Shared Entry Surface Or Live-Ready Branch (2026-04-03, Session 96)

`H267` is a real pass, but it does not prove too much.

What it proves:
- the observed breakout sleeve is no longer failing because of missingness
- the `H266` winner score can survive deterministic integration
- a high-conviction gate can turn a bad breakout-only sleeve into a locally positive restarted-window sleeve

What it does **not** prove:
- that reduced-shape intraday is a universal entry feature
- that the gate should be published as a shared entry contract
- that the live sticky branch should change
- that the broader entry book improves once the gate is reintroduced alongside the non-breakout families

The evidence remains narrow:
- winner:
  - `dev_q90`
- threshold:
  - `0.5198`
- overall allowed rows:
  - `536`
- confirmation allowed rows:
  - `151`
- confirmation allowed share inside the observed breakout sleeve:
  - about `8.50%`

So the honest next question is structural:
- if this gate only helps breakout rows, does it still help after reintegration into the broader family-mixed entry ladder?

**Key finding:** `H267` moves the branch from breakout-sleeve evidence to reintegration readiness, not to production readiness.

**Implication:** `H268` is the next honest step. If `H268` fails, keep `H267` as narrow offline evidence only and pivot to the breakout-survivor label rewrite or selector-state stress routing.

## F183: H268 Shows The Breakout Trust Gate Survives Reintegration Into The Carried Sparse-Breadth Book, So The H267 Result Was Not Only A Breakout-Sleeve Artifact (2026-04-03, Session 97)

Session 97 took the smallest honest reintegration follow-through after `H267`:
- same restarted `2023-2025` window
- no `2026+` read
- same `H267` score and threshold
- no live-branch change

The new question was:
- can the breakout trust gate still help once non-breakout families are reintroduced through a broader mixed-family deterministic book?

The carried broader baseline was the sparse-breadth contract:
- `top_m=5`
- `min_selection_score=0.65`
- `min_score_gap=0.03`

Baseline:
- validation relative return:
  - `-0.1218`
- confirmation relative return:
  - `-0.2142`
- overall relative return:
  - `-0.2796`
- validation IR:
  - `-0.4919`
- confirmation IR:
  - `-0.8462`

Best reintegration variant:
- `breakout_dev_q90_keep_missing`
  - validation relative return:
    - `-0.1148`
  - confirmation relative return:
    - `-0.0447`
  - overall relative return:
    - `+0.1518`
  - validation relative delta:
    - `+0.0070`
  - confirmation relative delta:
    - `+0.1696`
  - overall relative delta:
    - `+0.4314`
  - validation IR delta:
    - `+0.0641`
  - confirmation IR delta:
    - `+0.7411`
  - overall IR delta:
    - `+0.6031`

So `H268` does pass the reintegration question:
- the breakout trust gate still helps after non-breakout families come back
- the effect is no longer confined to the isolated breakout sleeve

**Key finding:** the `H267` breakout-trust effect is compatible with the carried sparse-breadth mixed-family book on the restarted contract.

**Implication:** if this exact branch continues, it earns one narrow current-account compatibility follow-through (`H269`) rather than immediate closure.

## F184: H268 Also Tightens The Ceiling On The Claim; Reintegration Improves The Carried Book Relative To Baseline, But It Still Does Not Produce A Broad-Book Absolute Winner (2026-04-03, Session 97)

`H268` is a pass, but it is not a strong broad-book win.

The best reintegrated book still has:
- validation relative return:
  - `-0.1148`
- confirmation relative return:
  - `-0.0447`

So the honest interpretation is:
- the overlay reduces damage materially
- it turns the stitched restarted-window book positive overall
- but it does **not** make the carried broad book benchmark-positive in both validation and confirmation

The structural narrowness also remains visible:
- best variant:
  - `breakout_dev_q90_keep_missing`
- total allowed rows:
  - `219`
- observed breakout rows kept:
  - `8`

That means the branch is still living on a small high-conviction sub-slice inside a broader book, not on a generally improved entry surface.

**Key finding:** `H268` is a compatibility / damage-reduction pass, not a broad-book deployment pass.

**Implication:** keep the result offline-only, do not treat it as a new entry-alpha champion, and only continue to `H269` if the explicit goal is one last narrow compatibility audit before parking the branch.

## F185: H269 Shows The Breakout-Trust Overlay Does Not Survive Current-Account Compatibility; It Loses To Both The Operational Sticky Baseline And The Carried Sparse Control (2026-04-03, Session 98)

Session 98 took the final narrow follow-through after `H268`:
- same restarted `2023-2025` window
- no `2026+` read
- same `H268` winner
- same live branch frozen

The question was no longer:
- "is the breakout-trust overlay real on some offline slice?"

It was:
- does that overlay help enough inside the actual current-account / sticky operational framing to justify staying alive?

Compared variants:
- `operational_sticky_baseline`
- `carried_sparse_plus_sticky`
- `h268_overlay_plus_sticky`

Operational sticky baseline:
- validation relative return:
  - `-0.0873`
- confirmation relative return:
  - `+0.1880`
- overall relative return:
  - `+0.4660`

Carried sparse control:
- validation relative return:
  - `-0.5346`
- confirmation relative return:
  - `-0.0824`
- overall relative return:
  - `-0.2154`

Candidate `h268_overlay_plus_sticky`:
- validation relative return:
  - `-0.5635`
- confirmation relative return:
  - `-0.3364`
- overall relative return:
  - `-0.5495`

Delta vs operational baseline:
- validation:
  - `-0.4762`
- confirmation:
  - `-0.5245`
- overall:
  - `-1.0155`

Delta vs sparse control:
- validation:
  - `-0.0288`
- confirmation:
  - `-0.2540`
- overall:
  - `-0.3342`

So `H269` is not a near-miss:
- the overlay loses badly to the operational baseline
- and it still fails even against the weaker carried sparse control

**Key finding:** the breakout-trust overlay does not survive current-account compatibility on the current restarted contract.

**Implication:** close this exact branch family and stop looking for one more compatibility tweak on the same contract.

## F186: H269 Also Shows The Failure Is Structural, Not Just Return-Level; Narrowness Cost Dominates The Operational Framing (2026-04-03, Session 98)

`H269` fails not only on returns, but on book shape.

Validation-plus-confirmation operational diagnostics:
- operational sticky baseline:
  - sparse-book rate:
    - `0.4910`
  - avg holdings:
    - `3.0962`
- carried sparse control:
  - sparse-book rate:
    - `0.9499`
  - avg holdings:
    - `0.9739`
- `h268_overlay_plus_sticky`:
  - sparse-book rate:
    - `0.9800`
  - avg holdings:
    - `0.7014`
  - zero-holding rate:
    - `0.5190`

That means the overlay is doing exactly the wrong thing for current-account compatibility:
- it is more sparse than the already-weak sparse control
- it carries much less breadth than the operational baseline
- and the narrowness cost is large enough to overwhelm any hoped-for breakout-trust benefit

**Key finding:** the branch dies because the operational framing cannot absorb its narrowness, not because the signal was fake on the earlier offline slices.

**Implication:** keep `H266-H268` as offline evidence only, close `H269`, and move to the next materially different fallback branch instead of stretching this family any further.

## F187: H270 Shows The Breakout-Specific Reduced-Shape Intraday Branch Survives A Materially Different Survivor-Target Rewrite On The Observed Breakout Sleeve (2026-04-03, Session 99)

Session 99 took the first honest follow-through after `H269`:
- same restarted `2023-2025` window
- no `2026+` read
- same observed `breakout_followthrough` entry subset
- same reduced-shape intraday surface
- no live-branch change

The branch question was no longer:
- "can the old breakout-trust gate survive one more compatibility tweak?"

It was:
- does the intraday branch become cleaner if the target is rewritten from generic `buy_now` into "breakout survives the next `1-2` cycles without immediate failure"?

Three fixed survivor contracts were audited:
- `net_relaxed_survivor`
  - `5d cycle_return_net > -0.02`
  - `10d cycle_return_net > 0.00`
- `net_soft_survivor`
  - `5d cycle_return_net > -0.01`
  - `10d cycle_return_net > 0.00`
- `net_strict_survivor`
  - `5d cycle_return_net > 0.00`
  - `10d cycle_return_net > 0.00`

Winning contract:
- `net_soft_survivor`

Winning intraday model:
- `intraday_shape_core`
  - validation AUC:
    - `0.5168`
  - confirmation AUC:
    - `0.5344`
  - validation top-quintile `10d` return:
    - `+0.87%`
  - confirmation top-quintile `10d` return:
    - `+0.89%`

Best path control on that same contract:
- `breakout_path_core`
  - validation AUC:
    - `0.5074`
  - validation top-quintile `10d` return:
    - `+0.61%`

Observed breakout-sleeve phase means on the winner contract:
- validation:
  - `+0.18%`
- confirmation:
  - `+0.59%`

So `H270` is a real target-contract pass:
- the reduced-shape intraday branch is not dead after `H269`
- it survives once the question is reframed around breakout survival instead of generic near-term entry success

**Key finding:** the breakout-specific reduced-shape intraday branch survives a materially different survivor-target rewrite on the observed breakout sleeve, with `net_soft_survivor` and `intraday_shape_core` as the cleanest contract.

**Implication:** advance to deterministic breakout-survivor gate integration (`H271`), not to live or broad-book promotion.

## F188: H270 Also Tightens The Ceiling Again; The Survivor-Target Rewrite Is A Predictive Pass, But Path Control Still Has Stronger Confirmation Top-Quintile Economics On The Winning Contract (2026-04-03, Session 99)

`H270` passes, but it does not prove that the branch is ready for deterministic rollout.

On the winning `net_soft_survivor` contract:
- best intraday model:
  - `intraday_shape_core`
  - confirmation top-quintile `10d` return:
    - `+0.89%`
- best path control:
  - `breakout_path_core`
  - confirmation top-quintile `10d` return:
    - `+1.24%`

So the target rewrite does **not** yet prove:
- that a deterministic intraday gate will beat the carried breakout path baseline
- that this branch belongs back in the broader book
- that the live sticky branch should change

The contract-level pattern is still useful:
- `net_relaxed_survivor` also passed with a compact hybrid:
  - `intraday_atoms_plus_breakout_path`
- `net_strict_survivor` degraded into `MIXED`
  - its confirmation top-quintile `10d` return fell below the phase mean

That means the shape of the new target matters:
- too loose risks collapsing back toward generic breakout continuation
- too strict starts compressing the useful sleeve again
- the current winner is the middle contract, not the extremes

**Key finding:** `H270` is a predictive survivor-contract pass, not a deterministic or economic dominance pass; the best path control still owns the stronger `2025` top-quintile `10d` payoff on the winning contract.

**Implication:** `H271` must be a strict deterministic sleeve-integration test. If that fails, keep `H270` as offline evidence only and pivot away instead of tuning more survivor-label variants.

## F189: H271 Shows The Breakout-Survivor Rewrite Survives Deterministic Sleeve Integration With A High-Conviction `dev_q90` Gate (2026-04-04, Session 100)

Session 100 took the exact deterministic follow-through after `H270`:
- same restarted `2023-2025` window
- no `2026+` read
- same observed `breakout_followthrough` survivor sleeve
- same winner contract from `H270`:
  - `net_soft_survivor`
- same live branch frozen

The question was no longer:
- "does the target rewrite only improve predictive ranking?"

It was:
- can a simple deterministic gate built from the `H270` winner score improve the realized breakout-survivor sleeve?

The gate grid was predeclared from the dev distribution of the `H270` winner score:
- `dev_q50`
- `dev_q80`
- `dev_q90`

Baseline:
- `observed_breakout_survivor_always_on`
  - validation relative return:
    - `-0.1615`
  - confirmation relative return:
    - `-0.3327`
  - overall relative return:
    - `-0.4499`
  - validation IR:
    - `-0.7329`
  - confirmation IR:
    - `-1.6465`

Winning gate:
- `dev_q90`
  - threshold:
    - `0.4572`
  - allowed rows:
    - `505`
      - dev `207`
      - validation `140`
      - confirmation `158`
  - validation relative return:
    - `+0.0498`
  - confirmation relative return:
    - `-0.2794`
  - overall relative return:
    - `-0.2594`
  - validation relative delta:
    - `+0.2113`
  - confirmation relative delta:
    - `+0.0534`
  - validation IR delta:
    - `+1.0527`
  - confirmation IR delta:
    - `+0.5324`

So `H271` is a real deterministic pass on the local survivor contract:
- the `H270` winner is no longer only a predictive-score artifact
- a simple high-conviction gate improves both validation and confirmation relative performance versus the ungated survivor sleeve
- the coverage guard stays intact:
  - confirmation allowed rows:
    - `158`

**Key finding:** the breakout-survivor rewrite survives deterministic sleeve integration when restricted to high-conviction `intraday_shape_core` entries.

**Implication:** advance to family-local breakout-survivor compatibility integration (`H272`), not to live promotion.

## F190: H271 Also Sharpens The Ceiling Again; The Deterministic Pass Is Still Narrow Offline Evidence, Not Broad-Book Or Operational Proof (2026-04-04, Session 100)

`H271` passes, but it still does not prove too much.

What it proves:
- the `H270` survivor-target rewrite can survive deterministic integration on the observed breakout sleeve
- the best gate remains compact and stable:
  - `dev_q90`
  - threshold `0.4572`
- the branch still contains real local economic improvement versus its own survivor-sleeve baseline

What it does **not** prove:
- that the branch improves the broader mixed-family entry book
- that the branch survives current-account compatibility
- that the live sticky branch should change

The narrowness and absolute weakness remain visible:
- winning gate:
  - overall allowed rows:
    - `505`
  - confirmation allowed rows:
    - `158`
  - confirmation relative return:
    - `-0.2794`
  - overall relative return:
    - `-0.2594`

So the honest next question is structural again:
- if the survivor gate only works on the narrow local sleeve, does it still help once breakout rows are reintroduced into the carried broader book and the other families are left untouched?

**Key finding:** `H271` moves the survivor branch from local deterministic evidence to reintegration readiness, not to deployment readiness.

**Implication:** `H272` is the next honest step. If `H272` fails, keep `H270-H271` as offline evidence only and pivot to the `top-k intraday stress router` or `library-grade intraday shape atoms`.

## F191: H272 Shows The Breakout-Survivor Gate Survives Family-Local Reintegration Into The Carried Sparse-Breadth Book (2026-04-04, Session 101)

Session 101 took the exact reintegration follow-through after `H271`:
- same restarted `2023-2025` window
- no `2026+` read
- same `H271` score and threshold:
  - `entry_prob__intraday_shape_core >= 0.4572`
- same winner survivor contract from `H270`:
  - `net_soft_survivor`
- same live branch frozen

The new question was:
- can the breakout-survivor gate still help once non-breakout families are reintroduced through the carried sparse-breadth deterministic book?

The carried broader baseline was still:
- `top_m=5`
- `min_selection_score=0.65`
- `min_score_gap=0.03`

Baseline:
- validation relative return:
  - `-0.1218`
- confirmation relative return:
  - `-0.2142`
- overall relative return:
  - `-0.2796`
- validation IR:
  - `-0.4919`
- confirmation IR:
  - `-0.8462`

Best reintegration variant:
- `survivor_dev_q90_keep_missing`
  - winner survivor contract:
    - `net_soft_survivor`
  - validation relative return:
    - `-0.1148`
  - confirmation relative return:
    - `-0.0447`
  - overall relative return:
    - `+0.1548`
  - validation relative delta:
    - `+0.0070`
  - confirmation relative delta:
    - `+0.1696`
  - overall relative delta:
    - `+0.4344`
  - validation IR delta:
    - `+0.0641`
  - confirmation IR delta:
    - `+0.7411`
  - overall IR delta:
    - `+0.6110`

So `H272` does pass the reintegration question:
- the `H271` survivor gate is not only a local survivor-sleeve artifact
- it still helps after non-breakout families come back through the carried sparse book

**Key finding:** the breakout-survivor gate is compatible with the carried sparse-breadth mixed-family book on the restarted contract.

**Implication:** if this exact branch continues, it earns one narrow current-account compatibility follow-through (`H273`) rather than immediate closure.

## F192: H272 Also Tightens The Ceiling Again; The Survivor Rewrite Does Not Solve Transportability, It Collapses Back To The Same Narrow Carried-Book Shape (2026-04-04, Session 101)

`H272` passes, but it still does not become a broad-book winner.

The best reintegrated book still has:
- validation relative return:
  - `-0.1148`
- confirmation relative return:
  - `-0.0447`

The structural narrowness also remains visible:
- best variant:
  - `survivor_dev_q90_keep_missing`
- total allowed rows:
  - `219`
- observed breakout rows kept:
  - `8`

That means the survivor rewrite does **not** fix the transportability problem:
- the broader book still only wants a tiny high-conviction breakout slice
- the practical carried-book shape is effectively the same narrow compatibility outcome already seen in `H268`

So the honest interpretation is:
- the survivor rewrite is real offline evidence
- deterministic sleeve integration is real
- carried-book reintegration is still only compatibility / damage reduction
- the branch is still not broad-book or operationally proven

**Key finding:** `H272` confirms that the new survivor contract does not materially widen the carried-book footprint; the branch collapses back to the same narrow reintegrated shape.

**Implication:** `H273` is the last honest follow-through if the lab wants to test operational compatibility once more. If `H273` fails, kill this exact reintegration continuation and pivot to the `top-k intraday stress router` or `library-grade intraday shape atoms`.

## F193: H273 Shows The Breakout-Survivor Overlay Does Not Survive Current-Account Compatibility; It Loses To Both The Operational Sticky Baseline And The Carried Sparse Control (2026-04-04, Session 102)

Session 102 took the final narrow follow-through after `H272`:
- same restarted `2023-2025` window
- no `2026+` read
- same `H272` winner:
  - `survivor_dev_q90_keep_missing`
  - `entry_prob__intraday_shape_core >= 0.4572`
- same survivor contract from `H270`:
  - `net_soft_survivor`
- same live branch frozen

The question was no longer:
- "is the breakout-survivor overlay real on some offline slice?"

It was:
- does that overlay help enough inside the actual current-account / sticky operational framing to justify staying alive?

Compared variants:
- `operational_sticky_baseline`
- `carried_sparse_plus_sticky`
- `h272_overlay_plus_sticky`

Operational sticky baseline:
- validation relative return:
  - `-0.0873`
- confirmation relative return:
  - `+0.1880`
- overall relative return:
  - `+0.4660`

Carried sparse control:
- validation relative return:
  - `-0.5346`
- confirmation relative return:
  - `-0.0824`
- overall relative return:
  - `-0.2154`

Candidate:
- validation relative return:
  - `-0.5635`
- confirmation relative return:
  - `-0.1650`
- overall relative return:
  - `-0.4340`
- validation delta vs operational:
  - `-0.4762`
- confirmation delta vs operational:
  - `-0.3530`
- overall delta vs operational:
  - `-0.8999`
- confirmation delta vs sparse control:
  - `-0.0826`
- overall delta vs sparse control:
  - `-0.2186`

So `H273` is not a near-miss:
- the survivor overlay loses badly to the unchanged operational sticky baseline
- it also loses to the weaker carried sparse control

**Key finding:** the breakout-survivor overlay does not survive current-account compatibility on the current restarted contract.

**Implication:** close the exact breakout-survivor continuation family on the current contract and pivot away from operational continuation of this line.

## F194: H273 Also Shows The Failure Is Structural, Not Just Return-Level; The Survivor Rewrite Still Collapses Into A Near-Empty Operational Book (2026-04-04, Session 102)

`H273` fails not only on returns, but on book shape.

The structural diagnostics remain extreme:
- candidate sparse-book rate:
  - `0.9800`
- operational baseline sparse-book rate:
  - `0.4910`
- candidate average holdings:
  - `0.7315`
- operational baseline average holdings:
  - `3.0962`
- candidate zero-holding rate:
  - `0.4890`

So the survivor rewrite still does **not** solve the operational transportability problem:
- the book is near-always sparse
- average holdings collapse relative to the sticky baseline
- the small carried-book compatibility pass does not survive once the real operational framing is restored

This is the same structural failure mode that killed the earlier breakout-trust line:
- the local breakout gate is real offline
- but narrowness cost dominates in the operational branch

**Key finding:** the breakout-survivor rewrite changes the local label contract, but it does not change the operational failure mode; narrowness still dominates.

**Implication:** `H270-H272` remain offline evidence only. The next honest queue is `top-k intraday stress router` or `library-grade intraday shape atoms`, not more survivor-gate continuation tuning on the current contract.

## F195: H274 Shows The Top-K Intraday Stress Router Does Not Survive The Frozen Sticky Branch Audit Even With High Reduced-Shape Coverage (2026-04-04, Session 103)

Session 103 took the first fallback after `H273`:
- exact frozen live branch:
  - `sticky_bonus_0p015`
- replay history:
  - `2019-2025`
- evaluation window:
  - activated rebalance dates in `2023-2025` only
- reduced-shape intraday source:
  - the passed `H258` contract panel

Coverage was not the problem:
- overall observed share across requested top-k names:
  - `0.9747`
- validation observed share:
  - `0.9697`
- confirmation observed share:
  - `0.9571`

The predeclared intraday summaries were:
- `stress_fade`
- `stress_failed_breakout`
- `stress_weak_close_repair`
- `stress_composite_mean`
- `stress_name_share_q70`

None survived the selector-state audit.

Best intraday candidate:
- `stress_weak_close_repair`
  - validation directional hits:
    - `0`
  - confirmation directional hits:
    - `1`
  - validation high-minus-low cycle delta:
    - `+0.0037`
  - confirmation high-minus-low cycle delta:
    - `-0.0021`

That is not a near-pass:
- no intraday summary produced even one validation directional hit
- most intraday candidates pointed the wrong way on next-cycle relative return
- high-stress intraday dates were often flat-to-better, not reliably worse

**Key finding:** the reduced-shape intraday summaries do not survive as a top-k selector-state router on the current frozen sticky contract.

**Implication:** close the `top-k intraday stress router` branch on the current contract and do not open a deterministic gate follow-through from this line.

## F196: H274 Also Shows The Older Slow Blocked-Buy Proxy Still Dominates The Same Audit; Intraday Stress Is Not A Cleaner Operational State Variable Here (2026-04-04, Session 103)

`H274` was not just an empty or underpowered audit.

The old slow proxy stayed materially stronger on the exact same rebalance dates:
- baseline:
  - `full_recent_blocked_buy_ewm5`
- validation directional hits:
  - `2`
- confirmation directional hits:
  - `4`
- validation high-minus-low cycle delta:
  - `-0.0201`
- confirmation high-minus-low cycle delta:
  - `-0.0073`

So the selector-state audit says:
- reduced-shape intraday is not simply recreating the blocked-buy family
- but it also is not replacing it with a better activation variable on the current contract
- the slower blocked-buy state still carries more operationally useful direction than any intraday top-k summary tested here

**Key finding:** if the reduced-shape intraday branch is useful, it is more likely to belong as library-grade state atoms than as an activation router on the frozen sticky branch.

**Implication:** move the queue to `library-grade intraday shape atoms`, not to more selector-state intraday gate tuning on the current contract.

## F197: H275 Shows The Surviving Library-Grade Part Of The Reduced-Shape Intraday Branch Is The Disagreement Component, Not The Raw Atom (2026-04-04, Session 104)

Session 104 took the next exact queue item after `H274`:
- do not open another gate
- instead test whether reduced-shape intraday atoms survive as offline signal-library state features
- use only the observed `2023-2025` reduced-shape subset
- gate every candidate against:
  - standalone IC `> 0.01`
  - positive years `>= 60%`
  - max dev correlation `< 0.30` versus `S1`, `C4`, and `C12`

Coverage stayed broad enough for an honest signal audit:
- observed row count:
  - `243,763`
- observed row share of the `2023-2025` matrix:
  - `0.9434`
- observed dates:
  - `718`
- observed tickers:
  - `394`

Two disagreement atoms passed cleanly:
- `fade_tension_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0323 / +0.0367 / +0.0202`
  - max dev anchor corr:
    - `0.0667`
- `intraday_shape_core_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0330 / +0.0259 / +0.0160`
  - max dev anchor corr:
    - `0.0751`

So the reduced-shape intraday branch does survive as offline state evidence.
But what survives is not the raw reduced-shape axis.
It is the cross-sectional disagreement left after removing the existing daily continuation / gap / close-location library.

**Key finding:** the transportable library-grade intraday signal is disagreement with `S1/C4/C12`, not raw reduced-shape direction itself.

**Implication:** promote the disagreement atoms as observed-subset offline signal-library candidates, not as a live timing gate.

## F198: H275 Also Shows The Raw Reduced-Shape Atoms Are Real But Redundant; They Collapse Onto Existing Daily Axes Despite Strong IC (2026-04-04, Session 104)

`H275` did not say the raw intraday atoms are useless.
It said they are not orthogonal enough to deserve separate library status on the current contract.

Raw atoms that stayed predictive:
- `fade_tension_rank`
  - dev / validation / confirmation IC:
    - `+0.0701 / +0.0821 / +0.0568`
  - but max dev anchor corr:
    - `0.3189`
- `intraday_shape_core_rank`
  - dev / validation / confirmation IC:
    - `+0.0694 / +0.0657 / +0.0469`
  - but max dev anchor corr:
    - `0.3157`
- `failed_breakout_rank`
  - dev / validation / confirmation IC:
    - `+0.0294 / +0.0144 / +0.0160`
  - but max dev anchor corr:
    - `0.3184`

So the queue instruction was exactly right:
- the raw atoms are not dead
- but they collapse onto the existing daily continuation / close-location axes closely enough that they fail the library orthogonality bar

The disagreement residual is what makes them useful:
- once residualized against `S1`, `C4`, and `C12`, the surviving IC remains while the redundancy drops sharply

**Key finding:** the raw reduced-shape intraday atoms are predictive but redundant; disagreement residualization is what makes them library-grade on the current observed subset.

**Implication:** update the signal registry with the disagreement atoms only, and keep the raw atoms out of the promoted library list.

## F199: H276 Shows Event-Conditioned Intraday Disagreement Does Not Earn Deterministic Follow-Through; No Regime Beats The Ungated Baseline Cleanly Enough To Justify H277 (2026-04-04, Session 105)

Session 105 took the next exact queue item after `H275`:
- same restarted `2023-2025` window
- no `2026+` read
- same observed `breakout_followthrough` entry subset
- same reduced-shape disagreement construction against `S1`, `C4`, and `C12`
- no live-branch change

Coverage was broad enough for a real audit:
- breakout rows:
  - `5,858`
- breakout dates:
  - `711`
- breakout tickers:
  - `379`

The question was:
- if raw event timing and raw intraday disagreement each fail alone, does event-conditioned disagreement beat the same-model ungated baseline strongly enough to earn a deterministic follow-through?

No candidate passed.

Best mixed result:
- `event_transition_any + disagreement_combo`
  - validation top-quintile cycle return delta vs `all_rows`:
    - `+0.0048`
  - confirmation top-quintile cycle return delta vs `all_rows`:
    - `+0.0120`
  - validation AUC delta vs `all_rows`:
    - `-0.0195`
  - confirmation AUC delta vs `all_rows`:
    - `-0.0135`

Cleaner directional clue:
- `event_transition_any + intraday_shape_core_disagreement`
  - validation top-quintile cycle return delta vs `all_rows`:
    - `+0.0043`
  - confirmation top-quintile cycle return delta vs `all_rows`:
    - `+0.0137`
  - validation AUC delta vs `all_rows`:
    - `-0.0055`
  - confirmation AUC delta vs `all_rows`:
    - `+0.0156`

Smaller event slice:
- `recent_filing_any` also produced mixed-only top-quintile improvement

Hard failure inside the same audit:
- `report_window_any` failed outright across all tested models

So `H276` did not earn `H277`:
- promoted candidates:
  - `0`

**Key finding:** event-conditioned disagreement improves realized high-score tails on the observed breakout subset, but it does not beat the ungated same-model baseline cleanly enough to justify deterministic follow-through on the current contract.

**Implication:** keep `H276` as narrow offline evidence only, do **not** open `H277`, and stop timing-model invention on the current stack until new data or more forward evidence arrives.

## F200: H276 Also Narrows The Surviving Event Thesis; The Useful Context Looks Closer To Broad Event Transition Than Pure Report Window, And More Like Conviction Concentration Than Universal Ranking Improvement (2026-04-04, Session 105)

`H276` did not kill every version of the event idea equally.

What failed hardest:
- pure `report_window_any`
  - all tested models failed

What survived partially:
- `event_transition_any`
  - report-window or recent-filing context
- `recent_filing_any`
  - smaller but still directionally useful slice

The shape of the evidence matters.

The mixed candidates improved:
- validation top-quintile realized return
- confirmation top-quintile realized return

But they did **not** improve validation ranking cleanly enough to pass.

That means the surviving event clue is not:
- "event days make the disagreement model a universally better classifier"

It is closer to:
- "event transition context concentrates the payoff in the highest-disagreement tail, even when whole-slice ranking quality is not reliably better"

So the surviving state is narrower than "report window trust":
- it looks more like broad transition / repricing context than pure scheduled-report context
- and it looks more like conviction concentration than a new general gate

**Key finding:** on the current observed breakout contract, the surviving event clue is broad event-transition context that sharpens the realized disagreement tail, not a pure report-window ranking upgrade.

**Implication:** if the event branch is ever reopened, start from a materially different label, operational contract, or richer event data rather than from another report-window gate tweak on the current stack.

## F202: H279 Shows Breadth-Aware Intraday Shape Routing Beats The Ungated Baseline Even Though The Raw Shape Score Is Weak (2026-04-04, Session 108)

`H279` fused the `first_hour_fade_proxy / weak_open_strong_close_proxy / failed_breakout_proxy` shape proxies with a simple breadth gap gate (`xs_sector_breadth_5d` lagged five days).

### Router result
- gate: shape score in the top 10% + `breadth_gap >= 0`
- router rows: `13,356`
- router 5-day hold advantage: `+0.000398` (vs baseline `+0.000278`)
- router positive rate: `46.6%` (vs baseline `45.2%`)
- shape-only set: mean adv `-0.000120`

### Key finding
The shape proxies by themselves are too weak / anti-predictive, but applying them inside a breadth-gap router lifts the 5-day hold advantage enough to be noteworthy.

**Implication:** keep the router logic offline for now; if it ever moves toward a live gate, do it through the saved panel/summary so you can reproduce the same gate structure rather than starting from scratch again.

## F203: H280 Shows The H279 Shape-Breadth Router Does Not Survive A Strict Confirmation Split; Validation Lift Reverses In 2025 (2026-04-05, Session 109)

`H280` rechecked the frozen H279 router on a strict split:
- validation years: `2023-2024`
- confirmation year: `2025`
- gate: frozen H279 `shape top 10% + breadth_gap >= 0`

### Split result
- validation router mean adv: `+0.002592`
- validation baseline mean adv: `+0.001631`
- validation lift: `+0.000962`
- validation router positive rate: `49.4%`
- confirmation router mean adv: `-0.004816`
- confirmation baseline mean adv: `-0.002828`
- confirmation lift: `-0.001988`
- confirmation router positive rate: `40.1%`
- confirmation shape-only mean adv: `-0.003746`

### Key finding
The router does produce a validation lift, but the effect does not survive the 2025 confirmation slice. The raw shape score also remains negative on confirmation.

**Implication:** treat `H279` as parked offline evidence only on the current contract. Do not promote the gate, and do not keep tuning the same shape+breadth rule without new data or a materially different label / contract.

## F204: H281 Shows The LLM News Surface Is Real, But The Simple Sentiment Contract Still Does Not Clear The Standalone Gate (2026-04-05, Sessions 110-112)

`xs_news_sentiment_daily.parquet` is the legacy keyword-news table, built by `extract_news_sentiment.py` from CafeF raw JSONL files restored by `fetch_news_archive.py`.

`xs_llm_news_ticker_day.parquet` is the separate LLM surface, built from `data/llm_cache/YYYY-MM-DD.jsonl` by `extract_llm_news_features.py` and `build_llm_news_features.py`.

`H281` rechecked the rebuilt LLM ticker-day surface directly:
- candidate rows: `826,404`
- nonzero LLM rows: `17,578`
- raw cache horizon: `2015-09-21` to `2017-06-04` at the current in-progress checkpoint
- test window: `2015-2025`
- compared against legacy keyword-news baseline `C1`

### Result
The rebuilt LLM surface is populated and real, but the upstream extraction is still in progress at the current checkpoint and the simplest sentiment-style candidates are still weak:
- best LLM candidate: `llm_sentiment_raw`
- best LLM avg IC: `+0.0061`
- best LLM positive years: `2 / 2`
- best LLM corr vs `S1`: `+0.0014`
- best LLM corr vs `C1`: `+0.0458`

### Key finding
The upstream source is not the keyword-news table, and the current LLM extraction contract does produce usable rows, but the raw sentiment-only features still do not beat the gate.

**Implication:** park `H98 / llm-news-gate` for raw sentiment. If this branch is revisited, test a state-router or interaction contract rather than another raw sentiment sweep.

## F206: H283 Shows The Gap-Failure Exhaustion Blend Is Predictive But Still Collapses Onto The Existing Compression Blow-Off Axis (2026-04-05, Session 113)

`H283` tested a narrow combined family built from the H130 gap-absorption logic and the H133 compression blow-off logic:
- `xs_gap_failure_exhaustion_1`
- `xs_gap_failure_exhaustion_2`
- `xs_gap_failure_exhaustion_3`

### Result
The combined family is real and predictive, but every variant is redundant with the existing compression blow-off candidate:
- best variant: `xs_gap_failure_exhaustion_3`
- best IC: `+0.0371`
- best positive years: `10 / 11`
- best corr vs `S1`: `+0.233`
- best max candidate corr: `+0.796`
- overlap verdict: `dup` against `c13_compress_blowoff_2`

### Key finding
The gap-failure thesis does not create a new axis under the current contract. It mostly repackages the existing compression blow-off reversal state.

**Implication:** close the generic gap-failure blend on this contract. If this idea is revisited, it needs a materially different conditioning layer, not another small variation of the same compression / gap interaction.

## F207: H284 Shows Sector Conditioning Does Not Rescue The Compression Blow-Off Reversal; Hot Sectors Weaken It And Ceiling Clusters Just Repackage C7 (2026-04-05, Session 114)

`H284` tested a fixed sector-conditioned version of the H133 compression blow-off reversal:
- `h284_c13_compress_blowoff_2`
- `h284_c13_hot_sector`
- `h284_c13_ceiling_cluster`
- `h284_c13_hot_and_cluster`

### Result
The base reversal state is real, but the conditioned variants do not create a new axis:
- base IC: `+0.0350`
- hot-sector interaction IC: `-0.0010`
- ceiling-cluster interaction IC: `+0.0137`
- hot-and-cluster interaction IC: `+0.0095`
- hot-sector subset c13 IC: `+0.0198`
- ceiling-cluster subset c13 IC: `-0.0512`
- hot-and-cluster subset c13 IC: `-0.0542`

### Key finding
The hot-sector gate weakens the state, and the ceiling-cluster gate is only a restatement of the existing ceiling-count axis. The branch does not produce a new standalone signal.

**Implication:** park `sector-conditioned blow-off`. Move on to the next materially different branch, `5d-label-contract`.

## F208: H285 Shows The 5d Label Contract Materially Reorders The Library; C6 Moves To The Top, C13 Drops, And The W Reclaim Family Gains Relative Relevance (2026-04-05, Session 115)

`H285` compared the current C4-C14 library and the upward-W family under the canonical 1d label versus a 5d forward excess-return label.

### Result
The ranking is not stable enough to reuse unchanged:
- rank Spearman between 1d and 5d ordering: `+0.5786`
- top-3 overlap: `1 / 3`
- 1d top feature: `c13_compress_blowoff_2`
- 5d top feature: `c6_contrarian_intra_5d`
- strongest 5d row: `c6_contrarian_intra_5d` with IC `+0.0393`
- 5d `c4_oc_asym_5d`: `+0.0269`
- 5d `c9_reversal_1d`: `+0.0248`
- 5d `xs_upward_w_reclaim_12d`: `+0.0100`

### Key finding
The slower horizon changes the relative ordering enough to matter. The core reversal/compression axis remains useful, but the 5d contract elevates `c6` and `c4` and gives the W reclaim family a clearer role than on the 1d target.

**Implication:** do not reuse the current 1d ranking unchanged for the next branch. The next honest step is a 5d workflow / wavefront pass on the horizon-specific ordering.

## F209: H286 Shows The 5d Barrier WF Proxy Does Not Improve The Cross-Sectional Contract Under The Available Extra-Trees Backend (2026-04-05, Session 116)

`H286` ran the existing cross-sectional walk-forward runner on a 5d relative triple-barrier label:
- `future_rel_barrier_5d`
- start date `2015-01-01`
- min-train-years `3`
- backend `extra_trees_classifier`

### Result
The proxy is not promotable:
- avg overall accuracy: `0.5416`
- focal avg edge: `-0.0218`
- focal sig years: `4 / 8`
- focal std edge: `0.1267`

### Key finding
The available tree backend does not turn the 5d barrier contract into a stronger WF. The focal edge is negative and noisy, so this is a park, not a promotion.

**Implication:** keep the 5d label-contract result as offline evidence only for now. If the branch is revisited, try a supported gradient-boosted backend or a different 5d formulation; otherwise move to the next independent branch.

## F210: H287 Shows Lagged Sector Breadth / Rotation Does Not Split The Library Into Fast-Reversal Versus Slow-Continuation Families; The Fast Family Still Wins In Every Quintile (2026-04-05, Session 117)

`H287` tested whether lagged sector breadth / rotation can route the library between the fast reversal family (`c13/c9/c12`) and the slower continuation / reclaim family (`c6/c4/W`).

### Result
The router does not work:
- best state correlation: `+0.0353` on `breadth_level_lag1`
- sign swap: `false`
- q1 gap: `-0.0287`
- q5 gap: `-0.0126`
- fast 1d mean IC: `+0.0321`
- slow 5d mean IC: `+0.0166`
- family gap mean: `-0.0154`

### Key finding
The breadth state does not create a horizon split. The fast family still dominates in every quintile, so the expected fast-vs-slow router does not emerge from lagged sector breadth / rotation.

**Implication:** park the breadth-to-horizon router. If a horizon allocator is still worth testing, it needs a different state variable, such as entry-book replacement pressure rather than sector breadth.

## F211: H288 Shows Entry-Book Breadth And Pressure Correlate With The Family Gap, But The Fast Family Still Wins In Every Quintile (2026-04-05, Session 118)

`H288` tested whether the entry book's own breadth / score-gap state can act as a horizon allocator between the fast reversal family (`c13/c9/c12`) and the slower continuation / reclaim family (`c6/c4/W`).

### Result
The state is weakly predictive, but not enough to route:
- best state correlation: `+0.0679` on `candidate_count_lag1`
- pressure-combo correlation: `+0.0528`
- sign swap: `false`
- q1 gap: `-0.0270`
- q5 gap: `-0.0052`
- family gap mean: `-0.0154`

### Key finding
More candidate breadth does line up with a higher slow-vs-fast family gap, but the fast family still wins in every quintile. That makes this a weak allocator, not a horizon router.

**Implication:** park the breadth-to-horizon router. If this line is revisited, it needs a materially stronger state variable or a different label contract.

## F212: H289 Shows The Marginal-Slot Label Is Monotone But Weak; The Best Existing Proxy Is Selection-Score Gap To Next Candidate (2026-04-05, Session 119)

`H289` relabeled the active-book panel as candidate cycle return minus the weakest held cycle return on the same date, then checked whether existing entry-alpha features still separate the target.

### Result
The label is directionally sensible, but weak:
- best feature: `selection_score_gap_to_next_candidate`
- mean daily IC: `+0.0090`
- positive years: `5 / 7`
- q1 label mean: `+0.0300`
- q5 label mean: `+0.0343`

### Key finding
The marginal-slot label is monotone in the expected direction, but the existing proxies only separate it slightly. The effect is too weak to replace the current contract on its own.

**Implication:** park the marginal-slot label as a weak evidence line. If it is revisited, it likely needs a stronger candidate-selection surface or a news-state overlay.

## F213: H290 Shows The Rebuilt LLM News Surface Has Real Edge Only In The Right State Buckets; Follow-Up And Miss-State News Beat The Pooled Sentiment Surface (2026-04-05, Session 120)

`H290` audited the rebuilt CafeF LLM news surface on the nonzero `2015-2017` window and bucketed the 5-day forward excess-return response by novelty, alignment, authority, and event-time state.

### Result
The pooled sentiment surface is weak or negative overall, but the gated buckets are real:
- nonzero window: `2015-11-13` to `2017-05-31`
- best feature: `llm_sentiment_5d`
- best state kind: `novelty`
- best bucket: `follow`
- mean daily IC: `+0.4796`
- daily hit rate: `0.8667`
- positive years: `1 / 1`
- pooled `llm_sentiment_30d` IC: `-0.0121`
- `novelty = follow` on `llm_sentiment_30d`: `+0.1618`
- `alignment × novelty = miss__new` on `llm_sentiment_30d`: `+0.1350`

### Key finding
LLM news does contain real signal, but the edge lives in the state gate, not in raw sentiment. Follow-up and miss-state news are the useful buckets; beat/new and pooled sentiment are weak or negative.

**Implication:** keep `C15` as offline evidence only for now. Do not treat the LLM surface as deployable on the current active-book years until those years have nonzero coverage.

## F205: H282 Shows The Simple Momentum-Disagreement Subtraction Is Predictive But Not Orthogonal; It Recombines S1 And C9 Instead Of Adding New Information (2026-04-05, Session 111)

`H282` built `xs_mom_disagree = xs_proba_rank - xs_reversal_1d_rank` from the existing `S1` and `C9` surfaces.

### Result
- avg IC: `+0.0854`
- positive years: `11 / 11`
- corr vs `S1`: `+0.5333`
- corr vs `C9`: `-0.6260`

### Key finding
The disagreement feature is strongly predictive, but it fails the orthogonality gate badly. It is best understood as a recombination of existing momentum/reversal information, not as a new independent signal.

**Implication:** do not promote the raw subtraction as a standalone library feature. If revisited, it should be residualized or interaction-only.

## F201: Explicit Upward-W Close Geometry Does Not Survive The Canonical Next-Day Signal Gate; The Only Surviving Evidence Is A Slower 5-Day Reclaim Effect (2026-04-04, Session 107)

Session 107 formalized the user-observed `upward W / double-bottom reclaim` chart pattern into an explicit close-only signal family instead of leaving it as eyeballing.

`H278` tested four daily variants:
- `xs_upward_w_base_12d`
- `xs_upward_w_moderate_12d`
- `xs_upward_w_reclaim_12d`
- `xs_upward_w_reclaim_15d`

### Canonical next-day result
No variant survived the standard next-day standalone gate.

Best canonical row:
- `xs_upward_w_reclaim_12d`
- next-day IC `-0.0003`
- positive years `5 / 11`
- corr vs `S1` `+0.0248`

The naive monotonic interpretation was outright wrong:
- `xs_upward_w_base_12d`
- next-day IC `-0.0060`
- `5d` IC `-0.0104`

### Slower-horizon result
Three reclaim-style variants did pass a forward `5`-day excess-return diagnostic on `2015-2025`:
- `xs_upward_w_reclaim_12d`
  - `5d` IC `+0.0171`
  - positive years `11 / 11`
  - corr vs `S1` `+0.0248`
  - max candidate corr `0.2960` vs `C8`
- `xs_upward_w_reclaim_15d`
  - `5d` IC `+0.0138`
  - positive years `10 / 11`
- `xs_upward_w_moderate_12d`
  - `5d` IC `+0.0117`
  - positive years `9 / 11`

**Key finding:** the eyeballed pattern is not fiction, but it is not a transportable `T+1` daily alpha on the current contract. The real information, if any, sits in a slower reclaim / short-swing horizon, not in the canonical next-day library target.

**Implication:** do not reopen the current daily next-day synthesis queue because of the `upward W` idea. If this family is revisited, do it only as alternative-horizon offline label work or as a future swing / entry contract, not as a live-branch or signal-library continuation.

## F214: H291 Shows News Decay Is Real But The Clean Single-Class Half-Life Contract Fails; `follow_up` Owns 1d While 5d Reorders The Classes (2026-04-05, Session 121)

`H291` audited the raw CafeF LLM novelty stream on the nonzero `2015-2017` window and compared `new`, `follow_up`, and `recycled` stories across `1d`, `5d`, and `30d` forward excess returns.

### Result
The half-life is real, but the clean contract is not:
- best 1d class: `follow_up`
  - mean rho `+0.0196`
  - daily hit rate `0.5256`
  - positive years `2 / 2`
- best 5d class: `follow_up_minus_new`
  - mean rho `+0.0038`
- best 30d class: `new`
  - mean rho `+0.0019`
- `recycled` stays weaker than `follow_up`

### Key finding
News novelty does decay in a learnable way, but the ordering is not stable enough to call it a single clean contract. The short-horizon edge sits in `follow_up`, while the 5d horizon shifts to a spread feature instead of preserving the same class ordering.

**Implication:** keep this as mixed evidence only. If revisited, it should be as a horizon-specific router or spread contract, not as a single novelty class rule.

## F215: H292 Shows Macro Themes Have Real Strength But Not A Clean Sector Router; Real-Estate Theme Dominates The Combined Property Basket (2026-04-05, Session 121)

`H292` audited the LLM macro-theme fractions against matched sector baskets built from the published rotation / event surfaces.

### Result
The macro themes are real, but the router is messy:
- best basket: `regulated_combo`
- best feature: `frac_real_estate_theme`
- mean rho `+0.0988`
- daily hit rate `1.0000`
- positive years `2 / 2`
- banking matched theme is positive but weaker
- regulation theme is weak to negative on its nominal basket

### Key finding
The theme surface does not cleanly switch by sector. The real-estate theme appears to behave like a broad property / balance-sheet state factor and can dominate the combined regulated basket, while the regulation theme itself does not own the combined basket. That is useful information, but it is not a crisp sector router yet.

**Implication:** keep the macro-theme branch parked as mixed evidence. If revisited, it likely needs a sharper target than pooled sector baskets, or a more explicit regime gate.

## F216: H295 Shows Big-Name HOSE Cohorts Preserve Some Recipient Heterogeneity But Lose Too Much Of The Canonical XS Edge To Reopen A Broad Stock-Local Branch (2026-04-08, Session 126)

`H295` formalized the user-proposed "go through the big HOSE names" idea as a bounded audit instead of reopening generic stock-local mining. The test froze the canonical `S1 / H93` probability surface and used a predeclared big-name proxy (`VN30` constituents) to compare the big-name cohort with the rest of the universe.

### Result
The broad big-name cohort is materially weaker than the full universe:
- full-universe IC: `+0.1491`
- big-name cohort IC: `+0.0823` (`55.2%` retention)
- full-universe q5-q1 spread: `+20.86%`
- big-name q5-q1 spread: `+10.84%` (`51.9%` retention)
- full-universe top-5 edge: `+24.16%`
- big-name top-5 edge: `+5.72%` (`23.7%` retention)

The rest of the universe retains essentially all of the signal:
- rest-of-universe IC: `+0.1553`
- rest-of-universe top-5 edge: `+24.00%`

There is some stock-level response heterogeneity inside the big-name proxy, but the ordering is not stable enough to support a new broad stock-local branch:
- qualified big-name stocks with dev+validation coverage: `30 / 30`
- positive dev+validation responders: `26 / 30`
- dev->validation stock-edge rank Spearman: `+0.0701`

### Key finding
The big-name proxy is not dead in the sense of "zero stock-local response", but it is decisively inferior as a cohort and the recipient ordering is too unstable to justify a generic return to single-stock / big-name HOSE search. The real edge still lives outside the large-cap sleeve.

**Implication:** kill the generic big-name stock-local branch under the current contract. If the lab wants an interim blocked-LLM task, the only honest follow-through is a frozen-prior execution/router audit or a very small recurrent-recipient audit around the strongest big-name responders, not a broad stock-by-stock alpha sweep.

## F217: H296 Shows The Simple Liquidity Router Is A Weak Allocator At Best; It Improves Bad Eligible Baselines Slightly But Does Not Solve The Execution Mismatch (2026-04-08, Session 127)

`H296` tested the next blocked-LLM interim idea on the parked H54 execution benchmark. The ranker stayed frozen. The audit only changed execution sleeves:
- large-liquidity names (`top 50` by trailing liquidity rank) -> daily `H=1`
- mid-liquidity names (`51-200`) -> weekly `H=5`
- thin names -> not traded by the router

The comparison used the same eligible-fill contract against two one-size-fits-all baselines:
- eligible-all `H=1`
- eligible-all weekly `H=5`

### Result
The raw universe mismatch is the first problem:
- raw top-5 thin share: `63.25%`

The router is directionally better than the eligible baselines, but still not viable:
- eligible-all `H=1` avg annual net: `-48.38%`
- eligible-all weekly `H=5` avg annual net: `-23.92%`
- router avg annual net: `-22.26%`
- router uplift vs eligible-all `H=1`: `+26.12%`
- router uplift vs eligible-all `H=5`: `+1.66%`
- router positive years: `4 / 11`
- router executed slot share: `32.86%`

### Key finding
The simple liquidity router is not a real execution solution. It only looks better because the eligible one-size-fits-all baselines are themselves already badly damaged once thin names are respected. The routed sleeve still stays negative on average and only converts about one-third of requested slots into actual trades once the slower mid-cap cadence is enforced.

**Implication:** park the liquidity-router idea as weak execution-allocation evidence only. Do not promote it, do not keep extending the same sleeve split, and treat the blocked-LLM interim queue as exhausted.

## F218: H297 Shows Reserve-Scarcity / Blocked-Buy Interactions Do Not Explain Selector Edge Better Than Even The Weak Breadth Baselines (2026-04-08, Session 128)

`H297` formalized the activation-pressure idea as a date-level selector-efficacy audit on the `2019-2025` candidate-panel stack. The target was not raw row-level alpha; it was the daily next-cycle selector edge:
- selected top-`5` mean cycle-relative return
- minus candidate-pool mean cycle-relative return

### Result
The new interaction states failed outright:
- best interaction: `replacement_pressure_combo`
- dev rho: `-0.0282`
- validation rho: `-0.0040`
- confirmation rho: `+0.0043`

Even the weak baseline states were stronger:
- best baseline: `buyable_breadth_all`
- validation rho: `+0.1172`

### Key finding
The current selector edge is not materially explained by reserve scarcity, score-gap compression, or blocked-buy concentration interactions. Under this contract, the activation-pressure story is weaker than the already-weak breadth-style baselines instead of improving on them.

**Implication:** close the activation-pressure interaction branch on the current contract. Do not keep extending this into a selector-state gate family unless a new label or materially different state surface appears.

## F219: H298 Shows Timing Can Create Local Slow-Data Pockets, But The Rescue Is Too Sparse And Too Unstable To Reopen Fundamentals Or Earnings Quality Broadly (2026-04-08, Session 128)

`H298` tested the most honest slow-data follow-through after `H109/H113`: keep the features the same, but only score them inside predeclared report or company-event clocks.

### Result
Conditioning does help locally, but not robustly enough:
- best masked row: `xs_npm_trend_rank × corporate_action_window`
- dev IC: `+0.0111`
- validation IC: `+0.1650`
- confirmation IC: `-0.0855`
- validation mask share: `1.14%`

There are steadier but weaker positives:
- `roe_rank × post_q_end_10d`
- validation IC: `+0.0161`
- confirmation IC: `+0.0408`

### Key finding
The slow-data family is not purely dead for all clocks, but the surviving slices are either too sparse or too unstable to justify reopening fundamentals / earnings quality as an active broad branch. Timing helps as a qualifier, not as a full rescue.

**Implication:** keep conditioned slow data only as constrained offline evidence tied to specific clocks. Do not reopen the broad slow-data branch under the current library contract.

## F220: H299 Shows Reduced-Shape Intraday Still Has Real Information, But It Lives In Disagreement Residuals Rather Than In The Raw Atoms Themselves (2026-04-08, Session 128)

`H299` reran the reduced-shape intraday family as the smallest honest standalone audit on the observed `2023-2025` subset. The question was no longer about a router. It was:
- do any daily atoms survive on their own once measured honestly against `S1 / C4 / C13`?

### Result
The raw atoms still fail or remain too redundant:
- `fade_tension_rank`
  - dev / validation / confirmation IC:
    - `+0.0712 / +0.0869 / +0.0592`
  - max anchor corr:
    - `0.3189`
- raw close/open path ranks stay sign-wrong or unstable

The disagreement residuals do survive:
- `fade_tension_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0318 / +0.0365 / +0.0208`
  - max anchor corr:
    - `0.0668`
- `intraday_shape_core_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0305 / +0.0252 / +0.0154`
  - max anchor corr:
    - `0.0612`

### Key finding
Reduced-shape intraday is not transportable as naive raw shape atoms, but it is not dead either. The real surviving information is the disagreement residue left after removing the current library anchors.

**Implication:** keep the reduced-shape branch alive only as a narrow observed-subset disagreement line. If continued, the next honest step is candidate-library review or a family-local follow-through, not another generic intraday router.

## F221: H300 Shows VN30 Add-Pressure Interactions Are Mechanically Real, But The Actual Boundary Cohort Is Still Weaker Than The Rest Of The Universe (2026-04-08, Session 128)

`H300` tested the one remaining honest VN30 follow-through after the big-name cohort failed:
- no VN30-only sleeve
- no large-cap revival
- only interaction / recipient-state overlays on top of existing signals

### Result
The interaction rows are very strong on paper:
- best interaction: `s1_x_add_pressure`
- dev / validation / confirmation IC:
  - `+0.1100 / +0.0994 / +0.0994`

But the actual boundary cohort remains weaker than the rest:
- boundary `S1` IC:
  - `+0.0748`
- rest-of-universe `S1` IC:
  - `+0.1671`
- boundary `C13` IC:
  - `+0.0217`
- rest-of-universe `C13` IC:
  - `+0.0407`

### Key finding
VN30 boundary pressure behaves like a local interaction modifier, not like a revived large-cap recipient branch. The cohort living near the boundary still carries less signal than the rest of the market, so the branch ceiling stays low.

**Implication:** keep VN30 boundary pressure only as weak local overlay evidence. Do not reopen a broad VN30 or big-name line from this result.

## F222: H301 Shows The CafeF Event-V2 Source Is Real And Much Richer Than The Seed, But Coverage Is Still Far Below The Broad V1 Proxy Surface (2026-04-08, Session 128)

`H301` finally formalized the event-v2 idea as a real data pilot instead of another source audit rerun.

### Result
The extraction quality is strong:
- alias holdout precision:
  - `98.82%`
- seed unique articles:
  - `1,072`
- pilot unique articles:
  - `3,933`
- novel daily share vs v1:
  - `74.48%`

Coverage improves materially versus the strict seed:
- seed 5d held-row coverage:
  - `0.75%`
- pilot 5d held-row coverage:
  - `2.30%`

But it is still far below the broad v1 company proxy:
- v1 5d company-proxy coverage:
  - `15.54%`

### Key finding
The CafeF archive really does support a cleaner company-specific timing source with first-public timestamps and substantial novelty versus `event_surface_daily`. But the current strict alias contract is still too sparse to justify opening a predictive event-v2 branch.

**Implication:** keep event-v2 as acquisition evidence only. The next honest step, if this branch is revisited, is source-hardening / mapping improvement rather than immediate alpha screening.

## F223: H302 Shows The News-Attention Branch Is Still A Hard Data Block, Not An Analytical Open Question (2026-04-08, Session 128)

`H302` implemented the planned novelty × attention disagreement audit with an explicit preflight gate on active-book coverage.

### Result
The blocker is unambiguous:
- active-book window:
  - `2018-01-01 -> 2025-12-31`
- rows on the ticker-day grid:
  - `652,527`
- nonzero LLM rows:
  - `0`

### Key finding
The branch is not waiting on better modeling. It is waiting on data. There is still no usable LLM ticker-day surface in the active-book years, so the novelty × uncrowded-attention question cannot be tested honestly yet.

**Implication:** keep the branch blocked behind `llm-cache-fill` and `llm-feature-refresh`. Do not treat H302 as a mixed research result; it is a clean `SKIP` caused by missing data.

## F224: H303 Shows Fresh Event-V2 Windows Can Help The Best H299 Disagreement Atom Locally, But Not Enough To Beat The Broader V1 Company-Proxy Control, So The Combined Timing Branch Stays Closed (2026-04-08, Session 129)

Session 129 took the smallest honest continuation after `H299` and `H301`:
- same observed `2023-2025` reduced-shape subset from `H299`
- no `2026+` read
- no live-branch change
- no family-specific retuning inside the event surface

The question was:
- are the surviving disagreement atoms really state-transition detectors that sharpen only when `H301` says a fresh company event just arrived?

The best local row was:
- `fade_tension_disagreement × event_v2_5d`

It did improve relative to the unconditional and no-event versions:
- validation IC:
  - `+0.0430`
- confirmation IC:
  - `+0.0455`
- validation uplift vs unconditional `H299`:
  - `+0.0065`
- confirmation uplift vs unconditional `H299`:
  - `+0.0247`
- validation uplift vs no-event complement:
  - `+0.0069`
- confirmation uplift vs no-event complement:
  - `+0.0251`

But it still failed the broader control comparison:
- broad v1 proxy `5d` validation IC:
  - `+0.0513`
- event-v2 `5d` validation uplift vs v1:
  - `-0.0083`

And the second disagreement atom did not survive the same test:
- `intraday_shape_core_disagreement × event_v2_5d`
  - validation uplift vs unconditional:
    - `-0.0123`
  - confirmation uplift vs unconditional:
    - `-0.0008`

So the honest conclusion is not:
- "event timing rescues the intraday disagreement branch"

It is:
- one local interaction exists for the best atom
- but the generic combined branch is still weaker than a broader company-proxy timing control

### Key finding
`H303` does not justify reopening a predictive combined timing branch on generic recent event-v2 windows.

**Implication:** keep `H299` disagreement atoms and `H301` event-v2 as separate offline evidence lines. If another blocked-LLM side branch is reopened, move to `execution-spillover-substitutes`, not to more generic event-conditioned intraday tuning.

## F225: H304 Shows The Execution Mismatch Does Not Cleanly Spill Into Nearest Eligible Substitutes; Any Substitute Effect Is Weak And Too Unstable To Reopen Routing (2026-04-08, Session 130)

Session 130 took the next smallest honest side-branch after `H296` and `H303`:
- same frozen `2019-2025` candidate panel
- no `2026+` read
- no live-branch change
- no re-ranking or router retuning beyond a substitute-beneficiary audit

The question was:
- when the raw top name is blocked or falls into the same thin bucket that broke
  `H296`, does the edge reroute into the nearest eligible substitute in the same
  thesis family or sector?

The stressed states were real enough to test:
- blocked top1 dates:
  - `137`
- thin top1 dates:
  - `1192`
- blocked-or-thin top1 dates:
  - `1238`

But the best recorded row was still weak:
- candidate:
  - `blocked_or_thin_top1 × same_family_or_sector`
- validation top-edge vs other eligible top:
  - `-0.0070`
- confirmation top-edge vs other eligible top:
  - `+0.0036`
- validation hit rate:
  - `46.91%`
- confirmation hit rate:
  - `54.95%`
- validation / confirmation dates:
  - `194 / 91`

No row met the predeclared pass bar:
- pass rows:
  - `0`
- mixed rows:
  - `4`

The pattern is not:
- "substitutes rescue the execution problem"

It is:
- the substitute rows are mostly negative in the main validation window
- a small local `2025` rebound exists
- but that rebound is too weak and too late to rescue the branch honestly

### Key finding
`H304` says the execution mismatch is mostly destructive, not a clean spillover
to the nearest eligible same-family or same-sector substitutes.

**Implication:** keep `H296` as the real branch diagnosis, keep `H304` only as weak local evidence, and if a non-LLM side branch is intentionally reopened move to `insider-event-confirmation`, not to more substitute-routing work.

## F226: H305 Shows Broad Event Confirmation Does Not Cleanly Upgrade C5; Only A Small Rights-Issuance Pocket Survives As Local Sparse-State Evidence (2026-04-09, Session 131)

Session 131 took the next smallest honest current-data branch after `H304`:
- same frozen live branch
- no `2026+` read
- no generic catalyst gate reopening
- only a sparse-row audit on `C5` fire rows inside predeclared event-v1 and
  event-v2 windows

The question was:
- does fresh company-event timing make the `C5` insider relative-size signal
  materially stronger than standalone `C5`?

Standalone `C5` on the `2023-2025` audit window was still positive:
- dev pooled IC:
  - `+0.0131`
- validation pooled IC:
  - `+0.0168`
- confirmation pooled IC:
  - `+0.0164`

The strongest broad conditioned row was the old v1 filing proxy:
- candidate:
  - `v1_recent_any_filing_5d`
- dev / validation / confirmation pooled IC:
  - `+0.0239 / +0.0124 / +0.0228`
- validation uplift vs baseline:
  - `-0.0044`
- confirmation uplift vs baseline:
  - `+0.0064`

That is not a clean conditioned upgrade:
- dev and `2025` improve
- but the main validation window is weaker than standalone `C5`

The broad v2 row is worse:
- candidate:
  - `v2_recent_company_event_article_v2_5d`
- dev / validation / confirmation pooled IC:
  - `-0.0104 / +0.0199 / -0.0124`

So broad event-v2 confirmation is not the answer on current coverage.

The only local surviving pocket was:
- candidate:
  - `v2_rights_issuance_5d`
- dev / validation / confirmation pooled IC:
  - `+0.1060 / +0.0203 / +0.0215`
- validation uplift vs baseline:
  - `+0.0035`
- confirmation uplift vs baseline:
  - `+0.0051`
- validation / confirmation rows:
  - `74 / 57`

That is real enough to keep as local evidence, but not enough to promote:
- pass rows:
  - `0`
- mixed rows:
  - `2`

### Key finding
`H305` says generic event confirmation does not materially upgrade `C5` on the
current `2023-2025` contract. The only surviving interaction is a narrow
rights / issuance pocket that is still too small to reopen a broad branch.

**Implication:** keep `C5 × recent filing` and `C5 × rights_issuance` as local sparse-state evidence only, do not reopen a generic insider-event timing branch, and move the next honest current-data branch to `insider-follow-through-split`.

## F227: H306 Shows Execution Follow-Through Works As A Robustness Rewrite Of C5; Weak Bullish Follow-Through Should Be Downweighted Or Gated (2026-04-09, Session 132)

Session 132 took the next honest continuation after `H305`:
- same long-only branch posture
- no `2026+` read
- same original `H108` `fwd_rel_5d` target
- no new data source
- only predeclared rewrites of the positive side of `C5`

The question was:
- is `xs_ins_exec_rate_5d` merely a dead standalone feature, or does it still
  help as a conditioner on bullish insider-conviction rows?

Raw `C5` remained strong but had one weak spot:
- avg IC:
  - `+0.0374`
- positive years:
  - `10 / 11`
- validation pooled IC:
  - `+0.0808`
- confirmation pooled IC:
  - `+0.0028`

The best predeclared rewrite was the soft follow-through scale:
- candidate:
  - `c5_scale_pos_exec_cap_dev_median`
- dev-defined bullish exec-rate threshold:
  - `0.20`
- avg IC:
  - `+0.0379`
- avg IC retention vs baseline:
  - `101.3%`
- positive years:
  - `11 / 11`
- validation pooled IC:
  - `+0.0740`
- confirmation pooled IC:
  - `+0.0119`
- confirmation uplift vs baseline:
  - `+0.0091`

The simpler hard gate also passed:
- candidate:
  - `c5_gate_pos_exec_gt_0`
- avg IC:
  - `+0.0368`
- avg IC retention vs baseline:
  - `98.6%`
- positive years:
  - `11 / 11`
- confirmation pooled IC:
  - `+0.0088`
- confirmation uplift vs baseline:
  - `+0.0060`

What did **not** survive was the harder or narrower version:
- gating positive `C5` by the dev-median threshold, especially with extra recent-filing restriction, lost too much average IC and did not beat the soft rewrite

So the correct interpretation is not:
- "execution rate is a new standalone insider signal"

It is:
- `exec_rate` is still weak alone
- but weak bullish follow-through pollutes raw `C5`
- the positive side of `C5` becomes more robust when scaled or lightly gated by follow-through

### Key finding
`H306` promotes execution follow-through from a dead standalone feature into a
useful robustness conditioner for the bullish side of `C5`.

**Implication:** update the lab's `C5` interpretation: keep raw `C5` as the primary insider signal, but prefer the soft positive-side follow-through rewrite (`c5_scale_pos_exec_cap_dev_median`) when the branch needs the more confirmation-stable form. Move the next honest current-data queue item to `event-novelty-half-life-without-llm`.

## F228: H307 Shows H301 Novelty Versus Crowding Does Not Survive As A Broad Recent-Window Contract; Only A Sparse Same-Day First-Public Pocket Remains (2026-04-09, Session 133)

Session 133 took the next honest current-data continuation after `H306`:
- same long-only posture
- no `2026+` read
- no new external data source
- only the saved `H301` first-public rows plus the frozen `S1 / H93` surface

The branch question was:
- does the `H301` archive already contain a usable company-event novelty /
  crowding split without waiting for the blocked LLM cache?

The intended broad promotion contract was the recent-window low-repeat state:
- candidate:
  - `recent5_low_repeat20`
- dev avg IC:
  - `+0.1000`
- validation avg IC:
  - `+0.0669`
- confirmation avg IC:
  - `+0.1567`

That looks positive in isolation, but it does **not** clear the honest branch
comparison:
- validation uplift versus crowded recent-window control:
  - `-0.0392`
- confirmation uplift versus crowded recent-window control:
  - `+0.0661`
- validation uplift versus broad v1 proxy:
  - `-0.0109`
- confirmation uplift versus broad v1 proxy:
  - `+0.0523`

So the broad recent-window novelty split fails. The branch only survives as a
much smaller same-day pocket:
- candidate:
  - `event_today_novel20`
- validation avg IC:
  - `+0.0008`
- confirmation avg IC:
  - `+0.1215`
- validation uplift versus crowded same-day follow-up:
  - `+0.0703`
- confirmation uplift versus crowded same-day follow-up:
  - `+0.1107`
- validation / confirmation daily IC rows:
  - `16 / 17`

That is enough to preserve as offline evidence, but not enough to reopen the
branch:
- the signal lives only in a sparse same-day first-public pocket
- the broader `5d` recent-window contract does not beat either crowded v2
  follow-ups or the broad v1 company proxy consistently

### Key finding
`H307` says H301 novelty is structurally real only as a sparse same-day pocket.
It is not broad enough to justify a predictive event-novelty branch under the
current strict alias / coverage contract.

**Implication:** keep same-day first-public versus crowded follow-up as local offline evidence only, do not reopen a broad event-novelty branch, move the next honest current-data queue to `stock-local-predictability-atlas`, and keep `issuer-lexicon-event-surface` as the event-family data-wiring follow-up.

## F229: H308 Shows There Is No Null-Controlled Broad Stock-Local Tail, Only A Small Nominal Recurrent-Recipient Pocket Concentrated In Smoother And More Liquid Names (2026-04-09, Session 134)

Session 134 took the next honest current-data continuation after `H307`:
- same long-only posture
- no `2026+` read
- frozen `S1 / H93` only
- no new alpha family or stock-by-stock retuning
- explicit null control and multiple-testing discipline

The branch question was:
- does an all-HOSE stock-local atlas reveal any non-random stable tail of
  recipient stocks worth deeper interrogation?

The broad answer is no:
- qualified tickers with enough dev / validation / confirmation selected days:
  - `45`
- observed dev->validation rank correlation of recipient edge:
  - `+0.1018`
- null `95th` percentile under within-day permutation:
  - `+0.2588`
- empirical rank-stability p:
  - `0.3134`
- FDR survivors at `q <= 0.10` with positive confirmation edge:
  - `0`

So the atlas does **not** justify reopening a generic stock-local branch.

What survives is only a smaller nominal tail:
- nominal tail rule:
  - empirical `p <= 0.10` on `min(dev, validation)` recipient edge
  - plus positive confirmation edge
- nominal tail count:
  - `7`
- nominal tail tickers:
  - `AAM, VTB, SRF, SHA, VID, TMT, DTA`

That tail is still not null-controlled enough to promote, but it is not random
in structure:
- recipient-edge correlation with overnight-share diagnostic:
  - `-0.5361`
- recipient-edge correlation with zero-range rate:
  - `-0.5706`
- recipient-edge correlation with median traded value:
  - `+0.4491`

So the strongest nominal recurrent recipients are **not** the most jumpy or
illiquid random-walk candidates. They tilt toward smoother and more liquid
names.

### Key finding
`H308` says the lab still does not have an honest broad stock-local alpha
branch. The apparent tail does not survive null control or multiple-testing.
What remains is only a bounded recipient-state diagnostic line around a few
recurrent names.

**Implication:** do not reopen generic stock-local OHLCV hunting. If the lab ever revisits this line, keep it tiny and recipient-first around the nominal tail only. Move the next honest queue item to `issuer-lexicon-event-surface`.

## F230: H309 Shows The H301 Event-V2 Ceiling Was Mostly Mapping, Not Source Quality (2026-04-09, Session 135)

Session 135 took the next honest follow-up after `H308`:
- same long-only posture
- no `2026+` read
- data-wiring only, not a predictive rescue
- issuer metadata proposed aliases, but only aliases validated on `2023-2024`
  known-ticker titles were allowed into the `2025` holdout and coverage audit

The branch question was:
- was `H301` sparse because the source itself was weak, or because the mapping
  contract was too narrow?

`H309` answered that cleanly in favor of mapping:
- metadata candidate aliases proposed from issuer names:
  - `1,191`
- metadata aliases that survived the support / dominance gate:
  - `120`
- `H301` strict holdout assignment share / precision:
  - `43.81% / 98.82%`
- `H309` combined holdout assignment share / precision:
  - `62.37% / 99.17%`
- absolute holdout assignment-share lift:
  - `+18.56pp`
- `H301` strict pilot held-row coverage at `5d`:
  - `2.30%`
- `H309` combined pilot held-row coverage at `5d`:
  - `3.84%`
- absolute `5d` held-row coverage lift:
  - `+1.55pp`
- unique pilot articles:
  - `3,933 -> 6,043`

The new assignments were not random noise. The validated metadata layer
correctly recovered a broad set of real issuer-name forms that the old
title-prefix map missed:
- `Bảo Việt` -> `BVH`
- `Phát Đạt` -> `PDR`
- `Techcombank` -> `TCB`-linked issuer contexts inside `MSN` coverage remained
  separable in the combined map
- `Dabaco` -> `DBC`
- `Đạt Phương` -> `DPG`
- `Searefico` -> `SRF`

Only one observed holdout miss remained in the combined map:
- `HHS` vs `TCH` inside the Hoàng Huy naming family

### Key finding
`H309` says the event-v2 source is richer than `H301` made it look. The main
ceiling was the alias contract, not the CafeF issuer-event archive itself.

**Implication:** the event-v2 branch is honestly reopened for a predictive
re-screen, but not yet for live promotion. Move the next queue item to
`event-v2-predictive-re-screen`, and use the `H309` combined issuer-validated
surface as the new acquisition baseline for any event-family follow-up.

## F231: H310 Shows The Richer H309 Event-V2 Surface Reopens A Real Predictive Branch; Same-Day First-Public And Recent Low-Repeat States Both Survive (2026-04-09, Session 136)

Session 136 took the full post-`H309` spark queue through the smallest honest
predictive rerun:
- same long-only posture
- no `2026+` read
- no live promotion claim
- the combined issuer-validated `H309` surface replaced the old strict-alias
  event-v2 baseline

The branch question was:
- was `H309` only a mapping improvement, or did it make event-v2 broad enough
  to pass the old predictive contract?

`H310` answered yes.

The richer surface was materially larger than the old event-v2 pilots:
- unique mapped event articles:
  - `6,043`
- first-public rows:
  - `7,970`
- unique event tickers:
  - `190`
- observed pilot `5d` held-row coverage:
  - `6.00%`

Two predeclared states passed cleanly:
- same-day first-public `event_today_novel20`
  - validation pooled IC:
    - `+0.1170`
  - confirmation pooled IC:
    - `+0.1829`
  - uplift vs same-day crowded follow-up:
    - `+0.1023 / +0.1043`
  - uplift vs v1 proxy:
    - `+0.0350 / +0.0835`
- recent low-repeat `recent5_low_repeat20`
  - validation pooled IC:
    - `+0.0811`
  - confirmation pooled IC:
    - `+0.1118`
  - uplift vs crowded recent-window follow-up:
    - `+0.0139 / +0.0173`

The old branch failure was therefore not just "event-v2 is weak." Under the
strict-alias contract, the branch was too sparse to judge honestly. Under the
richer issuer-validated contract, both the same-day shock state and a broader
recent low-repeat state survive.

### Key finding
`H310` says event-v2 is now a real predictive branch, not just acquisition
evidence. The strongest surviving contract is still issuer-specific novelty,
especially same-day first-public rows.

**Implication:** reopen event-v2 as a bounded predictive line and move the next
current-data queue to additive / promotion screening of the passed `H310`
states, not to more generic source-hardening.

## F232: H311 And H312 Show Publication-Time And V2-Only Disagreement Effects Are Directionally Real But Not Yet Broad Enough For A Router Branch (2026-04-09, Session 136)

After `H310` reopened event-v2, Session 136 tested two sharper routing stories:
- `H311` publication-time × family
- `H312` v2-only versus v1-only / both disagreement

The idea was:
- if the event edge is mostly timing-specific or disagreement-specific, then
  those refined states should dominate the broader `H310` windows

They did not pass that stronger bar.

For publication time × family:
- best row:
  - `board_management × post_close`
- validation actual / `fwd5` uplift vs intraday:
  - `+0.0271 / +0.0030`
- confirmation actual / `fwd5` uplift vs intraday:
  - `-0.0056 / -0.0006`

So publication-time effects exist, but they are too unstable across years to
promote as a broad router.

For v2-only disagreement:
- `v2_only_5d` validation / confirmation pooled IC:
  - `+0.0939 / +0.0928`
- validation IC uplift vs `v1_only / both`:
  - `+0.0044 / +0.0732`
- confirmation IC uplift vs `v1_only / both`:
  - `-0.0015 / -0.0471`
- validation `fwd5` uplift vs `v1_only`:
  - `-0.0007`

So `v2_only` is directionally better than crowded `both` states, but it does
not beat `v1_only` robustly enough to justify a disagreement router.

### Key finding
The refined router stories are not dead, but they are not the next honest
promotion contract. The broad `H310` states are stronger than the narrower
publication-time and disagreement refinements.

**Implication:** keep publication-time and disagreement only as mixed local
evidence. Advance the broader event-v2 branch before spending more budget on
finer routing splits.

## F233: H313 Shows The Remaining H309 Alias Misses Do Not Justify A Family-Recipient Branch (2026-04-09, Session 136)

`H309` left one visible holdout miss inside the Hoàng Huy naming family, which
raised a legitimate question:
- are some event titles actually group-level signals where a listed family peer
  should receive the response instead of the named ticker?

`H313` tested that as a narrow ambiguity audit rather than a broad new branch:
- ambiguous family aliases derived from HOSE issuer names:
  - `9`
- matched evaluation article rows:
  - `0`
- validation / confirmation rows:
  - `0 / 0`

So the branch does not fail because the named ticker loses to peers. It fails
earlier: there is no surviving ambiguous-family panel large enough to support
the thesis.

### Key finding
The remaining `H309` miss cases are better treated as narrow mapping noise than
as evidence for a family-recipient signal or routing branch.

**Implication:** kill the family-spillover branch on the current contract and
keep exact issuer mapping as the default event-v2 interpretation.

## F234: H314 Shows The Richer H309/H310 Event Surface Still Does Not Broadly Rescue C5 (2026-04-09, Session 136)

Session 136 revisited the old insider-event idea under the stronger event-v2
surface:
- same long-only posture
- no `2026+` read
- `C5` kept as the benchmark; event windows had to beat it, not just look good
  in isolation

The richer surface did sharpen some local pockets:
- baseline `C5` validation / confirmation pooled IC:
  - `+0.0168 / +0.0164`
- best broad mixed row:
  - `v2_same_day_any`
- `v2_same_day_any` validation / confirmation pooled IC:
  - `+0.0988 / +0.0157`
- uplift vs baseline:
  - `+0.0820 / -0.0007`

There were also tiny validation-only pops such as `v2_same_day_earnings`, but
they remained too small to promote.

### Key finding
The richer event surface improves some local insider pockets, but it still does
not turn event-conditioned insider flow into a broad branch. Standalone `C5`
remains the honest default.

**Implication:** keep insider-event confirmation closed as a broad family and
preserve only the small local same-day pockets as offline evidence.

## F235: H315 And H316 Show Official Disclosure Timing And HNX Event Transfer Are Still Data-Blocked Rather Than Analytically Unresolved (2026-04-09, Session 136)

Session 136 also tested the two highest-value event-data extensions that were
supposed to follow if the local data existed:
- official disclosure timestamp history
- HNX event-transfer mapping

The official-source answer was immediate:
- local official-disclosure file hits:
  - `0`
- result:
  - `SKIP`

So the official-disclosure branch is still blocked by missing local data, not
by a missing experiment.

The HNX transfer answer was different but still data-limited:
- HNX tickers in pilot universe:
  - `402`
- training title rows:
  - `94`
- holdout rows:
  - `17`
- combined assigned share / precision:
  - `17.65% / 100.00%`
- validated metadata alias count:
  - `0`

So HNX does not fail on bad precision. It fails because there are far too few
event-title examples to make an honest transfer judgment.

### Key finding
Neither official disclosure timing nor HNX event transfer is ready to become an
active research branch from current local data. Both are still acquisition
problems first.

**Implication:** keep both branches parked behind new data acquisition. Do not
spend current-data research budget on them until the source situation changes.

## F236: H317 Shows H310 Event-V2 Survives As Sparse Predictive Cohort Evidence, But Not As An Additive Promotion Candidate Over The Frozen S1/C4/C13 Core (2026-04-09, Session 137)

After `H310` reopened event-v2 as a real predictive branch, the next honest
question was not another router split. It was:
- do the passed states actually help once forced into a simple additive score on
  top of the current daily core?

`H317` answered that with a narrow but important distinction.

The surviving standalone state is still the same-day first-public signal:
- state:
  - `event_today_novel20`
- validation / confirmation coverage:
  - `0.34% / 0.32%`
- validation / confirmation average IC:
  - `+0.0055 / +0.0026`
- validation / confirmation active-row lift vs daily average:
  - `+0.0314 / +0.0307`
- pooled anchor overlap:
  - corr vs `S1`:
    - `+0.0048`
  - corr vs `C4`:
    - `+0.0053`
  - corr vs `C13`:
    - `-0.0055`

So the same-day first-public state remains real and highly distinct from the
existing core. But it is also extremely sparse.

When pushed into the additive overlay, that sparsity matters:
- frozen core:
  - daily-ranked mean of `S1`, `C4`, and `C13`
- best additive candidate:
  - `core_mul__event_today_novel20__30`
- validation IC delta vs core baseline:
  - `+0.0002`
- validation IC delta vs same-form v1 control:
  - `+0.0019`
- confirmation IC delta vs core baseline:
  - `-0.00003`

That is not enough to justify promotion into a broader additive branch.

The broader recent-window state did even worse:
- `recent5_low_repeat20`
  - negative standalone IC in validation and confirmation
  - additive overlays failed cleanly

### Key finding
`H317` does not kill the reopened event-v2 branch. It sharpens it. The branch
is real as sparse predictive cohort evidence, especially on same-day
first-public rows, but it is not yet additive enough over the frozen
`S1 / C4 / C13` core to justify promotion.

**Implication:** keep `H310` as offline predictive evidence, keep
`event_today_novel20` as the surviving narrow state, and stop the current-data
event-v2 additive promotion path. The next honest non-LLM queue should return
to new-data acquisition rather than another local event retune.

## F237: H318 Shows The Published Market-Attention Surface Is Flat On 2023-2025 And Raw Attention-Proxies Do Not Stabilize An Event-V2 Router (2026-04-09, Session 138)

Session 138 formalized the first current-data branch from the new wild-frontier
queue:
- could market-wide attention congestion explain when the surviving `H310`
  event-v2 states diffuse more slowly?

The intended representation was the published market LLM surface:
- `xs_llm_news_market_daily.parquet`

But the first audit already narrowed the branch:
- `2023-2025` market-daily rows:
  - `748`
- audited column unique counts:
  - all `1`

So the published market-attention surface is effectively flat on the exact
window where the current event-v2 branch lives.

`H318` therefore tested the smallest honest proxy fallback:
- raw CafeF article count by day
- mapped event breadth by day
- high-distraction days:
  - top-tercile raw load plus bottom-tercile mapped share

The only local positive pocket was the primary same-day state under
high-distraction days:
- state:
  - `event_today_novel20`
- validation lag-gap / `fwd5` uplift vs not-high days:
  - `+0.0301 / +0.0154`
- confirmation lag-gap / `fwd5` uplift vs not-high days:
  - `-0.0412 / -0.0057`

So the slower-diffusion story appears in validation and then breaks in
confirmation. No proxy passed on the secondary recent-window state:
- best secondary row:
  - `recent5_low_repeat20 × high_event_breadth`
- verdict:
  - failed

### Key finding
The current local stack does not support a promotable market-attention router
for the reopened event-v2 branch. The published market-LLM surface is flat on
`2023-2025`, and the raw archive fallback produces only unstable local
separation.

**Implication:** keep attention congestion only as weak offline evidence. Do
not spend more current-data budget on this branch until a richer market-wide
attention source exists. Move the next current-data creative queue item to
`ownership-network-contagion`.

## F238: H319 Shows Pre-2023 Ownership Links Carry Only Weak Neighbor-C5 Spillover; Event-V2 Contagion Does Not Survive As A Broad Graph Branch (2026-04-09, Session 139)

Session 139 tested the next current-data creative line after `H318`:
- can a static ownership graph carry pure cross-ticker spillover after the
  target ticker's own direct event-v2 and insider shocks are removed?

The graph was intentionally predeclared and conservative:
- source window:
  - `2015-2022`
- edge types:
  - shared `ShareHolderCode`
  - shared `TransactionMan`
  - small issuer-family alias layer
- entity degree gate:
  - `2..20`
- evaluation panel:
  - `2023-2025`
- target rows:
  - only rows with no own `event_today_novel20`, no own
    `recent5_low_repeat20`, and no own positive `C5`

So the test was not asking whether linked names move together in general. It
was asking whether neighbor shocks alone create a recipient state.

The answer was mostly no.

For neighbor same-day event-v2 shock on the union graph:
- state:
  - `nbr_event`
- validation / confirmation active days:
  - `171 / 158`
- validation / confirmation actual lift:
  - `-0.0053 / -0.0106`
- validation / confirmation `fwd5` lift:
  - `+0.0024 / -0.0002`

So broad neighbor event contagion fails.

The only surviving line was weak neighbor insider contagion:
- state:
  - `nbr_c5`
- validation / confirmation active days:
  - `235 / 236`
- validation / confirmation actual lift:
  - `+0.0031 / +0.0127`
- validation / confirmation `fwd5` lift:
  - `+0.0001 / +0.0011`

That is directionally real enough to keep as offline evidence, but it is still
too small to justify a graph router or additive branch.

### Key finding
Pre-2023 ownership links do not reopen a broad graph-based spillover branch on
the current local stack. The event-contagion story fails, and the only durable
trace is a weak neighbor-`C5` effect.

**Implication:** keep ownership-network contagion only as weak offline
evidence. Do not promote it into a routing or library branch. Move the next
current-data creative queue item to `criticality-order-parameter`.

## F239: H320 Shows Raw Criticality Order Parameters Do Not Beat Recent-Efficacy Activation Memory (2026-04-09, Session 140)

Session 140 tested the next current-data creative line after `H319`:
- can raw market-criticality proxies explain next-cycle selector efficacy
  beyond the incumbent short-memory activation baseline?

The branch built daily order parameters from:
- raw daily OHLCV under `data/stock/`
- raw limit-hit shares using the shared `7%` daily limit convention
- gap/intraday same-direction alignment
- cross-sectional synchrony and large-move pressure
- dispersion / tail-spread / susceptibility terms
- the maintained `activation_meta_daily.parquet` selector-efficacy spine

The honest benchmark was deliberately hard:
- target:
  - `full_future_cycle_relative_return`
- incumbent baseline:
  - `full_recent_cycle_relative_return_ewm3`
- residual target:
  - target minus a dev-fit linear model on the incumbent baseline
- protocol:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation

The incumbent activation-memory state remained very strong:
- validation / confirmation rho vs target:
  - `+0.6126 / +0.6557`

No raw criticality proxy cleared the promotion bar. The best surviving trace was
adverse rather than constructive:
- feature:
  - `gap_alignment_pressure`
- validation / confirmation residual rho:
  - `-0.0431 / -0.1246`
- validation / confirmation high-minus-not residual lift:
  - `-0.0077 / -0.0083`
- validation / confirmation high-baseline conditioned residual lift:
  - `-0.0054 / -0.0410`

So high same-direction gap/intraday pressure appears to subtract from the
incumbent high-efficacy state, especially in `2025`, but this is still weak
offline meta-state evidence rather than a promotable router.

### Key finding
The complex-systems activation thesis does not currently beat the simpler
selector-efficacy memory model. Raw OHLCV criticality fields may contain a weak
adverse state, but they do not justify a new activation branch on the current
data.

**Implication:** keep the live activation-memory baseline unchanged. Keep
`gap_alignment_pressure` only as offline adverse-state evidence. Do not open a
raw OHLCV criticality router or additive overlay. Move the next current-data
creative queue item to `hawkes-disclosure-cascade`.

## F240: H321 Shows Event-V2 Disclosures Have A Sparse Self-Exciting Cascade State (2026-04-09, Session 141)

Session 141 tested the next current-data creative line after `H320`:
- can the H310 event-v2 surface be represented as a self-exciting disclosure
  process rather than only a simple novelty / repeat-count window?

The test used the issuer-validated H310 event-v2 artifacts:
- article-level timestamped event rows:
  - `6,043` unique articles
  - `190` mapped tickers
- daily first-public rows:
  - `7,970`
- evaluation panel:
  - `2023-2025`
  - `258,375` ticker-day rows
  - `394` tickers
  - `748` trading dates

The branch did not fit a full Hawkes likelihood. It used the smallest honest
point-process proxy:
- decayed prior event-article counts at ticker level
- decayed prior event-article counts at sector-peer level
- decay windows:
  - `tau=2`
  - `tau=5`
  - `tau=10`
- self-excitation acceleration:
  - short-horizon intensity minus long-horizon intensity

The winning state was:
- `today_self_accel_high`
- definition:
  - same-day H310 event-v2 row
  - high fast self-excitation acceleration, using dev thresholds
- matched H310 control:
  - `event_today_follow20`

It passed in both validation and confirmation:
- validation / confirmation daily IC rows:
  - `30 / 31`
- validation / confirmation daily IC:
  - `+0.2395 / +0.3215`
- validation / confirmation IC uplift vs matched control:
  - `+0.1831 / +0.2290`
- validation / confirmation actual uplift vs matched control:
  - `+0.0369 / +0.0329`
- validation / confirmation `fwd5` uplift vs matched control:
  - `+0.0014 / +0.0009`

This is materially different from the broad event-v2 additive result in H317:
- H317 said broad `event_today_novel20` was real but not additive enough.
- H321 says the event surface has a sharper cascade-state representation that
  may be worth an additive retest.

### Key finding
Event-v2 disclosure timing is not exhausted by novelty/crowding windows. A
sparse self-excitation acceleration state survives cleanly against the matched
H310 follow-up control.

**Implication:** reopen event-v2 only as a narrow cascade-state candidate. Do
not promote `today_self_accel_high` directly into the live library. The next
honest test is `cascade-additive-screen` against the frozen `S1 / C4 / C13`
core and the H310 event-state controls.

## F241: H322 Keeps The H321 Cascade State As Offline Timing Evidence, Not An Additive Promotion (2026-04-09, Session 142)

Session 142 tested the immediate follow-up after the H321 pass:
- does `today_self_accel_high` add enough value over the frozen
  `S1 / C4 / C13` core to justify promotion?

The test reused:
- the saved H321 panel
- `xs_rl_signal_matrix.parquet`
- the same simple multiplicative core-overlay pattern used in H317

The H321 state stayed real as a sparse standalone timing cohort:
- state:
  - `today_self_accel_high`
- validation / confirmation binary-state IC:
  - `+0.0046 / +0.0072`
- validation / confirmation active lift:
  - `+0.0288 / +0.0570`
- pooled correlations with core ranks:
  - `S1`: `+0.0066`
  - `C4`: `+0.0068`
  - `C13`: `-0.0059`

So the state is nearly orthogonal and has a meaningful active-row response.
But the full-universe additive effect is tiny.

The best additive overlay was:
- variant:
  - `core_mul__today_self_accel_high__50`
- validation / confirmation IC delta vs frozen core:
  - `+0.00015 / +0.00005`
- validation / confirmation spread delta vs frozen core:
  - `+0.00018 / -0.00021`
- validation / confirmation IC delta vs matched H310 follow-up control:
  - `+0.00076 / +0.00044`
- validation / confirmation IC delta vs H310 novelty control:
  - `-0.00012 / +0.00017`

This fails the promotion bar. The result is not a contradiction of H321: it
says the cascade label is a useful sparse event-timing diagnostic, but too
sparse to materially improve the frozen daily ranker through a blunt overlay.

### Key finding
The self-exciting event-v2 cascade state is real but not promotable as a core
additive feature on the current representation. H322 repeats the H317 lesson:
event-v2 timing can produce strong cohorts, but the current frozen core does
not benefit enough from simple event overlays.

**Implication:** keep `today_self_accel_high` as offline timing evidence only.
Do not continue local event-v2 overlay tuning on the current core. Move the
next current-data creative queue item to `policy-beneficiary-graph`, while the
highest-value acquisition queue remains `historical-foreign-flow-source`.

## F242: H323 Finds A Usable CafeF Public-Investment Corpus But No Promotable Beneficiary Router (2026-04-09, Session 143)

Session 143 tested the first political-economy beneficiary branch:
- can raw CafeF public-investment / infrastructure policy news predict
  explicitly mapped listed beneficiaries?

The branch used a deliberately tiny manual map:
- direct beneficiaries:
  - `Xây dựng và Vật liệu`
  - `55` tickers
- second-order beneficiaries:
  - `Bất động sản`
  - `57` tickers
- rest basket:
  - `282` tickers

The local source was not the blocker. A predeclared title / summary keyword
scan of the raw CafeF archive found:
- unique policy articles:
  - `5,964`
- trading signal days:
  - `744`
- article assignment:
  - first trading day on or after publication
- evaluation window:
  - `2023-2025`

The best state was:
- `policy_total_5d_high`
- definition:
  - high combined public-investment / infrastructure article count over the
    trailing `5d`, using the dev `q80` threshold

It showed weak beneficiary-state structure:
- validation / confirmation active days:
  - `96 / 211`
- validation / confirmation direct public-works `fwd5` edge vs rest:
  - `+0.0010 / +0.0023`
- validation / confirmation `fwd5` diff-in-diff:
  - `+0.0032 / +0.0007`

But it failed the promotion bar:
- validation / confirmation actual diff-in-diff:
  - `+0.0027 / -0.0006`
- validation / confirmation direct-minus-real-estate `fwd5`:
  - `+0.0048 / -0.0012`

So the direct public-works basket does not cleanly own the policy response.
Real estate catches or beats the direct basket in confirmation, which is
consistent with the older H292 lesson that macro / policy themes behave more
like broad balance-sheet or property states than crisp sector routers.

### Key finding
The local CafeF corpus is sufficient for a public-investment policy pilot, but
the simple manual beneficiary graph is not strong enough to promote. The
political-economy channel remains interesting as a data / mapping problem, not
as a current direct-public-works router.

**Implication:** keep the raw policy corpus and H323 daily panel as offline
evidence. Do not expand the branch without a better policy-event source or a
more explicit beneficiary graph. Move the next honest queue item to
`historical-foreign-flow-source`.

## F243: H324 Confirms Real Historical Foreign Flow Is Still Source-Blocked Locally (2026-04-09, Session 144)

Session 144 tested the acquisition queue item after H323:
- is there any real historical per-ticker foreign buy/sell or foreign-room
  table available locally?

The answer is no.

The local source-gate scan found only two relevant maintained surfaces:
- `data/features/xs_foreign_demand_daily.parquet`
- `data/fx-commodities/fx_commodities_vnm_etf_1D.parquet`

The real-source counts were:
- real historical per-ticker foreign-flow candidates:
  - `0`
- schema fragments with foreign buy/sell/room fields:
  - `0`

The existing surfaces are proxies:
- `xs_foreign_demand_daily.parquet`
  - `826,404` rows
  - `394` tickers
  - `2015-01-05` to `2025-12-31`
  - VNM ETF affinity / premium proxy
  - archive-only after H110 failed
- `fx_commodities_vnm_etf_1D.parquet`
  - `4,182` rows
  - `2009-08-14` to `2026-03-31`
  - date-level ETF price surface
  - not per-ticker foreign flow

The live vnstock probe with network permission did not unblock the branch:
- installed package:
  - `vnstock 3.5.0`
- no available method:
  - `quote.history_foreign_ownership`
- current-day board fields:
  - available through `price_board`
  - not backtestable as historical daily data

So this remains the same scientific state as F59, but now with a fresh
source-gate artifact after the recent acquisition queue reopened the question.

### Key finding
Historical foreign flow is not falsified as a mechanism, but it is still not
testable in this workspace. The only local surfaces are the already-failed VNM
ETF proxy family.

**Implication:** do not retest H110-style proxies as the historical foreign-flow
branch. Keep H95 blocked until a real historical source is acquired, or start a
forward-only collector for current-day board foreign fields. Move the next
acquisition queue item to `queueing-open-fill-source`.

## F244: H325 Confirms Queue / Open-Fill Alpha Is Source-Blocked By Missing Microstructure History (2026-04-09, Session 145)

Session 145 tested the next acquisition queue item after H324:
- does the canonical warehouse contain any historical auction, order-book,
  opening-queue, or fine-minute source that can honestly test queue imbalance
  / open-fill pain?

The answer is no.

The source-gate scan found:
- source-looking paths:
  - `13,637`
- true historical queue / order-book candidates:
  - `0`
- true fine-minute candidates:
  - `0`

The local intraday estate is broad but reduced:
- CafeF hourly yearly parts:
  - `11,996`
- raw CafeF hourly files:
  - `404`
- adjusted CafeF hourly files:
  - `404`
- legacy shallow hourly files:
  - `9`
- adjustment factor files:
  - `810`
- derived daily intraday summaries:
  - `1`

Representative sampled hourly schemas were only:
- `time`
- `open`
- `high`
- `low`
- `close`
- `volume`

The sampled hourly shape confirms the resolution limit:
- median bars/day:
  - `4.0`
- max bars/day:
  - `5`

So the current source can support reduced-shape intraday research, but not the
microstructure question. It cannot measure bid/ask imbalance, queued buy/sell
pressure at the open, order-book depth, order arrival, or a fine-minute tape.

The first implementation pass also caught a useful failure mode: broad substring
matching can mistake `ticker`, ticker `BID`, `order_date`, `insider`, and
`barrier_depth` for microstructure evidence. H325 now uses stricter token-level
classification so the source gate does not promote false positives.

### Key finding
Queue / open-fill alpha is not falsified as a mechanism, but it is not testable
with the current local data. Hourly OHLCV and price-limit blocked-buy proxies
must not be relabeled as queue imbalance.

**Implication:** keep queue/open-fill research acquisition-blocked until a real
auction/order-book/fine-minute source is acquired. Move the next cheap data
unlock to `forward-foreign-flow-collector`, with explicit metadata that the
collector will be forward-only and not immediately backtestable.

## F245: H326 Starts A Forward-Only Foreign-Flow Archive From Current-Day VCI Board Fields (2026-04-09, Session 146)

Session 146 implemented the only cheap continuation after H324 confirmed real
historical foreign flow is unavailable:
- start collecting current-day board foreign fields forward-only
- keep the contract explicitly non-backtestable until enough future history
  accrues

The producer is:
- `data_tools/collect_forward_foreign_flow.py`

The canonical root is:
- `data/foreign_flow_forward/vci_price_board/`

The written surfaces are:
- `snapshots/YYYY-MM-DD/vci_price_board_foreign_flow_YYYYMMDDTHHMMSSZ.parquet`
- `latest_snapshot.parquet`
- `daily_latest.parquet`
- `manifest.json`

The contract keeps these normalized fields:
- `collected_at_utc`
- `ticker`
- `trading_date`
- `current_room`
- `total_room`
- `foreign_buy_volume`
- `foreign_sell_volume`
- `foreign_net_volume`
- `foreign_buy_value`
- `foreign_sell_value`
- `foreign_net_value`
- `foreign_room_used_ratio`

H326 validated two things:
- the normalizer correctly handles vnstock's MultiIndex `price_board` schema
- the live VCI board path can produce a full local-HOSE snapshot

The first full run captured:
- rows:
  - `404`
- tickers:
  - `404`
- board trading date:
  - `2026-04-09`
- failed chunks:
  - `0`

Example current-day extremes from the first snapshot:
- largest positive net foreign value:
  - `HPG +482.15B VND`
- largest negative net foreign value:
  - `VPL -3.284T VND`

This is not an alpha result. With one collected day, there is no honest
historical test. The value of H326 is that the workspace is no longer passively
blocked on this surface: every future run adds real forward evidence.

### Key finding
Current-day VCI board fields are sufficient to start a real per-ticker
foreign-flow archive, but only forward from collection time. This is a data
acquisition pass, not a predictive-signal promotion.

**Implication:** run the collector daily after market close. Do not build or
backtest foreign-flow features from this surface until enough forward days
exist and a source-quality audit passes.

## F246: CafeF GDKhoiNgoai Exposes Historical Daily Foreign Flow And Reopens H95 Source Acquisition (2026-04-09, Session 146)

The earlier H324 conclusion was too narrow. It correctly showed that vnstock /
VCI did not expose historical per-ticker foreign flow locally, but it did not
mean the broader source class was absent.

A direct CafeF page + endpoint probe found that the stock-history `Khối ngoại`
tab is backed by:
- `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx`

The endpoint returns per-ticker daily rows including:
- `KLMua`
- `GtMua`
- `KLBan`
- `GtBan`
- `KLGDRong`
- `GTDGRong`
- `RoomConLai`
- `DangSoHuu`
- `ThayDoi`

Representative live probes confirmed real historical depth:
- `FPT`
  - returned rows:
    - `4,769`
  - oldest observed date:
    - `2006-12-13`
- `VCB`
  - oldest observed date:
    - `2009-06-30`
- `HPG`
  - oldest observed date:
    - `2007-03-01`
- `ACB`
  - oldest observed date:
    - `2007-01-02`

Session 146 then wired a raw historical fetcher:
- `data_tools/fetch_cafef_foreign_flow.py`

Its raw canonical outputs are:
- `data/foreign_flow/cafef/per_ticker/<TICKER>.parquet`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/foreign_flow/cafef/manifest.json`

The first live validation pull covered:
- tickers:
  - `2`
- rows:
  - `5,604`
- window:
  - `2015-01-01` to `2026-04-09`
- failures:
  - `0`

### Key finding
Historical foreign flow is available after all, but via CafeF rather than
vnstock. The source question is now resolved; the remaining work is source
quality audit and honest signal testing.

**Implication:** unblock `H95` from acquisition-blocked status. The next honest
step is not another source search. It is:
- align CafeF foreign-flow rows to the local trading calendar
- quantify ticker/date coverage and missingness
- test the smallest honest raw and lagged foreign-flow features

## F247: H327 Source-Audits CafeF Foreign Flow As Usable But Rejects The First Raw Feature Screen (2026-04-09, Session 147)

Session 147 completed the first honest source-quality audit and raw feature
screen after the CafeF `GDKhoiNgoai` source was found.

The full local backfill contains:
- tickers:
  - `404`
- rows:
  - `1,353,462`
- date range:
  - `2001-04-02` to `2026-04-09`
- fetch failures:
  - `0`

The producer is:
- `data_tools/fetch_cafef_foreign_flow.py`

Two fetcher defects were fixed during the monitored backfill:
- partial probe caches were not enough to prove full requested coverage
  - per-ticker `.meta.json` coverage sidecars now record the requested window
- subset reruns could clobber the combined panel with only the requested names
  - the combined panel is now rebuilt from all per-ticker caches on disk

`H327` then audited the source against the local stock calendar over
`2015-2025`:
- row coverage:
  - `98.80%`
- tickers with any flow:
  - `399`
- tickers with at least `60%` coverage:
  - `399`
- duplicate ticker-day rows:
  - `0`
- net volume mismatches:
  - `0`
- net value mismatches:
  - `0`

Known source gaps remain:
- `AAA`
- `YBM`
- `YEG`

These names had local stock-history rows in the `2015-2025` audit window but no
CafeF foreign-flow rows in that window.

The first predictive screen used the frozen 2015-2025 protocol:
- dev:
  - `2015-2022`
- validation:
  - `2023-2024`
- confirmation:
  - `2025`
- no tuning:
  - `2026+`

The best raw feature was:
- `xs_ff_room_scarcity_rank`

It produced:
- dev IC:
  - `+0.0117`
- dev directional years:
  - `7 / 8`
- validation IC:
  - `+0.0074`
- confirmation IC:
  - `-0.0048`
- corr vs `S1`:
  - `-0.0028`

### Key finding
The CafeF foreign-flow source is research-usable, but the first raw buy/sell/net
flow and room-scarcity feature set is not promotable. The near-pass is
orthogonal to `S1`, but it fails 2025 confirmation.

**Implication:** `H95` is no longer source-blocked, but raw foreign-flow ranks
are not a signal-library candidate. Do not publish a feature from H327.

## F248: H328 Shows High Foreign Participation And Room Scarcity Do Not Rescue Raw CafeF Flow Ranks (2026-04-09, Session 147)

Session 147 ran one constrained follow-up after H327:
- test whether raw foreign-flow ranks only work inside high foreign
  participation states
- test whether raw foreign-flow ranks only work inside high room-scarcity states

The screen reused the same honest predictive protocol:
- dev:
  - `2015-2022`
- validation:
  - `2023-2024`
- confirmation:
  - `2025`
- no tuning:
  - `2026+`

The tested states were:
- `foreign_participation_top30`
- `foreign_participation_top20`
- `room_scarcity_top30`
- `room_scarcity_top20`

The tested raw flow feature families were small and predeclared:
- `xs_ff_net_vol_share_1d_rank`
- `xs_ff_net_vol_share_1d_lag1_rank`
- `xs_ff_net_vol_share_5d_rank`
- `xs_ff_net_vol_share_5d_lag1_rank`
- `xs_ff_buy_share_5d_rank`
- `xs_ff_sell_share_5d_rank`

The best row was:
- state:
  - `foreign_participation_top30`
- feature:
  - `xs_ff_buy_share_5d_rank`
- orientation:
  - negative
- dev IC:
  - `-0.0088`
- validation IC:
  - `-0.0147`
- confirmation IC:
  - `+0.0079`
- corr vs `S1`:
  - `-0.0398`

### Key finding
High foreign participation and high room scarcity do not rescue simple CafeF
foreign-flow ranks. The strongest conditioned row flips sign in 2025, and the
dev IC is below the standalone signal gate.

**Implication:** close the raw buy/sell/net-rank path. If `H95` continues, it
must be a materially different thesis such as:
- room-change events
- ownership-regime transitions
- near-limit foreign-room discontinuities
- sector-specific foreign ownership pressure

## F249: H329 Shows Title-Sequence Novelty Distillation Recovers Some Teacher Structure But Does Not Preserve The Short-Horizon Novelty Contract (2026-04-09, Session 148)

Session 148 ran the first honest cheap non-API continuation from the LLM-news
branch:
- do not retry the dead keyword-sentiment path
- do not claim a full deterministic replacement up front
- test whether deterministic title / summary / article-sequence rules can
  recover enough of the saved LLM novelty labels to preserve the novelty
  half-life evidence from `H290/H291`

The teacher surface was restricted to ticker-tagged cached rows with usable
novelty labels:
- teacher article rows:
  - `12,295`
- teacher cached days:
  - `728`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- holdout slice:
  - `2017`

The deterministic classifier did recover real novelty structure versus a naive
baseline:
- holdout macro-F1:
  - `0.3965`
- naive `always_new` macro-F1:
  - `0.3107`
- holdout macro-F1 delta:
  - `+0.0858`
- holdout balanced accuracy:
  - `0.3971`

But the hard short-horizon novelty state remained weak:
- holdout `follow_up` precision:
  - `0.1255`
- holdout `follow_up` recall:
  - `0.0673`
- holdout `follow_up` F1:
  - `0.0876`

The more important test was whether the reconstructed novelty labels preserved
the saved teacher-alpha directions:
- preserved key contracts:
  - `1 / 3`
- `1d follow_up` teacher / deterministic IC:
  - `+0.0023 / -0.0142`
- `5d follow_up_minus_new` teacher / deterministic IC:
  - `-0.0025 / +0.0053`
- `30d new` teacher / deterministic IC:
  - `+0.0108 / +0.0092`

### Key finding
Title-sequence novelty distillation is not a dead end, because it recovers
meaningful teacher-label structure above a naive baseline. But it is not strong
enough to replace the LLM novelty branch on its own: the key `follow_up`
bucket remains too lossy, and only one of the three key novelty contracts keeps
the teacher sign.

**Implication:** do not continue retuning novelty-only deterministic rules in
isolation. If the cheap branch continues, move to:
- hybrid deterministic-first routing with API only for ambiguous rows
- broader teacher-state distillation on more lexical fields such as
  `event_type`, `expectation_alignment`, `impact_scope`, and
  `source_authority`

## F250: H330 Shows A Hybrid Novelty Cascade Can Save Large API Share, But It Still Fails The `1d follow_up` Contract (2026-04-10, Session 149)

Session 149 ran the next honest cheap non-API continuation after `H329`:
- keep the novelty rules from `H329`
- use them only as a deterministic-first confidence screen
- route the ambiguous rows back to the teacher as an oracle fallback
- test whether that hybrid contract preserves the saved novelty-alpha evidence
  while reducing API demand materially

The audit used the same ticker-tagged teacher window:
- teacher article rows:
  - `12,295`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- policy ladder:
  - `5` predeclared hybrid policies from strict to aggressive

The hybrid cascade did recover much more teacher-label structure than the pure
deterministic student:
- pure deterministic holdout macro-F1:
  - `0.3965`
- best hybrid holdout macro-F1:
  - `0.8840`
- pure deterministic holdout `follow_up` F1:
  - `0.0876`
- best hybrid holdout `follow_up` F1:
  - `0.8235`

It also showed that a large share of API traffic can be avoided:
- best cost / contract trade-off policy:
  - `aggressive_triple`
- best-policy API article share:
  - `0.2028`
- best-policy API text share:
  - `0.2035`
- best-policy preserved contracts:
  - `2 / 3`

But the more important result is what failed to recover:
- every tested hybrid policy preserved only:
  - `2 / 3`
- the failed contract in every policy was:
  - `1d follow_up`
- even the strict new-only cascade, which routed:
  - `58.9%` of articles
  - `60.2%` of article text
  back to the teacher, still left `1d follow_up` negative

### Key finding
The hybrid novelty cascade is real as a cost-reduction mechanism, but it still
does not preserve the short-horizon novelty contract that matters most. The
remaining information loss is concentrated in the `1d follow_up` line, and more
novelty-only cascade retuning is unlikely to change that.

**Implication:** do not continue the cheap branch with more novelty-only
distillation or cascade tuning. If the surrogate branch continues, move to:
- more lexical teacher fields such as `event_type`,
  `expectation_alignment`, `impact_scope`, and `source_authority`
- disagreement-residual tests that treat the teacher-fallback tail itself as a
  possible signal source

## F251: H331 Shows Direct Lexical Event-Family Routing Recovers Some Structure, But It Does Not Beat The Old Keyword Baseline Or Preserve The Key Authority State (2026-04-10, Session 150)

Session 150 ran the next honest cheap non-API continuation after `H330`:
- move off novelty-only routing
- test more lexical teacher fields directly from article text
- compare the rebuilt field routers with both teacher-state preservation and
  the old keyword-news baseline

The audited teacher surface stayed on the same ticker-tagged window:
- teacher article rows:
  - `12,378`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- tested field families:
  - `source_authority`
  - `expectation_alignment`
  - `impact_scope`
  - sparse focused `event_type`

The lexical router did recover meaningful article-level structure on several
fields:
- `source_authority` held-out macro-F1 delta vs train-majority:
  - `+0.1514`
- `impact_scope` held-out macro-F1 delta:
  - `+0.4364`
- sparse `event_type` held-out macro-F1 delta:
  - `+0.4458`
- preserved field champions:
  - `3 / 4`

But the broad branch still failed on the parts that mattered most:
- failed teacher champion:
  - `source_authority__rumor_source`
- teacher / deterministic mean IC:
  - `+0.0678 / -0.0848`
- weak field:
  - `expectation_alignment`
- its held-out macro-F1 delta:
  - `+0.0244`

The final bar was not cleared against the dead keyword path:
- best deterministic feature:
  - `source_authority__rumor_source`
  - abs IC `0.0848`
- best keyword baseline feature:
  - `sentiment_score`
  - abs IC `0.1303`
  - matched rows `609`

### Key finding
Direct lexical routing is not empty. It can recover real structure in
`impact_scope`, some authority buckets, and the densest event-type families.
But it still does not reopen the cheap branch as a broad replacement path: the
most important authority state flips sign, `expectation_alignment` stays weak,
and the best deterministic feature still trails the old keyword-news baseline
on the audited `5d` target.

**Implication:** close the direct lexical-router continuation on the current
contract. If the cheap branch continues, move to:
- disagreement-residual tests using student-teacher gaps or teacher-fallback
  rows themselves
- more selective narrow follow-ups only if a future branch needs one isolated
  lexical field rather than a broad replacement surface
