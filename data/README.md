# Data Contract

Canonical contract for the shared root `data/` warehouse.

This file exists because the detailed inventories previously lived mainly under
`alpha-research-lab/notes/data_sources.md` and
`alpha-research-lab/data_tools/README.md`, but the actual shared data root did
not have its own contract file.

## Authority

- Canonical shared data root: `/home/manh/stocks/data`
- Primary producer repo: `alpha-research-lab/`
- Detailed operator inventory: `alpha-research-lab/notes/data_sources.md`
- Tool ownership reference: `alpha-research-lab/data_tools/README.md`

Operational rule:
- prefer root `data/` over repo-local paths
- treat raw acquisition surfaces separately from published feature contracts
- do not assume a raw source is safe for historical backtests just because it is present

## Available Surfaces

| Path | Status | Source | Owner script(s) | Notes |
|------|--------|--------|-----------------|-------|
| `data/stock/` | available | VCI via `vnstock` | `fetch_stock.py`, `fetch_hose_universe.py`, `fetch_refresh_all.py` | Canonical daily HOSE price history and related intervals |
| `data/news/cafef/raw/` | available, large, not in git | CafeF article archive | `fetch_news_archive.py`, `fetch_news.py` | Raw article JSONL archive |
| `data/llm_cache/` | available | LLM extraction cache over CafeF news | `extract_llm_news_features.py` | Input cache for LLM news features |
| `data/fx-commodities/` | available | yfinance | `fetch_fx_commodities.py`, `fetch_global_macro.py` | Global macro and proxy basket |
| `data/macro/` | available | FRED and derived builders | `fetch_fred_macro.py`, `build_macro_regime_features.py` | Macro series and derived regime surface |
| `data/dividend_cache/` | available | vnstock / company events | `fetch_dividend_events.py` | Raw dividend-event cache |
| `data/fundamentals_cache/` | available | vnstock fundamentals | `fetch_fundamentals.py`, `fetch_all_stock_fundamentals.py` | Raw ratios / statements cache |
| `data/insider_cache/` | available | CafeF `GDCoDong` | `fetch_insider_deals.py` | Raw insider and large-holder disclosures for the HOSE universe |
| `data/foreign_flow/cafef/` | available | CafeF `GDKhoiNgoai` | `fetch_cafef_foreign_flow.py` | Raw historical foreign-flow archive |
| `data/order_stats/cafef/` | available | CafeF `ThongKeDL` | `fetch_cafef_order_stats.py` | Raw daily order-statistics summary, not depth |
| `data/proprietary_trading/cafef/` | available with source-side holes | CafeF `GDTuDoanh` | `fetch_cafef_proprietary_trading.py` | Raw daily proprietary-trading summary |
| `data/foreign_flow_forward/vci_price_board/` | available, forward-only | VCI price board | `collect_forward_foreign_flow.py` | Current-day accumulation snapshots only |
| `data/official_disclosures/hnx/` | partially available | HNX mobile official issuer-disclosure site | `fetch_hnx_official_disclosures.py` | Full official issuer universe is fetchable now; per-ticker disclosure history is wired, and transaction PDF extraction is available when attachments are downloaded |
| `data/features/` | available | research builders over raw inputs | multiple builders in `alpha-research-lab/data_tools/` | Shared published feature surfaces, including RL matrix, event surface, execution flags, activation surfaces, and recommendations |
| `data/labels/` | available | research label builders | multiple label/build scripts | Shared label surfaces used by lab workflows |

## Official Disclosure Subcontract

### `data/official_disclosures/hnx/`

Purpose:
- official HNX / UPCoM issuer universe
- official publication timestamps for issuer disclosures
- exchange-hosted attachment links and optional downloaded PDFs
- future support for official-source timing and HNX / UPCoM disclosure research

Produced by:
- `alpha-research-lab/data_tools/fetch_hnx_official_disclosures.py`

Current contract:
- `issuer_universe.json`
- `issuer_universe.parquet`
- `issuer_news.parquet` after a ticker crawl
- `issuer_news_attachments.parquet` after a ticker crawl
- `issuer_transaction_disclosures.parquet` after a ticker crawl
- `issuer_transaction_attachment_extracts.parquet` after a transaction-attachment parse run
- `attachments/<TICKER>/...pdf` after attachment download
- `extracted_text/<TICKER>/...txt` after text extraction or OCR
- `_easyocr_models/` after the first OCR-enabled run
- `manifest.json`

Important limitations:
- default fetch is universe-only unless tickers or `--fetch-all-linked` are supplied
- article attachments are only downloaded when `--download-attachments`, `--download-transaction-attachments`, or `--parse-transaction-attachments` is supplied
- transaction parsing is attachment-level and raw-source only; it does not publish a model feature contract by itself
- OCR is now available through EasyOCR for scanned transaction PDFs, and extracted text is cached locally so the extract table can be rebuilt without refetching HNX
- use `--refresh-transaction-text-cache` if the OCR backend changed and you want to regenerate those cached text files from local PDFs
- OCR output is still noisy, so extracted tables should be treated as assisted raw-source normalization rather than final truth
- latest-run parquet outputs are rewritten to match the current request scope; this root is not an append-only historical crawl ledger
- this is a raw official source surface, not a published feature contract
- HSX official disclosures are still source-blocked here because the current HSX SPA/API route has not yet been resolved into a stable crawler contract

## Unavailable Or Still Blocked

| Desired data | Current state | Reason / note |
|--------------|---------------|---------------|
| Historical full order-book depth | unavailable | Open stack does not provide historical depth archive |
| Historical queue position | unavailable | Not reconstructable from current raw sources |
| Historical auction-book state | unavailable | Not present in current open sources |
| Backfillable HSX official disclosure history | blocked | HSX site is a SPA and the stable disclosure API/route contract is still unresolved locally |
| Structured SSC disclosure API | unavailable | SSC portal remains HTML-first rather than a stable structured API |
| Historical liveboard depth for dates never recorded | unavailable | Forward collection cannot repair missing history |

## Published Feature Surfaces

These are shared consumer-facing contracts, not raw-source caches:

- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/features/activation_state_daily.parquet`
- `data/features/activation_meta_daily.parquet`
- `data/features/event_surface_daily.parquet`
- `data/features/recommendations/<profile>/latest_candidates.parquet`

## Maintenance Rule

When a new shared dataset root or canonical source is added:
- update this file
- update root `README.md`
- update `AGENTS.md`
- update `alpha-research-lab/README.md`
- update `alpha-research-lab/notes/data_sources.md`
- update `alpha-research-lab/data_tools/README.md`
