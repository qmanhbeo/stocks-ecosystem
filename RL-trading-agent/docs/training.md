# Training

Canonical command:

```bash
vn-stock-train --stock ACB --policy cnn-lstm --timesteps 500000
```

This command is installed from `pyproject.toml` when you run:

```bash
pip install -e ".[dev]"
```

## Architecture map

```text
data -> vn_stock_rl.env -> policy registry/config
     -> vn_stock_rl.training.cli -> SB3/RecurrentPPO
```

Use `vn-stock-train` as the canonical training entrypoint.
