# Findings 271-300

## F271: PhoBERT Forward-Looking Candidate Training On The Current Box Needs A Trusted Legacy-Weights Fallback And FP32 Model Init (2026-04-24, Session 166)

Session 166 took the first real watchdog-managed PhoBERT forward-looking
canary through the production teacher / stage build and into candidate startup
on the current workstation.

The canary established two durable runtime facts about the current environment:
- `transformers 4.57.6` with `torch 2.5.1+cu121` rejects legacy `.bin`
  checkpoint loads under `weights_only=True`
- the explicit `vinai/phobert-base` backbone therefore needs a trusted
  `weights_only=False` retry unless a safetensors checkpoint is available
- once the backbone is loaded, the training model must stay FP32 at load time
  and let AMP own mixed precision
- direct FP16 model instantiation caused:
  - `ValueError: Attempting to unscale FP16 gradients`

This did not invalidate the forward-looking lane itself.
The real production teacher and stage artifacts built cleanly:
- teacher rows:
  - `79,284`
- stage rows:
  - `40,065`
- split counts:
  - `train 26,113`
  - `val 6,736`
  - `test 7,216`

### Key finding
On this workstation, the PhoBERT forward-looking training lane is operationally
compatible with the canonical `vinai/phobert-base` backbone only if legacy
`.bin` checkpoints are treated as trusted explicit inputs for the initial load,
and the training model stays FP32 when it is instantiated.

**Implication:** keep the trusted `.bin` fallback local to the explicit
candidate list, save trained local checkpoints as safetensors, and do not
reintroduce direct FP16 model initialization in this lane. If the environment
is later upgraded to `torch>=2.6` or the backbone ships safetensors, reevaluate
whether the trusted legacy-load fallback is still needed.

## F272: Plan Local ML In Alpha-Lab Against A `3GB VRAM / 10GB RAM` Safety Budget (2026-04-24, Session 167)

Finding:
- alpha-lab should no longer plan local-ML and local heavy-script work against
  the older `6GB VRAM / 8-10GB RAM` assumption
- the safer default planning budget is now:
  - `3GB VRAM`
  - `10GB RAM`

Why it matters:
- the visible workstation totals can be higher than the amount of memory that is
  safe to rely on during real WSL runs
- future agents should leave the remaining headroom for background load,
  allocator spikes, and watchdog recovery rather than designing right up to the
  observed ceiling

Source sessions:
- `notes/session_167_log.md`

## F273: Heavy `data_tools/` Jobs In Alpha-Lab Should Expose A Canonical Status File Plus A Natural Durable Resume Boundary (2026-04-24, Session 168)

Finding:
- the alpha-lab long-job contract is now explicit for the materially touched
  `data_tools/` producers:
  - canonical status file under
    `alpha-research-lab/artifacts/job_status/<job>.json`
  - milestone logging
  - durable progress at the script's natural recovery unit

The durable recovery unit is script-specific:
- `fetch_hnx_official_disclosures.py`
  - ticker-level shard state under
    `data/official_disclosures/hnx/per_ticker/`
- `build_llm_news_features.py`
  - staged per-day aggregate shards under
    `data/features/_llm_news_build_stage/`
- `extract_llm_news_features.py`
  - day-level cache files under `data/llm_cache/`
- `extract_llm_news_features_legacy.py`
  - same day-level cache contract, now with structured status
- `fetch_news.py`
  - flushed raw JSONL batches plus crawler ledgers under `data/news/cafef/`

Why it matters:
- recovery no longer depends on replaying raw logs to infer where the job was
- completed work now survives aborts at the script's natural boundary
- operators can rerun the same command first and inspect the status file before
  widening scope or deleting state

Limit:
- this did not rewrite the legacy extractor into a small staged architecture;
  it made the legacy surface observable and resumable enough for continued
  compatibility use

Source sessions:
- `notes/session_168_log.md`
