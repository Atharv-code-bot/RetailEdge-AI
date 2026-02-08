# app/data/cleaners/clean_common.py

import pandas as pd


def drop_null_ids(df: pd.DataFrame, id_columns: list) -> pd.DataFrame:
    return df.dropna(subset=id_columns)


def enforce_positive_values(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Ensures columns are numeric and removes rows with negative values
    """
    for col in columns:
        # Convert to numeric, invalid parsing becomes NaN
        df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop rows where value is NaN or negative
        df = df[df[col].notna()]
        df = df[df[col] >= 0]

    return df
