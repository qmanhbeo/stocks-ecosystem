## F91: The RL Signal Library Does Not Yet Monetize as a Realistic Long-Only Portfolio (2026-03-28, Session 45)

H135 tested the promoted RL signal library as a deterministic long-only portfolio under the
workspace execution contract:
- signal observed at `T` close
- execute at `T+1` open
- cannot sell before `T+3` close / `T+4` open
- zero-volume and ceiling/floor tradability blocks active
- 0.30% round-trip cost (`0.15%` buy + `0.15%` sell)
- top-5 equal-weight portfolio
- 3-day rebalance cadence
- no ADV capacity cap in the baseline run

**Result:** the current library does **not** survive as a standalone long-only money machine.

| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio | Max DD | Positive Years |
|---|---:|---:|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 | -88.84% | 4/11 |
| `recent_core` (`S1+C10-C14`) | -83.44% | -15.21% | -94.88% | -0.67 | -96.19% | 3/11 |
| `full_library` (`S1+C4-C14`) | **-9.76%** | **-0.94%** | **-72.08%** | **-0.24** | **-77.25%** | **5/11** |

The benchmark VNINDEX compounded to **+223.17%** over the same 2015-2025 window.

**Key finding:** the signal library is still useful as a diverse state surface, but it is not yet a
plug-and-play long-only portfolio strategy under realistic execution. That means **RL is not the
next monetization shortcut**. The blocking problem is portfolio construction and execution reality,
not lack of more standalone signal IC.

**Implication:** before more RL training, the lab must search for a deterministic construction that
actually survives `T+2.5` settlement, turnover, and tradability constraints.

---
## F92: Capacity Is a First-Order Stress Variable, Not a Safe Default Constant (2026-03-28, Session 45)

A separate H135 stress run added a simple ADV participation cap:
- portfolio notional = `1B VND`
- max participation = `1%` of `ADV20`

Under that constraint, the portfolio became almost entirely uninvested:

| Strategy | Avg Cash Weight | Avg Holdings | Total Return |
|---|---:|---:|---:|
| `s1_only` | 99.88% | 12.52 | -1.08% |
| `recent_core` | 99.97% | 9.69 | -0.04% |
| `full_library` | 99.90% | 9.47 | -0.92% |

**Key finding:** a seemingly modest capacity rule can dominate the result on this historical HOSE
universe. The right interpretation is **not** “the strategy is safe because losses are small.” The
real interpretation is that the backtest is mostly sitting in cash because capacity has become the
main bottleneck.

**Implication:** capacity must be treated as a sweep / stress dimension, not hard-coded as the one
true default. The next honest step is a grid over portfolio notional and ADV participation, so the
lab can see where the strategy is actually deployable instead of arguing from a single arbitrary cap.

---
## F93: The Initial H135 Library-Blend Failure Was Caused by a Signal-Scale Bug, Not by the Library Being Economically Dead (2026-03-28, Session 46)

Session 46 re-audited the H135 deterministic baseline and found a structural bug in the blend
construction:

- non-presence signals were averaged directly in raw matrix scale
- `C4` and `C5` were not already on a common `0-1` rank scale inside
  `data/features/xs_rl_signal_matrix.parquet`
- this let raw-scale columns distort the `recent_core` / `full_library` score blends

The fix was to cross-sectionally rank each **non-presence** signal by date before averaging it into
the portfolio score. Presence flags remain `0/1`.

Under the corrected blend logic, the same realistic H135 contract:
- signal at `T` close
- buy at `T+1` open
- earliest sell at `T+3` close / `T+4` open
- zero-volume and ceiling/floor blocks
- `0.30%` round-trip cost
- top-5 equal-weight
- 3-day rebalance

now produces:

| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio |
|---|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 |
| `recent_core` | -46.81% | -5.63% | -83.54% | -0.40 |
| `full_library` | **+72.10%** | **+5.11%** | **-46.75%** | **-0.05** |

**Key finding:** the earlier “the library does not monetize at all” reading was too strong. The
library is weak under the default realistic construction, but it is **not** economically dead.
Session 45's original H135 `full_library` fail should be treated as superseded by this corrected
blend logic.

**Implication:** before making strategic decisions from any portfolio blend, enforce a common
cross-sectional scale across all input signals. Raw-signal averaging is not a harmless shortcut.

---
## F94: Portfolio Construction, Not More Signal Mining, Is the Dominant Lever After H136 (2026-03-28, Session 46)

H136 swept the corrected `full_library` blend across:
- `top_k = 3, 5, 8, 10`
- rebalance cadence `= 3, 5, 10` signal days
- weighting `= equal, linear, square`
- score gates `= none, 0.521, 0.570, 0.600`

Best configuration:
- `top_k = 5`
- rebalance every `5` signal days
- `equal` weighting
- score gate effectively irrelevant (`none`, `0.521`, and `0.570` tie)

Best result:

