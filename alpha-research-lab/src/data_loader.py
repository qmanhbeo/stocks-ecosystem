import pandas as pd
import numpy as np
from typing import Tuple

def load_data(file_path: str, start_date: str = "2016-01-01") -> pd.DataFrame:
    """Loads the parquet file and filters by date."""
    df = pd.read_parquet(file_path)
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= start_date].copy()
    df = df.sort_values("time").copy()
    return df

def split_data(df: pd.DataFrame, 
               test_size: float = 0.15, 
               val_size: float = 0.15) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits the data into train, validation, and test sets based on time."""
    n = len(df)
    train_end = int(n * (1 - test_size - val_size))
    val_end = int(n * (1 - test_size))

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()
    
    return train_df, val_df, test_df
