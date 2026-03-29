# Supervised Label

`research_pipelines/supervised_label/` is the canonical downstream supervised signal pipeline. It rebuilds favorable buy/hold regions into per-bar targets, trains a lightweight supervised model, exports per-bar probabilities, and publishes RL-ready signal parquet files into shared `stocks/data`.

Manual buy-zone labeling lives in `manual-label-factory`. Heuristic auto-labeling lives under `research_pipelines/signal_labelling/auto_label/`.

By default this pipeline resolves shared data under `/home/manh/stocks/data`. Override that with `STOCKS_DATA_ROOT` if you need a different workspace data root.

## Label Semantics

The UI saves hindsight-assisted region labels on a displayed chart chunk:

- Bars inside a selected region are labeled `1`.
- Bars outside the selected region but still inside that chunk are labeled `0`.

These labels are not online action labels and not ground-truth optimal actions. They are hindsight-assisted region annotations used to generate a supervised signal feature for RL.

## Directory Layout

```text
research_pipelines/signal_labelling/
`-- auto_label/          # Heuristic hindsight-assisted label generator

research_pipelines/supervised_label/
|-- core/                # Rebuild, feature export, merge helpers
|-- models/              # Dataset loader, baseline training, evaluation, predictions
|-- configs/             # Source-controlled config files
`-- tests/               # Signal-model and shared helper tests

stocks/data/
|-- labels/supervised/   # Splits, range labels, manifest
`-- features/signals/    # Exported datasets and per-bar signal predictions

artifacts/
`-- signal_models/       # Trained supervised model exports and evaluation plots
```

## Typical Workflow

For manual labeling, run the separate factory:

```bash
cd ../manual-label-factory
python -m manual_label_factory.manual_label
```

That command will:

- create supervised split files if they do not exist yet
- start a new labeling session
- launch the local Dash server on `http://127.0.0.1:8050`
- try to open your browser automatically

After you finish labeling, use the rebuild/export/train/predict commands only when you actually want to generate downstream artifacts.

## Full Workflow

1. Create or refresh supervised ticker splits.
2. Launch the labeling UI and label training-only chunks.
3. Validate saved label JSONL records.
4. Rebuild bar-level labels from the saved ranges.
5. Export the supervised dataset with leakage-safe features.
6. Train and evaluate the baseline signal model.
7. Generate per-bar signal probabilities for later RL feature merges.

The exported supervised dataset keeps the original ticker-level split metadata in `ticker_split`, persisted with the label/rebuild artifacts so later split refreshes do not rewrite provenance. Because v1 labels are created only from training tickers, it also adds a deterministic `dataset_split` column so the baseline model can reserve validation and test holdouts from labeled chunks without leaking across rows from the same chunk.

Heuristic auto labels follow that same pattern by default: generate labels on the ticker `train` split first, then let `export_supervised_dataset` assign chunk-level `dataset_split` values for supervised train/val/test holdouts.

## Commands

Validate labels:

```bash
python -m research_pipelines.supervised_label.core.validation
```

Rebuild bar labels:

```bash
python -m research_pipelines.supervised_label.core.rebuild_bar_labels
```

Auto-generate hindsight-assisted heuristic labels:

```bash
python -m research_pipelines.signal_labelling.auto_label --split train --horizon 20 --min-forward-return 0.08 --max-forward-drawdown -0.05
```

By default, the rebuild/export/train/evaluate/generate commands now process both `manual` and `auto` variants and keep their outputs separate:

- `data/features/signals/datasets/manual/` and `data/features/signals/datasets/auto/`
- `artifacts/signal_models/manual/` and `artifacts/signal_models/auto/`
- `data/features/signals/predictions/manual/` and `data/features/signals/predictions/auto/`

If you want to run only one branch, pass `--label-variant manual` or `--label-variant auto`.

Export supervised dataset:

```bash
python -m research_pipelines.supervised_label.core.export_supervised_dataset
```

Train baseline model:

```bash
python -m research_pipelines.supervised_label.models.train_signal_model
```

Evaluate baseline model:

```bash
python -m research_pipelines.supervised_label.models.evaluate_signal_model
```

Generate signal probabilities:

```bash
python -m research_pipelines.supervised_label.models.generate_signal_probs
```

## RL Integration

The exported prediction parquet files in `data/features/signals/predictions/manual/` and `data/features/signals/predictions/auto/` are the bridge back into RL. RL consumes the shared exported interface directly.

For RL training/evaluation, the default signal source is `data/features/signals/predictions/auto/`. Manual predictions remain available as an explicit override later via `--signal-prediction-dir`.

## Artifact Notes

- `data/labels/supervised/ranges/range_labels.jsonl` is append-only and human-readable.
- Raw market data stays in shared `stocks/data/stock/`; it is not copied into the pipeline package.
- Generated parquet datasets and prediction files are intentionally lightweight and inspectable.
