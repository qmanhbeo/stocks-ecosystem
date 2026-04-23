# Stocks Ecosystem

Workspace root for the VN stock research and RL ecosystem.

This is no longer a set of fully self-contained repos. The projects below now operate as one shared system around a common root data store:

- `data/`: canonical shared data root
- `alpha-research-lab/`: alpha research, feature generation, auto-labelling, supervised signal pipeline
- `manual-label-factory/`: manual buy-zone labelling UI
- `shared-recommendation/`: shared model-agnostic recommendation contracts, artifact registry, and candidate writer
- `RL-trading-agent/`: RL training, evaluation, and feature consumption
- `media-output/signal-xs-momentum/`: older signal-specific project kept alongside the ecosystem

## Canonical Ownership

- Raw and published research data live under `data/`
- Research producer code lives under `alpha-research-lab/`
- Manual label UI code lives under `manual-label-factory/`
- Shared recommendation contracts live under `shared-recommendation/`
- RL consumer/runtime code lives under `RL-trading-agent/`
- `alpha-research-lab/` resolves shared datasets from the root `data/` directory directly; a local `alpha-research-lab/data` symlink is optional compatibility only

## Data Layout

Shared `data/` currently contains both raw inputs and processed research outputs, including:

- `data/README.md`
- `data/stock/`
- `data/news/`
- `data/fx-commodities/`
- `data/features/`
- `data/features/recommendations/`
- `data/labels/`
- `data/dividend_cache/`
- `data/fundamentals_cache/`
- `data/insider_cache/`
- `data/foreign_flow/`
- `data/order_stats/`
- `data/proprietary_trading/`
- `data/foreign_flow_forward/`
- `data/official_disclosures/`
- `data/llm_cache/`

This means the root data directory is the canonical dataset surface for the whole ecosystem.

`data/llm_cache/` is the per-day CafeF LLM extraction cache: one JSON object per filtered article, used as the input to `alpha-research-lab/data_tools/build_llm_news_features.py`.

The canonical news pipeline can now also publish a separate local Vietnamese-encoder lane under `data/features/news/`: whole-article PhoBERT sentiment writes dedicated `datasets/phobert_*` artifacts, uses a tagged-only `phobert_input_articles.parquet` staging cache plus resumable checkpoint shards for long backfills, and publishes additive `phobert_*` columns in `predictions/*_news_features.parquet`. This is isolated from `data/llm_cache/` and does not overwrite the hosted LLM semantic/event surface.

`data/foreign_flow/` is the historical CafeF foreign-investor-flow archive. It
stores per-ticker daily buy/sell/net volume and value, remaining foreign room,
and reported ownership percentage from
`alpha-research-lab/data_tools/fetch_cafef_foreign_flow.py`. The source has now
been backfilled and audited, but it remains a raw research surface until a
separate published feature contract passes.

`data/order_stats/` is the historical CafeF order-statistics archive from the
`ThongKeDL` page-2 stock-history endpoint. It stores daily buy/sell order
counts, posted order volumes, average order size, and raw buy-sell volume
imbalance from `alpha-research-lab/data_tools/fetch_cafef_order_stats.py`. This
is a raw summary surface, not historical order-book depth.

`data/proprietary_trading/` is the historical CafeF proprietary-trading archive
from the `GDTuDoanh` page-4 stock-history endpoint. It stores daily proprietary
desk buy/sell volume and value from
`alpha-research-lab/data_tools/fetch_cafef_proprietary_trading.py`. This is a
raw source surface, not a published research feature contract.

`data/foreign_flow_forward/` is the forward-only VCI board foreign-flow archive
started on `2026-04-09`. It stores current-day accumulated foreign buy/sell and
foreign-room snapshots from `alpha-research-lab/data_tools/collect_forward_foreign_flow.py`.
It is not a historical backfill and is not backtestable until enough forward
collection days accrue.

`data/official_disclosures/` is the root official-disclosure acquisition
surface. The first wired contract is `data/official_disclosures/hnx/`, which
can store the official HNX / UPCoM issuer universe, official disclosure
timestamps, attachment metadata, optionally downloaded exchange-hosted PDFs,
and attachment-level transaction extracts from
`alpha-research-lab/data_tools/fetch_hnx_official_disclosures.py`. This is a
raw source surface, not yet a published feature contract. OCR text caches for
scanned filings also live under that root so local re-parsing does not require
re-fetching HNX.

## Workflow

1. Research and feature generation happen in `alpha-research-lab/`
2. Manual buy-zone annotation happens in `manual-label-factory/`
3. Published artifacts are written into root `data/`
4. The lab publishes a consolidated RL signal matrix at `data/features/xs_rl_signal_matrix.parquet`
5. The lab publishes shared execution tradability flags at `data/features/execution/tradability_daily.parquet`
6. The lab now also publishes the canonical corporate-event surface at `data/features/event_surface_daily.parquet`
7. The lab can publish canonical model-agnostic recommendation candidates at `data/features/recommendations/<profile>/latest_candidates.parquet`
8. RL training/evaluation in `RL-trading-agent/` reads from root `data/`, either directly from existing per-ticker exports or via the adapter command `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`