| Metric | Value |
|---|---:|
| Total Return | **+1105.71%** |
| Annualized Return | **+25.66%** |
| Relative vs VNINDEX | **+273.09%** |
| Information Ratio | **0.50** |
| Max Drawdown | **-59.76%** |
| Positive Years | **8 / 11** |
| Avg Daily Turnover | **33.54%** |

Grid-level pattern:
- `5d` cadence is the best regime
- `10d` cadence is next-best
- `3d` cadence is materially worse
- `equal` weighting beats `linear` and `square`
- `top_k = 5` is the best absolute performer
- moderate score gating does not matter in the winning region because the top names already clear it

**Key finding:** once the blend is normalized correctly, the monetization frontier shifts away from
“find more signals” and toward **portfolio construction and honest validation**.

**Implication:** the next work should be:
- honest out-of-sample validation of the H136 winner
- capacity and fee/slippage stress on that winner
- only after that, RL as a portfolio overlay that must beat the deterministic baseline

---
## F95: Simple ML-Style Construction Selection Does Not Yet Survive Honest Walk-Forward Testing (2026-03-28, Session 47)

H137 implemented the honest version of “let the machine choose the portfolio construction”:

- expanding train window
- minimum `4` train years
- candidate menu = the same H136 construction grid
- on each split, pick the best config on train years only
- freeze that config and test it on the next year
- stitched out-of-sample test years: `2019-2025`

The selected configs were not exotic:
- `top_k=5`, rebalance every `10` signal days, `equal` weighting was chosen `4/7` test years
- early years briefly chose `top_k=3`, `5d`, `equal`
- one year chose `top_k=10`, `5d`, `equal`

Out-of-sample stitched result:

| Metric | Value |
|---|---:|
| Total Return | **+21.38%** |
| Annualized Return | **+2.84%** |
| Relative vs VNINDEX | **-42.46%** |
| Information Ratio | **-0.08** |
| Max Drawdown | **-55.65%** |

Per-year test outcomes were mixed:
- positive in `2019`, `2020`, `2021`, `2023`
- negative in `2022`, `2024`, `2025`
- the final three test years were all benchmark-relative disappointments

**Key finding:** the full-sample H136 winner was too optimistic. A simple nested selector over the
existing construction grid does **not** validate “machine-learned configuration” as a near-term
production edge.

**Implication:** do not add more ML complexity yet. The next honest path is:
- reduce to a tiny fixed menu of simple constructions
- test those honestly
- if long-only still fails benchmark-relative, stay inside realistic long-only research and do not jump to synthetic hedges before RL

---
## F96: Fixed Simple Constructions Beat the Benchmark Out of Sample Better Than the ML-Style Selector (2026-03-28, Session 48)

H138 removed yearly re-selection entirely and tested a tiny fixed menu on the honest holdout
`2019-2025`:

- `k3_r5_eq` = top-3, rebalance every 5 signal days, equal weight
- `k5_r5_eq` = top-5, rebalance every 5 signal days, equal weight
- `k5_r10_eq` = top-5, rebalance every 10 signal days, equal weight

All three fixed rules beat VNINDEX on the holdout:

| Rule | Total Return | Annualized | Relative vs VNINDEX | Information Ratio | Positive Years |
|---|---:|---:|---:|---:|---:|
| `k3_r5_eq` | **+303.01%** | **+22.25%** | **+106.86%** | **0.43** | 5/7 |
| `k5_r5_eq` | +271.38% | +20.82% | +90.62% | 0.42 | **6/7** |
| `k5_r10_eq` | +241.90% | +19.39% | +75.49% | 0.38 | 4/7 |

For comparison, H137’s nested selector only achieved:
- `+21.38%` total
- `-42.46%` relative vs VNINDEX

**Key finding:** the yearly ML-style selector was worse than a few simple fixed rules. The problem
was not “the long-only construction idea is dead”; the problem was overfitting through re-selection.

**Implication:** before any more ML selection or RL overlays, the lab should treat a tiny menu of
simple deterministic constructions as the real baseline class.

---
## F97: The Long-Only Edge Survives Fee Stress but Collapses Under Any Tested ADV Participation Cap (2026-03-28, Session 48)

H139 stress-tested the H138 fixed-rule candidates on the same `2019-2025` holdout across:
- notionals `50m, 100m, 250m, 500m, 1B VND`
- ADV participation caps `0.0%, 0.5%, 1.0%, 2.0%`
- round-trip costs `0.30%, 0.50%`

Uncapped results remain economically strong:
- at `0.50%` RT and **no ADV cap**, all three candidates still stay positive benchmark-relative
- best uncapped stressed rule:
  - `k5_r10_eq`: `+154.31%` total, `+30.53%` relative vs VNINDEX

But capacity destroys deployability:
- number of scenarios with `relative_total_return > 0` and `max_adv_participation > 0`: **0**
- best relative return by ADV cap:
  - `0.0%`: **+106.86%**
  - `0.5%`: **-48.66%**
  - `1.0%`: **-48.64%**
  - `2.0%`: **-48.45%**
