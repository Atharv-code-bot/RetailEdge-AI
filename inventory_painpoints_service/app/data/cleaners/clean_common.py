# app/data/cleaners/clean_common.py
#
# Shared cleaning utilities used by all table-specific cleaners.
# No business logic here — pure data quality enforcement.

import pandas as pd


def drop_null_ids(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Drop rows where any required ID/key column is null."""
    if df.empty:
        return df
    before = len(df)
    df = df.dropna(subset=columns)
    dropped = before - len(df)
    if dropped > 0:
        print(f"  [clean] drop_null_ids: dropped {dropped} rows with nulls in {columns}")
    return df


def enforce_positive_values(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Coerce columns to numeric and keep only rows where value >= 0.
    Rows with non-numeric or negative values are removed.
    """
    if df.empty:
        return df
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        before = len(df)
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[df[col] >= 0]
        dropped = before - len(df)
        if dropped > 0:
            print(f"  [clean] enforce_positive_values: dropped {dropped} rows on '{col}'")
    return df


def enforce_date_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Parse a date column and drop rows where parsing fails."""
    if df.empty or column not in df.columns:
        return df
    df = df.copy()
    before = len(df)
    df[column] = pd.to_datetime(df[column], errors="coerce")
    df = df.dropna(subset=[column])
    dropped = before - len(df)
    if dropped > 0:
        print(f"  [clean] enforce_date_column: dropped {dropped} rows on '{column}'")
    return df


def drop_duplicate_keys(df: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Remove duplicate rows based on key columns. Keep first occurrence."""
    if df.empty:
        return df
    before = len(df)
    df = df.drop_duplicates(subset=keys)
    dropped = before - len(df)
    if dropped > 0:
        print(f"  [clean] drop_duplicate_keys: dropped {dropped} duplicates on {keys}")
    return df
