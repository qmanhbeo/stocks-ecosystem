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

## F274: The Local-News Branch Should Default To PhoBERT Plus A Narrow Ollama Residual Taxonomy, Not To The Old Hosted Full-Schema Dependency (2026-04-24, Session 171)

Finding:
- the active local-news production contract is now:
  - PhoBERT sentiment
  - PhoBERT `forward_looking`
  - a narrowed Ollama residual taxonomy with:
    - `event_family`
    - `impact_scope`
    - `source_authority`
    - `is_rumor`
    - local confidence / abstain diagnostics
- deterministic ticker linkage remains outside the model
- the canonical aggregate exporter now merges the residual daily features into
  the per-ticker news prediction files

Why it matters:
- the local-news branch no longer needs to treat hosted cache fill as the
  default next production dependency
- the repo can move forward with a coherent local-first contract instead of
  pretending the old hosted full schema is still required for day-to-day local
  operation
- the residual semantic scope is now small enough to audit honestly and expand
  only if it proves useful

Limit:
- PhoBERT still owns only sentiment and forward-looking in code today
- additional local heads such as routing / source-type remain future work
- legacy hosted labels may still be useful as offline bootstrap material, but
  they are no longer the default blocker for the local-news branch

Source sessions:
- `notes/session_171_log.md`

## F275: Separate PhoBERT Heads For `article_scope` And `source_type` Fit The Existing Low-Resource Forward-Looking Pattern Better Than A New Custom Pipeline (2026-04-24, Session 172)

Finding:
- the repo now has a shared PhoBERT binary-head path that cleanly supports:
  - teacher-label reconstruction from legacy `data/llm_cache/`
  - tagged-only stage datasets with date splits
  - sequential candidate training
  - winner-based publish/export
- that shared path now powers two additional local heads:
  - `phobert_article_scope`
  - `phobert_source_type`
- both heads are wired into the canonical combined news export contract

Why it matters:
- the local-news branch no longer has to treat `market_news` vs `stock_news`
  and `official_or_regulatory` vs `media_or_commentary` as vague future work
- the repo can expand local PhoBERT coverage by reusing one low-resource
  pattern instead of growing new ad hoc training and publish scripts per head
- the publish path now handles multi-ticker fanout safely by scoring unique
  article rows once before joining back onto tagged ticker rows

Limit:
- this session implemented the code path and contract wiring, not a fresh real
  training/evaluation pass for the two new heads
- the new heads still need honest quality gates before they should be trusted
  as promoted alpha inputs

Source sessions:
- `notes/session_172_log.md`

## F276: Reusing A Proven PhoBERT Lane Means Copying Its Trainer Observability And Local-First Runtime Behavior, Not Just Its High-Level Stage Names (2026-04-25, Session 173)

Finding:
- the new binary PhoBERT heads were only partially aligned with the proven
  `forward_looking` lane until the trainer itself copied the same runtime
  behavior:
  - epoch-level progress logging
  - per-epoch status writes
  - in-progress candidate state
  - gradient-step safety behavior
  - local-file-first model loading
- once that trainer-level parity was restored, the `article_scope` and
  `source_type` paths were much closer to the intended operator contract

Why it matters:
- "same pipeline" is not enough if the runtime surface feels silent or behaves
  differently under the same workstation constraints
- on this box, network-first startup behavior and silent multi-minute epochs
  are operator bugs, not just cosmetic differences
- future agents should copy the full working lane first and only generalize
  after the runtime contract stays intact

Limit:
- this finding is about pipeline/runtime parity, not model quality
- the new heads still need their real canary train/publish runs completed

Source sessions:
- `notes/session_173_log.md`

## F277: When A Local-Only PhoBERT Lane Is The Intended Default, The Offline Runtime Guard Belongs In Repo Code Rather Than In Shell Prefixes (2026-04-25, Session 174)

Finding:
- the local PhoBERT lanes now apply the offline Hugging Face / transformers
  defaults from repo code when local-file-first loading is enabled