- minimum average cash weight by ADV cap:
  - `0.5%`: **99.32%**
  - `1.0%`: **98.64%**
  - `2.0%`: **97.34%**

**Key finding:** the edge is not killed first by fees; it is killed first by capacity. The current
long-only constructions are only attractive in effectively uncapped backtests.

**Implication:** the next bottleneck is not more ML. It is finding a **capacity-aware construction**
that preserves enough of the edge to stay benchmark-competitive under explicit deployability
constraints.

---
## F98: Signal-Date Liquidity Alignment Is a Hard Market-Rule Invariant, Not an Implementation Detail (2026-03-28, Session 49)

Session 49 found a one-day timing bug in the deterministic portfolio engine:

- `can_buy_next_open`, `can_sell_next_open`, and `ADV20` were being read from the
  **execution-date** row (`T+1`)
- but the shared execution contract defines those quantities on the **signal-date** row (`T`),
  because they govern the next open after that date

That meant the engine was leaking one day of liquidity/tradability information into:
- buy/sell blocking
- ADV participation caps
- the retail deployability experiments built on top of those controls

The fix was to align all of those liquidity/tradability inputs to the signal-date row while
keeping the portfolio timing contract unchanged:
- signal at `T` close
- buy at `T+1` open
- earliest sell decision at `T+3` close
- earliest sell fill at `T+4` open

**Key finding:** once market rules become part of the scientific claim, a one-day indexing mistake
is not a minor bug. It changes the economic meaning of the result. Session 48 H138/H139 figures
should therefore be treated as superseded by the Session 49 reruns.

**Implication:** tradability and capacity inputs must always be indexed by the information set
available at decision time, not by the later execution row.

---
## F99: After Correcting Liquidity Timing, Simple Fixed Long-Only Constructions Are Stronger Than Session 48 Suggested, but Only in Uncapped Form (2026-03-28, Session 49)

Session 49 reran H138 and H139 under the corrected signal-date liquidity alignment.

Corrected H138 holdout results (`2019-2025`):

| Rule | Total Return | Annualized | Relative vs VNINDEX | Information Ratio | Positive Years |
|---|---:|---:|---:|---:|---:|
| `k5_r5_eq` | **+769.49%** | **+36.59%** | **+346.29%** | **0.81** | **7/7** |
| `k3_r5_eq` | +748.57% | +36.11% | +335.55% | 0.70 | 6/7 |
| `k5_r10_eq` | +573.69% | +31.65% | +245.79% | 0.67 | 4/7 |

Corrected H139 fee/capacity stress preserved the same qualitative split:
- with **no ADV cap**, the fixed rules remain economically strong
- at `0.50%` round-trip cost and **no cap**, all three candidates stay positive benchmark-relative
- with **any positive ADV cap** in the tested `0.5% / 1.0% / 2.0%` grid, positive benchmark-relative
  scenario count remains **0**

Best relative return by ADV cap in corrected H139:
- `0.0%`: **+346.29%**
- `0.5%`: **-47.52%**
- `1.0%`: **-46.36%**
- `2.0%`: **-43.24%**

Minimum average cash weight by ADV cap:
- `0.5%`: **99.40%**
- `1.0%`: **98.81%**
- `2.0%`: **97.74%**

**Key finding:** the corrected engine makes the uncapped long-only opportunity look better, not
worse. But it does **not** change the deployability conclusion: the edge is still highly dependent
on effectively uncapped position sizing.

**Implication:** do not confuse “stronger honest uncapped baseline” with “retail-capacity solved.”
Those are different questions.

---
## F100: Retail-Sized Long-Only Deployability Still Fails Under Explicit ADV Floors and Participation Caps (2026-03-28, Session 49)

H140 tested the actual retail question directly on the honest `2019-2025` holdout:
- notionals `20m, 50m, 100m, 200m VND`
- ADV caps `2%, 5%, 10%`
- ADV20 floors `250m, 500m, 1B, 2B, 5B VND`
- round-trip costs `0.30%, 0.50%`
- candidate menu = the corrected H138 fixed rules

Retail-viability gate:
- `relative_total_return > 0`
- `avg_cash_weight < 25%`
- `positive_years >= 5/7`

**Result:** viable scenario count = **0**.

Best H140 scenario:
- `k5_r10_eq`
- `20m` portfolio notional
- `2%` ADV cap
- `1B` ADV20 floor
- `0.30%` round-trip cost

Even that “best” case only produced:
- total return **+12.00%**
- relative vs VNINDEX **-42.51%**
- average cash weight **87.13%**
- positive years **2/7**

**Key finding:** once explicit retail-sized liquidity rules are imposed, the current long-only
portfolio library does not have a deployable region. The failure is not just a scaling-to-1B
problem. It persists even when the notional is pushed down to `20m-200m VND`.

