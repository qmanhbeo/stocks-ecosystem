# Session 272 Log

**Date**: 2026-05-05
**Focus**: S24x-S25x strong-signal methodology audit

## Summary

- Added reusable audit script:
  `analysis/audit_s24x_s25x_signal_claims.py`.
- Recomputed the S242-S253 "strong" C16/context claims on `2015-2025`
  rows only, with no `2026+`.
- Separated observable states from states derived from the same-date S1
  `actual` target.
- Verdict: several 24x/25x claims were real but overstated; the target-derived
  `consecutive_down` / `down_market_c16` validation was an error.

## Commands

```bash
python alpha-research-lab/analysis/audit_s24x_s25x_signal_claims.py
```

Saved artifacts:
- Metrics:
  `artifacts/audits/20260505_161922_s24x_s25x_signal_claim_audit_metrics.csv`
- Yearly table:
  `artifacts/audits/20260505_161922_s24x_s25x_signal_claim_audit_yearly.csv`
- Summary:
  `artifacts/run_summaries/20260505_161922_s24x_s25x_signal_claim_audit_audit_s24x_s25x_signal_claims.json`

## Methodology Issues Found

1. `data/features/xs_barrier_vol_1d_hose_full.parquet` column `actual` is a
   binary future 1d barrier label, not a signed return.
2. `analysis/s244_consecutive_final.py`, `analysis/s246_c16_intensity_modulation.py`,
   and `analysis/s253_true_wf_validation.py` used same-date `actual` averages
   to define market/down states. That conditions on the target surface.
3. `analysis/s247_deep_down_market.py` used `actual` mean as if it were signed
   return; because `actual` is `0/1`, its "down" state was effectively all rows
   and its "deep down" state was the bottom quintile of future label hit rate.
4. `analysis/s253_true_wf_validation.py` did not implement the advertised
   train `T-2,T-1` -> test `T` protocol. Its train-year selector is positional
   and includes the test year in early folds; the only "training" step is a
   monotonic z-score, so Spearman IC is unchanged from subset IC.

## Audit Metrics

Baseline:
- `c16_all`: avg year IC `+0.073765`, `11 / 11` positive years.

Survives:
- `insider_lead_next_trading_day`: avg year IC `+0.104981`, `11 / 11`
  positive years, 2023-2025 avg IC `+0.086101`. This remains a real C16
  support context.
- `vol_high_buy_count_gt_80`: avg year IC `+0.084359`, `11 / 11` positive
  years, lift `+0.010594` versus C16. This is a modest volume-context lift,
  not a standalone breakthrough.

Downgraded / error:
- Leaky target-derived `market_down`: avg year IC `+0.092478`.
- Leaky target-derived `market_down_2d`: avg year IC `+0.095095`.
- Correct observable `observed_vni_down`: avg year IC `+0.077064`, only
  `+0.003299` over C16.
- Correct observable `observed_vni_down_2d`: avg year IC `+0.080584`, only
  `+0.006818` over C16.
- `observed_stock_down`: avg year IC `+0.061540`, weaker than C16.
- `observed_stock_down_2d`: avg year IC `+0.067884`, weaker than C16.

Calendar / timing:
- `january_doy_le10`: avg year IC `+0.082334`, lift `+0.008568`.
- Actual first 10 trading days: avg year IC `+0.074432`, basically baseline.
- `monday_january_doy_le10`: avg year IC `+0.105363`, but only `2,891` rows
  on `11` dates. H390 remains the stronger mechanism audit: exact
  `monday_jan_combo` is context only, not an independent overlay.

Other downgrades:
- Correct dividend next-30-day windows were weak: record-date window avg IC
  `+0.052616`; ex-right window avg IC `+0.055744`.
- `rank_accel_5d` avg year IC was `+0.054809`, below C16 by `-0.018956`.

## Conclusion

- Keep `insider_buy_lead` as real support context.
- Keep high buy-order-count volume context as modest evidence.
- Do not treat S253 as resolving the methodology concern.
- Do not promote `consecutive_down`, target-derived `down_market_c16`, or
  `deep_down_c16` from the S244-S253 record.
- Keep calendar and dividend claims as context/parked paths unless reopened
  with a fixed observable contract and proper controls.
