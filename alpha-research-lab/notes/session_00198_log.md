# Session 198 Log - Order-Pressure Portfolio / Tradability Audit (2026-04-28)

## Objective

Continue the evergreen loop from the latest alpha-lab state while preserving
the hardware contract:
- keep the guarded Ollama residual backfill as the only heavy local-model job
- run only CPU-bounded research work alongside it
- keep `2026+` excluded from predictive experiments

The research objective was the required H358 follow-through after H357:
test whether the H356/H357 `order_volume_ratio_rank` candidate survives an
executable portfolio / tradability audit before any feature-publication design.

## Watchdog State

Preflight found the recorded Ollama worker state was stale:
- `artifacts/job_status/ollama_guarded_publish.json` still said `running`
- last checkpoint state was `505 / 7344`
- no active `build_ollama_guarded_features` process was visible
- `ollama ps` had no loaded model
- `nvidia-smi` showed no active GPU process

The job was restart-safe because checkpoint shards and score-cache shards
existed through batch `505`.

Restarted:

`tmux new-session -d -s ollama_guarded_backfill -c /home/manh/stocks-ecosystem/alpha-research-lab '/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.build_ollama_guarded_features >> artifacts/logs/ollama_guarded_backfill.log 2>&1'`

Latest watchdog check after restart:
- status: `running`
- completed batches: `516 / 7344`
- processed input rows: `10,320`
- GPU memory: about `2.32GB / 4GB`

The Ollama job was left running.

## Experiment

### H358 - Order-Pressure Portfolio / Tradability Audit

**Hypothesis:**
The H356/H357 `order_volume_ratio_rank` signal improves an executable
full-library top-5 equal-weight portfolio without materially worsening
tradability health.

**Command / code:**
`python analysis/h358_order_pressure_portfolio_tradability_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- `data/stock/gia_lich_su_<TICKER>_1D.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_212531_h358_order_pressure_portfolio_tradability_audit_research_branch_order_pressure_portfolio_tradability_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | portfolio gate passed, execution-health gate failed |
| order feature coverage | `98.04%` | `810,201 / 826,404` matrix rows |
| baseline validation relative return / IR | `+45.19% / 0.85` | full library |
| candidate validation relative return / IR | `+57.49% / 1.00` | full library + order pressure |
| validation relative / IR delta | `+12.31% / +0.1532` | additive portfolio gate passed |
| baseline confirmation relative return / IR | `-21.13% / -0.81` | full library |
| candidate confirmation relative return / IR | `-10.06% / -0.33` | still negative but improved |
| confirmation relative / IR delta | `+11.07% / +0.4739` | passed confirmation survival |
| validation turnover delta | `+0.0019` | acceptable |
| confirmation turnover delta | `-0.0048` | acceptable |
| validation cash delta | `+0.0214` | failed `0.02` health limit |
| confirmation cash delta | `+0.0175` | acceptable |

**Result:**
Order pressure has real executable portfolio relevance, but the equal-weight
full-library addition is not clean enough for publication. The failure was not
return or turnover; it was the validation cash-drag health rule.

**Verdict: MIXED**

## Debug Note

The first H358 run was invalid because the script resolved `full_library` after
merging the order-pressure column, which accidentally put the candidate feature
inside the baseline. The script was patched to resolve full-library columns
from the original matrix before rerunning. Treat only the `21:25:31` run above
as branch evidence.

## Branch Decision

Keep C16 as an unpublished candidate / offline RL-state axis.

Do not publish a shared `data/features/...` order-pressure artifact yet.

If C16 continues, the next honest step is one bounded sizing / state-scope
audit:
- smaller additive weight, or
- a narrower tradable-state scope that tries to keep the portfolio uplift
  without the cash-drag breach

If that follow-up fails, park C16 until a learned model contract or downstream
RL consumer specifically needs the axis.

## Memory Changes

Updated:
- `notes/live_state.md`
- `notes/findings-00271-00300.md`
- `notes/signal_library.md`

Added:
- `analysis/h358_order_pressure_portfolio_tradability_audit.py`

Durable finding:
- `F298`

## Verification

Completed:
- `python -m py_compile analysis/h358_order_pressure_portfolio_tradability_audit.py`
- `python analysis/h358_order_pressure_portfolio_tradability_audit.py`
- read the saved run summary and detail artifact
- rechecked the Ollama backfill status after restart and after H358

The broader test suite was not run.

## Next Step

Continue watchdog monitoring for the guarded Ollama residual backfill. In the
CPU-only research lane, run at most one bounded H359 sizing / state-scope audit
before either publication design or parking C16.

Live state: [live_state.md](./live_state.md)
Durable finding: [findings-00271-00300.md](./findings-00271-00300.md)