**Implication:** the next honest move is **not** more long-only tuning, RL, or synthetic hedging.
Within this repo, the valid continuation is an explicitly tiny-capital long-only
illiquidity-harvesting path with no scalability pretense, or a plain admission that the current
library is not deployable enough yet.

---
## F101: Without a Viable Retail Region, H141 and H142 Become a Stop Signal, Not a Promotion Path (2026-03-28, Session 49)

H141 was designed to re-open a tiny long-only construction sweep **only** inside the viable retail
region discovered by H140.

Because H140 found **zero** viable liquidity settings:
- H141 stopped immediately and wrote an empty-result summary
- there was no honest long-only region left to optimize

H142, the new live/paper-trade blotter exporter, was still implemented and then run manually on
the top H140 scenario as a diagnostic only.

Latest diagnostic snapshot (`2025-12-31` execution date):
- portfolio held only `SHB`
- target notional about `19.70m VND`
- target usage about `1.87%` of ADV20
- cash still **12.06%**

**Key finding:** the new blotter tooling is ready, but the candidate itself is not worthy of live
promotion. When the “best” capacity-aware long-only setup often degenerates into a one-name book
with large cash drag, that is a sign to change research direction rather than keep polishing the
same construction class.

**Implication:** treat H141/H142 as the end of the current long-only retail deployability branch.
The next branch should still remain long-only; do not jump to synthetic hedges or RL overlays on a
non-deployable book.

---
## F102: Long-Only and Anti-Synthetic Is a Permanent Repo Rule, Not a Temporary Preference (2026-03-28, Session 49)

The user set a hard constraint for this workspace:

- the repo is permanently **long-only**
- no synthetic hedges
- no stock shorting assumptions
- no “research-only” construction that cannot realistically make money in the Vietnam market

This rule exists because synthetic hedges and short-based diagnostics can create the false sense
that a weak long-only strategy has been “rescued” when the live trading path does not actually
exist for the intended user.

**Key finding:** once the execution/tradability layer is treated seriously, realism is not only
about fees and settlement. It is also about the **set of instruments and trade directions the user
can actually use**.

**Implication:** future work in this repo must remain inside the long-only constraint. If a strategy
cannot be made realistic as long-only in Vietnam, the correct response is to say so plainly, not to
introduce synthetic hedges or short exposure.

---
## F103: Soft Tradability-Aware Scoring Improves the Curve but Does Not Create a Retail-Viable Region (2026-03-28, Session 50)

H143 turned the generic “rank by signal” rule into several soft liquidity-aware score variants:
- `liq_x_adv_rank`
- `liq_x_tradability_rank`
- `liq_blend_70_30`
- `liq_blend_50_50`
- `liq_log_adv`

Tested on the honest `2019-2025` holdout across:
- notionals `20m, 50m, 100m VND`
- ADV caps `2%, 5%, 10%`
- ADV20 floors `250m, 500m, 1B`
- candidate menu = `k3_r5_eq`, `k5_r5_eq`, `k5_r10_eq`

Best H143 scenario:
- `liq_blend_50_50`
- `k3_r5_eq`
- `20m` notional
- `10%` ADV cap
- `250m` ADV20 floor
- total return **+32.46%**
- relative vs VNINDEX **-32.01%**
- average cash weight **25.11%**
- positive years **4/7**

**Key finding:** soft tradability-aware selection is directionally right. It materially improves the
absolute result and cash deployment relative to the H140 retail baseline, but it still does **not**
produce a benchmark-positive, retail-viable long-only region.

**Implication:** the failure is not just “the score ignores liquidity.” Even after the score is made
liquidity-aware, more friction remains in the extraction process.

---
## F104: Multi-Day Entry Slicing Makes the Execution Model More Realistic, but It Does Not Rescue Benchmark-Relative Economics (2026-03-28, Session 50)

H144 introduced pending multi-day buy plans:
- buys can continue over `2`, `3`, or `5` future execution days
- the ADV cap becomes a **daily buy limit** for sliced runs
- exits stay unchanged under the existing `T+2.5` long-only settlement rule

The experiment tested the strongest H143 score variants plus the base score under `k5_r5_eq`.

Best H144 scenario:
- `liq_x_tradability_rank`
- unsliced baseline (`entry_slice_days = 1`)
- `20m` notional
- `5%` ADV cap
- `250m` ADV20 floor
- total return **+28.57%**
- relative vs VNINDEX **-34.01%**

Sliced versions did reduce cash drag slightly:
- unsliced cash weight: **25.79%**
- 2-day / 3-day / 5-day sliced cash weight: about **25.18%**

But they also created many partial / expired plans and did **not** improve benchmark-relative return.

**Key finding:** the current edge is not failing only because the engine assumes one-shot entry.
Realistic staged accumulation is now modeled, and it is not the missing unlock.

**Implication:** keep the slicing capability for realism, but do not treat execution scheduling as
the next dominant research lever.

---
## F105: Liquidity-Opening Entry Gates Are the Strongest Friction Lever Tested So Far, but Still Miss the Retail Viability Bar (2026-03-28, Session 50)

