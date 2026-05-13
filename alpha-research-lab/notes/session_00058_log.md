# Session 58 Log

## Objective
Reopen activation alpha only with materially different designs than Session 57.

The branch assumptions were:
- selection alpha is already real
- binary deterministic on/off gating was tested and failed in Session 57
- if activation alpha exists, it is more likely to be:
  - partial exposure sizing
  - path-dependent selector-efficacy persistence
  - selector-specific or interaction-based logic
  - eventually a learnable meta-label problem

Hard rules stayed unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Build step

Extended the activation stack with:
- exposure-sized activation support inside `src/deterministic_portfolio.py`
- rebuilt `data/features/activation_state_daily.parquet` when stale columns are missing
- built new selector-efficacy artifact:
  - `data/features/activation_meta_daily.parquet`

New shared code:
- `src/activation_meta.py`
- `src/activation_meta_experiment_utils.py`
- `data_tools/build_activation_meta_features.py`

The meta artifact adds:
- forward next-cycle selector returns / relative returns
- recent selector efficacy EWMs
- recent implementation-pain EWMs
- selector drawdown-phase features
- first-difference tradability acceleration features
- selector confidence and entry-quality composites

## H163 — Partial Exposure Sizing

Best non-baseline full-library result:
- `size__recent_q55_q70`
- `+256.87%` total
- `+83.17%` relative vs VNINDEX
- IR `0.35`

Reading:
- partial sizing helps weaker branches
- it does not beat always-on `full_library`

## H164 — Opportunity Concentration

Best non-baseline full-library result:
- `conc__spread_q70`
- `+652.12%` total
- `+286.05%` relative
- IR `0.71`
- max DD `-26.51%`

Reading:
- concentration helps as a drawdown-trim gate
- still below the always-on champion on return and IR

## H165 — Selector Agreement / Disagreement

Best full-library reading:
- `agree__jaccard_q60` matched always-on exactly

Reading:
- selector agreement is not an activation edge for the champion
- it mostly says the always-on branch is already active in that state

## H166 — Tradability Acceleration

Best non-baseline full-library result:
- `tradacc__liq_breadth_delta_q60`
- `+315.84%` total
- `+113.45%` relative
- IR `0.44`

Reading:
- change in deployability helps, but not enough to beat the champion
- tradability acceleration is useful context, not the main activation driver

## H167 — Selector Fragility / Implementation Pain

Best full-library reading:
- `frag__turnover_mid_q60` matched always-on exactly

Reading:
- implementation pain does not create a useful activation edge for the champion in the uncapped branch
- it helps the weaker `S1` selector somewhat, not `full_library`

## H168 — Interaction Regime Gates

Best result came from `S1`, not `full_library`:
- `s1_only` `inter__conf_q60_above_ma20`
- `+332.40%` total
- `+121.94%` relative
- IR `0.40`

Best full-library interaction remained below champion:
- `inter__conf_q60_risk_on`
- `+121.47%` total
- `+13.67%` relative

Reading:
- interaction logic matters for weaker selectors
- it is not the edge source for the champion

## H169 — Breadth Collapse

Best non-baseline full-library result:
- `breadth__buyable_q40`
- `+551.01%` total
- `+234.15%` relative
- IR `0.68`

Reading:
- breadth collapse is a real risk-off state
- but avoiding it still underperforms always-on `full_library`

## H170 — Smoothed Recent Efficacy

This is the first activation family that actually beat the always-on champion.

Best result:
- `full_library_k5_r5_eq`
- `recentsm__rel3_gt0`
- `+841.14%` total
- `+383.07%` relative vs VNINDEX
- IR `0.84`
- max DD `-34.00%`

Secondary winner:
- `recentsm__hit5_ge55`
- `+796.59%` total
- `+360.20%` relative
- IR `0.82`
- max DD `-32.02%`

Reference always-on champion:
- `+769.71%` total
- `+346.40%` relative
- IR `0.81`
- max DD `-34.04%`

Reading:
- activation alpha exists when framed as smoothed selector-efficacy persistence
- path dependence matters more than static regime filtering
- this is now the active activation branch

## H171 — Selector Drawdown Phase

No full-library drawdown-phase gate beat the champion.

Best reading was again on `S1`:
- `dd__gt_m10`
- `+107.90%` total
- `+6.71%` relative

Reading:
- drawdown phase alone is too blunt

## H172 — Entry Window Quality

Best non-baseline full-library result:
- `entry__tv_rank_q60`
- `+256.89%` total
- `+83.18%` relative
- IR `0.36`

Reading:
- entry-window quality matters
- it is not the main activation unlock for the champion

## H173 — Selector-Specific Activation

Best result was again on `S1` with a shared/global gate:
- `spec__global_conf_liq_mkt`
- `+179.80%` total
- `+43.62%` relative

For `full_library`, neither the selector-specific nor the global gate beat the champion.

Reading:
- selector-specific logic is not enough on its own
- the real edge still looks like selector-efficacy persistence, not selector-identity branching

## H174 — Hysteresis / Opportunity Streaks

Best non-baseline full-library result:
- `streak__half_default_on2off2`
- `+418.09%` total
- `+165.92%` relative
- IR `0.61`
- max DD `-21.46%`

Reading:
- hysteresis can cut drawdown materially
- but it still gives up too much return versus always-on and versus `H170`

## Verdict

Session 57 said:
- deterministic binary activation does not beat always-on `full_library`

Session 58 refines that into a more precise truth:
- static activation logic still does not beat always-on `full_library`
- path-dependent smoothed selector-efficacy activation **does** beat always-on `full_library`

So the updated architectural conclusion is:
- selection alpha is real
- activation alpha is also real, but only in a narrow family so far
- the live activation branch is now:
  - smoothed selector-efficacy persistence
  - next likely extension: exposure sizing or learnable meta-labels on top of that state

## Branch decision

Primary next queue:
1. `H175`: robustify `H170` with honest threshold/window sweeps and walk-forward calibration
2. `H176`: convert `H170` into `off / half / full` exposure sizing
3. `H177`: train a compact activation meta-model using only past-cycle efficacy, implementation pain, selector confidence, and entry quality

Secondary parked queue:
1. `H151`
2. `H152`

## Artifacts

New data artifact:
- `data/features/activation_meta_daily.parquet`

Run summaries:
- `artifacts/run_summaries/latest_portfolio_activation_partial_exposure.json`
- `artifacts/run_summaries/latest_portfolio_activation_opportunity_concentration.json`
- `artifacts/run_summaries/latest_portfolio_activation_selector_agreement.json`
- `artifacts/run_summaries/latest_portfolio_activation_tradability_acceleration.json`
- `artifacts/run_summaries/latest_portfolio_activation_selector_fragility.json`
- `artifacts/run_summaries/latest_portfolio_activation_interaction_regime.json`
- `artifacts/run_summaries/latest_portfolio_activation_breadth_collapse.json`
- `artifacts/run_summaries/latest_portfolio_activation_smoothed_recent_efficacy.json`
- `artifacts/run_summaries/latest_portfolio_activation_drawdown_phase.json`
- `artifacts/run_summaries/latest_portfolio_activation_entry_window_quality.json`
- `artifacts/run_summaries/latest_portfolio_activation_selector_specific.json`
- `artifacts/run_summaries/latest_portfolio_activation_hysteresis.json`
