# Manual Label Factory

Standalone workspace for hand-labelling buy zones against the shared `stocks/data` market dataset.

Run from this repo root:

```bash
python -m manual_label_factory.manual_label
```

The UI reads stock data from `/home/manh/stocks/data/stock` by default and writes label artifacts to the shared supervised-label directories under `/home/manh/stocks/data/labels/supervised/`.