H145 tested entry-gating rules on the strongest H143 score variant (`liq_blend_50_50`):
- no gate
- `adv20_125`
- `adv20_150`
- `adv5_150`
- `adv20_125_clv50`

Best H145 scenario:
- gate = `adv20_125_clv50`
- `k3_r5_eq` or `k5_r5_eq`
- `20m` notional
- `5%` ADV cap
- `1B` ADV20 floor
- total return **+93.88%**
- relative vs VNINDEX **-0.49%**
- average cash weight **33.52%**
- positive years **4/7**

This is the closest any retail long-only branch has come since explicit capacity realism was added.

**Key finding:** “only enter when liquidity is visibly opening” is the best construction lever found
in Sessions 49-50. It moves the strategy from deeply benchmark-negative toward nearly benchmark-flat.
But under the current retail gate, it still fails:
- relative return is still slightly negative
- average cash is still above the `25%` viability cutoff
- positive-year count is still below the `5/7` bar

**Implication:** future long-only work should be conditioned on liquidity-opening states rather than
generic score ranking alone.

---
## F106: Variable Breadth Does Not Solve the Remaining Retail Deployability Gap Once the Stronger Entry Gate Is Applied (2026-03-28, Session 50)

H146 took the strongest H145 combination:
- score variant = `liq_blend_50_50`
- entry gate = `adv20_125_clv50`

and tested variable breadth across:
- `max_k = 3, 5`
- score gates `= none, 0.55, 0.60`
- minimum deployable weight `= 10%, 15%, 20%`
- thin-name cap `= off or 2`

Best H146 scenario:
- total return **+93.88%**
- relative vs VNINDEX **-0.49%**
- average cash weight **33.52%**
- average holdings **0.74**
- positive years **4/7**

This is effectively the same near-miss found in H145.

**Key finding:** once the stronger liquidity-opening gate is in place, fixed `top_k` is not the
main remaining bottleneck. Allowing the book to shrink dynamically does **not** unlock a benchmark-
positive retail region.

**Implication:** do not spend the next session on another broad construction sweep. The honest next
branch is either:
- a very local refinement around the H145 near-miss, or
- a new long-only alpha search explicitly conditioned on tradability / liquidity-opening states.

---
## F107: The H145 Near-Miss Is a Sparse Opportunity-State Problem, Not Just a Bad Threshold Problem (2026-03-28, Session 51)

H147 audited the H145 near-miss directly around:
- score variant `liq_blend_50_50`
- construction `k3_r5_eq`
- local gate grid on `tv_to_adv20` and `clv`
- `20m` notional, `5%` ADV cap, `0.30%` RT

Best audited state:
- `adv20_125_clv45` or `adv20_125_clv50`
- `1B` ADV20 floor
- same economics as H145:
  - total return **+93.88%**
  - relative vs VNINDEX **-0.49%**
  - average cash weight **33.52%**
  - positive years **4/7**

But the state itself is very sparse:
- raw zero-candidate days are about **97%** of dates
- `2019` and `2020` are fully in cash in the best scenario
- opportunity only becomes dense enough to matter later in the holdout

**Key finding:** the near-miss is not mainly caused by “choosing the wrong local threshold.” It is
caused by the fact that the attractive liquidity-opening state is genuinely rare, especially early
in the holdout.

**Implication:** threshold polishing alone is unlikely to create deployability. The next useful
lever must either:
- increase opportunity density without opening the junk-liquidity floodgate, or
- discover alpha that only exists inside tradable states.

---
## F108: Local H145 Gate Refinement Is Exhausted; the Best Result Is Still the Original Near-Miss (2026-03-28, Session 51)

H148 stayed tightly around the H145 neighborhood:
- score fixed at `liq_blend_50_50`
- candidate menu fixed at `k3_r5_eq`, `k5_r5_eq`, `k5_r10_eq`
- `tv_to_adv20 >= 1.05, 1.10, 1.15, 1.20, 1.25`
- `clv >= none, 0.45, 0.50, 0.55`
- ADV20 floor `= 500m, 750m, 1B, 1.5B`
- notionals `= 20m, 50m`
- ADV caps `= 5%, 10%`

Result:
- **no retail-viable scenario**
- best scenario is still:
  - `adv20_125_clv45` or `adv20_125_clv50`
  - `k3_r5_eq`
  - `20m`
  - `5%` ADV cap
  - `1B` floor
  - total return **+93.88%**
  - relative vs VNINDEX **-0.49%**
  - average cash weight **33.52%**
  - positive years **4/7**

**Key finding:** the local threshold branch is now scientifically exhausted. Re-running nearby gate
grids is not generating new information.

**Implication:** future work should not spend another session on narrow H145 threshold sweeps unless
new alpha enters the system.

---
## F109: Softening the Liquidity Gate Makes the Book Busier but Worse (2026-03-28, Session 51)