- that behavior now covers both CLI entrypoints and the underlying model-load
  paths for:
  - `forward_looking`
  - `article_scope`
  - `source_type`

Why it matters:
- users should not need to remember shell-level environment prefixes just to
  get the repo's intended safe local behavior
- the repo contract is more reliable when local-only runtime posture is encoded
  directly in code instead of scattered across docs and operator habits
- this also makes the local PhoBERT lanes more consistent with the broader
  preference-skill contract: working defaults should become repo defaults where
  possible

Limit:
- this hardens runtime behavior, not model quality
- a fresh real canary run is still needed to overwrite any stale status from
  earlier interrupted attempts

Source sessions:
- `notes/session_174_log.md`

## F278: On This WSL Workstation, Silent CPU Fallback For Heavy PhoBERT Jobs Is An Operator Bug And Should Fail Fast When The WSL CUDA Runtime Exists But The Session Hides `/dev/dxg` (2026-04-25, Session 175)

Finding:
- the workstation's real WSL runtime exposes the GPU correctly:
  - `/usr/lib/wsl/lib/nvidia-smi` reports the RTX 3050 Laptop GPU
  - PyTorch reports `cuda_available=True` outside the restricted sandbox
- the default Codex sandbox hides `/dev/dxg`, so the same PhoBERT commands can
  otherwise fall back to CPU even though the machine itself is GPU-capable
- the repo now treats that specific WSL shape as a hard runtime error for the
  heavy PhoBERT train/publish paths unless `NEWS_FEATURES_ALLOW_CPU=1` is set
  explicitly

Why it matters:
- this prevents multi-minute or multi-hour accidental CPU runs on a box where
  CUDA is actually available
- future agent runs can distinguish "sandbox hid the GPU" from "the machine has
  no GPU" immediately instead of wasting time on false runtime assumptions
- the repo now encodes the intended workstation posture directly: use CUDA by
  default, fail fast if the session hides it, and allow CPU only as an
  explicit override

Limit:
- this does not make a restricted sandbox expose `/dev/dxg`; it makes the
  wrong runtime fail early and loudly
- heavy agent-run PhoBERT commands still need an unsandboxed session to use the
  real WSL GPU

Source sessions:
- `notes/session_175_log.md`

## F279: The New Binary PhoBERT Heads Needed The Forward-Looking Publish Checkpoint Contract Too, Not Just The Forward-Looking Trainer Contract (2026-04-25, Session 176)

Finding:
- the binary-head publish path for `article_scope` and `source_type` now uses
  the same durable shape as the forward-looking publish lane:
  - checkpoint manifest
  - per-batch shard files
  - resume-safe batch skipping
  - finalize-from-shards before public dataset promotion
- before this change, binary-head publish wrote only final outputs and had to
  restart from scratch after interruption even though the forward-looking lane
  already had the correct pattern

Why it matters:
- the local PhoBERT branch now has a more coherent operational contract across
  all three heads
- interrupted article-scope/source-type publish runs no longer force a full
  rescoring restart
- this closes another concrete gap where "copied from forward-looking" was only
  partly true at runtime

Limit:
- this improves publish resume safety, not train-time optimizer resume
- binary-head training still resumes only at the candidate / completed-epoch
  level, not at the exact mid-epoch optimizer state

Source sessions:
- `notes/session_176_log.md`

## F280: Semantic PhoBERT Binary Heads Need A Calibrated Decision Threshold And A Task-Appropriate Split Contract; A Hard `0.5` Cutoff Plus Reused Time Split Can Make A Usable Checkpoint Look Dead (2026-04-25, Session 177)

Finding:
- the first real `article_scope` canary looked catastrophically bad under the
  inherited forward-looking runtime contract, but the saved checkpoint still
  had usable ranking signal
- the actual failure was the combination of:
  - a reused date split that created a sharp label-prevalence shift across
    train / val / test
  - a hard `0.5` positive cutoff during evaluation and publish
