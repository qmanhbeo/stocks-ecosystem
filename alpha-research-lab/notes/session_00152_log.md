# Session 152 Log — LLM Extractor Multi-Key Fanout Repair (2026-04-10)

## Objective

Resume `llm-cache-fill`, diagnose why the Google-only extractor was still
stalling on `2018-01-15`, and restore a stable frontier backfill without
reopening any research branch.

This session did not change the live alpha branch.
It stayed on extractor / data-operations work only.

---

## What changed

Patched the canonical Google extractor path:
- `data_tools/extract_llm_news_features.py`
- `data_tools/extract_llm_news_features_legacy.py`
- `tests/test_extract_llm_news_features.py`

### S127 — Google Workhorse Multi-Key Fanout
**Hypothesis:**
The extractor was still leaving most Google capacity idle because API keys were
assigned per model spec. With only `gemini-3.1-flash-lite-preview` healthy, the
current Google pool effectively used one key while the other configured Google
keys sat unused.

**Root cause:**
`_resolve_google_api_keys_for_specs()` mapped one API key to each Google model
spec. In the live state on `2026-04-10`, only
`google:gemini-3.1-flash-lite-preview` had `failure_streak == 0`, so the
remaining `GOOGLE_API_KEY*` entries were stranded behind dead or degraded
models.

**Fix:**
- added `slot_id` to `HostedModelSpec`, so one hosted model can be represented
  by multiple scheduler-visible slots without changing the actual API model name
- added `_expand_google_specs_across_keys()` in the canonical extractor
- when exactly one healthy Google model remains, or the user explicitly selects
  a single Google model via `--model`, the extractor now fans that model out
  across all configured Google keys as `@gk1`, `@gk2`, ...
- added a regression test that proves one healthy Google model expands across
  all configured keys instead of leaving four keys idle

**Validation:**
- `python -m py_compile data_tools/extract_llm_news_features.py data_tools/extract_llm_news_features_legacy.py tests/test_extract_llm_news_features.py`
- `python -m pytest tests/test_extract_llm_news_features.py`
- result: `36/36` passed

---

## Live validation

### Pre-fix operator finding
The old Google-only run from `2018-01-15` could stay alive for minutes without
writing `data/llm_cache/2018-01-15.jsonl`. Runtime stats advanced, but the day
did not flush, and the effective throughput was unusably low.

### Patched one-day probe
**Command:**
```bash
python -u data_tools/extract_llm_news_features.py \
  --provider google \
  --model gemini-3.1-flash-lite-preview \
  --workers 4 \
  --batch-size 10 \
  --timeout 45 \
  --log-every-batches 1 \
  --date-from 2018-01-15 \
  --date-to 2018-01-15
```

**Result:**
- startup pool showed all five Google key slots:
  - `google:gemini-3.1-flash-lite-preview@gk1`
  - `google:gemini-3.1-flash-lite-preview@gk2`
  - `google:gemini-3.1-flash-lite-preview@gk3`
  - `google:gemini-3.1-flash-lite-preview@gk4`
  - `google:gemini-3.1-flash-lite-preview@gk5`
- `2018-01-15.jsonl` written successfully
- `145 / 145` filtered articles parsed cleanly
- `0` parse failures
- `0` timeout failures
- wall time `52.5s`
- throughput `2.76` filtered art/s

### Frontier run after the fix
**Command:**
```bash
python -u data_tools/extract_llm_news_features.py \
  --provider google \
  --model gemini-3.1-flash-lite-preview \
  --workers 4 \
  --batch-size 10 \
  --timeout 45 \
  --date-from 2018-01-16
```

**Observed progress during this session:**
- `2018-01-16.jsonl` written
  - filtered `162`
  - parsed ok `162`
  - parse_fail `0`
  - timeout_fail `0`
  - wall time `61.1s`
  - two late `503` retries recovered inside the day
- `2018-01-17.jsonl` written
  - filtered `150`
  - parsed ok `150`
  - parse_fail `0`
  - timeout_fail `0`
  - wall time `58.5s`
- run crossed into `2018-01-18` cleanly during monitoring
- later cache inspection showed the run had advanced through `2018-01-29`
  before stopping, with no extractor process left live

**Cache frontier at note time:**
- cache files: `767 / 3750`
- last completed day: `2018-01-29.jsonl`
- no extractor process live

---

## Branch decision

Keep `llm-cache-fill` as the top queue item.

Operational rule:
- use the explicit workhorse command, not the mixed Google pool
- do not use raw `provider=auto` for the frontier fill; the unrestricted auto
  pool still spends too much time on `403`-forbidden or timeout-prone routes
- if the live process dies, rerun the same explicit command and let cache-skip
  resume from the next missing day

Current restart command:

```bash
python -u data_tools/extract_llm_news_features.py \
  --provider google \
  --model gemini-3.1-flash-lite-preview \
  --workers 4 \
  --batch-size 10 \
  --timeout 45
```