H149 replaced the hard H145 gate with soft activation scores built on top of `liq_blend_50_50`:
- `soft_85_15`
- `soft_75_25`
- `soft_65_35`
- `soft_mul`

Best H149 scenario:
- `soft_85_15`
- `k3_r5_eq`
- `50m`
- `5%` ADV cap
- `500m` floor
- total return **-0.57%**
- relative vs VNINDEX **-48.97%**
- average cash weight **36.65%**
- positive years **3/7**

Compared with the H145 near-miss:
- turnover rose sharply
- the book held more names
- benchmark-relative economics deteriorated badly

**Key finding:** the H145 gate is not failing because it is “too binary.” Softening the entry logic
does not rescue the strategy. It mostly adds activity and cost without preserving the favorable
selection effect.

**Implication:** do not spend more time on soft activation / fuzzy gating around the current
library. That branch is weaker than the hard-gated near-miss.

---
## F110: The Current Library Has a Tradability-Conditioned Sub-Core, but Construction Alone Is No Longer the Main Research Path (2026-03-28, Session 51)

H150 decomposed the current RL signal library under liquidity-opening states:
- unrestricted
- `tv_to_adv20 >= 1.10`
- `tv_to_adv20 >= 1.10 and clv >= 0.45`
- `tv_to_adv20 >= 1.25 and clv >= 0.50`

Findings:
- `s1_proba` remains the strongest signal both unrestricted and in tradable states
  - unrestricted avg daily IC **+0.1491**
  - `tv110` avg daily IC **+0.1510**
- strongest conditional uplifts vs unrestricted come from:
  - `c7_ceiling_count_5d`
  - `c12_gap_absorb_3`
  - `c13_compress_blowoff_2`
  - `c10_illiq_level_rank`
  - `c8_vol_zscore_5d`

This means the library is not uniformly useful under friction. A narrower subset becomes more
interesting exactly when liquidity is opening.

**Key finding:** the repo now has evidence for a **tradability-conditioned signal sub-core**. The
problem is no longer “we have no idea what survives.” The problem is that the current generic
construction layer does not monetize that sub-core yet.

**Implication:** the next honest step is not another broad construction tweak. It is either:
- a narrow tradability-conditioned composite built from the surviving signals, or
- new long-only alpha search explicitly defined inside tradable states.

---
## F111: Recent-Window Stock Refreshes Can Silently Break Live Scoring by Truncating Historical Continuity (2026-03-28, Session 52)

Session 52 tried to close the loop from research to a real long-only paper-trade recommendation.
The blocker was not signal quality. It was data integrity.

Observed during the live-paper-trade attempt:
- many stock files were refreshed through **2026-03-27**
- some tickers remained stale or truncated
- `VNINDEX` ended up as a recent slice instead of a full-history file
- the live `S1` artifact still stopped at **2026-03-11**
- rerunning `analysis/h75_2026_holdout.py` failed with `ValueError: No objects to concatenate`

The common failure mode was operational:
- recent-window refreshes wrote new raw parquet files without guaranteeing full historical continuity
- downstream live scorers need long lookback windows, not just “latest date present”
- mixed raw-history state can therefore block live feature generation entirely

**Key finding:** “latest stock data fetched” is not enough for a live paper trade. The raw stock
surface must remain historically continuous across the active universe and benchmark files, or the
live scoring stack becomes invalid.

**Implication:** before any future live recommendation attempt:
- restore full-history `data/stock/` continuity first
- verify lookback sufficiency explicitly
- only then rerun live `S1` and rebuild the latest `full_library` inputs

---
## F112: The Actual Live-Scoring Failure Mode Was Benchmark Truncation, and a Local Full-History VNINDEX Backup Can Recover the Path Temporarily (2026-03-28, Session 52)

The Session 52 live-paper-trade recovery showed that the decisive operational break was not the
individual stock parquet refresh itself. It was the fact that `VNINDEX` in root `data/stock/`
had been reduced to a recent slice.

Why that mattered:
- the live `S1` feature pipeline depends on long benchmark history for market-relative features
- with only a short `VNINDEX` window, per-ticker 2026 feature frames collapsed to a tiny recent tail
- training rows for the live scorer effectively disappeared, which is why `analysis/h75_2026_holdout.py`
  failed with `No objects to concatenate`

The session recovered live scoring by:
- merging the truncated root `VNINDEX` file with a local full-history backup at
  `../media-output/signal-xs-momentum/data/stock/gia_lich_su_VNINDEX_1D.parquet`
- then rebuilding live `S1` and the 2026 stock-derived `full_library` inputs on the fly

**Key finding:** if root `VNINDEX` is truncated, the live stack breaks even when most stock files
look fresh. Benchmark continuity is a first-class dependency for live scoring.

**Implication:** future live recovery should:
- check `VNINDEX` history first
- use the local media-output backup only as a temporary recovery path
- restore the canonical root benchmark file before treating the live pipeline as healthy

