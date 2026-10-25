import numpy as np
import pandas as pd

from vn_stock_rl.trade_episode.phase4d_experiment_support import _prediction_rows
from vn_stock_rl.trade_episode.phase4d_supervised import ExitExamples, FittedExitModel


def test_constant_and_age_baseline_predictions_do_not_require_market_matrix():
    metadata = pd.DataFrame(
        {
            "ticker": ["FPT", "FPT", "FPT"],
            "ticker_group": ["training_universe"] * 3,
            "year": [2023] * 3,
            "split": ["exploratory"] * 3,
        }
    )
    examples = ExitExamples(
        market_x=np.ones((3, 2)),
        alpha_x=np.ones((3, 3)),
        age_x=np.asarray([[0.01], [0.02], [0.03]]),
        target=np.asarray([-0.1, 0.0, 0.1]),
        metadata=metadata,
        sample_weight=np.ones(3),
    )
    models = {
        "constant_mean": FittedExitModel("constant_mean", "constant", (), constant=0.0),
        "age_only_ridge": FittedExitModel("age_only_ridge", "age_only", ("age",), constant=0.0),
        "ridge_market": FittedExitModel("ridge_market", "market_only", ("x",), constant=0.0),
        "ridge_market_alpha": FittedExitModel(
            "ridge_market_alpha", "market_plus_alpha", ("x",), constant=0.0
        ),
    }
    rows = _prediction_rows(examples, models)
    assert len(rows) == 8
    overall = [row for row in rows if "ticker" not in row]
    assert all(row["rows"] == 3 for row in overall)
