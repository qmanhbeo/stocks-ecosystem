# Session 59 Log

## Objective
Continue the activation-alpha branch only through the direct H170 follow-ups:
- `H175`: robustify the H170 family with threshold/window sweeps and yearly walk-forward rule selection
- `H176`: convert the H170 family into 3-state exposure sizing
- `H177`: test a compact walk-forward activation meta-model

Hard rules stayed unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Starting point

Session 58 had established the first real activation winner:
- `H170` `recentsm__rel3_gt0`
- `full_library + k5_r5_eq`
- `+841.14%` total
- `+383.07%` relative vs VNINDEX
- IR `0.84`
- max DD `-34.00%`

That became the family to stress, not the whole activation space.

## Build step

Added shared utilities to support the next branch cleanly:
- threshold-based 3-state schedules
- walk-forward logistic activation scores
- subperiod relative-return scoring for yearly rule selection

Files updated / added:
- `src/activation_meta_experiment_utils.py`
- `analysis/h175_h170_robustness.py`
- `analysis/h176_h170_three_state_sizing.py`
- `analysis/h177_activation_meta_model.py`

## H175 — H170 robustness

What was tested:
- faster and slower smoothing windows around recent selector relative return
- small threshold shifts around zero
- hit-rate thresholds
- one yearly walk-forward rule-selection path over the candidate family

New champion:
- `full_library + k5_r5_eq`
- `h175__rel2_gt0`
- `+1052.77%` total
- `+491.69%` relative vs VNINDEX
- IR `0.93`
- max DD `-20.57%`

Other strong variants:
- `h175__rel3_gt0`: `+841.14%` total, `+383.07%` relative, IR `0.84`
- `h175__hit5_ge55`: `+796.59%` total, `+360.20%` relative, IR `0.82`

Critical negative result:
- yearly walk-forward rule selection did **not** win
- `h175__wf_best_train_rel` only reached:
  - `+369.89%` total
  - `+141.19%` relative
  - IR `0.49`

Reading:
- the activation edge is real
- but the current best version is a simple fixed short-memory rule, not yearly re-selection

## H176 — H170 three-state sizing

Goal:
- see whether `off / half / full` exposure can beat the new fixed binary champion

Best result:
- `h176__rel3_0_p01`
- `+580.02%` total
- `+249.04%` relative
- IR `0.70`
- max DD `-33.01%`

Reading:
- 3-state sizing is viable
- it improves some weaker branches and remains respectable
- it does **not** beat `h175__rel2_gt0`

## H177 — compact activation meta-model

Model style:
- walk-forward logistic regression
- feature families:
  - recent selector efficacy
  - turnover / cash / blocked-buy implementation pain
  - selector drawdown
  - selector confidence
  - selector entry quality

Best full-library result:
- `h177__prob_ge60`
- `+480.78%` total
- `+198.10%` relative
- IR `0.60`
- max DD `-31.98%`

Reading:
- the compact meta-model learns something real
- but it is still worse than the simple fixed `rel2_gt0` rule

## Verdict

Session 58 said:
- activation alpha exists once it is framed as path-dependent selector efficacy

Session 59 refines that again:
- activation alpha is currently strongest as a **simple fixed short-memory efficacy rule**
- the branch does **not** currently reward extra complexity

So the new architectural conclusion is:
- selection alpha remains the base layer
- activation alpha is real and now has a better champion than always-on
- but the best activation rule is simpler than the more learned alternatives tested so far

## Branch decision

Primary next queue:
1. `H178`: robustness stress for `h175__rel2_gt0`
   - alternate start years
   - fee sensitivity
   - benchmark-relative subperiod stability
2. `H179`: live-paper activation overlay for the deterministic paper-trade branch using `h175__rel2_gt0`
3. `H180`: only small augmentations around `rel2_gt0` if needed
   - e.g. hit-rate guards
   - not a new broad activation family

Secondary parked queue:
1. `H151`
2. `H152`

## Artifacts

Run summaries:
- `artifacts/run_summaries/latest_portfolio_activation_h170_robustness.json`
- `artifacts/run_summaries/latest_portfolio_activation_h170_three_state_sizing.json`
- `artifacts/run_summaries/latest_portfolio_activation_meta_model.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h175_h170_robustness*`
- `artifacts/portfolio_baselines/*h176_h170_three_state_sizing*`
- `artifacts/portfolio_baselines/*h177_activation_meta_model*`