---
## F113: ADV / Capacity Is Now a Parked Scale-Risk Branch, Not the Active Blocker for the Current-Account Research Track (2026-03-29, Session 53)

Sessions 48-51 established two things simultaneously:
- the uncapped long-only branch is economically strong
- the same branch does not survive explicit ADV floors and participation caps

Session 53 did **not** overturn that evidence. Instead, it changed how the repo should use it.

New working interpretation:
- ADV / capacity remains **unsolved**
- ADV / capacity remains important for scale and deployability research
- ADV / capacity is **parked** for the current-account branch because the immediate account size does
  not justify treating those caps as the dominant active blocker

This creates two explicit tracks:
- **current-account branch:** long-only, no ADV cap as the active research constraint, keep live
  execution reality and the deterministic paper trade running
- **scale branch:** ADV / capacity research remains documented, but is not the next active queue

**Key finding:** the repo should stop treating capacity as the next mandatory obstacle for every
session. For the current account size, the more informative next question is whether the existing
signal library can be exploited better by a long-only RL policy than by the current deterministic
construction.

**Implication:** the active next branch is now:
- benchmark-first long-only portfolio-choice RL
- with the deterministic `full_library` / `S1` comparators as the gate
- while the tradability-conditioned alpha branch (`H151/H152`) stays parked rather than deleted

---
## F114: The First Same-Universe RL Comparator Shows a Real Bar for RL to Beat; the Conditioned Sub-Core Is the Strongest Deterministic Baseline in the RL Universe but Still Trails the Equal-Weight Universe Benchmark (2026-03-29, Session 54)

Session 54 implemented and ran `H153`, the first deterministic comparator built directly on top of
`PortfolioChoiceEnv` so it uses:
- the exact same liquid-universe selection
- the same panel intersection
- the same long-only settlement and tradability rules

Configuration:
- portfolio universe size = `20`
- top-k = `3`
- signal source = adapted lab matrix
- test split produced by the RL env:
  - `2025-06-12` to `2025-12-30`

Resolved universe:
- `STB`, `VNM`, `VRE`, `VJC`, `VHM`, `POW`, `HPG`, `VPB`, `TCB`, `NVL`,
  `CTG`, `MSN`, `BAF`, `MSB`, `PVD`, `BSR`, `HSG`, `PLX`, `DXG`, `VCB`

Results:
- `s1_only`: total **-2.50%**, relative **-25.99%**
- `full_library`: total **+0.41%**, relative **-23.78%**
- `conditioned_subcore`: total **+6.32%**, relative **-19.30%**
- equal-weight universe benchmark over the same period: **+31.74%**

The conditioned sub-core (`S1 + C7 + C8 + C10 + C12 + C13`) is the strongest deterministic baseline
inside this RL universe, but it still underperforms the naive equal-weight universe benchmark on the
test split.

**Key finding:** RL now has a meaningful, same-universe deterministic bar to beat. The branch is no
longer “run RL and compare to something vague.” But the first benchmark is not trivially strong,
which means any RL win must still be treated cautiously and checked against seed sensitivity.

**Implication:** move forward with `H154` only against this benchmark-first framing. Promote RL only
if it beats the matching deterministic comparator and survives `H155` multi-seed reruns.

---
## F115: The First Portfolio-Choice RL Ladder Says Simpler State Wins; `S1`-Only RL Beat Both the Same-Universe Deterministic Comparator and the Equal-Weight Universe Benchmark on the First Seed, While Richer Signal Sets Hurt (2026-03-29, Session 55)

Session 55 ran the first real `H154` ladder on top of the `H153` same-universe benchmark:
- portfolio universe size `20`
- top-k `3`
- test split `2025-06-12` to `2025-12-31`
- PPO `mlp`
- `100000` timesteps
- seed `1208`

Reference deterministic comparators from `H153`:
- `s1_only`: **-2.50%**
- `full_library`: **+0.41%**
- `conditioned_subcore`: **+6.32%**
- equal-weight universe benchmark: **+31.74%**

Held-out RL results:

| RL setup | Test Return | Sharpe | Max DD | Rebalances | Reading |
|---|---:|---:|---:|---:|---|
| `S1` only | **+40.30%** | **2.72** | **-8.55%** | **1** | clear win |
| full matrix (`S1 + C4-C14`) | **-7.90%** | **-0.27** | **-30.65%** | **90** | clean fail |
| conditioned sub-core (`S1 + C7 + C8 + C10 + C12 + C13`) | **+15.60%** | **1.01** | **-18.59%** | **97** | mixed / secondary |

The key comparisons:
- `S1`-only RL beat deterministic `s1_only` by a wide margin and also beat the equal-weight
  universe benchmark on this split
- conditioned sub-core RL improved over its deterministic comparator, but still trailed the
  equal-weight benchmark and was far worse than `S1`-only RL
- full-matrix RL underperformed even the deterministic full-library comparator and churned heavily

**Key finding:** on the first seed, adding more signals made the policy worse, not better. The only
clear win came from the smallest state surface.

