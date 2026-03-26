from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from typing import Any, Dict

def get_model(config: Dict[str, Any]):
    """Returns a model instance based on the configuration."""
    model_cfg = config.get("model", {})
    model_type = model_cfg.get("type", "linear_regression")
    params = model_cfg.get("params", {})

    if model_type == "linear_regression":
        return LinearRegression(**params)
    
    elif model_type == "mlp":
        # Default structure for MLP
        hidden_layers = params.get("hidden_layer_sizes", [64, 32])
        if isinstance(hidden_layers, list):
            hidden_layers = tuple(hidden_layers)
            
        return Pipeline([
            ("scaler", StandardScaler()),
            ("nn", MLPRegressor(
                hidden_layer_sizes=hidden_layers,
                activation=params.get("activation", "relu"),
                solver=params.get("solver", "adam"),
                max_iter=params.get("max_iter", 5000),
                random_state=42
            ))
        ])
    
    elif model_type == "xgboost":
        try:
            from xgboost import XGBRegressor
            return XGBRegressor(
                n_estimators=params.get("n_estimators", 100),
                max_depth=params.get("max_depth", 3),
                learning_rate=params.get("learning_rate", 0.1),
                subsample=params.get("subsample", 1.0),
                colsample_bytree=params.get("colsample_bytree", 1.0),
                eval_metric=params.get("eval_metric", "rmse"),
                random_state=42,
                n_jobs=-1,
                early_stopping_rounds=params.get("early_stopping_rounds", 20),
            )
        except ImportError:
            raise ImportError("XGBoost is not installed. Please install it to use this model.")
            
    elif model_type == "xgboost_classifier":
        # Binary classification (target must be 0/1).
        # scale_pos_weight corrects for class imbalance: set to n_neg/n_pos.
        # Use "auto" to let the pipeline compute it from training labels.
        try:
            from xgboost import XGBClassifier
            return XGBClassifier(
                n_estimators=params.get("n_estimators", 100),
                max_depth=params.get("max_depth", 3),
                learning_rate=params.get("learning_rate", 0.1),
                subsample=params.get("subsample", 1.0),
                colsample_bytree=params.get("colsample_bytree", 1.0),
                scale_pos_weight=params.get("scale_pos_weight", 1.0),
                eval_metric=params.get("eval_metric", "logloss"),
                random_state=42,
                n_jobs=-1,
                early_stopping_rounds=params.get("early_stopping_rounds", 20),
            )
        except ImportError:
            raise ImportError("XGBoost is not installed.")

    elif model_type == "random_forest_classifier":
        return RandomForestClassifier(
            n_estimators=params.get("n_estimators", 500),
            max_depth=params.get("max_depth", None),
            max_features=params.get("max_features", "sqrt"),
            min_samples_leaf=params.get("min_samples_leaf", 20),
            n_jobs=-1,
            random_state=42,
        )

    elif model_type == "extra_trees_classifier":
        return ExtraTreesClassifier(
            n_estimators=params.get("n_estimators", 500),
            max_depth=params.get("max_depth", None),
            max_features=params.get("max_features", "sqrt"),
            min_samples_leaf=params.get("min_samples_leaf", 20),
            n_jobs=-1,
            random_state=42,
        )

    elif model_type == "mlp_classifier":
        hidden = params.get("hidden_layer_sizes", (128, 64, 32))
        if isinstance(hidden, list):
            hidden = tuple(hidden)
        return Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(
                hidden_layer_sizes=hidden,
                activation=params.get("activation", "relu"),
                solver=params.get("solver", "adam"),
                learning_rate_init=params.get("learning_rate_init", 1e-3),
                max_iter=params.get("max_iter", 300),
                early_stopping=True,
                validation_fraction=0.1,
                n_iter_no_change=15,
                random_state=42,
            ))
        ])

    elif model_type == "lightgbm_classifier":
        # V9: LightGBM — different regularization, often generalizes better than XGBoost
        # on small/medium tabular datasets.
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier(
                n_estimators=params.get("n_estimators", 500),
                max_depth=params.get("max_depth", 3),
                learning_rate=params.get("learning_rate", 0.05),
                subsample=params.get("subsample", 0.8),
                colsample_bytree=params.get("colsample_bytree", 0.8),
                min_child_samples=params.get("min_child_samples", 20),
                reg_alpha=params.get("reg_alpha", 0.0),
                reg_lambda=params.get("reg_lambda", 1.0),
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
        except ImportError:
            raise ImportError("LightGBM is not installed. Run: conda install -c conda-forge lightgbm")

    else:
        raise ValueError(f"Unknown model type: {model_type}")
