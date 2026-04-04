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