This does **not** prove `S1`-only RL is production-ready; it is still a single-seed result.
But it does change the immediate queue:
- `H155` should focus on multi-seed robustness for `S1` first
- conditioned sub-core is optional secondary validation
- full-matrix RL should be deprioritized until there is a concrete explanation for the churn /
  instability caused by the larger state

---
## F116: `S1`-Only Portfolio RL Is Interesting but Not Stable Enough to Promote; H155 Produced Two Strong Wins and Two Failures Across Seeds (2026-03-29, Session 56)

Session 56 ran the required `H155` multi-seed robustness pass on the only promising RL setup from
Session 55:
- `S1`-only portfolio-choice RL
- same universe size `20`
- same top-k `3`
- same test split `2025-06-12` to `2025-12-31`
- same PPO `mlp` configuration

Reference lines:
- deterministic `s1_only`: **-2.50%**
- equal-weight universe benchmark: **+31.74%**

Held-out RL seed results:

| Seed | Test Return | Sharpe | Max DD | Rebalances | Reading |
|---|---:|---:|---:|---:|---|
| `1208` | **+40.30%** | **2.72** | **-8.55%** | **1** | strong win |
| `1209` | **+43.44%** | **1.89** | **-21.17%** | **41** | strong win |
| `1210` | **-1.06%** | **0.12** | **-30.59%** | **86** | weak fail |
| `1211` | **-17.98%** | **-1.10** | **-36.04%** | **88** | clear fail |

Aggregate:
- mean RL return: **+16.18%**
- median RL return: **+19.62%**
- wins vs equal-weight benchmark: **2 / 4**
- wins vs deterministic `s1_only`: **3 / 4**
- positive-return seeds: **2 / 4**

**Key finding:** `S1`-only RL can clearly extract useful behavior on some seeds, but it does not yet
meet the stability bar required to make RL the active primary branch.

This is not a “nothing there” result. It is a **high-variance** result:
- the branch is interesting
- the branch is not dependable enough yet

**Implication:** downgrade RL to exploratory status for now. The active repo branch should return to:
- `H151`: narrow tradability-conditioned composite
- `H152`: tradability-conditioned alpha search

If RL is revisited later, it should be under a deliberate design-change branch:
- reward redesign
- observation scaling / normalization
- action or turnover control

## F117: The Repo Must Separate Selection Alpha From Activation Alpha; Current Evidence Says the Library Is Stronger at Choosing Names Than at Deciding When to Turn the Selector On (2026-03-29, Session 57)

Session 57 formalized the problem into two layers:
- **selection alpha**: choose the right names cross-sectionally
- **activation alpha**: decide when the selector should be on, off, or later partially on

This split was already implicit in the results:
- `full_library + k5_r5_eq` was a strong always-on long-only selector
- `S1`-only RL could sometimes make a lot of money, but with high seed variance
- that pattern suggested the repo may already know **what** to own better than it knows **when** to have exposure

The lab now treats that split as an explicit architectural rule, not a vague interpretation.

**Implication:** future work should say clearly which layer it is attacking. Do not blur selection-side alpha search with activation overlays.

## F118: Deterministic Binary On/Off Activation Did Not Beat the Always-On `full_library + k5_r5_eq` Selector; Activation Is a Tested Branch, Not an Open Assumption (2026-03-29, Session 57)

Session 57 built the date-level activation artifact `data/features/activation_state_daily.parquet` and ran the full deterministic activation wave:
- `H157`: opportunity density gate
- `H158`: tradability breadth gate
- `H159`: market regime gate
- `H160`: breadth / dispersion gate
- `H161`: recent efficacy / cooldown gate
- `H162`: composite activation score

Reference line:
- always-on `full_library + k5_r5_eq`: **+769.71%** total, **+346.40%** relative vs VNINDEX, information ratio **0.81**, max DD **-34.04%**

Best non-trivial activation candidates on the full-library selector were all inferior:
- `H157` `opp__spread_q70`: **+652.12%** total, **+286.05%** relative, IR **0.71**, max DD **-26.51%**
- `H159` `mkt__credit_risk_on_ge2`: **+614.63%** total, **+266.81%** relative, IR **0.68**, max DD **-28.32%**
- `H161` `recent__prev_cycle_gt_m02`: **+706.77%** total, **+314.10%** relative, IR **0.76**, max DD **-38.96%**

None of them beat the always-on selector on return. None beat it on information ratio. The recent-efficacy gate was the nearest miss, but it still underperformed and actually worsened drawdown.

Secondary result:
- several activation gates improved the weaker `S1`-only selector materially
- but none of those variants overtook the always-on `full_library` selector

**Key finding:** deterministic binary activation is now a **tested negative** for the current champion selector.

**Implication:** the active branch should return to selection-side work (`H151/H152`). If activation is revisited later, it should not begin with another binary on/off gate sweep; it needs a materially different design, such as partial exposure sizing or a more structural timing model.
