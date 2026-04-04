# Session 103 Log

## Objective
Run the first fallback after Session 102 closed the breakout-survivor continuation family:
- `H274`: audit whether rebalance-date top-k intraday stress summaries on the frozen sticky branch predict implementation strain, replacement pressure, or next-cycle pain strongly enough to justify a new selector-state gate

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H273` had already failed and closed the exact breakout-survivor continuation family on the current restarted contract
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- the next honest fallback from `next_steps.md` was no longer a new broad backtest:
  - first summarize whether reduced-shape intraday conviction predicts sparse-book stress, replacement pressure, or breadth collapse on the `2023-2025` branch
  - only continue to a new gate if that selector-state audit survives
- `H258` had already passed the reduced-shape intraday contract audit, so the branch had usable multi-ticker `1H` coverage for a clean top-k state test

## What changed

Added:
- `analysis/h274_topk_intraday_stress_router_audit.py`

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_activation_topk_intraday_stress_router_audit.json`
- `artifacts/portfolio_baselines/20260404_130111_h274_topk_intraday_stress_router_audit_results.parquet`
- `artifacts/portfolio_baselines/20260404_130111_h274_topk_intraday_stress_router_audit_frame.parquet`
- `artifacts/portfolio_baselines/20260404_130111_h274_topk_intraday_stress_router_audit_sticky_daily.parquet`

### H274 - Top-K Intraday Stress Router Audit
**Hypothesis:**
If reduced-shape intraday contradiction is the missing activation state variable, date-level stress summaries over the selector's top names should predict blocked-buy strain, replacement pressure, or next-cycle pain on the frozen sticky branch strongly enough to justify a later gate follow-through.

**Command / code:**
`conda run -n stocks python analysis/h274_topk_intraday_stress_router_audit.py`

**Inputs:**
- reduced-shape intraday source:
  - `H258` reduced-shape panel
- frozen branch contract:
  - `sticky_bonus_0p015`
  - replay history `2019-2025`
  - evaluate activated rebalance dates in `2023-2025` only
- predeclared intraday summaries:
  - `stress_fade`
  - `stress_failed_breakout`
  - `stress_weak_close_repair`
  - `stress_composite_mean`
  - `stress_name_share_q70`
- slow operational control:
  - `full_recent_blocked_buy_ewm5`
- stress endpoints:
  - blocked-buy count
  - cash weight
  - top-5 replacement overlap
  - top-5 buyable count
  - next-cycle relative return
- directional hit rule:
  - Spearman correlation must have the expected sign with magnitude `>= 0.10`
  - high-stress dates use the dev `q80` threshold for each score

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_activation_topk_intraday_stress_router_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| rebalance rows | `95` | activated sticky rebalance dates in `2023-2025` |
| validation rows | `33` | `2024` |
| confirmation rows | `28` | `2025` |
| overall observed share | `0.9747` | reduced-shape coverage across requested top-k names |
| validation observed share | `0.9697` | reduced-shape coverage on `2024` rebalance dates |
| confirmation observed share | `0.9571` | reduced-shape coverage on `2025` rebalance dates |
| best intraday candidate | `stress_weak_close_repair` | top-ranked intraday summary under the predeclared audit sort |
| best intraday validation directional hits | `0` | none of the five core endpoints lined up with the expected sign in `2024` |
| best intraday confirmation directional hits | `1` | only one weak directional hit in `2025` |
| best intraday validation cycle delta | `+0.0037` | high-stress dates were slightly better, not worse |
| best intraday confirmation cycle delta | `-0.0021` | only a tiny negative cycle split |
| slow baseline validation directional hits | `2` | `full_recent_blocked_buy_ewm5` control |
| slow baseline confirmation directional hits | `4` | same control remained much stronger on `2025` |
| slow baseline validation cycle delta | `-0.0201` | high blocked-buy stress still aligned with worse next-cycle return |
| slow baseline confirmation cycle delta | `-0.0073` | same direction in confirmation |

**Result:**
`H274` fails cleanly.

What failed:
- no intraday top-k summary produced even one validation directional hit
- the best intraday candidate still had:
  - validation hits `0`
  - positive validation cycle delta
- most intraday candidates pointed the wrong way on next-cycle relative return:
  - stressier dates were as good as or better than low-stress dates

What the control showed:
- this is not just an empty audit frame or a missing-data artifact
- reduced-shape coverage stayed high
- the older slow blocked-buy proxy still carried more operational signal than any intraday summary on the same dates

So the selector-state router thesis does **not** survive the frozen sticky branch audit on the current contract.

**Verdict: FAILED**

## Branch decision

Do **not** change the live branch.

What Session 103 resolves:
- `H274` fails:
  - the reduced-shape intraday summaries do not survive as a top-k selector-state router on the current frozen sticky branch
  - the branch does not justify a follow-through gate test

Branch effect:
- close the `top-k intraday stress router` branch on the current contract
- keep the live sticky branch unchanged
- do **not** open `H275` on this exact state-router line
- move the queue to:
  - `library-grade intraday shape atoms`

## Validation

Completed before the run:
- `python -m py_compile alpha-research-lab/analysis/h274_topk_intraday_stress_router_audit.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h274_topk_intraday_stress_router_audit.py`
- read `artifacts/run_summaries/latest_portfolio_activation_topk_intraday_stress_router_audit.json`

Verdict:
- `H274`: **FAILED**