## Fresh Start

If you are starting this workspace fresh, read in this order:

1. `README.md`
2. `data/README.md`
3. `alpha-research-lab/README.md`
4. `alpha-research-lab/notes/next_steps.md`
5. `alpha-research-lab/notes/session_74_log.md`
6. `alpha-research-lab/README_for_AGENTS.md` if you are continuing research or making repo changes as an agent

If you are picking up the currently active timing-research branch, continue with:

7. `alpha-research-lab/notes/timing_data_acquisition_plan.md`
8. `alpha-research-lab/notes/timing_data_source_scorecard.csv`

If you are working on RL runtime or feature consumption, also read:

9. `RL-trading-agent/README.md`
10. `RL-trading-agent/AGENTS.md`

Current active live branch:
- `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

Current research posture:
- keep the live sticky branch frozen
- do not retune timing rules on `2026+`
- keep `llm-cache-fill` as the highest-value blocked branch
- if a non-LLM branch is intentionally reopened, prefer:
  - richer company-event timing follow-through on the saved CafeF event-v2 work
  - a different historical foreign-flow thesis such as room-change or ownership-regime transitions, not more raw buy/sell rank retunes
  - genuinely new acquisition work such as queue / order-book data, not another OHLCV proxy

## Strategy Guardrails

This workspace is long-only by policy.

- no synthetic hedges
- no equity shorting assumptions
- no research branches that depend on unrealistic short exposure
- if a strategy cannot make money realistically as long-only in Vietnam, it is not a valid direction for this ecosystem

This rule applies to both research in `alpha-research-lab/` and any future RL runtime work in `RL-trading-agent/`.

## Bootstrap

From the workspace root, install the current shared Python stack with:

```bash
conda create -n stocks python=3.10
conda activate stocks
pip install -r requirements.txt
```

This installs the shared `shared-market-rules` and `shared-recommendation` packages, `RL-trading-agent` in editable mode, and the extra research/UI packages used by `alpha-research-lab` and `manual-label-factory`.

For a stricter pinned install focused on reproducibility, use:

```bash
conda create -n stocks python=3.10
conda activate stocks
pip install -r requirements.lock.txt
```

Use `requirements.txt` for a live editable dev setup. Use `requirements.lock.txt` when you want the workspace dependency surface to stay fixed.
The lock file is intentionally Python-3.10-focused and pins the direct dependency surface only; it is not a full transitive hash lock.

Optional WSL NVIDIA CUDA bootstrap:

```bash
conda activate stocks
bash scripts/bootstrap_wsl_cuda.sh
conda deactivate && conda activate stocks
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

This keeps the repo dependency contract CPU-safe by default while providing a tested CUDA profile for local WSL GPU work. The bootstrap installs the current driver-compatible `cu121` PyTorch wheel set from [requirements-cuda-cu121.txt](/home/manh/stocks-ecosystem/requirements-cuda-cu121.txt), and adds conda activation hooks so `/usr/lib/wsl/lib` is visible to CUDA-aware Python packages.

Known tradeoff: packages that require newer torch floors, such as `marker-pdf` or `surya-ocr`, should live in a separate OCR-focused environment instead of the shared `stocks` env.

## Shared Market Rules

Execution reality is an ecosystem-level contract, not a repo-local detail.

- Canonical spec: `docs/execution_reality.md`
- Shared rule code: `shared-market-rules/shared_market_rules/`
- Producer artifact: `data/features/execution/tradability_daily.parquet`

Current strict-core defaults:
- signal at `T` close
- fill at `T+1` open
- earliest legal sell decision after a buy at `T+1` open is `T+3` close
- earliest exit fill is `T+4` open
- zero-volume blocks both sides
- ceiling blocks buys
- floor blocks sells

## Shared Recommendation Contract

Recommendation generation is now a workspace-level contract, not a repo-local helper.

- Shared package: `shared-recommendation/shared_recommendation/`
- Canonical artifact root: `data/features/recommendations/<profile>/`
- Default candidate artifact: `data/features/recommendations/<profile>/latest_candidates.parquet`
- Default manifest: `data/features/recommendations/<profile>/manifest.json`
- Alpha producer entrypoint: `cd alpha-research-lab && python analysis/live_recommendation.py`

This layer standardizes artifact resolution, adapter scoring, policy gating, and candidate-table writing across alpha and RL-adjacent consumers. It does not own model training or portfolio backtesting.

## Current Reality

- `alpha-research-lab/data/` has been fully moved into root `data/`
- `RL-trading-agent` has already been cleaned up toward a consumer-only role
- The workspace behaves like one ecosystem even though code is still split across multiple git repos

## Recommended Next Step

If you want the repository structure to match reality, promote this root into the long-term ecosystem repo and treat the child repos as subprojects inside it.
