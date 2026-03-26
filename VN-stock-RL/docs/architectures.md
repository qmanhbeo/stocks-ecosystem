# Architectures

Feature extractors now live under `vn_stock_rl/policies/extractors/`.

The canonical runtime package is now:

```text
vn_stock_rl/
  config/
  env/
  training/
  evaluation/
  policies/
  data_tools/
  utils/
```

The canonical runtime surface is:

- `vn-stock-train`
- `vn-stock-evaluate`
- `vn-stock-count-params`
