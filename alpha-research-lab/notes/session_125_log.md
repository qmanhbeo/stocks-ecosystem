# Session 125 Log — LLM Extractor Resume (2026-04-08)

## Objective

Resume the canonical Google LLM extractor after the S126 cooldown-persistence handoff, confirm that plain `python` uses the default `stocks` environment, and move the cache frontier forward without reopening any research branch.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Resumed the extractor with the current canonical script and default shell `python`.

Saved outputs:
- `data/llm_cache/2017-12-22.jsonl`
- `artifacts/llm_runtime/hosted_model_stats.json`

### S126 - LLM Extractor Resume After API-Key Cooldown Persistence
**Hypothesis:**
With persisted `api_key_cooldowns` in `hosted_model_stats.json`, the extractor should resume from the next missing cache day, avoid the dead-key reprobe loop on restart, and make forward progress under the current Google-only contract.

**Command / code:**
`python -u data_tools/extract_llm_news_features.py --provider google --workers 16 --timeout 45`

**Inputs:**
- `data/news/cafef/raw/2017-12-22.jsonl`
- `data/llm_cache/`
- `artifacts/llm_runtime/hosted_model_stats.json`

**Saved artifact:**
`data/llm_cache/2017-12-22.jsonl`

| Metric | Value | Note |
|--------|-------|------|
| python executable | `/home/manh/miniforge3/envs/stocks/bin/python` | plain `python` already points at the `stocks` env |
| cache files | `730 -> 731` | one new cache day written |
| processed day | `2017-12-22` | resumed from the expected frontier |
| next missing day | `2017-12-23.jsonl` | first raw news date not yet cached |
| filtered articles | `139` | loaded `143`, filtered `139` |
| parsed ok | `20` | no parse failures |
| parse_fail | `0` | clean parse on completed rows |
| timeout_fail | `0` | no timeout-marked failures on the saved day |
| wall time | `312.0s` | one long day under rate-limit pressure |
| stop reason | `all google model daily limits exhausted` | run ended cleanly after one day |
| persisted key cooldowns | `3` | `api_key_cooldowns` now present in stats file |

**Result:**
The extractor resumed cleanly from the correct frontier and wrote one new cache day. The persisted cooldown state is now present in `artifacts/llm_runtime/hosted_model_stats.json`, so dead keys no longer reset to zero on restart. The run then stopped cleanly because the Google pool exhausted its available daily-limit / cooldown budget on this pass. This is a provider-budget stop, not an environment or sandbox failure.

**Verdict: MIXED**

---

## Branch decision

Keep the extractor branch active.
Do not start a new research branch yet.
Wait for Google limits / cooldowns to clear, then rerun:

```bash
python -u data_tools/extract_llm_news_features.py --provider google --workers 16 --timeout 45
```

Current frontier:
- cache files: `731 / 3750`
- next missing day: `2017-12-23.jsonl`

---

## Validation

Completed during the pass:
- confirmed `python` resolves to `/home/manh/miniforge3/envs/stocks/bin/python`
- confirmed `artifacts/llm_runtime/hosted_model_stats.json` now includes `api_key_cooldowns`
- confirmed `data/llm_cache/2017-12-22.jsonl` was written

Verdict:
- `S126 resume`: **MIXED**
