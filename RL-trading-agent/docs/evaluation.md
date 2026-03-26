# Evaluation

Canonical command:

```bash
vn-stock-evaluate --model artifacts/trained_models/example_run/model_best.zip --stock ACB --mode val
```

This command is installed from `pyproject.toml` when you run:

```bash
pip install -e ".[dev]"
```

Use `vn-stock-evaluate` as the canonical evaluation entrypoint.
