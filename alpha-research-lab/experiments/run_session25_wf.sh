#!/bin/bash
# Session 25: Run all WF experiments sequentially
# H77, H79, H83a, H83b, H86, H80

set -e

echo "=== Session 25 WF Runs: $(date) ==="

echo ""
echo "--- H77: Dormant features ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.01 --threshold 0.05 --use-dormant-features \
    --save-all-probas data/features/xs_barrier_dormant_hose_full.parquet \
    2>&1 | tee logs/h77_dormant.log
echo "H77 WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_dormant_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h77_eval.log
echo "H77 COMPLETE: $(date)"

echo ""
echo "--- H79: VIX as training feature (393 stocks) ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.01 --threshold 0.05 --use-vix-feature \
    --save-all-probas data/features/xs_barrier_vix_feature_hose_full.parquet \
    2>&1 | tee logs/h79_vix.log
echo "H79 WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_vix_feature_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h79_eval.log
echo "H79 COMPLETE: $(date)"

echo ""
echo "--- H83a: Barrier 0.5% ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.005 --threshold 0.05 \
    --save-all-probas data/features/xs_barrier_0.5pct_hose_full.parquet \
    2>&1 | tee logs/h83a_0.5pct.log
echo "H83a WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_0.5pct_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h83a_eval.log
echo "H83a COMPLETE: $(date)"

echo ""
echo "--- H83b: Barrier 1.5% ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.015 --threshold 0.05 \
    --save-all-probas data/features/xs_barrier_1.5pct_hose_full.parquet \
    2>&1 | tee logs/h83b_1.5pct.log
echo "H83b WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_1.5pct_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h83b_eval.log
echo "H83b COMPLETE: $(date)"

echo ""
echo "--- H86: XS Fundamentals ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.01 --threshold 0.05 --use-xs-fundamentals \
    --save-all-probas data/features/xs_barrier_fundamentals_hose_full.parquet \
    2>&1 | tee logs/h86_fundamentals.log
echo "H86 WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_fundamentals_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h86_eval.log
echo "H86 COMPLETE: $(date)"

echo ""
echo "--- H80: Sector-Relative Features ---"
PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \
    --barrier-pct 0.01 --threshold 0.05 --use-sector-relative \
    --save-all-probas data/features/xs_barrier_sector_rel_hose_full.parquet \
    2>&1 | tee logs/h80_sector_rel.log
echo "H80 WF done. Now evaluating..."
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_sector_rel_hose_full.parquet --no-vix-filter \
    2>&1 | tee logs/h80_eval.log
echo "H80 COMPLETE: $(date)"

echo ""
echo "=== ALL SESSION 25 WF RUNS COMPLETE: $(date) ==="
