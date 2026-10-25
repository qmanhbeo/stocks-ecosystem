# Stock RL research hibernation report

**Status: parked, preserved, and not merged.** No new experiment, training, or trading-method change was made.

## Archive created

- [`RL-trading-agent/research/trade_episode/README.md`](RL-trading-agent/research/trade_episode/README.md): environment, state/actions, execution, reward, normalization, PPO, data splits, dependencies, and verified run/test commands. The RL project README now links to it.
- [`RESEARCH_FINDINGS.md`](RL-trading-agent/research/trade_episode/RESEARCH_FINDINGS.md): evidence and limitations for Phases 1–4D, including negative and inconclusive results.
- [`FUTURE_RESEARCH.md`](RL-trading-agent/research/trade_episode/FUTURE_RESEARCH.md): research order, restart gates, and a safe resumption checklist.

## Conclusion and reproducibility

PPO learned functioning, highly exposed policies but did not demonstrate repeatable superiority over mechanical strategies. Phase 4C found associations between the state and some trade outcomes; Phase 4D did not establish that supervised exits convert them into reliable chronological gains. The annualized per-trade reward is not portfolio CAGR. These results do not prove RL unsuitable or that alpha cannot exist.

The source, tests, protocols, and Phase 4B–4D metrics are versioned. Six Phase 4A checkpoints and six Phase 4D supervised models currently pass their saved SHA-256 checks. Early run bundles remain under `/tmp`, so they are not durable archival copies. Phase 4A's checkpoint manifest has no generating Git SHA; its checkpoint hashes are present. Shared Parquet data remains outside Git. No 2026 observations were used.

Focused verification: **71 passed**, Ruff passed; 14 non-fatal Matplotlib/PyParsing deprecation warnings. Local Markdown links in the archived reports and docs resolved.

## Parked state and resumption

Branch: `exp/stock-rl-trade-episode`; worktree: `/home/manh/stocks-ecosystem-worktrees/rl-trade-episode`. Documentation milestones are `040ede22`, `2649b51d`, and `265dc20f8ae95687b934ff40d781cd0b84101c2a`. The hibernation report is committed after those milestones. Its containing commit cannot include its own Git object ID; the exact final tip SHA is reported in the delivery handoff. Tag: `stock-rl-research-2026-parked` (target and push verified in the handoff).

To resume, inspect branch state, read the three archive docs above, then use the existing Python environment and rerun the focused suite from `RL-trading-agent`:

```bash
git -C /home/manh/stocks-ecosystem-worktrees/rl-trade-episode status --short --branch
cd /home/manh/stocks-ecosystem-worktrees/rl-trade-episode/RL-trading-agent
conda activate stocks
export PYTHONPATH=.
export STOCKS_DATA_ROOT=/home/manh/stocks-ecosystem/data
PYTHONPATH=. python -m pytest -q tests/test_trade_episode.py tests/test_phase4a.py tests/test_phase4b.py tests/test_phase4c_target_alignment.py tests/test_phase4d_policy.py tests/test_phase4d_prediction_support.py tests/test_phase4d_statistics.py tests/test_phase4d_supervised.py
```

Before any future run, verify required `/tmp` checkpoints by hash and define a new pre-registered question and fresh output paths. The current recommendation is **no-go for more PPO training** until a point-in-time signal and a simple executable policy first beat appropriate controls on an untouched period.
