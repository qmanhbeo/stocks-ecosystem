# %%
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# %%
df = pd.read_parquet("gia_lich_su_FPT_1D.parquet")
df = df.sort_values("time").reset_index(drop=True)
df.head()

# %%
X = 5 # predict X day ahead
df[f"future_return_{X}d"] = df["close"].shift(-X) / df["close"] - 1

for i in range(1, 101):  # 1 → 10
    df[f"past_return_{i}d"] = df["close"] / df["close"].shift(i) - 1
    df[f"ma_{i}"] = df["close"].rolling(i).mean()

df = df.dropna().copy()

# %%
df = df[df["time"]>="2016-01-01"].copy()  # filter out old data. 10 years kept
df = df.sort_values("time").copy()

df.tail()

# %%
# Features: open, high, low, close, volume
feature_cols = ["open", "high", "low", "close", "volume"] + \
               [f"past_return_{i}d" for i in range(1, 11)] + \
               [f"ma_{i}" for i in range(1, 11)]
y = f"future_return_{X}d"

# %%
# Keep the last 15% for testing, and split the rest into train/val
n = len(df)

train_end = int(n * 0.70)
val_end = int(n * 0.85)

train_df = df.iloc[:train_end].copy()
val_df = df.iloc[train_end:val_end].copy()
test_df = df.iloc[val_end:].copy()   # keep untouched for now

X_train = train_df[feature_cols]
y_train = train_df[y]

X_val = val_df[feature_cols]
y_val = val_df[y]

X_test = test_df[feature_cols]
y_test = test_df[y]

# %% [markdown]
# # Model choice

# %%
# Uncomment to choose model
# Linear Regression
# model = LinearRegression()

# Simple MLP with 2 hidden layers
# model = MLPRegressor(
#     hidden_layer_sizes=(64, 32),   # 2 hidden layers
#     activation="relu",
#     solver="adam",
#     max_iter=5000,
#     random_state=42
# )

# Simple MLP with 2 hidden layers + StandardScaler (scale by mean and std)
model = Pipeline([
    ("scaler", StandardScaler()),
    ("nn", MLPRegressor(
        hidden_layer_sizes=(256, 64, 32),
        activation="relu",
        solver="adam",
        max_iter=5000,
        random_state=42
    ))
])

# XGBoost Regressor
# from xgboost import XGBRegressor
# model = XGBRegressor(
#     n_estimators=500,
#     max_depth=1024,
#     learning_rate=0.05,
#     subsample=0.8,
#     colsample_bytree=0.8,
#     random_state=42
# )


# %%
# Train the model on training data
model.fit(X_train, y_train)

# %%
val_pred = model.predict(X_val)

# %%
val_direction_acc = ((val_pred > 0) == (y_val > 0)).mean()
print("Validation direction accuracy:", val_direction_acc)
pred_val = model.predict(X_val)

print("MAE:", mean_absolute_error(y_val, pred_val))
print("MSE:", mean_squared_error(y_val, pred_val))
print("R^2 :", r2_score(y_val, pred_val))

results = val_df[["time", y]].copy()
results[f"pred_{y}"] = pred_val
results.head(20)

# %% [markdown]
# 