- once the same saved winner was probed with a validation-calibrated threshold,
  the test F1 moved from effectively zero to a materially usable level without
  changing the underlying model weights

Why it matters:
- for semantic article classifiers, copying the forward-looking lane literally
  can be the wrong operator contract even if the code shape is similar
- binary-head training and publish must persist and reuse the calibrated
  threshold rather than pretending every head wants the same default cutoff
- split strategy should be a head-level choice, not an accidental inheritance
  from another task

Limit:
- this finding does not claim the current `article_scope` teacher labels are
  fully clean
- the repaired contract still needs a fresh real retrain before the new
  article-scope surface should be trusted downstream

Source sessions:
- `notes/session_177_log.md`

## F281: The Semantic Binary PhoBERT Heads Are Now Trained And Published Under A Restart-Safe Local Contract (2026-04-25, Session 178)

Finding:
- `article_scope` and `source_type` now have completed real `phobert_base`
  train and publish runs under the repaired binary-head contract
- binary-head training now writes mid-epoch model / optimizer / scaler
  checkpoints, so aborts no longer lose a whole epoch
- binary-head publish now rejects stale complete checkpoints when their stored
  top-level model id does not match the current winner model id
- the completed published parquets were sanity-checked to contain the new
  trained model ids rather than the old fake scorer ids

Why it matters:
- the local BERT path is no longer blocked on the two new semantic heads
- future rebuilds can recover from both train interruptions and publish
  interruptions using structured checkpoint state
- the stale-publish bug was concrete: a previous complete checkpoint could
  reuse old `fake-*` article shards even after a new winner was trained

Current artifacts:
- `article_scope`:
  - model id `phobert_article_scope::20260425T141320974641+0000::phobert_base`
  - threshold `0.28`
  - test F1 `0.3743236596163306`
  - test ROC-AUC `0.7233646025752045`
- `source_type`:
  - model id `phobert_source_type::20260425T161859367170+0000::phobert_base`
  - threshold `0.81`
  - test F1 `0.7869481765834933`
  - test ROC-AUC `0.9136848733161289`

Limit:
- this is a production-surface completion finding, not an alpha-promotion
  finding
- the next step is a downstream feature audit to measure whether these BERT
  fields add predictive or gating value

Source sessions:
- `notes/session_178_log.md`

## F282: The Default Local Ollama Residual Task Should Be Event-Family-Only And BERT-Gated, Not A Broad Full-Field Backfill (2026-04-25, Session 179)

Finding:
- after `article_scope` and `source_type` were trained, the remaining useful
  local-generator task narrowed further
- the best low-resource Ollama prompt in the Session 179 grid was:
  - bottom-schema JSON
  - `field_set=event_only`
  - `num_ctx=512`
  - first `300` words only
  - compact Vietnamese taxonomy hints
- on the mixed `8` article probe it reached:
  - parse OK `1.0`
  - event-family accuracy `0.625`
  - average `1.7357` seconds/article

Why it matters:
- asking the `3B` generator for scope/source/rumor by default is no longer the
  right tradeoff once PhoBERT heads own scope and source-type locally
- top-schema prompts at `512` context remain brittle; schema must stay near the
  end of the prompt for this small model
- CSV can look attractive on throughput but is semantically unsafe because it
  emits non-taxonomy labels
- the full tagged universe still projects to a multi-day local run even after
  prompt trimming, so BERT-gated priority backfills are the sane default

Current operational state:
- the guarded Ollama production defaults now use the event-only prompt
- a priority backfill is running in tmux session `ollama_guarded_backfill`
- current gate:
  - `phobert_article_scope_prob_positive >= 0.28`
- gated input rows:
  - `146872`
- checkpoint rows:
  - `200`

Limit:
- the event-family probe sample is still small
- the running backfill is a priority stock-news residual surface, not a full
  `342135` article semantic completion
- `is_rumor` remains better treated as unknown / conservative until a dedicated
  cheap detector or better local prompt is proven

Source sessions:
- `notes/session_179_log.md`
